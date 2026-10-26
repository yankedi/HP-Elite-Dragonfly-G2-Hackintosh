"""Compare independent semantic layers; correspondence never implies equivalence."""
from __future__ import annotations

from copy import deepcopy

from common import Rejected
from integrity import validate_program
from dependency_graph import build_graph
from semantic_ir import WIDTHS

CHECKED = 'STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS'
COUNTER = 'COUNTEREXAMPLE'
UNKNOWN = 'UNKNOWN'
LAYERS = ['opcode_math', 'operands_registers', 'execution_size', 'region_lane',
          'predicate_mask', 'accumulator_nf', 'send_message', 'payload_response',
          'eot', 'register_dependency', 'swsb_sbid', 'resource_thread_payload_abi']


def validate_mapping(source: dict, target: dict, witness: dict) -> list[dict]:
    """Validate arbitrary declared one-to-many contiguous instruction ranges.

    The witness is a correspondence hypothesis with provenance. A complete
    framing witness is not a proof that each expansion has equivalent effects.
    """
    if not isinstance(witness, dict) or not isinstance(witness.get('entries'), list):
        raise Rejected('MAPPING_SCHEMA', 'Expected a dictionary with an entries array')
    if (witness.get('source_sha256') != source['program_sha256']
            or witness.get('candidate_sha256') != target['program_sha256']):
        raise Rejected('MAPPING_IDENTITY', 'Correspondence witness must bind both complete raw program hashes')
    src = {n['byte_range'][0]: n for n in source['nodes']}
    dst = {n['byte_range'][0]: n for n in target['nodes']}
    used_source, used_target = set(), set()
    result = []
    for item in witness['entries']:
        if not isinstance(item, dict) or type(item.get('source_offset')) is not int:
            raise Rejected('MAPPING_SCHEMA', 'Source offset must be an integer')
        interval = item.get('target_byte_range')
        if not isinstance(interval, list) or len(interval) != 2 or any(type(x) is not int for x in interval):
            raise Rejected('MAPPING_SCHEMA', 'Target range must be two integer byte offsets')
        s = item['source_offset']
        lo, hi = interval
        if s not in src or s in used_source or lo not in dst or type(hi) is not int:
            raise Rejected('MAPPING_BOUNDARY', repr(item))
        selected = [n for n in target['nodes'] if lo <= n['byte_range'][0] < hi]
        if not selected or selected[-1]['byte_range'][1] != hi:
            raise Rejected('MAPPING_BOUNDARY', repr(item))
        if any(n['byte_range'][0] in used_target for n in selected):
            raise Rejected('MAPPING_OVERLAP', repr(item))
        used_source.add(s)
        used_target.update(n['byte_range'][0] for n in selected)
        result.append({**item, 'source': src[s], 'targets': selected})
    if used_source != set(src) or used_target != set(dst):
        raise Rejected('MAPPING_INCOMPLETE', 'Every raw instruction must have a correspondence or explicit unmapped report')
    return result


def canonical_operands(node):
    """Decoded data effects only, excluding scheduling, comments and compaction."""
    d = node['iga_fields']
    return {'dst': d.get('dst'), 'srcs': d.get('srcs', [])}


def register_projection(o):
    # Preserve every decoded operand field except the separately audited region;
    # no future modifier/indirect-offset field may be silently discarded.
    return {k: deepcopy(v) for k, v in o.items() if k != 'rgn'} | {'sat': o.get('sat', False)}


def partial_operand_compare(source, target, projection):
    """NF uncertainty applies to that operand, never hides a known GRF change."""
    ss, ts = all_operands(source), all_operands(target)
    if len(ss) != len(ts):
        return False, True, []
    unresolved, differences = False, []
    for index, (s, t) in enumerate(zip(ss, ts, strict=True)):
        if s.get('type') == 'nf' or t.get('type') == 'nf':
            unresolved = True
            continue
        if projection(s) != projection(t):
            differences.append(index)
    return not differences, unresolved, differences


def all_operands(n):
    d = n['iga_fields']
    return [d.get('dst', {}), *d.get('srcs', [])]


def region_projection(n):
    return {'eo': n['iga_fields'].get('eo', 0),
            'regions': [o.get('rgn') for o in all_operands(n)]}


def operand_region_projection(o):
    return {'region': o.get('rgn'), 'typed_subregister': o.get('reg', {}).get('sr', 0),
            'element_bytes': WIDTHS.get(o.get('type'))}


