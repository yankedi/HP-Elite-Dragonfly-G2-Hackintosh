#!/usr/bin/env python3
"""Audit observed Recovery VM evidence without treating loaded as initialized."""

import argparse
import json
from pathlib import Path
import plistlib
import re
import tempfile

from recovery_vm import ROOT, private, sha


def audit(directory, args):
    launch = json.loads((directory / "launch.json").read_text())
    serial = (directory / "serial.log").read_text(errors="replace")
    lines = [line.strip() for line in serial.splitlines()]
    # Use output between standalone markers, not the echoed command containing them.
    start = lines.index("VM_PROBE_BEGIN")
    end = lines.index("VM_PROBE_END", start + 1)
    output = "\n".join(lines[start + 1:end])
    assert "Darwin Kernel Version " + args.kernel in output, "Guest kernel version differs"
    assert re.search(r"ProductVersion:\s+" + re.escape(args.version) + r"(?:\s|$)", output), "Guest product version differs"
    assert re.search(r"BuildVersion:\s+" + re.escape(args.build) + r"(?:\s|$)", output), "Guest build differs"
    assert "panic(cpu" not in serial, "Panic observed; inspect failed case separately"
    assert not (directory / "qmp.sock").exists(), "VM still running"
    config_file = directory / "EFI/OC/config.plist"
    assert sha(config_file) == launch["config_sha256"], "Saved config differs"
    config = plistlib.loads(config_file.read_bytes())
    assert not config["ACPI"]["Add"] and not config["ACPI"]["Patch"]
    assert not config["DeviceProperties"]["Add"] and not config["Kernel"]["Patch"]
    assert launch["ocvalidate"]["exit_code"] == 0
    for tool in launch["tools"].values():
        assert sha(tool["path"]) == tool["sha256"], "Tool differs"
    command = launch["command"]
    assert command[command.index("-nic") + 1] == "none"
    assert "-no-user-config" in command and "-no-reboot" in command
    assert not any(flag in command for flag in ("-net", "-netdev", "-fsdev", "-virtfs", "-blockdev", "-readconfig"))
    for index, flag in enumerate(command):
        if flag == "-device":
            assert command[index + 1].split(",")[0] in {"ich9-ahci", "ide-hd", "qemu-xhci", "usb-kbd", "usb-tablet"}
        if flag == "-drive":
            match = re.search(r"(?:^|,)file=([^,]+)", command[index + 1])
            assert match, "Drive has no regular file"
            path = Path(match[1]).resolve(strict=True)
            assert path.is_file(), "Drive is not a regular file"
            if "unit=0,readonly=on" not in command[index + 1]:
                assert path.is_relative_to(directory), "Writable drive outside this private VM"
    loaded = {match[0]: {"version": match[1], "uuid": match[2]} for match in re.findall(
        r"as\.vit9696\.([A-Za-z]+) \(([^)]+)\) ([A-F0-9-]+)", output)}
    for item in launch["kext_inputs"]:
        bundle = directory / "EFI/OC/Kexts" / item["bundle"]
        info_file = bundle / "Contents/Info.plist"
        info = plistlib.loads(info_file.read_bytes())
        assert sha(info_file) == item["plist_sha256"], "Kext plist differs"
        assert sha(bundle / "Contents/MacOS" / info["CFBundleExecutable"]) == item["executable_sha256"], "Kext binary differs"
        name = item["id"].rsplit(".", 1)[-1]
        assert loaded[name]["version"] == item["version"], "Expected bundle/version not listed by guest kmutil"
    observations = {
        "guest_probe_completed": True, "kernel": args.kernel, "version": args.version, "build": args.build,
        "loaded": loaded, "lilu_force_enabling_log": "force enabling due to force flag" in serial,
        "lilu_console_initialization_log": "PE_initialize_console 6 performing init" in serial,
        "weg_api_request_log": "got load request from WhateverGreen (171)" in serial,
        "vsmc_api_request_log": "got load request from VirtualSMC (138)" in serial,
        "weg_parent_error_codes": re.findall(r"WhateverGreen\s+init: @ failed to call parent (\d+)", serial),
        "vsmc_parent_error_codes": re.findall(r"VirtualSMC\s+init: @ failed to call parent (\d+)", serial),
        "vsmc_legacy_log": "legacy mode, most of the features are disabled!" in serial,
        "vsmc_mmio_observed": '"IOMode" = "MMIO"' in output,
        "vsmc_pmio_observed": '"IOMode" = "PMIO"' in output,
        "virtualsmc_registry_header": next((line for line in lines if "<class VirtualSMC," in line), None),
        "weg_registry_header": next((line for line in lines if "<class WhateverGreen," in line), None),
        "lilu_registry_header": next((line for line in lines if "<class Lilu," in line), None),
    }
    evidence = [{"path": str(path.relative_to(ROOT)), "sha256": sha(path), "bytes": path.stat().st_size}
        for path in sorted(directory.iterdir()) if path.is_file() and path.suffix in (".json", ".jsonl", ".log", ".png", ".txt", ".stdout", ".stderr")]
    return {"run": str(directory.relative_to(ROOT)), "runner_at_launch_sha256": launch["runner_sha256"],
            "cpus": launch.get("cpus", 2), "kext_inputs": launch["kext_inputs"],
            "config_sha256": launch["config_sha256"], "observations": observations, "evidence": evidence}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--build", required=True)
    parser.add_argument("--kernel", required=True)
    args = parser.parse_args()
    cases = [audit(private(path), args) for path in args.run]
    root = ROOT / ".local/recovery-vm"
    run = Path(tempfile.mkdtemp(prefix="audit-", dir=root))
    report = {"schema_version": 1, "status": "guest_loading_evidence_audited_with_initialization_limits",
              "runner_sha256": sha(__file__), "vm_runner_sha256": sha(ROOT / "scripts/recovery_vm.py"),
              "cases": cases, "kernel_executed": True, "kexts_listed_by_guest": True,
              "all_plugins_fully_initialized": False, "hp_hardware_tested": False, "metal_tested": False,
              "macos_installed": False, "scope": "Exact observed guest loading and component diagnostics, not hardware function or generic ABI certification"}
    path = run / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(path.relative_to(ROOT)), "sha256": sha(path), "cases": len(cases),
                      "observations": [{"run": case["run"], **case["observations"]} for case in cases]}, indent=2))


if __name__ == "__main__":
    main()
