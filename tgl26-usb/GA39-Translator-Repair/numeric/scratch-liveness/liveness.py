"""Conservative byte liveness, independently implemented from GA38 hazard graphs.

This is a projection of *known* GRF accesses, never an ABI allocation proof.
Predicated/masked writes do not kill may-live bytes. Lane labels are recorded
but never establish physical-byte disjointness. Symbolic accesses stay unknown.
"""
from __future__ import annotations

GRF_BYTES = 4096


def intervals(values):
    values = sorted(set(values))
    result = []
    for value in values:
        if result and result[-1][1] == value:
            result[-1][1] += 1
        else:
            result.append([value, value + 1])
    return result


def footprint(access):
    """Unknown is None; architectural NONE is the empty set."""
    if access['state'] == 'NONE':
        return set()
    if access['state'] not in {'KNOWN', 'CONDITIONAL'} or access.get('elements') is None:
        return None
    result = set()
    for element in access['elements']:
        start, end = element['byte_start'], element['byte_end']
        if type(start) is not int or type(end) is not int or not 0 <= start <= end <= GRF_BYTES:
            raise ValueError('Invalid GRF byte range')
        result.update(range(start, end))
    return result


def accesses(node):
    value = node['register_access']
    # GA38 has one combined, explicit+implicit access array.
    return value['accesses']


def analyze(program, live_out=()):
    nodes = program['nodes']
    if not nodes or len(nodes) > 256:
        raise ValueError('Expected bounded nonempty straight-line program')
    live = set(live_out)
    if any(type(b) is not int or not 0 <= b < GRF_BYTES for b in live):
        raise ValueError('Invalid live-out byte')
    records = []
    symbolic = []
    ignored = []
    for node in reversed(nodes):
        reads, kills, writes = set(), set(), set()
        for access in accesses(node):
            if access['file'] not in {'GRF', 'ANY'}:
                ignored.append({'offset': node['byte_range'][0], 'access': access})
                continue
            bits = footprint(access)
            if access['file'] == 'ANY' or bits is None:
                symbolic.append({'offset': node['byte_range'][0], 'access': access})
                continue
            if access['mode'] == 'READ':
                reads |= bits
            elif access['mode'] == 'WRITE':
                writes |= bits
                # Only truly unconditional exact writes kill a may-live value.
                fields = node.get('iga_fields', {})
                # A display string alone never establishes must-execute. The
                # caller must supply structured execution evidence as in GA38
                # raw-anchored IR; absent/masked/predicated evidence cannot kill.
                if (access['state'] == 'KNOWN' and fields.get('wren') is True
                        and fields.get('pred') is None
                        and type(fields.get('es')) is int and 1 <= fields['es'] <= 32):
                    kills |= bits
            else:
                raise ValueError('Unknown access mode')
        after = set(live)
        live = reads | (live - kills)
        records.append({'offset': node['byte_range'][0], 'raw_hex': node['raw_hex'],
                        'live_before': intervals(live), 'live_after': intervals(after),
                        'reads': intervals(reads), 'writes': intervals(writes),
                        'must_kill': intervals(kills)})
    records.reverse()
    ranges = []
    for byte in sorted({b for r in records for lo, hi in r['live_before'] + r['live_after'] for b in range(lo, hi)}):
        active = [r['offset'] for r in records if any(lo <= byte < hi for lo, hi in r['live_before'] + r['live_after'])]
        ranges.append({'byte': byte, 'instruction_offsets': active})
    return {'schema': 'ga39-known-grf-liveness/v1', 'shader_id': program['shader_id'],
            'program_sha256': program['program_sha256'], 'records': records,
            'live_in_known_projection': intervals(live), 'per_byte_live_ranges': ranges,
            'symbolic_grf_accesses': list(reversed(symbolic)),
            'out_of_projection_accesses': list(reversed(ignored)),
            'kill_evidence': 'Structured iga_fields wren=true and pred=null; caller must authenticate derived IR to bytes',
            'external_thread_payload_abi': 'UNKNOWN', 'external_live_out_abi': 'UNKNOWN',
            'lane_policy': 'Physical byte union; conditional writes never kill',
            'scope': 'Known explicit/message GRF may-liveness projection; not full ABI proof'}


