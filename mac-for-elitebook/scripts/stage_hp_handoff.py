#!/usr/bin/env python3
"""Stage verified HP retry and offline data images as private local hardlinks.

Does not mount, copy to USB, edit Ventoy, or execute any boot/install process.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile

from reconstruct_installer_app import ROOT, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retry-report", required=True)
    parser.add_argument("--offline-report", required=True)
    args = parser.parse_args()
    paths = [(ROOT / v).resolve(strict=True) for v in (args.retry_report, args.offline_report)]
    if any(not p.is_relative_to(ROOT / ".local") for p in paths):
        raise ValueError("Input reports must stay private")
    retry, offline = [json.loads(p.read_text()) for p in paths]
    validation_exit = retry.get("opencore_ocvalidate_exit", retry.get("ocvalidate_exit"))
    if not (validation_exit == 0 and retry["other_efi_files_identical"] and retry["private_identity_preserved"]):
        raise ValueError("Retry audit incomplete")
    if not (offline["fsck_exit"] == 0 and offline["executable_modes_verified"] and offline["roundtrip_package_bytes"] > 18 * 10**9):
        raise ValueError("Offline image readback incomplete")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="hp-handoff-", dir=ROOT / ".local/install-prep"))
    files = []
    for report in (retry, offline):
        source = (ROOT / report["image"]).resolve(strict=True)
        if not source.is_relative_to(ROOT / ".local") or not source.is_file():
            raise ValueError("Expected private regular image")
        if source.stat().st_size != report["bytes"] or sha(source) != report["sha256"]:
            raise ValueError("Image differs from verification receipt")
        destination = out / source.name
        os.link(source, destination)
        if not os.path.samefile(source, destination):
            raise ValueError("Local staging hardlink differs")
        files.append({"name": source.name, "bytes": report["bytes"], "sha256": report["sha256"]})
    for name in ("collect_macos_handoff.sh", "attach_hp_offline_installer.sh"):
        helper = out / name
        shutil.copyfile(ROOT / "scripts" / name, helper)
        files.append({"name": name, "bytes": helper.stat().st_size, "sha256": sha(helper)})
    (out / "SHA256SUMS").write_text("".join(item["sha256"] + "  " + item["name"] + "\n" for item in files))
    (out / "README.txt").write_text(
        "HP local handoff: controlled VESA retry plus complete offline installer app data.\n"
        "Retry change: " + retry["only_config_change"] + "\n"
        "No USB update has been performed by this staging command.\n"
        "HP-Tahoe-VESA-Recovery.img is the private-identity boot retry; choose HPRECOVERY (dmg).\n"
        "Tahoe-26.6.2-Offline-App.hfs is a read-only-mountable data image, not a boot image.\n"
        "It contains Install macOS Tahoe.app including the complete signed SharedSupport.\n"
        "The offline app has not been executed or installed on HP.\n"
        "After Recovery starts, use diskutil list to locate the physical exFAT volume.\n"
        "Replace <volume-name> below with the mounted removable volume name.\n"
        "sh /Volumes/<volume-name>/iso/linux/collect_macos_handoff.sh\n"
        "sh /Volumes/<volume-name>/iso/linux/attach_hp_offline_installer.sh /Volumes/<volume-name>/iso/linux/Tahoe-26.6.2-Offline-App.hfs\n"
        "The attach helper mounts only this data image read-only and prints the app path.\n"
        "It does not launch the installer or choose a target disk.\n"
        "Both images are ordinary files for the existing Ventoy data filesystem.\n"
        "Private SMBIOS identity is embedded in the boot image; keep this bundle private.\n"
        "See docs/install-handoff.md and docs/offline-installer-inputs.md for evidence and current limits.\n")
    receipt = {"schema_version": 1, "directory": str(out.relative_to(ROOT)), "files": files,
                "retry_report_sha256": sha(paths[0]), "offline_report_sha256": sha(paths[1]),
                "retry_change": retry["only_config_change"],
               "runner_sha256": sha(Path(__file__)), "usb_updated": False,
               "hp_retry_tested": False, "hp_offline_installer_executed": False,
               "ventoy_configuration_changed": False, "physical_devices_written": False,
               "usb_boot_image_destination": "/iso/linux/HP-Tahoe-VESA-Recovery.img",
               "usb_offline_data_destination": "/iso/linux/Tahoe-26.6.2-Offline-App.hfs"}
    (out / "report.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
