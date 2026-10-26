#!/usr/bin/env python3
"""Observe a disposable UEFI media probe directly and through Ventoy.

Only regular images in .local are attached. EFI marker reads and protocol
availability are the evidence; starting an EFI binary alone is insufficient.
"""

import argparse
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time

from recovery_vm import ROOT, private, sha, png_from_ppm, qmp_command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", required=True, help="Private prepare.json")
    parser.add_argument("--tools-from", required=True, help="Previous pinned nonboot-vm report.json")
    parser.add_argument("--route", choices=["direct", "ordinary", "f6"], required=True)
    args = parser.parse_args()
    prepared = json.loads(private(args.prepared).read_text())
    tools = json.loads(private(args.tools_from).read_text())["toolchain"]
    for name in ("qemu", "ovmf_code", "ovmf_vars"):
        if sha(tools[name]["path"]) != tools[name]["sha256"]:
            raise ValueError("Pinned VM tool differs")
    disk = private(prepared["probe" if args.route == "direct" else "disk"])
    if not disk.is_file():
        raise ValueError("Use a private regular test disk")
    run = Path(tempfile.mkdtemp(prefix=args.route + "-", dir=disk.parent))
    variables = run / "OVMF_VARS.fd"
    shutil.copyfile(tools["ovmf_vars"]["path"], variables)
    command = [tools["qemu"]["path"], "-no-user-config", "-machine", "q35", "-accel", "tcg",
        "-m", "512", "-smp", "1", "-drive", f'if=pflash,format=raw,unit=0,readonly=on,file={tools["ovmf_code"]["path"]}',
        "-drive", f"if=pflash,format=raw,unit=1,file={variables}",
        "-drive", f"if=virtio,format=raw,file={disk},snapshot=on", "-nic", "none", "-display", "none",
        "-vga", "std", "-serial", f"file:{run / 'serial.log'}", "-debugcon", f"file:{run / 'debugcon.log'}",
        "-global", "isa-debugcon.iobase=0xe9", "-device", "isa-debug-exit,iobase=0xf4,iosize=4",
        "-qmp", f"unix:{run / 'qmp.sock'},server=on,wait=off", "-no-reboot"]
    events = []

    def q(command, arguments=None):
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(5)
            client.connect(str(run / "qmp.sock"))
            with client.makefile("rwb") as stream:
                stream.readline()
                qmp_command(stream, "qmp_capabilities")
                response = qmp_command(stream, command, arguments)
                events.append({"command": command, "arguments": arguments, "response": response})
                return response

    timed_out = False
    with (run / "qemu.stdout").open("wb") as out, (run / "qemu.stderr").open("wb") as err:
        process = subprocess.Popen(command, stdout=out, stderr=err)
        try:
            if args.route == "f6":
                time.sleep(2)  # Hold picker before the ordinary-route timeout.
                q("send-key", {"keys": [{"type": "qcode", "data": "esc"}], "hold-time": 100})
                time.sleep(5)
                q("send-key", {"keys": [{"type": "qcode", "data": "f6"}], "hold-time": 100})
                time.sleep(2)
                q("send-key", {"keys": [{"type": "qcode", "data": "ret"}], "hold-time": 100})
            process.wait(timeout=35)
        except subprocess.TimeoutExpired:
            timed_out = True
            response = q("screendump", {"filename": str(run / "screen.ppm")})
            if "return" in response:
                png_from_ppm(run / "screen.ppm")
        finally:
            if process.poll() is None:
                try:
                    q("quit")
                    process.wait(timeout=5)
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    process.kill()
                    process.wait()
    text = (run / "debugcon.log").read_text(errors="replace")
    observations = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and value.isdigit():
            observations[key] = int(value)
    passed = observations.get("MARKER_FILESYSTEMS", 0) > 0 and observations.get("MARKER_BLOCK_HANDLES", 0) > 0
    report = {"route": args.route, "protocol_probe_passed": passed, "timed_out": timed_out,
              "exit_code": process.returncode, "observations": observations, "events": events,
              "command": command, "disk_sha256": sha(disk), "runner_sha256": sha(Path(__file__)),
              "physical_devices_accessed": False, "macos_executed": False,
              "scope": "Virtual FAT32-only probe; no physical exFAT or Apple booter proof"}
    (run / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str((run / "report.json").relative_to(ROOT)), **report}, indent=2))


if __name__ == "__main__":
    main()