def scratch_contract(source, target, register, mapping):
    """mapping: {target_offset: source_offset}, checked externally against raw IR.

    Live interference is a conservative MAY conflict, not a semantic counterexample.
    A definite direct source access collision is a static allocation counterexample.
    """
    if type(register) is not int or not 0 <= register < 128:
        raise ValueError('Scratch GRF outside Xe-LP file')
    source_result, target_result = analyze(source), analyze(target)
    scratch = set(range(register * 32, (register + 1) * 32))
    source_nodes = {n['byte_range'][0]: n for n in source['nodes']}
    source_records = {r['offset']: r for r in source_result['records']}
    touches, conflicts, edges = [], [], []
    definitions = []
    for node in target['nodes']:
        pc = node['byte_range'][0]
        relevant = []
        for access in accesses(node):
            if access['file'] != 'GRF':
                continue
            bits = footprint(access)
            if bits is not None and bits & scratch:
                relevant.append({'mode': access['mode'], 'role': access['role'],
                                 'bytes': intervals(bits & scratch), 'condition': access['condition'],
                                 'lanes': [e['lane'] for e in access['elements']]})
        if not relevant:
            continue
        spc = mapping.get(pc)
        if spc not in source_nodes:
            raise ValueError('Scratch touch has no valid source mapping')
        touches.append({'target_offset': pc, 'source_offset': spc, 'accesses': relevant})
        source_node = source_nodes[spc]
        for access in accesses(source_node):
            if access['file'] != 'GRF':
                continue
            bits = footprint(access)
            if bits is not None and scratch & bits:
                conflicts.append({'kind': 'DIRECT_SOURCE_COLLISION', 'source_offset': spc,
                                  'target_offset': pc, 'bytes': intervals(scratch & bits)})
        record = source_records[spc]
        live = {b for lo, hi in record['live_before'] + record['live_after'] for b in range(lo, hi)}
        if scratch & live:
            edges.append({'scratch_register': register, 'source_offset': spc, 'target_offset': pc,
                          'kind': 'MAY_LIVE_INTERFERENCE', 'bytes': intervals(scratch & live)})
        # EU operands are read before this instruction's destination definition.
        for item in relevant:
            if item['mode'] == 'READ':
                for producer in definitions:
                    edges.append({'producer': producer, 'consumer': pc,
                                  'kind': 'SCRATCH_MAY_REACHING_DEFINITION', 'bytes': item['bytes']})
        if any(item['mode'] == 'WRITE' for item in relevant):
            definitions.append(pc)
    unresolved = ['THREAD_PAYLOAD_EXTERNAL_LIVE_IN', 'TARGET_RESOURCE_GRF_LIMIT',
                  'SOURCE_TO_SCRATCH_NUMERIC_EQUIVALENCE', 'MASKED_TEMPORARY_VALUE_PRESERVATION']
    if source_result['symbolic_grf_accesses'] or target_result['symbolic_grf_accesses']:
        unresolved.append('SYMBOLIC_OR_INDIRECT_GRF_ACCESS')
    if edges:
        unresolved.append('CONSERVATIVE_REACHING_DEFINITION_AND_INTERFERENCE')
    return {'schema': 'ga39-scratch-contract/v1', 'shader_id': source['shader_id'],
            'scratch_register': register, 'scratch_byte_range': [register * 32, (register + 1) * 32],
            'touches': touches, 'interference_graph': edges, 'static_collisions': conflicts,
            'known_source_projection': source_result, 'known_target_projection': target_result,
            'allocation_status': 'REFUTED_WITH_COUNTEREXAMPLE' if conflicts else 'UNKNOWN_REJECTED',
            'unmet_obligations': unresolved, 'hardware_validated': False}
