"""Gen12 Xe-LP single-in-order-pipe + explicit SEND token subset checker.

This is an event-order proof under explicit ISA assumptions, not a latency
simulator. Unknown variable pipelines, symbolic side effects, SYNC forms and
message-specific EOT visibility remain UNKNOWN_SCHEDULING_SEMANTICS.
"""
from __future__ import annotations

import re
from common import Rejected
from integrity import validate_program
from dependency_graph import build_graph

CHECKED = 'STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS'
COUNTER = 'COUNTEREXAMPLE'
UNKNOWN = 'UNKNOWN'
INORDER = {'mov', 'add', 'mul', 'mad', 'mac'}


def decode_swsb(node):
    d = node['iga_fields']
    distance = d.get('regDist')
    match = re.fullmatch(r'@(\d+)', distance or '')
    regdist = int(match[1]) if match else None
    sbid = d.get('sbid')
    valid_sbid = (sbid is None or isinstance(sbid, dict) and type(sbid.get('id')) is int
                  and 0 <= sbid['id'] < 16 and sbid.get('func') in {'', '.src', '.dst'})
    return {'encoded_byte': int.from_bytes(bytes.fromhex(node['raw_hex'])[:4], 'little') >> 8 & 0xFF,
            'raw_iga_regDist': distance, 'regDist': regdist,
            'sbid': sbid, 'distance_pipe': 'single in-order pipe' if match else None,
            'state': 'KNOWN' if valid_sbid and (distance is None or match and 1 <= regdist <= 7) else 'UNKNOWN',
            'evidence': ['IGA-JSON', 'GEN12-SWSB-ENCODING']}


