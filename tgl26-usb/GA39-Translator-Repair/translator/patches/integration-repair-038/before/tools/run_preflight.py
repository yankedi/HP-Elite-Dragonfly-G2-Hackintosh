#!/usr/bin/env python3
"""Run closed whole-program admission on all four actual programs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('strict_policy', ROOT / 'translator/strict-policy/policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def run(baseline, destination):
    destination = destination.resolve()
    if ROOT not in destination.parents or destination.exists():
        raise ValueError('Fresh GA39 destination required')
    destination.mkdir(parents=True)
    summary = []
    for shader in ['PS0', 'PS-KP1', 'PS-KP2', 'VS']:
        def load(p):
            return json.loads((baseline / p).read_text())
        source, candidate = [load(f'ir/outputs/{shader}-{side}.json') for side in ['source', 'candidate']]
        source_bytes = (baseline / f'corpus/source/{shader}.bin').read_bytes()
        target_bytes = (baseline / f'corpus/candidate/{shader}.bin').read_bytes()
        for program, raw in [(source, source_bytes), (candidate, target_bytes)]:
            if hashlib.sha256(raw).hexdigest() != program['program_sha256']:
                raise ValueError('Program digest mismatch')
            if b''.join(bytes.fromhex(n['raw_hex']) for n in program['nodes']) != raw:
                raise ValueError('IR raw coverage mismatch')
        comparison = load(f'validator/outputs/{shader}-comparison.json')
        schedule = load(f'validator/outputs/{shader}-schedule.json')
        report = policy.preflight(source, candidate, comparison, schedule)
        out = destination / shader
        out.mkdir()
        (out / 'source.bin').write_bytes(source_bytes)
        (out / 'strict-rejection.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
        summary.append({'shader_id': shader, 'status': report['status'], 'source_sha256': source['program_sha256'],
                        'full_shader_emitted': False, 'obligations': len(report['obligations']),
                        'baseline_comparison_counts_unchanged': comparison['counts']})
    (destination / 'summary.json').write_text(json.dumps(summary, sort_keys=True, indent=2) + '\n')
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    run(a.baseline, a.output)
