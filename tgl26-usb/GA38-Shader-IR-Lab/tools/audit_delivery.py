#!/usr/bin/env python3
"""Audit concrete deliverables and final status scope before creating the seal."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from common import ROOT, dump, load, output_root, sha

STATES = {
    'INPUT_PROVENANCE': {'VERIFIED', 'PARTIAL', 'BLOCKED'},
    'FOUR_SHADER_FRAMING': {'VERIFIED', 'PARTIAL', 'BLOCKED'},
    'SOURCE_SEMANTIC_IR': {'COMPLETE', 'PARTIAL', 'BLOCKED'},
    'MESSAGE_CONTRACTS': {'COMPLETE', 'PARTIAL', 'BLOCKED'},
    'REGISTER_DEPENDENCIES': {'COMPLETE', 'PARTIAL', 'BLOCKED'},
    'GEN12_SWSB_CHECKER': {'VALIDATED_SUBSET', 'PARTIAL', 'BLOCKED'},
    'FOUR_CANDIDATE_REVIEW': {'COMPLETE', 'PARTIAL', 'BLOCKED'},
    'NF_ACC_SEMANTICS': {'VERIFIED_SUBSET', 'UNKNOWN', 'BLOCKED'},
    'SEND_ABI_SEMANTICS': {'VERIFIED_SUBSET', 'PARTIAL', 'UNKNOWN'},
    'MUTATION_TESTS': {'PASS', 'PARTIAL', 'BLOCKED'},
    'INDEPENDENT_AUDIT': {'PASS', 'CONDITIONAL', 'BLOCKED'},
    'READY_FOR_TRANSLATOR_REPAIR': {'YES', 'PARTIAL', 'NO'},
    'READY_FOR_HARDWARE_APPROVAL': {'NO'},
}


def audit(receipt):
    receipt = output_root(receipt)
    if receipt.exists():
        raise ValueError('Refuse to replace a delivery receipt')
    state = load(ROOT / 'state.json')
    assert set(state['final_status']) == set(STATES), 'Exactly 13 final status keys required'
    for key, allowed in STATES.items():
        assert state['final_status'][key] in allowed, key
    assert state['hardware_validated'] is False
    verification = load(ROOT / state['latest_verification'])
    mutants = load(ROOT / state['latest_mutation_verification'])
    assert verification['status'] == mutants['status'] == 'PASS'
    assert verification['schema_validation'] == 'PASS' and not verification['differences']
    assert len(mutants['covered_classes']) >= 14 and len(mutants['results']) >= 21
    native = load(ROOT / 'tests/historical-regression/results.json')
    debug = load(ROOT / 'tests/historical-regression/debug-extension/extension-results.json')
    assert debug['status'] == 'OK' and not debug['blockers']
    required = ['README.md', 'FINAL-REPORT.md', 'state.json', 'history.json', 'continuation.md',
                'reports/PS0.md', 'reports/PS-KP1.md', 'reports/PS-KP2.md', 'reports/VS.md',
                'reports/MESSAGE-CONTRACTS.md', 'reports/SWSB-DEPENDENCIES.md',
                'reports/CANDIDATE-FINDINGS.md', 'reports/TRANSLATOR-FIX-BACKLOG.md',
                'reports/INDEPENDENT-AUDIT.md', 'reports/REQUIREMENTS-MAP.md', 'reports/NF-ACC-SCRATCH-AUDIT.md',
                'review/initial/findings.json', 'review/final/closure.json', 'review/final/FINAL-CLOSURE.md']
    records = []
    for relative in required:
        p = ROOT / relative
        assert p.is_file() and p.stat().st_size > 0, relative
        records.append({'path': relative, 'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size})
    source_total = target_total = findings_total = source_send = target_send = 0
    for shader, count in [('PS0', 11), ('PS-KP1', 29), ('PS-KP2', 15), ('VS', 24)]:
        for side in ['source', 'candidate']:
            ir = load(ROOT / f'ir/outputs/{shader}-{side}.json')
            binary = (ROOT / f'corpus/{side}/{shader}.bin').read_bytes()
            assert b''.join(bytes.fromhex(n['raw_hex']) for n in ir['nodes']) == binary
            assert ir['program_sha256'] == sha(binary)
            assert len(ir['nodes']) == count
            graph = load(ROOT / f'dependency/graphs/{shader}-{side}.json')
            assert len(graph['pairs']) == count*(count-1)//2
            message_count = len(load(ROOT / f'ir/messages/{shader}-{side}.json')['messages'])
            if side == 'source':
                source_total += count
                source_send += message_count
            else:
                target_total += count
                target_send += message_count
        comparison = load(ROOT / f'validator/outputs/{shader}-comparison.json')
        assert len(comparison['findings']) == count*12 and comparison['mapping_failure'] is None
        assert comparison['hardware_validated'] is False
        findings_total += len(comparison['findings'])
        for f in comparison['findings']:
            assert f['source_raw_hex'] and f['target_raw_hex'] and f['rule'] and f['evidence']
            assert f['detail'] and f['minimal_repair'] and f['necessary_assumptions']
    assert (source_total, target_total, findings_total, source_send, target_send) == (79, 79, 948, 10, 10)
    expansion = load(ROOT / 'runs/expansion-015/results.json')
    assert expansion['status'] == 'PASS' and expansion['source_nodes'] != expansion['target_nodes']
    for p in ROOT.rglob('*.pyc'):
        # Third-party dependencies are installed without compiling bytecode.
        raise AssertionError('Unexpected bytecode artifact: ' + str(p))
    dump(receipt, {'status': 'PASS', 'required_artifacts': records, 'final_status': state['final_status'],
        'source_nodes': source_total, 'candidate_nodes': target_total, 'layer_findings': findings_total,
        'source_sends': source_send, 'candidate_sends': target_send,
        'fresh_run_verification': state['latest_verification'], 'mutants': state['latest_mutation_verification'],
        'independent_audit': 'review/final/closure.json',
        'native_scope': 'Archived3build640runs plus independently built Clang/GCC standaloneDebug extension; no hardware execution',
        'bytecode': 'NONE', 'hardware_validated': False})
    print(f'PASS {len(records)} required artifacts,79+79 raw nodes,20messages,948layerfindings,13states')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--receipt', type=Path, required=True)
    args = ap.parse_args()
    audit(args.receipt)