def check(program, graph):
    if program['platform'] != '12p1':
        raise Rejected('PLATFORM_UNSUPPORTED', 'Gen12 schedule checker requires 12p1 target IR')
    validate_program(program)
    if graph != build_graph(program):
        raise Rejected('DEPENDENCY_GRAPH_INTEGRITY', 'Graph differs from the complete IR-derived hazard set')
    nodes = program['nodes']
    bypc = {n['byte_range'][0]: i for i, n in enumerate(nodes)}
    annotations = [decode_swsb(n) for n in nodes]
    constraints = []
    # Ordered index counts only in-order ALU instructions; SEND is asynchronous.
    inorder = []
    completed_rank = -1
    rank = {}
    complete_at = []
    token_state = {}
    send_events = {}
    events = []

    def add(status, rule, detail, producer=None, consumer=None, edge=None):
        constraints.append({'status': status, 'rule': rule, 'detail': detail,
            'producer_offset': producer, 'consumer_offset': consumer, 'edge_index': edge,
            'necessary_assumptions': ['Xe-LP single in-order ALU pipeline',
                'IGA-decoded SWSB field semantics; masked/predicated execution may suppress events',
                'Destination wait covers token destination completion; side-effect visibility is separate'],
            'evidence': [rule], 'unknown_code': 'UNKNOWN_SCHEDULING_SEMANTICS' if status == UNKNOWN else None})

    for i, n in enumerate(nodes):
        pc = n['byte_range'][0]
        sw = annotations[i]
        d = n['iga_fields']
        if sw['state'] == 'UNKNOWN':
            add(UNKNOWN, 'GEN12-SWSB-ENCODING', 'SWSB form outside modeled single-pipe subset', consumer=pc)
        if sw['state'] == 'KNOWN' and sw['regDist'] is not None:
            prior_rank = len(inorder) - sw['regDist']
            if prior_rank >= 0:
                completed_rank = max(completed_rank, prior_rank)
                events.append({'offset': pc, 'event': 'INORDER_DISTANCE_WAIT', 'completed_through_offset': inorder[prior_rank]})
            else:
                add(UNKNOWN, 'REGDIST-UNDERFLOW', 'Distance refers before this bounded program; incoming state unknown', consumer=pc)
        token = sw['sbid'] if sw['state'] == 'KNOWN' else None
        if token is not None and sw['state'] == 'KNOWN' and token['func'] in {'.src', '.dst'}:
            old = token_state.get(token['id'])
            if old is None:
                add(UNKNOWN, 'TOKEN-WAIT-UNBOUND', 'No token producer in bounded program (incoming token state unknown)', consumer=pc)
            else:
                if token['func'] == '.dst' and not old['has_response']:
                    old['completion_unknown'] = True
                    add(UNKNOWN, 'NULL-RESPONSE-DST-WAIT',
                        'No-response SEND destination-wait completion is not established by the pinned specification',
                        old['producer_offset'], pc)
                else:
                    old['src_complete'] = True
                    if token['func'] == '.dst':
                        old['dst_complete'] = True
                events.append({'offset': pc, 'event': 'TOKEN_WAIT', 'token': token['id'],
                               'function': token['func'], 'producer_offset': old['producer_offset']})
        if n['opcode'] == 'sync':
            subop = d.get('subop')
            if subop in {'allrd', 'allwr'}:
                # Exact mask decoding is deliberately required. Do not interpret
                # an unknown register mask as all tokens or assume sync.nop is a fence.
                src = d.get('srcs', [])
                try:
                    mask = int(src[0]['value'], 0) if src and src[0].get('kind') == 'IM' else None
                except (ValueError, TypeError, KeyError):
                    mask = None
                if mask is None:
                    add(UNKNOWN, 'SYNC-MASK-UNKNOWN', 'SYNC allrd/allwr mask is not a known immediate', consumer=pc)
                else:
                    for tid, old in token_state.items():
                        if mask & (1 << tid):
                            old['src_complete'] = True
                            if subop == 'allwr':
                                old['dst_complete'] = True
                    events.append({'offset': pc, 'event': 'SYNC_' + subop, 'mask': mask})
            elif subop != 'nop':
                add(UNKNOWN, 'SYNC-UNMODELED', 'SYNC form not in current executable subset', consumer=pc)
        # Capture readiness before executing this instruction; a wait on a SEND
        # is processed before checking whether it overwrites a live SBID.
        complete_at.append({'inorder_completed_rank': completed_rank,
                            'send': {key: dict(value) for key, value in send_events.items()}})
        if n['message_effects']['is_send']:
            if token is None or token.get('func') != '':
                add(UNKNOWN, 'SEND-TOKEN-MISSING', 'Asynchronous SEND has no modeled token set', consumer=pc)
                send_events[pc] = {'producer_offset': pc, 'src_complete': False, 'dst_complete': False, 'token': None}
            else:
                old = token_state.get(token['id'])
                if old is not None and not old['dst_complete']:
                    # Source-only completion may free a no-response token under
                    # message-specific rules, which are not generalized here.
                    old['completion_unknown'] = True
                    add(UNKNOWN, 'SBID-REUSE-SYNC-UNPROVEN',
                        'Explicit completion missing; IGA implements implicit synchronization on SBID reuse, but exact hardware rule is not independently established',
                        old['producer_offset'], pc)
                event = {'producer_offset': pc, 'src_complete': False, 'dst_complete': False,
                         'completion_unknown': False,
                         'token': token['id'], 'has_response': d.get('dst', {}).get('len', 0) > 0}
                token_state[token['id']] = event
                send_events[pc] = event
                events.append({'offset': pc, 'event': 'SEND_TOKEN_SET', 'token': token['id']})
        elif n['opcode'] in INORDER:
            rank[pc] = len(inorder)
            inorder.append(pc)
        elif n['opcode'] != 'sync':
            add(UNKNOWN, 'PIPELINE-UNMODELED', 'Opcode pipeline/variable latency unmodeled', consumer=pc)
        if n['control_effects']['eot']:
            add(UNKNOWN, 'EOT-MESSAGE-SPECIFIC-COMPLETION',
                'EOT does not by itself prove global side-effect visibility; exact message termination rules unresolved', consumer=pc)

    for k, edge in enumerate(graph['edges']):
        p, c = edge['producer_offset'], edge['consumer_offset']
        ci = bypc[c]
        pn = nodes[bypc[p]]
        cn = nodes[ci]
        state = complete_at[ci]
        if edge['relation'] == 'UNKNOWN':
            add(UNKNOWN, 'SYMBOLIC-DEPENDENCY', 'Symbolic register footprint/effect has no exact schedule proof', p, c, k)
            continue
        if pn['message_effects']['is_send']:
            old = state['send'].get(p)
            need_src = edge['kind'] == 'WAR'
            ready = old and old['src_complete' if need_src else 'dst_complete']
            status = CHECKED if ready else UNKNOWN if old and old.get('completion_unknown') else COUNTER
            add(status, 'SEND-PAYLOAD-WAIT' if need_src else 'SEND-RESPONSE-WAIT',
                'Explicit token event covers required completion' if ready else
                'Completion depends on unresolved null-response/reuse synchronization' if status == UNKNOWN else
                'No explicit token event proves required SEND consumption/response before overlap',
                p, c, k)
        elif p in rank:
            ready = rank[p] <= state['inorder_completed_rank']
            # ALU -> later ALU read-before-write hazards and WAW ordering may be
            # guaranteed by pipeline issue rules. We do not promote missing
            # modeled distance to a violation for those unproved categories.
            if ready:
                status, detail = CHECKED, 'A distance barrier completes the in-order producer'
            elif edge['kind'] == 'RAW':
                status, detail = COUNTER, 'No modeled distance wait covers the required in-order RAW'
            else:
                status, detail = UNKNOWN, 'Applicable in-order WAR/WAW automatic ordering rule not independently discharged'
            add(status, 'INORDER-DISTANCE', detail, p, c, k)
        else:
            add(UNKNOWN, 'PIPELINE-UNMODELED', 'Producer pipeline is not supported by the subset model', p, c, k)
    return {'schema_version': 1, 'shader_id': program['shader_id'], 'platform': program['platform'],
            'program_sha256': program['program_sha256'], 'annotations': [dict(offset=n['byte_range'][0], **a)
                for n, a in zip(nodes, annotations, strict=True)], 'events': events, 'constraints': constraints,
            'counts': {s: sum(c['status'] == s for c in constraints) for s in [CHECKED, COUNTER, UNKNOWN]},
            'model_scope': 'single-in-order-ALU distance + explicit SEND token event subset; not hardware validation',
            'hardware_validated': False}
