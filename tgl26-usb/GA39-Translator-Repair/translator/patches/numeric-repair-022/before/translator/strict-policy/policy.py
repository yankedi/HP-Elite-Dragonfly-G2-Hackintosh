"""Closed rule registry. Caller assertions never discharge unknown semantics.

Whole-shader admission is deliberately stronger than isolated instruction proof.
No pass-through fallback exists for an unsupported opcode or resource contract.
"""
from __future__ import annotations

PROVEN = 'PROVEN_UNDER_EXPLICIT_ASSUMPTIONS'
UNKNOWN = 'UNKNOWN_REJECTED'
REFUTED = 'REFUTED_WITH_COUNTEREXAMPLE'


def integer_mov_eligibility(ins):
    """Finite bit-copy theorem domain; no arithmetic/float/control assumptions."""
    if ins.get('op') != 'mov':
        return False, 'ISA_NUMERIC_RULE_NOT_IMPLEMENTED'
    if set(ins.get('opts', [])) - {'Compacted'}:
        return False, 'EXECUTION_OPTIONS_NOT_PROVEN'
    if any(ins.get(k) not in (None, False) for k in ('sat', 'fm', 'cond', 'pred')):
        return False, 'MODIFIED_OR_PREDICATED_MOV_NOT_PROVEN'
    if ins.get('es') not in {1, 2, 4, 8, 16, 32}:
        return False, 'EXECUTION_WIDTH_INVALID'
    operands = [ins.get('dst', {}), *ins.get('srcs', [])]
    if len(operands) != 2:
        return False, 'MOV_ARITY'
    types = {o.get('type') for o in operands}
    if len(types) != 1 or not types <= {'ud', 'd', 'uw', 'w'}:
        return False, 'NON_INTEGER_BITCOPY_OR_CONVERSION'
    for o in operands:
        if o.get('kind') != 'RD' or o.get('reg', {}).get('rn') != 'r':
            return False, 'NON_DIRECT_GRF'
        if set(o) - {'kind', 'reg', 'rgn', 'type'}:
            return False, 'OPERAND_MODIFIER_UNPROVEN'
        reg = o['reg']
        if set(reg) - {'rn', 'r', 'sr'}:
            return False, 'REGISTER_FIELD_UNPROVEN'
        if not 0 <= reg.get('r', 0) < 128:
            return False, 'REGISTER_RANGE'
    allowed = {'kind', 'id', 'pc', 'op', 'es', 'eo', 'wren', 'opts', 'dst', 'srcs'}
    if set(ins) - allowed:
        return False, 'UNKNOWN_INSTRUCTION_FIELD'
    return True, 'DIRECT_SAME_TYPE_INTEGER_MOV_BITCOPY'


def obligation(rule, node, target_nodes, unmet, evidence, assumptions=()):
    return {'rule': rule, 'status': UNKNOWN if unmet else PROVEN,
            'source_instruction': {'offset': node['byte_range'][0], 'raw_hex': node['raw_hex'],
                                   'fields': node['iga_fields']},
            'target_sequence': [{'offset': n['byte_range'][0], 'raw_hex': n['raw_hex'],
                                 'fields': n['iga_fields']} for n in target_nodes],
            'input_constraints': list(assumptions), 'output_constraints': ['No unproved deployable shader'],
            'temporary_grf': None,
            'liveness_proof': 'NO_TEMPORARY' if not node['numeric_semantics'].get('accumulator') else 'REQUIRED_UNPROVEN',
            'mask_predicate': node['execution_semantics'],
            'implicit_acc_state': node['implicit_operands'],
            'observable_outputs': ['GRF destinations', 'SEND side effects', 'architectural state'],
            'evidence': evidence, 'unmet_conditions': unmet}


def preflight(source, target, comparison, schedule):
    """Admit only complete programs whose every necessary obligation is proven.

    Current implementation supports isolated integer MOV lowering only. It has
    no whole-program EOT/ABI theorem and therefore cannot accept a full shader.
    All per-node reasons are returned, rather than stopping after its first NF.
    """
    target_by_pc = {n['byte_range'][0]: n for n in target['nodes']}
    witness = comparison['mapping_witness']
    obligations = []
    mapping = {e['source_offset']: e['target_byte_range'] for e in witness.get('entries', [])}
    for node in source['nodes']:
        pc = node['byte_range'][0]
        bounds = mapping.get(pc)
        targets = [n for off, n in target_by_pc.items() if bounds and bounds[0] <= off and n['byte_range'][1] <= bounds[1]]
        reasons = []
        if not targets:
            reasons.append('SOURCE_TARGET_MAPPING_MISSING')
        numeric = node['numeric_semantics']
        if numeric.get('nf') or numeric.get('accumulator'):
            reasons += ['NF_ACC_BIT_LEVEL_NUMERIC_MODEL', 'INTERMEDIATE_ROUNDING_FUSION_PACKING',
                        'MASK_PREDICATE_IMPLICIT_ACC_PRESERVATION', 'SCRATCH_LIVENESS_AND_EXTERNAL_ABI']
        if node['control_effects']['debug_switch'] or node['control_effects']['debug_effect']['state'] != 'NONE':
            reasons += ['DEBUG_SWITCH_ELIMINATION_UNKNOWN']
        if node['message_effects']['is_send']:
            reasons += ['SEND_CROSS_GENERATION_SEMANTIC_CONTRACT', 'RESOURCE_HEAP_AND_THREAD_PAYLOAD_ABI',
                        'MESSAGE_COMPLETION_AND_EOT_CONTRACT']
        eligible, reason = integer_mov_eligibility(node['iga_fields'])
        if not eligible:
            reasons.append(reason)
        obligations.append(obligation('GA39-CLOSED-TRANSLATOR-RULES', node, targets, reasons,
                                      ['GA38 raw anchored IR and twelve-layer results', 'GA39 finite integer bitcopy rule']))
    unresolved = [f for f in comparison['findings'] if f['status'] != 'STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS']
    return {'schema': 'ga39-proof-carrying-admission/v1', 'mode': 'strict', 'status': UNKNOWN,
            'shader_id': source['shader_id'], 'source_sha256': source['program_sha256'],
            'candidate_sha256': target['program_sha256'], 'obligations': obligations,
            'baseline_nonproven_evaluations': len(unresolved),
            'schedule_counts': schedule['counts'],
            'whole_program_obligations': ['WHOLE_SHADER_EOT_ABI_THEOREM_NOT_IMPLEMENTED'],
            'accepted_program': False, 'full_shader_emitted': False, 'hardware_validated': False,
            'artifact_class': 'NOT_FOR_HARDWARE',
            'note': 'Strict rejection is not a demonstrated semantic counterexample in the upstream bytes'}
