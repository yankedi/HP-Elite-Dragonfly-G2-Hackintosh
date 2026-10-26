#!/usr/bin/env python3
"""Launch and inspect a local, disk-isolated Tahoe recovery VM (no installation).

Only regular image files in .local are attached. This profile is independent of
the HP EFI. Kext injection, kernel initialization and device function require
separate observations; a successful launch or ocvalidate proves none of them.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import zipfile
import zlib

from check_nonboot_vm import qmp_command, run_logged
from check_recovery_probe import ARCHIVE, ARCHIVE_SHA, ROOT, SCRIPT_SHA

CPU = "Haswell-noTSX,stepping=3,-pcid,-tsc-deadline,-invpcid"
GUID = "7C436110-AB2A-4BBB-A880-FE41995C9F82"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def private(path):
    path = (ROOT / path).resolve(strict=True)
    if not path.is_relative_to(ROOT / ".local"):
        raise ValueError("VM images and reports must be inside private .local")
    return path


def png_from_ppm(source):
    magic, shape, maximum, raw = source.read_bytes().split(b"\n", 3)
    if magic != b"P6" or maximum != b"255":
        raise ValueError("Unexpected QEMU screen format")
    width, height = map(int, shape.split())
    if len(raw) != width * height * 3:
        raise ValueError("Truncated QEMU screenshot")
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    rows = b"".join(b"\0" + raw[i*width*3:(i+1)*width*3] for i in range(height))
    source.with_suffix(".png").write_bytes(b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def launch(args):
    tools = {name: Path(getattr(args, name)).resolve(strict=True) for name in ("qemu", "ovmf_code", "ovmf_vars")}
    if any(not path.is_file() for path in tools.values()):
        raise ValueError("Tool and firmware inputs must be regular files")
    recovery = private(args.recovery)
    if sha(ARCHIVE) != ARCHIVE_SHA:
        raise ValueError("Pinned OpenCore archive differs")
    root = ROOT / ".local/recovery-vm"
    root.mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=root))
    with zipfile.ZipFile(ARCHIVE) as archive:
        verifier = run / "macrecovery.py"
        verifier.write_bytes(archive.read("Utilities/macrecovery/macrecovery.py"))
        if sha(verifier) != SCRIPT_SHA:
            raise ValueError("Pinned Apple chunk verifier differs")
        spec = importlib.util.spec_from_file_location("pinned_macrecovery", verifier)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Exhausting this generator verifies the RSA signature, not just hashes.
        chunks = list(module.verify_chunklist(recovery / "BaseSystem.chunklist"))
        with (recovery / "BaseSystem.dmg").open("rb") as image:
            for length, expected in chunks:
                data = image.read(length)
                if len(data) != length or hashlib.sha256(data).digest() != expected:
                    raise ValueError("Recovery differs from signed chunklist")
            if image.read(1):
                raise ValueError("Recovery has trailing data")
        esp = run / "EFI"
        (esp / "BOOT").mkdir(parents=True)
        oc = esp / "OC"
        for directory in ("Drivers", "Tools", "ACPI", "Kexts"):
            (oc / directory).mkdir(parents=True)
        for name in (".contentVisibility", ".contentFlavour"):
            (esp / "BOOT" / name).write_bytes(archive.read("X64/EFI/BOOT/" + name))
        (esp / "BOOT/BOOTX64.EFI").write_bytes(archive.read("X64/EFI/BOOT/BOOTx64.efi"))
        (oc / "OpenCore.efi").write_bytes(archive.read("X64/EFI/OC/OpenCore.efi"))
        config = plistlib.loads(archive.read("Docs/Sample.plist"))
        for section in ("ACPI", "Booter", "Kernel"):
            for field in ("Add", "Delete", "Patch", "Block", "Force", "MmioWhitelist"):
                if field in config[section]:
                    config[section][field] = []
        config["DeviceProperties"] = {"Add": {}, "Delete": {}}
        config["Misc"].update(Entries=[], Tools=[], BlessOverride=[])
        config["Misc"]["Boot"].update(LauncherOption="Disabled", ShowPicker=True, HideAuxiliary=False, Timeout=3, PickerMode="Builtin")
        config["Misc"]["Security"].update(AllowSetDefault=False, SecureBootModel="Disabled", Vault="Optional", ScanPolicy=0, DmgLoading="Signed")
        config["Misc"]["Debug"].update(Target=75, DisplayLevel=0x80000042, SysReport=False, AppleDebug=True, ApplePanic=True)
        config["Misc"]["Serial"]["Init"] = True
        config["Booter"]["Quirks"].update(EnableWriteUnprotector=False, RebuildAppleMemoryMap=True, SyncRuntimePermissions=True,
                                          SetupVirtualMap=False, ProtectUefiServices=True)
        config["Kernel"]["Quirks"].update(DisableIoMapper=True, DisableLinkeditJettison=True, PanicNoKextDump=True, ProvideCurrentCpuInfo=True)
        kexts = []
        for source in args.kext:
            source = Path(source).resolve(strict=True)
            if source.suffix != ".kext" or not source.is_dir():
                raise ValueError("Kext inputs must be bundle directories")
            target = oc / "Kexts" / source.name
            shutil.copytree(source, target)
            info_path = target / "Contents/Info.plist"
            info = plistlib.loads(info_path.read_bytes())
            executable = "Contents/MacOS/" + info["CFBundleExecutable"]
            binary = (target / executable).resolve(strict=True)
            if not binary.is_relative_to(target.resolve()) or not binary.is_file():
                raise ValueError("Invalid kext executable path")
            config["Kernel"]["Add"].append({"Arch": "x86_64", "BundlePath": source.name,
                "Comment": "Isolated recovery experiment", "Enabled": True, "ExecutablePath": executable,
                "PlistPath": "Contents/Info.plist", "MinKernel": "25.0.0", "MaxKernel": "25.99.99"})
            kexts.append({"bundle": source.name, "id": info["CFBundleIdentifier"], "version": info["CFBundleVersion"],
                          "executable_sha256": sha(binary), "plist_sha256": sha(info_path)})
        config["NVRAM"].update(Add={GUID: {"boot-args": "-v keepsyms=1 debug=0x100 serial=3 -no_compat_check"
                + (" -s" if args.single_user else "") + (" -liluforce" if args.force_lilu else "")
                + (" -liludbgall" if args.lilu_debug else ""), "csr-active-config": bytes(4), "prev-lang:kbd": b"en-US:0"}},
                Delete={}, LegacySchema={}, WriteFlash=False)
        config["PlatformInfo"].update(Automatic=True, UpdateDataHub=True, UpdateSMBIOS=True, UpdateNVRAM=False)
        config["PlatformInfo"]["Generic"].update(SystemProductName="MacPro7,1", SystemSerialNumber="", MLB="",
                SystemUUID="00000000-0000-0000-0000-000000000000", ROM=bytes(6))
        config["UEFI"]["Drivers"] = []
        for name in ("OpenRuntime.efi", "OpenHfsPlus.efi"):
            (oc / "Drivers" / name).write_bytes(archive.read("X64/EFI/OC/Drivers/" + name))
            config["UEFI"]["Drivers"].append({"Arguments": "", "Comment": "Pinned virtual test", "Enabled": True,
                "HideVerbose": False, "LoadEarly": False, "Path": name})
        config["UEFI"]["Output"].update(ProvideConsoleGop=True, Resolution="1024x768")
        config["UEFI"]["Input"]["KeySupport"] = True
        config_path = oc / "config.plist"
        config_path.write_bytes(plistlib.dumps(config, sort_keys=False))
        validator = run / "ocvalidate"
        validator.write_bytes(archive.read("Utilities/ocvalidate/ocvalidate.linux"))
        validator.chmod(0o755)
        validation = run_logged([str(validator), str(config_path)], run, "ocvalidate")
    media = run / "com.apple.recovery.boot"
    if not args.raw_system:
        media.mkdir()
        for name in ("BaseSystem.dmg", "BaseSystem.chunklist"):
            shutil.copyfile(recovery / name, media / name)
    disk = run / "esp.img"
    with disk.open("wb") as stream:
        stream.truncate((128 if args.raw_system else 1280) * 2**20)
    setup = [run_logged([shutil.which("mkfs.vfat"), "-F", "32", str(disk)], run, "format")]
    for directory in ([esp] if args.raw_system else [esp, media]):
        setup.append(run_logged([shutil.which("mcopy"), "-i", str(disk), "-s", str(directory), "::/"], run, "copy-" + directory.name))
    variables = run / "OVMF_VARS.fd"
    shutil.copyfile(tools["ovmf_vars"], variables)
    raw_drive = []
    if args.raw_system:
        qemu_img = tools["qemu"].with_name("qemu-img")
        if not qemu_img.is_file():
            raise ValueError("qemu-img must be alongside QEMU for raw conversion")
        tools["qemu_img"] = qemu_img
        raw = run / "BaseSystem.raw"
        setup.append(run_logged([str(qemu_img), "convert", "-f", "dmg", "-O", "raw",
                                 str(recovery / "BaseSystem.dmg"), str(raw)], run, "convert"))
        # A disposable raw derivative; no host block devices or install target.
        raw_drive = ["-drive", f"id=BaseSystem,if=none,format=raw,file={raw}", "-device", "ide-hd,bus=sata.1,drive=BaseSystem"]
    extra_drives = []
    for index, drive in enumerate(getattr(args, "scratch_drives", []), start=2):
        path = private(drive["path"])
        if not path.is_file() or index > 5:
            raise ValueError("Scratch drives must be private regular images within SATA capacity")
        serial = drive["serial"]
        if not serial.isascii() or not serial.isalnum():
            raise ValueError("Scratch disk serial must be ASCII alphanumeric")
        # ide-hd requires a writable backend; snapshot protects the input file.
        extra_drives += ["-drive", f"id=scratch{index},if=none,format=raw,file={path},snapshot={'on' if drive['readonly'] else 'off'}",
                         "-device", f"ide-hd,bus=sata.{index},drive=scratch{index},serial={serial}"]
    command = [str(tools["qemu"]), "-no-user-config", "-machine", "q35", "-accel", "tcg,thread=multi", "-cpu", CPU, "-m", "4096", "-smp", str(args.cpus),
        "-drive", f'if=pflash,format=raw,unit=0,readonly=on,file={tools["ovmf_code"]}',
        "-drive", f"if=pflash,format=raw,unit=1,file={variables}",
        "-device", "ich9-ahci,id=sata", "-drive", f"id=ESP,if=none,format=raw,file={disk}",
        "-device", "ide-hd,bus=sata.0,drive=ESP", *raw_drive, *extra_drives, "-device", "qemu-xhci,id=xhci",
        "-device", "usb-kbd,bus=xhci.0", "-device", "usb-tablet,bus=xhci.0",
        "-nic", "none", "-vga", "std", "-display", "none", "-serial", f'file:{run / "serial.log"}',
        "-qmp", f'unix:{run / "qmp.sock"},server=on,wait=off', "-no-reboot"]
    with (run / "qemu.stdout").open("wb") as out, (run / "qemu.stderr").open("wb") as err:
        process = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=True)
    report = {"schema_version": 1, "runner_sha256": sha(__file__), "pid": process.pid, "command": command,
              "opencore_archive_sha256": ARCHIVE_SHA, "ocvalidate": validation, "setup": setup,
              "config_sha256": sha(config_path), "kext_inputs": kexts, "cpu": CPU,
              "recovery_image_sha256": sha(recovery / "BaseSystem.dmg"), "chunklist_sha256": sha(recovery / "BaseSystem.chunklist"),
              "tools": {name: {"path": str(path), "sha256": sha(path)} for name, path in tools.items()},
              "single_user": args.single_user, "force_lilu": args.force_lilu, "lilu_debug": args.lilu_debug,
              "raw_system": args.raw_system, "cpus": args.cpus, "scratch_drives": getattr(args, "scratch_drives", []), "macos_installed": False, "network_attached": False,
              "physical_disks_attached": False, "passthrough_devices": [],
              "scope": "Launch only; assess observed serial/guest evidence separately"}
    (run / "launch.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"run": str(run.relative_to(ROOT)), "pid": process.pid}))


def control(args):
    run = private(args.run)
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(15)
        client.connect(str(run / "qmp.sock"))
        with client.makefile("rwb") as stream:
            stream.readline()
            qmp_command(stream, "qmp_capabilities")
            if args.action == "screen":
                if not args.name.replace("-", "").replace("_", "").isalnum():
                    raise ValueError("Use a simple screenshot name")
                path = run / (args.name + ".ppm")
                result = qmp_command(stream, "screendump", {"filename": str(path)})
                if "return" in result:
                    png_from_ppm(path)
                    print(path.with_suffix(".png").relative_to(ROOT))
            elif args.action == "key":
                result = qmp_command(stream, "send-key", {"keys": [{"type": "qcode", "data": key} for key in args.keys.split("+")], "hold-time": 100})
            elif args.action == "type":
                shifted = {"_": "minus", ":": "semicolon", '"': "apostrophe", "|": "backslash", ">": "dot", "<": "comma",
                           "(": "9", ")": "0", "$": "4", "!": "1", "&": "7", "*": "8", "?": "slash", "+": "equal"}
                plain = {" ": "spc", "-": "minus", "=": "equal", "/": "slash", ".": "dot", ",": "comma",
                         ";": "semicolon", "'": "apostrophe", "\\": "backslash", "\n": "ret", "[": "bracket_left", "]": "bracket_right"}
                events = []
                for char in args.text:
                    shift = char.isupper() or char in shifted
                    key = shifted.get(char, plain.get(char, char.lower()))
                    if not (char in shifted or char in plain or char.isascii() and char.isalnum()):
                        raise ValueError(f"Unsupported guest keyboard character: {char!r}")
                    keys = (["shift"] if shift else []) + [key]
                    result = qmp_command(stream, "send-key", {"keys": [{"type": "qcode", "data": code} for code in keys], "hold-time": 15})
                    if "error" in result:
                        raise RuntimeError(result)
                    events.append(keys)
                    time.sleep(0.04)
                result = {"typed_characters": len(args.text), "events": events}
            elif args.action == "stop":
                result = qmp_command(stream, "quit")
            else:
                result = qmp_command(stream, "query-status")
            with (run / "control.jsonl").open("a") as log:
                log.write(json.dumps({"action": args.action, "keys": args.keys, "name": args.name,
                                      "text": args.text, "result": result}) + "\n")
            print(json.dumps({"typed_characters": result["typed_characters"]} if args.action == "type" else result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    start = commands.add_parser("launch")
    for name in ("qemu", "ovmf-code", "ovmf-vars", "recovery"):
        start.add_argument("--" + name, required=True)
    start.add_argument("--kext", action="append", default=[], help="Bundle path, repeated in dependency order")
    start.add_argument("--single-user", action="store_true")
    start.add_argument("--force-lilu", action="store_true", help="Override Lilu's documented single-user opt-out")
    start.add_argument("--lilu-debug", action="store_true", help="Request debug logs; needs DEBUG Lilu/plugin binaries")
    start.add_argument("--raw-system", action="store_true", help="Convert verified DMG to disposable raw; boot CoreServices bootbase automatically")
    start.add_argument("--cpus", type=int, choices=[1, 2], default=2)
    for name in ("screen", "key", "type", "stop", "status"):
        sub = commands.add_parser(name)
        sub.add_argument("--run", required=True)
        sub.add_argument("--name", default="screen")
        sub.add_argument("--keys", default="ret")
        sub.add_argument("--text", default="")
    args = parser.parse_args()
    if args.action == "launch":
        launch(args)
    else:
        control(args)


if __name__ == "__main__":
    main()
