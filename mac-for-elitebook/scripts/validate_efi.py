#!/usr/bin/env python3
"""Check prototype references, native architectures, dependencies and experiment isolation."""

import json
from pathlib import Path
import plistlib
import struct
import sys


def is_x64_macho(data):
    if data[:4] == b"\xcf\xfa\xed\xfe":
        return struct.unpack_from("<I", data, 4)[0] == 0x01000007
    if data[:4] in (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"):
        count = struct.unpack_from(">I", data, 4)[0]
        stride = 32 if data[:4] == b"\xca\xfe\xba\xbf" else 20
        if 8 + count * stride > len(data):
            return False
        return any(struct.unpack_from(">I", data, 8 + i * stride)[0] == 0x01000007 for i in range(count))
    return False


def is_x64_efi(data):
    if len(data) < 64 or data[:2] != b"MZ":
        return False
    offset = struct.unpack_from("<I", data, 60)[0]
    return offset + 24 <= len(data) and data[offset:offset+4] == b"PE\0\0" and struct.unpack_from("<H", data, offset + 4)[0] == 0x8664


def validate(build):
    oc = build / "EFI/OC"
    config = plistlib.loads((oc / "config.plist").read_bytes())
    ids = set()
    kext_results = []
    enabled = [item for item in config["Kernel"]["Add"] if item["Enabled"]]
    all_ids = {plistlib.loads((oc / "Kexts" / item["BundlePath"] / item["PlistPath"]).read_bytes())["CFBundleIdentifier"] for item in enabled}
    for item in enabled:
        base = oc / "Kexts" / item["BundlePath"]
        info = plistlib.loads((base / item["PlistPath"]).read_bytes())
        identifier = info["CFBundleIdentifier"]
        if identifier in ids:
            raise ValueError(f"Duplicate bundle identifier: {item['BundlePath']}")
        plist_only = not item["ExecutablePath"]
        if plist_only:
            if info.get("CFBundleExecutable") or not info.get("IOKitPersonalities"):
                raise ValueError(f"Plist-only injector must have personalities and no executable: {item['BundlePath']}")
        elif not is_x64_macho((base / item["ExecutablePath"]).read_bytes()):
            raise ValueError(f"Missing x86_64 Mach-O: {item['BundlePath']}")
        dependencies = info.get("OSBundleLibraries", {})
        for dependency in dependencies:
            if dependency in all_ids and dependency not in ids:
                raise ValueError(f"Kext dependency is not ordered before {identifier}: {dependency}")
            if not dependency.startswith("com.apple.") and dependency not in ids:
                raise ValueError(f"Third-party kext dependency is absent: {dependency}")
        ids.add(identifier)
        kext_results.append({"bundle": item["BundlePath"], "identifier": identifier,
                             "version": info["CFBundleVersion"], "x86_64": None if plist_only else True,
                             "plist_only": plist_only,
                             "third_party_dependencies_ordered": True})
    efi_files = [build / "EFI/BOOT/BOOTx64.efi", oc / "OpenCore.efi"]
    efi_files += [oc / "Drivers" / item["Path"] for item in config["UEFI"]["Drivers"] if item["Enabled"]]
    if any(not is_x64_efi(path.read_bytes()) for path in efi_files):
        raise ValueError("Enabled EFI image is not AMD64 PE/COFF")
    for item in config["ACPI"]["Add"]:
        if item["Enabled"]:
            data = (oc / "ACPI" / item["Path"]).read_bytes()
            if data[:4] != b"SSDT" or int.from_bytes(data[4:8], "little") != len(data) or sum(data) % 256:
                raise ValueError("Compiled SSDT signature, length or checksum is invalid")
    args = config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]
    if "-igfxvesa" not in args.split() or any(word in args for word in ("igfxtgl", "lilucpu", "igfxdvmt")):
        raise ValueError("VESA prototype contains a framebuffer experiment or lacks VESA request")
    if config["DeviceProperties"]["Add"] or any("WhateverXe" in item["BundlePath"] for item in enabled):
        raise ValueError("VESA experiment must not contain a GPU spoof or Xe accelerator")
    if config["Misc"]["Tools"] or config["Misc"]["Boot"]["LauncherOption"] != "Disabled" or config["NVRAM"]["WriteFlash"] or config["PlatformInfo"]["UpdateNVRAM"]:
        raise ValueError("Offline prototype unexpectedly enables launchers, tools or configured persistent variable writes")
    return {"kexts": kext_results, "x64_efi_images_checked": len(efi_files), "ssdt_checksums_valid": True,
            "vesa_experiment_isolated": True,
            "note": "Static checks do not exercise firmware, macOS linking, USB enumeration or runtime driver compatibility."}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: validate_efi.py <prototype-build-directory>")
    print(json.dumps(validate(Path(sys.argv[1]).resolve()), indent=2))
