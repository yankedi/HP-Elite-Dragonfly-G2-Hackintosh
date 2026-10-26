"""Typed, raw-anchored EU IR. Symbolic/unknown footprints never mean no access.

Byte coordinates are physical register-file coordinates. `lane` identifies the
execution channel conditional on mask/predicate; differing lane labels NEVER
prove byte-disjointness. Execution channel offset does not advance a GRF base.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any, Literal

from common import Rejected, sha

Knowledge = Literal['KNOWN', 'CONDITIONAL', 'UNKNOWN', 'NONE', 'INVALID']
WIDTHS = {'ub': 1, 'b': 1, 'uw': 2, 'w': 2, 'hf': 2, 'ud': 4, 'd': 4,
          'f': 4, 'uq': 8, 'q': 8, 'df': 8}
SUPPORTED_ALU = {'mov', 'add', 'mul', 'mad', 'mac'}


@dataclass
class Fact:
    state: Knowledge
    value: Any = None
    evidence: list[str] = field(default_factory=list)
    condition: str | None = None


@dataclass
class Access:
    mode: Literal['READ', 'WRITE']
    file: str
    state: Knowledge
    # Half-open byte intervals, one per lane. None for a symbolic footprint.
    elements: list[dict] | None
    role: str
    condition: str
    symbolic_set: str | None = None
    evidence: list[str] = field(default_factory=lambda: ['EU-REGION', 'IGA-JSON'])


@dataclass
class Instruction:
    shader_id: str
    platform: str
    source_identity: dict
    byte_range: list[int]
    eu_window_range: list[int] | None
    raw_hex: str
    length: int
    compact: bool
    iga_fields: dict
    opcode: str
    execution_semantics: dict
    explicit_operands: dict
    implicit_operands: dict
    register_access: dict
    control_effects: dict
    message_effects: dict
    numeric_semantics: dict
    unresolved_semantics: list[dict]
    evidence: list[str]

    def as_dict(self):
        return asdict(self)


def unknown(code, impact, evidence):
    return {'code': code, 'impact': impact, 'evidence': evidence}


def symbolic(mode, file, role, expression, condition, state='UNKNOWN'):
    return Access(mode, file, state, None, role, condition, expression)


def operand_access(o: dict, mode: str, es: int, eo: int, condition: str, role: str) -> Access:
    kind = o.get('kind')
    if kind == 'IM':
        return Access(mode, 'immediate', 'NONE', [], role, 'no register access')
    reg = o.get('reg', {})
    if kind == 'AD':  # IGA send src0 address carrier; not ordinary indirect GRF.
        reg = o.get('areg', {})
    rn = reg.get('rn')
    if rn == 'null':
        return Access(mode, 'null', 'NONE', [], role, 'architectural null register')
    file = {'r': 'GRF', 'acc': 'ACC', 'f': 'FLAG', 'a': 'ADDRESS',
            'dbg': 'DBG', 'cr': 'CONTROL', 'sr': 'STATE'}.get(rn, 'ANY')
    r, sr = reg.get('r', 0), reg.get('sr', 0)
    if type(r) is not int or type(sr) is not int or not 0 <= r < 256 or not 0 <= sr < 256:
        raise Rejected('REGISTER_RANGE', repr(reg))
    if kind in {'DA', 'AD'}:
        length = o.get('len') if kind == 'DA' else o.get('alen')
        if file != 'GRF' or type(length) is not int or not 0 <= length <= 31:
            return symbolic(mode, file, role, 'message register range unknown', condition)
        if r + length > 128:
            return symbolic(mode, file, role, 'message register range exceeds Xe-LP GRF file', condition, 'INVALID')
        if not length:
            return Access(mode, file, 'NONE', [], role, 'zero-length message operand')
        # SEND carriers have whole-GRF payload/response, not scalar element types.
        return Access(mode, file, 'CONDITIONAL', [{'byte_start': 32 * r,
                      'byte_end': 32 * (r + length), 'lane': None}], role, condition,
                      evidence=['SEND-CARRIER', 'IGA-JSON'])
    if kind != 'RD' or file == 'ANY':
        return symbolic(mode, file, role, 'unresolved indirect/special register operand', condition)
    if file == 'ACC' and o.get('type') == 'nf':
        return symbolic(mode, 'ACC', role, f'acc{r} NF execution lanes [{eo},{eo + es}); internal bytes UNKNOWN',
                        condition)
    width = WIDTHS.get(o.get('type'))
    region = o.get('rgn', {})
    if width is None or 'h' not in region:
        return symbolic(mode, file, role, 'unknown type width or region', condition)
    if file not in {'GRF', 'ACC'}:
        return symbolic(mode, file, role, f'{rn}{r}.{sr} special register semantics', condition)
    h = region['h']
    if type(h) is not int or not 0 <= h <= 32:
        raise Rejected('REGION_RANGE', repr(region))
    if mode == 'READ':
        v, w = region.get('v'), region.get('w')
        if type(v) is not int or type(w) is not int or not 0 <= v <= 256 or not 1 <= w <= 32:
            return symbolic(mode, file, role, 'unknown source vertical stride/width', condition)
        indices = [(i // w) * v + (i % w) * h for i in range(es)]
    else:
        indices = [i * h for i in range(es)]
    # IGA represents subregisters in elements of the operand type (not bytes).
    start = 32 * r + width * sr
    elements = [{'lane': eo + i, 'byte_start': start + width * x,
                 'byte_end': start + width * (x + 1)} for i, x in enumerate(indices)]
    if file == 'GRF' and any(e['byte_end'] > 4096 for e in elements):
        return symbolic(mode, file, role, 'GRF footprint exceeds 128 registers', condition, 'INVALID')
    # ACC addressing is retained, but its physical packing/precision is not inferred from GRF size.
    if file == 'ACC':
        canonical_region = json.dumps(region, sort_keys=True, separators=(',', ':'))
        return symbolic(mode, file, role, f'acc{r}.{sr}, typed {o.get("type")}, region {canonical_region}, lanes {eo}:{eo+es}',
                        condition)
    return Access(mode, file, 'KNOWN' if condition == 'all instruction channels execute' else 'CONDITIONAL',
                  elements, role, condition)


def make_instruction(shader: str, data: bytes, platform: str, decoded: dict,
                     pc: int, size: int, window_offset: int | None, evidence: dict) -> Instruction:
    if decoded['pc'] != pc or len(data[pc:pc + size]) != size:
        raise Rejected('IR_ANCHOR', shader, pc)
    es, eo = decoded['es'], decoded.get('eo', 0)
    if type(es) is not int or es not in {1, 2, 4, 8, 16, 32} or type(eo) is not int or not 0 <= eo <= 31 or eo + es > 32:
        raise Rejected('EXECUTION_RANGE', repr((es, eo)), pc)
    pred = decoded.get('pred')
    opts = decoded.get('opts', [])
    condition = 'all instruction channels execute' if decoded.get('wren', False) and pred is None else 'execution mask and predicate active for channel'
    accesses = []
    implicit = []
    op = decoded['op']
    is_send = op.startswith('send')
    if 'dst' in decoded:
        accesses.append(operand_access(decoded['dst'], 'WRITE', es, eo, condition,
                                       'SEND_RESPONSE' if is_send else 'DST'))
    for index, operand in enumerate(decoded.get('srcs', [])):
        accesses.append(operand_access(operand, 'READ', es, eo, condition,
                        f'SEND_PAYLOAD{index}' if is_send and index < 2 else f'SRC{index}'))
    if is_send:
        sources = decoded.get('srcs', [])
        dynamic_desc = len(sources) < 4 or sources[-1].get('kind') != 'IM'
        dynamic_exdesc = len(sources) < 4 or sources[-2].get('kind') != 'IM'
        for index, access in enumerate(accesses):
            if ((dynamic_desc and access.role in {'SEND_PAYLOAD0', 'SEND_RESPONSE'})
                    or (dynamic_exdesc and access.role == 'SEND_PAYLOAD1')) and access.file != 'null':
                accesses[index] = symbolic(access.mode, access.file, access.role,
                    'Register carrier base decoded but runtime descriptor length unknown', condition)
    if not decoded.get('wren', False):
        implicit.append(symbolic('READ', 'EXEC_MASK', 'EXECUTION_MASK', f'channels {eo}:{eo+es}', 'instruction executes', 'CONDITIONAL'))
    if pred is not None:
        implicit.append(symbolic('READ', 'FLAG', 'PREDICATE', json.dumps(pred, sort_keys=True, separators=(',', ':')), 'predicate evaluated'))
    if decoded.get('fm') is not None or decoded.get('cond') is not None:
        implicit.append(symbolic('WRITE', 'FLAG', 'CONDITION_MODIFIER', 'condition modifier flag footprint', condition))
    if op == 'mac':
        implicit.append(symbolic('READ', 'ACC', 'MAC_IMPLICIT_ACC', f'implicit accumulator lanes {eo}:{eo+es}', condition))
    if op == 'mul' and any(o.get('type') in {'d', 'ud'} for o in decoded.get('srcs', [])):
        implicit.append(symbolic('WRITE', 'ACC', 'MUL_DW_FULL_PRECISION_ACC',
                                 'integer DW multiply full-precision implicit accumulator result; packing/control conditions unresolved', condition))
    if 'AccWrEn' in opts:
        implicit.append(symbolic('WRITE', 'ACC', 'ACC_WRITE_ENABLE', f'acc write lanes {eo}:{eo+es}', condition))
    if op in {'add', 'mul', 'mad', 'mac'}:
        implicit.append(symbolic('READ', 'CONTROL', 'FP_CONTROL', 'rounding/denormal/control mode', condition))
    if op not in SUPPORTED_ALU and not is_send and op != 'sync':
        implicit.extend([symbolic('READ', 'ANY', 'UNSUPPORTED_OPCODE', op, condition),
                         symbolic('WRITE', 'ANY', 'UNSUPPORTED_OPCODE', op, condition)])
    all_accesses = accesses + implicit
    unresolved = []
    for a in all_accesses:
        if a.state in {'UNKNOWN', 'INVALID'}:
            unresolved.append(unknown('ACCESS_' + a.state, a.role + ': ' + str(a.symbolic_set), a.evidence))
    has_nf = any(o.get('type') == 'nf' for o in [decoded.get('dst', {}), *decoded.get('srcs', [])])
    uses_acc = any(a.file == 'ACC' and a.state != 'NONE' for a in all_accesses)
    if uses_acc or has_nf:
        unresolved.append(unknown('NUMERIC_SEMANTICS_UNKNOWN',
            'Accumulator internal precision/packing, intermediate rounding and GRF substitution equivalence not proved', ['EU-ACC-NF']))
    unknown_keys = sorted(set(decoded) - {'kind', 'id', 'pc', 'op', 'subop', 'wren', 'es', 'eo', 'dst', 'srcs',
                                         'opts', 'regDist', 'sbid', 'comment', 'pred', 'fm', 'cond'})
    if unknown_keys:
        unresolved.append(unknown('UNMODELED_IGA_FIELDS', repr(unknown_keys), ['IGA-JSON']))
        all_accesses.extend([symbolic('READ', 'ANY', 'UNMODELED_IGA_FIELDS', repr(unknown_keys), condition),
                             symbolic('WRITE', 'ANY', 'UNMODELED_IGA_FIELDS', repr(unknown_keys), condition)])
    eot = 'EOT' in opts
    implicit_state = 'UNKNOWN' if any(a.state == 'UNKNOWN' for a in implicit) else ('CONDITIONAL' if implicit else 'NONE')
    return Instruction(shader, platform, {'program_sha256': sha(data), **evidence}, [pc, pc + size],
        [window_offset + pc, window_offset + pc + size] if window_offset is not None else None,
        data[pc:pc + size].hex(), size, size == 8, decoded, op,
        {'execution_size': asdict(Fact('KNOWN', es, ['IGA-JSON'])),
         'channel_offset': asdict(Fact('KNOWN', eo, ['IGA-JSON-DEFAULTS'])),
         'mask_control': asdict(Fact('KNOWN', 'NoMask' if decoded.get('wren', False) else 'Normal', ['IGA-JSON'])),
         'predicate': asdict(Fact('KNOWN' if pred is not None else 'NONE', pred, ['IGA-JSON'])),
         'flag_register': asdict(Fact('UNKNOWN' if pred is not None or decoded.get('fm') is not None else 'NONE',
                                    decoded.get('fm'), ['IGA-JSON'])),
         'saturate': asdict(Fact('KNOWN', decoded.get('dst', {}).get('sat', False), ['IGA-JSON']))},
        {'destination': decoded.get('dst'), 'sources': decoded.get('srcs', []),
         'state': 'KNOWN', 'scope': 'decoded operands, including type/region/modifier; not arithmetic equivalence'},
        {'state': implicit_state, 'accesses': [asdict(a) for a in implicit]},
        {'state': 'UNKNOWN' if any(a.state == 'UNKNOWN' for a in all_accesses) else 'CONDITIONAL',
         'accesses': [asdict(a) for a in all_accesses],
         'coordinate_system': 'physical byte footprint; lane labels are conditional, not alias exclusions'},
        {'eot': eot, 'options': opts, 'debug_switch': 'Switch' in opts,
         'debug_effect': asdict(Fact('UNKNOWN' if 'Switch' in opts else 'NONE', None, ['EU-DEBUG-SWITCH']))},
        {'state': 'CONDITIONAL' if is_send else 'NONE', 'is_send': is_send, 'eot': eot},
        {'state': 'UNKNOWN' if uses_acc or has_nf or op in {'add', 'mul', 'mad', 'mac'} else 'CONDITIONAL',
         'nf': has_nf, 'accumulator': uses_acc,
         'rounding_mode': asdict(Fact('UNKNOWN', None, ['THREAD-CONTROL-STATE-MISSING'])),
         'fused_and_intermediate_precision': asdict(Fact('UNKNOWN', None, ['EU-ACC-NF']))},
        unresolved, ['IGA-JSON', 'EU-REGION'])


def build_program(shader: str, data: bytes, decoded: dict, window_offset=None) -> dict:
    nodes = [make_instruction(shader, data, decoded['platform'], ins, pc, n, window_offset,
             {'tool': decoded['tool'], 'iga_json_sha256': decoded['json_sha256']}).as_dict()
             for ins, (pc, n) in zip(decoded['instructions'], decoded['frames'], strict=True)]
    eots = [n['byte_range'][0] for n in nodes if n['control_effects']['eot']]
    if not eots or eots != [nodes[-1]['byte_range'][0]]:
        raise Rejected('EOT_FRAMING', 'Expected a single EOT as the last bounded instruction')
    return {'schema_version': 1, 'shader_id': shader, 'platform': decoded['platform'],
            'program_sha256': sha(data), 'byte_length': len(data), 'nodes': nodes,
            'coverage': 'All raw instructions represented; unknown fields remain explicit',
            'hardware_validated': False}
