#!/usr/bin/env python3
"""Run closed whole-program admission on all four actual programs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / 'translator'))
from trust import baseline_inputs
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
        source_bytes, source, candidate, comparison, schedule, _, _ = baseline_inputs(baseline, shader)
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
