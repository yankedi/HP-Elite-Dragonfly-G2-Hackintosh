#!/usr/bin/env python3
"""Read-only THAG v2 extraction for the GA3.2b hang capture.

Source layout provenance: GA33-research/analysis/parse_thag.py plus the clang
`-fdump-record-layouts-complete` dump (layout_dump_ga32.txt).  This script does
NOT import or execute the ZIP's extract_ga32b.py; it re-derives every offset
from the verified layout and writes only new analysis outputs.

Capture layout (GA3.1/GA3.2, record size 0xC2A0 = 49,824 bytes):

  HangRecord header (0x00..0x8F)
    0x00 magic 'THAG' | 0x04 index | 0x08 ms | 0x0C attempts
    0x10 wakeDomain | 0x14 attemptReasons[8] | 0x34 regs[16] u32
    0x74 ggc | 0x78 dsmLo | 0x7C dsmHi | 0x80 resolveDiag/pad
    0x88 maxMem u64
  CaptureOutput at 0x90
    0x000 result | 0x008 fences[12 u64-ish] | 0x060 ramTop
    0x068 bbAddr | 0x070 pml4 | 0x078 batchStart
    0x080 batchPhys[8] | 0x0C0 batchValid | 0x0C4 batchPages
    0x0C8 tableReads | 0x0CC pageReads | 0x0D0 readBytes u64
    0x0D8 classifierReady | 0x0DC probeOk | 0x0E0 probe1
    0x0E4 bridgeValid | 0x0E8..0x0F4 exclusion flags
    0x0F8 bridgeRegs[4] | 0x108 foundSba/Vs/Ps | 0x110 sbaAt
    0x118 instructionBase | 0x120 kernelOffset[2] | 0x130 kernelAt[2]
    0x140 sbaCmd[22] | 0x198 kernelCmd[24] | 0x1F8 kernelPhys[2]
    0x208 kernelPages[2] | 0x210 batch[8*4096]
    0x8210 kernelVS[2*4096] | 0xA210 kernelPS[2*4096]

Kernel offsets/addresses are stored as index 0 = VS and index 1 = PS for this
capture (verified against the values; the array order is not assumed).
All addresses are CANDIDATES: no command-stream/genxml audit is performed here.
The capture stores driver-reported kernelPhys values but no raw PTEs, so a
"shared physical page" is a recorded field, never independently proved here.
"""

import argparse
import hashlib
import json
import posixpath
import stat
import struct
import sys
import zipfile
from pathlib import Path

RECORD_SIZE_V2 = 0xC2A0
MAX_RECORDS = 3
MAGIC = 0x47414854  # 'THAG' little-endian
KNOWN_CAPTURE_SIZE = 99_648
KNOWN_CAPTURE_SHA256 = "1622ecc2aecdcc85ae45dcf86e4219338f6e41e0243b27d5e7128a9999f13333"

REASONS = [
    "Ok", "RegsInvalid", "StolenUnknown", "AddrOutside", "LimitHit",
    "NotMapped", "ReadFailed", "Pml4Invalid", "NoBatch", "ScanIncomplete",
    "Disabled", "MemoryMapUnverified", "UnsafePhysicalRange", "WakesUnusable",
]

HANG_REGS = [
    (0x2140, "GFXREG_BATCHBUFF_BB_ADDR"),
    (0x2168, "GFXREG_BB_ADDR_UDW"),
    (0x2270, "GFXREG_RCS_PDP0_DESCRIPTOR_LO"),
    (0x2274, "GFXREG_RCS_PDP0_DESCRIPTOR_HI"),
    (0x2074, "GFXREG_RENDERDEBUG_ACTHD"),
    (0x2068, "GFXREG_RENDERDEBUG_IPEHR"),
    (0x2034, "GFXREG_RING_BUFFER_PRB0_HEAD"),
    (0x2030, "GFXREG_RING_BUFFER_PRB0_TAIL"),
    (0x2038, "GFXREG_RING_BUFFER_PRB0_START"),
    (0x206C, "GFXREG_RENDERDEBUG_INSTDONE_1"),
    (0x229C, "GFXREG_RCS_GFX_MODE"),
    (0x20C8, "(no GA2 report name)"),
    (0x2180, "GFXREG_RING_BUFFER_CCID"),
    (0x2234, "GFXREG_RCS_EXECLIST_STATUS"),
    (0x7100, "GFXREG_COMMON_SLICE_INSTDONE_REG"),
    (0x20B0, "GFXREG_CONDITION_EIR"),
]

