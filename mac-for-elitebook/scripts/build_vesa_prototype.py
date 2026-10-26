#!/usr/bin/env python3
"""Assemble and statically validate a non-deployable VESA prototype locally."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import plistlib
import shutil
import struct
import subprocess
import zipfile

from fetch_assets import fetch
from validate_efi import validate

ROOT = Path(__file__).resolve().parents[1]
GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"


def extract(archive, prefix, destination):
    """Extract only a selected archive subtree, refusing special or unsafe paths."""
    with zipfile.ZipFile(archive) as package:
        for info in package.infolist():
            if not info.filename.startswith(prefix):
                continue
            relative = PurePosixPath(info.filename[len(prefix):])
            if relative.is_absolute() or ".." in relative.parts or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError("Unsafe zip member")
            if info.is_dir():
                continue
            path = destination.joinpath(*relative.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(package.read(info))


def main():
    recipe = json.loads((ROOT / "configs/vesa-prototype.json").read_text())
    sources = json.loads((ROOT / "manifests/core-sources.json").read_text())["sources"]
    sources += json.loads((ROOT / "manifests/vesa-assets.json").read_text())["sources"]
    needed = ("OpenCorePkg", "Lilu", "VirtualSMC", "VoodooPS2", "WhateverGreen")
    assets = {}
    for name in needed:
        source = next(s for s in sources if s["name"] == name)
        receipt, = fetch(source)
        assets[name] = receipt
    if assets["OpenCorePkg"]["tag"] != recipe["opencore_version"]:
        raise ValueError("OpenCore recipe and source pin disagree")
    # Only our generated prototype tree is replaced; no disk/USB/EFI deployment.
    build = ROOT / "build/vesa-prototype"
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    (build / "Licenses").mkdir()
    for name, receipt in assets.items():
        if receipt.get("license"):
            shutil.copyfile(ROOT / receipt["license"]["local_path"], build / "Licenses" / (name + ".txt"))
    oc = build / "EFI/OC"
    extract(ROOT / assets["OpenCorePkg"]["local_path"], "X64/EFI/", build / "EFI")
    # Remove bundled optional drivers/tools, not arbitrary user files.
    shutil.rmtree(oc / "Drivers")
    shutil.rmtree(oc / "Tools")
    (oc / "Drivers").mkdir()
    (oc / "Tools").mkdir()
    archive = ROOT / assets["OpenCorePkg"]["local_path"]
    with zipfile.ZipFile(archive) as package:
        config = plistlib.loads(package.read("Docs/Sample.plist"))
        validator = build / "ocvalidate.linux"
        validator.write_bytes(package.read("Utilities/ocvalidate/ocvalidate.linux"))
        validator.chmod(0o755)
        for name in recipe["drivers"]:
            (oc / "Drivers" / name).write_bytes(package.read("X64/EFI/OC/Drivers/" + name))
    for source, prefix in (("Lilu", ""), ("VirtualSMC", "Kexts/"), ("VoodooPS2", ""), ("WhateverGreen", "")):
        bundle = {"Lilu": "Lilu.kext", "VirtualSMC": "VirtualSMC.kext", "VoodooPS2": "VoodooPS2Controller.kext", "WhateverGreen": "WhateverGreen.kext"}[source]
        extract(ROOT / assets[source]["local_path"], prefix + bundle + "/", oc / "Kexts" / bundle)
    ps2_plugins = oc / "Kexts/VoodooPS2Controller.kext/Contents/PlugIns"
    for path in ps2_plugins.iterdir():
        if path.name != "VoodooPS2Keyboard.kext":
            shutil.rmtree(path)
    (oc / "ACPI").mkdir(exist_ok=True)
    acpi_results = []
    for name in recipe["acpi"]:
        prefix = oc / "ACPI" / Path(name).stem
        result = subprocess.run(["iasl", "-p", str(prefix), str(ROOT / "acpi" / name)], capture_output=True, check=True)
        (build / (name + ".log")).write_bytes(result.stdout + result.stderr)
        acpi_results.append({"source": "acpi/" + name, "sha256": hashlib.sha256((ROOT / "acpi" / name).read_bytes()).hexdigest(), "exit_code": result.returncode})
    for section in ("ACPI", "Booter", "Kernel"):
        for key in ("Add", "Delete", "Patch", "Block", "Force", "MmioWhitelist"):
            if key in config[section]:
                config[section][key] = []
    config["ACPI"]["Add"] = [{"Comment": "HP PR00 Darwin plugin-type; untested", "Enabled": True, "Path": Path(n).with_suffix(".aml").name} for n in recipe["acpi"]]
    config["DeviceProperties"] = {"Add": {}, "Delete": {}}
    config["Booter"]["Quirks"].update(EnableWriteUnprotector=False, RebuildAppleMemoryMap=True, SyncRuntimePermissions=True, SetupVirtualMap=False, ProtectUefiServices=True)
    config["Kernel"]["Emulate"].update(Cpuid1Data=struct.pack("<I", int(recipe["cpu_spoof_eax"], 16)) + bytes(12), Cpuid1Mask=b"\xff" * 4 + bytes(12), MinKernel=recipe["kernel_range"][0], MaxKernel=recipe["kernel_range"][1])
    config["Kernel"]["Quirks"].update(AppleXcpmCfgLock=True, AppleXcpmExtraMsrs=True, ProvideCurrentCpuInfo=True, DisableIoMapper=True, PanicNoKextDump=True, DisableLinkeditJettison=True, XhciPortLimit=False)
    for bundle in recipe["kexts"]:
        plist = "Contents/Info.plist"
        info = plistlib.loads((oc / "Kexts" / bundle / plist).read_bytes())
        config["Kernel"]["Add"].append({"Arch": "x86_64", "BundlePath": bundle, "Comment": "VESA prototype; HP runtime untested", "Enabled": True,
                                        "ExecutablePath": "Contents/MacOS/" + info["CFBundleExecutable"], "PlistPath": plist,
                                        "MinKernel": recipe["kernel_range"][0], "MaxKernel": recipe["kernel_range"][1]})
    config["Misc"]["Tools"] = []
    config["Misc"]["Entries"] = []
    config["Misc"]["BlessOverride"] = []
    config["Misc"]["Boot"].update(LauncherOption="Disabled", ShowPicker=True, HideAuxiliary=False, Timeout=0, PickerMode="Builtin", HibernateMode="None")
    config["Misc"]["Security"].update(AllowSetDefault=False, SecureBootModel="Disabled", Vault="Optional", ScanPolicy=0, DmgLoading="Signed")
    config["Misc"]["Debug"].update(AppleDebug=True, ApplePanic=True, DisableWatchDog=True, Target=67, SysReport=False)
    config["NVRAM"]["Add"] = {GUID: {"boot-args": recipe["boot_args"], "csr-active-config": bytes(4), "prev-lang:kbd": b"ja-JP:0"}}
    config["NVRAM"]["Delete"] = {}
    config["NVRAM"]["WriteFlash"] = False
    config["NVRAM"]["LegacySchema"] = {}
    config["PlatformInfo"]["Generic"].update(SystemProductName=recipe["system_product_name"], SystemSerialNumber="", MLB="", SystemUUID="00000000-0000-0000-0000-000000000000", ROM=bytes(6))
    config["PlatformInfo"]["UpdateNVRAM"] = False
    config["UEFI"]["Drivers"] = [{"Arguments": "", "Comment": "Pinned OpenCore driver", "Enabled": True, "HideVerbose": False, "LoadEarly": False, "Path": name} for name in recipe["drivers"]]
    config["UEFI"]["Input"]["KeySupport"] = True
    config["UEFI"]["Output"].update(ProvideConsoleGop=True, Resolution="Max")
    config["UEFI"]["Quirks"].update(RequestBootVarRouting=True, ForceOcWriteFlash=False)
    plist_path = oc / "config.plist"
    plist_path.write_bytes(plistlib.dumps(config, sort_keys=False))
    result = subprocess.run([str(validator), str(plist_path)], capture_output=True)
    (build / "ocvalidate.log").write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit((result.stdout + result.stderr).decode())
    # Check every enabled reference; ocvalidate alone does not check the filesystem.
    references = [oc / "Drivers" / n for n in recipe["drivers"]]
    references += [oc / "ACPI" / item["Path"] for item in config["ACPI"]["Add"]]
    for item in config["Kernel"]["Add"]:
        references.extend(oc / "Kexts" / item["BundlePath"] / item[k] for k in ("PlistPath", "ExecutablePath"))
    if any(not p.is_file() for p in references):
        raise ValueError("Enabled configuration reference missing from build tree")
    static_validation = validate(build)
    report = {"schema_version": 1, "status": recipe["status"], "opencore_version": recipe["opencore_version"],
              "ocvalidate_exit_code": result.returncode, "acpi": acpi_results, "assets": list(assets.values()),
              "referenced_files_checked": len(references), "static_validation": static_validation,
              "deployment_blockers": recipe["deployment_blockers"],
              "files": [{"path": str(p.relative_to(build)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((build / "EFI").rglob("*")) if p.is_file()]}
    (build / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (build / "NOT-DEPLOYABLE.txt").write_text("Offline prototype only. No HP boot test. Blank identities and incomplete EC/USB/media review. Do not copy to a USB or internal EFI. See configs/vesa-prototype.json and docs/vesa-prototype.md.\n")
    print(f"Offline prototype: {build.relative_to(ROOT)}; ocvalidate 0; {len(references)} references exist. Not deployment-ready.")


if __name__ == "__main__":
    main()