def predicate_projection(n):
    d = n['iga_fields']
    return {k: d.get(k, False if k == 'wren' else None) for k in ['wren', 'pred', 'fm', 'cond']}


def finding(layer, state, s, targets, rule, detail, repair, fields, assumptions=None):
    return {'layer': layer, 'status': state, 'source_offset': s['byte_range'][0],
            'source_eu_window_range': s['eu_window_range'], 'source_raw_hex': s['raw_hex'],
            'target_offsets': [t['byte_range'][0] for t in targets],
            'target_raw_hex': [t['raw_hex'] for t in targets],
            'rule': rule, 'detail': detail, 'dependency_fields': fields,
            'violated_constraint': detail if state == COUNTER else None,
            'necessary_assumptions': assumptions or ['Pinned IGA field decoding', 'Declared source-to-target correspondence'],
            'minimal_repair': repair,
            'evidence': ['IGA-JSON', rule], 'hardware_validated': False}


def compare(source, target, witness, source_graph, target_graph, schedule, source_messages, target_messages):
    validate_program(source)
    validate_program(target)
    if source_graph != build_graph(source) or target_graph != build_graph(target):
        raise Rejected('DEPENDENCY_GRAPH_INTEGRITY', 'A source or target dependency graph is incomplete/inconsistent')
    try:
        pairs = validate_mapping(source, target, witness)
    except Rejected as exc:
        # Keep the complete program represented even if correspondence fails.
        pairs = [{'source': s, 'targets': []} for s in source['nodes']]
        mapping_failure = exc.as_dict()
    else:
        mapping_failure = None
    correspondence = {}
    for pair in pairs:
        bodies = [t for t in pair['targets'] if t['opcode'] != 'sync']
        correspondence[pair['source']['byte_range'][0]] = [n['byte_range'][0] for n in bodies]
    dependency_correspondence = []
    for index, edge in enumerate(source_graph['edges']):
        p, c = edge['producer_offset'], edge['consumer_offset']
        target_edges = [(k, e) for k, e in enumerate(target_graph['edges'])
                        if e['producer_offset'] in correspondence.get(p, [])
                        and e['consumer_offset'] in correspondence.get(c, []) and e['kind'] == edge['kind']]
        # Source symbolic effects need a separate renaming/semantic theorem.
        # Presence of an arbitrary overlapping target edge cannot discharge it.
        if edge['relation'] == 'UNKNOWN' or len(correspondence.get(p, [])) != 1 or len(correspondence.get(c, [])) != 1:
            state, detail = UNKNOWN, 'Symbolic source effect or multi-operation expansion lacks an edge-equivalence theorem'
        elif target_edges:
            state, detail = CHECKED, 'Mapped producer/consumer retain this hazard kind; operand and schedule proofs remain separate'
        else:
            state, detail = UNKNOWN, 'Source hazard has no matched target edge; renaming/effect proof required'
        dependency_correspondence.append({'source_edge_index': index, 'source_producer_offset': p,
            'source_consumer_offset': c, 'target_edge_indices': [k for k, _ in target_edges],
            'status': state, 'detail': detail, 'rule': 'GRAPH-CORRESPONDENCE'})
    findings = []
    sm = {m['instruction_offset']: m for m in source_messages['messages']}
    tm = {m['instruction_offset']: m for m in target_messages['messages']}
    for pair in pairs:
        s, targets = pair['source'], pair['targets']
        if not targets:
            for layer in LAYERS:
                findings.append(finding(layer, UNKNOWN, s, [], 'MAPPING-UNRESOLVED',
                    str(mapping_failure), 'Recover an independently anchored correspondence witness', []))
            continue
        # Extra SYNCs may live in a range; arbitrary multi-ALU expansions need a
        # symbolic equivalence proof, not a zip or same instruction-count test.
        bodies = [n for n in targets if n['opcode'] != 'sync']
        if len(bodies) != 1:
            for layer in LAYERS:
                findings.append(finding(layer, UNKNOWN, s, targets, 'EXPANSION-SEMANTICS',
                    'Multi-operation expansion lacks a composition proof', 'Provide per-expansion effect equivalence', []))
            continue
        t = bodies[0]
        sd, td = s['iga_fields'], t['iga_fields']
        source_options = set(sd.get('opts', [])) - {'Compacted', 'EOT'}
        target_options = set(td.get('opts', [])) - {'Compacted', 'EOT'}
        option_difference = source_options != target_options
        special = (s['control_effects']['debug_switch'] or t['control_effects']['debug_switch']
                   or any(a['file'] == 'DBG' for n in [s, t] for a in n['register_access']['accesses'])
                   or option_difference)
        nf = s['numeric_semantics']['nf'] or t['numeric_semantics']['nf']
        acc = s['numeric_semantics']['accumulator'] or t['numeric_semantics']['accumulator']
        send = s['message_effects']['is_send'] or t['message_effects']['is_send']
        add = lambda layer, state, rule, detail, repair, fields: findings.append(
            finding(layer, state, s, targets, rule, detail, repair, fields))
        expected_op = {'sends': 'send', 'sendsc': 'sendc'}.get(s['opcode'], s['opcode'])
        sameop = expected_op == t['opcode']
        # Identical opcode text proves the opcode projection. It cannot by
        # itself prove cross-generation rounding/denormal/FP-mode equivalence.
        mathunknown = nf or acc or special or s['opcode'] in {'add', 'mul', 'mad', 'mac'}
        add('opcode_math', COUNTER if not sameop else UNKNOWN if mathunknown else CHECKED,
            'OPCODE-CORRESPONDENCE',
            'Opcode differs' if not sameop else 'Opcode projection preserved; numeric/FP-mode equivalence unresolved' if mathunknown else 'Opcode projection preserved within decoded move/carrier subset',
            'Restore the source operation; prove numeric/rounding rules before claiming equivalence', ['opcode', 'numeric_semantics'])
        regsame = [register_projection(o) for o in all_operands(s)] == [register_projection(o) for o in all_operands(t)]
        known_regs_equal, regs_unknown, register_differences = partial_operand_compare(s, t, register_projection)
        add('operands_registers', UNKNOWN if special or send else COUNTER if not known_regs_equal else UNKNOWN if regs_unknown else CHECKED,
            'OPERAND-EFFECTS',
            'Special/debug effect or message carrier needs a separate contract' if special or send else
            f'Known register/type/modifier/value projection differs at operand indices {register_differences}' if not known_regs_equal else
            'Non-NF operand projections equal; NF scratch rename and numeric equivalence unresolved' if regs_unknown else 'Decoded register/type/modifier/value projection equal',
            'Prove scratch liveness and numeric equivalence; preserve all observable register effects', ['dst', 'srcs'])
        exsame = sd['es'] == td['es']
        add('execution_size', CHECKED if exsame else COUNTER, 'EXECUTION-SIZE',
            f"source={sd['es']}, target={td['es']}", 'Preserve execution size', ['es'])
        rsame = region_projection(s) == region_projection(t)
        known_regions_equal, regions_unknown, region_differences = partial_operand_compare(s, t, operand_region_projection)
        channel_equal = sd.get('eo', 0) == td.get('eo', 0)
        add('region_lane', UNKNOWN if send or special else COUNTER if not known_regions_equal or not channel_equal else UNKNOWN if regions_unknown else CHECKED,
            'EU-REGION', 'Message/special effect region requires its own contract' if send or special else
            f'Known region/channel projection differs at operand indices {region_differences}' if not known_regions_equal or not channel_equal else
            'Non-NF region/channel projections equal; NF operand region mapping unresolved' if regions_unknown else 'Region/channel projections equal',
            'Preserve byte-to-channel mapping with type-specific subregister units', ['rgn', 'eo', 'type'])
        psame = predicate_projection(s) == predicate_projection(t)
        add('predicate_mask', COUNTER if not psame else UNKNOWN if option_difference else CHECKED, 'MASK-PREDICATE',
            'Mask/predicate/flag-control projection differs' if not psame else
            'Mask/predicate equal but other execution-control options differ; observability unresolved' if option_difference else
            'Decoded mask/predicate/flag-control projections equal',
            'Preserve mask and predicate including flag selection', ['wren', 'pred', 'fm', 'cond'])
        add('accumulator_nf', UNKNOWN if acc or nf else CHECKED, 'EU-ACC-NF',
            'NF/acc internal format, rounding and fusion equivalence not established' if acc or nf else 'No accumulator/NF effect in the modeled instruction',
            'Acquire exact NF/ACC precision rule and an independent equivalence proof; do not rely on float random testing', ['implicit_operands', 'numeric_semantics'])
        if send:
            sc, tc = sm.get(s['byte_range'][0]), tm.get(t['byte_range'][0])
            if sc is None or tc is None:
                msgstate, detail = COUNTER, 'A SEND contract is missing on one side'
            elif sc['sfid']['state'] != 'KNOWN' or tc['sfid']['state'] != 'KNOWN':
                msgstate, detail = UNKNOWN, 'Dynamic or unknown SFID/message descriptor'
            elif sc['sfid']['value'] != tc['sfid']['value']:
                msgstate, detail = COUNTER, 'SEND functional unit (SFID) changed'
            elif sc['descriptor']['state'] == tc['descriptor']['state'] == 'KNOWN' and sc['descriptor']['value'] != tc['descriptor']['value']:
                msgstate, detail = UNKNOWN, 'Cross-generation descriptor differs; conversion rule required'
            else:
                msgstate, detail = UNKNOWN, 'Carrier and decoded fields compared; complete per-generation message/resource semantics not proved'
            add('send_message', msgstate, 'SEND-GENERATION-CONTRACT', detail,
                'Prove each message-specific descriptor field under Gen11 and Gen12 rules', ['sfid', 'descriptor', 'extended_descriptor'])
            same_payload = sc is not None and tc is not None and sc['carrier_register_ranges'] == tc['carrier_register_ranges'] and sc['lengths'] == tc['lengths']
            add('payload_response', CHECKED if same_payload else COUNTER if sc and tc else UNKNOWN,
                'SEND-CARRIER', 'Carrier GRF ranges and descriptor lengths equal; heap/thread payload ABI still unknown' if same_payload else 'Carrier GRF ranges or descriptor lengths differ',
                'Preserve physical payload/response ranges and separately establish ABI contents', ['carrier_register_ranges', 'lengths'])
        else:
            for layer in ['send_message', 'payload_response']:
                add(layer, CHECKED, 'NO-SEND-EFFECT', 'Neither instruction is a SEND', 'No message-local repair', ['opcode'])
        sameeot = s['control_effects']['eot'] == t['control_effects']['eot']
        add('eot', CHECKED if sameeot else COUNTER, 'EOT-FRAMING',
            'EOT flag/position preserved; completion semantics reviewed independently' if sameeot else 'EOT flag differs',
            'Restore EOT boundary and prove message-specific termination/completion rules', ['EOT'])
        incoming = [e for e in dependency_correspondence if e['source_consumer_offset'] == s['byte_range'][0]]
        deps_unknown = any(e['status'] == UNKNOWN for e in incoming)
        add('register_dependency', UNKNOWN if nf or acc or special or deps_unknown else CHECKED if regsame or send and same_payload else UNKNOWN,
            'GRAPH-CORRESPONDENCE',
            'Both complete hazard graphs exist; symbolic ACC/debug and cross-generation side effects are not discharged' if nf or acc or special else 'Local access projection preserved; graph-level schedule coverage is reported separately',
            'Discharge symbolic effects and verify every mapped hazard constraint', ['source_graph', 'target_graph', 'register_access'])
        range_offsets = {n['byte_range'][0] for n in targets}
        local_sched = [v for v in schedule['constraints'] if v.get('consumer_offset') in range_offsets]
        schedstate = COUNTER if any(x['status'] == COUNTER for x in local_sched) else UNKNOWN if not local_sched or any(x['status'] == UNKNOWN for x in local_sched) else CHECKED
        add('swsb_sbid', schedstate, 'GEN12-SWSB',
            f'{len(local_sched)} local schedule constraints, with independent status per edge' if local_sched else
            'No local schedule constraint was exercised at this offset; no positive schedule-validation claim',
            'Repair only concrete uncovered waits; unresolved pipeline/EOT rules need specification evidence', ['regDist', 'sbid', 'sync', 'schedule.constraints'])
        add('resource_thread_payload_abi', UNKNOWN, 'MISSING-LIVE-RESOURCE-STATE',
            'Capture does not contain a complete Surface/BindingTable/Sampler/URB/RT/thread payload ABI witness',
            'Define an offline symbolic ABI and required future independently authenticated resource inventory', ['thread_payload_dependencies', 'resource_dependencies'])
    counts = {state: sum(f['status'] == state for f in findings) for state in [CHECKED, COUNTER, UNKNOWN]}
    return {'schema_version': 1, 'shader_id': source['shader_id'],
            'source_sha256': source['program_sha256'], 'candidate_sha256': target['program_sha256'],
            'mapping_witness': witness, 'mapping_failure': mapping_failure, 'layers': LAYERS,
            'dependency_correspondence': dependency_correspondence,
            'unmapped_target_offsets': [n['byte_range'][0] for n in target['nodes']] if mapping_failure else [],
            'findings': findings, 'counts': counts, 'hardware_validated': False}