# Candidate batch command headers recorded by the ZIP extraction.
EXPECTED_HEADERS = [
    ("STATE_BASE_ADDRESS", 0x61010014, 0x69F8),
    ("3DSTATE_PS", 0x7820000A, 0x6B6C),
    ("3DSTATE_VS", 0x78100007, 0x6C00),
]


def u8(buf, off):
    return buf[off]


def u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def u64(buf, off):
    return struct.unpack_from("<Q", buf, off)[0]


def sha256_bytes(blob):
    return hashlib.sha256(blob).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def reason_name(value):
    return REASONS[value] if 0 <= value < len(REASONS) else f"Unknown({value})"


def decode_record(data, index):
    base = index * RECORD_SIZE_V2
    out = base + 0x90
    result_raw = u32(data, out + 0x00)
    kernel_offset = [u64(data, out + 0x120 + 8 * i) for i in range(2)]
    kernel_at = [u64(data, out + 0x130 + 8 * i) for i in range(2)]
    regs = []
    for i, (addr, name) in enumerate(HANG_REGS):
        value = u32(data, base + 0x34 + 4 * i)
        regs.append({
            "index": i,
            "record_offset": hex(0x34 + 4 * i),
            "address": hex(addr),
            "name": name,
            "value": value,
            "value_hex": hex(value),
        })
    return {
        "index_field": u32(data, base + 0x04),
        "magic": hex(u32(data, base + 0x00)),
        "ms": u32(data, base + 0x08),
        "attempts": u32(data, base + 0x0C),
        "wakeDomain": u32(data, base + 0x10),
        "attemptReasons": [u32(data, base + 0x14 + 4 * i) for i in range(8)],
        "attemptReasonNames": [reason_name(u32(data, base + 0x14 + 4 * i)) for i in range(8)],
        "resolveDiag": u32(data, base + 0x80),
        "maxMem": u64(data, base + 0x88),
        "regs": regs,
        "out": {
            "result": result_raw,
            "resultName": reason_name(result_raw),
            "ramTop": u64(data, out + 0x60),
            "bbAddr": u64(data, out + 0x68),
            "pml4": u64(data, out + 0x70),
            "batchStart": u64(data, out + 0x78),
            "batchPhys": [u64(data, out + 0x80 + 8 * i) for i in range(8)],
            "batchValid": u32(data, out + 0xC0),
            "batchPages": u32(data, out + 0xC4),
            "tableReads": u32(data, out + 0xC8),
            "pageReads": u32(data, out + 0xCC),
            "readBytes": u64(data, out + 0xD0),
            "classifierReady": u32(data, out + 0xD8),
            "classifierProbeOk": u32(data, out + 0xDC),
            "classifierProbe1": u32(data, out + 0xE0),
            "bridgeValid": u32(data, out + 0xE4),
            "exclusionStolen": u32(data, out + 0xE8),
            "exclusionLowTop": u32(data, out + 0xEC),
            "exclusionTseg": u32(data, out + 0xF0),
            "exclusionsVerified": u32(data, out + 0xF4),
            "bridgeRegs": {
                "TOLUD": u32(data, out + 0xF8),
                "TSEGMB": u32(data, out + 0xFC),
                "BDSM": u32(data, out + 0x100),
                "BGSM": u32(data, out + 0x104),
            },
            "scan": {
                "foundSba": u8(data, out + 0x108),
                "foundVs": u8(data, out + 0x109),
                "foundPs": u8(data, out + 0x10A),
                "sbaAt": u64(data, out + 0x110),
                "instructionBase": u64(data, out + 0x118),
                "kernelOffset": kernel_offset,
                "kernelAt": kernel_at,
                "sbaCmdNonzero": sum(1 for i in range(22) if u32(data, out + 0x140 + 4 * i)),
                "kernelCmdNonzero": sum(1 for i in range(24) if u32(data, out + 0x198 + 4 * i)),
            },
            "kernelPhys": [u64(data, out + 0x1F8 + 8 * i) for i in range(2)],
            "kernelPages": [u32(data, out + 0x208 + 4 * i) for i in range(2)],
        },
    }


