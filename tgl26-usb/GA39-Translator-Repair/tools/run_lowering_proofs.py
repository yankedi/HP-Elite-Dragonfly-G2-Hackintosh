#!/usr/bin/env python3
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / 'translator'))
from trust import baseline_inputs
spec = importlib.util.spec_from_file_location('nf_proof', ROOT / 'numeric/proofs/lowering.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def run(baseline, destination):
    destination = destination.resolve()
    if ROOT not in destination.parents or destination.exists():
        raise ValueError('Fresh GA39 destination required')
    destination.mkdir(parents=True)
    counts = {}
    for shader in ['PS0', 'PS-KP1', 'PS-KP2', 'VS']:
        _, source, target, comparison, _, _, _ = baseline_inputs(baseline, shader)
        witness = comparison['mapping_witness']
        paths = {shader: f'numeric/scratch-liveness/run-031/{shader}-scratch.json'} if shader != 'VS' else {}
        proofs = module.prove(source, target, witness, paths)
        (destination / f'{shader}.json').write_text(json.dumps(proofs, sort_keys=True, indent=2) + '\n')
        counts[shader] = len(proofs['proofs'])
    print(json.dumps(counts, sort_keys=True))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    run(a.baseline, a.output)
