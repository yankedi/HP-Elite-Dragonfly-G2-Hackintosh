#!/usr/bin/env python3
"""CPU-only tests for the read-only TGL compatibility preflight.

The Mach-O files here are synthetic fixtures. They are deliberately labelled
FIXTURE_ONLY and are never described as Apple drivers.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "check-tgl-compat.py"
MH_MAGIC_64 = 0xFEEDFACF
CPU_X86_64 = 0x01000007
CPU_ARM64 = 0x0100000C


def make_macho(
    *,
    filetype: int = 0x6,
    cputype: int = CPU_X86_64,
    patch_at_0x100: bytes = bytes.fromhex("aabbccdd"),
    pattern_count: int = 1,
) -> bytes:
    uuid = bytes(range(16))
    load = struct.pack("<IIIIII", 0x32, 24, 2, 0x000F0000, 0x000F0000, 0) + struct.pack(
        "<II", 0x1B, 24
    ) + uuid
    header = struct.pack(
        "<IiiIIIII",
        MH_MAGIC_64,
        cputype,
        3,
        filetype,
        2,
        len(load),
        0,
        0,
    )
    data = bytearray(header + load)
    if len(data) < 0x400:
        data.extend(b"\0" * (0x400 - len(data)))
    data[0x100 : 0x104] = patch_at_0x100
    for i in range(pattern_count):
        start = 0x200 + i * 0x20
        data[start : start + 4] = bytes.fromhex("deadbeef")
    return bytes(data)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_config(
    digest: str,
    *,
    patches: list[dict] | None = None,
    fixture: bool = True,
    known_role: str = "fixture",
    expected_arch: str = "x86_64",
    relative_path: str = "fixture.bin",
) -> dict:
    if patches is None:
        patches = [
            {
                "id": "fixture.offset",
                "offset": 0x100,
                "old_hex": "aabbccdd",
                "new_hex": "11223344",
                "classification": "B",
                "selected": True,
                "status": "NOT_TESTED",
            },
            {
                "id": "fixture.pattern",
                "pattern_hex": "deadbeef",
                "replace_hex": "cafebabe",
                "expected_matches": 1,
                "classification": "B",
                "selected": True,
                "status": "NOT_TESTED",
            },
        ]
    return {
        "schema_version": 1,
        "profile_id": "fixture-profile",
        "fixture": fixture,
        "target": {"macos_build": "25G83", "pci_id": "8086:9A49"},
        "binaries": {
            "fixture": {
                "relative_path": relative_path,
                "expected_arch": expected_arch,
                "expected_filetype": "MH_DYLIB",
                "require_info_plist": False,
                "known_hashes": [
                    {
                        "sha256": digest,
                        "role": known_role,
                        "origin": "test-generated synthetic file",
                        "status": "FIXTURE",
                    }
                ],
                "patches": patches,
            }
        },
    }


class FixtureCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="tgl-compat-test-")
        self.dir = Path(self.tmp.name)
        self.bin = self.dir / "fixture.bin"
        self.config = self.dir / "config.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_fixture(self, data: bytes, **config_kwargs) -> dict:
        self.bin.write_bytes(data)
        config = make_config(sha(data), **config_kwargs)
        self.config.write_text(json.dumps(config))
        return config

    def run_tool(self, *extra: str) -> tuple[int, dict, str]:
        cmd = [
            sys.executable,
            str(TOOL),
            "--config",
            str(self.config),
            "--input-dir",
            str(self.dir),
            "--json",
            *extra,
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"tool did not emit JSON (exit {proc.returncode}):\nstdout={proc.stdout}\nstderr={proc.stderr}")
        return proc.returncode, result, proc.stderr

    def test_fixture_requires_explicit_flag(self) -> None:
        self.write_fixture(make_macho())
        code, result, _ = self.run_tool()
        self.assertEqual(code, 7)
        self.assertEqual(result["overall"], "FAIL")
        self.assertIn("allow-fixture", result["errors"][0])

    def test_fixture_success_is_not_a_target_pass(self) -> None:
        self.write_fixture(make_macho())
        code, result, _ = self.run_tool("--allow-fixture")
        self.assertEqual(code, 0)
        self.assertEqual(result["overall"], "FIXTURE_ONLY")
        self.assertEqual(result["binaries"][0]["status"], "FIXTURE_ONLY")
        self.assertNotIn("PASS", result["overall"])

    def test_strict_rejects_fixture(self) -> None:
        self.write_fixture(make_macho())
        code, result, _ = self.run_tool("--allow-fixture", "--strict")
        self.assertEqual(code, 7)
        self.assertIn("strict", " ".join(result["errors"]))

    def test_fixture_role_cannot_be_relabelled_target(self) -> None:
        self.write_fixture(make_macho(), known_role="target_25G83")
        code, result, _ = self.run_tool("--allow-fixture")
        self.assertEqual(code, 0)
        self.assertEqual(result["overall"], "FIXTURE_ONLY")
        self.assertEqual(result["binaries"][0]["status"], "FIXTURE_ONLY")

    def test_missing_file_exit_2(self) -> None:
        self.bin.write_bytes(make_macho())
        config = make_config("00" * 32, relative_path="does-not-exist.bin")
        self.config.write_text(json.dumps(config))
        code, result, _ = self.run_tool("--allow-fixture")
        self.assertEqual(code, 2)
        self.assertIn("not supplied", " ".join(result["errors"]))

    def test_hash_mismatch_exit_3(self) -> None:
        self.write_fixture(make_macho())
        config = json.loads(self.config.read_text())
        config["binaries"]["fixture"]["known_hashes"][0]["sha256"] = "00" * 32
        self.config.write_text(json.dumps(config))
        code, result, _ = self.run_tool("--allow-fixture")
        self.assertEqual(code, 3)
        self.assertIn("SHA-256", " ".join(result["errors"]))

    def test_wrong_arch_exit_4(self) -> None:
        data = make_macho(cputype=CPU_ARM64)
        self.write_fixture(data, expected_arch="x86_64")
        code, result, _ = self.run_tool("--allow-fixture")
        self.assertEqual(code, 4)
        self.assertIn("architecture", " ".join(result["errors"]))

    def test_fat_macho_exit_4(self) -> None:
        data = b"\xca\xfe\xba\xbe" + make_macho()[4:]
        self.write_fixture(data)
        code, result, _ = self.run_tool("--allow-fixture")
        self.assertEqual(code, 4)
        self.assertIn("fat/universal", " ".join(result["errors"]))

    def test_offset_mismatch_exit_5(self) -> None:
        data = bytearray(make_macho())
        data[0x100:0x104] = b"WXYZ"
        self.write_fixture(bytes(data))
        code, result, _ = self.run_tool("--allow-fixture")
        self.assertEqual(code, 5)
        self.assertIn("do not match", " ".join(result["errors"]))

    def test_pattern_count_mismatch_exit_5(self) -> None:
        self.write_fixture(make_macho(pattern_count=2))
        code, result, _ = self.run_tool("--allow-fixture")
        self.assertEqual(code, 5)
        self.assertIn("expected 1", " ".join(result["errors"]))

    def test_overlapping_selected_patches_exit_6(self) -> None:
        patches = [
            {
                "id": "fixture.first",
                "offset": 0x100,
                "old_hex": "aabbccdd",
                "new_hex": "11223344",
                "classification": "B",
                "selected": True,
                "status": "NOT_TESTED",
            },
            {
                "id": "fixture.second",
                "offset": 0x102,
                "old_hex": "ccdd",
                "new_hex": "5566",
                "classification": "B",
                "selected": True,
                "status": "NOT_TESTED",
            },
        ]
        self.write_fixture(make_macho(), patches=patches)
        code, result, _ = self.run_tool("--allow-fixture")
        self.assertEqual(code, 6)
        self.assertIn("overlaps", " ".join(result["errors"]))

    def test_duplicate_patch_id_exit_6(self) -> None:
        patches = [
            {
                "id": "fixture.same",
                "offset": 0x100,
                "old_hex": "aabbccdd",
                "new_hex": "11223344",
                "classification": "B",
                "selected": True,
                "status": "NOT_TESTED",
            },
            {
                "id": "fixture.same",
                "pattern_hex": "deadbeef",
                "replace_hex": "cafebabe",
                "expected_matches": 1,
                "classification": "B",
                "selected": True,
                "status": "NOT_TESTED",
            },
        ]
        self.write_fixture(make_macho(), patches=patches)
        code, result, _ = self.run_tool("--allow-fixture")
        self.assertEqual(code, 6)
        self.assertIn("duplicate patch id", result["errors"][0])

    def test_audit_unselected_reports_mismatch_without_failing(self) -> None:
        patches = [
            {
                "id": "fixture.selected",
                "offset": 0x100,
                "old_hex": "aabbccdd",
                "new_hex": "11223344",
                "classification": "B",
                "selected": True,
                "status": "NOT_TESTED",
            },
            {
                "id": "fixture.unselected",
                "pattern_hex": "f0e0d0c0",
                "replace_hex": "f1e1d1c1",
                "expected_matches": 1,
                "classification": "A",
                "selected": False,
                "status": "EXCLUDED_RPL",
            },
        ]
        self.write_fixture(make_macho(), patches=patches)
        code, result, _ = self.run_tool("--allow-fixture", "--audit-unselected")
        self.assertEqual(code, 0)
        self.assertEqual(result["overall"], "FIXTURE_ONLY")
        audit = result["binaries"][0]["audit"]
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["audit_status"], "MISMATCH_OR_AMBIGUOUS")

    def test_tool_does_not_modify_input(self) -> None:
        data = make_macho()
        self.write_fixture(data)
        before = self.bin.stat()
        before_hash = hashlib.sha256(self.bin.read_bytes()).hexdigest()
        code, _, _ = self.run_tool("--allow-fixture")
        self.assertEqual(code, 0)
        after = self.bin.stat()
        after_hash = hashlib.sha256(self.bin.read_bytes()).hexdigest()
        self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)
        self.assertEqual(before.st_size, after.st_size)
        self.assertEqual(before_hash, after_hash)


if __name__ == "__main__":
    unittest.main()
