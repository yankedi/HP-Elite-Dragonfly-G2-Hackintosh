#!/usr/bin/env python3
"""
parse_thag.py (v3) — read-only decoder for the GA3.1 / GA3.2 "THAG" GPU-hang capture file.

Layout provenance: verified with clang `-fdump-record-layouts-complete` against the real
kern_igfx.hpp of both trees (GA31-hang/analysis/layout_dump.txt,
GA33-research/analysis/layout_dump_ga32.txt). Both trees lay out the record identically:

    struct IGFX::TigerLakeRegisterMap::HangRecord
       0 magic u32 | 4 index u32 | 8 ms u32 | 12 attempts u32 | 16 wakeDomain u32
      20 attemptReasons[8] | 52 regs[16] | 116 ggc | 120 dsmLo | 124 dsmHi
     128 pad(GA3.1)/resolveDiag(GA3.2) u32 | 136 maxMem u64 | 144 out (CaptureOutput)
    sizeof(HangRecord) = 144 + 49680 = 49824 = 0xC2A0

CaptureOutput (offsets relative to 144):
    result 0, fences 8..103, ramTop 96, bbAddr 104, pml4 112, batchStart 120,
    batchPhys[8] 128, batchValid 192, batchPages 196, tableReads 200, pageReads 204,
    readBytes 208, classifierReady 216, classifierProbeOk 220, classifierProbe1 224,
    bridgeValid 228, exclusionStolen/LowTop/Tseg 232/236/240, exclusionsVerified 244,
    bridgeRegs[4] 248, scan 264..503 (foundSba/Vs/Ps 264..266, sbaAt 272,
    instructionBase 280, kernelOffset 288, kernelAt 304, sbaCmd 320, kernelCmd 408),
    kernelPhys 504, kernelPages 520, batch 528 (8x4096), kernel 33296 (2x2x4096)
    total 49680.

Kernel data regions in record coordinates: batch 0x2A0, VS kernel 0x82A0, PS kernel 0xA2A0
(CaptureOutput+0x210 / +0x8210 / +0xA210).

The file is only read. All-zero payloads are reported as "no data", never as captured shaders.
"""

import argparse
import hashlib
import json
import struct
import sys

RECORD_SIZE_V2 = 0xC2A0  # GA3.1 / GA3.2 records (49,824 bytes)
RECORD_SIZE_V3 = 0xC2F8  # GA3.3 records (49,824 + 88 diagnostics)
RECORD_SIZE = RECORD_SIZE_V3  # kept for callers that expect a single constant
MAX_RECORDS = 3
MAGIC = 0x47414854
RECORD_VERSION_GA33 = 3
STAGE_NAMES = {0: "None", 1: "Classifier", 2: "Exclusions", 3: "Registers", 4: "Batch", 5: "Scan",
               6: "Kernel", 7: "Done"}

def decode_diag(d, base):
    """GA3.3 diagnostics appended after CaptureOutput (present only in v3 records)."""
    return {
        "version": u32(d, base + 0x00),
        "size": u32(d, base + 0x04),
        "stage": u32(d, base + 0x08),
        "stageName": STAGE_NAMES.get(u32(d, base + 0x08), "?"),
        "failReason": u32(d, base + 0x0C),
        "failReasonName": reason_name(u32(d, base + 0x0C)),
        "failLevel": u32(d, base + 0x10),
        "pmapChecked": u32(d, base + 0x14),
        "pmapAccepted": u32(d, base + 0x18),
        "pmapRejected": u32(d, base + 0x1C),
        "fenceRejected": u32(d, base + 0x20),
        "readAttempts": u32(d, base + 0x24),
        "readSuccesses": u32(d, base + 0x28),
        "batchBytes": u32(d, base + 0x2C),
        "vsBytes": u32(d, base + 0x30),
        "psBytes": u32(d, base + 0x34),
        "bridgeDiag": u32(d, base + 0x38),
        "failGpuVA": u64(d, base + 0x40),
        "failPhys": u64(d, base + 0x48),
        "failTable": u64(d, base + 0x50),
    }

def diag_fail_reason(diag):
    """Rejection source inferred from the counters when a refusal was attributed."""
    if diag["pmapRejected"]:
        return "pmap_valid_page refused (pmapRejected>0)"
    if diag["fenceRejected"]:
        return "extra fences refused (fenceRejected>0)"
    return "n/a"

