"""GA3.9 track D: independent source->target per-field message contracts.

Standalone, dependency-free (stdlib only) comparator for the frozen GA3.8
Gen11 source and Gen12 candidate message IR.  For every aligned source/target
SEND pair it emits one *per-field contract* row that separates:

  * encoding provenance  -- which bit range / carrier the value was decoded from
                            and whether that decode relation is proven;
  * semantic state       -- whether the *meaning* of the field is proven across
                            generations (KNOWN / CONDITIONAL / UNKNOWN);
  * equivalence enum     -- FIELD_EQUIVALENCE_PROVEN / FIELD_EQUIVALENCE_CONDITIONAL /
                            FIELD_DIFFERENCE_CONFIRMED / FIELD_SEMANTICS_UNKNOWN;
  * raw identity         -- source/target raw bytes, program SHA-256 and offsets;
  * symbolic externals   -- resource heaps, thread payload ABI and completion
                            events, which are never resolved from these bytes.

Hard invariant: an identical descriptor DWORD (``sameDWORD``) is recorded only
as ``SAME_DWORD_ENCODING_ONLY`` with ``semantic_state = UNKNOWN``.  This module
never maps a shared DWORD to semantic equivalence.

Repair-001 (2026-10-20) changes driven by the independent initial audit:
  * semantic state is capped by encoding state; UNKNOWN encoding can never be
    CONDITIONAL/KNOWN (FM-P5, FM-P15);
  * ``None == None`` is no longer an encoding equality (FM-P6);
  * payload1_grf_length shares exDesc[9:6] with extended_mlen and is therefore
    CONDITIONAL, not KNOWN (FM-P7);
  * the ORDINAL fallback is removed; shifted layouts need an explicit,
    hash-bound witness and are otherwise left unpaired (FM-P9b);
  * target-only messages are preserved as UNPAIRED_TARGET rows (FM-P10);
  * response_is_null, absent scalars and missing facts stay UNKNOWN, never
    KNOWN (FM-P13, FM-P14);
  * every contract carries raw source/target bytes, program SHA-256 and offsets
    (FM-P8); cross-family pairs expose an explicit ``family_mismatch`` flag and
    mismatched bit layouts are never compared like-for-like (FM-P12).

Scope discipline (GA3.9, track D):
  * Not the translator; imports no translator policy and no GA3.8 code.
  * Encoding legality (IGA decoded) is not hardware semantics.
  * Field-level equality is reported as equality of the pinned encoding, with
    the semantic verdict kept separate and conservatively UNKNOWN where the
    PRM/IGA evidence is conditional (Gen12 exDesc low nibble U5, RC descriptor
    structure U7, EML width narrow rule, TS_EOT conflict U3/W2).

Rule ids referenced (GA3.8 `reference/rules/RULES.json`): D1/D2 descriptor
common fields, X1/X2/extended descriptor, E1/E2/E3 EOT, M1/M2/M3/M4/M5
sampler/RT/URB field maps and SFID numeric mapping, U3/U5/U6/U7 unknowns.

Public API
----------
    field_contracts(source_messages, target_messages, source_ir=None,
                    target_ir=None, witness=None) -> dict
        source_messages / target_messages : GA3.8 message IR dict(s) (a single
            program, a bundle ``{"programs":[...]}`` or a list).
        source_ir / target_ir            : optional GA3.8 node IR dict(s) used to
            anchor each message to a decoded instruction range.
        witness                          : optional explicit layout witness for
            shifted layouts.  Must be hash-bound, e.g.
            ``{"source_program_sha256": "...", "target_program_sha256": "...",
               "entries": [{"shader_id": "PS0", "source_offset": 80,
                            "target_offset": 80}]}``.
        Returns ``{"schema_version", "invariant", "pairs":[...], "summary":{...}}``
        with one per-field contract per paired SEND plus an UNPAIRED* row for
        every preserved message (ten paired rows for the four frozen programs).

    contract_for_pair(source_msg, target_msg, source_node=None, target_node=None) -> dict

CLI
---
    python3 -B field_mapping.py \
        --source-messages SRC.json_or_dir --target-messages TGT.json_or_dir \
        [--source-ir ...] [--target-ir ...] [--witness WITNESS.json] [--out OUT.json]
    Directories are scanned for ``*-source.json`` / ``*-candidate.json``.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

SCHEMA_VERSION = 2
KNOWN = "KNOWN"
CONDITIONAL = "CONDITIONAL"
UNKNOWN = "UNKNOWN"
MISSING = "MISSING"

EQUIV_PROVEN = "FIELD_EQUIVALENCE_PROVEN"
EQUIV_CONDITIONAL = "FIELD_EQUIVALENCE_CONDITIONAL"
DIFFERENCE_CONFIRMED = "FIELD_DIFFERENCE_CONFIRMED"
SEMANTICS_UNKNOWN = "FIELD_SEMANTICS_UNKNOWN"

INVARIANT = "an identical descriptor DWORD is encoding evidence only; it is never mapped to semantic equivalence"

#: family-specific descriptor fields: family -> [(name, high, low, rule, semantic)]
FAMILY_FIELDS = {
    "SAMPLER": [
        ("binding_table_index", 7, 0, "SAMPLER-BTI", KNOWN),
        ("sampler_index", 11, 8, "SAMPLER-INDEX", KNOWN),
        ("message_type", 16, 12, "SAMPLER-MESSAGE-TYPE", CONDITIONAL),
        ("simd_mode_low", 18, 17, "SAMPLER-SIMD", KNOWN),
        ("simd_mode_high", 29, 29, "SAMPLER-SIMD", KNOWN),
        ("return_format", 30, 30, "SAMPLER-RETURN-FORMAT", KNOWN),
    ],
    "RENDER_TARGET": [
        ("binding_table_index", 7, 0, "RT-BTI", KNOWN),
        ("message_control", 13, 8, "RT-MESSAGE-CONTROL", KNOWN),
        ("message_type", 17, 14, "RT-MESSAGE-TYPE", CONDITIONAL),
        ("per_sample", 13, 13, "RT-PER-SAMPLE", KNOWN),
        ("last_render_target", 12, 12, "RT-LAST-TARGET", KNOWN),
        ("slot_group", 11, 11, "RT-SLOT-GROUP", KNOWN),
        ("subtype_simd_control", 10, 8, "RT-SUBTYPE", KNOWN),
    ],
    "URB": [
        ("urb_opcode", 3, 0, "URB-OPCODE", KNOWN),
        ("global_offset_encoded", 14, 4, "URB-GLOBAL-OFFSET", KNOWN),
        ("per_slot_offset", 17, 17, "URB-PER-SLOT", KNOWN),
        ("channel_mask_present", 15, 15, "URB-CHANNEL-MASK", KNOWN),
    ],
}

#: render-target fields whose *encoded index* is proven by Vol2a MSD_RTW +
#: Mesa brw_fb_desc, while full RC message semantics remain U7/UNKNOWN.
RT_ENCODED_FIELDS = {
    "binding_table_index", "message_control", "last_render_target",
    "slot_group", "subtype_simd_control", "per_sample", "message_type",
}

#: top-level field order for the emitted contract rows.
FIELD_ORDER = [
    "family", "opcode_form", "sfid",
    "descriptor_dword", "extended_descriptor_dword",
    "header_present", "message_length_mlen", "response_length_rlen",
    "extended_mlen", "extended_function_control", "eot",
    "execution_size",
    "payload0_grf_length", "payload1_grf_length", "response_grf_length",
    "response_is_null",
]


class MappingError(ValueError):
    """Raised when a supplied object is not a recognised GA3.8 message IR."""


def _bits(value, high, low):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise MappingError("value out of 32-bit range: %r" % (value,))
    if not 0 <= low <= high <= 31:
        raise MappingError("bad bit range: %r" % ((high, low),))
    return (value >> low) & ((1 << (high - low + 1)) - 1)


def _fact(fact):
    """Return (state, value); a bare/missing value is never KNOWN."""
    if isinstance(fact, dict) and "state" in fact:
        return (fact.get("state") or UNKNOWN), fact.get("value")
    if fact is None:
        return MISSING, None
    return KNOWN, fact


def _int_fact(fact, max_value):
    """Validate a numeric fact: KNOWN requires a bounded real int (bool excluded).

    A contradictory ``state=KNOWN, value=null`` (or bool/out-of-range) is
    downgraded to UNKNOWN instead of raising or defaulting to 0.
    """
    if not isinstance(fact, dict):
        return MISSING, None
    state, value = fact.get("state"), fact.get("value")
    if state == KNOWN and type(value) is int and not isinstance(value, bool) \
            and 0 <= value <= max_value:
        return KNOWN, value
    if state == KNOWN:
        return UNKNOWN, None
    return (state if state in {CONDITIONAL, UNKNOWN} else UNKNOWN), None


#: Field-specific length bounds, verified against D1/D2/X1 before tightening:
#:   RLEN desc[24:20] is 5 bits but D2 limits valid values to 0..16;
#:   MLEN desc[28:25] and EML exDesc[9:6] are both 4-bit fields (0..15).
#:   payload0_grf uses MLEN, payload1_grf uses EML, response_grf uses RLEN.
LENGTH_BOUNDS = {"response_grf": 16, "payload0_grf": 15, "payload1_grf": 15}


def _length_fact(container, key):
    return _int_fact((container or {}).get(key), LENGTH_BOUNDS.get(key, 15))


def _u32_fact(fact):
    return _int_fact(fact, 0xFFFFFFFF)


def _iter_program_dicts(obj):
    if obj is None:
        return
    if isinstance(obj, list):
        for item in obj:
            yield from _iter_program_dicts(item)
        return
    if not isinstance(obj, dict):
        raise MappingError("unsupported container: %r" % (type(obj),))
    if "programs" in obj and isinstance(obj["programs"], list):
        for item in obj["programs"]:
            yield from _iter_program_dicts(item)
        return
    if "messages" in obj and isinstance(obj["messages"], list):
        yield obj
        return
    raise MappingError("dict has no 'messages' list")


def _ir_nodes_by_program(ir):
    """{shader_id: {offset: node}} for a node IR (programs have 'nodes')."""
    out = {}
    if ir is None:
        return out
    items = ir if isinstance(ir, list) else ([ir] if isinstance(ir, dict) else [])
    flat = []
    for item in items:
        if isinstance(item, dict) and "programs" in item:
            flat.extend(item["programs"])
        else:
            flat.append(item)
    for prog in flat:
        if not isinstance(prog, dict) or "nodes" not in prog:
            continue
        out[prog.get("shader_id")] = {n.get("byte_range", [None])[0]: n for n in prog["nodes"]}
    return out


def _sfid_pair(msg, side):
    """Return (value, state, bits, carrier, rule)."""
    ex_state, ex = _u32_fact(msg.get("extended_descriptor"))
    if side == "source":
        if ex_state != KNOWN:
            return None, UNKNOWN, [3, 0], "exDesc[3:0]", "SEND-SFID-GEN11"
        return _bits(ex, 3, 0), KNOWN, [3, 0], "exDesc[3:0]", "SEND-SFID-GEN11"
    raw = msg.get("raw_hex")
    if isinstance(raw, str) and len(raw) >= 24:
        try:
            return (int.from_bytes(bytes.fromhex(raw), "little") >> 92) & 15, KNOWN, [95, 92], "instruction[95:92]", "SEND-SFID-GEN12"
        except ValueError:
            pass
    st, sf = _fact(msg.get("sfid"))
    return sf, st, [95, 92], "instruction[95:92]", "SEND-SFID-GEN12"


def _eot_pair(msg, side):
    if side == "source":
        st, ex = _u32_fact(msg.get("extended_descriptor"))
        if st != KNOWN:
            return None, UNKNOWN, [5, 5], "exDesc[5]", "SEND-EOT-GEN11"
        return _bits(ex, 5, 5), KNOWN, [5, 5], "exDesc[5]", "SEND-EOT-GEN11"
    return int(bool(msg.get("eot"))), KNOWN, None, "instruction EOT option", "SEND-EOT-GEN12"


def _valid_grf_destination(dst):
    """Validate a decoded SEND destination.

    A known non-null destination must be a structured GRF reference: ``rn`` is
    ``r`` (with optional ``r``/``sr``; omitting ``r`` means 0, as IGA prints it)
    or ``null``.  Malformed/unknown ``kind``/``len``/``reg``/``rn``/types are
    UNKNOWN, never a known non-null destination (O6).
    """
    if not isinstance(dst, dict):
        return False
    if dst.get("kind") not in (None, "DA"):
        return False
    length = dst.get("len")
    if length is not None and (type(length) is not int or isinstance(length, bool)
                               or not 0 <= length <= 31):
        return False
    reg = dst.get("reg")
    if not isinstance(reg, dict):
        return False
    rn = reg.get("rn")
    if rn not in {"r", "null"}:
        return False
    if rn == "r":
        r = reg.get("r", 0)  # IGA omits r for register 0
        if type(r) is not int or isinstance(r, bool) or not 0 <= r < 256:
            return False
        sr = reg.get("sr", 0)
        if type(sr) is not int or isinstance(sr, bool) or not 0 <= sr < 256:
            return False
    return True


def _response_destination(msg):
    dst = (msg or {}).get("response_destination")
    if not isinstance(dst, dict):
        return MISSING, None
    state = dst.get("state")
    if state is None:
        # GA3.8 stores the decoded destination object without a state field.
        state = KNOWN
    if state != KNOWN:
        return state or UNKNOWN, None
    if not _valid_grf_destination(dst):
        return UNKNOWN, None
    return KNOWN, dst


def extract_fields(msg, side, node=None):
    """Decode the pinned fields of one message record into a name->entry map.

    Missing facts are ``MISSING``/``UNKNOWN`` with value ``None``; they are never
    stamped KNOWN.  Each entry carries the source/target raw bytes and the
    program SHA-256 so a contract can be re-checked without the input JSON.
    """
    fields = {}
    desc_state, desc = _u32_fact(msg.get("descriptor"))
    ex_state, ex = _u32_fact(msg.get("extended_descriptor"))
    desc_known, ex_known = desc_state == KNOWN, ex_state == KNOWN
    raw_hex = msg.get("raw_hex")
    program_sha = msg.get("program_sha256")

    def put(name, value, state, bits_range, carrier, rule, semantic):
        fields[name] = {
            "bits": bits_range,
            "value": value,
            "state": state if value is not None else UNKNOWN,
            "carrier": carrier,
            "rule": rule,
            "semantic": semantic,
            "raw_hex": raw_hex,
            "program_sha256": program_sha,
        }

    family_value = msg.get("family")
    family_present = isinstance(family_value, str) and bool(family_value)
    fields["family"] = {"bits": None, "value": family_value if family_present else None,
                        "state": KNOWN if family_present else UNKNOWN,
                        "carrier": "SFID/opcode classification", "rule": "M4",
                        "semantic": CONDITIONAL, "raw_hex": raw_hex,
                        "program_sha256": program_sha}
    op_value = msg.get("opcode_form")
    op_present = isinstance(op_value, str) and bool(op_value)
    fields["opcode_form"] = {"bits": None, "value": op_value if op_present else None,
                             "state": KNOWN if op_present else UNKNOWN,
                             "carrier": "%s split/native form" % side,
                             "rule": "OPCODE-CORRESPONDENCE",
                             "semantic": CONDITIONAL, "raw_hex": raw_hex,
                             "program_sha256": program_sha}
    sfid, sfid_state, sfid_bits, sfid_carrier, sfid_rule = _sfid_pair(msg, side)
    fields["sfid"] = {"bits": sfid_bits, "value": sfid, "state": sfid_state,
                      "carrier": sfid_carrier, "rule": sfid_rule, "semantic": KNOWN,
                      "raw_hex": raw_hex, "program_sha256": program_sha}

    def desc_field(name, high, low, rule, semantic, max_value=None):
        if not desc_known:
            put(name, None, UNKNOWN, [high, low], "desc", rule, semantic)
        else:
            value = _bits(desc, high, low)
            if max_value is not None and value > max_value:
                put(name, None, UNKNOWN, [high, low], "desc", rule, semantic)
                fields[name]["invalid_encoding"] = True
            else:
                put(name, value, KNOWN, [high, low], "desc", rule, semantic)

    def ex_field(name, high, low, rule, semantic, max_value=None):
        if not ex_known:
            put(name, None, UNKNOWN, [high, low], "exDesc", rule, semantic)
        else:
            value = _bits(ex, high, low)
            if max_value is not None and value > max_value:
                put(name, None, UNKNOWN, [high, low], "exDesc", rule, semantic)
                fields[name]["invalid_encoding"] = True
            else:
                put(name, value, KNOWN, [high, low], "exDesc", rule, semantic)

    fields["descriptor_dword"] = {"bits": None, "value": desc, "state": desc_state,
                                  "carrier": "desc", "rule": "D1", "semantic": UNKNOWN,
                                  "raw_hex": raw_hex, "program_sha256": program_sha}
    fields["extended_descriptor_dword"] = {"bits": None, "value": ex, "state": ex_state,
                                           "carrier": "exDesc", "rule": "X1", "semantic": UNKNOWN,
                                           "raw_hex": raw_hex, "program_sha256": program_sha}
    desc_field("header_present", 19, 19, "SEND-COMMON-HEADER", KNOWN)
    desc_field("message_length_mlen", 28, 25, "SEND-COMMON-MLEN", KNOWN, max_value=15)
    desc_field("response_length_rlen", 24, 20, "SEND-COMMON-RLEN", KNOWN, max_value=16)
    ex_field("extended_mlen", 9, 6, "SEND-EX-MLEN", CONDITIONAL, max_value=15)
    ex_field("extended_function_control", 31, 12, "SEND-EX-FUNCTION-CONTROL", UNKNOWN)
    eot_val, eot_state, eot_bits, eot_carrier, eot_rule = _eot_pair(msg, side)
    fields["eot"] = {"bits": eot_bits, "value": eot_val, "state": eot_state,
                     "carrier": eot_carrier, "rule": eot_rule, "semantic": CONDITIONAL,
                     "raw_hex": raw_hex, "program_sha256": program_sha}

    es = msg.get("execution_size")
    es_ok = type(es) is int and not isinstance(es, bool) and es in {1, 2, 4, 8, 16, 32}
    fields["execution_size"] = {"bits": None, "value": es if es_ok else None,
                                "state": KNOWN if es_ok else UNKNOWN,
                                "carrier": "IGA decoded es", "rule": "J2",
                                "semantic": KNOWN, "raw_hex": raw_hex,
                                "program_sha256": program_sha}

    for lens_name, out_name, semantic in [
            ("payload0_grf", "payload0_grf_length", KNOWN),
            # payload1 length is carried by the same exDesc[9:6] bits as EML,
            # whose width is context-dependent -> CONDITIONAL (FM-P7).
            ("payload1_grf", "payload1_grf_length", CONDITIONAL),
            ("response_grf", "response_grf_length", KNOWN)]:
        lstate, lv = _length_fact(msg.get("lengths"), lens_name)
        fields[out_name] = {"bits": None, "value": lv, "state": lstate,
                            "carrier": "decoded length", "rule": "D1",
                            "semantic": semantic, "raw_hex": raw_hex,
                            "program_sha256": program_sha}
    dst_state, dst = _response_destination(msg)
    fields["response_is_null"] = {
        "bits": None,
        "value": (dst.get("reg", {}).get("rn") == "null") if dst is not None else None,
        "state": dst_state,
        "carrier": "decoded destination", "rule": "D2", "semantic": KNOWN,
        "raw_hex": raw_hex, "program_sha256": program_sha,
    }

    family = msg.get("family")
    for name, high, low, rule, semantic in FAMILY_FIELDS.get(family, []):
        desc_field(name, high, low, rule, semantic)

    # D2 cross-field consistency: a null destination requires RLEN==0.
    # A null destination with RLEN>0 is a contradiction, so the related rows
    # cannot be semantic KNOWN/proven.  D2 says nothing about a non-null
    # destination with RLEN==0; do not guess a violation there.
    is_null = fields["response_is_null"]["value"]
    rlen_entry = fields["response_length_rlen"]
    grf_entry = fields["response_grf_length"]
    contradiction = (is_null is True and rlen_entry.get("state") == KNOWN
                     and type(rlen_entry.get("value")) is int
                     and not isinstance(rlen_entry.get("value"), bool)
                     and rlen_entry["value"] > 0)
    if contradiction:
        for name in ("response_is_null", "response_length_rlen", "response_grf_length"):
            entry = fields[name]
            entry["cross_field_state"] = "CONTRADICTS_D2_NULL_DEST_RLEN_GT_0"
            entry["semantic"] = UNKNOWN
    elif (rlen_entry.get("state") == KNOWN and rlen_entry.get("value") == 0
          and is_null is False):
        rlen_entry["cross_field_state"] = "D2_NOT_APPLICABLE_NONNULL_DEST"
    elif dst_state != KNOWN:
        for name in ("response_length_rlen", "response_grf_length"):
            fields[name]["cross_field_state"] = "RESPONSE_DESTINATION_UNKNOWN"

    # N15: the descriptor field and the decoded length fact are two
    # representations of the same quantity.  A known disagreement (or one side
    # unknown/malformed) is a cross-field contradiction: downgrade the relevant
    # rows while retaining their actual encoded/raw values.
    if not contradiction:
        def _cross_state(desc_name, dec_name, prefix):
            d, c = fields[desc_name], fields[dec_name]
            dk = (d.get("state") == KNOWN and type(d.get("value")) is int
                  and not isinstance(d.get("value"), bool))
            ck = (c.get("state") == KNOWN and type(c.get("value")) is int
                  and not isinstance(c.get("value"), bool))
            if dk and ck:
                if d["value"] != c["value"]:
                    return prefix + "_DISAGREE"
                return None
            if dk and not ck:
                return prefix + "_DECODED_UNKNOWN"
            if not dk and ck:
                return prefix + "_DESCRIPTOR_UNKNOWN"
            return prefix + "_UNKNOWN"

        for desc_name, dec_name, prefix, extra in (
                ("response_length_rlen", "response_grf_length",
                 "DESCRIPTOR_RLEN_DECODED_LENGTH", ["response_is_null"]),
                ("message_length_mlen", "payload0_grf_length",
                 "DESCRIPTOR_MLEN_DECODED_LENGTH", []),
                ("extended_mlen", "payload1_grf_length",
                 "DESCRIPTOR_EML_DECODED_LENGTH", [])):
            cross = _cross_state(desc_name, dec_name, prefix)
            if cross:
                for name in [desc_name, dec_name] + extra:
                    fields[name]["cross_field_state"] = cross
                    fields[name]["semantic"] = UNKNOWN
    return fields


def _relation(name, s_entry, t_entry):
    """Classify the encoding relation; None==None is never equality."""
    sv, tv = s_entry["value"], t_entry["value"]
    both_known = (s_entry["state"] == KNOWN and t_entry["state"] == KNOWN
                  and sv is not None and tv is not None)
    if name == "descriptor_dword":
        if not both_known:
            return "UNKNOWN", UNKNOWN
        return ("SAME_DWORD_ENCODING_ONLY" if sv == tv else "DWORD_CHANGED"), KNOWN
    if name == "extended_descriptor_dword":
        if not both_known:
            return "UNKNOWN", UNKNOWN
        if sv == tv:
            return "SAME_DWORD_ENCODING_ONLY", KNOWN
        return "VALUE_CHANGED_CARRIER_CLEARED", KNOWN
    if not both_known:
        return "UNKNOWN", UNKNOWN
    if name in {"sfid", "eot"}:
        if sv == tv:
            return "CARRIER_RELOCATED_KEEPING_VALUE", KNOWN
        return "VALUE_CHANGED", KNOWN
    if sv == tv:
        return "IDENTICAL_VALUE", KNOWN
    return "VALUE_CHANGED", KNOWN


def _semantic_state(name, rel, enc_state, s_entry, t_entry, layout_match):
    """Semantic state can never exceed the encoding state.

    ``sfid`` and ``eot`` are documented carrier relocations (X1/X2, E1/E2);
    their bit ranges are expected to differ, so the generic layout-mismatch
    guard does not apply to them.
    """
    if enc_state != KNOWN:
        return UNKNOWN
    if name == "sfid":
        return KNOWN if rel == "CARRIER_RELOCATED_KEEPING_VALUE" else UNKNOWN
    if name == "eot":
        return CONDITIONAL
    if layout_match is False:
        return UNKNOWN
    if name in {"descriptor_dword", "extended_descriptor_dword"}:
        return UNKNOWN
    if name == "extended_function_control":
        return UNKNOWN
    if name == "extended_mlen":
        return CONDITIONAL
    if name == "message_type":
        return CONDITIONAL
    if rel == "IDENTICAL_VALUE":
        return s_entry.get("semantic", UNKNOWN)
    return UNKNOWN


def _equivalence(name, rel, enc_state, semantic_state, layout_match):
    if name in {"descriptor_dword", "extended_descriptor_dword"}:
        return SEMANTICS_UNKNOWN
    if enc_state != KNOWN:
        return SEMANTICS_UNKNOWN
    # sfid/eot are documented carrier relocations; other fields with different
    # bit layouts are not compared like-for-like.
    if layout_match is False and name not in {"sfid", "eot"}:
        return SEMANTICS_UNKNOWN
    if rel in {"VALUE_CHANGED", "VALUE_CHANGED_CARRIER_CLEARED", "DWORD_CHANGED"}:
        return DIFFERENCE_CONFIRMED
    if semantic_state == KNOWN:
        return EQUIV_PROVEN
    if semantic_state == CONDITIONAL:
        return EQUIV_CONDITIONAL
    return SEMANTICS_UNKNOWN


def contract_for_pair(source_msg, target_msg, source_node=None, target_node=None,
                      alignment="OFFSET", alignment_basis="DEFAULT_OFFSET_LAYOUT_HYPOTHESIS",
                      witness_proven=False):
    """Build one per-field source->target contract for an aligned message pair."""
    sf = extract_fields(source_msg, "source", source_node)
    tf = extract_fields(target_msg, "target", target_node)
    names = [n for n in FIELD_ORDER if n in sf or n in tf]
    names += [n for n in sf if n not in names]
    names += [n for n in tf if n not in names]

    family = target_msg.get("family") or source_msg.get("family")
    src_family = source_msg.get("family")
    tgt_family = target_msg.get("family")
    family_mismatch = bool(src_family is not None and tgt_family is not None
                           and src_family != tgt_family)

    rows = []
    for name in names:
        s_entry = sf.get(name, {"bits": None, "value": None, "state": MISSING,
                                "carrier": "absent", "rule": "ABSENT", "semantic": UNKNOWN,
                                "raw_hex": source_msg.get("raw_hex"),
                                "program_sha256": source_msg.get("program_sha256")})
        t_entry = tf.get(name, {"bits": None, "value": None, "state": MISSING,
                                "carrier": "absent", "rule": "ABSENT", "semantic": UNKNOWN,
                                "raw_hex": target_msg.get("raw_hex"),
                                "program_sha256": target_msg.get("program_sha256")})
        rel, enc_state = _relation(name, s_entry, t_entry)
        sb, tb = s_entry.get("bits"), t_entry.get("bits")
        layout_match = None if (sb is None or tb is None) else (list(sb) == list(tb))
        sem_state = _semantic_state(name, rel, enc_state, s_entry, t_entry, layout_match)
        s_cross = s_entry.get("cross_field_state")
        t_cross = t_entry.get("cross_field_state")
        consistency_fields = {
            "response_is_null", "response_length_rlen", "response_grf_length",
            "message_length_mlen", "payload0_grf_length",
            "extended_mlen", "payload1_grf_length",
        }
        downgrade = False
        if name in consistency_fields and (s_cross or t_cross):
            downgrade = any(
                c and (c.startswith("DESCRIPTOR_")
                       or c == "CONTRADICTS_D2_NULL_DEST_RLEN_GT_0"
                       or c == "RESPONSE_DESTINATION_UNKNOWN")
                for c in (s_cross, t_cross))
            if downgrade:
                sem_state = UNKNOWN
        # Contradictory facts cannot establish even a difference verdict.
        # Keep the raw encoding relation separately for diagnostic inspection.
        equiv = (SEMANTICS_UNKNOWN if downgrade else
                 _equivalence(name, rel, enc_state, sem_state, layout_match))
        if name == "descriptor_dword":
            note = INVARIANT
        elif name == "extended_descriptor_dword":
            note = INVARIANT
        elif name == "extended_function_control":
            note = "Gen12 exDesc[31:12] semantics unresolved (U5)"
        elif name == "extended_mlen":
            note = "EML width is context-dependent ([9:6] sends/RT vs [10:6] generic); bit10 is 0 here"
        elif name == "payload1_grf_length":
            note = "same exDesc[9:6] bits as extended_mlen; semantic verdict kept coherent (CONDITIONAL)"
        elif name == "eot":
            note = "EOT carrier relocated from exDesc[5] to the instruction EOT option (E2); TS_EOT conflict is U3/W2"
        elif name == "message_type":
            note = "family message-type field; RC structure dispute is U7"
        elif name == "sfid":
            note = "SFID numeric mapping is generation-independent (M4); carrier differs (X1 vs X2)"
        elif layout_match is False:
            note = "source and target bit layouts differ; values are not compared like-for-like"
        else:
            note = None
        if name in {"descriptor_dword", "extended_descriptor_dword", "extended_function_control"}:
            semantic_scope = "ENCODING_IDENTITY_ONLY"
        elif name == "opcode_form":
            semantic_scope = "OPCODE_MNEMONIC_ONLY"
        else:
            semantic_scope = "ENCODED_FIELD_VALUE_ONLY"
        u7_open = (family == "RENDER_TARGET" and name in RT_ENCODED_FIELDS)
        rows.append({
            "field": name,
            "source": dict(s_entry),
            "target": dict(t_entry),
            "encoding_relation": rel,
            "encoding_state": enc_state,
            "semantic_state": sem_state,
            "semantic_scope": semantic_scope,
            "semantic_scope_note": (
                "encoded RT index/value only; full render-target message semantics remain U7/UNKNOWN"
                if u7_open else
                ("exDesc/descriptor encoding identity only; hardware semantics remain U5/UNKNOWN"
                 if name in {"descriptor_dword", "extended_descriptor_dword", "extended_function_control"}
                 else ("SEND split/native mnemonic normalization; not a semantic difference or CE"
                       if name == "opcode_form" else "per-field encoded value only"))
            ),
            "u7_open": u7_open,
            "difference_kind": ("OPCODE_MNEMONIC_NORMALIZATION"
                                if name == "opcode_form" and rel == "VALUE_CHANGED" else None),
            "semantic_counterexample": (False if name == "opcode_form" and rel == "VALUE_CHANGED" else None),
            "equivalence": equiv,
            "bit_layouts_match": layout_match,
            "evidence": sorted({s_entry.get("rule"), t_entry.get("rule")} - {None}),
            "note": note,
            **({"cross_field_state": s_cross or t_cross}
               if (s_cross or t_cross) else {}),
        })

    def symbolic(msg):
        return {
            "resource_dependencies": [
                {"resource": r.get("resource"), "state": r.get("state", UNKNOWN), "identity": r.get("identity")}
                for r in (msg.get("resource_dependencies") or [])
            ],
            "thread_payload_dependencies": _fact(msg.get("thread_payload_dependencies"))[1],
            "completion_semantics": {
                k: (_fact(v)[0]) for k, v in (msg.get("completion_semantics") or {}).items()
            },
            "potential_external_side_effect": _fact(msg.get("potential_external_side_effect"))[1],
        }

    return {
        "shader_id": target_msg.get("shader_id") or source_msg.get("shader_id"),
        "source_offset": source_msg.get("instruction_offset"),
        "target_offset": target_msg.get("instruction_offset"),
        "family": family,
        "source_family": src_family,
        "target_family": tgt_family,
        "family_mismatch": family_mismatch,
        "alignment": alignment,
        "alignment_basis": alignment_basis,
        "layout_proof": False,
        "witness_proven": witness_proven,
        "source": {
            "program_sha256": source_msg.get("program_sha256"),
            "instruction_offset": source_msg.get("instruction_offset"),
            "raw_hex": source_msg.get("raw_hex"),
            "platform": source_msg.get("platform"),
        },
        "target": {
            "program_sha256": target_msg.get("program_sha256"),
            "instruction_offset": target_msg.get("instruction_offset"),
            "raw_hex": target_msg.get("raw_hex"),
            "platform": target_msg.get("platform"),
        },
        "fields": rows,
        "symbolic_external": {"source": symbolic(source_msg), "target": symbolic(target_msg),
                              "state": UNKNOWN},
        "ir_anchors": {
            "source_in_ir": source_node is not None,
            "target_in_ir": target_node is not None,
            "source_byte_range": (source_node or {}).get("byte_range"),
            "target_byte_range": (target_node or {}).get("byte_range"),
        },
        "same_dword_implies_equivalence": False,
    }


def contract_for_unpaired(msg, side, node=None):
    """Preserve a source-only or target-only message without inventing a pair."""
    present = extract_fields(msg, "source" if side == "source" else "target", node)
    rows = []
    for name in [n for n in FIELD_ORDER if n in present] + [n for n in present if n not in FIELD_ORDER]:
        entry = present[name]
        absent = {"bits": None, "value": None, "state": MISSING, "carrier": "absent",
                  "rule": "ABSENT", "semantic": UNKNOWN, "raw_hex": None,
                  "program_sha256": None}
        s_entry, t_entry = (entry, absent) if side == "source" else (absent, entry)
        rows.append({
            "field": name,
            "source": dict(s_entry),
            "target": dict(t_entry),
            "encoding_relation": "UNKNOWN",
            "encoding_state": UNKNOWN,
            "semantic_state": UNKNOWN,
            "equivalence": SEMANTICS_UNKNOWN,
            "bit_layouts_match": None,
            "evidence": sorted({s_entry.get("rule"), t_entry.get("rule")} - {None, "ABSENT"}),
            "note": "unpaired %s message; no source/target correspondence" % side,
        })
    side_block = {
        "program_sha256": msg.get("program_sha256"),
        "instruction_offset": msg.get("instruction_offset"),
        "raw_hex": msg.get("raw_hex"),
        "platform": msg.get("platform"),
    }
    return {
        "shader_id": msg.get("shader_id"),
        "source_offset": msg.get("instruction_offset") if side == "source" else None,
        "target_offset": msg.get("instruction_offset") if side == "target" else None,
        "family": msg.get("family"),
        "source_family": msg.get("family") if side == "source" else None,
        "target_family": msg.get("family") if side == "target" else None,
        "family_mismatch": False,
        "alignment": "UNMATCHED" if side == "source" else "UNPAIRED_TARGET",
        "alignment_basis": "NO_CORRESPONDENCE",
        "layout_proof": False,
        "witness_proven": False,
        "unpaired_side": side,
        "source": side_block if side == "source" else {"program_sha256": None, "instruction_offset": None,
                                                       "raw_hex": None, "platform": None},
        "target": side_block if side == "target" else {"program_sha256": None, "instruction_offset": None,
                                                       "raw_hex": None, "platform": None},
        "fields": rows,
        "symbolic_external": {"source": None if side != "source" else {"state": UNKNOWN},
                              "target": None if side != "target" else {"state": UNKNOWN},
                              "state": UNKNOWN},
        "ir_anchors": {
            "source_in_ir": node is not None if side == "source" else False,
            "target_in_ir": node is not None if side == "target" else False,
            "source_byte_range": (node or {}).get("byte_range") if side == "source" else None,
            "target_byte_range": (node or {}).get("byte_range") if side == "target" else None,
        },
        "same_dword_implies_equivalence": False,
    }


def _group_programs(obj):
    """Group programs by shader_id; duplicate identities are rejected, not last-wins."""
    groups = {}
    for prog in _iter_program_dicts(obj):
        groups.setdefault(prog.get("shader_id"), []).append(prog)
    unique, ambiguous, errors = {}, {}, []
    for sid, progs in groups.items():
        if len(progs) == 1:
            unique[sid] = progs[0]
        else:
            ambiguous[sid] = progs
            errors.append({
                "code": "AMBIGUOUS_PROGRAM_IDENTITY",
                "shader_id": sid,
                "count": len(progs),
                "program_sha256": [p.get("program_sha256") for p in progs],
                "detail": "duplicate shader_id programs are rejected; no last-wins selection",
            })
    return unique, ambiguous, errors


def _validate_witness(witness, source_progs, target_progs):
    """Validate a per-shader hash-bound layout witness.

    Returns ``(map, diagnostics, meta)``.  Global SHA set-membership is NOT
    enough: each shader with entries needs its own source/target SHA binding.
    """
    if not witness:
        return {}, [], {"supplied": False, "hash_bound": False,
                        "bindings": [], "diagnostics": []}
    if not isinstance(witness, dict):
        raise MappingError("WITNESS_SHAPE")
    entries = witness.get("entries")
    if not isinstance(entries, list) or not entries:
        raise MappingError("WITNESS_ENTRIES_MISSING")
    raw_bindings = list(witness.get("bindings") or [])
    top_src = witness.get("source_program_sha256")
    top_tgt = witness.get("target_program_sha256")
    diagnostics = []
    if top_src or top_tgt:
        if len(source_progs) == 1 and len(target_progs) == 1:
            sid = next(iter(source_progs))
            raw_bindings.append({"shader_id": sid, "source_program_sha256": top_src,
                                 "target_program_sha256": top_tgt})
        else:
            diagnostics.append({
                "code": "WITNESS_TOP_LEVEL_BINDING_AMBIGUOUS",
                "detail": "top-level SHAs need exactly one source and one target program; use bindings[]",
            })
    if not raw_bindings and not (top_src or top_tgt):
        raise MappingError("WITNESS_NOT_HASHBOUND")
    bindings = []
    for b in raw_bindings:
        if not isinstance(b, dict):
            raise MappingError("WITNESS_BINDING_SHAPE")
        sid = b.get("shader_id")
        if sid not in source_progs or sid not in target_progs:
            raise MappingError("WITNESS_UNKNOWN_SHADER")
        s_sha, t_sha = b.get("source_program_sha256"), b.get("target_program_sha256")
        if not s_sha or not t_sha:
            raise MappingError("WITNESS_NOT_HASHBOUND")
        if source_progs[sid].get("program_sha256") != s_sha:
            raise MappingError("WITNESS_SOURCE_SHA_MISMATCH")
        if target_progs[sid].get("program_sha256") != t_sha:
            raise MappingError("WITNESS_TARGET_SHA_MISMATCH")
        bindings.append({"shader_id": sid, "source_program_sha256": s_sha,
                         "target_program_sha256": t_sha})
    bound = {b["shader_id"]: b for b in bindings}
    if not bound:
        # top-level binding on a multi-program bundle: fail closed, not raise.
        return {}, diagnostics, {"supplied": True, "hash_bound": False,
                                 "bindings": bindings, "diagnostics": diagnostics}
    wmap, targets = {}, {}
    for e in entries:
        if not isinstance(e, dict):
            raise MappingError("WITNESS_ENTRY_SHAPE")
        sid = e.get("shader_id")
        so, to = e.get("source_offset"), e.get("target_offset")
        if sid not in source_progs and sid not in target_progs:
            raise MappingError("WITNESS_UNKNOWN_SHADER")
        if type(so) is not int or isinstance(so, bool) \
                or type(to) is not int or isinstance(to, bool):
            raise MappingError("WITNESS_ENTRY_SHAPE")
        if sid not in bound:
            diagnostics.append({
                "code": "WITNESS_NOT_BOUND_FOR_SHADER",
                "shader_id": sid,
                "detail": "entry ignored: no per-shader source/target SHA binding",
            })
            continue
        if sid not in source_progs or sid not in target_progs:
            raise MappingError("WITNESS_UNKNOWN_SHADER")
        src_offs = {m.get("instruction_offset") for m in source_progs[sid].get("messages", [])}
        tgt_offs = {m.get("instruction_offset") for m in target_progs[sid].get("messages", [])}
        if so not in src_offs or to not in tgt_offs:
            raise MappingError("WITNESS_OFFSET_NOT_FOUND")
        key = (sid, so)
        if key in wmap:
            if wmap[key] != to:
                raise MappingError("WITNESS_CONFLICT")
            raise MappingError("WITNESS_DUPLICATE_ENTRY")
        if (sid, to) in targets:
            raise MappingError("WITNESS_TARGET_CONFLICT")
        wmap[key] = to
        targets[(sid, to)] = so
    return wmap, diagnostics, {"supplied": True, "hash_bound": bool(wmap),
                               "bindings": bindings, "diagnostics": diagnostics}


def _ambiguous_program_row(sid, source_progs, target_progs):
    def programs(progs):
        return [{"program_sha256": p.get("program_sha256"), "platform": p.get("platform"),
                 "messages": [{"instruction_offset": m.get("instruction_offset"),
                               "raw_hex": m.get("raw_hex")} for m in p.get("messages", [])]}
                for p in progs]
    return {
        "shader_id": sid, "source_offset": None, "target_offset": None,
        "family": None, "source_family": None, "target_family": None,
        "family_mismatch": False,
        "alignment": "AMBIGUOUS_PROGRAM_IDENTITY",
        "alignment_basis": "REJECTED_DUPLICATE_PROGRAM_IDENTITY",
        "layout_proof": False, "witness_proven": False, "unpaired_side": None,
        "source": {"duplicate_programs": programs(source_progs)},
        "target": {"duplicate_programs": programs(target_progs)},
        "fields": [],
        "program_identity_errors": [{
            "code": "AMBIGUOUS_PROGRAM_IDENTITY",
            "shader_id": sid,
            "detail": "duplicate programs with the same shader_id are rejected; no last-wins",
        }],
        "symbolic_external": {"state": UNKNOWN},
        "ir_anchors": {"source_in_ir": False, "target_in_ir": False,
                       "source_byte_range": None, "target_byte_range": None},
        "same_dword_implies_equivalence": False,
    }


def _with_program(msg, prog):
    """Attach program-level identity to a message copy for contract output."""
    out = dict(msg)
    out.setdefault("program_sha256", prog.get("program_sha256"))
    out.setdefault("shader_id", prog.get("shader_id"))
    out.setdefault("platform", prog.get("platform"))
    return out


def _align(source_prog, target_prog, witness_map):
    """Explicit witness first, then exact-offset layout hypothesis. No ORDINAL.

    An explicit witness assignment always wins over a default-offset collision;
    the default offset can never silently override it.
    """
    src = list(source_prog.get("messages", []))
    tgt = list(target_prog.get("messages", []))
    tgt_by_off = {m.get("instruction_offset"): m for m in tgt}
    sid = source_prog.get("shader_id")
    used, assign = set(), {}
    for i, sm in enumerate(src):
        off = sm.get("instruction_offset")
        if (sid, off) in witness_map:
            tm = tgt_by_off.get(witness_map[(sid, off)])
            if tm is None:
                raise MappingError("WITNESS_OFFSET_NOT_FOUND")
            if id(tm) in used:
                raise MappingError("WITNESS_TARGET_CONFLICT")
            used.add(id(tm))
            assign[i] = (tm, "EXPLICIT_WITNESS", "EXPLICIT_WITNESS")
    for i, sm in enumerate(src):
        if i in assign:
            continue
        off = sm.get("instruction_offset")
        tm = tgt_by_off.get(off)
        if tm is not None and id(tm) not in used:
            used.add(id(tm))
            assign[i] = (tm, "OFFSET", "DEFAULT_OFFSET_LAYOUT_HYPOTHESIS")
        else:
            assign[i] = (None, "UNMATCHED", "NO_CORRESPONDENCE")
    for i, sm in enumerate(src):
        tm, kind, basis = assign[i]
        yield sm, tm, kind, basis
    for tm in tgt:
        if id(tm) not in used:
            yield None, tm, "UNPAIRED_TARGET", "NO_CORRESPONDENCE"


def field_contracts(source_messages, target_messages, source_ir=None, target_ir=None,
                    witness=None):
    """Emit per-field source->target contracts for every aligned SEND pair.

    All source and target messages are represented: unmatched messages become
    UNMATCHED / UNPAIRED_TARGET rows rather than being dropped.
    """
    src_progs, src_amb, src_errors = _group_programs(source_messages)
    tgt_progs, tgt_amb, tgt_errors = _group_programs(target_messages)
    src_nodes = _ir_nodes_by_program(source_ir)
    tgt_nodes = _ir_nodes_by_program(target_ir)
    if witness:
        witness_map, wdiag, wmeta = _validate_witness(witness, src_progs, tgt_progs)
    else:
        witness_map, wdiag, wmeta = {}, [], {"supplied": False, "hash_bound": False,
                                             "bindings": [], "diagnostics": []}
    wmeta = dict(wmeta)
    if wdiag and not wmeta.get("diagnostics"):
        wmeta["diagnostics"] = list(wdiag)

    pairs = []
    all_sids = sorted(set(src_progs) | set(tgt_progs) | set(src_amb) | set(tgt_amb))
    for sid in all_sids:
        if sid in src_amb or sid in tgt_amb:
            pairs.append(_ambiguous_program_row(sid, src_amb.get(sid, []), tgt_amb.get(sid, [])))
            # Preserve the unambiguous side symmetrically: each unambiguous
            # source message becomes UNMATCHED and each unambiguous target
            # message becomes UNPAIRED_TARGET, alongside the ambiguous row.
            if sid in src_progs:
                for sm in src_progs[sid].get("messages", []):
                    sm = _with_program(sm, src_progs[sid])
                    pairs.append(contract_for_unpaired(
                        sm, "source", src_nodes.get(sid, {}).get(sm.get("instruction_offset"))))
            if sid in tgt_progs:
                for tm in tgt_progs[sid].get("messages", []):
                    tm = _with_program(tm, tgt_progs[sid])
                    pairs.append(contract_for_unpaired(
                        tm, "target", tgt_nodes.get(sid, {}).get(tm.get("instruction_offset"))))
            continue
        sp, tp = src_progs.get(sid), tgt_progs.get(sid)
        if sp is None:
            for tm in tp.get("messages", []):
                tm = _with_program(tm, tp)
                pairs.append(contract_for_unpaired(
                    tm, "target", tgt_nodes.get(sid, {}).get(tm.get("instruction_offset"))))
            continue
        if tp is None:
            for sm in sp.get("messages", []):
                sm = _with_program(sm, sp)
                pairs.append(contract_for_unpaired(
                    sm, "source", src_nodes.get(sid, {}).get(sm.get("instruction_offset"))))
            continue
        for sm, tm, kind, basis in _align(sp, tp, witness_map):
            if sm is None:
                tm = _with_program(tm, tp)
                pairs.append(contract_for_unpaired(
                    tm, "target", tgt_nodes.get(sid, {}).get(tm.get("instruction_offset"))))
                continue
            if tm is None:
                sm = _with_program(sm, sp)
                pairs.append(contract_for_unpaired(
                    sm, "source", src_nodes.get(sid, {}).get(sm.get("instruction_offset"))))
                continue
            sm, tm = _with_program(sm, sp), _with_program(tm, tp)
            sn = src_nodes.get(sid, {}).get(sm.get("instruction_offset"))
            tn = tgt_nodes.get(sid, {}).get(tm.get("instruction_offset"))
            row = contract_for_pair(sm, tm, sn, tn, alignment=kind, alignment_basis=basis,
                                    witness_proven=(kind == "EXPLICIT_WITNESS"))
            pairs.append(row)

    field_states = {}
    equiv_counts = {}
    for p in pairs:
        for f in p.get("fields", []):
            field_states.setdefault(f["field"], set()).add(f["semantic_state"])
            equiv_counts[f["equivalence"]] = equiv_counts.get(f["equivalence"], 0) + 1
    paired = [p for p in pairs if p.get("alignment") in {"OFFSET", "EXPLICIT_WITNESS"}]
    summary = {
        "pairs": len(pairs),
        "paired": len(paired),
        "unpaired_sources": sum(1 for p in pairs if p.get("alignment") == "UNMATCHED"),
        "unpaired_targets": sum(1 for p in pairs if p.get("alignment") == "UNPAIRED_TARGET"),
        "ambiguous_programs": sorted(set(src_amb) | set(tgt_amb)),
        "program_identity_errors": list(src_errors) + list(tgt_errors),
        "matcher": "explicit hash-bound witness first, then exact instruction_offset (layout hypothesis); NO ordinal fallback",
        "families": sorted({p.get("family") for p in pairs if p.get("family")}),
        "semantic_states": {k: sorted(v) for k, v in sorted(field_states.items())},
        "equivalence_counts": dict(sorted(equiv_counts.items())),
        "equivalence_scope": "PER_FIELD_ENCODED_VALUE",
        "message_level_equivalence_claimed": False,
        "witness": {
            "supplied": bool(witness),
            "hash_bound": bool(wmeta.get("hash_bound")),
            "bindings": wmeta.get("bindings", []),
            "diagnostics": wmeta.get("diagnostics", []),
        },
        "invariant": INVARIANT,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "module": "ga39.messages.field_mapping",
        "invariant": INVARIANT,
        "equivalence_scope": "PER_FIELD_ENCODED_VALUE",
        "message_level_equivalence_claimed": False,
        "pairs": pairs,
        "summary": summary,
        "hardware_validated": False,
    }


def _load_paths(paths, suffix):
    """Accept a file, a directory (glob *suffix) or a list; return list of JSON."""
    if isinstance(paths, (list, tuple)):
        out = []
        for p in paths:
            out.extend(_load_paths(p, suffix))
        return out
    if paths is None:
        return []
    if os.path.isdir(paths):
        files = sorted(glob.glob(os.path.join(paths, "*" + suffix)))
        return [_load_json(f) for f in files]
    return [_load_json(paths)]


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    parser = argparse.ArgumentParser(description="GA3.9 independent source->target per-field message contracts")
    parser.add_argument("--source-messages", required=True, help="GA3.8 source message IR file or directory")
    parser.add_argument("--target-messages", required=True, help="GA3.8 target message IR file or directory")
    parser.add_argument("--source-ir", default=None, help="optional GA3.8 source node IR file/dir")
    parser.add_argument("--target-ir", default=None, help="optional GA3.8 target node IR file/dir")
    parser.add_argument("--witness", default=None, help="optional hash-bound layout witness JSON")
    parser.add_argument("--out", default=None, help="write JSON here instead of stdout")
    args = parser.parse_args(argv)

    sources = _load_paths(args.source_messages, "-source.json")
    targets = _load_paths(args.target_messages, "-candidate.json")
    if not targets:
        targets = _load_paths(args.target_messages, ".json")
    if not sources:
        sources = _load_paths(args.source_messages, ".json")
    src_ir = [_load_json(f) for f in sorted(glob.glob(os.path.join(args.source_ir, "*.json")))] if args.source_ir and os.path.isdir(args.source_ir) else ([_load_json(args.source_ir)] if args.source_ir else None)
    tgt_ir = [_load_json(f) for f in sorted(glob.glob(os.path.join(args.target_ir, "*.json")))] if args.target_ir and os.path.isdir(args.target_ir) else ([_load_json(args.target_ir)] if args.target_ir else None)
    witness = _load_json(args.witness) if args.witness else None

    result = field_contracts({"programs": sources}, {"programs": targets}, src_ir, tgt_ir, witness)
    text = json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
