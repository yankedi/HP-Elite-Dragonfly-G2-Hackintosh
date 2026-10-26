"""GA3.9 track B: independent SEND/token event-obligation builder.

Standalone, dependency-free (stdlib only) reader of the frozen GA3.8 candidate
IR.  It turns the decoded Gen12 (Xe-LP single-distance-pipe) SWSB/token stream
into an explicit list of *event obligations*:

    SOURCE_CONSUMPTION  -- the SEND payload registers must be consumed
    RESPONSE_WRITE      -- a response is written back (RLEN>0)
    NO_RESPONSE         -- the SEND declares RLEN==0 / null destination
    DST_WAIT            -- a consumer waits for write-back completion  ($N.dst)
    SRC_WAIT            -- a consumer waits for source-read completion  ($N.src)
    SBID_SET            -- a SEND allocates a shared-function SBID token
    SBID_REUSE          -- a SEND re-allocates an SBID that is still live
    TOKEN_SOURCE_COMPLETE / TOKEN_DST_COMPLETE -- per-token completion events
    SIDE_EFFECT         -- potential externally visible shared-function effect
    EOT                 -- the terminating end-of-thread message
    SWSB_UNMODELED / SYNC_UNMODELED / SEND_TOKEN_MISSING / TOKEN_WAIT_UNBOUND

Every obligation carries the exact producer/consumer byte offsets, the pinned
rule id it rests on, its evidence list, a KNOWN|CONDITIONAL|UNKNOWN state and an
`unknown_code` when it is not discharged.

Repair-001 (2026-10-20) changes driven by the independent initial audit:
  * missing / unknown / identity-mismatched response-length or payload-length
    facts are NEVER coerced to 0; they keep an explicit UNKNOWN obligation
    (SC-C1, SC-C2, SC-C3, SC-C3b);
  * supplied message IR must match the node program's shader_id, platform and
    program_sha256; incompatible source/candidate IR is never silently used and
    duplicate compatible IR is rejected instead of last-wins (SC-C7);
  * SBID re-use is never KNOWN from IGA-implementation-only rules K2/K3; both
    branches stay UNKNOWN (SC-C4);
  * the null-response `$N.dst` and re-use UNKNOWNs introduced in the first
    delivery are retained unchanged (SC-C5);
  * dead helpers removed (SC-DEAD).

Scope discipline (GA3.9, track B):
  * This module is NOT the translator and does NOT import translator policy.
  * It never fabricates a SYNC.  A missing explicit wait is not promoted to an
    error and never silently converted into an implicit one.
  * `$N.dst` on a no-response SEND stays UNKNOWN (`NULL_RESPONSE_DST_WAIT_UNRESOLVED`).
  * Re-use of a still-live SBID stays UNKNOWN (`SBID_REUSE_SYNC_UNPROVEN`).
  * Message completion / payload consumption / external visibility stay UNKNOWN.
  * `KNOWN` means "the cited pinned evidence establishes this obligation's
    required ordering event"; it is NOT hardware validation.  Rules whose only
    pinned confidence is IGA_IMPL (K2, K3) therefore never yield KNOWN.

Rule ids referenced (from GA3.8 `reference/rules/RULES.json` and
`validator/rules/evidence-map.json`, both pinned by SHA in the receipt):
  K1 `$N.src`/`$N.dst` meaning, K2 dType selection/SBID clearing (IGA_IMPL),
  K3 IGA implicit re-use synchronisation (IGA_IMPL), K5 null-response SEND,
  S1-S4 Xe-LP single distance pipe, D1/D2 descriptor lengths, W1 EOT waits.

Public API
----------
    build_obligations(ir, messages=None) -> dict
        ir        : GA3.8 candidate IR dict (a program with ``nodes``) or a
                    GA3.8 message IR dict (with ``messages``) or a bundle
                    ({"programs":[...]}) or a list of any of these.
        messages  : optional GA3.8 message IR used to enrich SEND records with
                    family / RLEN / payload lengths.  Identity must match the
                    node program (shader_id + platform + program_sha256).
    obligations_for_program(program, message_index=None) -> dict
    extract_instructions(program, message_index=None) -> list[dict]
    decode_swsb(record) -> dict

CLI
---
    python3 -B completion.py --ir IR.json [--messages MSG.json] [--out OUT.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys

SCHEMA_VERSION = 2
KNOWN = "KNOWN"
CONDITIONAL = "CONDITIONAL"
UNKNOWN = "UNKNOWN"
MISSING = "MISSING"

#: Opcodes that advance the single in-order counter (S3).  SEND/MATH do not.
INORDER_OPCODES = {"mov", "add", "mul", "mad", "mac"}

#: message families whose side effect is modelled only conditionally.
SIDE_EFFECT_FAMILIES = {
    "SAMPLER": ("CONDITIONAL", "SAMPLER-MESSAGE-TYPE"),
    "RENDER_TARGET": ("CONDITIONAL", "RT-MESSAGE-TYPE"),
    "URB": ("CONDITIONAL", "URB-OPCODE"),
}

EVENT_ORDER = [
    "SBID_SET", "SBID_REUSE", "SEND_TOKEN_MISSING",
    "SOURCE_CONSUMPTION", "SRC_WAIT", "RESPONSE_WRITE", "NO_RESPONSE",
    "DST_WAIT", "TOKEN_WAIT_UNBOUND",
    "TOKEN_SOURCE_COMPLETE", "TOKEN_DST_COMPLETE",
    "SIDE_EFFECT", "EOT", "SWSB_UNMODELED", "SYNC_UNMODELED",
]

#: obligation states and the rule ids they may cite as KNOWN.
#: Only SPEC-backed rules can establish a KNOWN hardware obligation.
KNOWN_RULE_CONFIDENCE = {
    "K1": ["SPEC"],
    "D1": ["SPEC", "IGA_IMPL", "LOCAL_DECODE"],
    "D2": ["SPEC"],
}


class CompletionError(ValueError):
    """Raised when the supplied object is not a recognised GA3.8 IR shape."""


def _fact_tristate(fact):
    """Return (state, value) without collapsing missing/unknown to a number."""
    if isinstance(fact, dict) and "state" in fact:
        return (fact.get("state") or UNKNOWN), fact.get("value")
    if fact is None:
        return MISSING, None
    return KNOWN, fact


def _length_fact(container, key, max_value=31):
    """Return (state, value) for a descriptor length fact.

    Only a KNOWN bounded real int (bool excluded) can be used as a length.
    Missing, UNKNOWN and contradictory ``KNOWN+null`` facts are returned as
    UNKNOWN/MISSING -- callers must not substitute 0 and must not raise.
    """
    fact = (container or {}).get(key)
    if not isinstance(fact, dict):
        return MISSING, None
    state, value = fact.get("state"), fact.get("value")
    if state == KNOWN and type(value) is int and not isinstance(value, bool) \
            and 0 <= value <= max_value:
        return KNOWN, value
    if state == KNOWN:
        # contradictory KNOWN+null / bool / out-of-range must not stay KNOWN
        return UNKNOWN, None
    return (state if state in {CONDITIONAL, UNKNOWN} else UNKNOWN), None


def _valid_grf_destination(dst):
    """Validate a decoded SEND destination (O6).

    A known non-null destination must be a structured GRF reference: ``rn`` is
    ``r`` (optional ``r``/``sr``; omitting ``r`` means 0, as IGA prints it) or
    ``null``.  Malformed/unknown ``kind``/``len``/``reg``/``rn``/types are
    UNKNOWN, never a known non-null destination.
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


