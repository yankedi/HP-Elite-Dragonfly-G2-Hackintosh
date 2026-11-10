#!/usr/bin/env python3
"""Deterministic verification tool for macOS Tahoe 26.6.2 (25G83) release deliverables."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]

INSTALL_PREP_REL = "configs/install-preparation.json"
DEPLOY_RECEIPT_REL = (
    ".local/driver-repair-20261103/s0ix-standby-prep-20261107/"
    "post-wake-ebaba2ee/lidwake-greenfix-deploy-receipt.json"
)
BUNDLE_RECEIPT_REL = (
    ".local/driver-repair-20261103/s0ix-standby-prep-20261107/"
    "postinstall-bundle-20261108/bundle-receipt.json"
)
BUNDLE_DIR_REL = (
    ".local/driver-repair-20261103/s0ix-standby-prep-20261107/"
    "postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108"
)
BUNDLE_TAR_GZ_REL = (
    ".local/driver-repair-20261103/s0ix-standby-prep-20261107/"
    "postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108.tar.gz"
)
RECOVERY_IMG_REL = (
    ".local/driver-repair-20261103/s0ix-standby-prep-20261107/"
    "HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img"
)
RECOVERY_ESP_OFFSET = 1048576  # 2048 * 512

RECOVERY_KEY_EFI_FILES = (
    "BOOT/BOOTx64.efi",
    "OC/config.plist",
    "OC/ACPI/SSDT-DEEPIDLE.aml",
    "OC/ACPI/SSDT-EC0-ITLB.aml",
    "OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen",
    "OC/Kexts/S0ixStandby.kext/Contents/MacOS/S0ixStandby",
    "OC/Kexts/TGLDmic.kext/Contents/MacOS/TGLDmic",
    "OC/Kexts/SimpleHDA.kext/Contents/MacOS/SimpleHDA",
    "OC/Kexts/WhateverGreen.kext/Contents/MacOS/WhateverGreen",
)

LIVE_NIXOS_KEY_OC_FILES = (
    "config.plist",
    "ACPI/SSDT-DEEPIDLE.aml",
    "ACPI/SSDT-EC0-ITLB.aml",
    "Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen",
    "Kexts/S0ixStandby.kext/Contents/MacOS/S0ixStandby",
)


def sha256_file(path: Path) -> tuple[str, int]:
    """Compute SHA-256 hex digest and byte count of a file by streaming."""
    h = hashlib.sha256()
    total = 0
    with path.open("rb") as fp:
        while chunk := fp.read(1024 * 1024):
            h.update(chunk)
            total += len(chunk)
    return h.hexdigest(), total


def sha256_stream(stream) -> tuple[str, int]:
    """Compute SHA-256 hex digest and byte count of a binary stream."""
    h = hashlib.sha256()
    total = 0
    while chunk := stream.read(1024 * 1024):
        h.update(chunk)
        total += len(chunk)
    return h.hexdigest(), total


def load_json_safe(path: Path, label: str, errors: list[str]) -> dict | None:
    """Read and parse a JSON object file safely without raising on malformed JSON."""
    if not path.is_file():
        errors.append(f"Missing {label}: {path}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"Failed to parse JSON in {label} ({path}): {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"Expected JSON object in {label} ({path}), got {type(data).__name__}")
        return None
    return data


def parse_sha256sums(text: str, errors: list[str]) -> dict[str, str]:
    """Parse a standard two-space separated SHA256SUMS.txt manifest."""
    entries: dict[str, str] = {}
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = raw_line.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            errors.append(f"Malformed SHA256SUMS.txt line {lineno}: {raw_line!r}")
            continue
        digest, rel_path = parts[0].lower(), parts[1]
        if any(ch not in "0123456789abcdef" for ch in digest):
            errors.append(f"Non-hex SHA256 digest on SHA256SUMS.txt line {lineno}: {parts[0]!r}")
            continue
        if rel_path in entries:
            errors.append(f"Duplicate path in SHA256SUMS.txt line {lineno}: {rel_path}")
            continue
        entries[rel_path] = digest
    return entries


def read_fat32_partition_files(
    img_path: Path, part_offset: int, errors: list[str]
) -> dict[str, tuple[str, int]]:
    """Read all regular files (relative_path -> (sha256, size_bytes)) from a FAT32 partition."""
    results: dict[str, tuple[str, int]] = {}
    try:
        with img_path.open("rb") as fp:
            fp.seek(part_offset)
            bpb = fp.read(512)
            if len(bpb) < 90:
                errors.append(f"Truncated FAT32 BPB at offset {part_offset} in {img_path.name}")
                return results
            (
                bytes_per_sec,
                sec_per_clus,
                rsvd_sec_cnt,
                num_fats,
                _root_ent_cnt,
                _tot_sec16,
                _media,
                fat_sz16,
            ) = struct.unpack_from("<HBHBHHBH", bpb, 11)
            fat_sz32, _ext_flags, _fs_ver, root_clus = struct.unpack_from("<IHHI", bpb, 36)
            fat_sz = fat_sz16 if fat_sz16 != 0 else fat_sz32
            if bytes_per_sec == 0 or sec_per_clus == 0 or fat_sz == 0 or root_clus < 2:
                errors.append(f"Invalid FAT32 geometry at offset {part_offset} in {img_path.name}")
                return results

            clus_size = bytes_per_sec * sec_per_clus
            fat_offset = part_offset + rsvd_sec_cnt * bytes_per_sec
            data_offset = fat_offset + num_fats * fat_sz * bytes_per_sec
            fp.seek(fat_offset)
            fat_bytes = fp.read(fat_sz * bytes_per_sec)
            fat = struct.unpack(f"<{len(fat_bytes) // 4}I", fat_bytes)

            def get_chain_bytes(start_clus: int, size: int | None = None) -> bytes:
                if start_clus < 2 or ( size is not None and size == 0 ):
                    return b""
                chunks: list[bytes] = []
                c = start_clus
                seen: set[int] = set()
                total = 0
                while 2 <= c < 0x0FFFFFF8 and c not in seen and c < len(fat):
                    seen.add(c)
                    fp.seek(data_offset + (c - 2) * clus_size)
                    data = fp.read(clus_size)
                    if not data:
                        break
                    chunks.append(data)
                    total += len(data)
                    if size is not None and total >= size:
                        break
                    c = fat[c] & 0x0FFFFFFF
                raw = b"".join(chunks)
                return raw[:size] if size is not None else raw

            def walk_dir(clus: int, prefix: str) -> None:
                raw = get_chain_bytes(clus)
                lfn_parts: list[tuple[int, str]] = []
                for off in range(0, len(raw), 32):
                    ent = raw[off : off + 32]
                    if len(ent) < 32 or ent[0] == 0x00:
                        break
                    if ent[0] == 0xE5:
                        lfn_parts.clear()
                        continue
                    attr = ent[11]
                    if attr == 0x0F:
                        seq = ent[0] & 0x1F
                        chars = ent[1:11] + ent[14:26] + ent[28:32]
                        part = chars.decode("utf-16le", errors="replace").split("\x00", 1)[0]
                        lfn_parts.append((seq, part))
                        continue
                    if attr & 0x08:
                        lfn_parts.clear()
                        continue
                    if lfn_parts:
                        lfn_parts.sort(key=lambda x: x[0])
                        name = "".join(p for _, p in lfn_parts)
                    else:
                        base = ent[0:8].decode("ascii", errors="replace").rstrip(" ")
                        ext = ent[8:11].decode("ascii", errors="replace").rstrip(" ")
                        nt_res = ent[12]
                        if nt_res & 0x08:
                            base = base.lower()
                        if nt_res & 0x10:
                            ext = ext.lower()
                        name = f"{base}.{ext}" if ext else base
                    lfn_parts.clear()
                    if name in (".", ".."):
                        continue
                    hi_clus = struct.unpack_from("<H", ent, 20)[0]
                    lo_clus = struct.unpack_from("<H", ent, 26)[0]
                    fsize = struct.unpack_from("<I", ent, 28)[0]
                    start_c = (hi_clus << 16) | lo_clus
                    rel = f"{prefix}/{name}" if prefix else name
                    if attr & 0x10:
                        walk_dir(start_c, rel)
                    else:
                        fbytes = get_chain_bytes(start_c, fsize)
                        results[rel] = (hashlib.sha256(fbytes).hexdigest(), len(fbytes))

            walk_dir(root_clus, "")
    except (OSError, struct.error) as exc:
        errors.append(f"Failed to read FAT32 partition in {img_path.name}: {exc}")
    return results


def verify_section1_manifests(root: Path, errors: list[str]) -> dict:
    """1. Core Configuration & Receipt Hash Parity."""
    local_dir_exists = (root / ".local").is_dir()
    install_prep_path = root / INSTALL_PREP_REL
    install_prep = load_json_safe(install_prep_path, INSTALL_PREP_REL, errors)
    if install_prep is None:
        return {"passed": False, "local_present": local_dir_exists, "error": f"Invalid or missing {INSTALL_PREP_REL}"}

    driver_repair = install_prep.get("driver_repair_20261103", {})
    phase10 = (
        driver_repair.get("phase10_lidwake_and_safari_green_video_fix_20261108", {})
        if isinstance(driver_repair, dict)
        else {}
    )
    if local_dir_exists:
        if not isinstance(phase10, dict) or not phase10:
            errors.append(
                "Missing driver_repair_20261103.phase10_lidwake_and_safari_green_video_fix_20261108 "
                f"in {INSTALL_PREP_REL}"
            )
            return {"passed": False, "local_present": True, "error": "Missing phase10 configuration block"}
        repo_meta = phase10
    else:
        public_tracked = (
            install_prep.get("public_tracked_files", {})
            if install_prep.get("record_type") == "sanitized_public_current_status"
            else {}
        )
        repo_meta = (
            phase10
            if (isinstance(phase10, dict) and phase10)
            else (public_tracked if isinstance(public_tracked, dict) else {})
        )
        if not repo_meta:
            errors.append(
                "Missing driver_repair_20261103.phase10_lidwake_and_safari_green_video_fix_20261108 "
                f"(or public_tracked_files for sanitized_public_current_status) in {INSTALL_PREP_REL}"
            )
            return {"passed": False, "local_present": False, "error": "Missing phase10 or public_tracked_files block"}

    # Always verify repository-tracked files referenced in phase10 / public_tracked_files
    repo_tracked_checks = [
        ("nootedgreen_patch", repo_meta.get("nootedgreen_patch", "patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch"), repo_meta.get("nootedgreen_patch_sha256"), repo_meta.get("nootedgreen_patch_size_bytes")),
        ("readme_md", "README.md", repo_meta.get("readme_md_sha256"), repo_meta.get("readme_md_size_bytes")),
        ("clean_install_guide_md", "docs/clean-install-guide.md", repo_meta.get("clean_install_guide_md_sha256"), repo_meta.get("clean_install_guide_md_size_bytes")),
        ("from_source_rebuild_guide_md", "docs/from-source-rebuild-guide.md", repo_meta.get("from_source_rebuild_guide_md_sha256"), repo_meta.get("from_source_rebuild_guide_md_size_bytes")),
        ("makefile", repo_meta.get("makefile", "Makefile"), repo_meta.get("makefile_sha256"), repo_meta.get("makefile_size_bytes")),
        ("verify_release_artifacts_py", repo_meta.get("verify_release_artifacts_py", "scripts/verify_release_artifacts.py"), repo_meta.get("verify_release_artifacts_py_sha256"), repo_meta.get("verify_release_artifacts_py_size_bytes")),
    ]

    verified_files: list[dict] = []
    for label, rel_path, expected_sha, expected_size in repo_tracked_checks:
        if not rel_path:
            errors.append(f"[{label}] Missing repository file path in manifest")
            verified_files.append({"label": label, "path": rel_path, "sha256": None, "size_bytes": None, "matched": False})
            continue
        fpath = root / rel_path
        if not fpath.is_file():
            errors.append(f"[{label}] Missing repository file: {rel_path}")
            verified_files.append({"label": label, "path": rel_path, "sha256": None, "size_bytes": None, "matched": False})
            continue
        actual_sha, actual_size = sha256_file(fpath)
        sha_ok = actual_sha == expected_sha
        size_ok = expected_size is None or actual_size == expected_size
        if not sha_ok:
            errors.append(f"[{label}] SHA256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}")
        if not size_ok:
            errors.append(f"[{label}] Size mismatch for {rel_path}: expected {expected_size}, got {actual_size}")
        verified_files.append({
            "label": label,
            "path": rel_path,
            "sha256": actual_sha,
            "size_bytes": actual_size,
            "matched": sha_ok and size_ok,
        })

    if not local_dir_exists:
        return {
            "passed": len(errors) == 0 and all(f["matched"] for f in verified_files),
            "local_present": False,
            "verified_file_count": len(verified_files),
            "verified_files": verified_files,
            "cross_manifest_parity_checks": [],
        }

    deploy_receipt_rel = phase10.get("deploy_receipt", DEPLOY_RECEIPT_REL)
    deploy_receipt_path = root / deploy_receipt_rel
    bundle_receipt_path = root / BUNDLE_RECEIPT_REL

    deploy_receipt = load_json_safe(deploy_receipt_path, deploy_receipt_rel, errors)
    bundle_receipt = load_json_safe(bundle_receipt_path, BUNDLE_RECEIPT_REL, errors)
    if deploy_receipt is None or bundle_receipt is None:
        return {
            "passed": False,
            "local_present": True,
            "verified_file_count": len(verified_files),
            "verified_files": verified_files,
            "cross_manifest_parity_checks": [],
            "error": "Missing or invalid receipt JSON in .local/",
        }

    deployed = deploy_receipt.get("deployed_artifacts", {})
    if not isinstance(deployed, dict):
        errors.append(f"Invalid deployed_artifacts in {deploy_receipt_rel}")
        deployed = {}

    # Verify local_bundle_dir and local_archive_path recorded in bundle-receipt.json
    rec_bundle_dir = str(bundle_receipt.get("local_bundle_dir", ""))
    rec_archive_path = str(bundle_receipt.get("local_archive_path", ""))
    if not rec_bundle_dir.endswith(BUNDLE_DIR_REL) or not (root / BUNDLE_DIR_REL).is_dir():
        errors.append(
            f"[bundle_receipt.local_bundle_dir] Expected directory ending with {BUNDLE_DIR_REL}, got {rec_bundle_dir!r}"
        )
    if not rec_archive_path.endswith(BUNDLE_TAR_GZ_REL) or not (root / BUNDLE_TAR_GZ_REL).is_file():
        errors.append(
            f"[bundle_receipt.local_archive_path] Expected file ending with {BUNDLE_TAR_GZ_REL}, got {rec_archive_path!r}"
        )

    local_file_checks = [
        ("deploy_receipt", phase10.get("deploy_receipt"), phase10.get("deploy_receipt_sha256"), None),
        ("postinstall_bundle_receipt_json", deployed.get("postinstall_bundle_receipt_json"), deployed.get("postinstall_bundle_receipt_json_sha256"), deployed.get("postinstall_bundle_receipt_json_size_bytes")),
        ("efivars_post_ebaba2ee_tar", phase10.get("efivars_post_ebaba2ee_tar"), phase10.get("efivars_post_ebaba2ee_tar_sha256"), None),
        ("before_boot_oc_tar", phase10.get("before_boot_oc_tar"), phase10.get("before_boot_oc_tar_sha256"), None),
        ("after_boot_oc_tar", phase10.get("after_boot_oc_tar"), phase10.get("after_boot_oc_tar_sha256"), None),
        ("ssdt_deepidle_dsl", deployed.get("ssdt_deepidle_dsl"), deployed.get("ssdt_deepidle_dsl_sha256"), None),
        ("ssdt_deepidle_aml", deployed.get("ssdt_deepidle_aml"), deployed.get("ssdt_deepidle_aml_sha256"), None),
        ("kern_gen11_cpp", deployed.get("kern_gen11_cpp"), deployed.get("kern_gen11_cpp_sha256"), None),
        ("nootedgreen_bin", deployed.get("nootedgreen_bin"), deployed.get("nootedgreen_bin_sha256"), None),
        ("nootedgreen_info_plist", ".local/driver-repair-20261103/repair32-readback/build/snapshot/NootedGreen.kext/Contents/Info.plist", deployed.get("nootedgreen_info_plist_sha256"), None),
        ("s0ixstandby_cpp", deployed.get("s0ixstandby_cpp"), deployed.get("s0ixstandby_cpp_sha256"), deployed.get("s0ixstandby_cpp_size_bytes")),
        ("s0ixstandby_gpu_cpp", deployed.get("s0ixstandby_gpu_cpp"), deployed.get("s0ixstandby_gpu_cpp_sha256"), deployed.get("s0ixstandby_gpu_cpp_size_bytes")),
        ("s0ixstandby_hpp", deployed.get("s0ixstandby_hpp"), deployed.get("s0ixstandby_hpp_sha256"), deployed.get("s0ixstandby_hpp_size_bytes")),
        ("s0ixstandby_bin", deployed.get("s0ixstandby_bin"), deployed.get("s0ixstandby_bin_sha256"), deployed.get("s0ixstandby_bin_size_bytes")),
        ("config_plist", ".local/driver-repair-20261103/s0ix-standby-prep-20261107/config.plist", deployed.get("config_plist_sha256"), None),
        ("bundle_efi_config_plist", f"{BUNDLE_DIR_REL}/EFI-OC/OC/config.plist", deployed.get("config_plist_sha256"), None),
        ("libxedrv_m", deployed.get("libxedrv_m"), deployed.get("libxedrv_m_sha256"), None),
        ("libxedrv_dylib", deployed.get("libxedrv_dylib"), deployed.get("libxedrv_dylib_sha256"), None),
        ("verify_postinstall_sh", deployed.get("verify_postinstall_sh"), deployed.get("verify_postinstall_sh_sha256"), deployed.get("verify_postinstall_sh_size_bytes")),
        ("verify_phase10_lidwake_and_video_sh", deployed.get("verify_phase10_lidwake_and_video_sh"), deployed.get("verify_phase10_lidwake_and_video_sh_sha256"), deployed.get("verify_phase10_lidwake_and_video_sh_size_bytes")),
        ("test_420v_blitalign", deployed.get("test_420v_blitalign"), deployed.get("test_420v_blitalign_sha256"), deployed.get("test_420v_blitalign_size_bytes")),
        ("postinstall_bundle_tar_gz", deployed.get("postinstall_bundle_tar_gz"), deployed.get("postinstall_bundle_tar_gz_sha256"), deployed.get("postinstall_bundle_tar_gz_size_bytes")),
        ("postinstall_sha256sums", deployed.get("postinstall_sha256sums"), deployed.get("postinstall_sha256sums_sha256"), deployed.get("postinstall_sha256sums_size_bytes")),
        ("recovery_img", deployed.get("recovery_img"), deployed.get("recovery_img_sha256"), deployed.get("recovery_img_size_bytes")),
        ("phase10_audit_report_md", phase10.get("phase10_audit_report_md"), phase10.get("phase10_audit_report_md_sha256"), None),
        ("phase10_audit_report_json", phase10.get("phase10_audit_report_json"), phase10.get("phase10_audit_report_json_sha256"), None),
        ("phase11_parity_audit_md", phase10.get("phase11_parity_audit_md"), phase10.get("phase11_parity_audit_md_sha256"), None),
        ("phase11_parity_audit_json", phase10.get("phase11_parity_audit_json"), phase10.get("phase11_parity_audit_json_sha256"), None),
        ("phase12_cross_session_audit_md", phase10.get("phase12_cross_session_audit_md"), phase10.get("phase12_cross_session_audit_md_sha256"), phase10.get("phase12_cross_session_audit_md_size_bytes")),
        ("phase12_cross_session_audit_json", phase10.get("phase12_cross_session_audit_json"), phase10.get("phase12_cross_session_audit_json_sha256"), phase10.get("phase12_cross_session_audit_json_size_bytes")),
    ]

    # Also verify bundle-receipt.json phase10_updated_artifacts and scripts on disk
    p10_updated = bundle_receipt.get("phase10_updated_artifacts", {})
    if isinstance(p10_updated, dict):
        for rel_in_bundle, expected_sha in p10_updated.items():
            local_file_checks.append((
                f"bundle_receipt.phase10_updated_artifacts[{rel_in_bundle}]",
                f"{BUNDLE_DIR_REL}/{rel_in_bundle}",
                expected_sha,
                None,
            ))
    bundle_scripts_map = bundle_receipt.get("scripts", {})
    if isinstance(bundle_scripts_map, dict):
        for script_name, expected_sha in bundle_scripts_map.items():
            local_file_checks.append((
                f"bundle_receipt.scripts[{script_name}]",
                f"{BUNDLE_DIR_REL}/{script_name}",
                expected_sha,
                None,
            ))

    for label, rel_path, expected_sha, expected_size in local_file_checks:
        if not rel_path or not isinstance(rel_path, str):
            errors.append(f"[{label}] Missing local file path in manifest")
            verified_files.append({
                "label": label,
                "path": rel_path,
                "sha256": None,
                "size_bytes": None,
                "matched": False,
            })
            continue
        fpath = root / rel_path
        if not fpath.is_file():
            errors.append(f"[{label}] Missing local file: {rel_path}")
            verified_files.append({
                "label": label,
                "path": rel_path,
                "sha256": None,
                "size_bytes": None,
                "matched": False,
            })
            continue
        actual_sha, actual_size = sha256_file(fpath)
        sha_ok = actual_sha == expected_sha
        size_ok = expected_size is None or actual_size == expected_size
        if not sha_ok:
            errors.append(f"[{label}] SHA256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}")
        if not size_ok:
            errors.append(f"[{label}] Size mismatch for {rel_path}: expected {expected_size}, got {actual_size}")
        verified_files.append({
            "label": label,
            "path": rel_path,
            "sha256": actual_sha,
            "size_bytes": actual_size,
            "matched": sha_ok and size_ok,
        })

    # Verify cross-manifest agreement across shared keys
    staged_ntfs = bundle_receipt.get("staged_on_target_ntfs", {})
    if not isinstance(staged_ntfs, dict):
        staged_ntfs = {}
    staged_tools = staged_ntfs.get("additional_staged_tools", {})
    if not isinstance(staged_tools, dict):
        staged_tools = {}
    p10_bundle = p10_updated if isinstance(p10_updated, dict) else {}
    bundle_scripts = bundle_scripts_map if isinstance(bundle_scripts_map, dict) else {}

    parity_pairs = [
        ("nixos_boot_id", [
            driver_repair.get("current_nixos_boot_latest"),
            phase10.get("nixos_boot_id"),
            deploy_receipt.get("nixos_boot_id"),
            staged_ntfs.get("nixos_boot_id"),
        ]),
        ("previous_macos_boot_uuid", [
            phase10.get("previous_macos_boot_uuid", deploy_receipt.get("previous_macos_boot_uuid")),
            deploy_receipt.get("previous_macos_boot_uuid"),
        ]),
        ("efivars_post_ebaba2ee_tar", [phase10.get("efivars_post_ebaba2ee_tar"), deploy_receipt.get("efivars_post_ebaba2ee_tar")]),
        ("efivars_post_ebaba2ee_tar_sha256", [phase10.get("efivars_post_ebaba2ee_tar_sha256"), deploy_receipt.get("efivars_post_ebaba2ee_tar_sha256")]),
        ("before_boot_oc_tar", [phase10.get("before_boot_oc_tar"), deploy_receipt.get("before_boot_oc_tar")]),
        ("before_boot_oc_tar_sha256", [phase10.get("before_boot_oc_tar_sha256"), deploy_receipt.get("before_boot_oc_tar_sha256")]),
        ("after_boot_oc_tar", [phase10.get("after_boot_oc_tar"), deploy_receipt.get("after_boot_oc_tar")]),
        ("after_boot_oc_tar_sha256", [phase10.get("after_boot_oc_tar_sha256"), deploy_receipt.get("after_boot_oc_tar_sha256")]),
        ("ssdt_deepidle_dsl_sha256", [phase10.get("ssdt_deepidle_dsl_sha256"), deployed.get("ssdt_deepidle_dsl_sha256")]),
        ("ssdt_deepidle_aml_sha256", [phase10.get("ssdt_deepidle_aml_sha256"), deployed.get("ssdt_deepidle_aml_sha256"), p10_bundle.get("EFI-OC/OC/ACPI/SSDT-DEEPIDLE.aml")]),
        ("nootedgreen_patch", [phase10.get("nootedgreen_patch"), deployed.get("nootedgreen_patch")]),
        ("nootedgreen_patch_sha256", [phase10.get("nootedgreen_patch_sha256"), deployed.get("nootedgreen_patch_sha256")]),
        ("kern_gen11_cpp_sha256", [phase10.get("kern_gen11_cpp_sha256"), deployed.get("kern_gen11_cpp_sha256")]),
        ("nootedgreen_bin_sha256", [phase10.get("nootedgreen_bin_sha256"), deployed.get("nootedgreen_bin_sha256"), p10_bundle.get("EFI-OC/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen")]),
        ("nootedgreen_info_plist_sha256", [deployed.get("nootedgreen_info_plist_sha256"), p10_bundle.get("EFI-OC/OC/Kexts/NootedGreen.kext/Contents/Info.plist")]),
        ("nootedgreen_uuid", [phase10.get("nootedgreen_uuid"), deployed.get("nootedgreen_uuid")]),
        ("s0ixstandby_cpp_sha256", [phase10.get("s0ixstandby_cpp_sha256"), deployed.get("s0ixstandby_cpp_sha256")]),
        ("s0ixstandby_gpu_cpp_sha256", [phase10.get("s0ixstandby_gpu_cpp_sha256"), deployed.get("s0ixstandby_gpu_cpp_sha256")]),
        ("s0ixstandby_hpp_sha256", [phase10.get("s0ixstandby_hpp_sha256"), deployed.get("s0ixstandby_hpp_sha256")]),
        ("s0ixstandby_bin_sha256", [phase10.get("s0ixstandby_bin_sha256"), deployed.get("s0ixstandby_bin_sha256"), p10_bundle.get("EFI-OC/OC/Kexts/S0ixStandby.kext/Contents/MacOS/S0ixStandby")]),
        ("libxedrv_m_sha256", [phase10.get("libxedrv_m_sha256"), deployed.get("libxedrv_m_sha256")]),
        ("libxedrv_dylib_sha256", [phase10.get("libxedrv_dylib_sha256"), deployed.get("libxedrv_dylib_sha256"), p10_bundle.get("stage2-gpu/Library-GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib")]),
        ("recovery_img_path", [phase10.get("recovery_img_path"), deployed.get("recovery_img")]),
        ("recovery_img_sha256", [phase10.get("recovery_img_sha256"), deployed.get("recovery_img_sha256")]),
        ("postinstall_bundle_tar_gz_sha256", [
            phase10.get("postinstall_bundle_tar_gz_sha256"),
            deployed.get("postinstall_bundle_tar_gz_sha256"),
            bundle_receipt.get("local_archive_sha256"),
        ]),
        ("postinstall_bundle_tar_gz_size_bytes", [
            deployed.get("postinstall_bundle_tar_gz_size_bytes"),
            bundle_receipt.get("local_archive_size_bytes"),
        ]),
        ("win_sys_postinstall_tar_gz_sha256", [
            deployed.get("win_sys_postinstall_tar_gz_sha256"),
            bundle_receipt.get("win_sys_archive_sha256"),
            staged_ntfs.get("sha256"),
        ]),
        ("win_sys_postinstall_tar_gz_ntfs_path", [
            deployed.get("win_sys_postinstall_tar_gz"),
            staged_ntfs.get("ntfs_path"),
        ]),
        ("win_sys_postinstall_tar_gz_macos_path", [
            bundle_receipt.get("win_sys_archive_path"),
            staged_ntfs.get("macos_path"),
        ]),
        ("postinstall_sha256sums_sha256", [
            phase10.get("postinstall_sha256sums_sha256"),
            deployed.get("postinstall_sha256sums_sha256"),
            bundle_receipt.get("sha256sums_manifest_sha256"),
        ]),
        ("postinstall_sha256sums_file_count", [
            deployed.get("postinstall_sha256sums_file_count"),
            bundle_receipt.get("total_files_in_manifest"),
            431,
        ]),
        ("postinstall_bundle_receipt_sha256", [
            phase10.get("postinstall_bundle_receipt_sha256"),
            deployed.get("postinstall_bundle_receipt_json_sha256"),
        ]),
        ("verify_postinstall_sh_sha256", [
            deployed.get("verify_postinstall_sh_sha256"),
            bundle_scripts.get("verify-postinstall.sh"),
        ]),
        ("verify_phase10_lidwake_and_video_sh_sha256", [
            deployed.get("verify_phase10_lidwake_and_video_sh_sha256"),
            p10_bundle.get("verify-phase10-lidwake-and-video.sh"),
            bundle_scripts.get("verify-phase10-lidwake-and-video.sh"),
            staged_tools.get("/mnt/win_sys/hpdiag/verify-phase10-lidwake-and-video.sh", {}).get("sha256"),
        ]),
        ("verify_phase10_lidwake_and_video_sh_size_bytes", [
            deployed.get("verify_phase10_lidwake_and_video_sh_size_bytes"),
            staged_tools.get("/mnt/win_sys/hpdiag/verify-phase10-lidwake-and-video.sh", {}).get("size_bytes"),
        ]),
        ("test_420v_blitalign_sha256", [
            deployed.get("test_420v_blitalign_sha256"),
            p10_bundle.get("test_420v_blitalign"),
            staged_tools.get("/mnt/win_sys/hpdiag/test_420v_blitalign", {}).get("sha256"),
        ]),
        ("test_420v_blitalign_size_bytes", [
            deployed.get("test_420v_blitalign_size_bytes"),
            staged_tools.get("/mnt/win_sys/hpdiag/test_420v_blitalign", {}).get("size_bytes"),
        ]),
        ("readme_md_sha256", [phase10.get("readme_md_sha256"), deployed.get("readme_md_sha256")]),
        ("clean_install_guide_md_sha256", [phase10.get("clean_install_guide_md_sha256"), deployed.get("clean_install_guide_md_sha256")]),
        ("from_source_rebuild_guide_md_sha256", [phase10.get("from_source_rebuild_guide_md_sha256"), deployed.get("from_source_rebuild_guide_md_sha256")]),
    ]

    parity_results: list[dict] = []
    for key_name, values in parity_pairs:
        try:
            distinct = set(values)
        except TypeError:
            distinct = set()
        ok = len(distinct) == 1 and None not in distinct
        if not ok:
            errors.append(f"Cross-manifest disagreement for {key_name}: {values!r}")
        parity_results.append({
            "key": key_name,
            "value": values[0] if ok else values,
            "matched": ok,
        })

    bundle_paths_ok = (
        rec_bundle_dir.endswith(BUNDLE_DIR_REL)
        and (root / BUNDLE_DIR_REL).is_dir()
        and rec_archive_path.endswith(BUNDLE_TAR_GZ_REL)
        and (root / BUNDLE_TAR_GZ_REL).is_file()
    )
    return {
        "passed": (
            bundle_paths_ok
            and all(f["matched"] for f in verified_files)
            and all(p["matched"] for p in parity_results)
        ),
        "local_present": True,
        "verified_file_count": len(verified_files),
        "verified_files": verified_files,
        "cross_manifest_parity_count": len(parity_results),
        "cross_manifest_parity_checks": parity_results,
    }


def verify_section2_postinstall_bundle(root: Path, errors: list[str]) -> dict:
    """2. 431-File Post-Install Bundle (HP-Tahoe-PostInstall-20261108) Integrity."""
    bundle_dir = root / BUNDLE_DIR_REL
    bundle_tar = root / BUNDLE_TAR_GZ_REL
    sha256sums_path = bundle_dir / "SHA256SUMS.txt"

    if not bundle_dir.is_dir() or not sha256sums_path.is_file():
        errors.append(f"Missing post-install bundle directory or SHA256SUMS.txt: {sha256sums_path}")
        return {"passed": False, "error": "Missing post-install bundle"}

    sha256sums_sha, sha256sums_size = sha256_file(sha256sums_path)
    if sha256sums_size != 64420:
        errors.append(f"SHA256SUMS.txt byte size mismatch: expected 64420, got {sha256sums_size}")

    manifest_entries = parse_sha256sums(sha256sums_path.read_text(encoding="utf-8", errors="replace"), errors)
    if len(manifest_entries) != 431:
        errors.append(f"SHA256SUMS.txt entry count mismatch: expected 431, got {len(manifest_entries)}")

    # Verify all 431 files on disk against SHA256SUMS.txt and check for untracked extra files
    disk_files = {
        p.relative_to(bundle_dir).as_posix()
        for p in bundle_dir.rglob("*")
        if p.is_file() and p.name != "SHA256SUMS.txt"
    }
    missing_on_disk = sorted(set(manifest_entries) - disk_files)
    extra_on_disk = sorted(disk_files - set(manifest_entries))
    if missing_on_disk:
        errors.append(f"Bundle directory missing {len(missing_on_disk)} files: {missing_on_disk[:5]}")
    if extra_on_disk:
        errors.append(f"Bundle directory has {len(extra_on_disk)} untracked files: {extra_on_disk[:5]}")

    disk_mismatches: list[str] = []
    disk_verified = 0
    for rel_path, expected_sha in manifest_entries.items():
        fpath = bundle_dir / rel_path
        if not fpath.is_file():
            continue
        actual_sha, _ = sha256_file(fpath)
        if actual_sha != expected_sha:
            disk_mismatches.append(rel_path)
            errors.append(f"Bundle disk SHA256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}")
        else:
            disk_verified += 1

    # Verify HP-Tahoe-PostInstall-20261108.tar.gz by streaming tar members
    if not bundle_tar.is_file():
        errors.append(f"Missing post-install archive: {BUNDLE_TAR_GZ_REL}")
        return {"passed": False, "error": f"Missing {BUNDLE_TAR_GZ_REL}"}

    tar_sha, tar_size = sha256_file(bundle_tar)
    if tar_size != 125569879:
        errors.append(f"HP-Tahoe-PostInstall-20261108.tar.gz size mismatch: expected 125569879, got {tar_size}")

    prefix = "HP-Tahoe-PostInstall-20261108/"
    tar_file_hashes: dict[str, str] = {}
    tar_sha256sums_sha: str | None = None
    tar_stream_ok = True

    try:
        with tarfile.open(bundle_tar, "r:gz") as tf:
            for member in tf:
                if not member.isfile():
                    continue
                name = member.name
                if name.startswith("./"):
                    name = name[2:]
                if not name.startswith(prefix):
                    errors.append(f"Unexpected tar member prefix in {BUNDLE_TAR_GZ_REL}: {member.name}")
                    tar_stream_ok = False
                    continue
                rel_name = name[len(prefix):]
                extracted = tf.extractfile(member)
                if extracted is None:
                    errors.append(f"Unable to stream tar member: {member.name}")
                    tar_stream_ok = False
                    continue
                digest, _ = sha256_stream(extracted)
                if rel_name == "SHA256SUMS.txt":
                    if tar_sha256sums_sha is not None:
                        errors.append(f"Duplicate SHA256SUMS.txt member in {BUNDLE_TAR_GZ_REL}")
                        tar_stream_ok = False
                    tar_sha256sums_sha = digest
                else:
                    if rel_name in tar_file_hashes:
                        errors.append(f"Duplicate tar member in {BUNDLE_TAR_GZ_REL}: {rel_name}")
                        tar_stream_ok = False
                    tar_file_hashes[rel_name] = digest
    except (tarfile.TarError, EOFError, OSError) as exc:
        errors.append(f"Corrupted or unreadable tar.gz archive {BUNDLE_TAR_GZ_REL}: {exc}")
        tar_stream_ok = False

    if tar_sha256sums_sha != sha256sums_sha:
        errors.append(
            f"SHA256SUMS.txt inside tar.gz ({tar_sha256sums_sha}) does not match disk ({sha256sums_sha})"
        )

    missing_in_tar = sorted(set(manifest_entries) - set(tar_file_hashes))
    extra_in_tar = sorted(set(tar_file_hashes) - set(manifest_entries))
    if missing_in_tar:
        errors.append(f"Archive missing {len(missing_in_tar)} files from SHA256SUMS.txt: {missing_in_tar[:5]}")
    if extra_in_tar:
        errors.append(f"Archive has {len(extra_in_tar)} extra files not in SHA256SUMS.txt: {extra_in_tar[:5]}")

    tar_mismatches: list[str] = []
    tar_verified = 0
    for rel_path, expected_sha in manifest_entries.items():
        actual_sha = tar_file_hashes.get(rel_path)
        if actual_sha is None:
            continue
        if actual_sha != expected_sha:
            tar_mismatches.append(rel_path)
            errors.append(f"Archive member SHA256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}")
        else:
            tar_verified += 1

    passed = (
        sha256sums_size == 64420
        and len(manifest_entries) == 431
        and not missing_on_disk
        and not extra_on_disk
        and not disk_mismatches
        and tar_size == 125569879
        and tar_stream_ok
        and tar_sha256sums_sha == sha256sums_sha
        and not missing_in_tar
        and not extra_in_tar
        and not tar_mismatches
    )
    return {
        "passed": passed,
        "sha256sums_path": f"{BUNDLE_DIR_REL}/SHA256SUMS.txt",
        "sha256sums_size_bytes": sha256sums_size,
        "sha256sums_sha256": sha256sums_sha,
        "manifest_entry_count": len(manifest_entries),
        "disk_verified_count": disk_verified,
        "disk_mismatches": disk_mismatches,
        "archive_path": BUNDLE_TAR_GZ_REL,
        "archive_size_bytes": tar_size,
        "archive_sha256": tar_sha,
        "archive_verified_count": tar_verified,
        "archive_sha256sums_member_matched": tar_sha256sums_sha == sha256sums_sha,
        "archive_mismatches": tar_mismatches,
    }


def verify_section3_efi_parity(root: Path, errors: list[str]) -> dict:
    """3. 112-File OpenCore EFI Parity across Bundle, Recovery .img, and Target /boot/EFI/OC Readback Tar."""
    bundle_efi = root / BUNDLE_DIR_REL / "EFI-OC"
    oc_readback_tar = (
        root
        / ".local/driver-repair-20261103/s0ix-standby-prep-20261107/"
        "post-wake-ebaba2ee/after-lidwake-greenfix-boot-oc.tar"
    )
    recovery_img = root / RECOVERY_IMG_REL

    if not bundle_efi.is_dir():
        errors.append(f"Missing bundle EFI-OC directory: {bundle_efi}")
        return {"passed": False, "error": "Missing bundle EFI-OC directory"}

    bundle_efi_hashes: dict[str, str] = {}
    for p in sorted(bundle_efi.rglob("*")):
        if p.is_file():
            rel = p.relative_to(bundle_efi).as_posix()
            bundle_efi_hashes[rel], _ = sha256_file(p)

    bundle_oc_hashes = {
        rel: sha for rel, sha in bundle_efi_hashes.items() if rel.startswith("OC/")
    }
    if len(bundle_efi_hashes) != 112:
        errors.append(f"Expected 112 files in EFI-OC (BOOT/BOOTx64.efi + 111 OC/ files), got {len(bundle_efi_hashes)}")
    if len(bundle_oc_hashes) != 111:
        errors.append(f"Expected 111 files in EFI-OC/OC/, got {len(bundle_oc_hashes)}")

    # Compare against after-lidwake-greenfix-boot-oc.tar
    readback_tar_hashes: dict[str, str] = {}
    skipped_runtime_logs: list[str] = []
    readback_stream_ok = True
    if not oc_readback_tar.is_file():
        errors.append(f"Missing target OC readback tar: {oc_readback_tar.relative_to(root)}")
        readback_stream_ok = False
    else:
        try:
            with tarfile.open(oc_readback_tar, "r:*") as tf:
                for member in tf:
                    if not member.isfile():
                        continue
                    name = member.name
                    if name.startswith("./"):
                        name = name[2:]
                    if name.startswith("OC/opencore-") and name.endswith(".txt"):
                        skipped_runtime_logs.append(name)
                        continue
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        errors.append(f"Unable to read member {name} in {oc_readback_tar.name}")
                        readback_stream_ok = False
                        continue
                    if name in readback_tar_hashes:
                        errors.append(f"Duplicate member {name} in {oc_readback_tar.name}")
                        readback_stream_ok = False
                    readback_tar_hashes[name], _ = sha256_stream(extracted)
        except (tarfile.TarError, EOFError, OSError) as exc:
            errors.append(f"Corrupted or unreadable tar archive {oc_readback_tar.name}: {exc}")
            readback_stream_ok = False

    missing_in_readback = sorted(set(bundle_oc_hashes) - set(readback_tar_hashes))
    extra_in_readback = sorted(set(readback_tar_hashes) - set(bundle_oc_hashes))
    if missing_in_readback:
        errors.append(f"after-lidwake-greenfix-boot-oc.tar missing {len(missing_in_readback)} OC files: {missing_in_readback[:5]}")
    if extra_in_readback:
        errors.append(f"after-lidwake-greenfix-boot-oc.tar has {len(extra_in_readback)} extra OC files: {extra_in_readback[:5]}")

    readback_mismatches: list[str] = []
    readback_verified = 0
    for rel, expected_sha in bundle_oc_hashes.items():
        actual_sha = readback_tar_hashes.get(rel)
        if actual_sha is None:
            continue
        if actual_sha != expected_sha:
            readback_mismatches.append(rel)
            errors.append(f"Readback tar SHA256 mismatch for {rel}: expected {expected_sha}, got {actual_sha}")
        else:
            readback_verified += 1

    # Compare against HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img:
    # 1) Pure-Python FAT32 partition traversal verifies all 112 EFI/ files and detects extra/missing files
    #    even when mtools is not installed.
    # 2) When mtype/mdir are available in PATH, also verify RECOVERY_KEY_EFI_FILES via mdir/mtype.
    mtype_bin = shutil.which("mtype")
    mdir_bin = shutil.which("mdir")
    mtools_available = bool(mtype_bin and mdir_bin)
    recovery_verified_count = 0
    recovery_mismatches: list[str] = []
    recovery_missing: list[str] = []
    recovery_extra: list[str] = []
    recovery_key_files_report: dict[str, dict] = {}

    if not recovery_img.is_file():
        errors.append(f"Missing recovery image: {RECOVERY_IMG_REL}")
    else:
        fat_tree = read_fat32_partition_files(recovery_img, RECOVERY_ESP_OFFSET, errors)
        fat_efi_files = {
            rel[4:]: info
            for rel, info in fat_tree.items()
            if rel.startswith("EFI/")
        }
        recovery_missing = sorted(set(bundle_efi_hashes) - set(fat_efi_files))
        recovery_extra = sorted(set(fat_efi_files) - set(bundle_efi_hashes))
        if recovery_missing:
            errors.append(f"Recovery image missing {len(recovery_missing)} EFI files: {recovery_missing[:5]}")
        if recovery_extra:
            errors.append(f"Recovery image has {len(recovery_extra)} extra EFI files: {recovery_extra[:5]}")

        for rel, expected_sha in bundle_efi_hashes.items():
            fat_info = fat_efi_files.get(rel)
            if fat_info is None:
                recovery_mismatches.append(rel)
                continue
            actual_sha, actual_size = fat_info
            matched = actual_sha == expected_sha
            if not matched:
                recovery_mismatches.append(rel)
                errors.append(
                    f"Recovery image SHA256 mismatch for ::/EFI/{rel}: expected {expected_sha}, got {actual_sha}"
                )
            else:
                recovery_verified_count += 1
            if rel in RECOVERY_KEY_EFI_FILES:
                recovery_key_files_report[rel] = {
                    "sha256": actual_sha,
                    "size_bytes": actual_size,
                    "matched": matched,
                }

        if mtools_available:
            img_spec = f"{recovery_img}@@{RECOVERY_ESP_OFFSET}"
            mdir_proc = subprocess.run(
                [mdir_bin, "-i", img_spec, "::/EFI/OC"],
                capture_output=True,
                text=True,
                check=False,
            )
            if mdir_proc.returncode != 0:
                errors.append(f"mdir failed on {RECOVERY_IMG_REL}@@{RECOVERY_ESP_OFFSET}: {mdir_proc.stderr.strip()}")
            else:
                for rel in RECOVERY_KEY_EFI_FILES:
                    expected_sha = bundle_efi_hashes.get(rel)
                    proc = subprocess.run(
                        [mtype_bin, "-i", img_spec, f"::/EFI/{rel}"],
                        capture_output=True,
                        check=False,
                    )
                    if proc.returncode != 0:
                        if rel not in recovery_mismatches:
                            recovery_mismatches.append(rel)
                        errors.append(
                            f"mtype failed for ::/EFI/{rel} in recovery image: {proc.stderr.decode(errors='replace').strip()}"
                        )
                        continue
                    mtype_sha = hashlib.sha256(proc.stdout).hexdigest()
                    matched = mtype_sha == expected_sha
                    if not matched:
                        if rel not in recovery_mismatches:
                            recovery_mismatches.append(rel)
                        errors.append(
                            f"mtype SHA256 mismatch for ::/EFI/{rel}: expected {expected_sha}, got {mtype_sha}"
                        )
                    recovery_key_files_report[rel] = {
                        "sha256": mtype_sha,
                        "size_bytes": len(proc.stdout),
                        "matched": matched,
                    }

    passed = (
        len(bundle_efi_hashes) == 112
        and len(bundle_oc_hashes) == 111
        and readback_stream_ok
        and not missing_in_readback
        and not extra_in_readback
        and not readback_mismatches
        and recovery_img.is_file()
        and recovery_verified_count == 112
        and not recovery_missing
        and not recovery_extra
        and not recovery_mismatches
    )
    return {
        "passed": passed,
        "bundle_efi_total_files": len(bundle_efi_hashes),
        "bundle_oc_files": len(bundle_oc_hashes),
        "readback_tar_path": oc_readback_tar.relative_to(root).as_posix(),
        "readback_tar_verified_oc_files": readback_verified,
        "readback_tar_skipped_runtime_logs": skipped_runtime_logs,
        "readback_tar_mismatches": readback_mismatches,
        "recovery_img_path": RECOVERY_IMG_REL,
        "recovery_esp_offset_bytes": RECOVERY_ESP_OFFSET,
        "mtools_available": mtools_available,
        "recovery_img_verified_efi_files": recovery_verified_count,
        "recovery_img_mismatches": recovery_mismatches,
        "recovery_key_files": recovery_key_files_report,
    }


def verify_section4_binary_markers(root: Path, errors: list[str]) -> dict:
    """4. Binary Feature & Fix Marker Verification."""
    bundle_dir = root / BUNDLE_DIR_REL
    patch_path = root / "patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch"

    # In SSDT-DEEPIDLE.aml, Package (0x02) { 0x6E, 0x04 } in _PRW / PRW0 is encoded
    # in AML as 0x12 0x06 0x02 0x0A 0x6E 0x0A 0x04 (occurring 4 times: LID_._PRW,
    # LID_.PRW0, SLPB._PRW, SLPB.PRW0). Checking this exact AML sequence avoids
    # false-matching the ASCII 'n' (0x6e) in _OSI ("Darwin").
    aml_prw_gpe6e_pkg = b"\x12\x06\x02\x0a\x6e\x0a\x04"

    targets = [
        {
            "name": "NootedGreen",
            "path": bundle_dir / "EFI-OC/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen",
            "expected_sha256": "00982625148fe975c777a2e24f433d1624f2b45f08169acdba7883d18a33e5e3",
            "expected_size_bytes": 540944,
            "markers": [
                ("HP-BLITALIGN", b"HP-BLITALIGN"),
                ("HP-BLITFIX", b"HP-BLITFIX"),
                ("HP-BLIT16", b"HP-BLIT16"),
                ("R32-PCFIX36-WAKECOLOR", b"R32-PCFIX36-WAKECOLOR"),
                ("ngreen-wake-plane-rgb-fix", b"ngreen-wake-plane-rgb-fix"),
            ],
        },
        {
            "name": "S0ixStandby",
            "path": bundle_dir / "EFI-OC/OC/Kexts/S0ixStandby.kext/Contents/MacOS/S0ixStandby",
            "expected_sha256": "be55592c42c5003cd86ac99695c56dbd92b368954301a78d3eecdd3095411184",
            "expected_size_bytes": 74584,
            "markers": [
                ("-s0ixcnvwd3", b"-s0ixcnvwd3"),
                ("-s0ixusbwake", b"-s0ixusbwake"),
                ("wifiTimerFired", b"wifiTimerFired"),
                ("pmCPUHaltHook", b"pmCPUHaltHook"),
                ("clearXsqdForSleep", b"clearXsqdForSleep"),
                ("dispPlaneSleep", b"dispPlaneSleep"),
                ("EC_SCI_filter", b"EC SCI filter"),
                ("XSQD", b"XSQD"),
                ("Display_plane_DMA_gate", b"Display plane DMA gate"),
                ("USB_wake_block", b"USB wake block"),
            ],
        },
        {
            "name": "libxedrv.dylib",
            "path": bundle_dir / "stage2-gpu/Library-GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib",
            "expected_sha256": "312ecf603a27526df87417980fd64fddd2d51e16754aa5deff8a1deeb76226b2",
            "expected_size_bytes": None,
            "markers": [
                ("xe_tex_ios_desalinhada", b"xe_tex_ios_desalinhada"),
                ("IOS_UNALIGN", b"IOS_UNALIGN"),
                ("XE_IOS_COPY", b"XE_IOS_COPY"),
            ],
        },
        {
            "name": "SSDT-DEEPIDLE.aml",
            "path": bundle_dir / "EFI-OC/OC/ACPI/SSDT-DEEPIDLE.aml",
            "expected_sha256": "280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1",
            "expected_size_bytes": 371,
            "markers": [
                ("LID_", b"LID_"),
                ("SLPB", b"SLPB"),
                ("_PRW", b"_PRW"),
                ("PRW0", b"PRW0"),
                ("_S0W", b"_S0W"),
                ("GPE_0x6E", aml_prw_gpe6e_pkg),
                ("USWE", b"USWE"),
            ],
        },
        {
            "name": "SSDT-EC0-ITLB.aml",
            "path": bundle_dir / "EFI-OC/OC/ACPI/SSDT-EC0-ITLB.aml",
            "expected_sha256": "122a5b9d778c6429d32f73f1da7e695ba7498e6714e172f708b22894bd8ddaf8",
            "expected_size_bytes": 1572,
            "markers": [
                ("ITLB", b"ITLB"),
                ("XTLB", b"XTLB"),
                ("EC12", b"EC12"),
                ("XC12", b"XC12"),
                ("EC13", b"EC13"),
                ("XC13", b"XC13"),
                ("ODVP", b"ODVP"),
                ("XDVP", b"XDVP"),
            ],
        },
        {
            "name": "xe-h264sw-fixd",
            "path": bundle_dir / "stage2-gpu/usr-local-libexec/xe-h264sw-fixd",
            "expected_sha256": "4e388dfd1720d25e73d5701b4be0919cac190cca38ee03fc7ee9a7532048d5af",
            "expected_size_bytes": 24496,
            "markers": [
                ("VTDecoderXPCService", b"VTDecoderXPCService"),
                ("AppleH264SW", b"AppleH264SW"),
            ],
        },
        {
            "name": "hp-wake-helper",
            "path": bundle_dir / "stage3-audio/usr-local-bin/hp-wake-helper",
            "expected_sha256": "b592620b3ef2f816b006d0fa6414e206b142da5779ece3b82604b6bf12f7b491",
            "expected_size_bytes": 50112,
            "markers": [
                ("AppleBacklightDisplay", b"AppleBacklightDisplay"),
                ("ngreen-wake-plane-rgb-fix", b"ngreen-wake-plane-rgb-fix"),
                ("wake-hold-release+0.83s", b"wake-hold-release+0.83s"),
            ],
        },
        {
            "name": "hp-bridge",
            "path": bundle_dir / "stage3-brightness-hotkeys/usr-local-bin/hp-bridge",
            "expected_sha256": "3854aabe44e6fd859111b859e6b9a66f3a82867b086389aa03b6263a0c27cfb7",
            "expected_size_bytes": 70192,
            "markers": [
                ("DisplayServicesCanChangeBrightness", b"DisplayServicesCanChangeBrightness"),
            ],
        },
        {
            "name": "hp-syslogger.py",
            "path": bundle_dir / "stage3-logging/usr-local-bin/hp-syslogger.py",
            "expected_sha256": "9f22348437736568d9ca6906b2934e5358432200615fe4503729b851e2f89f59",
            "expected_size_bytes": 13043,
            "markers": [
                ("STOP_EVENT", b"STOP_EVENT"),
                ("Out_of_range_RSSI", b"Out of range RSSI value"),
                ("unified_errors_rotate", b"unified-errors.log.1"),
                ("mlock", b"mlock"),
            ],
        },
    ]

    results: dict[str, dict] = {}
    all_passed = True

    for item in targets:
        fpath: Path = item["path"]
        if not fpath.is_file():
            errors.append(f"Missing binary for marker check: {fpath}")
            all_passed = False
            continue
        payload = fpath.read_bytes()
        actual_sha = hashlib.sha256(payload).hexdigest()
        actual_size = len(payload)
        sha_ok = actual_sha == item["expected_sha256"]
        size_ok = item["expected_size_bytes"] is None or actual_size == item["expected_size_bytes"]
        if not sha_ok:
            errors.append(f"[{item['name']}] SHA256 mismatch: expected {item['expected_sha256']}, got {actual_sha}")
            all_passed = False
        if not size_ok:
            errors.append(f"[{item['name']}] Size mismatch: expected {item['expected_size_bytes']}, got {actual_size}")
            all_passed = False

        marker_status: dict[str, bool] = {}
        for label, needle in item["markers"]:
            if item["name"] == "SSDT-DEEPIDLE.aml" and label == "GPE_0x6E":
                present = payload.count(needle) == 4
            else:
                present = needle in payload
            marker_status[label] = present
            if not present:
                errors.append(f"[{item['name']}] Missing required binary marker {label!r}")
                all_passed = False

        results[item["name"]] = {
            "path": fpath.relative_to(root).as_posix(),
            "sha256": actual_sha,
            "size_bytes": actual_size,
            "sha256_matched": sha_ok,
            "size_matched": size_ok,
            "markers": marker_status,
            "passed": sha_ok and size_ok and all(marker_status.values()),
        }

    # Also verify that patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch contains the PCFIX37 WakeRGB + BlitAlign hunks
    if patch_path.is_file():
        patch_bytes = patch_path.read_bytes()
        patch_sha = hashlib.sha256(patch_bytes).hexdigest()
        patch_markers = {
            "HP-BLITALIGN": b"HP-BLITALIGN" in patch_bytes,
            "HP-BLITFIX": b"HP-BLITFIX" in patch_bytes,
            "HP-BLIT16": b"HP-BLIT16" in patch_bytes,
            "ngreen-wake-plane-rgb-fix": b"ngreen-wake-plane-rgb-fix" in patch_bytes,
            "pcfix37_filename": "pcfix37" in patch_path.name,
        }
        patch_ok = patch_sha == "d7b02ea9405468109fa755e4b4321768ef0c0ce722c183306529cc4d2ae1d4ea" and all(patch_markers.values())
        if not patch_ok:
            errors.append("NootedGreen PCFIX37 patch file hash or marker check failed")
            all_passed = False
        results["nootedgreen_pcfix37_patch"] = {
            "path": patch_path.relative_to(root).as_posix(),
            "sha256": patch_sha,
            "size_bytes": len(patch_bytes),
            "markers": patch_markers,
            "passed": patch_ok,
        }
    else:
        errors.append(f"Missing patch file for marker check: {patch_path}")
        all_passed = False

    return {
        "passed": all_passed,
        "artifacts": results,
    }


def verify_section5_live_nixos(root: Path, host: str, errors: list[str]) -> dict:
    """5. Optional Live Target Read-Only Verification (--check-live-nixos <host>)."""
    bundle_efi = root / BUNDLE_DIR_REL / "EFI-OC"
    expected_key_hashes: dict[str, str] = {}
    for rel_oc in LIVE_NIXOS_KEY_OC_FILES:
        fpath = bundle_efi / "OC" / rel_oc
        if not fpath.is_file():
            errors.append(f"Missing local reference file for live NixOS check: {fpath}")
            return {"passed": False, "host": host, "error": f"Missing {fpath}"}
        expected_key_hashes[f"/boot/EFI/OC/{rel_oc}"], _ = sha256_file(fpath)

    expected_all_oc_hashes: dict[str, str] = {}
    for p in sorted((bundle_efi / "OC").rglob("*")):
        if p.is_file():
            rel_oc = p.relative_to(bundle_efi / "OC").as_posix()
            expected_all_oc_hashes[f"/boot/EFI/OC/{rel_oc}"], _ = sha256_file(p)

    remote_paths = " ".join(expected_key_hashes.keys())
    remote_cmd = (
        "uname -s && "
        "cat /proc/sys/kernel/random/boot_id && "
        "if test -d /boot/EFI/OC 2>/dev/null; then "
        f"sha256sum {remote_paths} 2>/dev/null || true; "
        "echo '---ALL_OC---'; "
        "find /boot/EFI/OC -type f -exec sha256sum {} + 2>/dev/null || true; "
        "else "
        "sudo -n test -d /boot/EFI/OC && "
        f"(sudo -n sha256sum {remote_paths} 2>/dev/null || true) && "
        "echo '---ALL_OC---' && "
        "(sudo -n find /boot/EFI/OC -type f -exec sha256sum {} + 2>/dev/null || true); "
        "fi"
    )

    proc = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "ConnectTimeout=10",
            host,
            remote_cmd,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        err_msg = proc.stderr.strip() or proc.stdout.strip()
        errors.append(f"Live NixOS read-only SSH check failed on {host}: {err_msg}")
        return {"passed": False, "host": host, "error": err_msg}

    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        errors.append(f"Unexpected SSH output from {host}: {proc.stdout!r}")
        return {"passed": False, "host": host, "error": "Incomplete SSH output"}

    uname_s = lines[0]
    boot_id = lines[1]
    if uname_s != "Linux":
        errors.append(f"Target {host} is not running Linux (uname -s == {uname_s!r})")

    key_lines: list[str] = []
    all_oc_lines: list[str] = []
    in_all_oc = False
    for line in lines[2:]:
        if line == "---ALL_OC---":
            in_all_oc = True
            continue
        if in_all_oc:
            all_oc_lines.append(line)
        else:
            key_lines.append(line)

    parsed_key_hashes: dict[str, str] = {}
    for line in key_lines:
        parts = line.split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 64:
            parsed_key_hashes[parts[1].strip()] = parts[0].lower()

    key_verification: dict[str, dict] = {}
    for remote_path, expected_sha in expected_key_hashes.items():
        actual_sha = parsed_key_hashes.get(remote_path)
        matched = actual_sha == expected_sha
        if not matched:
            errors.append(
                f"Live target {host} SHA256 mismatch for {remote_path}: expected {expected_sha}, got {actual_sha}"
            )
        key_verification[remote_path] = {
            "expected_sha256": expected_sha,
            "actual_sha256": actual_sha,
            "matched": matched,
        }

    parsed_all_oc: dict[str, str] = {}
    for line in all_oc_lines:
        parts = line.split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 64:
            rpath = parts[1].strip()
            if rpath.startswith("/boot/EFI/OC/opencore-") and rpath.endswith(".txt"):
                continue
            parsed_all_oc[rpath] = parts[0].lower()

    all_oc_mismatches = []
    matched_live_oc_count = 0
    for rpath, expected_sha in expected_all_oc_hashes.items():
        if parsed_all_oc.get(rpath) == expected_sha:
            matched_live_oc_count += 1
        else:
            all_oc_mismatches.append(rpath)
    extra_live_oc = sorted(set(parsed_all_oc) - set(expected_all_oc_hashes))
    if all_oc_mismatches:
        errors.append(f"Live target {host} has {len(all_oc_mismatches)} /boot/EFI/OC mismatches: {all_oc_mismatches[:5]}")
    if extra_live_oc:
        errors.append(f"Live target {host} has {len(extra_live_oc)} extra /boot/EFI/OC files: {extra_live_oc[:5]}")

    matched_key_files_count = sum(1 for v in key_verification.values() if v["matched"])
    passed = (
        uname_s == "Linux"
        and matched_key_files_count == len(expected_key_hashes)
        and not all_oc_mismatches
        and not extra_live_oc
    )
    return {
        "passed": passed,
        "host": host,
        "uname_s": uname_s,
        "boot_id": boot_id,
        "key_files": key_verification,
        "matched_key_files_count": matched_key_files_count,
        "total_live_oc_files_verified": matched_live_oc_count,
        "live_oc_mismatches": all_oc_mismatches,
        "extra_live_oc_files": extra_live_oc,
    }


def _resolve_build_env(root: Path, errors: list[str]) -> tuple[dict[str, str], dict[str, str]] | None:
    """Resolve toolchain binaries and environment variables (supporting direct nix develop or flake fallback)."""
    root = root.resolve()
    env = dict(os.environ)
    path_str = env.get("PATH", "")
    default_sdk = "/srv/tgl26-usb/GA45-AppleTGL-Native-Port/toolchain/MacOSX26.5.sdk"
    default_pr_lld = "/srv/tgl26-usb/GA46-TGL-Integration/toolchain/pr204805/build/bin/ld64.lld"

    def find_tools(cur_env: dict[str, str]) -> dict[str, str | None]:
        cur_path = cur_env.get("PATH", "")
        clang_env = cur_env.get("CLANG_APPLE")
        clang_bin = (
            (clang_env if clang_env and Path(clang_env).is_file() else None)
            or shutil.which("clang-21", path=cur_path)
            or shutil.which("clang", path=cur_path)
        )
        lld_env = cur_env.get("LD64_LLD")
        if lld_env and Path(lld_env).is_file():
            lld_bin: str | None = lld_env
        elif Path(default_pr_lld).is_file():
            lld_bin = default_pr_lld
        else:
            lld_bin = shutil.which("ld64.lld", path=cur_path)
        path_lld_bin = shutil.which("ld64.lld", path=cur_path)
        rc_env = cur_env.get("RCODESIGN")
        rcodesign_bin = (
            (rc_env if rc_env and Path(rc_env).is_file() else None)
            or shutil.which("rcodesign", path=cur_path)
        )
        iasl_bin = shutil.which("iasl", path=cur_path)
        patch_bin = shutil.which("patch", path=cur_path)
        sdk_env = cur_env.get("SDKROOT")
        if sdk_env and Path(sdk_env).is_dir():
            sdkroot: str | None = sdk_env
        elif Path(default_sdk).is_dir():
            sdkroot = default_sdk
        else:
            sdkroot = None
        return {
            "clang": clang_bin if clang_bin and Path(clang_bin).is_file() else None,
            "ld64_lld": lld_bin if lld_bin and Path(lld_bin).is_file() else None,
            "path_ld64_lld": path_lld_bin if path_lld_bin and Path(path_lld_bin).is_file() else None,
            "rcodesign": rcodesign_bin if rcodesign_bin and Path(rcodesign_bin).is_file() else None,
            "iasl": iasl_bin if iasl_bin and Path(iasl_bin).is_file() else None,
            "patch": patch_bin if patch_bin and Path(patch_bin).is_file() else None,
            "sdkroot": sdkroot,
        }

    tools = find_tools(env)
    if not all(tools.values()):
        nix_bin = shutil.which("nix", path=path_str)
        flake_dir = root if (root / "flake.nix").is_file() else (ROOT if (ROOT / "flake.nix").is_file() else None)
        if nix_bin and flake_dir is not None:
            nix_in_env = dict(env)
            for k_file in ("CLANG_APPLE", "LD64_LLD", "RCODESIGN"):
                v_file = nix_in_env.get(k_file)
                if v_file is not None and (not v_file or not Path(v_file).is_file()):
                    nix_in_env.pop(k_file, None)
            v_sdk = nix_in_env.get("SDKROOT")
            if v_sdk is not None and (not v_sdk or not Path(v_sdk).is_dir()):
                nix_in_env.pop("SDKROOT", None)
            proc = subprocess.run(
                [
                    nix_bin,
                    "develop",
                    str(flake_dir),
                    "-c",
                    "python3",
                    "-c",
                    "import json, os; print(json.dumps(dict(os.environ)))",
                ],
                capture_output=True,
                text=True,
                env=nix_in_env,
                check=False,
            )
            if proc.returncode == 0:
                try:
                    env = json.loads(proc.stdout.strip().splitlines()[-1])
                    tools = find_tools(env)
                except (IndexError, json.JSONDecodeError):
                    pass

    missing = [name for name, val in tools.items() if not val]
    if missing:
        errors.append(
            f"Missing required clean-room build tools/SDK for --check-source-rebuilds: {', '.join(missing)}"
        )
        return None
    return env, {k: str(v) for k, v in tools.items() if v is not None}


def verify_section6_source_rebuilds(root: Path, errors: list[str]) -> dict:
    """6. Clean-Room Source-to-Binary Rebuild Verification (--check-source-rebuilds)."""
    root = root.resolve()
    resolved = _resolve_build_env(root, errors)
    if resolved is None:
        return {
            "passed": False,
            "verified_target_count": 0,
            "expected_target_count": 9,
            "temp_dir_cleaned_up": True,
            "remaining_temp_bytes": 0,
            "total_duration_ms": 0.0,
            "targets": {},
            "error": "Toolchain resolution failed",
        }
    env, tools = resolved

    bundle_dir = root / BUNDLE_DIR_REL
    t_start = time.monotonic()
    rebuilds: dict[str, dict] = {}
    all_passed = True

    with tempfile.TemporaryDirectory(prefix="hp-tahoe-cleanroom-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        # 6.1 ACPI SSDT Clean-Room Compilation (iasl -ve)
        acpi_targets = [
            {
                "name": "SSDT-DEEPIDLE.aml",
                "prefix": "SSDT-DEEPIDLE",
                "dsl_rel": ".local/driver-repair-20261103/s0ix-standby-prep-20261107/SSDT-DEEPIDLE.dsl",
                "expected_dsl_sha256": "1f569b6bbb0d4305a27fcadeedf69a463c18f47b581d5140fb8acb2ecccfb1b9",
                "expected_dsl_size": 2793,
                "ref_aml_rel": f"{BUNDLE_DIR_REL}/EFI-OC/OC/ACPI/SSDT-DEEPIDLE.aml",
                "expected_aml_sha256": "280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1",
                "expected_aml_size": 371,
            },
            {
                "name": "SSDT-EC0-ITLB.aml",
                "prefix": "SSDT-EC0-ITLB",
                "dsl_rel": (
                    ".local/driver-repair-20261103/s0ix-standby-prep-20261107/"
                    "subsystem-audit-3b5cd162/live-acpi/SSDT-EC0-ITLB.dsl"
                ),
                "expected_dsl_sha256": "30dd9d79d501cb83cab902fe9acc3f46553ef6efafc5878641fe1174387186ed",
                "expected_dsl_size": 7231,
                "ref_aml_rel": f"{BUNDLE_DIR_REL}/EFI-OC/OC/ACPI/SSDT-EC0-ITLB.aml",
                "expected_aml_sha256": "122a5b9d778c6429d32f73f1da7e695ba7498e6714e172f708b22894bd8ddaf8",
                "expected_aml_size": 1572,
            },
        ]

        for spec in acpi_targets:
            step_t0 = time.monotonic()
            dsl_path = root / spec["dsl_rel"]
            ref_aml_path = root / spec["ref_aml_rel"]
            if not dsl_path.is_file() or not ref_aml_path.is_file():
                errors.append(f"[{spec['name']}] Missing DSL or reference AML: {dsl_path} / {ref_aml_path}")
                rebuilds[spec["name"]] = {"passed": False, "error": "Missing source DSL or reference AML"}
                all_passed = False
                continue

            dsl_sha, dsl_size = sha256_file(dsl_path)
            out_prefix = tmp_dir / spec["prefix"]
            out_aml = tmp_dir / spec["name"]
            proc = subprocess.run(
                [tools["iasl"], "-ve", "-p", str(out_prefix), str(dsl_path)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            step_ms = round((time.monotonic() - step_t0) * 1000.0, 2)
            m_summary = re.search(
                r"Compilation successful\.\s+(\d+)\s+Errors,\s+(\d+)\s+Warnings,\s+(\d+)\s+Remarks",
                proc.stdout,
            )
            iasl_errors = int(m_summary.group(1)) if m_summary else -1
            iasl_warnings = int(m_summary.group(2)) if m_summary else -1
            iasl_remarks = int(m_summary.group(3)) if m_summary else -1

            if proc.returncode != 0 or not out_aml.is_file():
                errors.append(
                    f"[{spec['name']}] iasl -ve failed (rc={proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
                )
                rebuilds[spec["name"]] = {
                    "passed": False,
                    "exit_code": proc.returncode,
                    "duration_ms": step_ms,
                }
                all_passed = False
                continue

            rebuilt_bytes = out_aml.read_bytes()
            ref_bytes = ref_aml_path.read_bytes()
            rebuilt_sha = hashlib.sha256(rebuilt_bytes).hexdigest()
            rebuilt_size = len(rebuilt_bytes)
            exact_match = rebuilt_bytes == ref_bytes and rebuilt_sha == spec["expected_aml_sha256"]
            # Also check AML payload ignoring the 4-byte Creator Revision at header offset 32..36
            payload_ignoring_creator_rev_match = (
                len(rebuilt_bytes) == len(ref_bytes)
                and rebuilt_bytes[:32] == ref_bytes[:32]
                and rebuilt_bytes[36:] == ref_bytes[36:]
            )
            step_ok = (
                proc.returncode == 0
                and iasl_errors == 0
                and iasl_warnings == 0
                and dsl_sha == spec["expected_dsl_sha256"]
                and dsl_size == spec["expected_dsl_size"]
                and rebuilt_size == spec["expected_aml_size"]
                and exact_match
            )
            if not step_ok:
                errors.append(
                    f"[{spec['name']}] Clean-room ACPI rebuild mismatch: rc={proc.returncode}, "
                    f"errors={iasl_errors}, warnings={iasl_warnings}, size={rebuilt_size} "
                    f"(expected {spec['expected_aml_size']}), sha256={rebuilt_sha} "
                    f"(expected {spec['expected_aml_sha256']})"
                )
                all_passed = False

            rebuilds[spec["name"]] = {
                "passed": step_ok,
                "source_dsl": spec["dsl_rel"],
                "source_dsl_size_bytes": dsl_size,
                "source_dsl_sha256": dsl_sha,
                "reference_aml": spec["ref_aml_rel"],
                "exit_code": proc.returncode,
                "iasl_errors": iasl_errors,
                "iasl_warnings": iasl_warnings,
                "iasl_remarks": iasl_remarks,
                "size_bytes": rebuilt_size,
                "expected_size_bytes": spec["expected_aml_size"],
                "sha256": rebuilt_sha,
                "expected_sha256": spec["expected_aml_sha256"],
                "byte_for_byte_matched": exact_match,
                "aml_body_matched": payload_ignoring_creator_rev_match,
                "duration_ms": step_ms,
            }

        # 6.2 S0ixStandby.kext (v0.4.4) Clean-Room Kext Compilation & Link
        step_t0 = time.monotonic()
        ksdk = root / ".local/build-readiness/isolated/WhateverGreen/MacKernelSDK"
        s0ix_src_dir = root / ".local/peripheral-prep-20261105/S0ixStandby-repo/S0ixStandby"
        s0ix_ref_bin = bundle_dir / "EFI-OC/OC/Kexts/S0ixStandby.kext/Contents/MacOS/S0ixStandby"
        s0ix_out_bin = tmp_dir / "S0ixStandby"

        s0ix_sources = [
            s0ix_src_dir / "S0ixStandby.cpp",
            s0ix_src_dir / "S0ixGPU.cpp",
            s0ix_src_dir / "S0ixStandby.hpp",
            s0ix_src_dir / "kmod_info.c",
        ]
        ksdk_libs = [
            ksdk / "Library/x86_64/libkmod.a",
            ksdk / "Library/universal/libkmodc++.a",
        ]
        if (
            not (ksdk / "Headers").is_dir()
            or not all(p.is_file() for p in ksdk_libs)
            or not all(p.is_file() for p in s0ix_sources)
            or not s0ix_ref_bin.is_file()
        ):
            errors.append("[S0ixStandby] Missing MacKernelSDK headers/libs, S0ixStandby sources, or reference binary")
            rebuilds["S0ixStandby"] = {"passed": False, "error": "Missing S0ixStandby inputs"}
            all_passed = False
        else:
            common_flags = [
                "-target", "x86_64-apple-macos10.13",
                "-mkernel", "-nostdinc",
                "-fno-builtin", "-fno-common", "-fno-stack-protector",
                "-mmmx", "-msse", "-msse2",
                "-DKERNEL", "-DKERNEL_PRIVATE", "-DDRIVER_PRIVATE", "-DAPPLE", "-DNeXT",
                f"-I{ksdk}/Headers",
                "-Wall", "-Wextra", "-Wno-unused-parameter", "-Os",
                "-fno-use-cxa-atexit", "-fno-register-global-dtors-with-atexit",
                "-mllvm", "-disable-atexit-based-global-dtor-lowering",
                "-fno-asynchronous-unwind-tables",
            ]
            cxx_flags = [*common_flags, "-std=gnu++17", "-fapple-kext", "-fno-rtti", "-fno-exceptions"]
            c_flags = [
                *common_flags,
                "-std=gnu11",
                "-DKEXT_BUNDLE_ID=com.labrouss.S0ixStandby",
                '-DKEXT_VERSION="0.4.4"',
            ]
            cmds = [
                [
                    tools["clang"], *cxx_flags,
                    "-c", str(s0ix_src_dir / "S0ixStandby.cpp"),
                    "-o", str(tmp_dir / "S0ixStandby.o"),
                ],
                [
                    tools["clang"], *cxx_flags,
                    "-c", str(s0ix_src_dir / "S0ixGPU.cpp"),
                    "-o", str(tmp_dir / "S0ixGPU.o"),
                ],
                [
                    tools["clang"], *c_flags,
                    "-c", str(s0ix_src_dir / "kmod_info.c"),
                    "-o", str(tmp_dir / "kmod_info.o"),
                ],
                [
                    tools["ld64_lld"],
                    "-kext", "-arch", "x86_64",
                    "-platform_version", "macos", "10.13", "26.5",
                    "-export_dynamic",
                    str(tmp_dir / "S0ixStandby.o"),
                    str(tmp_dir / "S0ixGPU.o"),
                    str(tmp_dir / "kmod_info.o"),
                    str(ksdk / "Library/x86_64/libkmod.a"),
                    str(ksdk / "Library/universal/libkmodc++.a"),
                    "-o", str(s0ix_out_bin),
                ],
            ]
            s0ix_rc = 0
            s0ix_err_detail = ""
            for cmd in cmds:
                proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
                if proc.returncode != 0:
                    s0ix_rc = proc.returncode
                    s0ix_err_detail = proc.stderr.strip() or proc.stdout.strip()
                    break
            step_ms = round((time.monotonic() - step_t0) * 1000.0, 2)

            if s0ix_rc != 0 or not s0ix_out_bin.is_file():
                errors.append(f"[S0ixStandby] Clean-room compilation failed (rc={s0ix_rc}): {s0ix_err_detail}")
                rebuilds["S0ixStandby"] = {
                    "passed": False,
                    "exit_code": s0ix_rc,
                    "duration_ms": step_ms,
                }
                all_passed = False
            else:
                rebuilt_bytes = s0ix_out_bin.read_bytes()
                ref_bytes = s0ix_ref_bin.read_bytes()
                rebuilt_sha = hashlib.sha256(rebuilt_bytes).hexdigest()
                rebuilt_size = len(rebuilt_bytes)
                expected_sha = "be55592c42c5003cd86ac99695c56dbd92b368954301a78d3eecdd3095411184"
                expected_size = 74584
                exact_match = rebuilt_bytes == ref_bytes and rebuilt_sha == expected_sha and rebuilt_size == expected_size
                if not exact_match:
                    errors.append(
                        f"[S0ixStandby] Clean-room rebuild mismatch: size={rebuilt_size} (expected {expected_size}), "
                        f"sha256={rebuilt_sha} (expected {expected_sha})"
                    )
                    all_passed = False
                rebuilds["S0ixStandby"] = {
                    "passed": exact_match,
                    "source_dir": ".local/peripheral-prep-20261105/S0ixStandby-repo/S0ixStandby",
                    "reference_binary": s0ix_ref_bin.relative_to(root).as_posix(),
                    "exit_code": 0,
                    "size_bytes": rebuilt_size,
                    "expected_size_bytes": expected_size,
                    "sha256": rebuilt_sha,
                    "expected_sha256": expected_sha,
                    "byte_for_byte_matched": exact_match,
                    "duration_ms": step_ms,
                }

        # 6.3 NootedGreen Patch Application Clean-Room Verification
        step_t0 = time.monotonic()
        ng_baseline_dir = root / ".local/driver-repair-20261103/repair32-preemption-investigation/source"
        ng_patched_ref = root / ".local/driver-repair-20261103/repair32-readback/source/src/NootedGreen/kern_gen11.cpp"
        ng_patch_file = root / "patches/nootedgreen-r32-pcfix37-wakergb-20261111.patch"
        ng_tmp_dir = tmp_dir / "ng-src"

        if (
            not (ng_baseline_dir / "src/NootedGreen/kern_gen11.cpp").is_file()
            or not ng_patched_ref.is_file()
            or not ng_patch_file.is_file()
        ):
            errors.append("[NootedGreen_patch] Missing baseline NootedGreen source tree, patch file, or reference kern_gen11.cpp")
            rebuilds["NootedGreen_patch"] = {"passed": False, "error": "Missing NootedGreen patch inputs"}
            all_passed = False
        else:
            shutil.copytree(ng_baseline_dir, ng_tmp_dir)
            baseline_kg_path = ng_tmp_dir / "src/NootedGreen/kern_gen11.cpp"
            baseline_kg_sha, baseline_kg_size = sha256_file(baseline_kg_path)
            proc = subprocess.run(
                [tools["patch"], "-p1", "--batch", "--forward", "-i", str(ng_patch_file)],
                cwd=ng_tmp_dir,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            step_ms = round((time.monotonic() - step_t0) * 1000.0, 2)
            patched_bytes = baseline_kg_path.read_bytes()
            ref_bytes = ng_patched_ref.read_bytes()
            patched_sha = hashlib.sha256(patched_bytes).hexdigest()
            patched_size = len(patched_bytes)
            expected_sha = "6c42d019445988feb826ac6581f2c0c90a34f0e1266436ef81eed35f03f2d240"
            expected_size = 707888
            exact_match = (
                proc.returncode == 0
                and patched_bytes == ref_bytes
                and patched_sha == expected_sha
                and patched_size == expected_size
            )
            if not exact_match:
                errors.append(
                    f"[NootedGreen_patch] Clean-room patch verification failed: rc={proc.returncode}, "
                    f"size={patched_size} (expected {expected_size}), sha256={patched_sha} (expected {expected_sha})"
                )
                all_passed = False
            rebuilds["NootedGreen_patch"] = {
                "passed": exact_match,
                "baseline_source_dir": ng_baseline_dir.relative_to(root).as_posix(),
                "baseline_kern_gen11_size_bytes": baseline_kg_size,
                "baseline_kern_gen11_sha256": baseline_kg_sha,
                "patch_file": ng_patch_file.relative_to(root).as_posix(),
                "reference_kern_gen11": ng_patched_ref.relative_to(root).as_posix(),
                "exit_code": proc.returncode,
                "size_bytes": patched_size,
                "expected_size_bytes": expected_size,
                "sha256": patched_sha,
                "expected_sha256": expected_sha,
                "byte_for_byte_matched": exact_match,
                "duration_ms": step_ms,
            }

        # 6.4a Userspace libxedrv.dylib Clean-Room Compilation + Signing
        step_t0 = time.monotonic()
        libxedrv_src = root / ".local/driver-repair-20261103/vt-audio-fix-20261106/libxedrv.m"
        libxedrv_ref = (
            bundle_dir
            / "stage2-gpu/Library-GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib"
        )
        libxedrv_obj = tmp_dir / "libxedrv.o"
        libxedrv_out = tmp_dir / "libxedrv.dylib"

        if not libxedrv_src.is_file() or not libxedrv_ref.is_file():
            errors.append("[libxedrv.dylib] Missing libxedrv.m or reference libxedrv.dylib")
            rebuilds["libxedrv.dylib"] = {"passed": False, "error": "Missing libxedrv.m or reference"}
            all_passed = False
        else:
            xedrv_cmds = [
                [
                    tools["clang"],
                    "-target", "x86_64-apple-macos15.0",
                    "-isysroot", tools["sdkroot"],
                    "-O2", "-fPIC", "-fno-objc-arc",
                    "-c", str(libxedrv_src),
                    "-o", str(libxedrv_obj),
                ],
                [
                    tools["ld64_lld"],
                    "-dylib", "-arch", "x86_64",
                    "-platform_version", "macos", "15.0", "26.5",
                    "-syslibroot", tools["sdkroot"],
                    "-install_name",
                    "/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib",
                    str(libxedrv_obj),
                    "-lSystem",
                    "-framework", "Foundation",
                    "-framework", "CoreFoundation",
                    "-lobjc",
                    "-framework", "Metal",
                    "-framework", "IOSurface",
                    "-o", str(libxedrv_out),
                ],
                [
                    tools["rcodesign"],
                    "sign",
                    str(libxedrv_out),
                ],
            ]
            xedrv_rc = 0
            xedrv_err = ""
            for cmd in xedrv_cmds:
                proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
                if proc.returncode != 0:
                    xedrv_rc = proc.returncode
                    xedrv_err = proc.stderr.strip() or proc.stdout.strip()
                    break
            step_ms = round((time.monotonic() - step_t0) * 1000.0, 2)
            if xedrv_rc != 0 or not libxedrv_out.is_file():
                errors.append(f"[libxedrv.dylib] Clean-room compilation failed (rc={xedrv_rc}): {xedrv_err}")
                rebuilds["libxedrv.dylib"] = {
                    "passed": False,
                    "exit_code": xedrv_rc,
                    "duration_ms": step_ms,
                }
                all_passed = False
            else:
                rebuilt_bytes = libxedrv_out.read_bytes()
                ref_bytes = libxedrv_ref.read_bytes()
                rebuilt_sha = hashlib.sha256(rebuilt_bytes).hexdigest()
                rebuilt_size = len(rebuilt_bytes)
                expected_sha = "312ecf603a27526df87417980fd64fddd2d51e16754aa5deff8a1deeb76226b2"
                expected_size = 65280
                markers = {
                    "xe_tex_ios_desalinhada": b"xe_tex_ios_desalinhada" in rebuilt_bytes,
                    "IOS_UNALIGN": b"IOS_UNALIGN" in rebuilt_bytes,
                    "XE_IOS_COPY": b"XE_IOS_COPY" in rebuilt_bytes,
                }
                exact_match = (
                    rebuilt_bytes == ref_bytes
                    and rebuilt_sha == expected_sha
                    and rebuilt_size == expected_size
                    and all(markers.values())
                )
                if not exact_match:
                    errors.append(
                        f"[libxedrv.dylib] Clean-room rebuild mismatch: size={rebuilt_size} (expected {expected_size}), "
                        f"sha256={rebuilt_sha} (expected {expected_sha}), markers={markers}"
                    )
                    all_passed = False
                rebuilds["libxedrv.dylib"] = {
                    "passed": exact_match,
                    "source_file": libxedrv_src.relative_to(root).as_posix(),
                    "reference_binary": libxedrv_ref.relative_to(root).as_posix(),
                    "exit_code": 0,
                    "size_bytes": rebuilt_size,
                    "expected_size_bytes": expected_size,
                    "sha256": rebuilt_sha,
                    "expected_sha256": expected_sha,
                    "byte_for_byte_matched": rebuilt_bytes == ref_bytes,
                    "markers": markers,
                    "duration_ms": step_ms,
                }

        # 6.4b Userspace test_420v_blitalign Clean-Room Compilation + Signing
        step_t0 = time.monotonic()
        test420_src = (
            root
            / ".local/driver-repair-20261103/s0ix-standby-prep-20261107/"
            "post-wake-ebaba2ee/test_420v_blitalign.m"
        )
        test420_ref = bundle_dir / "test_420v_blitalign"
        test420_out = tmp_dir / "test_420v_blitalign"

        if not test420_src.is_file() or not test420_ref.is_file():
            errors.append("[test_420v_blitalign] Missing test_420v_blitalign.m or reference binary")
            rebuilds["test_420v_blitalign"] = {"passed": False, "error": "Missing test_420v_blitalign inputs"}
            all_passed = False
        else:
            test420_cmds = [
                [
                    tools["clang"],
                    "-target", "x86_64-apple-macos15.0",
                    "-isysroot", tools["sdkroot"],
                    "-fuse-ld=lld",
                    f"--ld-path={tools['path_ld64_lld']}",
                    "-O2", "-fobjc-arc",
                    "-framework", "Foundation",
                    "-framework", "Metal",
                    "-framework", "CoreVideo",
                    "-framework", "IOSurface",
                    "-framework", "VideoToolbox",
                    "-framework", "IOKit",
                    str(test420_src),
                    "-o", str(test420_out),
                ],
                [
                    tools["rcodesign"],
                    "sign",
                    str(test420_out),
                ],
            ]
            t420_rc = 0
            t420_err = ""
            for cmd in test420_cmds:
                proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
                if proc.returncode != 0:
                    t420_rc = proc.returncode
                    t420_err = proc.stderr.strip() or proc.stdout.strip()
                    break
            step_ms = round((time.monotonic() - step_t0) * 1000.0, 2)
            if t420_rc != 0 or not test420_out.is_file():
                errors.append(f"[test_420v_blitalign] Clean-room compilation failed (rc={t420_rc}): {t420_err}")
                rebuilds["test_420v_blitalign"] = {
                    "passed": False,
                    "exit_code": t420_rc,
                    "duration_ms": step_ms,
                }
                all_passed = False
            else:
                rebuilt_bytes = test420_out.read_bytes()
                ref_bytes = test420_ref.read_bytes()
                rebuilt_sha = hashlib.sha256(rebuilt_bytes).hexdigest()
                rebuilt_size = len(rebuilt_bytes)
                expected_sha = "887743ebd0b11797fa46553fa2420df21adf266c76ce6d0d540ac51e415e75bf"
                expected_size = 51680
                exact_match = (
                    rebuilt_bytes == ref_bytes
                    and rebuilt_sha == expected_sha
                    and rebuilt_size == expected_size
                )
                if not exact_match:
                    errors.append(
                        f"[test_420v_blitalign] Clean-room rebuild mismatch: size={rebuilt_size} "
                        f"(expected {expected_size}), sha256={rebuilt_sha} (expected {expected_sha})"
                    )
                    all_passed = False
                rebuilds["test_420v_blitalign"] = {
                    "passed": exact_match,
                    "source_file": test420_src.relative_to(root).as_posix(),
                    "reference_binary": test420_ref.relative_to(root).as_posix(),
                    "exit_code": 0,
                    "size_bytes": rebuilt_size,
                    "expected_size_bytes": expected_size,
                    "sha256": rebuilt_sha,
                    "expected_sha256": expected_sha,
                    "byte_for_byte_matched": exact_match,
                    "duration_ms": step_ms,
                }

        # 6.4c Userspace xe-h264sw-fixd Clean-Room Compilation + Mach-O Parity
        step_t0 = time.monotonic()
        h264_src = (
            root
            / ".local/driver-repair-20261103/s0ix-standby-prep-20261107/"
            "live-846ba6e6/xe-h264sw-fixd.c"
        )
        h264_ref = bundle_dir / "stage2-gpu/usr-local-libexec/xe-h264sw-fixd"
        h264_out = tmp_dir / "xe-h264sw-fixd"
        if not h264_src.is_file() or not h264_ref.is_file():
            errors.append("[xe-h264sw-fixd] Missing xe-h264sw-fixd.c or reference binary")
            rebuilds["xe-h264sw-fixd"] = {"passed": False, "error": "Missing xe-h264sw-fixd inputs"}
            all_passed = False
        else:
            h264_cmds = [
                [
                    tools["clang"],
                    "-target", "x86_64-apple-macos15.0",
                    "-isysroot", tools["sdkroot"],
                    "-fuse-ld=lld",
                    f"--ld-path={tools['ld64_lld']}",
                    "-O2",
                    str(h264_src),
                    "-o", str(h264_out),
                ],
                [
                    tools["rcodesign"],
                    "sign",
                    str(h264_out),
                ],
            ]
            h264_rc = 0
            h264_err = ""
            for cmd in h264_cmds:
                proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
                if proc.returncode != 0:
                    h264_rc = proc.returncode
                    h264_err = proc.stderr.strip() or proc.stdout.strip()
                    break
            step_ms = round((time.monotonic() - step_t0) * 1000.0, 2)
            if h264_rc != 0 or not h264_out.is_file():
                errors.append(f"[xe-h264sw-fixd] Clean-room compilation failed (rc={h264_rc}): {h264_err}")
                rebuilds["xe-h264sw-fixd"] = {"passed": False, "exit_code": h264_rc, "duration_ms": step_ms}
                all_passed = False
            else:
                rebuilt_bytes = h264_out.read_bytes()
                ref_bytes = h264_ref.read_bytes()
                rebuilt_size = len(rebuilt_bytes)
                expected_size = 24496
                expected_uuid = b"\x4c\x4c\x44\xb3\x55\x55\x31\x44\xa1\xe7\xa9\x19\xcc\x28\x6f\x49"
                # Reference binary was ad-hoc re-signed on macOS with Apple codesign (adding empty 0xfade0c01
                # requirements blob inside CS_SuperBlob at >= 0x47b6); Mach-O segments/symbols [0..0x47b0)
                # and LC_UUID match byte-for-byte.
                macho_body_match = (
                    rebuilt_size == expected_size
                    and len(ref_bytes) == expected_size
                    and rebuilt_bytes[:0x47B0] == ref_bytes[:0x47B0]
                    and expected_uuid in rebuilt_bytes
                )
                if not macho_body_match:
                    errors.append(
                        f"[xe-h264sw-fixd] Mach-O body or UUID mismatch: size={rebuilt_size} (expected {expected_size})"
                    )
                    all_passed = False
                rebuilds["xe-h264sw-fixd"] = {
                    "passed": macho_body_match,
                    "source_file": h264_src.relative_to(root).as_posix(),
                    "reference_binary": h264_ref.relative_to(root).as_posix(),
                    "exit_code": 0,
                    "size_bytes": rebuilt_size,
                    "expected_size_bytes": expected_size,
                    "sha256": hashlib.sha256(rebuilt_bytes).hexdigest(),
                    "reference_sha256": hashlib.sha256(ref_bytes).hexdigest(),
                    "macho_body_0x47b0_matched": macho_body_match,
                    "lc_uuid": "4C4C44B3-5555-3144-A1E7-A919CC286F49",
                    "duration_ms": step_ms,
                }

        # 6.4d Userspace hp-wake-helper Cross-Compilation Verification
        step_t0 = time.monotonic()
        wake_src = (
            root
            / ".local/driver-repair-20261103/s0ix-standby-prep-20261107/"
            "live-846ba6e6/hp-wake-helper.m"
        )
        wake_ref = bundle_dir / "stage3-audio/usr-local-bin/hp-wake-helper"
        wake_out = tmp_dir / "hp-wake-helper"
        if not wake_src.is_file() or not wake_ref.is_file():
            errors.append("[hp-wake-helper] Missing hp-wake-helper.m or reference binary")
            rebuilds["hp-wake-helper"] = {"passed": False, "error": "Missing hp-wake-helper inputs"}
            all_passed = False
        else:
            wake_cmds = [
                [
                    tools["clang"],
                    "-target", "x86_64-apple-macos15.0",
                    "-isysroot", tools["sdkroot"],
                    "-fuse-ld=lld",
                    f"--ld-path={tools['path_ld64_lld']}",
                    "-O2", "-fobjc-arc",
                    "-framework", "Foundation",
                    "-framework", "CoreWLAN",
                    "-framework", "CoreAudio",
                    "-framework", "CoreGraphics",
                    "-framework", "IOKit",
                    "-framework", "CoreFoundation",
                    str(wake_src),
                    "-o", str(wake_out),
                ],
                [
                    tools["rcodesign"],
                    "sign",
                    str(wake_out),
                ],
            ]
            wake_rc = 0
            wake_err = ""
            for cmd in wake_cmds:
                proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
                if proc.returncode != 0:
                    wake_rc = proc.returncode
                    wake_err = proc.stderr.strip() or proc.stdout.strip()
                    break
            step_ms = round((time.monotonic() - step_t0) * 1000.0, 2)
            if wake_rc != 0 or not wake_out.is_file():
                errors.append(f"[hp-wake-helper] Clean-room cross-compilation failed (rc={wake_rc}): {wake_err}")
                rebuilds["hp-wake-helper"] = {"passed": False, "exit_code": wake_rc, "duration_ms": step_ms}
                all_passed = False
            else:
                rebuilt_bytes = wake_out.read_bytes()
                ref_bytes = wake_ref.read_bytes()
                wake_ok = (
                    rebuilt_bytes[:4] == b"\xcf\xfa\xed\xfe"
                    and b"AppleBacklightDisplay" in rebuilt_bytes
                    and b"ngreen-wake-plane-rgb-fix" in rebuilt_bytes
                    and b"wake-hold-release+0.83s" in rebuilt_bytes
                    and hashlib.sha256(ref_bytes).hexdigest()
                    == "b592620b3ef2f816b006d0fa6414e206b142da5779ece3b82604b6bf12f7b491"
                )
                if not wake_ok:
                    errors.append("[hp-wake-helper] Cross-compiled Mach-O or reference SHA256 check failed")
                    all_passed = False
                rebuilds["hp-wake-helper"] = {
                    "passed": wake_ok,
                    "source_file": wake_src.relative_to(root).as_posix(),
                    "reference_binary": wake_ref.relative_to(root).as_posix(),
                    "exit_code": 0,
                    "cross_compiled_size_bytes": len(rebuilt_bytes),
                    "cross_compiled_sha256": hashlib.sha256(rebuilt_bytes).hexdigest(),
                    "reference_native_macos_sha256": hashlib.sha256(ref_bytes).hexdigest(),
                    "byte_for_byte_matched": False,
                    "note": "Reference binary built natively on macOS 26.6.2 (ld_prime minos 26.0); Linux cross-compile + markers verified",
                    "duration_ms": step_ms,
                }

        # 6.4e Userspace hp-bridge Cross-Compilation Verification
        step_t0 = time.monotonic()
        bridge_src = (
            root
            / ".local/driver-repair-20261103/s0ix-standby-prep-20261107/"
            "live-846ba6e6/hp-bridge.m"
        )
        bridge_ref = bundle_dir / "stage3-brightness-hotkeys/usr-local-bin/hp-bridge"
        bridge_out = tmp_dir / "hp-bridge"
        if not bridge_src.is_file() or not bridge_ref.is_file():
            errors.append("[hp-bridge] Missing hp-bridge.m or reference binary")
            rebuilds["hp-bridge"] = {"passed": False, "error": "Missing hp-bridge inputs"}
            all_passed = False
        else:
            bridge_cmds = [
                [
                    tools["clang"],
                    "-target", "x86_64-apple-macos15.0",
                    "-isysroot", tools["sdkroot"],
                    "-fuse-ld=lld",
                    f"--ld-path={tools['path_ld64_lld']}",
                    "-O2", "-fobjc-arc",
                    "-F", f"{tools['sdkroot']}/System/Library/PrivateFrameworks",
                    "-framework", "Cocoa",
                    "-framework", "Carbon",
                    "-framework", "CoreAudio",
                    "-framework", "CoreFoundation",
                    "-framework", "CoreGraphics",
                    "-framework", "IOKit",
                    "-framework", "DisplayServices",
                    "-framework", "CoreDisplay",
                    "-framework", "AppKit",
                    "-framework", "Foundation",
                    str(bridge_src),
                    "-o", str(bridge_out),
                ],
                [
                    tools["rcodesign"],
                    "sign",
                    str(bridge_out),
                ],
            ]
            bridge_rc = 0
            bridge_err = ""
            for cmd in bridge_cmds:
                proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
                if proc.returncode != 0:
                    bridge_rc = proc.returncode
                    bridge_err = proc.stderr.strip() or proc.stdout.strip()
                    break
            step_ms = round((time.monotonic() - step_t0) * 1000.0, 2)
            if bridge_rc != 0 or not bridge_out.is_file():
                errors.append(f"[hp-bridge] Clean-room cross-compilation failed (rc={bridge_rc}): {bridge_err}")
                rebuilds["hp-bridge"] = {"passed": False, "exit_code": bridge_rc, "duration_ms": step_ms}
                all_passed = False
            else:
                rebuilt_bytes = bridge_out.read_bytes()
                ref_bytes = bridge_ref.read_bytes()
                bridge_ok = (
                    rebuilt_bytes[:4] == b"\xcf\xfa\xed\xfe"
                    and b"DisplayServicesCanChangeBrightness" in rebuilt_bytes
                    and hashlib.sha256(ref_bytes).hexdigest()
                    == "3854aabe44e6fd859111b859e6b9a66f3a82867b086389aa03b6263a0c27cfb7"
                )
                if not bridge_ok:
                    errors.append("[hp-bridge] Cross-compiled Mach-O or reference SHA256 check failed")
                    all_passed = False
                rebuilds["hp-bridge"] = {
                    "passed": bridge_ok,
                    "source_file": bridge_src.relative_to(root).as_posix(),
                    "reference_binary": bridge_ref.relative_to(root).as_posix(),
                    "exit_code": 0,
                    "cross_compiled_size_bytes": len(rebuilt_bytes),
                    "cross_compiled_sha256": hashlib.sha256(rebuilt_bytes).hexdigest(),
                    "reference_native_macos_sha256": hashlib.sha256(ref_bytes).hexdigest(),
                    "byte_for_byte_matched": False,
                    "note": "Reference binary built natively on macOS 26.6.2 (ld_prime minos 26.0); Linux cross-compile + markers verified",
                    "duration_ms": step_ms,
                }

    temp_cleaned = not Path(tmp_dir_str).exists()
    remaining_bytes = (
        0
        if temp_cleaned
        else sum(p.stat().st_size for p in Path(tmp_dir_str).rglob("*") if p.is_file())
    )
    if not temp_cleaned:
        errors.append(f"Temporary clean-room build directory was not cleaned up: {tmp_dir_str}")
        all_passed = False

    total_ms = round((time.monotonic() - t_start) * 1000.0, 2)
    return {
        "passed": all_passed and len(rebuilds) == 9 and all(r.get("passed", False) for r in rebuilds.values()),
        "verified_target_count": sum(1 for r in rebuilds.values() if r.get("passed", False)),
        "expected_target_count": 9,
        "temp_dir_cleaned_up": temp_cleaned,
        "remaining_temp_bytes": remaining_bytes,
        "total_duration_ms": total_ms,
        "targets": rebuilds,
    }


def run_verification(
    root: Path,
    live_nixos_host: str | None = None,
    check_source_rebuilds: bool = False,
) -> tuple[dict, list[str]]:
    """Run all release verification checks and return (report_dict, errors_list)."""
    root = root.resolve()
    errors: list[str] = []
    sec1 = verify_section1_manifests(root, errors)

    if not sec1.get("local_present", False):
        sections: dict[str, dict] = {
            "1_core_config_and_receipt_parity": sec1,
        }
        if live_nixos_host:
            sections["5_live_nixos_readonly_esp_parity"] = verify_section5_live_nixos(
                root, live_nixos_host, errors
            )
        overall_passed = len(errors) == 0 and all(s.get("passed", False) for s in sections.values())
        report = {
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "target_os_release": "macOS Tahoe 26.6.2 (25G83)",
            "local_artifacts_present": False,
            "overall_passed": overall_passed,
            "error_count": len(errors),
            "errors": errors,
            "sections": sections,
        }
        return report, errors

    sec2 = verify_section2_postinstall_bundle(root, errors)
    sec3 = verify_section3_efi_parity(root, errors)
    sec4 = verify_section4_binary_markers(root, errors)
    sections = {
        "1_core_config_and_receipt_parity": sec1,
        "2_postinstall_bundle_431_integrity": sec2,
        "3_opencore_efi_112_parity": sec3,
        "4_binary_feature_and_aml_markers": sec4,
    }
    if live_nixos_host:
        sections["5_live_nixos_readonly_esp_parity"] = verify_section5_live_nixos(
            root, live_nixos_host, errors
        )
    if check_source_rebuilds:
        sections["6_clean_room_source_rebuilds"] = verify_section6_source_rebuilds(
            root, errors
        )

    overall_passed = len(errors) == 0 and all(s.get("passed", False) for s in sections.values())
    report = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_os_release": "macOS Tahoe 26.6.2 (25G83)",
        "local_artifacts_present": True,
        "overall_passed": overall_passed,
        "error_count": len(errors),
        "errors": errors,
        "sections": sections,
    }
    return report, errors


def print_summary(report: dict) -> None:
    """Print human-readable verification summary."""
    print("========================================================================")
    print("  HP EliteBook 840 G8 — macOS Tahoe 26.6.2 (25G83) Release Verification")
    print(f"  Timestamp (UTC): {report['timestamp_utc']}")
    print("========================================================================")
    sections = report["sections"]

    s1 = sections["1_core_config_and_receipt_parity"]
    if not report.get("local_artifacts_present", False):
        status = "PASS" if s1.get("passed") else "FAIL"
        print(
            f"[{status}] 1. Core Config & Repo Tracked Hashes: "
            f"{s1.get('verified_file_count', 0)} repo files verified (.local/ absent; skipping private bundle checks)"
        )
        if "5_live_nixos_readonly_esp_parity" in sections:
            s5 = sections["5_live_nixos_readonly_esp_parity"]
            matched_keys = s5.get(
                "matched_key_files_count",
                sum(1 for v in s5.get("key_files", {}).values() if v.get("matched")),
            )
            print(
                f"[{'PASS' if s5.get('passed') else 'FAIL'}] 5. Live NixOS Read-Only ESP Check ({s5.get('host')}): "
                f"uname={s5.get('uname_s')}, boot_id={s5.get('boot_id')}, "
                f"key_files={matched_keys}/5, "
                f"all_oc_files={s5.get('total_live_oc_files_verified', 0)}/111"
            )
        print("========================================================================")
        overall = "PASSED" if report["overall_passed"] else f"FAILED ({report['error_count']} errors)"
        print(f"  Overall Release Verification: {overall}")
        print("========================================================================")
        return

    print(
        f"[{'PASS' if s1.get('passed') else 'FAIL'}] 1. Core Configuration & Receipt Hash Parity: "
        f"{s1.get('verified_file_count', 0)} local file hashes + "
        f"{s1.get('cross_manifest_parity_count', 0)} cross-manifest keys verified"
    )

    s2 = sections["2_postinstall_bundle_431_integrity"]
    print(
        f"[{'PASS' if s2.get('passed') else 'FAIL'}] 2. Post-Install Bundle Integrity: "
        f"disk={s2.get('disk_verified_count', 0)}/{s2.get('manifest_entry_count', 0)} files, "
        f"tar.gz={s2.get('archive_verified_count', 0)}/{s2.get('manifest_entry_count', 0)} members "
        f"({s2.get('archive_size_bytes', 0):,} B, SHA256SUMS={s2.get('sha256sums_size_bytes', 0):,} B)"
    )

    s3 = sections["3_opencore_efi_112_parity"]
    mtools_tag = "FAT32+mtools" if s3.get("mtools_available") else "FAT32"
    rec_note = (
        f"recovery.img={s3.get('recovery_img_verified_efi_files', 0)}/{s3.get('bundle_efi_total_files', 0)} EFI files ({mtools_tag})"
    )
    print(
        f"[{'PASS' if s3.get('passed') else 'FAIL'}] 3. OpenCore 112-File EFI Parity: "
        f"bundle_efi={s3.get('bundle_efi_total_files', 0)} (1 BOOT + {s3.get('bundle_oc_files', 0)} OC), "
        f"readback_tar={s3.get('readback_tar_verified_oc_files', 0)}/{s3.get('bundle_oc_files', 0)} OC files, "
        f"{rec_note}"
    )

    s4 = sections["4_binary_feature_and_aml_markers"]
    marker_summary = ", ".join(
        f"{name}={'OK' if info['passed'] else 'FAIL'}"
        for name, info in s4.get("artifacts", {}).items()
    )
    print(f"[{'PASS' if s4.get('passed') else 'FAIL'}] 4. Binary & AML Fix Markers: {marker_summary}")

    if "5_live_nixos_readonly_esp_parity" in sections:
        s5 = sections["5_live_nixos_readonly_esp_parity"]
        matched_keys = s5.get(
            "matched_key_files_count",
            sum(1 for v in s5.get("key_files", {}).values() if v.get("matched")),
        )
        print(
            f"[{'PASS' if s5.get('passed') else 'FAIL'}] 5. Live NixOS Read-Only ESP Check ({s5.get('host')}): "
            f"uname={s5.get('uname_s')}, boot_id={s5.get('boot_id')}, "
            f"key_files={matched_keys}/5, "
            f"all_oc_files={s5.get('total_live_oc_files_verified', 0)}/111"
        )

    if "6_clean_room_source_rebuilds" in sections:
        s6 = sections["6_clean_room_source_rebuilds"]
        target_summary = ", ".join(
            f"{name}={'OK' if info.get('passed') else 'FAIL'}"
            for name, info in s6.get("targets", {}).items()
        ) or str(s6.get("error", "no targets executed"))
        print(
            f"[{'PASS' if s6.get('passed') else 'FAIL'}] 6. Clean-Room Source Rebuilds "
            f"({s6.get('verified_target_count', 0)}/{s6.get('expected_target_count', 9)} verified, "
            f"{s6.get('total_duration_ms', 0):.1f} ms, temp_bytes={s6.get('remaining_temp_bytes', 0)}): "
            f"{target_summary}"
        )

    print("========================================================================")
    overall = "PASSED" if report["overall_passed"] else f"FAILED ({report['error_count']} errors)"
    print(f"  Overall Release Verification: {overall}")
    print("========================================================================")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify macOS Tahoe 26.6.2 (25G83) release artifacts, manifests, and EFI parity."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root directory (default: auto-detected).",
    )
    parser.add_argument(
        "--check-live-nixos",
        metavar="HOST",
        help="Optionally verify live target ESP over read-only SSH (e.g. <user>@<nixos-host>).",
    )
    parser.add_argument(
        "--check-source-rebuilds",
        action="store_true",
        help="Perform clean-room compilation of ACPI SSDTs, S0ixStandby.kext, NootedGreen patch, libxedrv.dylib, test_420v_blitalign, xe-h264sw-fixd, hp-wake-helper, and hp-bridge in a TemporaryDirectory.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        metavar="PATH",
        help="Write machine-readable verification report JSON to PATH.",
    )
    args = parser.parse_args(argv)

    report, errors = run_verification(
        args.root.resolve(),
        args.check_live_nixos,
        check_source_rebuilds=args.check_source_rebuilds,
    )
    print_summary(report)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n")

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
