"""Proof-carrying *rejection* of every actual explicit/implicit ACC operation.

No external assertion/certificate can promote UNKNOWN in this version. All
operand replacements are recorded separately from the unproved numeric theorem.
"""
from __future__ import annotations

NUMERIC_OBLIGATIONS = [
    'NF_INTERNAL_REPRESENTATION', 'ACC_PACK_UNPACK', 'INTERMEDIATE_PRECISION',
    'ROUNDING_MODE', 'MAD_MAC_FUSION', 'DENORMAL_FTZ_DAZ', 'SATURATE',
    'SIMD_WIDTH_AND_CHANNELS', 'EXECUTION_MASK', 'PREDICATE', 'IMPLICIT_ACC_STATE',
    'EOT_OBSERVABLE_NUMERIC_OUTPUT',
]


def prove(source, target, witness, scratch_paths=None):
    if witness.get('source_sha256') != source['program_sha256'] or witness.get('candidate_sha256') != target['program_sha256']:
        raise ValueError('Lowering witness identity mismatch')
    source_nodes = {n['byte_range'][0]: n for n in source['nodes']}
    targets = target['nodes']
    entries = witness.get('entries', [])
    by_source = {}
    covered = set()
    for entry in entries:
        pc, (lo, hi) = entry['source_offset'], entry['target_byte_range']
        if pc in by_source or pc not in source_nodes:
            raise ValueError('Invalid/duplicate source mapping')
        mapped = [n for n in targets if lo <= n['byte_range'][0] and n['byte_range'][1] <= hi]
        if not mapped or mapped[0]['byte_range'][0] != lo or mapped[-1]['byte_range'][1] != hi:
            raise ValueError('Target mapping boundary mismatch')
        for n in mapped:
            if n['byte_range'][0] in covered:
                raise ValueError('Target mapping overlap')
            covered.add(n['byte_range'][0])
        by_source[pc] = mapped
    if set(by_source) != set(source_nodes) or len(covered) != len(targets):
        raise ValueError('Lowering mapping incomplete')
    results = []
    for pc, node in source_nodes.items():
        if not (node['numeric_semantics'].get('accumulator') or node['numeric_semantics'].get('nf')):
            continue
        mapped = by_source[pc]
        replacements = []
        sf = node['iga_fields']
        for target_node in mapped:
            tf = target_node['iga_fields']
            source_ops = [('DST', sf.get('dst', {})), *[(f'SRC{i}', o) for i, o in enumerate(sf.get('srcs', []))]]
            target_ops = dict([('DST', tf.get('dst', {})), *[(f'SRC{i}', o) for i, o in enumerate(tf.get('srcs', []))]])
            for role, operand in source_ops:
                if operand.get('reg', {}).get('rn') != 'acc' and operand.get('type') != 'nf':
                    continue
                destination = target_ops.get(role, {})
                if destination.get('reg', {}).get('rn') == 'r':
                    replacements.append({'role': role, 'source_operand': operand, 'target_operand': destination,
                        'target_offset': target_node['byte_range'][0],
                        'temporary_grf': destination['reg'].get('r', 0),
                        'target_footprint': [a for a in target_node['register_access']['accesses'] if a['role'] == role]})
        results.append({'rule': 'GA39-NF-ACC-PROOF-REQUIRED', 'status': 'UNKNOWN_REJECTED',
            'shader_id': source['shader_id'], 'source_program_sha256': source['program_sha256'],
            'target_program_sha256': target['program_sha256'],
            'source_instruction': {'offset': pc, 'raw_hex': node['raw_hex'], 'fields': sf},
            'target_sequence': [{'offset': n['byte_range'][0], 'raw_hex': n['raw_hex'], 'fields': n['iga_fields']} for n in mapped],
            'numeric_semantics': {name: {'state': 'UNKNOWN', 'value': None} for name in NUMERIC_OBLIGATIONS},
            'NF_NUMERIC_MODEL': 'UNKNOWN', 'operand_replacements': replacements,
            'input_constraints': ['Need exact generation-specific ACC/NF and thread FP-control contract'],
            'output_constraints': ['No NF precision loss or implicit-ACC change unless proved'],
            'liveness_proof': {'state': 'UNKNOWN', 'known_projection': (scratch_paths or {}).get(source['shader_id']),
                               'external_thread_payload_abi': 'UNKNOWN'},
            'mask_predicate_preservation': {'state': 'CONDITIONAL', 'source': node['execution_semantics'],
                                           'target': [n['execution_semantics'] for n in mapped]},
            'implicit_acc_state': {'source': node['implicit_operands'], 'target': [n['implicit_operands'] for n in mapped]},
            'observable_outputs': ['reaching GRF writes', 'actual SEND payloads and side effects before EOT'],
            'specification_basis': ['reference/numeric-debug (independent evidence inventory)',
                                    'GA38 reports/NF-ACC-SCRATCH-AUDIT.md; source/target raw anchored IR'],
            'unmet_conditions': NUMERIC_OBLIGATIONS + (['SCRATCH_LIVENESS_EXTERNAL_ABI'] if replacements else []),
            'smallest_next_evidence': 'Bit-level Gen11 ACC/NF specification plus original FP-control and payload ABI',
            'hardware_validated': False})
    return {'schema': 'ga39-nf-acc-proof-obligations/v1', 'shader_id': source['shader_id'],
            'proofs': results, 'status': 'UNKNOWN_REJECTED', 'NF_NUMERIC_MODEL': 'UNKNOWN'}