def nonzero(blob):
    return sum(1 for value in blob if value)


def first_last_nonzero(blob):
    hits = [i for i, value in enumerate(blob) if value]
    if not hits:
        return None
    return {"first": hex(hits[0]), "last": hex(hits[-1]), "nonzero_bytes": len(hits)}


def extract(capture_path, outdir, zip_path=None, zip_json_path=None):
    source = Path(capture_path)
    data = source.read_bytes()
    size = len(data)
    sha = sha256_bytes(data)

    problems = []
    if size == 0 or size % RECORD_SIZE_V2 != 0:
        problems.append(f"size {size} is not a whole multiple of 0x{RECORD_SIZE_V2:X}")
    records_in_file = size // RECORD_SIZE_V2 if size % RECORD_SIZE_V2 == 0 else 0
    if not 1 <= records_in_file <= MAX_RECORDS:
        problems.append(f"record count {records_in_file} outside 1..{MAX_RECORDS}")
    if size != KNOWN_CAPTURE_SIZE:
        problems.append(f"size {size} != known GA32b size {KNOWN_CAPTURE_SIZE}")
    if sha != KNOWN_CAPTURE_SHA256:
        problems.append(f"sha256 {sha} != known GA32b sha256 {KNOWN_CAPTURE_SHA256}")
    if problems:
        raise SystemExit("capture validation failed: " + "; ".join(problems))

    records = []
    for i in range(records_in_file):
        base = i * RECORD_SIZE_V2
        if u32(data, base) != MAGIC:
            raise SystemExit(f"record {i}: missing THAG magic")
        if u32(data, base + 0x04) != i:
            raise SystemExit(f"record {i}: index field {u32(data, base + 0x04)}")
        records.append(decode_record(data, i))

    success = [r for r in records
               if r["out"]["result"] == 0
               and r["out"]["batchValid"] == 0xFF
               and r["out"]["batchPages"] == 8]
    if len(success) != 1:
        raise SystemExit(f"expected exactly one complete success record, found {len(success)}")
    rec = success[0]
    i = rec["index_field"]
    base = i * RECORD_SIZE_V2

    batch = data[base + 0x2A0:base + 0x82A0]
    vs_window = data[base + 0x82A0:base + 0xA2A0]
    ps_window = data[base + 0xA2A0:base + 0xC2A0]
    if len(batch) != 32768 or len(vs_window) != 8192 or len(ps_window) != 8192:
        raise SystemExit("payload slice length mismatch")

    out = rec["out"]
    instr = out["scan"]["instructionBase"]
    vs_offset, ps_offset = out["scan"]["kernelOffset"][0], out["scan"]["kernelOffset"][1]
    vs_entry, ps_entry = out["scan"]["kernelAt"][0], out["scan"]["kernelAt"][1]
    address_checks = {
        "vs_entry_equals_instruction_base_plus_offset": vs_entry == instr + vs_offset,
        "ps_entry_equals_instruction_base_plus_offset": ps_entry == instr + ps_offset,
        "vs_offset_inside_window": vs_offset < 8192,
        "ps_offset_inside_window": ps_offset < 8192,
        "batch_start_plus_0x7104_equals_bbaddr": out["batchStart"] + 0x7104 == out["bbAddr"],
    }
    if not all(address_checks.values()):
        raise SystemExit(f"address consistency failure: {address_checks}")

    # Candidate windows, deliberately not asserted to be real kernel lengths.
    ps_candidate = ps_window[ps_offset:vs_offset] if ps_offset < vs_offset else ps_window[ps_offset:]
    last_vs = max((idx for idx, value in enumerate(vs_window) if value), default=None)
    if last_vs is None:
        vs_candidate = b""
    else:
        vs_candidate = vs_window[vs_offset:((last_vs + 16) // 16) * 16]

    slices = {
        "batch-8pages.bin": {
            "blob": batch,
            "source": "record+0x2A0..+0x829F (CaptureOutput+0x210, batch[8*4096])",
            "record_offset": 0x2A0,
            "size": 32768,
            "note": "8-page batch capture window; not a proven complete command stream.",
        },
        "shared-eu-window-2pages.bin": {
            "blob": vs_window,
            "source": "record+0x82A0..+0xA29F (CaptureOutput+0x8210, kernelVS[2*4096])",
            "record_offset": 0x82A0,
            "size": 8192,
            "note": "VS window. The PS window is byte-identical in this capture; "
                    "the name does not prove a shared physical page.",
        },
        "ps-from-entry-to-next-entry-candidate.bin": {
            "blob": ps_candidate,
            "source": f"PS window[{hex(ps_offset)}:{hex(vs_offset)}]",
            "record_offset": 0xA2A0 + ps_offset,
            "size": len(ps_candidate),
            "note": "Candidate only: bytes before the next known entry, not a proven PS kernel length.",
        },
        "vs-from-entry-to-last-nonzero-candidate.bin": {
            "blob": vs_candidate,
            "source": f"VS window[{hex(vs_offset)}:{hex(((last_vs + 16) // 16) * 16)}]",
            "record_offset": 0x82A0 + vs_offset,
            "size": len(vs_candidate),
            "note": "Candidate only: entry to 16-byte-aligned last nonzero byte, not a proven VS length.",
        },
    }

    batch_headers = []
    for kind, word, offset in EXPECTED_HEADERS:
        found = u32(batch, offset)
        batch_headers.append({
            "kind": kind,
            "batch_offset_dwords": offset // 4,
            "batch_offset": hex(offset),
            "gpu_va_candidate": hex(out["batchStart"] + offset),
            "expected_header": hex(word),
            "observed_header": hex(found),
            "match": found == word,
            "dword_length": (word & 0xFF) + 2,
        })
    if not all(h["match"] for h in batch_headers):
        raise SystemExit(f"batch header mismatch: {batch_headers}")

    result = {
        "format": {
            "name": "THAG v2 / GA3.2 HangRecord",
            "record_size": RECORD_SIZE_V2,
            "record_size_hex": hex(RECORD_SIZE_V2),
            "records_in_file": records_in_file,
            "trailing_bytes": size % RECORD_SIZE_V2,
            "max_records": MAX_RECORDS,
        },
        "capture": {
            "path": str(source),
            "size": size,
            "sha256": sha,
            "known_expected_size": KNOWN_CAPTURE_SIZE,
            "known_expected_sha256": KNOWN_CAPTURE_SHA256,
            "size_matches_known": size == KNOWN_CAPTURE_SIZE,
            "sha256_matches_known": sha == KNOWN_CAPTURE_SHA256,
        },
        "records": [],
        "success_record": i,
        "address_candidates": {
            "status": "CANDIDATE — pointer/register semantics deferred to the main agent's genxml audit",
            "bb_addr": hex(out["bbAddr"]),
            "pml4_candidate": hex(out["pml4"]),
            "batch_start": hex(out["batchStart"]),
            "instruction_base_candidate": hex(instr),
            "vs_offset_candidate": hex(vs_offset),
            "ps_offset_candidate": hex(ps_offset),
            "vs_entry_candidate": hex(vs_entry),
            "ps_entry_candidate": hex(ps_entry),
            "checks": address_checks,
        },
        "payload_counts": {
            "batch_pages": out["batchPages"],
            "batch_valid_mask": hex(out["batchValid"]),
            "batch_nonzero_bytes": nonzero(batch),
            "batch_nonzero_range": first_last_nonzero(batch),
            "vs_kernel_pages": out["kernelPages"][0],
            "vs_nonzero_bytes": nonzero(vs_window),
            "ps_kernel_pages": out["kernelPages"][1],
            "ps_nonzero_bytes": nonzero(ps_window),
            "vs_ps_windows_byte_identical": vs_window == ps_window,
            "vs_ps_first_page_byte_identical": vs_window[:4096] == ps_window[:4096],
            "readBytes_recorded": out["readBytes"],
            "table_reads_recorded": out["tableReads"],
            "data_page_reads_recorded": out["pageReads"],
        },
        "shared_physical_page": {
            "recorded_in_capture": True,
            "recorded_kernelPhys": [hex(out["kernelPhys"][0]), hex(out["kernelPhys"][1])],
            "recorded_same_physical_page": out["kernelPhys"][0] == out["kernelPhys"][1],
            "recorded_intra_page_delta": hex(abs(vs_entry - ps_entry)),
            "independently_proved_by_raw_pte_capture": False,
            "reason": "THAG stores driver-reported translations and read counters, not raw PTE bytes; "
                      "the same kernelPhys value is a recorded field, not an independent mapping proof.",
        },
        "entry_bytes": {
            "ps_32": ps_window[ps_offset:ps_offset + 32].hex(),
            "vs_32": vs_window[vs_offset:vs_offset + 32].hex(),
        },
        "batch_headers": batch_headers,
        "slices": {},
    }

    for rec_idx, decoded in enumerate(records):
        out_fields = decoded["out"]
        compact_out = {key: value for key, value in out_fields.items() if key != "scan"}
        compact_scan = dict(out_fields["scan"])
        compact = {
            "index": decoded["index_field"],
            "magic": decoded["magic"],
            "ms": decoded["ms"],
            "attempts": decoded["attempts"],
            "wakeDomain": decoded["wakeDomain"],
            "attemptReasons": decoded["attemptReasons"],
            "attemptReasonNames": decoded["attemptReasonNames"],
            "resolveDiag": hex(decoded["resolveDiag"]),
            "maxMem": decoded["maxMem"],
            "regs": decoded["regs"],
            "out": compact_out,
            "scan": compact_scan,
            "payload_nonzero_batch_vs_ps": [
                nonzero(data[rec_idx * RECORD_SIZE_V2 + 0x2A0:rec_idx * RECORD_SIZE_V2 + 0x82A0]),
                nonzero(data[rec_idx * RECORD_SIZE_V2 + 0x82A0:rec_idx * RECORD_SIZE_V2 + 0xA2A0]),
                nonzero(data[rec_idx * RECORD_SIZE_V2 + 0xA2A0:(rec_idx + 1) * RECORD_SIZE_V2]),
            ],
        }
        result["records"].append(compact)

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, info in slices.items():
        target = outdir / name
        if target.exists():
            if target.read_bytes() != info["blob"]:
                raise SystemExit(f"refusing to overwrite a different existing output: {target}")
        else:
            target.write_bytes(info["blob"])
        written[name] = {"size": len(info["blob"]), "sha256": sha256_bytes(info["blob"])}
    result["slices"] = {
        name: {
            "source": info["source"],
            "record_offset": hex(info["record_offset"]),
            "size": info["size"],
            "sha256": written[name]["sha256"],
            "note": info["note"],
        }
        for name, info in slices.items()
    }

    if zip_path:
        result["zip_audit"] = audit_zip(zip_path, slices, zip_json_path, result)

    json_path = outdir / "extraction.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in
                      ("format", "capture", "success_record", "payload_counts",
                       "shared_physical_page", "slices")}, ensure_ascii=False, indent=2))
    print(f"wrote {json_path}")
    return 0