def _response_destination_state(msg):
    dst = (msg or {}).get("response_destination")
    if not isinstance(dst, dict):
        return MISSING, None
    state = dst.get("state")
    if state is None:
        # GA3.8 stores the decoded destination object without a state field.
        state = KNOWN
    if state != KNOWN:
        return (state or UNKNOWN), None
    if not _valid_grf_destination(dst):
        return UNKNOWN, None
    return KNOWN, dst


def decode_swsb(record):
    """Decode the SWSB fields of one instruction/message record.

    Accepts a node ``iga_fields``-style dict (``regDist`` string + ``sbid``
    dict) or a message ``swsb`` dict, or a raw dict carrying both.  Returns a
    normalised description; ``state`` is UNKNOWN when the shape is outside the
    modelled Xe-LP single-pipe subset (never guessed).
    """
    if not isinstance(record, dict):
        raise CompletionError("SWSB record must be a dict, got %r" % (type(record),))
    src = record.get("iga_fields") if isinstance(record.get("iga_fields"), dict) else record
    if isinstance(src.get("swsb"), dict) and "regDist" not in src:
        src = src["swsb"]
    raw_reg = src.get("regDist")
    sbid_raw = src.get("sbid")

    regdist = None
    if raw_reg is not None:
        m = re.fullmatch(r"@(\d+)", raw_reg if isinstance(raw_reg, str) else "")
        if m and 1 <= int(m.group(1)) <= 7:
            regdist = int(m.group(1))

    sbid = None
    ok = True
    if sbid_raw is not None:
        if not isinstance(sbid_raw, dict):
            ok = False
        else:
            sid = sbid_raw.get("id")
            func = sbid_raw.get("func", "")
            if type(sid) is not int or not 0 <= sid < 16 or func not in {"", ".src", ".dst"}:
                ok = False
            else:
                sbid = {"id": sid, "func": func}

    encoded_byte = None
    raw_hex = record.get("raw_hex")
    if isinstance(raw_hex, str) and len(raw_hex) >= 8:
        try:
            encoded_byte = (int.from_bytes(bytes.fromhex(raw_hex)[:4], "little") >> 8) & 0xFF
        except ValueError:
            encoded_byte = None

    state = KNOWN if (ok and (raw_reg is None or regdist is not None)) else UNKNOWN
    return {
        "regDist": regdist,
        "raw_regDist": raw_reg,
        "sbid": sbid,
        "encoded_byte": encoded_byte,
        "state": state,
        "evidence": ["IGA-JSON", "GEN12-SWSB-ENCODING"],
    }


