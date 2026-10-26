#!/usr/bin/env python3
"""Audit HP Recovery storage/USB/keyboard matching without booting or patching.

Uses the verified Apple KC/DMG and a private candidate. Matching declarations
and available utilities do not prove that a driver probes or works on HP.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
KC_SHA = "c80161fa3065883753fc285339281361a8469cbb6fb27653c88e2a22eb4807a4"
DMG_SHA = "edddd0d5869caaa12e29e6996a04f11590280580976a119dbd42c24fa62fe18e"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def private(value):
    path = (ROOT / value).resolve(strict=True)
    if not path.is_relative_to(ROOT / ".local"):
        raise ValueError("Inputs must stay in .local")
    return path


def kc_plists(data):
    magic, _, _, filetype, count, commands_size = struct.unpack_from("<6I", data)
    if magic != 0xFEEDFACF or filetype != 0xC or 32 + commands_size > len(data):
        raise ValueError("Expected a 64-bit KC fileset")
    position = 32
    for _ in range(count):
        command, size = struct.unpack_from("<II", data, position)
        if size < 8 or position + size > 32 + commands_size:
            raise ValueError("Malformed KC load command")
        if command == 0x19:
            segment = struct.unpack_from("<II16sQQQQiiII", data, position)
            if segment[2].rstrip(b"\0") == b"__PRELINK_INFO":
                start, length = segment[5:7]
                if start + length > len(data):
                    raise ValueError("KC plist outside file")
                return plistlib.loads(data[start:start + length].rstrip(b"\0"))["_PrelinkInfoDictionary"]
        position += size
    raise ValueError("No KC prelink metadata")


def class_match(declaration, pci_class):
    # IOPCI class matching uses class/subclass/prog-if in bits 31..8.
    for token in declaration.split():
        parts = token.split("&")
        value = int(parts[0], 16)
        mask = int(parts[1], 16) if len(parts) == 2 else 0xFFFFFFFF
        if ((pci_class << 8) & mask) == (value & mask):
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--efi", required=True, help="Private directory containing EFI/")
    parser.add_argument("--pci-classes", required=True, help="Saved read-only BDF/class observation")
    args = parser.parse_args()
    efi, classes = private(args.efi), private(args.pci_classes)
    hardware = json.loads((ROOT / "hardware/elite-dragonfly-g2.json").read_text())
    capture = private(hardware["capture_directory"])
    kc = ROOT / ".local/recovery-repair/BootKernelExtensions.kc"
    dmg = ROOT / ".local/recovery-repair/recovery/BaseSystem.dmg"
    if sha(kc) != KC_SHA or sha(dmg) != DMG_SHA:
        raise ValueError("Verified Apple inputs differ")
    entries = {v["CFBundleIdentifier"]: v for v in kc_plists(kc.read_bytes())}
    observations = {bdf: int(value, 16) for bdf, value in (line.split() for line in classes.read_text().splitlines())}
    config_path = efi / "EFI/OC/config.plist"
    config = plistlib.loads(config_path.read_bytes())
    enabled = [v["BundlePath"] for v in config["Kernel"]["Add"] if v["Enabled"]]
    xhci_id = "com.apple.driver.usb.AppleUSBXHCIPCI"
    nvme_id = "com.apple.iokit.IONVMeFamily"
    xhci = entries[xhci_id]["IOKitPersonalities"]["AppleUSBXHCIPCI"]
    nvme = entries[nvme_id]["IOKitPersonalities"]["GenericNVMeSSD"]
    controllers = []
    for bdf, ident in (("0000:00:0d.0", "8086:9a13"), ("0000:00:14.0", "8086:a0ed")):
        controllers.append({"pci_address": bdf, "pci_id": ident, "observed_pci_class": hex(observations[bdf]),
                            "generic_class_match": class_match(xhci["IOPCIClassMatch"], observations[bdf]),
                            "class": xhci["IOClass"], "bundle": xhci_id})
    storage = {"pci_id": hardware["storage"]["pci_id"], "observed_pci_class": hex(observations["0000:55:00.0"]),
               "generic_class_match": class_match(nvme["IOPCIClassMatch"], observations["0000:55:00.0"]),
               "class": nvme["IOClass"], "bundle": nvme_id}
    ps2_bundle = "VoodooPS2Controller.kext"
    keyboard_bundle = ps2_bundle + "/Contents/PlugIns/VoodooPS2Keyboard.kext"
    ps2_path = efi / "EFI/OC/Kexts" / ps2_bundle / "Contents/Info.plist"
    ps2 = plistlib.loads(ps2_path.read_bytes())
    dsdt = capture / "analysis/acpi/DSDT.dsl"
    block = re.search(r"Device \(PS2K\).*?(?=\n        Device)", dsdt.read_text(), re.S)
    if not block:
        raise ValueError("Expected HP keyboard device")
    compatible = re.search(r'Name \(_CID, EisaId \("([A-Z0-9]+)"\)', block[0])[1]
    keyboard = {"acpi_device": "PS2K", "compatible_id": compatible,
                "controller_iok_name_match": compatible in ps2["IOKitPersonalities"]["ACPI PS/2 Nub"]["IONameMatch"],
                "controller_enabled": ps2_bundle in enabled, "keyboard_plugin_enabled": keyboard_bundle in enabled,
                "controller_precedes_keyboard": ps2_bundle in enabled and keyboard_bundle in enabled and enabled.index(ps2_bundle) < enabled.index(keyboard_bundle),
                "device_has_sta_method": "Method (_STA" in block[0], "version": ps2["CFBundleVersion"]}
    tools_pin = ROOT / ".local/recovery-repair/extraction-toolchain.json"
    tools = json.loads(tools_pin.read_text())
    sevenzip = Path(tools["binary_path"])
    if sha(sevenzip) != tools["binary_sha256"]:
        raise ValueError("Pinned DMG reader changed")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="recovery-path-audit-", dir=ROOT / ".local/install-prep"))
    result = subprocess.run([str(sevenzip), "l", "-slt", str(dmg)], capture_output=True, check=True, timeout=120)
    (out / "dmg-listing.txt").write_bytes(result.stdout)
    paths = set(re.findall(r"^Path = (.+)$", result.stdout.decode(), re.M))
    required = ("usr/bin/hdiutil", "usr/sbin/diskutil", "usr/libexec/PlistBuddy",
                "System/Library/Extensions/exfat.kext/Contents/Info.plist")
    available = {p: any(v.endswith("/" + p) for v in paths) for p in required}
    report = {"schema_version": 1, "status": "static_driver_matching_and_recovery_utilities_only",
              "kernel_collection_sha256": KC_SHA, "base_system_sha256": DMG_SHA,
              "candidate_config_sha256": sha(config_path), "pci_class_observation_sha256": sha(classes),
              "usb_controllers": controllers, "nvme": storage, "keyboard": keyboard,
              "recovery_utilities_present": available,
              "hfs_kc_bundle_present": "com.apple.filesystems.hfs.kext" in entries,
              "usb_mass_storage_bundle_present": "com.apple.iokit.IOUSBMassStorageDriver" in entries,
              "candidate_enabled_kexts": enabled,
              "evidence": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in
                           (classes, dsdt, ps2_path, out / "dmg-listing.txt")],
              "runner_sha256": sha(Path(__file__)), "hp_runtime_tested": False,
              "limit": "Class/name matching is a necessary declaration check, not successful driver probe, USB port mapping, NVMe operations, keyboard input, image attachment or installation."}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str((out / "report.json").relative_to(ROOT)), **report}, indent=2))


if __name__ == "__main__":
    main()