def _safe_zip_entries(archive):
    entries = []
    for info in archive.infolist():
        name = info.filename
        mode = info.external_attr >> 16
        if name.startswith("/") or "\\" in name or "/../" in name or posixpath.normpath(name).startswith(".."):
            raise SystemExit(f"unsafe ZIP entry name: {name!r}")
        if stat.S_ISLNK(mode):
            raise SystemExit(f"symlink ZIP entry: {name!r}")
        if not (info.is_dir() or stat.S_ISREG(mode)):
            raise SystemExit(f"special ZIP entry: {name!r}")
        entries.append(info)
    return entries


def audit_zip(zip_path, slices, zip_json_path, result):
    audit = {
        "zip_path": str(zip_path),
        "zip_sha256": sha256_file(zip_path),
        "entry_count": 0,
        "uncompressed_bytes": 0,
        "safety": {},
        "entries": [],
        "script_review": {
            "executed": False,
            "reason": "ZIP script inspected statically; independent extractor re-derived every offset.",
        },
        "binary_comparisons": {},
        "json_comparison": {},
    }
    with zipfile.ZipFile(zip_path) as archive:
        entries = _safe_zip_entries(archive)
        if archive.testzip() is not None:
            raise SystemExit("ZIP CRC test failed")
        audit["entry_count"] = len(entries)
        audit["uncompressed_bytes"] = sum(i.file_size for i in entries)
        audit["safety"] = {
            "crc_test": "ok",
            "path_traversal": False,
            "absolute_paths": False,
            "symlinks": False,
            "special_files": False,
            "declared_uncompressed_bytes": audit["uncompressed_bytes"],
        }
        for info in entries:
            if info.is_dir():
                continue
            blob = archive.read(info)
            audit["entries"].append({
                "name": info.filename,
                "size": info.file_size,
                "crc32": f"{info.CRC:08x}",
                "sha256": sha256_bytes(blob),
                "compression": info.compress_type,
            })

        base = posixpath.commonpath([i.filename for i in entries if not i.is_dir()])
        for name, info in slices.items():
            members = [i.filename for i in entries
                       if i.filename == posixpath.join(base, name)]
            if len(members) != 1:
                audit["binary_comparisons"][name] = {"found": False}
                continue
            zip_blob = archive.read(members[0])
            audit["binary_comparisons"][name] = {
                "found": True,
                "zip_size": len(zip_blob),
                "slice_size": len(info["blob"]),
                "zip_sha256": sha256_bytes(zip_blob),
                "slice_sha256": sha256_bytes(info["blob"]),
                "byte_identical": zip_blob == info["blob"],
            }

        if zip_json_path:
            embedded_path = posixpath.join(base, "extraction.json")
            embedded = json.loads(archive.read(embedded_path))
            external = json.loads(Path(zip_json_path).read_text(encoding="utf-8"))
            audit["json_comparison"]["embedded_equals_external_copy"] = embedded == external
            audit["json_comparison"].update(compare_extraction_json(embedded, result))

    audit["all_binaries_byte_identical"] = all(
        item.get("byte_identical", False) for item in audit["binary_comparisons"].values())
    audit["all_discrepancies"] = audit["json_comparison"].get("discrepancies", [])
    return audit


