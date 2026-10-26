#!/usr/bin/env python3
"""Fresh CPU-only delivery replay; paired runs compare explicit semantic artifacts."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'validator/ga38/tools'))
sys.path.insert(0, str(ROOT / 'translator'))
from driver import run as translate
from analyze import run as baseline_run
from compare_runs import compare
from four_shader_metrics import run as metrics
from run_positive_fragment import run as positive
from run_semantic_bundle import run as semantic


def run(output):
    output = output.resolve()
    if ROOT not in output.parents or output.exists():
        raise ValueError('Fresh GA39 delivery directory required')
    output.mkdir(parents=True)
    baseline_run(output / 'baseline')
    for shader in ['PS0', 'PS-KP1', 'PS-KP2', 'VS']:
        translate(shader, output / 'strict' / shader, baseline=output / 'baseline')
        translate(shader, output / 'research' / shader, mode='research', baseline=output / 'baseline')
    semantic(output / 'baseline', output / 'semantics')
    positive(output / 'positive')
    compare(output / 'baseline', output / 'research', output / 'comparison')
    metrics(output / 'baseline', output / 'research', output / 'metrics')
    print(json.dumps({'status': 'PASS', 'full_programs_strictly_accepted': 0, 'research_programs': 4,
                      'hardware_validated': False}, sort_keys=True))


def stable_artifacts(root):
    selected = []
    for pattern in ['baseline/ir/**/*.json', 'baseline/dependency/**/*.json', 'baseline/validator/**/*.json',
                    'baseline/corpus/**/*.bin', 'baseline/corpus/provenance.json', 'baseline/summary.json',
                    'strict/*/report.json', 'strict/*/source.bin', 'strict/*/semantic-bundle.json',
                    'research/*/report.json', 'research/*/semantic-bundle.json',
                    'research/*/research-NOT_FOR_HARDWARE/candidate.NOT_FOR_HARDWARE.bin',
                    'research/*/research-NOT_FOR_HARDWARE/ga38-review/analysis/*.json',
                    'semantics/*.json', 'positive/strict-unit/report.json',
                    'positive/strict-unit/isolated-fragment.bin', 'comparison/diff.json', 'metrics/metrics.json']:
        selected.extend(root.glob(pattern))
    return sorted(set(selected))


VOLATILE = {'elapsed_seconds', 'generation_validation_seconds_observed',
            'research_generation_validation_seconds_observed'}


def normalize(obj, root):
    if isinstance(obj, dict):
        return {k: normalize(v, root) for k, v in obj.items() if k not in VOLATILE}
    if isinstance(obj, list):
        return [normalize(v, root) for v in obj]
    if isinstance(obj, str):
        return obj.replace(str(root), '<RUN>')
    return obj


def compare_fresh(left, right, output):
    left, right, output = left.resolve(), right.resolve(), output.resolve()
    if left == right or ROOT not in output.parents or output.exists():
        raise ValueError('Distinct runs and fresh GA39 receipt required')
    a, b = [{str(p.relative_to(root)): p for p in stable_artifacts(root)} for root in [left, right]]
    if set(a) != set(b) or not a:
        raise ValueError('Semantic artifact sets differ or are empty')
    rows = []
    for name in sorted(a):
        raw_a, raw_b = a[name].read_bytes(), b[name].read_bytes()
        normalized_a, normalized_b = raw_a, raw_b
        if name.endswith('.json'):
            normalized_a, normalized_b = [json.dumps(normalize(json.loads(raw), root), sort_keys=True).encode()
                                          for raw, root in [(raw_a, left), (raw_b, right)]]
        rows.append({'path': name, 'left_raw_sha256': hashlib.sha256(raw_a).hexdigest(),
                     'right_raw_sha256': hashlib.sha256(raw_b).hexdigest(),
                     'normalized_sha256': hashlib.sha256(normalized_a).hexdigest(),
                     'equal': normalized_a == normalized_b})
    output.mkdir(parents=True)
    data = {'schema': 'ga39-dual-fresh-determinism/v1', 'left': str(left), 'right': str(right),
            'normalization': {'keys_omitted': sorted(VOLATILE), 'run_root_string_replaced': '<RUN>'},
            'scope': 'Raw shader binaries and full selected semantic JSON, not command-log textual identity',
            'rows': rows, 'equal': all(r['equal'] for r in rows), 'hardware_validated': False}
    (output / 'determinism.json').write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    if not data['equal']:
        raise ValueError('Determinism failed; retained exact row identities in receipt')
    print(json.dumps({'status': 'PASS', 'artifacts': len(rows)}, sort_keys=True))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='command', required=True)
    run_parser = sub.add_parser('run')
    run_parser.add_argument('--output', type=Path, required=True)
    cmp = sub.add_parser('compare')
    cmp.add_argument('--left', type=Path, required=True)
    cmp.add_argument('--right', type=Path, required=True)
    cmp.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    if a.command == 'run':
        run(a.output)
    else:
        compare_fresh(a.left, a.right, a.output)
