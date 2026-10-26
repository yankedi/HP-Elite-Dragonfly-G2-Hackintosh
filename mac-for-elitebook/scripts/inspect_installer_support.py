#!/usr/bin/env python3
"""Read verified InstallAssistant's inner MobileAsset version and payload digest.

Extracts the hybrid package's HFS+ partition locally using a pinned 7zz, reads
the board-specific catalog record, and hashes the large install ZIP by streaming.
No package scripts, macOS processes, VM or physical device writes are involved.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile

from reconstruct_installer_app import ROOT, sha

SEVENZIP_SHA256 = "3e3a0fa5d764701c81076b1574012b7ecb1563b24439d548eb5da498e6875d6f"
CATALOG = "Shared Support/com_apple_MobileAsset_MacSoftwareUpdate/com_apple_MobileAsset_MacSoftwareUpdate.xml"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default=".local/install-prep/full-installer/InstallAssistant.pkg")
    parser.add_argument("--verification", required=True)
    parser.add_argument("--sevenzip", required=True)
    parser.add_argument("--board", default="Mac-5F9802EFE386AA28")
    args = parser.parse_args()
    package, verification = [(ROOT / v).resolve(strict=True) for v in (args.package, args.verification)]
    tool = Path(args.sevenzip).resolve(strict=True)
    if any(not p.is_relative_to(ROOT / ".local") for p in (package, verification)):
        raise ValueError("Package and verification must stay private")
    proof = json.loads(verification.read_text())
    if not all(proof.get(k) for k in ("toc_rsa_signature_verified", "certificate_chain_verified_at_current_time", "tampered_signature_rejected")):
        raise ValueError("Missing package signature evidence")
    package_sha = sha(package)
    if proof["package_sha256"] != package_sha or sha(tool) != SEVENZIP_SHA256:
        raise ValueError("Package or extractor pin differs")
    os.umask(0o077)
    out = Path(tempfile.mkdtemp(prefix="support-inspection-", dir=ROOT / ".local/install-prep"))
    hfs = out / "SharedSupport.hfs"
    with hfs.open("xb") as target:
        result = subprocess.run([str(tool), "x", "-so", "-tDmg", str(package), "5.hfs"],
                                stdout=target, stderr=subprocess.PIPE, timeout=600)
    (out / "extract.stderr").write_bytes(result.stderr)
    if result.returncode or hfs.stat().st_size != 19705679872:
        raise ValueError("Unexpected selected SharedSupport partition")
    result = subprocess.run([str(tool), "x", "-so", str(hfs), CATALOG], capture_output=True, timeout=60, check=True)
    (out / "MobileAsset.plist").write_bytes(result.stdout)
    assets = plistlib.loads(result.stdout)["Assets"]
    selected = [a for a in assets if args.board in a.get("SupportedDeviceModels", [])]
    if len(selected) != 1:
        raise ValueError("Expected one catalog record for the chosen SMBIOS board")
    asset = selected[0]
    relative = Path(asset["__RelativePath"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unsafe catalog payload path")
    h = hashlib.sha256()
    count = 0
    with (out / "payload.stderr").open("wb") as err:
        process = subprocess.Popen([str(tool), "x", "-so", str(hfs), "Shared Support/" + str(relative)],
                                   stdout=subprocess.PIPE, stderr=err)
        while chunk := process.stdout.read(4 * 2**20):
            h.update(chunk)
            count += len(chunk)
        if process.wait(timeout=60) or h.digest() != asset["_Measurement-SHA256"] or count != asset["_DownloadSize"]:
            raise ValueError("Inner MobileAsset bytes/digest differ")
    report = {"schema_version": 1, "package_sha256": package_sha, "verification_report_sha256": sha(verification),
              "version_from_package_internals": asset["OSVersion"], "build_from_package_internals": asset["Build"],
              "catalog_sha256": sha(out / "MobileAsset.plist"), "selected_smbios_board": args.board,
              "documentation_id": asset.get("SUDocumentationID"), "train": asset.get("TrainName"),
              "payload_path": str(relative), "payload_bytes": count, "payload_sha256": h.hexdigest(),
              "payload_digest_matches_inner_catalog": True, "hfs_sha256": sha(hfs),
              "extractor_sha256": sha(tool), "runner_sha256": sha(Path(__file__)),
              "vm_executed": False, "macos_installation_tested": False}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    hfs.unlink()
    print(json.dumps({"report": str((out / "report.json").relative_to(ROOT)), **report}, indent=2))


if __name__ == "__main__":
    main()
