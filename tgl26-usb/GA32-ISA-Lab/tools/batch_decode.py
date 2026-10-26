#!/usr/bin/env python3
"""Bounded, CPU-only, read-only generic GPU batch command-stream decoder.

Project: GA32-ISA-Lab (HP Elite Dragonfly G2 / Tiger Lake GPU hang forensics).

Scope and hard limits
---------------------
* This tool is a *decoder*, not an emulator.  It never claims that a decoded
  instruction was executed, that a chain was entered at its first offset, or
  that any address is physically mapped.
* The input file (raw THAG capture, or an extracted batch window) is opened
  strictly read-only; the tool only ever writes the requested JSON report.
* The pinned Mesa 23.3.6 genxml definitions are consumed through Mesa's own
  ``intel_genxml.GenXml`` importer (import resolution + engine filtering).
  The Mesa source clone is never modified (bytecode writing is disabled).

Recognition model
-----------------
* A candidate instruction is recognised from the *fixed default bits* declared
  in the genxml instruction header (``default=`` attributes), together with the
  structural ``mbo``/``mbz`` constants.  The ``DWord Length`` field is excluded
  from the fixed mask because it is the variable length.
* The declared length is ``DWordLength_field + bias``; it is validated against
  the instruction's genxml ``length`` attribute when one is present.
* Address/offset bitfields are decoded with their low-zero-bit alignment:
  ``align = start % 32``; an ``address`` field stores ``addr >> align`` and an
  ``offset`` field stores a byte offset ``off >> align`` (a relative offset that
  is made absolute only when a documented base is known).

Two outputs are deliberately kept separate:
1. ``header_scan``  - every aligned dword that *looks like* an instruction
   header (candidates only, not a chain; false positives are expected).
2. ``chains``       - sequential decoding of bounded runs that start at a
   non-NOOP candidate and terminate at MI_BATCH_BUFFER_END, a nested
   MI_BATCH_BUFFER_START, an unknown/invalid/truncated dword, or the window
   edge.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import struct
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Never write .pyc into the pinned Mesa source clone.
sys.dont_write_bytecode = True

SCHEMA_VERSION = 1
TOOL_NAME = "GA32-ISA-Lab/batch_decode.py"

# 48-bit GPU virtual address space on Gen12/TGL.
MAX_GPU_VA = (1 << 48) - 1
# Header dwords are compared as one little-endian integer.
MAX_INSN_DWORDS = 512

DEFAULT_RECORD = 1
DEFAULT_RECORD_OFFSET = 0xC2A0
DEFAULT_BATCH_OFFSET = 0x2A0
DEFAULT_BATCH_SIZE = 32768
DEFAULT_GPU_BASE = 0x426F7000
DEFAULT_BB_ADDR = 0x426FE104
DEFAULT_ANCHORS = {"sba": 0x69F8, "ps": 0x6B6C, "vs": 0x6C00}
MESA_COMMIT = "863338275d915e867319c3690ffd3272b06303c3"

GEN_FILES = {"gen11": "gen11.xml", "gen12": "gen12.xml"}


def _norm_name(name: str) -> str:
    return "".join(name.lower().split())


def len_field_of(el) -> Optional[Tuple[int, int]]:
    for f in el.findall("field"):
        if _norm_name(f.attrib.get("name", "")) == "dwordlength":
            return (int(f.attrib["start"]), int(f.attrib["end"]))
    return None


def bit_mask(start: int, end: int) -> int:
    return ((1 << (end - start + 1)) - 1) << start


def read_bits(buf: bytes, byte_off: int, start: int, end: int) -> Optional[int]:
    """Little-endian bitfield [start, end] (inclusive) of the dword stream."""
    nbytes = (end // 32 + 1) * 4
    if byte_off < 0 or byte_off + nbytes > len(buf):
        return None
    value = int.from_bytes(buf[byte_off:byte_off + nbytes], "little")
    return (value >> start) & ((1 << (end - start + 1)) - 1)


def read_dword(buf: bytes, byte_off: int) -> Optional[int]:
    if byte_off + 4 > len(buf):
        return None
    return struct.unpack_from("<I", buf, byte_off)[0]


@dataclasses.dataclass
class FieldDef:
    name: str
    start: int
    end: int
    type: str
    default: Optional[int]
    enum: Dict[int, str]


@dataclasses.dataclass
class GroupDef:
    start: int
    count: int
    size: int
    fields: List[FieldDef]


@dataclasses.dataclass
class InstrDef:
    name: str
    bias: int
    xml_length: Optional[int]
    engine: str
    len_field: Optional[Tuple[int, int]]
    dflt_mask: int
    dflt_value: int
    struct_mask: int
    struct_value: int
    fixed_maxbit: int
    fields: List[FieldDef]
    groups: List[GroupDef]

    def declared_length(self, dw0: int) -> int:
        if self.len_field is None:
            return self.bias
        start, end = self.len_field
        raw = (dw0 >> start) & ((1 << (end - start + 1)) - 1)
        return raw + self.bias


def _field_enum(f) -> Dict[int, str]:
    enum: Dict[int, str] = {}
    for v in f.findall("value"):
        try:
            enum[int(v.attrib["value"], 0)] = v.attrib["name"]
        except (KeyError, ValueError):
            continue
    return enum


def _parse_fields(container) -> Tuple[List[FieldDef], List[GroupDef]]:
    fields: List[FieldDef] = []
    groups: List[GroupDef] = []
    for child in container:
        if child.tag == "field":
            fields.append(
                FieldDef(
                    name=child.attrib.get("name", ""),
                    start=int(child.attrib["start"]),
                    end=int(child.attrib["end"]),
                    type=child.attrib.get("type", "uint"),
                    default=int(child.attrib["default"], 0)
                    if "default" in child.attrib
                    else None,
                    enum=_field_enum(child),
                )
            )
        elif child.tag == "group":
            gfields, _ = _parse_fields(child)
            groups.append(
                GroupDef(
                    start=int(child.attrib["start"]),
                    count=int(child.attrib["count"]),
                    size=int(child.attrib["size"]),
                    fields=gfields,
                )
            )
    return fields, groups


class GenModel:
    """Resolved instruction set for one genxml file."""

    def __init__(self, gen_name: str, genxml_dir: Path, engine: str = "render"):
        sys.path.insert(0, str(genxml_dir))
        import intel_genxml  # type: ignore
        importlib_path = genxml_dir / GEN_FILES[gen_name]
        self.gen_name = gen_name
        self.xml_path = importlib_path
        self.engine = engine
        genxml = intel_genxml.GenXml(str(importlib_path))
        genxml.merge_imported()
        genxml.filter_engines({engine})
        self.defs: List[InstrDef] = []
        self.by_name: Dict[str, InstrDef] = {}
        for el in genxml.et.getroot():
            if el.tag != "instruction":
                continue
            fields, groups = _parse_fields(el)
            len_field = len_field_of(el)
            dflt_mask = dflt_value = 0
            struct_mask = struct_value = 0
            fixed_maxbit = -1
            for f in fields:
                if (f.start, f.end) == len_field:
                    continue
                mask = bit_mask(f.start, f.end)
                if f.default is not None:
                    dflt_mask |= mask
                    dflt_value |= (f.default << f.start) & mask
                    fixed_maxbit = max(fixed_maxbit, f.end)
                if f.type == "mbo":
                    struct_mask |= mask
                    struct_value |= mask
                    fixed_maxbit = max(fixed_maxbit, f.end)
                elif f.type == "mbz":
                    struct_mask |= mask
                    fixed_maxbit = max(fixed_maxbit, f.end)
            xml_length = int(el.attrib["length"]) if "length" in el.attrib else None
            d = InstrDef(
                name=el.attrib["name"],
                bias=int(el.attrib.get("bias", 1)),
                xml_length=xml_length,
                engine=el.attrib.get("engine", ""),
                len_field=len_field,
                dflt_mask=dflt_mask,
                dflt_value=dflt_value,
                struct_mask=struct_mask,
                struct_value=struct_value,
                fixed_maxbit=fixed_maxbit,
                fields=fields,
                groups=groups,
            )
            self.defs.append(d)
            self.by_name[d.name] = d

    def find(self, name: str) -> Optional[InstrDef]:
        return self.by_name.get(name)


def match_candidate(d: InstrDef, buf: bytes, off: int, dw0: int) -> Optional[Dict[str, Any]]:
    """Return a candidate record if the dword at ``off`` matches ``d``.

    The returned dict distinguishes default-bit recognition from structural
    and length validation so the caller can report *why* a candidate was
    rejected instead of silently inventing an instruction.
    """
    decl = d.declared_length(dw0)
    if decl <= 0 or decl > MAX_INSN_DWORDS:
        return None
    # Cheap prune on the first dword before reading the whole instruction.
    dflt_lo = d.dflt_mask & 0xFFFFFFFF
    if (dw0 & dflt_lo) != (d.dflt_value & dflt_lo):
        return None
    if off + decl * 4 > len(buf):
        return {"name": d.name, "declared": decl, "status": "truncated"}
    raw = int.from_bytes(buf[off:off + decl * 4], "little")
    if (raw & d.dflt_mask) != d.dflt_value:
        return None
    structural_ok = (raw & d.struct_mask) == d.struct_value
    if d.fixed_maxbit >= decl * 32:
        structural_ok = False
    # ``DWordLength + bias`` is authoritative for walking the stream.  The XML
    # ``length`` attribute is a fixed-size model; some encodings (e.g.
    # 3DPRIMITIVE with extended parameters, dynamic groups) legitimately declare
    # more dwords than the modelled length.  Declaring *fewer* dwords than the
    # fixed XML length, however, means the header cannot describe the fixed
    # instruction and must not be walked.
    declared_shorter = d.xml_length is not None and decl < d.xml_length
    xml_length_match = d.xml_length is None or decl == d.xml_length
    valid = structural_ok and not declared_shorter
    if declared_shorter:
        note = "declared DWordLength+bias is shorter than the XML fixed length (invalid)"
    elif not xml_length_match:
        note = "bounded declared-length walk only; longer fixed command is NOT validated as a legal extension"
    else:
        note = None
    return {
        "name": d.name,
        "declared": decl,
        "xml_length": d.xml_length,
        "default_ok": True,
        "structural_ok": structural_ok,
        "xml_length_match": xml_length_match,
        "length_semantics_validated": xml_length_match,
        "declared_shorter_than_xml": declared_shorter,
        "valid": valid,
        "note": note,
        "specificity": bin(d.dflt_mask).count("1") + bin(d.struct_mask).count("1"),
    }


def candidates_at(gen: GenModel, buf: bytes, off: int) -> List[Dict[str, Any]]:
    dw0 = read_dword(buf, off)
    if dw0 is None:
        return []
    out: List[Dict[str, Any]] = []
    for d in gen.defs:
        c = match_candidate(d, buf, off, dw0)
        if c is not None:
            out.append(c)
    return out


def pick_valid(cands: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    valid = [c for c in cands if c.get("valid")]
    if not valid:
        return None
    valid.sort(key=lambda c: (not c.get("xml_length_match", True), -c["specificity"], c["name"]))
    return valid[0]


# --------------------------------------------------------------------------
# Field decoding
# --------------------------------------------------------------------------

def _decode_field(f: FieldDef, buf: bytes, off: int, decl: int,
                  instruction_base: Optional[int]) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "name": f.name,
        "start": f.start,
        "end": f.end,
        "type": f.type,
    }
    if off + (f.end // 32 + 1) * 4 > off + decl * 4:
        rec["present"] = False
        rec["status"] = "beyond_declared_length"
        return rec
    raw = read_bits(buf, off, f.start, f.end)
    if raw is None:
        rec["present"] = False
        rec["status"] = "outside_window"
        return rec
    rec["present"] = True
    rec["raw"] = raw
    rec["raw_hex"] = "0x%x" % raw
    align = f.start % 32
    if f.type == "address":
        value = raw << align
        rec["alignment_bits"] = align
        rec["value"] = value
        rec["value_hex"] = "0x%x" % value
        rec["overflow"] = value > MAX_GPU_VA
    elif f.type == "offset":
        value = raw << align
        rec["alignment_bits"] = align
        rec["byte_offset"] = value
        rec["byte_offset_hex"] = "0x%x" % value
        if instruction_base is not None:
            rec["absolute_va"] = instruction_base + value
            rec["absolute_va_hex"] = "0x%x" % (instruction_base + value)
        rec["overflow"] = value > MAX_GPU_VA
    elif f.type == "bool":
        rec["value"] = bool(raw)
    elif f.type == "int":
        width = f.end - f.start + 1
        sign = raw & (1 << (width - 1))
        rec["value"] = raw - (1 << width) if sign else raw
    elif f.type in ("uint", "mbo", "mbz"):
        rec["value"] = raw
        if f.type == "mbo":
            rec["constraint"] = "must_be_ones"
            rec["constraint_ok"] = raw == (1 << (f.end - f.start + 1)) - 1
        elif f.type == "mbz":
            rec["constraint"] = "must_be_zero"
            rec["constraint_ok"] = raw == 0
    else:
        rec["value"] = raw
        rec["type_unhandled"] = f.type
        rec["note"] = "type not specially decoded; raw value preserved"
    if f.enum and "value" in rec:
        try:
            rec["enum_name"] = f.enum.get(int(rec["value"]))
        except (TypeError, ValueError):
            pass
    return rec


def decode_instruction(gen: GenModel, buf: bytes, off: int,
                       instruction_base: Optional[int] = None) -> Dict[str, Any]:
    cands = candidates_at(gen, buf, off)
    picked = pick_valid(cands)
    entry: Dict[str, Any] = {
        "offset": off,
        "offset_hex": "0x%x" % off,
    }
    if picked is None:
        dw0 = read_dword(buf, off)
        entry["status"] = "no_valid_instruction"
        entry["raw_dword"] = dw0
        entry["raw_dword_hex"] = "0x%x" % dw0 if dw0 is not None else None
        entry["candidates"] = cands
        return entry
    d = gen.find(picked["name"])
    assert d is not None
    decl = picked["declared"]
    raw_dwords = [read_dword(buf, off + 4 * i) for i in range(decl)]
    entry.update(
        {
            "status": "ok",
            "name": d.name,
            "declared_length": decl,
            "xml_length": d.xml_length,
            "length_semantics_validated": picked.get("length_semantics_validated", False),
            "validation_level": "xml_fields_and_length" if picked.get("length_semantics_validated") else "bounded_length_walk_only",
            "raw_dwords": raw_dwords,
            "raw_dwords_hex": ["0x%x" % v for v in raw_dwords],
            "candidates": cands,
            "fields": [
                _decode_field(f, buf, off, decl, instruction_base) for f in d.fields
            ],
            "groups": _decode_groups(d, buf, off, decl),
        }
    )
    return entry


def _decode_groups(d: InstrDef, buf: bytes, off: int, decl: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for g in d.groups:
        rec: Dict[str, Any] = {
            "start": g.start,
            "size": g.size,
            "count": g.count,
            "fields": [f.name for f in g.fields],
        }
        if g.size <= 0:
            rec["status"] = "unsupported_zero_size"
        elif g.count == 0:
            rec["status"] = "unsupported_dynamic_count"
            rec["note"] = "dynamic group: entry count must come from the command; not invented"
        else:
            available = max(0, (decl * 32 - g.start) // g.size)
            rec["entries_present_in_declared_length"] = min(g.count, available)
            if any(f.type not in ("uint", "int", "bool", "address", "offset", "mbo", "mbz")
                   for f in g.fields):
                rec["status"] = "unsupported_struct_type"
            else:
                rec["status"] = "decoded"
                entries = []
                for i in range(min(g.count, available)):
                    entries.append([
                        _decode_field(dataclasses.replace(f, start=f.start+g.start+i*g.size,
                                                         end=f.end+g.start+i*g.size),
                                      buf, off, decl, None) for f in g.fields
                    ])
                rec["entries"] = entries
        raw_start = off + (g.start // 32) * 4
        raw_end = min(len(buf), off + max(decl * 4, (g.start // 32 + 1) * 4))
        rec["raw_dwords_hex"] = [
            "0x%x" % struct.unpack_from("<I", buf, p)[0]
            for p in range(raw_start, raw_end, 4)
            if p + 4 <= len(buf)
        ]
        out.append(rec)
    return out


# --------------------------------------------------------------------------
# Sequential chain decoding
# --------------------------------------------------------------------------

def simulate_chain(gen: GenModel, buf: bytes, start: int,
                   max_steps: int = MAX_INSN_DWORDS) -> Dict[str, Any]:
    off = start
    instructions: List[Dict[str, Any]] = []
    reason = "window_end"
    detail: Dict[str, Any] = {}
    while off + 4 <= len(buf) and len(instructions) < max_steps:
        cands = candidates_at(gen, buf, off)
        picked = pick_valid(cands)
        if picked is None:
            dw0 = read_dword(buf, off)
            reason = "unknown"
            for c in cands:
                if c.get("status") == "truncated":
                    reason = "truncated"
                    break
                if not c.get("structural_ok", True):
                    reason = "structural_mismatch"
                elif c.get("declared_shorter_than_xml"):
                    reason = "invalid_length"
            detail = {
                "offset": off,
                "offset_hex": "0x%x" % off,
                "raw_dword": dw0,
                "raw_dword_hex": "0x%x" % dw0 if dw0 is not None else None,
                "candidates": cands,
            }
            instructions.append(
                {
                    "offset": off,
                    "offset_hex": "0x%x" % off,
                    "status": "stop",
                    "reason": reason,
                    **{k: v for k, v in detail.items() if k not in ("offset",)},
                }
            )
            break
        entry = decode_instruction(gen, buf, off)
        instructions.append(entry)
        name = entry["name"]
        decl = entry["declared_length"]
        if name == "MI_BATCH_BUFFER_END":
            reason = "mi_end"
            detail = {"mi_end_offset": off}
            break
        if name == "MI_BATCH_BUFFER_START":
            target = None
            for f in entry["fields"]:
                if f.get("name") == "Batch Buffer Start Address":
                    target = f.get("value")
            reason = "mi_bb_start"
            detail = {"target_va": target, "target_va_hex": "0x%x" % target if target is not None else None}
            break
        off += decl * 4
    else:
        if off + 4 > len(buf):
            reason = "window_end"
            detail = {"offset": off, "offset_hex": "0x%x" % off}
    return {
        "start": start,
        "start_hex": "0x%x" % start,
        "instructions": instructions,
        "instruction_count": len([i for i in instructions if i.get("status") == "ok"]),
        "decoded_dwords": sum(i.get("declared_length", 0) for i in instructions if i.get("status") == "ok"),
        "stop_reason": reason,
        "stop_detail": detail,
        "end_offset": off if instructions and instructions[-1].get("status") == "ok" else start,
    }


def annotate_chain(chain: Dict[str, Any], gpu_base: int, size: int,
                   anchors: Dict[str, int],
                   entry_offset: Optional[int] = None) -> Dict[str, Any]:
    ok = [i for i in chain["instructions"] if i.get("status") == "ok"]
    first = ok[0] if ok else None
    chain["starts_with_mi_noop"] = bool(first and first.get("name") == "MI_NOOP")
    chain["contains_anchors"] = {
        k: any(i.get("offset") == v for i in ok) for k, v in anchors.items()
    }
    chain["entry_provenance_level"] = (
        "external_ring_mi_bb_start_target"
        if entry_offset is not None and chain["start"] == entry_offset
        else "header_scan_candidate"
    )
    chain["mi_noop_count"] = sum(1 for i in ok if i.get("name") == "MI_NOOP")
    chain["mi_noop_zero_dword_count"] = sum(
        1 for i in ok
        if i.get("name") == "MI_NOOP" and all(d == 0 for d in (i.get("raw_dwords") or [1]))
    )
    chain["zero_dword_ambiguity"] = (
        "all-zero dwords decode as MI_NOOP (opcode 0); a run of them is preserved but may be padding"
    )
    for i in ok:
        i["gpu_va"] = gpu_base + i["offset"]
        i["gpu_va_hex"] = "0x%x" % i["gpu_va"]
    for i in chain["instructions"]:
        i["gpu_va"] = gpu_base + i["offset"]
        i["gpu_va_hex"] = "0x%x" % i["gpu_va"]
    last = chain["instructions"][-1] if chain["instructions"] else None
    chain["terminal_offset"] = last["offset"] if last else None
    chain["terminal_gpu_va_hex"] = "0x%x" % (gpu_base + last["offset"]) if last else None
    chain["window_end_offset"] = gpu_base + size
    if chain["stop_reason"] == "mi_bb_start":
        target = chain.get("stop_detail", {}).get("target_va")
        if target is None:
            chain["nested_target_status"] = "unknown_target"
        elif gpu_base <= target < gpu_base + size:
            chain["nested_target_status"] = "in_window_not_followed"
        else:
            chain["nested_target_status"] = "out_of_window_unresolved"
    return chain


def chain_from_candidates(gen: GenModel, buf: bytes, gpu_base: int,
                          starts: Iterable[int], anchors: Dict[str, int],
                          size: int, limit: int = 24,
                          entry_offset: Optional[int] = None) -> List[Dict[str, Any]]:
    """Simulate a chain from each candidate start; return the most useful ones."""
    results: List[Dict[str, Any]] = []
    for start in sorted(set(starts)):
        chain = simulate_chain(gen, buf, start)
        annotate_chain(chain, gpu_base, size, anchors, entry_offset)
        chain["anchors_ok"] = all(chain["contains_anchors"].values())
        results.append(chain)
    chosen = None
    # External ring provenance wins over the heuristic "longest chain": the
    # captured RCS ring contains an MI_BATCH_BUFFER_START whose target lands on
    # this window offset, so decoding may legitimately start there.
    if entry_offset is not None:
        chosen = next((c for c in results if c["start"] == entry_offset), None)
    if chosen is None:
        # primary: non-NOOP start, anchored, terminates at MI_END, longest.
        primary = [
            c for c in results
            if not c["starts_with_mi_noop"] and c["anchors_ok"] and c["stop_reason"] == "mi_end"
        ]
        primary.sort(key=lambda c: (-c["instruction_count"], c["start"]))
        chosen = primary[0] if primary else None
    if chosen is None:
        alt = [c for c in results if not c["starts_with_mi_noop"]]
        alt.sort(key=lambda c: (-c["instruction_count"], c["start"]))
        chosen = alt[0] if alt else None
    # Keep the chosen chain plus anchor chains and a few longest alternatives.
    keep: List[Dict[str, Any]] = []
    if chosen is not None:
        keep.append(chosen)
    for a in anchors.values():
        cand = next((c for c in results if c["start"] == a), None)
        if cand is not None and cand is not chosen:
            keep.append(cand)
    rest = [c for c in results if c not in keep]
    rest.sort(key=lambda c: (-c["instruction_count"], c["start"]))
    keep.extend(rest[:max(0, limit - len(keep))])
    # Keep the full per-instruction decode only for the primary chain; the rest
    # are retained as scalar summaries to bound the JSON size.
    for idx, c in enumerate(keep):
        if idx == 0:
            continue
        first = c.get("instructions", [{}])[0] if c.get("instructions") else {}
        c["first_instruction"] = {
            "offset_hex": first.get("offset_hex"),
            "name": first.get("name"),
            "status": first.get("status"),
        }
        c.pop("instructions", None)
    return keep


# --------------------------------------------------------------------------
# Header scan
# --------------------------------------------------------------------------

def header_scan(gen: GenModel, buf: bytes, gpu_base: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for off in range(0, len(buf) - 3, 4):
        dw0 = read_dword(buf, off)
        if dw0 == 0:
            continue  # all-zero dwords are ambiguous MI_NOOP padding; skipped, see caveats
        cands = candidates_at(gen, buf, off)
        if not cands:
            continue
        picked = pick_valid(cands)
        out.append(
            {
                "offset": off,
                "offset_hex": "0x%x" % off,
                "gpu_va": gpu_base + off,
                "gpu_va_hex": "0x%x" % (gpu_base + off),
                "raw_dword_hex": "0x%x" % dw0,
                "candidates": cands,
                "selected": picked["name"] if picked else None,
                "valid": picked is not None,
                "note": "header-scan candidate only; not a chain and not evidence of execution",
            }
        )
    return out


# --------------------------------------------------------------------------
# XML verification
# --------------------------------------------------------------------------

def field_signature(f: FieldDef) -> Tuple[str, int, int, str, Optional[int]]:
    return (f.name, f.start, f.end, f.type, f.default)


def verify_xml(gen11: GenModel, gen12: GenModel) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "mesa_commit": MESA_COMMIT,
        "requested_fields": {
            "STATE_BASE_ADDRESS.Instruction Base Address": {"start": 332, "end": 383, "type": "address"},
            "3DSTATE_VS.Kernel Start Pointer": {"start": 38, "end": 95, "type": "offset"},
            "3DSTATE_PS.Kernel Start Pointer 0": {"start": 38, "end": 95, "type": "offset"},
        },
        "per_gen": {},
    }
    for gen in (gen11, gen12):
        per: Dict[str, Any] = {}
        for name in ("STATE_BASE_ADDRESS", "3DSTATE_VS", "3DSTATE_PS"):
            d = gen.find(name)
            if d is None:
                per[name] = {"present": False}
                continue
            per[name] = {
                "present": True,
                "bias": d.bias,
                "length": d.xml_length,
                "fields": [
                    {"name": f.name, "start": f.start, "end": f.end, "type": f.type,
                     "default": f.default, "alignment_bits": f.start % 32}
                    for f in d.fields
                ],
            }
        out["per_gen"][gen.gen_name] = per
    # field-level differences for the three anchor instructions
    diffs: Dict[str, Any] = {}
    for name in ("STATE_BASE_ADDRESS", "3DSTATE_VS", "3DSTATE_PS"):
        a, b = gen11.find(name), gen12.find(name)
        if a is None or b is None:
            diffs[name] = "present_in_only_one_gen"
            continue
        sa = {field_signature(f) for f in a.fields}
        sb = {field_signature(f) for f in b.fields}
        diffs[name] = {
            "identical": sa == sb and a.xml_length == b.xml_length and a.bias == b.bias,
            "only_gen11": sorted(x[0] for x in (sa - sb)),
            "only_gen12": sorted(x[0] for x in (sb - sa)),
            "length_gen11": a.xml_length,
            "length_gen12": b.xml_length,
        }
    out["anchor_field_differences"] = diffs
    na = {d.name for d in gen11.defs}
    nb = {d.name for d in gen12.defs}
    out["instruction_sets"] = {
        "gen11_count": len(na),
        "gen12_count": len(nb),
        "only_gen12": sorted(nb - na),
        "only_gen11": sorted(na - nb),
    }
    st11 = gen11.find("3DSTATE_STENCIL_BUFFER")
    st12 = gen12.find("3DSTATE_STENCIL_BUFFER")
    out["example_gen12_difference"] = {
        "instruction": "3DSTATE_STENCIL_BUFFER",
        "gen11_length": st11.xml_length if st11 else None,
        "gen11_source": "imported (gen8.xml) via gen11.xml",
        "gen12_length": st12.xml_length if st12 else None,
        "effect": (
            "the captured stream at offset 0x6AB0 declares total length 5; it satisfies the "
            "gen11 import but not the gen12 override (length 8). The captured encoding therefore "
            "matches the gen11 model; this decoder does not claim which encoding the hardware consumed."
        ),
    }
    return out


# --------------------------------------------------------------------------
# Pipeline state
# --------------------------------------------------------------------------

def decode_pipeline_state(gen: GenModel, buf: bytes, gpu_base: int,
                          anchors: Dict[str, int]) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "gen": gen.gen_name,
        "anchors": {k: {"offset": v, "offset_hex": "0x%x" % v,
                        "gpu_va_hex": "0x%x" % (gpu_base + v)} for k, v in anchors.items()},
        "instructions": {},
        "missing": [],
    }
    sba = decode_instruction(gen, buf, anchors["sba"])
    state["instructions"]["STATE_BASE_ADDRESS"] = sba
    instruction_base = None
    if sba.get("status") == "ok":
        for f in sba["fields"]:
            if f.get("name") == "Instruction Base Address" and "value" in f:
                instruction_base = f["value"]
    state["instruction_base_address"] = instruction_base
    state["instruction_base_address_hex"] = "0x%x" % instruction_base if instruction_base is not None else None
    for key, name in (("vs", "3DSTATE_VS"), ("ps", "3DSTATE_PS")):
        entry = decode_instruction(gen, buf, anchors[key], instruction_base)
        state["instructions"][name] = entry
        if entry.get("status") != "ok":
            state["missing"].append({"instruction": name, "offset": anchors[key],
                                     "status": entry.get("status")})
    # summarise kernel pointers explicitly
    kernel_pointers = []
    for inst_name in ("3DSTATE_VS", "3DSTATE_PS"):
        entry = state["instructions"].get(inst_name, {})
        for f in entry.get("fields", []) if entry.get("status") == "ok" else []:
            if "Kernel Start Pointer" in f.get("name", ""):
                kernel_pointers.append(
                    {
                        "instruction": inst_name,
                        "field": f["name"],
                        "raw": f.get("raw"),
                        "alignment_bits": f.get("alignment_bits"),
                        "byte_offset": f.get("byte_offset"),
                        "byte_offset_hex": f.get("byte_offset_hex"),
                        "absolute_va": f.get("absolute_va"),
                        "absolute_va_hex": f.get("absolute_va_hex"),
                        "overflow": f.get("overflow"),
                    }
                )
    state["kernel_pointers"] = kernel_pointers
    state["caveats"] = [
        "kernel start pointers are decoded as Instruction Base Address + byte offset; this is a "
        "decoder derivation from the XML offset semantics, not proof of execution",
        "a zero kernel pointer means the captured command carried zero there; it is reported as "
        "present-and-zero, not silently dropped",
        "physical mapping 0x3E9026000 (from capture metadata) is not independently proven by a PTE log "
        "and is not used by this decoder",
    ]
    return state


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_batch(args) -> Tuple[bytes, Dict[str, Any]]:
    if args.batch_bin:
        p = Path(args.batch_bin)
        data = p.read_bytes()
        meta = {
            "source_kind": "extracted_batch_window",
            "path": str(p),
            "size": len(data),
            "sha256": sha256_bytes(data),
        }
        return data, meta
    p = Path(args.thag)
    raw = p.read_bytes()
    start = args.record * args.record_size + args.batch_offset
    end = start + args.batch_size
    if end > len(raw):
        raise SystemExit(f"batch window {start:#x}..{end:#x} exceeds {p} ({len(raw)} bytes)")
    data = raw[start:end]
    meta = {
        "source_kind": "raw_thag_readonly",
        "path": str(p),
        "file_size": len(raw),
        "file_sha256": sha256_bytes(raw),
        "record_index": args.record,
        "record_size": args.record_size,
        "record_offset": args.record * args.record_size,
        "batch_offset_in_record": args.batch_offset,
        "batch_file_offset": start,
        "batch_size": args.batch_size,
        "batch_sha256": sha256_bytes(data),
        "read_only": True,
    }
    return data, meta


def words_to_bytes(words: Sequence[int]) -> bytes:
    return b"".join(struct.pack("<I", int(w) & 0xFFFFFFFF) for w in words)


def load_entry_evidence(path: Optional[str], gen: GenModel, gpu_base: int,
                        size: int, prefer_substr: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Read the main agent's RCS ring evidence JSON (read-only).

    The RCS ring dump from the real gpuRestart contains an MI_BATCH_BUFFER_START
    whose target lands inside the captured batch window.  That gives the chain
    entry an *external* provenance level instead of a header-scan guess.  The
    raw ring dwords are independently re-decoded here with the same genxml model
    rather than trusting the pre-decoded fields.
    """
    if not path:
        return None
    p = Path(path)
    out: Dict[str, Any] = {"source": str(p), "source_exists": p.exists()}
    if not p.exists():
        out["selected"] = None
        out["entry_offset"] = None
        out["evidence_level"] = "header_scan_candidate"
        out["note"] = "entry evidence not present; chain entry falls back to header-scan candidate level"
        return out
    try:
        records = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        out["error"] = str(exc)
        out["selected"] = None
        out["entry_offset"] = None
        out["evidence_level"] = "header_scan_candidate"
        return out
    considered: List[Dict[str, Any]] = []
    matches: List[Dict[str, Any]] = []
    for r in records if isinstance(records, list) else []:
        for bs in (r.get("ring_batch_starts") or []):
            raw = bs.get("raw") or []
            offset = bs.get("offset")
            pre = (bs.get("fields") or {}).get("Batch Buffer Start Address")
            entry: Dict[str, Any] = {
                "record_path": r.get("path"),
                "record_sha256": r.get("sha256"),
                "stage": r.get("stage"),
                "context_id": r.get("context_id"),
                "ring_start": r.get("RING_START"),
                "ring_head": r.get("RING_HEAD"),
                "bb_addr": r.get("BB_ADDR"),
                "ring_offset": offset,
                "ring_offset_hex": "0x%x" % offset if offset is not None else None,
                "presupplied_target_va": pre,
                "raw_dwords_hex": ["0x%x" % (w & 0xFFFFFFFF) for w in raw],
            }
            target = pre
            if len(raw) >= 3:
                buf = words_to_bytes(raw)
                dec = decode_instruction(gen, buf, 0)
                fields = {f["name"]: f for f in dec.get("fields", [])}
                tb = fields.get("Batch Buffer Start Address", {})
                if dec.get("status") == "ok" and tb.get("value") is not None:
                    target = tb["value"]
                entry["independent_redecode"] = {
                    "name": dec.get("name"),
                    "status": dec.get("status"),
                    "declared_length": dec.get("declared_length"),
                    "target_va": tb.get("value"),
                    "target_va_hex": tb.get("value_hex"),
                    "address_space_indicator": fields.get("Address Space Indicator", {}).get("value"),
                    "second_level_batch_buffer": fields.get("Second Level Batch Buffer", {}).get("value"),
                    "predication_enable": fields.get("Predication Enable", {}).get("value"),
                }
            entry["target_va"] = target
            entry["target_va_hex"] = "0x%x" % target if target is not None else None
            if target is not None and gpu_base <= target < gpu_base + size:
                entry["window_offset"] = target - gpu_base
                entry["window_offset_hex"] = "0x%x" % (target - gpu_base)
                entry["gpu_va_hex"] = "0x%x" % target
                matches.append(entry)
            considered.append(entry)
    out["records_considered"] = considered
    out["match_count"] = len(matches)
    selected = None
    if matches:
        if prefer_substr:
            for m in matches:
                if prefer_substr in (m.get("record_path") or ""):
                    selected = m
                    break
        if selected is None:
            selected = matches[0]
    out["selected"] = selected
    if selected is not None:
        out["entry_offset"] = selected["window_offset"]
        out["entry_offset_hex"] = selected["window_offset_hex"]
        out["evidence_level"] = "external_ring_mi_bb_start_target"
        out["interpretation"] = (
            "The captured RCS ring contains an MI_BATCH_BUFFER_START whose decoded PPGTT target VA "
            "maps into this batch window at the entry offset. Decoding may start there; this still does "
            "not prove that any instruction retired or that the whole chain executed."
        )
    else:
        out["entry_offset"] = None
        out["evidence_level"] = "header_scan_candidate"
    out["not_claimed"] = [
        "GPU shader retirement",
        "execution past the external entry offset",
        "that the chain start is the batch submission start",
        "that the recorded BB_ADDR is the submission start",
    ]
    return out