REASONS = ["Ok", "RegsInvalid", "StolenUnknown", "AddrOutside", "LimitHit", "NotMapped",
           "ReadFailed", "Pml4Invalid", "NoBatch", "ScanIncomplete", "Disabled",
           "MemoryMapUnverified", "UnsafePhysicalRange", "WakesUnusable"]

# GA3.2 TglHang::packResolveDiag bit definitions (kern_tglhang.hpp)
RESOLVE_BITS = [
    (1 << 0, "maxMemResolved", "bit0: _max_mem symbol resolved"),
    (1 << 1, "pmapResolved", "bit1: _pmap_valid_page symbol resolved"),
    (1 << 2, "probeOk", "bit2: pmap_valid_page(0) reported invalid (probe accepted)"),
    (1 << 3, "uioFreeResolved", "bit3: _uio_free symbol resolved"),
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

# Intel Gen12 command headers the capture looks for (kern_tglhang.hpp scanBatch)
def scan_command_headers(batch_bytes):
    hits = []
    words = struct.unpack_from("<%dI" % (len(batch_bytes) // 4), batch_bytes)
    for i, w in enumerate(words):
        if w == 0x61010014:
            hits.append({"offset": i * 4, "value": hex(w), "kind": "STATE_BASE_ADDRESS"})
        elif w == 0x78100007:
            hits.append({"offset": i * 4, "value": hex(w), "kind": "3DSTATE_VS"})
        elif (w & 0xFFFFFF00) == 0x78200000:
            hits.append({"offset": i * 4, "value": hex(w), "kind": "3DSTATE_PS"})
    return hits

def u8(d, o):
    return d[o]

def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]

def u64(d, o):
    return struct.unpack_from("<Q", d, o)[0]

def reason_name(v):
    return REASONS[v] if 0 <= v < len(REASONS) else f"Unknown({v})"

def decode_resolve_diag(v):
    return {
        "raw": v,
        "bits": {name: bool(v & bit) for bit, name, _ in RESOLVE_BITS},
        "lastSolveSymbolError": (v >> 16) & 0xFF,
        "explanation": " | ".join(desc for bit, _, desc in RESOLVE_BITS if v & bit) or "none set",
    }

def decode_capture_output(d, base):
    o = {
        "result_raw": u32(d, base + 0x00),
        "result": reason_name(u32(d, base + 0x00)),
        "fences": {
            "haveStolen": u8(d, base + 0x08), "stolenBase": u64(d, base + 0x10), "stolenSize": u64(d, base + 0x18),
            "haveLowTop": u8(d, base + 0x20), "lowTop": u64(d, base + 0x28),
            "haveTseg": u8(d, base + 0x30), "tsegBase": u64(d, base + 0x38),
            "haveFirmwareFloor": u8(d, base + 0x40), "firmwareFloor": u64(d, base + 0x48),
            "haveMaxMem": u8(d, base + 0x50), "maxMem": u64(d, base + 0x58),
        },
        "ramTop": u64(d, base + 0x60),
        "bbAddr": u64(d, base + 0x68),
        "pml4": u64(d, base + 0x70),
        "batchStart": u64(d, base + 0x78),
        "batchPhys": [u64(d, base + 0x80 + 8 * i) for i in range(8)],
        "batchValid": u32(d, base + 0xC0),
        "batchValidPages": bin(u32(d, base + 0xC0)).count("1"),
        "batchPages": u32(d, base + 0xC4),
        "tableReads": u32(d, base + 0xC8),
        "pageReads": u32(d, base + 0xCC),
        "readBytes": u64(d, base + 0xD0),
        "classifierReady": u32(d, base + 0xD8),
        "classifierProbeOk": u32(d, base + 0xDC),
        "classifierProbe1": u32(d, base + 0xE0),
        "bridgeValid": u32(d, base + 0xE4),
        "exclusionStolen": u32(d, base + 0xE8),
        "exclusionLowTop": u32(d, base + 0xEC),
        "exclusionTseg": u32(d, base + 0xF0),
        "exclusionsVerified": u32(d, base + 0xF4),
        "bridgeRegs": {
            "TOLUD": u32(d, base + 0xF8 + 0), "TSEGMB": u32(d, base + 0xF8 + 4),
            "BDSM": u32(d, base + 0xF8 + 8), "BGSM": u32(d, base + 0xF8 + 12),
        },
        "scan": {
            "foundSba": u8(d, base + 0x108), "foundVs": u8(d, base + 0x109), "foundPs": u8(d, base + 0x10A),
            "sbaAt": u64(d, base + 0x110),
            "instructionBase": u64(d, base + 0x118),
            "kernelOffset": [u64(d, base + 0x120 + 8 * i) for i in range(2)],
            "kernelAt": [u64(d, base + 0x130 + 8 * i) for i in range(2)],
            "sbaCmdNonzero": sum(1 for i in range(22) if u32(d, base + 0x140 + 4 * i)),
            "kernelCmdNonzero": sum(1 for i in range(24) if u32(d, base + 0x198 + 4 * i)),
        },
        "kernelPhys": [u64(d, base + 0x1F8 + 8 * i) for i in range(2)],
        "kernelPages": [u32(d, base + 0x208 + 4 * i) for i in range(2)],
    }
    def nz(start, size):
        return sum(1 for i in range(start, start + size) if d[i] != 0)
    o["payload"] = {
        "batch_region": {"record_offset": hex(base + 0x210), "size": 8 * 4096, "nonzero_bytes": nz(base + 0x210, 8 * 4096),
                         "valid_bytes": min(o["batchPages"], 8) * 4096},
        "kernel_vs_region": {"record_offset": hex(base + 0x8210), "size": 2 * 4096, "nonzero_bytes": nz(base + 0x8210, 2 * 4096),
                             "valid_bytes": min(o["kernelPages"][0], 2) * 4096},
        "kernel_ps_region": {"record_offset": hex(base + 0xA210), "size": 2 * 4096, "nonzero_bytes": nz(base + 0xA210, 2 * 4096),
                             "valid_bytes": min(o["kernelPages"][1], 2) * 4096},
    }
    o["payload"]["batch_pages_nonzero"] = [nz(base + 0x210 + i * 4096, 4096) for i in range(8)]
    # Intel command headers in the batch region (only meaningful if batch bytes were captured)
    o["batch_command_headers"] = scan_command_headers(d[base + 0x210: base + 0x210 + 8 * 4096]) if o["payload"]["batch_region"]["valid_bytes"] else []
    return o

def infer_first_failure(rec):
    """Best-effort stage inference from recorded fields; returns stage + explanation + unknowns."""
    o = rec["out"]
    r = o["result_raw"]
    ev = o["exclusionsVerified"]
    notes = []
    if r == 0:
        return {"stage": "complete", "explanation": "result Ok; capture completed", "unknown": []}
    if r == 10:
        return {"stage": "disabled", "explanation": "feature off", "unknown": []}
    if r == 13:
        return {"stage": "0a-forcewake", "explanation": "only unusable SafeForceWake windows were seen", "unknown": []}
    if r == 11:
        which = "classifier missing" if not o["classifierReady"] else "probe rejected"
        return {"stage": "0a-classifier", "explanation": f"MemoryMapUnverified ({which})", "unknown": []}
    if r == 12:
        if not ev:
            missing = [k for k, v in (("stolen", o["exclusionStolen"]), ("lowTop", o["exclusionLowTop"]), ("tseg", o["exclusionTseg"])) if not v]
            return {"stage": "0b-exclusions", "explanation": f"exclusions not verified before any read; missing/refused fence(s): {', '.join(missing) or 'n/a'}", "unknown": []}
        if o["pml4"] == 0:
            notes.append("result 12 with exclusionsVerified but pml4==0: rejection before stage 1 recorded outputs")
        if o["batchPages"] == 0 and o["pageReads"] == 0:
            return {"stage": "1..3-first-page", "explanation": f"a page was refused before any data-page read (tableReads={o['tableReads']}); first refused page not recorded",
                    "unknown": ["which page (table level / GPU VA / physical page) was refused; add firstFailure* diagnostics"]}
        if o["batchPages"] > 0 and o["kernelPages"][0] + o["kernelPages"][1] == 0:
            return {"stage": "5-kernel-page", "explanation": "batch was captured but a shader kernel page was refused", "unknown": []}
        return {"stage": "later", "explanation": f"page refused after some progress (batchPages={o['batchPages']}, kernelPages={o['kernelPages']})", "unknown": []}
    if r == 7:
        return {"stage": "1-pml4", "explanation": "Pml4Invalid (bbAddr/pml4 sanity check)", "unknown": []}
    if r == 1:
        return {"stage": "1-regs", "explanation": "RegsInvalid (0xFFFFFFFF register read)", "unknown": []}
    if r == 8:
        return {"stage": "3-batch", "explanation": "NoBatch (no batch page mapped/read)", "unknown": []}
    if r == 9:
        return {"stage": "4-scan", "explanation": "ScanIncomplete (batch read but no SBA/VS/PS found)", "unknown": []}
    return {"stage": "unknown", "explanation": f"unmapped reason {r}", "unknown": []}

def decode_record(d, index, rec_size=RECORD_SIZE_V3):
    base = index * rec_size
    r = {
        "magic": hex(u32(d, base + 0x00)),
        "index": u32(d, base + 0x04),
        "ms": u32(d, base + 0x08),
        "attempts": u32(d, base + 0x0C),
        "wakeDomain": u32(d, base + 0x10),
        "attemptReasons": [u32(d, base + 0x14 + 4 * i) for i in range(8)],
        "regs": [u32(d, base + 0x34 + 4 * i) for i in range(16)],
        "ggc": u32(d, base + 0x74),
        "dsmLo": u32(d, base + 0x78),
        "dsmHi": u32(d, base + 0x7C),
        "resolveDiagOrPad": u32(d, base + 0x80),
        "maxMem": u64(d, base + 0x88),
    }
    r["mode"] = "GA3.2" if (r["resolveDiagOrPad"] or r["wakeDomain"]) else "GA3.1"
    r["styleNote"] = ("resolveDiag/wakeDomain populated -> GA3.2-style record" if r["mode"] == "GA3.2"
                      else "pad=0, wakeDomain=0 -> GA3.1-style record (resolveDiag field existed only as padding)")
    r["attemptReasonNames"] = [reason_name(v) for v in r["attemptReasons"]]
    r["attemptReasonsUsed"] = r["attemptReasons"][:r["attempts"]] if r["attempts"] <= 8 else r["attemptReasons"]
    r["attemptReasonNamesUsed"] = [reason_name(v) for v in r["attemptReasonsUsed"]]
    r["registers"] = [
        {"index": i, "offset": hex(0x34 + 4 * i), "address": hex(addr), "name": name, "value": r["regs"][i]}
        for i, (addr, name) in enumerate(HANG_REGS)
    ]
    r["dsmBase"] = (r["dsmHi"] << 32) | r["dsmLo"]
    r["resolveDiag"] = decode_resolve_diag(r["resolveDiagOrPad"])
    r["out"] = decode_capture_output(d, base + 0x90)
    if rec_size >= RECORD_SIZE_V3:
        r["diag"] = decode_diag(d, base + 0x90 + 0xC210)
        r["diag"]["rejectionSource"] = diag_fail_reason(r["diag"])
    r["metadata_nonzero_bytes"] = sum(1 for i in range(base, base + 0x90) if d[i] != 0)
    r["first_failure"] = infer_first_failure(r)
    return r

def main():
    ap = argparse.ArgumentParser(description="Decode GA3.1/GA3.2 THAG captures (read-only).")
    ap.add_argument("--file", required=True)
    ap.add_argument("--expect-sha", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    with open(args.file, "rb") as f:
        data = f.read()
    sha = hashlib.sha256(data).hexdigest()

    # GA3.3 files use the larger record; v2 files (GA3.1/GA3.2) the old one. Detect by validating
    # the magic at every record start for each candidate size (both are whole multiples for 1..3 records).
    rec_size = None
    for size in (RECORD_SIZE_V3, RECORD_SIZE_V2):
        if len(data) % size == 0:
            n = len(data) // size
            if 1 <= n <= MAX_RECORDS and all(u32(data, i * size) == MAGIC for i in range(n)):
                rec_size = size
                break
    report = {
        "file": args.file, "size": len(data), "sha256": sha,
        "expected_sha256": args.expect_sha,
        "sha_ok": (sha == args.expect_sha) if args.expect_sha else None,
        "format": ("GA3.3 (v3, 0x%X)" % rec_size) if rec_size == RECORD_SIZE_V3 else
                  (("GA3.1/GA3.2 (v2, 0x%X)" % rec_size) if rec_size else "unrecognised"),
        "record_size": rec_size, "records_in_file": (len(data) // rec_size) if rec_size else 0,
        "trailing_bytes": (len(data) % rec_size) if rec_size else len(data), "max_records": MAX_RECORDS,
    }
    ok = True
    if args.expect_sha and sha != args.expect_sha:
        report["error"] = "SHA-256 mismatch"; ok = False
    if len(data) == 0 or u32(data, 0) != MAGIC:
        report["error"] = "missing THAG magic"; ok = False
    elif rec_size is None:
        report["error"] = "file size does not match any known record layout (truncated or unknown version)"
        ok = False
    if ok and report["records_in_file"] > MAX_RECORDS:
        report["warning"] = f"more records than TglHang::MaxRecords ({MAX_RECORDS})"

    report["records"] = []
    if ok:
        for i in range(report["records_in_file"]):
            rec = decode_record(data, i, rec_size)
            if rec_size >= RECORD_SIZE_V3 and "diag" in rec:
                if rec["diag"]["version"] != RECORD_VERSION_GA33:
                    report["warning"] = f"record {i}: unexpected diagnostic version {rec['diag']['version']}"
                if rec["diag"]["size"] != rec_size:
                    report["warning"] = f"record {i}: diagnostic size field {rec['diag']['size']} != record size {rec_size}"
            if rec["magic"] != hex(MAGIC):
                report["error"] = f"record {i}: bad magic {rec['magic']}"; ok = False; break
            if rec["index"] != i:
                report["warning"] = f"record {i}: index field is {rec['index']}"
            report["records"].append(rec)
    report["ok"] = ok

    text = json.dumps(report, indent=2)
    if args.json:
        with open(args.json, "w") as f:
            f.write(text + "\n")
        print(f"wrote {args.json}")
    else:
        print(text)

    rs = report.get("record_size") or 0
    print(f"\nfile {args.file}\n  sha256 {sha} ({'ok' if report.get('sha_ok') is True else ('n/a' if report.get('sha_ok') is None else 'MISMATCH')})"
          f"  size {len(data)}  format {report.get('format')}  records {report['records_in_file']} x 0x{rs:X}")
    for rec in report["records"]:
        o = rec["out"]
        print(f"  record {rec['index']} [{rec['mode']}]: ms={rec['ms']} attempts={rec['attempts']} "
              f"wakeDomain={rec['wakeDomain']} reasons={rec['attemptReasonNamesUsed']}")
        print(f"    resolveDiag=0x{rec['resolveDiag']['raw']:X} bits={rec['resolveDiag']['bits']} lastErr={rec['resolveDiag']['lastSolveSymbolError']}")
        print(f"    out.result={o['result']} classifierReady={o['classifierReady']} probeOk={o['classifierProbeOk']} "
              f"bridgeValid={o['bridgeValid']} exclusionsVerified={o['exclusionsVerified']} "
              f"(stolen={o['exclusionStolen']} lowTop={o['exclusionLowTop']} tseg={o['exclusionTseg']})")
        print(f"    bbAddr={hex(o['bbAddr'])} pml4={hex(o['pml4'])} batchStart={hex(o['batchStart'])} "
              f"batchValid=0x{o['batchValid']:02X} batchPages={o['batchPages']} tableReads={o['tableReads']} "
              f"pageReads={o['pageReads']} readBytes={o['readBytes']}")
        print(f"    bridgeRegs={ {k: hex(v) for k, v in o['bridgeRegs'].items()} }")
        print(f"    payload nonzero batch/VS/PS = "
              f"{o['payload']['batch_region']['nonzero_bytes']}/{o['payload']['kernel_vs_region']['nonzero_bytes']}/"
              f"{o['payload']['kernel_ps_region']['nonzero_bytes']} ; valid bytes = "
              f"{o['payload']['batch_region']['valid_bytes']}/{o['payload']['kernel_vs_region']['valid_bytes']}/"
              f"{o['payload']['kernel_ps_region']['valid_bytes']}")
        if o["batch_command_headers"]:
            print(f"    batch command headers: {o['batch_command_headers'][:6]}")
        if "diag" in rec:
            dg = rec["diag"]
            print(f"    diag: stage={dg['stageName']} fail={dg['failReasonName']} level={dg['failLevel']} "
                  f"pmap={dg['pmapChecked']}/{dg['pmapAccepted']}/{dg['pmapRejected']} fence={dg['fenceRejected']} "
                  f"reads={dg['readAttempts']}/{dg['readSuccesses']} bytes={dg['batchBytes']}/{dg['vsBytes']}/{dg['psBytes']}")
            if dg["failPhys"] or dg["failGpuVA"]:
                print(f"      first refusal: gpuVA={hex(dg['failGpuVA'])} phys={hex(dg['failPhys'])} table={hex(dg['failTable'])} [{dg['rejectionSource']}]")
        print(f"    first failure: {rec['first_failure']['stage']} — {rec['first_failure']['explanation']}")
        for u in rec["first_failure"]["unknown"]:
            print(f"      unknown: {u}")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
