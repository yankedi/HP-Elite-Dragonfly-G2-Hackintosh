#!/usr/bin/env python3
"""Export existing deterministic captures/CPU fixtures and authentic logs for review."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
GA = ROOT / 'ga415'
SPEC = importlib.util.spec_from_file_location('verifier', GA / 'tools/verify-capture.py')
v = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(v)


def copy(source, dest):
    if source.is_dir():
        if dest.exists():
            assert {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()} == {str(p.relative_to(dest)): hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file()}
        else: shutil.copytree(source, dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists(): assert dest.read_bytes() == source.read_bytes()
        else: shutil.copyfile(source, dest)


def main():
    captures = GA / 'captures'; captures.mkdir(exist_ok=True)
    checks = []
    for case in 'ABC':
        source = GA / 'private' / ('case-' + case)
        dest = captures / ('case-' + case); copy(source / ('gpu-' + case), dest / ('gpu-' + case))
        for suffix in ['stdout', 'stderr', 'exit']:
            copy(source / ('gpu-' + case + '.' + suffix), dest / ('gpu-' + case + '.' + suffix))
        actual = v.verify(dest / ('gpu-' + case))
        previous = json.loads((GA / 'reports' / ('CASE-' + case + '-PIXELS-v2.json')).read_text())
        for key in ('CASE_ID', 'RESULT', 'CPU_RESULT', 'BAD_PIXELS', 'DIFFERENT_BYTES', 'FIRST_BAD_PIXEL',
                    'earliest_observable_difference', 'independent_expected_active_sha256', 'files'):
            assert actual[key] == previous[key], key
        for name, comparison in actual['comparisons'].items():
            for key in ('RESULT', 'BAD_PIXELS', 'DIFFERENT_BYTES', 'FIRST_BAD_PIXEL'):
                assert comparison[key] == previous['comparisons'][name][key], (name, key)
        (GA / 'reports' / ('CASE-' + case + '-PIXELS-export.json')).write_text(json.dumps(actual, indent=2) + '\n')
        checks.append({'case': case, 'status': actual['RESULT'], 'copied_capture_primary_pixel_counts_and_hashes_identical': True,
                       'note': 'Current verifier also includes later legacy-tile candidate diagnostics; original v2 reports preserved.'})
    fixtures = GA / 'fixtures'; fixtures.mkdir(exist_ok=True)
    fixture_source = GA / 'private/cpu-fixtures-v5'; copy(fixture_source, fixtures / 'pixel-tools')
    tests = json.loads((fixtures / 'pixel-tools/TEST-RESULT.json').read_text())
    assert tests['status'] == 'CPU_TEST_PASS' and len(tests['tests']) == 24 and not tests['GPU_commands_submitted']
    copy(GA / 'private/cpu-build-v2/cpu-align16-B', fixtures / 'native-cpu-capture-B')
    copy(GA / 'private/verifier-fixtures-v1/TEST-RESULT.json', fixtures / 'verifier-adversarial-result.json')
    build = GA / 'private/cpu-build-v2/build-v2'
    for name in ['build.stdout', 'build.stderr']: copy(build / name, GA / 'reports/native-build-v2' / name)
    for name in ['build.log', 'image-build.log']: copy(GA / 'private/blit-observer' / name, GA / 'reports/blit-observer-logs' / name)
    receipt = json.loads((GA / 'private/commands/blitobs-cpu-test-contract.json').read_text())
    assert receipt['returncode'] == 0
    (GA / 'reports/blit-observer-logs/cpu-contract.stdout').write_text(receipt['stdout'])
    (GA / 'reports/blit-observer-logs/cpu-contract.stderr').write_text(receipt['stderr'])
    inventory = {}
    for folder in [captures, fixtures, GA / 'reports/native-build-v2', GA / 'reports/blit-observer-logs']:
        for path in sorted(folder.rglob('*')):
            if path.is_file(): inventory[str(path.relative_to(GA))] = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    report = {'status': 'DETERMINISTIC_REAL_CAPTURES_AND_CPU_FIXTURES_EXPORTED', 'actual_cases': checks,
              'synthetic_checks': 24, 'adversarial_verifier_checks': 13, 'new_GPU_submissions': 0, 'files': inventory,
              'limits': 'Captured affine test images are real GPU outputs. Synthetic fixtures are explicitly labelled. Desktop screenshots and machine health receipts remain under private/.'}
    (GA / 'reports/EVIDENCE-EXPORT.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['status', 'actual_cases', 'new_GPU_submissions']}))


if __name__ == '__main__':
    main()