def _iter_programs(obj, allow_messages=False):
    """Yield normalised GA3.8 program dicts from any accepted container."""
    if obj is None:
        return
    if isinstance(obj, list):
        for item in obj:
            yield from _iter_programs(item, allow_messages)
        return
    if not isinstance(obj, dict):
        raise CompletionError("unsupported IR container: %r" % (type(obj),))
    if "programs" in obj and isinstance(obj["programs"], list):
        for item in obj["programs"]:
            yield from _iter_programs(item, allow_messages)
        return
    if "nodes" in obj and isinstance(obj["nodes"], list):
        yield {**obj, "kind": "program"}
        return
    if allow_messages and "messages" in obj and isinstance(obj["messages"], list):
        yield {**obj, "kind": "messages"}
        return
    raise CompletionError("dict is neither a program (nodes) nor a message IR (messages)")


def _message_programs(obj):
    """Return message-IR descriptors, preserving every distinct identity."""
    out = []
    seen = {}
    for prog in _iter_programs(obj, allow_messages=True):
        if prog.get("kind") != "messages":
            continue
        if "messages" not in prog:
            continue
        identity = (prog.get("shader_id"), prog.get("platform"), prog.get("program_sha256"))
        canon = json.dumps(prog.get("messages"), sort_keys=True, separators=(",", ":"))
        if identity in seen:
            if seen[identity] != canon:
                raise CompletionError(
                    "AMBIGUOUS_MESSAGE_IR_IDENTITY: duplicate shader/platform/program_sha256 %r with different content" % (identity,))
            continue
        seen[identity] = canon
        out.append(prog)
    return out


def _identity_match(node, message_prog):
    """True when the message IR belongs to the same shader/generation/program.

    Both program SHA-256 values are required: a node without a SHA cannot prove
    identity, so the message IR is not accepted (NEW-N7).
    """
    if node.get("shader_id") != message_prog.get("shader_id"):
        return False
    if node.get("platform") != message_prog.get("platform"):
        return False
    a, b = node.get("program_sha256"), message_prog.get("program_sha256")
    if not isinstance(a, str) or not isinstance(b, str) or a != b:
        return False
    return True