def build_report(args: Dict[str, Any]) -> Dict[str, Any]:
    genxml_dir = Path(args.genxml_dir).resolve()
    buf, input_meta = load_batch(args)
    models = {g: GenModel(g, genxml_dir) for g in GEN_FILES}
    gen11, gen12 = models["gen11"], models["gen12"]
    gpu_base = args.gpu_base
    anchors = dict(DEFAULT_ANCHORS)

    entry_provenance = load_entry_evidence(
        getattr(args, "entry_evidence", None), gen11, gpu_base,
        args.batch_size, getattr(args, "entry_record", None),
    )
    entry_offset = entry_provenance.get("entry_offset") if entry_provenance else None

    per_gen: Dict[str, Any] = {}
    for gname, gen in models.items():
        scan = header_scan(gen, buf, gpu_base)
        starts = [c["offset"] for c in scan if c["selected"]]
        chains = chain_from_candidates(gen, buf, gpu_base, starts, anchors,
                                       args.batch_size, limit=args.chain_limit,
                                       entry_offset=entry_offset)
        primary = chains[0] if chains else None
        per_gen[gname] = {
            "instruction_defs": len(gen.defs),
            "header_scan": scan,
            "chains": chains,
            "primary_chain_start": primary["start"] if primary else None,
            "primary_chain_count": primary["instruction_count"] if primary else None,
            "primary_stop_reason": primary["stop_reason"] if primary else None,
            "entry_offset_used": entry_offset,
        }

    def reaches_end(name: str) -> bool:
        c = per_gen[name]["chains"][0] if per_gen[name]["chains"] else None
        return bool(c and c["stop_reason"] == "mi_end" and c["anchors_ok"])

    if args.gen == "auto":
        if reaches_end("gen12") and not reaches_end("gen11"):
            primary_gen = "gen12"
        elif reaches_end("gen11") and not reaches_end("gen12"):
            primary_gen = "gen11"
        else:
            counts = {g: (per_gen[g]["primary_chain_count"] or 0) for g in per_gen}
            primary_gen = max(counts, key=lambda g: (counts[g], g))
    else:
        primary_gen = args.gen
    pipeline_state = decode_pipeline_state(models[primary_gen], buf, gpu_base, anchors)

    report: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "scope": "bounded CPU-only generic batch decoder; no execution claim",
        "input": input_meta,
        "gpu_base": gpu_base,
        "gpu_base_hex": "0x%x" % gpu_base,
        "recorded_bb_addr": args.bb_addr,
        "recorded_bb_addr_hex": "0x%x" % args.bb_addr,
        "recorded_bb_addr_offset_in_window": args.bb_addr - gpu_base,
        "known_anchor_offsets": {k: {"offset": v, "hex": "0x%x" % v} for k, v in anchors.items()},
        "genxml": {
            "mesa_commit": MESA_COMMIT,
            "dir": str(genxml_dir),
            "resolver": "mesa intel_genxml.GenXml (merge_imported + filter_engines render)",
            "engine": "render",
        },
        "recognition": {
            "method": "fixed XML header default bits (+ mbo/mbz structural bits); DWord Length excluded",
            "length_validation": "declared_length = DWordLength + bias; declared < XML fixed length is invalid and stops the chain; declared > XML length is allowed for extended/dynamic encodings and flagged xml_length_match=false",
            "declared_length_cap_dwords": MAX_INSN_DWORDS,
            "address_alignment": "address byte_value = field_raw << (start % 32); offset byte_offset = field_raw << (start % 32)",
            "max_gpu_va": MAX_GPU_VA,
            "max_gpu_va_hex": "0x%x" % MAX_GPU_VA,
        },
        "xml_verification": verify_xml(gen11, gen12),
        "per_gen": per_gen,
        "primary_gen": primary_gen,
        "entry_provenance": entry_provenance,
        "pipeline_state": pipeline_state,
        "caveats": [
            "Header-scan candidates are NOT a chain and NOT evidence of execution; a candidate can be an operand dword.",
            "Sequential decoding produces a bounded chain inside the captured 32 KiB window only.",
            "When entry_provenance.evidence_level is external_ring_mi_bb_start_target, the chain entry offset is the target of an MI_BATCH_BUFFER_START decoded from the captured RCS ring; this justifies starting the decode there but still does NOT prove shader retirement or full execution.",
            "The recorded BB_ADDR is the current batch pointer, not the submission start; it decodes to window offset 0x7104, one dword after the MI_BATCH_BUFFER_END found at 0x7100 when the gen11 model is used.",
            "MI_BATCH_BUFFER_START targets inside the batch window are never followed recursively; out-of-window targets are reported unresolved.",
            "Dynamic/large groups are marked unsupported rather than invented.",
            "The capture window may be truncated at either end; unknown dwords are preserved with their raw value.",
            "Physical mapping 0x3E9026000 is capture metadata only; there is no independent PTE log in this analysis.",
            "gen11 and gen12 genxml disagree on some instruction lengths (e.g. 3DSTATE_STENCIL_BUFFER 5 vs 8); both chains are reported.",
        ],
    }
    return report


