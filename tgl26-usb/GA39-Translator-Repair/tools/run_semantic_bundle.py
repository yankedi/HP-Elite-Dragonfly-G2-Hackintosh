#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'translator'))
from semantic_bundle import build


def run(baseline, destination):
    destination = destination.resolve()
    if ROOT not in destination.parents or destination.exists():
        raise ValueError('Fresh GA39 output required')
    destination.mkdir(parents=True)
    summary = []
    for shader in ['PS0', 'PS-KP1', 'PS-KP2', 'VS']:
        def load(relative):
            return json.loads((baseline / relative).read_text())
        source, target = [load(f'ir/outputs/{shader}-{side}.json') for side in ['source', 'candidate']]
        source_messages, target_messages = [load(f'ir/messages/{shader}-{side}.json') for side in ['source', 'candidate']]
        witness = load(f'validator/outputs/{shader}-comparison.json')['mapping_witness']
        bundle = build(source, target, source_messages, target_messages, witness)
        (destination / f'{shader}.json').write_text(json.dumps(bundle, sort_keys=True, indent=2) + '\n')
        summary.append({'shader_id': shader, 'strict_status': bundle['strict_status'],
                        'nf_acc_nodes': len(bundle['nf_acc']['proofs']),
                        'scratch_registers': [x['scratch_register'] for x in bundle['scratch_contracts']],
                        'debug_nodes': len(bundle['debug_switch']['records'])})
    (destination / 'summary.json').write_text(json.dumps(summary, sort_keys=True, indent=2) + '\n')
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    run(a.baseline, a.output)