def _select_messages(node, message_programs):
    """Pick exactly one identity-compatible message IR for a node program.

    Returns (message_program | None, diagnostics).  Never last-wins.
    """
    compatible = [mp for mp in message_programs if _identity_match(node, mp)]
    same_shader = [mp for mp in message_programs
                   if mp.get("shader_id") == node.get("shader_id") and mp not in compatible]
    diagnostics = []
    if same_shader:
        diagnostics.append({
            "code": "MESSAGE_IR_IDENTITY_MISMATCH",
            "detail": "message IR for shader %r differs in platform/program_sha256; not used"
                      % (node.get("shader_id"),),
            "supplied": [{"platform": mp.get("platform"), "program_sha256": mp.get("program_sha256")}
                         for mp in same_shader],
        })
    if not compatible:
        if not same_shader:
            diagnostics.append({
                "code": "MESSAGE_IR_ABSENT",
                "detail": "no message IR supplied for this node program; response/payload facts are UNKNOWN",
            })
        return None, diagnostics
    if len(compatible) > 1:
        raise CompletionError(
            "AMBIGUOUS_MESSAGE_IR_IDENTITY: %d compatible message IRs for shader %r"
            % (len(compatible), node.get("shader_id")))
    return compatible[0], diagnostics


def extract_instructions(program, message_index=None):
    """Normalise one program into an ordered list of instruction records.

    Each record: offset, opcode, is_send, eot, subop, swsb, raw_hex and, for
    SENDs, family / response state+length / payload states+lengths / response
    destination state.  Missing facts are recorded as MISSING/UNKNOWN, never 0.
    """
    if program.get("kind") == "messages":
        records = []
        for msg in program.get("messages", []):
            records.append(_record_from_message(msg))
        return sorted(records, key=lambda r: r["offset"])

    local = message_index or {}
    records = []
    for node in program.get("nodes", []):
        fields = node.get("iga_fields") or {}
        off = node.get("byte_range", [None])[0]
        msg = local.get(off)
        if msg is not None:
            rec = _record_from_message(msg)
            rec.update({
                "offset": off,
                "opcode": node.get("opcode") or fields.get("op"),
                "is_send": bool((node.get("message_effects") or {}).get("is_send")),
                "eot": bool((node.get("control_effects") or {}).get("eot")),
                "subop": fields.get("subop"),
                "swsb": decode_swsb({"regDist": fields.get("regDist"), "sbid": fields.get("sbid"),
                                     "raw_hex": node.get("raw_hex")}),
                "raw_hex": node.get("raw_hex"),
                "message_present": True,
            })
            records.append(rec)
        else:
            records.append({
                "offset": off,
                "opcode": node.get("opcode") or fields.get("op"),
                "is_send": bool((node.get("message_effects") or {}).get("is_send")),
                "eot": bool((node.get("control_effects") or {}).get("eot")),
                "subop": fields.get("subop"),
                "swsb": decode_swsb({"regDist": fields.get("regDist"), "sbid": fields.get("sbid"),
                                     "raw_hex": node.get("raw_hex")}),
                "raw_hex": node.get("raw_hex"),
                "family": "UNKNOWN_MESSAGE",
                "response_state": MISSING,
                "response_len": None,
                "payload_states": [MISSING, MISSING],
                "payload_lengths": [None, None],
                "response_destination_state": MISSING,
                "response_is_null": None,
                "message_present": False,
            })
    return sorted(records, key=lambda r: r["offset"])


def _record_from_message(msg):
    lengths = msg.get("lengths") or {}
    # Field-specific encodings (verified before the restrictive fix):
    #   RLEN  desc[24:20] is 5 bits but D2 limits the valid range to 0..16.
    #   MLEN  desc[28:25] is 4 bits -> 0..15 (payload0).
    #   EML   exDesc[9:6] is 4 bits -> 0..15 (payload1).
    rstate, rlen = _length_fact(lengths, "response_grf", 16)
    p0 = _length_fact(lengths, "payload0_grf", 15)
    p1 = _length_fact(lengths, "payload1_grf", 15)
    dst_state, dst = _response_destination_state(msg)
    response_is_null = None
    if isinstance(dst, dict):
        response_is_null = dst.get("reg", {}).get("rn") == "null"
    return {
        "offset": msg.get("instruction_offset"),
        "opcode": msg.get("opcode_form", "send"),
        "is_send": True,
        "eot": bool(msg.get("eot")),
        "subop": None,
        "swsb": decode_swsb(msg.get("swsb") or {}),
        "raw_hex": msg.get("raw_hex"),
        "family": msg.get("family", "UNKNOWN_MESSAGE"),
        "response_state": rstate,
        "response_len": rlen,
        "payload_states": [p0[0], p1[0]],
        "payload_lengths": [p0[1], p1[1]],
        "response_destination_state": dst_state,
        "response_is_null": response_is_null,
        "message_present": True,
    }


