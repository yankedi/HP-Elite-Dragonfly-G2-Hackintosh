"""Check serialized derived IR consistency, not authenticate an external decoder.

The supported CLI always obtains IGA fields afresh from authenticated raw bytes.
These additional invariants prevent dropped derived accesses/graph edges from
silently weakening a checker. An arbitrary forged IGA decode still needs a new
native decode; this module does not pretend JSON can authenticate itself.
"""
from common import Rejected, frames, sha
from semantic_ir import make_instruction


def validate_instruction(node):
    d = node['iga_fields']
    accesses = node['register_access']['accesses']
    if d['op'] == 'mac' and not any(a['mode'] == 'READ' and a['file'] == 'ACC'
                                   and a['role'] == 'MAC_IMPLICIT_ACC' and a['state'] != 'NONE' for a in accesses):
        raise Rejected('MAC-IMPLICIT-ACC-READ-REQUIRED', 'MAC cannot omit its implicit accumulator read', d['pc'])
    if node['opcode'] != d['op'] or node['byte_range'][0] != d['pc']:
        raise Rejected('IR_DECODE_INCONSISTENT', 'Opcode/PC differs from native decoder fields', d['pc'])
    for access in accesses:
        if access['state'] in {'UNKNOWN', 'INVALID'} and (access['elements'] is not None or not access['symbolic_set']):
            raise Rejected('UNKNOWN_NOT_NONE', 'Unknown footprint requires a nonempty symbolic set and null elements', d['pc'])


def validate_program(program):
    for node in program['nodes']:
        validate_instruction(node)
    raw = b''.join(bytes.fromhex(n['raw_hex']) for n in program['nodes'])
    if sha(raw) != program['program_sha256'] or len(raw) != program['byte_length']:
        raise Rejected('IR_RAW_HASH_MISMATCH', 'Reassembled raw program does not match its identity')
    framing = frames(raw)
    if len(framing) != len(program['nodes']):
        raise Rejected('IR_RAW_FRAMING', 'Raw framing has a different node count')
    for (pc, size), node in zip(framing, program['nodes'], strict=True):
        if (node['source_identity']['program_sha256'] != program['program_sha256']
                or node['shader_id'] != program['shader_id'] or node['platform'] != program['platform']):
            raise Rejected('IR_NODE_IDENTITY', 'Node shader/platform/hash differs from its enclosing program', pc)
        if node['byte_range'] != [pc, pc + size] or node['length'] != size or node['compact'] != (size == 8):
            raise Rejected('IR_RAW_FRAMING', 'Declared node range differs from raw compact bit', pc)
        window = node['eu_window_range']
        evidence = {k: v for k, v in node['source_identity'].items() if k != 'program_sha256'}
        reconstructed = make_instruction(program['shader_id'], raw, program['platform'], node['iga_fields'],
                                         pc, size, window[0] - pc if window is not None else None, evidence).as_dict()
        for key in ['execution_semantics', 'explicit_operands', 'implicit_operands', 'register_access',
                    'control_effects', 'numeric_semantics', 'message_effects', 'unresolved_semantics', 'evidence']:
            if node[key] != reconstructed[key]:
                raise Rejected('IR_DERIVED_FIELD_MISMATCH', key, pc)
    return raw
