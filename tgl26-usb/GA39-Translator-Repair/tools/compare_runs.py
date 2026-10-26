#!/usr/bin/env python3
"""Compare exactly the same (shader,source offset,layer) evaluation universe."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'translator'))
from trust import HISTORY, manifest, sealed_json


def load(path):
    return json.loads(path.read_text())


def compare(baseline, research, destination, strict=None):
    destination = destination.resolve()
    if ROOT not in destination.parents or destination.exists():
        raise ValueError('Fresh GA39 output required')
    destination.mkdir(parents=True)
    result = {'schema': 'ga39-same-universe-diff/v1', 'unit': '(shader_id, source_offset, layer)',
              'rows': [], 'programs': [], 'hardware_validated': False}
    before_counts, after_counts = Counter(), Counter()
    entries = manifest()
    strict = strict or research.parent / 'strict'
    accepted = 0
    for shader in ['PS0', 'PS-KP1', 'PS-KP2', 'VS']:
        old_path = baseline / f'validator/outputs/{shader}-comparison.json'
        new_path = research / f'{shader}/research-NOT_FOR_HARDWARE/ga38-review/analysis/comparison.json'
        before, after = load(old_path), load(new_path)
        if before['source_sha256'] != after['source_sha256']:
            raise ValueError('Source identity changed; same unit comparison invalid')
        old = {(r['source_offset'], r['layer']): r for r in before['findings']}
        new = {(r['source_offset'], r['layer']): r for r in after['findings']}
        relative = f'validator/outputs/{shader}-comparison.json'
        historical = sealed_json(HISTORY / relative, relative, entries)
        historical_keys = {(r['source_offset'], r['layer']) for r in historical['findings']}
        if set(old) != historical_keys or before['source_sha256'] != historical['source_sha256']:
            raise ValueError('Evaluation universe does not match immutable GA38 historical anchor')
        if len(old) != len(before['findings']) or len(new) != len(after['findings']) or set(old) != set(new):
            raise ValueError('Evaluation universe changed')
        report = load(research / f'{shader}/report.json')
        disposition = load(strict / shader / 'report.json')
        if disposition.get('mode') != 'strict' or type(disposition.get('accepted_program')) is not bool:
            raise ValueError('Missing actual strict disposition')
        accepted += int(disposition['accepted_program'])
        result['programs'].append({'shader_id': shader, 'source_sha256': before['source_sha256'],
            'before_target_sha256': before['candidate_sha256'], 'after_target_sha256': after['candidate_sha256'],
            'bytes_unchanged': before['candidate_sha256'] == after['candidate_sha256'],
            'source_instructions': len({k[0] for k in old}), 'evaluations': len(old),
            'before_counts': before['counts'], 'after_counts': after['counts'],
            'generation_validation_seconds_observed': report['elapsed_seconds'],
            'before_comparison_sha256': hashlib.sha256(old_path.read_bytes()).hexdigest(),
            'after_comparison_sha256': hashlib.sha256(new_path.read_bytes()).hexdigest()})
        for key in sorted(old):
            b, a = old[key], new[key]
            before_counts[b['status']] += 1
            after_counts[a['status']] += 1
            result['rows'].append({'shader_id': shader, 'source_offset': key[0], 'layer': key[1],
                'before': b['status'], 'after': a['status'], 'changed': b['status'] != a['status'],
                'source_raw_hex': b['source_raw_hex'], 'target_raw_hex': a['target_raw_hex'],
                'before_rule': b['rule'], 'after_rule': a['rule'],
                'strict_disposition': disposition['status'],
                'strict_accepted_program': disposition['accepted_program'],
                'unknown_closed': b['status'] == 'UNKNOWN' and a['status'] != 'UNKNOWN',
                'note': 'Whole-program rejection is not a change of this per-layer semantic verdict'})
    result.update(before_counts=dict(before_counts), after_counts=dict(after_counts),
                  evaluations=len(result['rows']), changed=sum(r['changed'] for r in result['rows']),
                  unknown_closed=sum(r['unknown_closed'] for r in result['rows']),
                   strict_accepted_actual_programs=accepted,
                  new_numeric_format_evidence='NF format outline known with 66/67-bit conflict; full numeric equivalence stays UNKNOWN',
                  remaining_constraints=['NF arithmetic/narrowing', 'scratch/thread payload ABI', 'DBG/Switch effects',
                                         'message resource heaps', 'null-response/SBID hardware completion', 'EOT visibility'])
    if result['evaluations'] != 948:
        raise ValueError('Expected fixed 948 evaluation units')
    (destination / 'diff.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['evaluations', 'before_counts', 'after_counts', 'changed', 'unknown_closed']}, sort_keys=True))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--research', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    compare(a.baseline, a.research, a.output)
