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

SHADERS = ['PS0', 'PS-KP1', 'PS-KP2', 'VS']


def verify_dispositions(root):
    rows = []
    for shader in SHADERS:
        strict = json.loads((root / f'strict/{shader}/report.json').read_text())
        research = json.loads((root / f'research/{shader}/report.json').read_text())
        if (strict.get('mode') != 'strict' or strict.get('status') != 'UNKNOWN_REJECTED'
                or strict.get('accepted_program') is not False or strict.get('full_shader_emitted') is not False):
            raise ValueError('Unexpected strict acceptance/disposition: ' + shader)
        if (research.get('mode') != 'research' or research.get('accepted_program') is not False
                or research.get('research_program_generated') is not True
                or research.get('research_validation_state') != 'MAPPED_DECODED_ROUNDTRIPPED_NOT_SEMANTICALLY_PROVEN'):
            raise ValueError('Research did not finish validation: ' + shader)
        rows.append({'shader_id': shader, 'strict_status': strict['status'],
                     'strict_accepted': strict['accepted_program'],
                     'research_generated': research['research_program_generated']})
    return {'status': 'PASS', 'full_programs_strictly_accepted': sum(int(r['strict_accepted']) for r in rows),
            'research_programs': sum(int(r['research_generated']) for r in rows),
            'programs': rows, 'hardware_validated': False}


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
    summary = verify_dispositions(output)
    (output / 'delivery-summary.json').write_text(json.dumps(summary, sort_keys=True, indent=2) + '\n')
    print(json.dumps(summary, sort_keys=True))


def stable_artifacts(root):
    selected = []
    for pattern in ['baseline/ir/**/*.json', 'baseline/dependency/**/*.json', 'baseline/validator/**/*.json',
                    'baseline/corpus/**/*.bin', 'baseline/corpus/provenance.json', 'baseline/summary.json',
                    'strict/*/report.json', 'strict/*/source.bin', 'strict/*/semantic-bundle.json',
                    'research/*/report.json', 'research/*/semantic-bundle.json',
                    'research/*/research-NOT_FOR_HARDWARE/candidate.NOT_FOR_HARDWARE.bin',
                    'research/*/research-NOT_FOR_HARDWARE/ga38-review/analysis/*.json',
                    'semantics/*.json', 'positive/strict-unit/report.json',
                    'positive/strict-unit/isolated-fragment.bin', 'comparison/diff.json', 'metrics/metrics.json',
                    'delivery-summary.json']:
        selected.extend(root.glob(pattern))
    return sorted(set(selected))


def required_artifacts():
    out = {'baseline/corpus/provenance.json', 'baseline/summary.json', 'semantics/summary.json',
           'comparison/diff.json', 'metrics/metrics.json', 'delivery-summary.json',
           'positive/strict-unit/report.json', 'positive/strict-unit/isolated-fragment.bin'}
    for s in SHADERS:
        for side in ['source', 'candidate']:
            out.update({f'baseline/ir/outputs/{s}-{side}.json', f'baseline/ir/messages/{s}-{side}.json',
                        f'baseline/dependency/graphs/{s}-{side}.json', f'baseline/corpus/{side}/{s}.bin'})
        for kind in ['comparison', 'schedule']:
            out.add(f'baseline/validator/outputs/{s}-{kind}.json')
        out.update({f'strict/{s}/report.json', f'strict/{s}/source.bin', f'strict/{s}/semantic-bundle.json',
                    f'research/{s}/report.json', f'research/{s}/semantic-bundle.json', f'semantics/{s}.json'})
        prefix = f'research/{s}/research-NOT_FOR_HARDWARE/'
        out.add(prefix + 'candidate.NOT_FOR_HARDWARE.bin')
        for name in ['source-ir', 'candidate-ir', 'source-graph', 'candidate-graph',
                     'source-messages', 'candidate-messages', 'schedule', 'comparison']:
            out.add(prefix + f'ga38-review/analysis/{name}.json')
    return out


VOLATILE = {'elapsed_seconds', 'generation_validation_seconds_observed',
            'research_generation_validation_seconds_observed'}


def normalize(obj, root, artifact='', trail=()):
    if isinstance(obj, dict):
        def omit(k):
            if artifact.endswith('/report.json') and not trail and k == 'elapsed_seconds':
                return True
            if artifact == 'comparison/diff.json' and len(trail) == 2 and trail[0] == 'programs' and k == 'generation_validation_seconds_observed':
                return True
            return (artifact == 'metrics/metrics.json' and len(trail) == 2 and trail[0] == 'programs'
                    and k == 'research_generation_validation_seconds_observed')
        return {k: normalize(v, root, artifact, trail + (k,)) for k, v in obj.items() if not omit(k)}
    if isinstance(obj, list):
        return [normalize(v, root, artifact, trail + (i,)) for i, v in enumerate(obj)]
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
    required = required_artifacts()
    if not required <= set(a):
        raise ValueError('Required semantic artifacts missing: ' + str(sorted(required-set(a))))
    verify_dispositions(left)
    verify_dispositions(right)
    rows = []
    for name in sorted(a):
        raw_a, raw_b = a[name].read_bytes(), b[name].read_bytes()
        normalized_a, normalized_b = raw_a, raw_b
        if name.endswith('.json'):
            normalized_a, normalized_b = [json.dumps(normalize(json.loads(raw), root, name), sort_keys=True).encode()
                                          for raw, root in [(raw_a, left), (raw_b, right)]]
        rows.append({'path': name, 'left_raw_sha256': hashlib.sha256(raw_a).hexdigest(),
                     'right_raw_sha256': hashlib.sha256(raw_b).hexdigest(),
                     'normalized_sha256': hashlib.sha256(normalized_a).hexdigest(),
                     'equal': normalized_a == normalized_b})
    output.mkdir(parents=True)
    data = {'schema': 'ga39-dual-fresh-determinism/v1', 'left': str(left), 'right': str(right),
            'normalization': {'timing_fields_omitted': ['*/report.json:$.elapsed_seconds',
                              'comparison/diff.json:$.programs[*].generation_validation_seconds_observed',
                              'metrics/metrics.json:$.programs[*].research_generation_validation_seconds_observed'],
                              'json_object_key_order_and_whitespace_normalized': True,
                              'run_root_string_replaced': '<RUN>'},
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
