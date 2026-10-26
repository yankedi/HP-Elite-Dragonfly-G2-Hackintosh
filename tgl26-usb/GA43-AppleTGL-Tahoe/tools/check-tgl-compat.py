#!/usr/bin/env python3
"""Read-only Apple TGL driver compatibility preflight for the GA4.3 profile.

This tool never writes to the driver files it inspects. It checks:

  * SHA-256 against the hashes declared in the profile;
  * thin Mach-O architecture / file type / build-version load command;
  * bundle version from Contents/Info.plist;
  * expected original bytes for offset patches;
  * exact occurrence counts for pattern patches;
  * duplicate patch IDs, overlapping writes and conflicting replacements.

A matching target hash is only file identity. It is not proof that a patch is
safe on the target OS, and the tool says so in its status text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import struct
import sys
from pathlib import Path

TOOL_VERSION = "1.0.0"

MH_MAGIC_64 = 0xFEEDFACF
FAT_MAGICS = {0xCAFEBABE, 0xBEBAFECA, 0xCAFEBABF, 0xBFBAFECA}
CPU_X86_64 = 0x01000007
CPU_ARM64 = 0x0100000C
FILETYPES = {
    0x1: "MH_OBJECT",
    0x2: "MH_EXECUTE",
    0x6: "MH_DYLIB",
    0x8: "MH_BUNDLE",
    0xB: "MH_KEXT_BUNDLE",
}
LC_BUILD_VERSION = 0x32
LC_VERSION_MIN_MACOSX = 0x24
LC_UUID = 0x1B
LC_ID_DYLIB = 0x0D
LC_SEGMENT_64 = 0x19

EXIT_OK = 0
EXIT_MISSING_TARGET = 2
EXIT_HASH_MISMATCH = 3
EXIT_MACHO_INVALID = 4
EXIT_PATCH_MISMATCH = 5
EXIT_CONFIG = 6
EXIT_FIXTURE_OR_DONOR = 7


class ConfigError(Exception):
    pass


class CheckError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_only_bytes(path: Path) -> bytes:
    # O_RDONLY only; no mmap with write permission and no temporary file.
    fd = os.open(path, os.O_RDONLY)
    try:
        before = os.fstat(fd)
        chunks = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise CheckError(EXIT_MACHO_INVALID, f"file changed while being read: {path}")
    return b"".join(chunks)


def decode_version(value: int) -> str:
    return f"{(value >> 16) & 0xFFFF}.{(value >> 8) & 0xFF}.{value & 0xFF}"


def parse_macho(data: bytes) -> dict:
    if len(data) < 32:
        raise CheckError(EXIT_MACHO_INVALID, "file is shorter than a Mach-O 64 header")
    magic_be = struct.unpack_from(">I", data, 0)[0]
    if magic_be in FAT_MAGICS:
        raise CheckError(EXIT_MACHO_INVALID, "fat/universal Mach-O is not supported; provide a thin x86_64 slice")
    magic_le = struct.unpack_from("<I", data, 0)[0]
    if magic_le != MH_MAGIC_64:
        raise CheckError(EXIT_MACHO_INVALID, f"not a thin 64-bit Mach-O (magic 0x{magic_le:08x})")
    cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags, reserved = struct.unpack_from(
        "<IiiIIII", data, 4
    )
    arch = {CPU_X86_64: "x86_64", CPU_ARM64: "arm64"}.get(cputype, f"cputype_0x{cputype:08x}")
    out = {
        "magic": "MH_MAGIC_64",
        "cputype": cputype,
        "cpusubtype": cpusubtype,
        "arch": arch,
        "filetype": FILETYPES.get(filetype, f"0x{filetype:x}"),
        "ncmds": ncmds,
        "sizeofcmds": sizeofcmds,
        "flags": flags,
        "load_commands": [],
        "uuid": None,
        "id_dylib": None,
        "build_version": None,
    }
    if 32 + sizeofcmds > len(data):
        raise CheckError(EXIT_MACHO_INVALID, "load command table extends past end of file")
    cursor = 32
    for _ in range(ncmds):
        if cursor + 8 > 32 + sizeofcmds:
            raise CheckError(EXIT_MACHO_INVALID, "truncated load command")
        cmd, cmdsize = struct.unpack_from("<II", data, cursor)
        if cmdsize < 8 or cursor + cmdsize > 32 + sizeofcmds:
            raise CheckError(EXIT_MACHO_INVALID, f"invalid load command size {cmdsize} at 0x{cursor:x}")
        entry = {"cmd": f"0x{cmd:08x}", "cmdsize": cmdsize, "offset": cursor}
        if cmd == LC_BUILD_VERSION and cmdsize >= 24:
            platform, minos, sdk, ntools = struct.unpack_from("<IIII", data, cursor + 8)
            entry.update(
                {
                    "platform": platform,
                    "minos": decode_version(minos),
                    "sdk": decode_version(sdk),
                    "ntools": ntools,
                }
            )
            out["build_version"] = entry
        elif cmd == LC_VERSION_MIN_MACOSX and cmdsize >= 16:
            version, sdk = struct.unpack_from("<II", data, cursor + 8)
            entry.update({"minos": decode_version(version), "sdk": decode_version(sdk)})
            out["build_version"] = entry
        elif cmd == LC_UUID and cmdsize >= 24:
            entry["uuid"] = data[cursor + 8 : cursor + 24].hex()
            out["uuid"] = entry["uuid"]
        elif cmd == LC_ID_DYLIB and cmdsize >= 24:
            name_off = struct.unpack_from("<I", data, cursor + 8)[0]
            start = cursor + name_off
            end = cursor + cmdsize
            name = data[start:end].split(b"\0", 1)[0].decode("utf-8", "replace")
            entry["name"] = name
            out["id_dylib"] = name
        elif cmd == LC_SEGMENT_64 and cmdsize >= 72:
            segname = data[cursor + 8 : cursor + 24].split(b"\0", 1)[0].decode("ascii", "replace")
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<QQQQ", data, cursor + 24)
            entry.update(
                {
                    "segname": segname,
                    "vmaddr": vmaddr,
                    "vmsize": vmsize,
                    "fileoff": fileoff,
                    "filesize": filesize,
                }
            )
        out["load_commands"].append(entry)
        cursor += cmdsize
    return out


def find_all(data: bytes, needle: bytes) -> list[int]:
    out = []
    start = 0
    while True:
        pos = data.find(needle, start)
        if pos < 0:
            return out
        out.append(pos)
        start = pos + 1


def hex_bytes(value: object, field: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) % 2:
        raise ConfigError(f"{field} must be a non-empty even-length hex string")
    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise ConfigError(f"{field} is not valid hex: {exc}") from exc


def validate_patch(patch: dict, binary_key: str) -> None:
    pid = patch.get("id")
    if not isinstance(pid, str) or not pid:
        raise ConfigError(f"{binary_key}: every patch needs a non-empty id")
    if not isinstance(patch.get("selected"), bool):
        raise ConfigError(f"{pid}: selected must be a boolean")
    has_offset = "offset" in patch
    has_pattern = "pattern_hex" in patch
    if has_offset == has_pattern:
        raise ConfigError(f"{pid}: exactly one of offset or pattern_hex is required")
    if has_offset:
        off = patch["offset"]
        if not isinstance(off, int) or off < 0:
            raise ConfigError(f"{pid}: offset must be a non-negative integer")
        old = hex_bytes(patch.get("old_hex"), f"{pid}.old_hex")
        new = hex_bytes(patch.get("new_hex"), f"{pid}.new_hex")
        if len(old) != len(new):
            raise ConfigError(f"{pid}: in-place replacement must have the same length")
        if old == new:
            raise ConfigError(f"{pid}: old and new bytes are identical")
    else:
        old = hex_bytes(patch.get("pattern_hex"), f"{pid}.pattern_hex")
        new = hex_bytes(patch.get("replace_hex"), f"{pid}.replace_hex")
        if len(old) != len(new):
            raise ConfigError(f"{pid}: pattern replacement must have the same length")
        if old == new:
            raise ConfigError(f"{pid}: pattern and replacement are identical")
        expected = patch.get("expected_matches")
        if not isinstance(expected, int) or expected < 1:
            raise ConfigError(f"{pid}: expected_matches must be a positive integer")


def load_config(path: Path) -> dict:
    try:
        config = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config is not valid JSON: {exc}") from exc
    if config.get("schema_version") != 1:
        raise ConfigError("unsupported config schema_version")
    if not config.get("target") or not config.get("binaries"):
        raise ConfigError("config must contain target and binaries")
    seen_ids: set[str] = set()
    for key, binary in config["binaries"].items():
        if not isinstance(binary, dict):
            raise ConfigError(f"binaries.{key} must be an object")
        if not binary.get("relative_path"):
            raise ConfigError(f"binaries.{key}.relative_path is required")
        for patch in binary.get("patches", []):
            validate_patch(patch, key)
            pid = patch["id"]
            if pid in seen_ids:
                raise ConfigError(f"duplicate patch id: {pid}")
            seen_ids.add(pid)
    return config


def check_conflicts(binary_key: str, patches: list[dict]) -> list[str]:
    errors: list[str] = []
    selected = [p for p in patches if p["selected"]]
    seen_offsets: dict[int, str] = {}
    seen_shapes: dict[tuple[str, str], str] = {}
    for patch in selected:
        pid = patch["id"]
        if "offset" in patch:
            off = patch["offset"]
            if off in seen_offsets:
                errors.append(f"{binary_key}: {pid} overlaps offset 0x{off:x} used by {seen_offsets[off]}")
            seen_offsets[off] = pid
        else:
            shape = (patch["pattern_hex"], patch["replace_hex"])
            if shape in seen_shapes:
                errors.append(f"{binary_key}: {pid} duplicates pattern/replacement of {seen_shapes[shape]}")
            seen_shapes[shape] = pid
    return errors


def check_patch_bytes(pid: str, data: bytes, patch: dict) -> dict:
    if "offset" in patch:
        off = patch["offset"]
        old = bytes.fromhex(patch["old_hex"])
        new = bytes.fromhex(patch["new_hex"])
        if off + len(old) > len(data):
            raise CheckError(EXIT_PATCH_MISMATCH, f"{pid}: patch range 0x{off:x}+{len(old)} exceeds file size")
        actual = data[off : off + len(old)]
        if actual != old:
            raise CheckError(
                EXIT_PATCH_MISMATCH,
                f"{pid}: bytes at 0x{off:x} do not match (expected {old.hex()}, got {actual.hex()})",
            )
        return {"id": pid, "kind": "offset", "offset": off, "length": len(old), "match": True}
    pattern = bytes.fromhex(patch["pattern_hex"])
    positions = find_all(data, pattern)
    expected = patch["expected_matches"]
    if len(positions) != expected:
        raise CheckError(
            EXIT_PATCH_MISMATCH,
            f"{pid}: expected {expected} occurrence(s), found {len(positions)} at "
            + ", ".join(f"0x{p:x}" for p in positions[:8]),
        )
    return {
        "id": pid,
        "kind": "pattern",
        "expected_matches": expected,
        "matches": positions,
    }


def check_overlaps(binary_key: str, results: list[dict]) -> list[str]:
    intervals = []
    errors = []
    for item in results:
        if item["kind"] == "offset":
            intervals.append((item["offset"], item["offset"] + item["length"], item["id"]))
        else:
            length = item["_length"]
            for pos in item["matches"]:
                intervals.append((pos, pos + length, item["id"]))
    intervals.sort()
    for i in range(1, len(intervals)):
        prev_start, prev_end, prev_id = intervals[i - 1]
        start, end, pid = intervals[i]
        if start < prev_end:
            errors.append(f"{binary_key}: {pid} overlaps {prev_id} at 0x{start:x}")
    return errors


def strip_private(result: dict) -> dict:
    return {k: v for k, v in result.items() if not k.startswith("_")}


def check_binary(config: dict, key: str, binary: dict, input_dir: Path, allow_donor: bool, audit_unselected: bool = False) -> tuple[dict, int]:
    path = input_dir / binary["relative_path"]
    if not path.is_file():
        raise CheckError(EXIT_MISSING_TARGET, f"{key}: target file not supplied: {path}")
    data = read_only_bytes(path)
    digest = sha256_bytes(data)
    known = binary.get("known_hashes", [])
    match = next((h for h in known if h.get("sha256", "").lower() == digest), None)
    info = {
        "key": key,
        "path": str(path),
        "sha256": digest,
        "role": match.get("role") if match else None,
        "hash_origin": match.get("origin") if match else None,
        "hash_status": match.get("status") if match else "UNKNOWN",
        "macho": None,
        "bundle": None,
        "patches": [],
        "status": "UNKNOWN",
    }
    if match is None:
        raise CheckError(
            EXIT_HASH_MISMATCH,
            f"{key}: SHA-256 {digest} is not one of the declared target/donor hashes; refusing",
        )
    is_target = match.get("role") == "target_25G83"
    is_donor = match.get("role") == "donor_16.0.32"
    is_fixture = match.get("role") == "fixture"
    if config.get("fixture"):
        # A profile marked as a fixture can never produce a target result,
        # even if its hash entry was labelled target_25G83 by mistake.
        is_target = False
        is_donor = False
        is_fixture = True
    if is_donor and not allow_donor:
        raise CheckError(
            EXIT_FIXTURE_OR_DONOR,
            f"{key}: this is the pinned 16.0.32 donor, not a 25G83 target file; rerun with --allow-donor for a donor-only audit",
        )
    if not (is_target or is_donor or is_fixture):
        raise CheckError(EXIT_HASH_MISMATCH, f"{key}: hash matched an unsupported role {match.get('role')!r}")

    macho = parse_macho(data)
    info["macho"] = {
        "arch": macho["arch"],
        "filetype": macho["filetype"],
        "uuid": macho["uuid"],
        "id_dylib": macho["id_dylib"],
        "build_version": macho["build_version"],
        "ncmds": macho["ncmds"],
        "sizeofcmds": macho["sizeofcmds"],
    }
    if macho["arch"] != binary.get("expected_arch", "x86_64"):
        raise CheckError(EXIT_MACHO_INVALID, f"{key}: architecture {macho['arch']} != {binary.get('expected_arch')}")
    if binary.get("expected_filetype") and macho["filetype"] != binary["expected_filetype"]:
        raise CheckError(
            EXIT_MACHO_INVALID,
            f"{key}: file type {macho['filetype']} != {binary['expected_filetype']}",
        )

    info_path = binary.get("info_plist_relative_path")
    if info_path:
        plist_path = input_dir / info_path
        if plist_path.is_file():
            try:
                plist = plistlib.loads(plist_path.read_bytes())
            except Exception as exc:  # noqa: BLE001 - report exact parse failure
                raise CheckError(EXIT_MACHO_INVALID, f"{key}: cannot parse Info.plist: {exc}") from exc
            info["bundle"] = {
                "CFBundleIdentifier": plist.get("CFBundleIdentifier"),
                "CFBundleShortVersionString": plist.get("CFBundleShortVersionString"),
                "CFBundleVersion": plist.get("CFBundleVersion"),
                "CFBundleExecutable": plist.get("CFBundleExecutable"),
            }
            expected_version = binary.get("expected_bundle_version")
            if expected_version and plist.get("CFBundleShortVersionString") != expected_version:
                raise CheckError(
                    EXIT_MACHO_INVALID,
                    f"{key}: bundle version {plist.get('CFBundleShortVersionString')!r} != {expected_version!r}",
                )
        elif binary.get("require_info_plist"):
            raise CheckError(EXIT_MACHO_INVALID, f"{key}: required Info.plist not found: {plist_path}")

    conflicts = check_conflicts(key, binary.get("patches", []))
    if conflicts:
        raise CheckError(EXIT_CONFIG, "; ".join(conflicts))

    selected = [p for p in binary.get("patches", []) if p["selected"]]
    results = []
    for patch in selected:
        result = check_patch_bytes(patch["id"], data, patch)
        result["classification"] = patch.get("classification")
        result["status"] = patch.get("status")
        if result["kind"] == "pattern":
            result["_length"] = len(bytes.fromhex(patch["pattern_hex"]))
        results.append(result)
    overlaps = check_overlaps(key, results)
    if overlaps:
        raise CheckError(EXIT_CONFIG, "; ".join(overlaps))
    info["patches"] = [strip_private(r) for r in results]
    info["audit"] = []
    if audit_unselected:
        for patch in binary.get("patches", []):
            if patch["selected"]:
                continue
            try:
                checked = check_patch_bytes(patch["id"], data, patch)
                checked["audit_status"] = "MATCH"
                checked["classification"] = patch.get("classification")
                checked["status"] = patch.get("status")
            except CheckError as exc:
                checked = {
                    "id": patch["id"],
                    "audit_status": "MISMATCH_OR_AMBIGUOUS",
                    "classification": patch.get("classification"),
                    "status": patch.get("status"),
                    "detail": str(exc),
                }
            info["audit"].append(strip_private(checked))

    if is_target:
        info["status"] = "TARGET_BINARY_MATCH"
        code = EXIT_OK
    elif is_donor:
        info["status"] = "DONOR_ONLY"
        code = EXIT_OK
    else:
        info["status"] = "FIXTURE_ONLY"
        code = EXIT_OK
    return info, code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="profile JSON")
    parser.add_argument("--input-dir", required=True, type=Path, help="directory containing the supplied Apple files")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="require a target hash and reject donor/fixture modes")
    parser.add_argument("--allow-donor", action="store_true", help="allow the pinned 16.0.32 donor for audit only")
    parser.add_argument("--allow-fixture", action="store_true", help="allow a synthetic fixture; never a target pass")
    parser.add_argument("--audit-unselected", action="store_true", help="check unselected patch bytes without failing on mismatch")
    return parser


def run(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        result = {
            "tool": "check-tgl-compat",
            "tool_version": TOOL_VERSION,
            "config": str(args.config),
            "profile_id": None,
            "mode": "config",
            "target": None,
            "overall": "FAIL",
            "binaries": [],
            "errors": [str(exc)],
            "warnings": [],
        }
        return emit(result, args.json, EXIT_CONFIG)

    fixture = bool(config.get("fixture"))
    result = {
        "tool": "check-tgl-compat",
        "tool_version": TOOL_VERSION,
        "config": str(args.config),
        "profile_id": config.get("profile_id"),
        "mode": "fixture" if fixture else "target",
        "target": config.get("target"),
        "overall": "FAIL",
        "binaries": [],
        "errors": [],
        "warnings": [],
    }
    if fixture and not args.allow_fixture:
        result["errors"].append("fixture config requires --allow-fixture; fixtures are never an Apple target result")
        return emit(result, args.json, EXIT_FIXTURE_OR_DONOR)
    if fixture and args.strict:
        result["errors"].append("--strict cannot be used with a fixture")
        return emit(result, args.json, EXIT_FIXTURE_OR_DONOR)

    try:
        for key, binary in config["binaries"].items():
            info, _ = check_binary(config, key, binary, args.input_dir, args.allow_donor, args.audit_unselected)
            result["binaries"].append(info)
    except CheckError as exc:
        result["errors"].append(str(exc))
        return emit(result, args.json, exc.code)
    except ConfigError as exc:
        result["errors"].append(str(exc))
        return emit(result, args.json, EXIT_CONFIG)

    modes = {b["status"] for b in result["binaries"]}
    if fixture:
        result["overall"] = "FIXTURE_ONLY"
        code = EXIT_OK
        result["warnings"].append("Synthetic fixture only. This is not an Apple driver and proves no macOS/TGL compatibility.")
    elif "DONOR_ONLY" in modes:
        result["overall"] = "DONOR_ONLY"
        code = EXIT_OK
        result["warnings"].append("Pinned 16.0.32 donor only. This is not a 25G83 target verification.")
    elif modes == {"TARGET_BINARY_MATCH"}:
        result["overall"] = "TARGET_PREFLIGHT_OK"
        code = EXIT_OK
        result["warnings"].append("Preconditions matched; this does not prove runtime safety or patch necessity.")
    else:
        result["overall"] = "FAIL"
        code = EXIT_PATCH_MISMATCH
    if args.strict:
        if any(b["status"] != "TARGET_BINARY_MATCH" for b in result["binaries"]):
            result["overall"] = "TARGET_HASH_REQUIRED"
            code = EXIT_HASH_MISMATCH
            result["errors"].append("--strict requires every binary to match a target_25G83 hash")
    return emit(result, args.json, code)


def emit(result: dict, as_json: bool, code: int) -> int:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=False))
        return code
    print(f"check-tgl-compat {TOOL_VERSION}: {result.get('profile_id')} -> {result['overall']}")
    for binary in result.get("binaries", []):
        macho = binary.get("macho") or {}
        bundle = binary.get("bundle") or {}
        print(
            f"  {binary['key']}: {binary['status']} sha256={binary['sha256']} "
            f"arch={macho.get('arch')} type={macho.get('filetype')} "
            f"version={bundle.get('CFBundleShortVersionString')} "
            f"uuid={macho.get('uuid')} build={macho.get('build_version', {}).get('minos') if macho.get('build_version') else None}"
        )
        for patch in binary.get("patches", []):
            where = f"0x{patch['offset']:x}" if patch["kind"] == "offset" else ",".join(
                f"0x{p:x}" for p in patch.get("matches", [])
            )
            print(f"    {patch['id']} [{patch.get('classification')}] {where}")
        for patch in binary.get("audit", []):
            print(f"    audit {patch['id']} [{patch.get('classification')}] {patch['audit_status']}")
    for warning in result.get("warnings", []):
        print(f"  warning: {warning}")
    for error in result.get("errors", []):
        print(f"  error: {error}", file=sys.stderr)
    return code


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
