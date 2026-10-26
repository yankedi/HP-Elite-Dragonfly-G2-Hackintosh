#!/usr/bin/env python3
"""Build and independently read back a private HFS+ offline installer-app image.

Uses regular files only. This is a mountable data image for Recovery, not a
bootable createinstallmedia disk. macOS execution/installation remains untested.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

from reconstruct_installer_app import ROOT, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-report", required=True)
    parser.add_argument("--hfsplus", required=True)
    parser.add_argument("--mkfs", required=True)
    parser.add_argument("--fsck", required=True)
    parser.add_argument("--sevenzip", required=True)
    parser.add_argument("--fsck-preload", help="Linux regular-image ioctl adapter, if needed")
    parser.add_argument("--verify-image", help="Independently verify an existing private raw HFS+ image instead of rebuilding")
    args = parser.parse_args()
    report_path = (ROOT / args.app_report).resolve(strict=True)
    if not report_path.is_relative_to(ROOT / ".local"):
        raise ValueError("Input report must be private")
    report = json.loads(report_path.read_text())
    app = (ROOT / report["app"]).resolve(strict=True)
    if not app.is_relative_to(ROOT / ".local"):
        raise ValueError("App must be private")
    for item in report["entries"]:
        path = report_path.parent / item["path"]
        if item["type"] == "file" and sha(path) != item["sha256"]:
            raise ValueError("Reconstructed app bytes differ")
        if item["type"] == "symlink" and str(path.readlink()) != item["target"]:
            raise ValueError("App symlink differs")
    support = app / "Contents/SharedSupport/SharedSupport.dmg"
    if sha(support) != report["package_sha256"]:
        raise ValueError("Verified complete support input differs")
    tools = {name: Path(getattr(args, name)).resolve(strict=True) for name in ("hfsplus", "mkfs", "fsck", "sevenzip")}
    preload = Path(args.fsck_preload).resolve(strict=True) if args.fsck_preload else None
    if any(not path.is_file() for path in tools.values()):
        raise ValueError("Tools must be regular executable files")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="offline-volume-", dir=ROOT / ".local/install-prep"))
    image = out / "Tahoe-26.6.2-Offline-App.hfs"
    existing = (ROOT / args.verify_image).resolve(strict=True) if args.verify_image else None
    if existing:
        if not existing.is_relative_to(ROOT / ".local") or not existing.is_file():
            raise ValueError("Existing image must be a private regular file")
        os.link(existing, image)
    else:
        with image.open("xb") as stream:
            stream.truncate(19000 * 2**20)

    def run(tool, arguments, label, timeout=60):
        command = [str(tools[tool]), *map(str, arguments)]
        env = dict(os.environ, LD_PRELOAD=str(preload)) if tool == "fsck" and preload else None
        # The enclosing output directory remains private (0700). Let the decoder
        # restore original modes within it, independent of the process umask.
        result = subprocess.run(command, capture_output=True, timeout=timeout, env=env,
                                umask=0 if tool == "sevenzip" else -1)
        with (out / "commands.jsonl").open("a") as log:
            log.write(json.dumps({"label": label, "command": command, "exit_code": result.returncode}) + "\n")
        if result.returncode or label in ("format", "fsck", "extract", "listing"):
            (out / (label + ".stdout")).write_bytes(result.stdout)
            (out / (label + ".stderr")).write_bytes(result.stderr)
        if result.returncode:
            raise ValueError("Tool failed: " + label)
        return result.stdout

    paths = [app, *sorted(app.rglob("*"))]

    def inside(path):
        return "/" + str(path.relative_to(app.parent))

    if not existing:
        run("mkfs", ["-U", "0", "-G", "0", "-v", "TahoeOffline", image], "format")
        # addall dereferences links and discards executable modes; import explicitly.
        directories = [path for path in paths if path.is_dir() and not path.is_symlink()]
        for path in sorted(directories, key=lambda p: len(p.parts)):
            run("hfsplus", [image, "mkdir", inside(path)], "mkdir")
            mode = 0o755 if path == support.parent else stat.S_IMODE(path.stat().st_mode)
            run("hfsplus", [image, "chmod", f"{mode:o}", inside(path)], "directory-mode")
        for path in paths:
            if path.is_file() and not path.is_symlink():
                run("hfsplus", [image, "add", path, inside(path)], "add-file", timeout=600)
                run("hfsplus", [image, "chmod", f"{stat.S_IMODE(path.stat().st_mode):o}", inside(path)], "file-mode")
        links = [path for path in paths if path.is_symlink()]
        for path in links:
            run("hfsplus", [image, "symlink", inside(path), str(path.readlink())], "symlink")
    run("fsck", ["-f", "-n", image], "fsck", timeout=180)
    run("sevenzip", ["l", "-slt", image], "listing")
    roundtrip = out / "roundtrip"
    roundtrip.mkdir()
    support_inside = "TahoeOffline" + inside(support)
    run("sevenzip", ["x", "-y", "-o" + str(roundtrip), "-x!" + support_inside, image], "extract", timeout=120)
    compared, compared_links = 0, 0
    for path in paths:
        extracted = roundtrip / "TahoeOffline" / path.relative_to(app.parent)
        if path.is_symlink():
            if not extracted.is_symlink() or extracted.readlink() != path.readlink():
                raise ValueError("HFS symlink readback differs: " + inside(path))
            compared_links += 1
        elif path.is_file() and path != support:
            if sha(path) != sha(extracted) or stat.S_IMODE(path.stat().st_mode) != stat.S_IMODE(extracted.stat().st_mode):
                raise ValueError("HFS app bytes/mode readback differs: " + inside(path))
            compared += 1
    # Hash the 18 GB nested package directly from the independently decoded HFS.
    h = hashlib.sha256()
    count = 0
    with (out / "support-readback.stderr").open("wb") as err:
        process = subprocess.Popen([str(tools["sevenzip"]), "x", "-so", str(image), support_inside],
                                   stdout=subprocess.PIPE, stderr=err)
        while chunk := process.stdout.read(4 * 2**20):
            h.update(chunk)
            count += len(chunk)
        if process.wait(timeout=60) or h.hexdigest() != report["package_sha256"] or count != support.stat().st_size:
            raise ValueError("HFS complete package readback differs")
    receipt = {"schema_version": 1, "image": str(image.relative_to(ROOT)), "bytes": image.stat().st_size,
               "sha256": sha(image), "app_report_sha256": sha(report_path), "fsck_exit": 0,
               "roundtrip_app_files_verified": compared, "roundtrip_symlinks_verified": compared_links,
               "roundtrip_package_bytes": count, "roundtrip_package_sha256": h.hexdigest(),
               "executable_modes_verified": True, "format": "raw case-insensitive HFS+ volume; mount as CRawDiskImage",
               "tools": {name: {"path": str(path), "sha256": sha(path)} for name, path in tools.items()},
               "fsck_regular_file_adapter": {"path": str(preload), "sha256": sha(preload)} if preload else None,
               "runner_sha256": sha(Path(__file__)), "physical_devices_written": False, "vm_executed": False,
               "verification_source_image": str(existing.relative_to(ROOT)) if existing else None,
               "apple_installation_tested": False, "status": "offline_app_data_image_built_and_readback_verified"}
    (out / "report.json").write_text(json.dumps(receipt, indent=2) + "\n")
    shutil.rmtree(roundtrip)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
