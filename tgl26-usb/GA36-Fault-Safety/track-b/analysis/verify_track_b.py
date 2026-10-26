#!/usr/bin/env python3
"""独立复核 TrackB 24 个片段及其原始字节证据。

本脚本只读 GA35 已封存的 SystemKC 和本目录 JSON；找不到精确输入或任一
字节/hash/身份检查失败时以非零状态退出，不降级为静态“通过”。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SOURCE_SHA = "fbab2d48bf1470fb0ec15dd62a6bb90c39d8bb45ed68240d3c73f1e43e770dee"
SOURCE_REL = "inputs/macos-readonly/System/Library/KernelCollections/SystemKernelExtensions.kc"
UUID_BY_IMAGE = {
    "com.apple.driver.AppleIntelICLGraphics": "B7DF3049-D3A9-3070-9843-6E5AE47673D7",
    "com.apple.driver.AppleIntelICLLPGraphicsFramebuffer": "7949B335-4901-3B40-9EB6-3D9A34FE65C7",
    "com.apple.iokit.IOAcceleratorFamily2": "B77A42EC-6B0C-3A8D-89A2-B8F4CDBAC8C9",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_record_bytes(raw: bytes, record: dict[str, Any], label: str) -> None:
    """Check a caller/field fragment against its KC file offset."""
    offset = int(record["kc_fileoff"])
    encoded = bytes.fromhex(record["bytes"])
    if "size" in record:
        check(len(encoded) == int(record["size"]), f"{label}: encoded size mismatch")
    va_key = "instruction_va" if "instruction_va" in record else "va"
    check(int(record[va_key]) == offset, f"{label}: VA/fileoff mismatch")
    check(raw[offset : offset + len(encoded)] == encoded, f"{label}: raw bytes mismatch")


def main() -> int:
    track_b = Path(__file__).resolve().parents[1]
    ga35 = track_b.parents[1] / "GA35-Driver-Reversing"
    source_path = ga35 / SOURCE_REL
    evidence_path = track_b / "analysis" / "focused-fragments.json"

    check(source_path.is_file(), f"missing sealed raw KC: {source_path}")
    check(evidence_path.is_file(), f"missing evidence: {evidence_path}")
    raw = source_path.read_bytes()
    check(sha256(raw) == SOURCE_SHA, "raw SystemKC SHA-256 mismatch")

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    check(evidence.get("schema") == "GA36-track-b-focused-functions-v1", "schema mismatch")
    check(evidence.get("source_sha256") == SOURCE_SHA, "evidence source SHA mismatch")
    functions = evidence.get("functions")
    check(isinstance(functions, list), "functions is not a list")
    check(len(functions) == 24, f"expected 24 functions, got {len(functions)}")
    check(evidence.get("focus_count") == 24, "focus_count mismatch")
    check(evidence.get("max_focus_functions") == 24, "function budget mismatch")

    selected = 0
    callers = 0
    fragments = 0
    for index, function in enumerate(functions):
        label = f"function[{index}] {function.get('name', '<unnamed>')}"
        check(function.get("source") == SOURCE_REL, f"{label}: source path mismatch")
        check(function.get("source_sha256") == SOURCE_SHA, f"{label}: source SHA mismatch")
        image = function.get("image")
        check(image in UUID_BY_IMAGE, f"{label}: unknown image")
        check(function.get("image_uuid") == UUID_BY_IMAGE[image], f"{label}: image UUID mismatch")

        entry = int(function["entry_va"])
        fileoff = int(function["kc_fileoff"])
        end = int(function["extent_end_va"])
        length = int(function["length_bytes"])
        check(entry == fileoff, f"{label}: entry/fileoff mismatch")
        check(end - entry == length, f"{label}: extent length mismatch")
        check(length > 0, f"{label}: empty extent")

        expected = bytes.fromhex(function["raw_bytes"])
        check(len(expected) == length, f"{label}: raw_bytes length mismatch")
        actual = raw[fileoff : fileoff + length]
        check(actual == expected, f"{label}: selected slice bytes mismatch")
        check(sha256(actual) == function["raw_sha256"], f"{label}: selected slice SHA mismatch")
        selected += 1

        for block_index, block in enumerate(function.get("basic_block_starts", [])):
            block_va = int(block, 16) if isinstance(block, str) else int(block)
            check(entry <= block_va < end, f"{label} block[{block_index}]: outside extent")

        for caller_index, caller in enumerate(function.get("callers", [])):
            check_record_bytes(raw, caller, f"{label} caller[{caller_index}]")
            callers += 1

        for fragment_index, fragment in enumerate(function.get("field_lock_fragments", [])):
            check_record_bytes(raw, fragment, f"{label} fragment[{fragment_index}]")
            fragment_offset = int(fragment["kc_fileoff"])
            fragment_size = int(fragment["size"])
            check(entry <= fragment_offset and fragment_offset + fragment_size <= end,
                  f"{label} fragment[{fragment_index}]: outside function extent")
            fragments += 1

    print(
        f"PASS: raw SystemKC SHA, {selected}/24 selected slices, "
        f"{callers} caller records, {fragments} field/lock fragments, "
        "basic-block bounds, and image/source UUID-SHA identities verified"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}")
        raise SystemExit(1)
