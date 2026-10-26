#!/usr/bin/env python3
"""Report raw identities and observed static costs; never a GPU performance test."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text())


def metrics(ir):
    nodes = ir['nodes']
    regs = {o.get('reg', {}).get('r', 0) for n in nodes
            for o in [n['iga_fields'].get('dst', {}), *n['iga_fields'].get('srcs', [])]
            if o.get('reg', {}).get('rn') == 'r'}
    waits = [{'offset': n['byte_range'][0], 'raw_hex': n['raw_hex'], 'platform': ir['platform'],
              'scope': 'Explicit IGA fields only; Gen11 lacks Gen12 SWSB. Absence is not SBID0 or completion',
              'sbid': n['iga_fields'].get('sbid'), 'regDist': n['iga_fields'].get('regDist')}
             for n in nodes if 'sbid' in n['iga_fields'] or 'regDist' in n['iga_fields']]
    sends = [{'offset': n['byte_range'][0], 'platform': ir['platform'], 'raw_hex': n['raw_hex'],
              'sbid': n['iga_fields'].get('sbid'), 'regDist': n['iga_fields'].get('regDist'),
              'sbid_present': 'sbid' in n['iga_fields'], 'regDist_present': 'regDist' in n['iga_fields']}
             for n in nodes if n['message_effects']['is_send']]
    return {'instructions': len(nodes), 'explicit_grf_max': max(regs) if regs else None,
            'send_wait_and_token_carriers': sends,
            'grf_default_scope': 'IGA omits r=0; max explicit index is a decoded projection, not raw resource allocation',
            'explicit_grf_indices': sorted(regs), 'wait_and_token_carriers': waits,
            'send_offsets': [n['byte_range'][0] for n in nodes if n['message_effects']['is_send']],
            'NF_offsets': [n['byte_range'][0] for n in nodes if n['numeric_semantics'].get('nf')],
            'ACC_offsets': [n['byte_range'][0] for n in nodes if n['numeric_semantics'].get('accumulator')]}


def run(baseline, research, output):
    output = output.resolve()
    if ROOT not in output.parents or output.exists():
        raise ValueError('Fresh GA39 output required')
    output.mkdir(parents=True)
    rows = []
    for shader in ['PS0', 'PS-KP1', 'PS-KP2', 'VS']:
        raw_source = (baseline / f'corpus/source/{shader}.bin').read_bytes()
        raw_target = (research / f'{shader}/research-NOT_FOR_HARDWARE/candidate.NOT_FOR_HARDWARE.bin').read_bytes()
        source = load(baseline / f'ir/outputs/{shader}-source.json')
        target = load(research / f'{shader}/research-NOT_FOR_HARDWARE/ga38-review/analysis/candidate-ir.json')
        report = load(research / f'{shader}/report.json')
        if hashlib.sha256(raw_source).hexdigest() != source['program_sha256'] or hashlib.sha256(raw_target).hexdigest() != target['program_sha256']:
            raise ValueError('Raw identity mismatch')
        if (report.get('research_candidate_sha256') != target['program_sha256']
                or report.get('candidate_sha256') != target['program_sha256']
                or report.get('accepted_program') is not False
                or report.get('status') != 'UNKNOWN_REJECTED' or report.get('research_program_generated') is not True):
            raise ValueError('Report identity or disposition differs from raw research candidate')
        rows.append({'shader_id': shader, 'source_sha256': source['program_sha256'],
                     'target_sha256': target['program_sha256'], 'source_bytes': len(raw_source),
                     'target_bytes': len(raw_target), 'expansion_ratio': len(raw_target) / len(raw_source),
                     'source': metrics(source), 'target': metrics(target),
                     'research_generation_validation_seconds_observed': report['elapsed_seconds'],
                     'strict_status': report['status'], 'accepted_program': report['accepted_program'],
                     'new_waits_compared_to_archived_candidate': 0 if report['baseline_bytes_unchanged'] else 'REQUIRES_DIFF',
                     'runtime_GRF_allocation_limit': 'UNKNOWN', 'hardware_validated': False})
    data = {'schema': 'ga39-four-shader-metrics/v1', 'programs': rows,
            'scope': 'CPU observed static transformation costs; max explicit GRF is not a resource allocation proof',
            'hardware_validated': False}
    (output / 'metrics.json').write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'programs': len(rows), 'source_bytes': sum(r['source_bytes'] for r in rows),
                      'target_bytes': sum(r['target_bytes'] for r in rows)}, sort_keys=True))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--research', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    run(a.baseline, a.research, a.output)