def write_json(report: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")


def print_summary(report: Dict[str, Any]) -> None:
    pg = report["per_gen"]
    ep = report.get("entry_provenance") or {}
    print("input: %s" % report["input"]["path"])
    if ep.get("selected"):
        sel = ep["selected"]
        print("entry: ring offset %s -> target %s -> window offset %s (%s)" % (
            sel.get("ring_offset_hex"), sel.get("target_va_hex"),
            sel.get("window_offset_hex"), ep.get("evidence_level")))
    else:
        print("entry: no external ring provenance (%s)" % ep.get("note", "none"))
    print("primary gen: %s" % report["primary_gen"])
    for g, d in pg.items():
        ch = d["chains"][0] if d["chains"] else None
        if ch:
            print("  %s: chain %s -> %s, %d instructions, stop=%s, anchors=%s" % (
                g, ch["start_hex"], hex(ch["terminal_offset"]),
                ch["instruction_count"], ch["stop_reason"], ch["contains_anchors"]))
        print("  %s: header-scan candidates=%d" % (g, len(d["header_scan"])))


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    lab_root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--thag", help="raw THAG capture (read-only)")
    src.add_argument("--batch-bin", help="pre-extracted 32 KiB batch window (read-only)")
    p.add_argument("--record", type=int, default=DEFAULT_RECORD)
    p.add_argument("--record-size", type=lambda x: int(x, 0), default=DEFAULT_RECORD_OFFSET)
    p.add_argument("--batch-offset", type=lambda x: int(x, 0), default=DEFAULT_BATCH_OFFSET)
    p.add_argument("--batch-size", type=lambda x: int(x, 0), default=DEFAULT_BATCH_SIZE)
    p.add_argument("--gpu-base", type=lambda x: int(x, 0), default=DEFAULT_GPU_BASE)
    p.add_argument("--bb-addr", type=lambda x: int(x, 0), default=DEFAULT_BB_ADDR)
    p.add_argument("--genxml-dir", default=str(lab_root / "tools/mesa-eu/source/src/intel/genxml"))
    p.add_argument("--entry-evidence", default=str(lab_root / "analysis/rcs-evidence.json"),
                   help="main agent's RCS ring evidence JSON used for chain entry provenance")
    p.add_argument("--entry-record", default="Kernel_2026-10-18-040341_host.gpuRestart",
                   help="preferred gpuRestart record path substring for entry selection")
    p.add_argument("--gen", choices=("auto", "gen11", "gen12"), default="auto")
    p.add_argument("--chain-limit", type=int, default=24)
    p.add_argument("--json", default=str(lab_root / "analysis/batch-decoded.json"))
    p.add_argument("--summary-only", action="store_true")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    report = build_report(args)
    if not args.summary_only:
        write_json(report, Path(args.json))
        print("wrote %s" % args.json)
    print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
