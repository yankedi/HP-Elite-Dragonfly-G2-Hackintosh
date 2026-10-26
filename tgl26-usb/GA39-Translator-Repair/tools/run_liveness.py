#!/usr/bin/env python3
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('scratch_live', ROOT / 'numeric/scratch-liveness/liveness.py')
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


def run(baseline, destination):
    destination = destination.resolve()
    if ROOT not in destination.parents or destination.exists():
        raise ValueError('Fresh GA39 directory required')
    destination.mkdir(parents=True)
    summary = []
    for shader, scratch in [('PS0', 122), ('PS-KP1', 107), ('PS-KP2', 117), ('VS', None)]:
        programs = {}
        for side in ['source', 'candidate']:
            p = json.loads((baseline / f'ir/outputs/{shader}-{side}.json').read_text())
            programs[side] = p
            (destination / f'{shader}-{side}-liveness.json').write_text(json.dumps(live.analyze(p), sort_keys=True, indent=2) + '\n')
        if scratch is not None:
            comparison = json.loads((baseline / f'validator/outputs/{shader}-comparison.json').read_text())
            witness = comparison['mapping_witness']
            if witness['source_sha256'] != programs['source']['program_sha256'] or witness['candidate_sha256'] != programs['candidate']['program_sha256']:
                raise ValueError('Mapping identity mismatch')
            mapping = {}
            for entry in witness['entries']:
                lo, hi = entry['target_byte_range']
                for node in programs['candidate']['nodes']:
                    if lo <= node['byte_range'][0] and node['byte_range'][1] <= hi:
                        pc = node['byte_range'][0]
                        if pc in mapping:
                            raise ValueError('Overlapping mapping')
                        mapping[pc] = entry['source_offset']
            result = live.scratch_contract(programs['source'], programs['candidate'], scratch, mapping)
            (destination / f'{shader}-scratch.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
            summary.append({'shader_id': shader, 'register': scratch, 'touch_offsets': [t['target_offset'] for t in result['touches']],
                            'status': result['allocation_status'], 'static_collisions': len(result['static_collisions'])})
    (destination / 'summary.json').write_text(json.dumps(summary, sort_keys=True, indent=2) + '\n')
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    run(a.baseline, a.output)