def obligations_for_program(program, message_index=None, identity_diagnostics=None,
                            message_ir_matched=None):
    """Build the ordered event-obligation list for a single program."""
    records = extract_instructions(program, message_index)
    platform = program.get("platform")
    obligations = []
    tokens = {}
    diagnostics = list(identity_diagnostics or [])

    def add(event, state, rule, **kw):
        entry = {
            "event": event,
            "state": state,
            "rule": rule,
            "evidence": kw.pop("evidence", [rule]),
            "producer_offset": kw.pop("producer_offset", None),
            "consumer_offset": kw.pop("consumer_offset", None),
            "token_id": kw.pop("token_id", None),
            "unknown_code": kw.pop("unknown_code", None),
            "detail": kw.pop("detail", None),
        }
        entry.update(kw)
        obligations.append(entry)

    for rec in records:
        off = rec["offset"]
        sw = rec["swsb"]
        token = sw["sbid"]

        if sw["state"] == UNKNOWN:
            add("SWSB_UNMODELED", UNKNOWN, "GEN12-SWSB-ENCODING", consumer_offset=off,
                unknown_code="SWSB_FORM_OUTSIDE_SUBSET",
                detail="SWSB form outside the modelled Xe-LP single-distance-pipe subset")

        if token is not None and token["func"] in (".src", ".dst"):
            live = tokens.get(token["id"])
            if live is None:
                add("TOKEN_WAIT_UNBOUND", UNKNOWN, "TOKEN-WAIT-UNBOUND", consumer_offset=off,
                    token_id=token["id"], unknown_code="TOKEN_WAIT_UNBOUND",
                    detail="No token producer inside the bounded program; incoming token state unknown")
            elif token["func"] == ".dst":
                if live["response_state"] != KNOWN:
                    live["completion_unknown"] = True
                    add("DST_WAIT", UNKNOWN, "K5", producer_offset=live["producer_offset"],
                        consumer_offset=off, token_id=token["id"],
                        response_length_state=live["response_state"],
                        unknown_code="RESPONSE_LENGTH_UNKNOWN",
                        detail="Producer response length is missing/UNKNOWN; destination-wait completion cannot be decided")
                elif live.get("contradiction"):
                    live["completion_unknown"] = True
                    add("DST_WAIT", UNKNOWN, "D2", producer_offset=live["producer_offset"],
                        consumer_offset=off, token_id=token["id"],
                        unknown_code="NULL_DEST_NONZERO_RLEN_CONTRADICTION",
                        cross_field_state="CONTRADICTS_D2_NULL_DEST_RLEN_GT_0",
                        detail="D2 contradiction: null destination with RLEN>0; destination-wait completion cannot be KNOWN")
                elif live.get("dest_unknown"):
                    live["completion_unknown"] = True
                    add("DST_WAIT", UNKNOWN, "D2", producer_offset=live["producer_offset"],
                        consumer_offset=off, token_id=token["id"],
                        unknown_code="RESPONSE_DESTINATION_UNKNOWN",
                        cross_field_state="RESPONSE_DESTINATION_UNKNOWN",
                        detail="Producer response destination is unknown; D2 cross-field consistency cannot be checked")
                elif live["has_response"]:
                    live["dst_complete"] = True
                    add("DST_WAIT", KNOWN, "K1", producer_offset=live["producer_offset"],
                        consumer_offset=off, token_id=token["id"], evidence=["K1"],
                        detail="Explicit $N.dst wait for write-back of a response SEND")
                else:
                    live["completion_unknown"] = True
                    add("DST_WAIT", UNKNOWN, "K5", producer_offset=live["producer_offset"],
                        consumer_offset=off, token_id=token["id"],
                        unknown_code="NULL_RESPONSE_DST_WAIT_UNRESOLVED",
                        detail="No-response SEND destination-wait completion is not established by the pinned specification")
            else:  # ".src"
                live["src_complete"] = True
                add("SRC_WAIT", KNOWN, "K1", producer_offset=live["producer_offset"],
                    consumer_offset=off, token_id=token["id"], evidence=["K1"],
                    detail="Explicit $N.src wait for source-read of the token producer")

        if rec["opcode"] == "sync" and rec.get("subop") not in (None, "nop"):
            add("SYNC_UNMODELED", UNKNOWN, "SYNC-UNMODELED", consumer_offset=off,
                unknown_code="SYNC_FORM_UNMODELED",
                detail="SYNC sub-op outside the modelled token subset; no guessed implicit fence")

        if rec["is_send"]:
            family = rec["family"]
            rstate, rlen = rec["response_state"], rec["response_len"]
            p_states = rec["payload_states"]
            p_lens = rec["payload_lengths"]
            r_null = rec.get("response_is_null")
            # D2: a null destination requires RLEN==0.  A null destination with
            # RLEN>0 is a cross-field contradiction and cannot be KNOWN/proven.
            contradiction = (rstate == KNOWN and rlen is not None and rlen > 0 and r_null is True)
            dest_unknown = (rstate == KNOWN and rlen is not None and rlen > 0 and r_null is None)
            has_response = (rstate == KNOWN and rlen is not None and rlen > 0 and r_null is False)

            if token is None or token["func"] != "":
                add("SEND_TOKEN_MISSING", UNKNOWN, "SEND-TOKEN-MISSING", consumer_offset=off,
                    unknown_code="SEND_TOKEN_MISSING",
                    detail="Asynchronous SEND has no modelled SBID set")
            else:
                prev = tokens.get(token["id"])
                if prev is not None:
                    if prev["dst_complete"]:
                        # K2 is IGA_IMPL only; it can never establish a KNOWN
                        # hardware rule.  Re-use remains undecided.
                        add("SBID_REUSE", UNKNOWN, "K2", evidence=["IGA_IMPL", "K2"],
                            producer_offset=prev["producer_offset"], consumer_offset=off,
                            token_id=token["id"],
                            unknown_code="SBID_REUSE_HARDWARE_RULE_UNPROVEN",
                            detail="Previous $N.dst wait was discharged, but the hardware re-use rule is IGA-implementation-only")
                    else:
                        add("SBID_REUSE", UNKNOWN, "K3", evidence=["IGA_IMPL", "K3"],
                            producer_offset=prev["producer_offset"], consumer_offset=off,
                            token_id=token["id"],
                            unknown_code="SBID_REUSE_SYNC_UNPROVEN",
                            detail="SBID re-used while still live; implicit re-use synchronisation has only implementation evidence, not an independently sourced hardware rule")
                tokens[token["id"]] = {
                    "producer_offset": off, "has_response": has_response,
                    "response_state": rstate, "response_len": rlen,
                    "response_is_null": r_null,
                    "contradiction": contradiction, "dest_unknown": dest_unknown,
                    "src_complete": False, "dst_complete": False,
                    "completion_unknown": False, "family": family,
                }
                add("SBID_SET", KNOWN, "K1", producer_offset=off, token_id=token["id"],
                    evidence=["K1"], detail="SEND allocates SBID token %d" % token["id"])

            # Payload: only a fully KNOWN length set may decide whether payload
            # exists; any missing/unknown fact keeps the obligation explicit.
            if all(s == KNOWN for s in p_states):
                total = sum(v for v in p_lens if v is not None)
                if total > 0:
                    add("SOURCE_CONSUMPTION", UNKNOWN, "SEND-COMPLETION", producer_offset=off,
                        unknown_code="SOURCE_CONSUMPTION_UNRESOLVED",
                        detail="SEND payload consumption event is not established by the pinned evidence")
            else:
                add("SOURCE_CONSUMPTION", UNKNOWN, "SEND-COMPLETION", producer_offset=off,
                    unknown_code="PAYLOAD_LENGTH_UNKNOWN",
                    payload_length_states=list(p_states),
                    detail="Payload length fact is missing/UNKNOWN; payload consumption is NOT assumed to be zero-length")

            if rstate == KNOWN:
                if contradiction:
                    add("RESPONSE_WRITE", UNKNOWN, "D2", producer_offset=off,
                        evidence=["D1", "D2"], cross_field_state="CONTRADICTS_D2_NULL_DEST_RLEN_GT_0",
                        unknown_code="NULL_DEST_NONZERO_RLEN_CONTRADICTION",
                        detail="D2 contradiction: null destination with RLEN>0; response write cannot be KNOWN")
                elif dest_unknown:
                    add("RESPONSE_WRITE", UNKNOWN, "D2", producer_offset=off,
                        evidence=["D1", "D2"], cross_field_state="RESPONSE_DESTINATION_UNKNOWN",
                        unknown_code="RESPONSE_DESTINATION_UNKNOWN",
                        detail="Response destination is unknown; D2 cross-field consistency cannot be checked")
                elif rlen > 0:
                    add("RESPONSE_WRITE", KNOWN, "D2", producer_offset=off,
                        evidence=["D1", "D2"],
                        detail="RLEN>0 declares a response written back to the destination GRF")
                else:
                    extra = {}
                    detail = "RLEN==0 / null destination: no response expected"
                    if r_null is False:
                        # D2 only forbids null-dest + RLEN>0; it does not forbid
                        # a non-null destination with RLEN==0.  Do not guess.
                        extra["cross_field_state"] = "D2_NOT_APPLICABLE_NONNULL_DEST"
                        detail = "RLEN==0 with a known non-null destination; D2 does not forbid this"
                    add("NO_RESPONSE", KNOWN, "D2", producer_offset=off,
                        evidence=["D2"], detail=detail, **extra)
            else:
                add("RESPONSE_WRITE", UNKNOWN, "D1", producer_offset=off,
                    evidence=["D1", "D2"], response_length_state=rstate,
                    unknown_code="RESPONSE_LENGTH_UNKNOWN",
                    detail="Response-length fact is missing/UNKNOWN; must not be treated as a response or as NO_RESPONSE")

            add("TOKEN_SOURCE_COMPLETE", UNKNOWN, "SEND-COMPLETION", producer_offset=off,
                token_id=(token or {}).get("id"), unknown_code="TOKEN_SOURCE_COMPLETE_UNRESOLVED",
                detail="Token source-read completion is a distinct event from token allocation")
            if contradiction:
                add("TOKEN_DST_COMPLETE", UNKNOWN, "D2", producer_offset=off,
                    token_id=(token or {}).get("id"),
                    cross_field_state="CONTRADICTS_D2_NULL_DEST_RLEN_GT_0",
                    unknown_code="NULL_DEST_NONZERO_RLEN_CONTRADICTION",
                    detail="D2 contradiction: null destination with RLEN>0; token completion cannot be KNOWN")
            elif dest_unknown:
                add("TOKEN_DST_COMPLETE", UNKNOWN, "D2", producer_offset=off,
                    token_id=(token or {}).get("id"),
                    cross_field_state="RESPONSE_DESTINATION_UNKNOWN",
                    unknown_code="RESPONSE_DESTINATION_UNKNOWN",
                    detail="Response destination is unknown; token completion cannot be decided")
            elif rstate == KNOWN and rlen > 0:
                add("TOKEN_DST_COMPLETE", KNOWN, "K1", producer_offset=off,
                    token_id=(token or {}).get("id"), evidence=["K1", "D2"],
                    detail="Token write-back completion event for a response SEND")
            elif rstate == KNOWN and rlen == 0:
                add("TOKEN_DST_COMPLETE", UNKNOWN, "K5", producer_offset=off,
                    token_id=(token or {}).get("id"),
                    unknown_code="NULL_RESPONSE_DST_COMPLETE_UNRESOLVED",
                    detail="Token write-back completion event for a no-response SEND is unresolved")
            else:
                add("TOKEN_DST_COMPLETE", UNKNOWN, "K5", producer_offset=off,
                    token_id=(token or {}).get("id"), response_length_state=rstate,
                    unknown_code="RESPONSE_LENGTH_UNKNOWN",
                    detail="Token write-back completion cannot be decided without a KNOWN response length")

            if family in SIDE_EFFECT_FAMILIES:
                state, rule = SIDE_EFFECT_FAMILIES[family]
                add("SIDE_EFFECT", state, rule, producer_offset=off, family=family,
                    detail="Potential externally visible %s shared-function effect; absolute visibility unresolved" % family)
            else:
                add("SIDE_EFFECT", UNKNOWN, "UNMODELED-MESSAGE-FAMILY", producer_offset=off,
                    family=family, unknown_code="UNKNOWN_MESSAGE_FAMILY",
                    detail="Message family not modelled; external effect unknown")

        if rec["eot"]:
            add("EOT", UNKNOWN, "EOT-MESSAGE-SPECIFIC-COMPLETION", producer_offset=off,
                unknown_code="EOT_COMPLETION_UNRESOLVED",
                detail="EOT carrier is decoded, but message-specific termination/visibility is not established")

    obligations.sort(key=lambda o: (
        o["producer_offset"] if o["producer_offset"] is not None else o["consumer_offset"],
        EVENT_ORDER.index(o["event"]) if o["event"] in EVENT_ORDER else 99,
        o["consumer_offset"] if o["consumer_offset"] is not None else -1,
    ))
    counts = {}
    for o in obligations:
        counts[o["state"]] = counts.get(o["state"], 0) + 1
    unknown_codes = sorted({o["unknown_code"] for o in obligations if o["unknown_code"]})
    if message_ir_matched is None:
        message_ir_matched = not any(
            d.get("code") in {"MESSAGE_IR_ABSENT", "MESSAGE_IR_IDENTITY_MISMATCH"}
            for d in diagnostics)
    return {
        "schema_version": SCHEMA_VERSION,
        "shader_id": program.get("shader_id"),
        "platform": platform,
        "program_sha256": program.get("program_sha256"),
        "identity": {
            "shader_id": program.get("shader_id"),
            "platform": platform,
            "program_sha256": program.get("program_sha256"),
            "message_ir_matched": message_ir_matched,
            "diagnostics": diagnostics,
        },
        "instruction_count": len(records),
        "obligations": obligations,
        "counts": counts,
        "unknown_codes": unknown_codes,
        "known_rule_policy": "only SPEC-backed rules may establish KNOWN; IGA_IMPL-only K2/K3 never do",
        "model_scope": "Xe-LP single in-order ALU distance pipe + explicit SEND token event subset; not hardware validation",
        "module": "ga39.scheduling.completion",
        "hardware_validated": False,
    }


