#!/usr/bin/env python3
"""Execute independently authored oracle fixtures; never synthesize expectations."""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from common import ROOT, Rejected, dump, load, output_root, sha
for sub in ['corpus', 'ir', 'dependency', 'validator']:
    sys.path.insert(0, str(ROOT / sub))
from iga_adapter import decode
from semantic_ir import build_program, make_instruction
from integrity import validate_instruction
from message_ir import build_messages, contract
from dependency_graph import build_graph
from gen12_schedule_check import check
from compare_program import compare


def evaluate(item, run, output):
    path = ROOT / 'tests' / item['file']
    data = path.read_bytes()
    if sha(data) != item['sha256']:
        raise Rejected('ORACLE_FIXTURE_HASH', item['id'])
    if item['class'] == 'deleteimplicitdependency':
        validate_instruction(load(path)['nodes'][0])
        return []
    platform = item.get('construction', {}).get('base_platform') or '12p1'
    decoded = decode(data, platform, output / item['id'] / 'decode')
    if item['id'].startswith(('N02', 'N04')):
        # Explicitly unit-scoped message fixtures need not be full EOT programs.
        nodes = [make_instruction(item['id'], data, platform, ins, pc, size, None,
                  {'tool': decoded['tool'], 'iga_json_sha256': decoded['json_sha256']}).as_dict()
                 for ins, (pc, size) in zip(decoded['instructions'], decoded['frames'], strict=True)]
        msgs = [c for n in nodes if (c := contract(n)) is not None]
        dump(output / item['id'] / 'message-units.json', msgs)
        observed = []
        for m in msgs:
            for u in m['unresolved_fields']:
                if u['code'] == 'DYNAMIC_DESCRIPTOR':
                    observed.append({'status': 'UNKNOWN', 'rule': 'DYNAMIC-DESCRIPTOR', 'offset': m['instruction_offset']})
                if u['code'] == 'UNKNOWN_MESSAGE_TYPE':
                    observed.append({'status': 'UNKNOWN', 'rule': 'UNMODELED-MESSAGE-FAMILY', 'offset': m['instruction_offset'],
                                     'decoded_sfid': m['sfid']})
        return observed
    base = item.get('construction', {}).get('base')
    if item['class'] == 'debugSwitchchange':
        p = build_program('PS0', data, decoded, 0x40)
        original = load(run / 'ir/outputs/PS0-source.json')
        offset = item['target']['instruction_offset']
        before = next(n for n in original['nodes'] if n['byte_range'][0] == offset)
        after = next(n for n in p['nodes'] if n['byte_range'][0] == offset)
        dump(output / item['id'] / 'source-mutant-ir.json', p)
        # The factual field change is tested. Its physical observability remains
        # unknown, so no hardware semantic counterexample is fabricated.
        if before['control_effects']['debug_switch'] != after['control_effects']['debug_switch']:
            return [{'status': 'UNKNOWN', 'rule': 'EU-DEBUG-SWITCH', 'offset': offset,
                     'field_difference': ['Switch', before['control_effects']['debug_switch'], after['control_effects']['debug_switch']]}]
        return []
    ident = Path(base).stem if base else item['id']
    mutated = build_program(ident, data, decoded)
    graph = build_graph(mutated)
    if platform == '11':
        target = load(run / f'ir/outputs/{ident}-candidate.json')
        target_graph = load(run / f'dependency/graphs/{ident}-candidate.json')
        schedule = check(target, target_graph)
        original_review = load(run / f'validator/outputs/{ident}-comparison.json')
        witness = deepcopy(original_review['mapping_witness'])
        witness['source_sha256'] = sha(data)
        witness['scope'] = 'Independent source mutant compared with the unchanged real Gen12 candidate'
        reviewed = compare(mutated, target, witness, graph, target_graph, schedule, build_messages(mutated), build_messages(target))
        dump(output / item['id'] / 'source-mutant-ir.json', mutated)
        dump(output / item['id'] / 'comparison.json', reviewed)
        return reviewed['findings']
    sched = check(mutated, graph)
    dump(output / item['id'] / 'ir.json', mutated)
    dump(output / item['id'] / 'schedule.json', sched)
    observed = list(sched['constraints'])
    if base is not None:
        original_review = load(run / f'validator/outputs/{ident}-comparison.json')
        source = load(run / f'ir/outputs/{ident}-source.json')
        source_graph = load(run / f'dependency/graphs/{ident}-source.json')
        source_messages = load(run / f'ir/messages/{ident}-source.json')
        witness = deepcopy(original_review['mapping_witness'])
        witness['candidate_sha256'] = sha(data)
        witness['scope'] = 'Independent mutant fixture reuses declared layout; no semantic equivalence presumed'
        reviewed = compare(source, mutated, witness, source_graph, graph, sched, source_messages, build_messages(mutated))
        dump(output / item['id'] / 'comparison.json', reviewed)
        observed.extend(reviewed['findings'])
    return observed


def run(root, analysis):
    root = output_root(root)
    root.mkdir(parents=True, exist_ok=False)
    oracle_path = ROOT / 'tests/oracles/oracles.json'
    oracles = load(oracle_path)
    # Corrections remain separate, independently justified, append-only evidence.
    errata_path = ROOT / 'tests/oracles/ERRATA.json'
    errata = load(errata_path) if errata_path.exists() else None
    # The independent author already applied corrections to current oracles;
    # preserve the separately hashed errata/old checkpoint as the audit trail.
    corrections = {e['id']: e for e in (errata.get('operations', []) if errata else [])
                   if e['op'] == 'merge' and e.get('path') == 'expected_detection'}
    results = []
    for original in oracles['mutants'] + oracles['negative_fixtures']:
        item = deepcopy(original)
        if item['id'] in corrections:
            item['expected_detection'].update(corrections[item['id']]['value'])
        expectation = item['expected_detection']
        try:
            observed = evaluate(item, analysis, root)
        except Rejected as exc:
            observed = [{'status': 'REJECTED', 'rule': exc.code, 'detail': exc.detail, 'offset': exc.offset}]
        desired_rule = expectation['primary_rule']
        if desired_rule == 'PROTOCOL_OR_DECODE_BOUNDARY':
            accepted_rules = {'ILLEGAL_ENCODING', 'DECODE_BOUNDARY_MISMATCH', 'EOT_FRAMING',
                              'TRUNCATED_COMPACT', 'TRUNCATED_NATIVE', 'DECODER_SCHEMA'}
        else:
            accepted_rules = {desired_rule}
        matches = [o for o in observed if o['status'] == expectation['status'] and o.get('rule') in accepted_rules]
        result = {'id': item['id'], 'class': item['class'], 'input_sha256': item['sha256'],
                  'expectation': expectation, 'independent_erratum_applied': item['id'] in corrections,
                  'status': 'PASS' if matches else 'FAIL', 'matched_detections': matches,
                  'all_observed_status_rules': sorted({(o['status'], o.get('rule')) for o in observed})}
        dump(root / item['id'] / 'result.json', result)
        results.append(result)
    report = {'status': 'PASS' if all(r['status'] == 'PASS' for r in results) else 'FAIL',
              'oracle_sha256': sha(oracle_path.read_bytes()),
              'errata_sha256': sha(errata_path.read_bytes()) if errata else None,
              'covered_classes': sorted({r['class'] for r in results}), 'results': results,
              'hardware_validated': False}
    dump(root / 'results.json', report)
    failed = [r['id'] for r in results if r['status'] == 'FAIL']
    print(f'{len(results)-len(failed)}/{len(results)} oracle fixtures passed; failed={failed}')
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    run(args.output, output_root(args.run))
