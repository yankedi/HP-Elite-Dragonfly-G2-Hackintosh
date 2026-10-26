"""Executable conservative byte-overlap hazard graph for bounded straight-line EU.

Includes transitive hazards; it is not a minimal SSA graph. Mask/predicate
uncertainty and symbolic register footprints cannot create independence proofs.
"""
from __future__ import annotations
from common import MAX_INSTRUCTIONS, Rejected


def overlap(a: dict, b: dict) -> dict:
    if a['state'] == 'NONE' or b['state'] == 'NONE':
        return {'relation': 'INDEPENDENT_PROVEN', 'reason': 'architectural no-access', 'overlap_bytes': []}
    if a['file'] != b['file'] and 'ANY' not in {a['file'], b['file']}:
        return {'relation': 'INDEPENDENT_PROVEN', 'reason': 'distinct physical register files', 'overlap_bytes': []}
    if a['elements'] is None or b['elements'] is None:
        return {'relation': 'UNKNOWN', 'reason': 'symbolic footprint can overlap; do not assume disjoint', 'overlap_bytes': None}
    intersections = []
    for x in a['elements']:
        for y in b['elements']:
            lo, hi = max(x['byte_start'], y['byte_start']), min(x['byte_end'], y['byte_end'])
            if lo < hi:
                item = {'byte_start': lo, 'byte_end': hi, 'producer_lane': x['lane'], 'consumer_lane': y['lane']}
                if item not in intersections:
                    intersections.append(item)
    if not intersections:
        return {'relation': 'INDEPENDENT_PROVEN', 'reason': 'byte-disjoint (not merely lane-disjoint)', 'overlap_bytes': []}
    must = a['state'] == b['state'] == 'KNOWN'
    return {'relation': 'MUST_DEPEND' if must else 'MAY_DEPEND',
            'reason': 'physical byte overlap; execution predicates/masks retained', 'overlap_bytes': intersections}


def kind(a, b):
    return {('WRITE', 'READ'): 'RAW', ('READ', 'WRITE'): 'WAR',
            ('WRITE', 'WRITE'): 'WAW'}.get((a['mode'], b['mode']))


def constraint(producer, consumer, a, b, hazard):
    if producer['message_effects']['is_send']:
        if a['role'] == 'SEND_RESPONSE' and hazard in {'RAW', 'WAW'}:
            return 'SEND_RESPONSE_COMPLETE_BEFORE_CONSUMER'
        if a['role'].startswith('SEND_PAYLOAD') and hazard == 'WAR':
            return 'SEND_PAYLOAD_CONSUMED_BEFORE_OVERWRITE'
    if consumer['message_effects']['is_send'] and b['role'].startswith('SEND_PAYLOAD') and hazard == 'RAW':
        return 'PAYLOAD_PRODUCER_COMPLETE_BEFORE_SEND'
    return 'REGISTER_' + hazard + '_ORDER'


def build_graph(program: dict) -> dict:
    nodes = program['nodes']
    if len(nodes) > MAX_INSTRUCTIONS:
        raise Rejected('INSTRUCTION_RESOURCE_BOUND', f'At most {MAX_INSTRUCTIONS} graph nodes')
    edges, pairs, waits = [], [], []
    for j, consumer in enumerate(nodes):
        for i in range(j):
            producer = nodes[i]
            pair_edges = []
            for a in producer['register_access']['accesses']:
                for b in consumer['register_access']['accesses']:
                    hazard = kind(a, b)
                    if hazard is None:
                        continue
                    relation = overlap(a, b)
                    if relation['relation'] == 'INDEPENDENT_PROVEN':
                        continue
                    # A potential intervening overwrite prevents claiming a
                    # definite reaching-value dependence for an old producer.
                    if relation['relation'] == 'MUST_DEPEND' and hazard == 'RAW':
                        if any(overlap(w, b)['relation'] != 'INDEPENDENT_PROVEN'
                               for mid in nodes[i + 1:j]
                               for w in mid['register_access']['accesses'] if w['mode'] == 'WRITE'):
                            relation = {**relation, 'relation': 'MAY_DEPEND',
                                        'reason': 'intervening write may kill the old reaching definition'}
                    item = {'producer_offset': producer['byte_range'][0],
                            'consumer_offset': consumer['byte_range'][0], 'kind': hazard,
                            'producer_access': a, 'consumer_access': b,
                            **relation, 'constraint': constraint(producer, consumer, a, b, hazard),
                            'evidence': ['EU-REGION', 'BYTE-INTERSECTION', *a['evidence'], *b['evidence']],
                            'evidence_grade': 'SYMBOLIC' if relation['relation'] == 'UNKNOWN' else 'STATIC_FOOTPRINT'}
                    pair_edges.append(len(edges))
                    edges.append(item)
                    if len(edges) > 100000:
                        raise Rejected('DEPENDENCY_RESOURCE_BOUND', 'At most 100000 conservative hazard edges')
                    if item['constraint'].startswith('SEND_'):
                        waits.append(len(edges) - 1)
            pair_status = ('UNKNOWN' if any(edges[k]['relation'] == 'UNKNOWN' for k in pair_edges)
                           else 'MUST_DEPEND' if any(edges[k]['relation'] == 'MUST_DEPEND' for k in pair_edges)
                           else 'MAY_DEPEND' if pair_edges else 'INDEPENDENT_PROVEN')
            pairs.append({'producer_offset': producer['byte_range'][0], 'consumer_offset': consumer['byte_range'][0],
                          'relation': pair_status, 'edge_indices': pair_edges,
                          'scope': 'modeled explicit+implicit register effects; not external resources'})
    messages = [n for n in nodes if n['message_effects']['is_send']]
    eot = nodes[-1]['byte_range'][0]
    # Payload consumed, destination ready, side-effect globally visible, and
    # thread termination are deliberately separate events. No universal EOT
    # fence is fabricated when the precise message/EOT rule has not been proved.
    completion = [{'instruction_offset': n['byte_range'][0],
                   'events': ['SUBMITTED', 'PAYLOAD_CONSUMED', 'RESPONSE_WRITTEN',
                              'SIDE_EFFECT_COMPLETE', 'TOKEN_RELEASED'],
                   'eot_offset': eot,
                   'eot_requirement': 'UNKNOWN_MESSAGE_SPECIFIC_EOT_COMPLETION',
                   'evidence': ['SEND-COMPLETION', 'EOT-COMPLETION-UNRESOLVED']}
                  for n in messages]
    return {'schema_version': 1, 'shader_id': program['shader_id'], 'platform': program['platform'],
            'program_sha256': program['program_sha256'],
            'nodes': [{'offset': n['byte_range'][0], 'raw_hex': n['raw_hex'], 'opcode': n['opcode']}
                      for n in nodes], 'edges': edges, 'pairs': pairs, 'necessary_wait_edge_indices': waits,
            'message_completion': completion,
            'graph_kind': 'conservative all-pairs hazard graph, including transitive constraints',
            'unknown_dependency_count': sum(e['relation'] == 'UNKNOWN' for e in edges),
            'hardware_validated': False}
