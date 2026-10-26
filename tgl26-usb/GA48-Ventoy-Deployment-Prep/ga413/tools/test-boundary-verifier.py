#!/usr/bin/env python3
"""CPU-only rejection/acceptance fixtures for three-CB audit and comparisons."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


old_tests = load('ga412_fixtures', ROOT / 'ga412/tools/test-pixel-verifier.py')
verifier = load('ga413_verifier', HERE / 'verify-pixel-dump.py')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def metadata():
    result = old_tests.baseline()
    result.update(schema='ga413-managed-rt-v1', mode='staged-boundary',
                  operation_counts={'render': 1, 'synchronize': 1, 'copy': 1},
                  gpu_frozen_ns=160, cpu_getBytes_begin_ns=170, cpu_getBytes_end_ns=180)
    commands = []
    for ordinal, stage in enumerate(verifier.STAGES, 1):
        command = copy.deepcopy(result['commands'][0])
        shift = (ordinal - 1) * 50
        for key in ['created_ns', 'commit_ns', 'wait_begin_ns', 'completed_callback_ns', 'completion_observed_ns']:
            command[key] += shift
        command.update(id=f'fixture-cb-{ordinal}', ordinal=ordinal, stage=stage,
                       resources={'source': result['source'], 'target': result['target'],
                                  'readback_buffer': {'storage': 0, 'length': 332800}})
        commands.append(command)
    result['commands'] = commands
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'ga413/out' / ('fixtures-' + uuid.uuid4().hex[:12]))
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists() and not args.report.exists(), 'preserve earlier fixture results')
    args.output.mkdir(parents=True)
    source, expected = verifier.base.load_generator()()
    tests, directories = [], {}

    def fixture(name, mutate=None, expected_code=0, file_change=None):
        directory = args.output / name; directory.mkdir()
        data = {'input': bytearray(source), 'expected': bytearray(expected),
                'gpu': bytearray(expected), 'cpu': bytearray(expected)}
        result = metadata()
        if mutate:
            mutate(data, result)
        for n, raw in data.items():
            (directory / f'{n}.bin').write_bytes(raw)
        (directory / 'result.json').write_text(json.dumps(result))
        for ordinal, command in enumerate(result['commands'], 1):
            (directory / f'command-{ordinal}.json').write_text(json.dumps(command))
        if file_change:
            file_change(directory)
        reports = []
        for optimized in (False, True):
            command = [sys.executable] + (['-O'] if optimized else []) + [str(HERE / 'verify-pixel-dump.py'), str(directory)]
            completed = subprocess.run(command, capture_output=True, text=True)
            suffix = 'optimized' if optimized else 'normal'
            (directory / f'{suffix}.stdout.json').write_text(completed.stdout)
            (directory / f'{suffix}.stderr').write_text(completed.stderr)
            require(completed.returncode == expected_code, f'{name}/{suffix}: {completed.returncode}: {completed.stdout[:250]}')
            report = json.loads(completed.stdout)
            require(report['status'] == {0: 'PIXEL_PASS', 1: 'PIXEL_FAIL', 2: 'INVALID'}[expected_code], name)
            reports.append(report)
        require(reports[0] == reports[1], '-O changed acceptance: ' + name)
        directories[name] = directory
        tests.append({'fixture': name, 'status': reports[0]['status'], 'returncode': expected_code,
                      'normal_and_optimized_identical': True})

    fixture('clean')
    fixture('CPU-one-byte', lambda d, r: d['cpu'].__setitem__(0, 1), 1)
    fixture('both-same-wrong', lambda d, r: (d['cpu'].__setitem__(slice(None), bytes(83200)), d['gpu'].__setitem__(slice(None), bytes(83200))), 1)
    for index in range(3):
        fixture(f'failed-CB-{index + 1}', lambda d, r, i=index: r['commands'][i].update(status=5, error='fault', error_code=1), 2)
    fixture('missing-CB', lambda d, r: r['commands'].pop(), 2)
    fixture('duplicate-CB', lambda d, r: r['commands'][1].update(id=r['commands'][0]['id']), 2)
    fixture('wrong-stage', lambda d, r: r['commands'][0].update(stage='copy'), 2)
    fixture('wrong-ordinal', lambda d, r: r['commands'][1].update(ordinal=3), 2)
    fixture('overlapping-boundaries', lambda d, r: r['commands'][1].update(created_ns=49), 2)
    fixture('missing-callback', lambda d, r: r['commands'][1].update(completed_callback_ns=0), 2)
    fixture('timed-out', lambda d, r: r['commands'][1].update(timeout=True), 2)
    fixture('wait-not-returned', lambda d, r: r['commands'][0].update(wait_returned=False), 2)
    fixture('changed-resource', lambda d, r: r['commands'][1]['resources'].update(target=dict(r['target'], width=256)), 2)
    fixture('changed-readback-size', lambda d, r: r['commands'][2]['resources']['readback_buffer'].update(length=83200), 2)
    fixture('extra-copy', lambda d, r: r['operation_counts'].update(copy=2), 2)
    fixture('wrong-row', lambda d, r: r.update(output_pitch=1028), 2)
    fixture('freeze-too-early', lambda d, r: r.update(gpu_frozen_ns=100), 2)
    fixture('truncated-data', lambda d, r: d.__setitem__('cpu', d['cpu'][:-1]), 2)
    fixture('missing-command-file', expected_code=2, file_change=lambda p: (p / 'command-2.json').unlink())
    fixture('tampered-command-file', expected_code=2, file_change=lambda p: (p / 'command-1.json').write_text('{}'))
    fixture('missing-GPU-file', expected_code=2, file_change=lambda p: (p / 'gpu.bin').unlink())
    fixture('no-observer', lambda d, r: r['tracer'].update(installed=0), 2)

    # Separate historical legacy fixture with two known errors, including last-row blue.
    historical = args.output / 'legacy'; historical.mkdir()
    data = {'input': source, 'expected': expected, 'gpu': expected, 'cpu': bytearray(expected)}
    data['cpu'][0] = 1; data['cpu'][82946] = 1
    for name, raw in data.items():
        (historical / f'{name}.bin').write_bytes(raw)
    (historical / 'result.json').write_text(json.dumps(old_tests.baseline()))
    fixture('same-two-errors', lambda d, r: (d['cpu'].__setitem__(0, 1), d['cpu'].__setitem__(82946, 1)), 1)
    fixture('shifted-error', lambda d, r: d['cpu'].__setitem__(1, 1), 1)
    fixture('GPU-correct-CPU-all-wrong', lambda d, r: d['cpu'].__setitem__(slice(None), bytes(83200)), 1)
    comparisons = []
    for name in ['clean', 'same-two-errors', 'shifted-error', 'GPU-correct-CPU-all-wrong', 'failed-CB-2']:
        completed = subprocess.run([sys.executable, str(HERE / 'compare-boundaries.py'), str(historical), str(directories[name])],
                                   capture_output=True, text=True)
        (directories[name] / 'comparison.json').write_text(completed.stdout)
        expected_code = 2 if name == 'failed-CB-2' else 0
        require(completed.returncode == expected_code, 'comparison ' + name)
        report = json.loads(completed.stdout)
        if name != 'failed-CB-2':
            p = report['pattern_comparison']
            if name == 'clean': require(p['legacy_only'] == 2 and p['bad_byte_positions_common'] == 0, 'clean delta')
            if name == 'same-two-errors': require(p['identical_error_location_mask'] and p['identical_wrong_values_at_common_error_positions'] == 2, 'same error positions/values')
            if name == 'shifted-error': require(p['legacy_only'] == 2 and p['staged_only'] == 1 and p['bad_byte_positions_common'] == 0, 'error position shift')
            if name == 'GPU-correct-CPU-all-wrong': require('locked backing' in report['interpretation'], 'next hypothesis selection')
        comparisons.append({'fixture': name, 'returncode': completed.returncode})
    report = {'status': 'CPU_TEST_PASS', 'GPU_commands_submitted': False, 'fixture_count': len(tests),
              'verifier_CLI_invocations': len(tests) * 2, 'comparison_CLI_invocations': len(comparisons),
              'cases': tests, 'comparison_cases': comparisons,
              'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [Path(__file__), HERE / 'verify-pixel-dump.py', HERE / 'compare-boundaries.py']}}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ['status', 'fixture_count', 'verifier_CLI_invocations', 'comparison_CLI_invocations', 'GPU_commands_submitted']}))


if __name__ == '__main__':
    main()
