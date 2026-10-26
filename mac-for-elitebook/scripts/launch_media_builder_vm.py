#!/usr/bin/env python3
"""Start an isolated Recovery VM with private files for installer-media work.

Two brand-new sparse scratch disks are created inside its private run directory.
An existing .local FAT input image is protected by a disposable snapshot. No physical devices,
network, install destination or HP firmware are accessed.
"""

import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile

from recovery_vm import ROOT, launch, private, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools-from-launch", required=True, help="Existing private launch.json with pinned QEMU/OVMF paths")
    parser.add_argument("--inputs", required=True, help="Private regular raw FAT image")
    parser.add_argument("--recovery", default=".local/recovery-repair/recovery")
    args = parser.parse_args()
    inputs = private(args.inputs)
    if not inputs.is_file() or inputs.stat().st_size > 24 * 2**30:
        raise ValueError("Use a bounded regular input image")
    previous = json.loads(private(args.tools_from_launch).read_text())
    tools = previous["tools"]
    for item in tools.values():
        if sha(item["path"]) != item["sha256"]:
            raise ValueError("Pinned previous tool differs")
    run = Path(tempfile.mkdtemp(prefix="media-disks-", dir=ROOT / ".local/install-prep"))
    drives = [(inputs, "media_inputs", "MEDIAINPUT", True, None),
              (run / "media-workspace.raw", "media_work", "OCMEDIAWORK", False, 28),
              (run / "media-output.raw", "media_output", "OCMEDIAOUT", False, 24)]
    for path, _, _, readonly, gib in drives:
        if not readonly:
            with path.open("xb") as stream:
                stream.truncate(gib * 2**30)
    vm_args = argparse.Namespace(qemu=tools["qemu"]["path"], ovmf_code=tools["ovmf_code"]["path"],
        ovmf_vars=tools["ovmf_vars"]["path"], recovery=args.recovery,
        kext=[str(ROOT / "build/vesa-prototype/EFI/OC/Kexts" / name) for name in ("Lilu.kext", "VirtualSMC.kext")],
        single_user=True, force_lilu=True, lilu_debug=False, raw_system=True, cpus=2,
        scratch_drives=[{"path": str(path), "serial": serial, "readonly": readonly}
                        for path, node, serial, readonly, gib in drives])
    with contextlib.redirect_stdout(io.StringIO()) as buffer:
        launch(vm_args)
    vm_run = private(json.loads(buffer.getvalue())["run"])
    report = {"schema_version": 1, "runner_sha256": sha(Path(__file__)),
              "base_launch_sha256": sha(vm_run / "launch.json"), "inputs_sha256": sha(inputs),
              "disks": [{"path": str(path), "serial": serial, "readonly": readonly, "new_size_gib": gib}
                        for path, node, serial, readonly, gib in drives],
              "physical_disks_attached": False, "macos_installed": False,
              "scope": "Media-builder scratch disks only; no target macOS installation"}
    (vm_run / "media-builder-launch.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"run": str(vm_run.relative_to(ROOT)), "disks": report["disks"]}, indent=2))


if __name__ == "__main__":
    main()
