#!/usr/bin/env python3
"""Boot pinned OpenCore and its real UEFI drivers in a disk-isolated QEMU VM."""

import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import socket
import subprocess
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TCG_CPU = "Haswell-noTSX,-pcid,-tsc-deadline,-invpcid"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_logged(command, directory, name, timeout=60):
    result = subprocess.run(command, capture_output=True, timeout=timeout)
    (directory / (name + ".stdout")).write_bytes(result.stdout)
    (directory / (name + ".stderr")).write_bytes(result.stderr)
    if result.returncode:
        raise RuntimeError(f"{name} exited {result.returncode}: {result.stderr.decode(errors='replace')[-3000:]}")
    return {"command": command, "exit_code": result.returncode}


def qmp_command(stream, command, arguments=None):
    request = {"execute": command}
    if arguments is not None:
        request["arguments"] = arguments
    stream.write(json.dumps(request).encode() + b"\n")
    stream.flush()
    while True:
        response = json.loads(stream.readline())
        if "return" in response or "error" in response:
            return response


def boot_case(args, root, name, efi, expected_code, expected_runtime, expected_hfs):
    directory = root / name
    directory.mkdir()
    disk = directory / "esp.img"
    with disk.open("wb") as file:
        file.truncate(128 * 1024 * 1024)
    setup = [run_logged([shutil.which("mkfs.vfat"), "-F", "32", str(disk)], directory, "format")]
    setup.append(run_logged([shutil.which("mcopy"), "-i", str(disk), "-s", str(efi), "::/"], directory, "copy"))
    variables = directory / "OVMF_VARS.fd"
    shutil.copyfile(args.ovmf_vars, variables)
    variables_before = digest(variables)
    # Only generated regular files are disks; no host disks, device passthrough or network.
    qmp_path = directory / "qmp.sock"
    command = [args.qemu, "-no-user-config", "-machine", "q35,accel=" + args.accel, "-cpu", "host" if args.accel == "kvm" else TCG_CPU, "-m", "512", "-smp", "2",
               "-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={args.ovmf_code}",
               "-drive", f"if=pflash,format=raw,unit=1,file={variables}",
               "-drive", f"if=virtio,format=raw,file={disk}",
               "-nic", "none", "-display", "none", "-vga", "std",
               "-serial", f"file:{directory / 'serial.log'}", "-debugcon", f"file:{directory / 'debugcon.log'}",
               "-global", "isa-debugcon.iobase=0xe9", "-device", "isa-debug-exit,iobase=0xf4,iosize=4",
               "-qmp", f"unix:{qmp_path},server=on,wait=off", "-no-reboot"]
    started = time.monotonic()
    input_events = []
    with (directory / "qemu.stdout").open("wb") as out, (directory / "qemu.stderr").open("wb") as err:
        process = subprocess.Popen(command, stdout=out, stderr=err)
        timed_out = False
        try:
            if name != "firmware-control":
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    # OpenCore intentionally does not auto-select a tool as a boot default.
                    # The ESP contains exactly one visible entry: our component probe.
                    with socket.socket(socket.AF_UNIX) as client:
                        client.settimeout(5)
                        client.connect(str(qmp_path))
                        with client.makefile("rwb") as stream:
                            stream.readline()
                            qmp_command(stream, "qmp_capabilities")
                            qmp_command(stream, "screendump", {"filename": str(directory / "picker.ppm")})
                            event = {"keys": [{"type": "qcode", "data": "ret"}], "hold-time": 100}
                            response = qmp_command(stream, "send-key", event)
                            input_events.append({"command": "send-key", "arguments": event, "response": response})
            process.wait(timeout=max(1, 45 - (time.monotonic() - started)))
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                with socket.socket(socket.AF_UNIX) as client:
                    client.settimeout(5)
                    client.connect(str(qmp_path))
                    stream = client.makefile("rwb")
                    stream.readline()
                    qmp_command(stream, "qmp_capabilities")
                    response = qmp_command(stream, "screendump", {"filename": str(directory / "screen.ppm")})
                    (directory / "screendump.json").write_text(json.dumps(response))
                    qmp_command(stream, "quit")
            except (OSError, ValueError):
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    log = (directory / "debugcon.log").read_text(errors="replace")
    observed = {line.split("=", 1)[0]: int(line.split("=", 1)[1]) for line in log.splitlines() if "=" in line and line.split("=", 1)[1].isdigit()}
    valid = (not timed_out and process.returncode == expected_code
             and observed.get("OPENRUNTIME_REVISION_12") == expected_runtime
             and observed.get("HFSPLUS_DRIVER_BINDING") == expected_hfs
             and observed.get("VIRTUAL_GOP") == 1 and observed.get("VIRTUAL_ACPI_2_TABLE") == 1
             and observed.get("KEXT_EXECUTED") == 0 and observed.get("MACOS_KERNEL_EXECUTED") == 0)
    return {"name": name, "status": "passed" if valid else "failed", "setup": setup, "command": command,
            "exit_code": process.returncode, "expected_exit_code": expected_code, "timed_out": timed_out,
            "elapsed_seconds": round(time.monotonic() - started, 2), "observations": observed,
            "qmp_input_events": input_events,
            "variables_before_sha256": variables_before, "variables_after_sha256": digest(variables),
            "log_sha256": {p.name: digest(p) for p in directory.glob("*.log")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ["qemu", "ovmf-code", "ovmf-vars", "efi-include", "lld"]:
        parser.add_argument("--" + flag, required=True)
    parser.add_argument("--accel", choices=["tcg", "kvm"], default="tcg", help="TCG uses an emulated Intel CPU; KVM exposes the host CPU")
    args = parser.parse_args()
    for flag in ["qemu", "ovmf_code", "ovmf_vars", "efi_include", "lld"]:
        setattr(args, flag, str(Path(getattr(args, flag)).resolve(strict=True)))
    if not Path(args.efi_include).is_dir() or any(not Path(getattr(args, flag)).is_file() for flag in ["qemu", "ovmf_code", "ovmf_vars", "lld"]):
        raise ValueError("Tool/firmware inputs must be regular files; EFI include must be a directory")
    root = ROOT / ".local/nonboot-vm"
    root.mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=root))
    archive = ROOT / ".cache/assets/OpenCorePkg/1.0.8/OpenCore-1.0.8-RELEASE.zip"
    expected_archive = "2011e8b7216ecb2645d97ea710df965947edd406846e92050b9bc4190be6d27b"
    if digest(archive) != expected_archive:
        raise ValueError("Pinned OpenCore archive differs")
    probe_source = ROOT / "tests/uefi_component_probe.c"
    compile_command = [shutil.which("clang"), "--target=x86_64-pc-windows-msvc", "-ffreestanding", "-fshort-wchar", "-mno-red-zone",
                       "-fno-stack-protector", "-DGNU_EFI_USE_MS_ABI", "-I", args.efi_include, "-I", args.efi_include + "/x86_64",
                       "-c", str(probe_source), "-o", str(run / "probe.obj")]
    compilation = run_logged(compile_command, run, "compile")
    linking = run_logged([args.lld, "/subsystem:efi_application", "/entry:efi_main", "/nodefaultlib", "/machine:x64",
                          "/out:" + str(run / "ComponentProbe.efi"), str(run / "probe.obj")], run, "link")
    direct = run / "direct/EFI/BOOT"
    direct.mkdir(parents=True)
    shutil.copyfile(run / "ComponentProbe.efi", direct / "BOOTX64.EFI")
    cases = [boot_case(args, run, "firmware-control", direct.parent, 35, 0, 0)]
    with zipfile.ZipFile(archive) as package:
        for case_name, use_hfs in [("opencore-drivers", True), ("missing-hfs-control", False)]:
            esp = run / (case_name + "-files") / "EFI"
            (esp / "BOOT").mkdir(parents=True)
            oc = esp / "OC"
            for folder in ["Drivers", "Tools", "ACPI", "Kexts"]:
                (oc / folder).mkdir(parents=True)
            (esp / "BOOT/BOOTX64.EFI").write_bytes(package.read("X64/EFI/BOOT/BOOTx64.efi"))
            for name in [".contentVisibility", ".contentFlavour"]:
                (esp / "BOOT" / name).write_bytes(package.read("X64/EFI/BOOT/" + name))
            (oc / "OpenCore.efi").write_bytes(package.read("X64/EFI/OC/OpenCore.efi"))
            # This profile is exclusively for the VM. HP ACPI/CPU/device patches are not copied.
            config = plistlib.loads(package.read("Docs/Sample.plist"))
            for section in ["ACPI", "Booter", "Kernel"]:
                for field in ["Add", "Delete", "Patch", "Block", "Force", "MmioWhitelist"]:
                    if field in config[section]: config[section][field] = []
            config["DeviceProperties"] = {"Add": {}, "Delete": {}}
            config["Misc"]["Entries"] = []
            config["Misc"]["BlessOverride"] = []
            config["Misc"]["Tools"] = [{"Arguments": "", "Auxiliary": False, "Comment": "Isolated virtual firmware component probe",
                "Enabled": True, "Flavour": "Auto", "FullNvramAccess": False, "Name": "ComponentProbe", "Path": "ComponentProbe.efi",
                "RealPath": False, "TextMode": True}]
            config["Misc"]["Boot"].update(LauncherOption="Disabled", ShowPicker=True, HideAuxiliary=False, Timeout=1, PickerMode="Builtin")
            config["Misc"]["Security"].update(AllowSetDefault=False, SecureBootModel="Disabled", Vault="Optional", ScanPolicy=0)
            config["Misc"]["Debug"].update(Target=3, DisplayLevel=0x80000042, SysReport=False)
            config["NVRAM"].update(Add={}, Delete={}, LegacySchema={}, WriteFlash=False)
            config["PlatformInfo"].update(Automatic=False, UpdateDataHub=False, UpdateNVRAM=False, UpdateSMBIOS=False)
            config["UEFI"]["Drivers"] = []
            for name in ["OpenRuntime.efi"] + (["OpenHfsPlus.efi"] if use_hfs else []):
                (oc / "Drivers" / name).write_bytes(package.read("X64/EFI/OC/Drivers/" + name))
                config["UEFI"]["Drivers"].append({"Arguments": "", "Comment": "Pinned virtual test", "Enabled": True, "HideVerbose": False, "LoadEarly": False, "Path": name})
            config["UEFI"]["Output"].update(ProvideConsoleGop=True, Resolution="1024x768")
            config["UEFI"]["Input"]["KeySupport"] = True
            config_path = oc / "config.plist"
            config_path.write_bytes(plistlib.dumps(config, sort_keys=False))
            shutil.copyfile(run / "ComponentProbe.efi", oc / "Tools/ComponentProbe.efi")
            validator = run / "ocvalidate"
            if not validator.exists():
                validator.write_bytes(package.read("Utilities/ocvalidate/ocvalidate.linux"))
                validator.chmod(0o755)
            validation = run_logged([str(validator), str(config_path)], run, case_name + "-ocvalidate")
            case = boot_case(args, run, case_name, esp, 33 if use_hfs else 35, 1, int(use_hfs))
            case.update(config_sha256=digest(config_path), ocvalidate=validation)
            cases.append(case)
    report = {"schema_version": 1, "status": "passed" if all(x["status"] == "passed" for x in cases) else "failed",
              "runner_sha256": digest(__file__), "probe_source_sha256": digest(probe_source), "probe_efi_sha256": digest(run / "ComponentProbe.efi"),
              "opencore_version": "1.0.8", "opencore_archive_sha256": expected_archive,
              "qemu_version": subprocess.check_output([args.qemu, "--version"], text=True).splitlines()[0],
              "accelerator": args.accel, "cpu": "host" if args.accel == "kvm" else TCG_CPU,
              "toolchain": {flag: {"path": getattr(args, flag), "sha256": digest(getattr(args, flag))} for flag in ["qemu", "ovmf_code", "ovmf_vars", "lld"]},
              "compilation": compilation, "linking": linking, "cases": cases,
              "network_attached": False, "physical_disks_attached": False, "passthrough_devices": [],
              "macos_installed": False, "macos_kernel_executed": False, "macos_kext_loaded": False,
              "scope": "Real UEFI driver startup under OVMF/QEMU; no Apple kernel, kext loader or HP device execution"}
    (run / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (root / "latest.json").write_text(json.dumps({"report": str((run / "report.json").relative_to(ROOT))}) + "\n")
    print(json.dumps({"status": report["status"], "report": str((run / "report.json").relative_to(ROOT)), "cases": [{k: c[k] for k in ["name", "status", "exit_code", "observations"]} for c in cases]}, indent=2))
    if report["status"] != "passed": raise SystemExit(1)


if __name__ == "__main__":
    main()