def build_obligations(ir, messages=None):
    """Build event obligations for one IR program, a bundle, or a list.

    ``ir`` must contain nodes (full IR) and/or messages (message IR).
    ``messages`` optionally supplies a message IR to enrich node-based programs.
    Message IR identity (shader_id + platform + program_sha256) must match the
    node program; mismatched IR is recorded as a diagnostic and never used.
    """
    supplied = _message_programs(ir)
    supplied.extend(_message_programs(messages))
    # de-duplicate identical identities again after merging both sources
    supplied = _message_programs({"programs": supplied})

    programs = []
    for prog in _iter_programs(ir, allow_messages=True):
        if prog.get("kind") == "messages":
            programs.append(obligations_for_program(prog))
        else:
            message_prog, diagnostics = _select_messages(prog, supplied)
            index = {msg.get("instruction_offset"): msg for msg in (message_prog or {}).get("messages", [])}
            result = obligations_for_program(prog, index, diagnostics,
                                             message_ir_matched=message_prog is not None)
            # Explicitly report message offsets that did not match any SEND node.
            matched = {r["offset"] for r in extract_instructions(prog, index) if r["message_present"]}
            missing_offsets = sorted(set(index) - matched)
            if missing_offsets:
                result["identity"]["diagnostics"].append({
                    "code": "MESSAGE_OFFSET_NOT_FOUND",
                    "detail": "message IR offsets did not match any SEND node in the node IR",
                    "offsets": missing_offsets,
                })
                result["identity"]["message_ir_matched"] = False
            programs.append(result)
    if len(programs) == 1:
        return programs[0]
    return {
        "schema_version": SCHEMA_VERSION,
        "bundle": True,
        "programs": programs,
        "shader_ids": [p["shader_id"] for p in programs],
        "module": "ga39.scheduling.completion",
        "hardware_validated": False,
    }


def _load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    parser = argparse.ArgumentParser(description="GA3.9 independent SEND/token event-obligation builder")
    parser.add_argument("--ir", required=True, help="GA3.8 candidate IR JSON (nodes) or message IR JSON (messages)")
    parser.add_argument("--messages", default=None, help="optional GA3.8 message IR to enrich a node IR")
    parser.add_argument("--out", default=None, help="write JSON here instead of stdout")
    args = parser.parse_args(argv)
    result = build_obligations(_load(args.ir), _load(args.messages) if args.messages else None)
    text = json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