def _cmp(path, expected, actual, discrepancies, matched):
    matched[0] += 1
    if expected != actual:
        discrepancies.append({"field": path, "zip_value": expected, "recomputed": actual})


def compare_extraction_json(zip_json, result):
    """Field-by-field audit of the ZIP's extraction.json against recomputation."""
    discrepancies = []
    matched = [0]
    rec = result["records"][result["success_record"]]
    out = rec["out"]
    payload = result["payload_counts"]

    def check(path, expected, actual):
        _cmp(path, expected, actual, discrepancies, matched)

    check("size", zip_json.get("size"), result["capture"]["size"])
    check("sha256", zip_json.get("sha256"), result["capture"]["sha256"])
    check("record_size", zip_json.get("record_size"), result["format"]["record_size"])
    check("success_record", zip_json.get("success_record"), result["success_record"])
    address_key_map = {
        "bb_addr": "bb_addr",
        "pml4_candidate": "pml4_candidate",
        "batch_start": "batch_start",
        "instruction_base": "instruction_base_candidate",
        "vs_offset": "vs_offset_candidate",
        "ps_offset": "ps_offset_candidate",
        "vs_entry": "vs_entry_candidate",
        "ps_entry": "ps_entry_candidate",
    }
    for zip_key, our_key in address_key_map.items():
        check(zip_key, zip_json.get(zip_key), result["address_candidates"][our_key])
    check("vs_ps_windows_identical", zip_json.get("vs_ps_windows_identical"),
          payload["vs_ps_windows_byte_identical"])
    check("vs_ps_first_page_same", zip_json.get("vs_ps_first_page_same"),
          payload["vs_ps_first_page_byte_identical"])
    check("entry_bytes", zip_json.get("entry_bytes"), result["entry_bytes"])
    check("batch_headers", zip_json.get("batch_headers"), [
        {"kind": h["kind"], "batch_offset": h["batch_offset"],
         "gpu_va": h["gpu_va_candidate"], "header": h["observed_header"],
         "dword_length": h["dword_length"]}
        for h in result["batch_headers"]
    ])
    check("files", zip_json.get("files"),
          {name: {"size": info["size"], "sha256": info["sha256"]}
           for name, info in result["slices"].items()})

    zip_records = {item.get("index"): item for item in zip_json.get("records", [])}
    for idx, decoded in enumerate(result["records"]):
        got = zip_records.get(idx)
        if got is None:
            discrepancies.append({"field": f"records[{idx}]", "zip_value": None, "recomputed": "present"})
            continue
        payload_idx = decoded["payload_nonzero_batch_vs_ps"]
        expected = {
            "index": decoded["index"],
            "result_code": decoded["out"]["result"],
            "attempt_reason": decoded["attemptReasons"][0],
            "wake_domain": decoded["wakeDomain"],
            "resolve_diag": decoded["resolveDiag"].lower(),
            "page_table_reads": decoded["out"]["tableReads"],
            "data_page_reads": decoded["out"]["pageReads"],
            "read_bytes": decoded["out"]["readBytes"],
            "batch_nonzero": payload_idx[0],
            "vs_window_nonzero": payload_idx[1],
            "ps_window_nonzero": payload_idx[2],
        }
        for key, value in expected.items():
            check(f"records[{idx}].{key}", got.get(key), value)

    # The only expected provenance difference is the ZIP author's local source path.
    source_value = zip_json.get("source")
    matched[0] += 1
    if not isinstance(source_value, str) or posixpath.basename(source_value) != posixpath.basename(result["capture"]["path"]):
        discrepancies.append({
            "field": "source",
            "zip_value": source_value,
            "recomputed": result["capture"]["path"],
            "kind": "provenance_path",
            "explanation": "ZIP records its author's local path; the basename matches and all bytes/hashes match.",
        })
    else:
        discrepancies.append({
            "field": "source",
            "zip_value": source_value,
            "recomputed": result["capture"]["path"],
            "kind": "provenance_path_only",
            "explanation": "Different absolute path with identical basename; no content discrepancy.",
        })

    return {
        "fields_checked": matched[0],
        "matching_fields": matched[0] - len(discrepancies),
        "discrepancies": discrepancies,
        "note": "Binary slices and hashes are compared byte-for-byte; JSON values are compared field-by-field.",
    }


def main():
    parser = argparse.ArgumentParser(description="Read-only THAG v2 capture extractor/auditor.")
    parser.add_argument("--capture", required=True, help="original .bin capture (read-only)")
    parser.add_argument("--outdir", required=True, help="new output directory")
    parser.add_argument("--zip", help="optional GA32b-offline-analysis.zip to audit")
    parser.add_argument("--zip-json", help="optional external copy of the ZIP extraction.json")
    args = parser.parse_args()
    return extract(args.capture, args.outdir, args.zip, args.zip_json)


if __name__ == "__main__":
    sys.exit(main())
