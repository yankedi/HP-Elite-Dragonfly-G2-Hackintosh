#!/usr/bin/env python3
"""Adversarial synthetic metadata/dump fixtures. Never runtime GPU evidence."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('capture_verifier', HERE / 'verify-capture.py')
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)


def main():
    p = argparse.ArgumentParser(); p.add_argument('--cpu-capture', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False); tests = []
    original = json.loads((a.cpu_capture / 'result.json').read_text())
    assert original['cpu_only'] is True
    def case(name, edit, expected):
        dest = a.output / name; shutil.copytree(a.cpu_capture, dest)
        edit(dest)
        try: result = v.verify(dest); classification = result['RESULT']
        except (ValueError, OSError, KeyError, TypeError): classification = 'CAPTURE_INVALID'
        assert classification == expected, (name, classification)
        tests.append(dict(name=name, expected=expected, actual=classification,
                          origin='SYNTHETIC_CPU_FIXTURE_NOT_GPU_RUNTIME'))
    def mutate_json(path, name, fn, refresh_record=False):
        obj = json.loads((path / name).read_text()); fn(obj)
        (path / name).write_text(json.dumps(obj))
        if refresh_record:
            r = json.loads((path / 'result.json').read_text()); data = (path / name).read_bytes()
            r['files'][name].update(bytes=len(data), sha256=v.diff.sha(data))
            (path / 'result.json').write_text(json.dumps(r))
    case('cpu-not-gpu-pass', lambda p: None, 'CAPTURE_PATH_UNVERIFIED')
    case('missing-dump', lambda p: (p / 'iosurface-before.bin').unlink(), 'CAPTURE_INVALID')
    case('short-dump', lambda p: (p / 'iosurface-before.bin').write_bytes(b'\x00'), 'CAPTURE_INVALID')
    case('geometry', lambda p: mutate_json(p, 'resource.json', lambda r: r.update(width=1), True), 'CAPTURE_INVALID')
    case('submitted-in-cpu', lambda p: mutate_json(p, 'command.json', lambda r: r.update(submitted=True), True), 'CAPTURE_INVALID')
    case('mode-mismatch', lambda p: mutate_json(p, 'result.json', lambda r: r.update(cpu_only=False)), 'CAPTURE_INVALID')
    case('unsafe-path', lambda p: mutate_json(p, 'result.json', lambda r: r['files'].update({'../escape':{}})), 'CAPTURE_INVALID')
    case('unsupported-schema', lambda p: mutate_json(p, 'result.json', lambda r: r.update(schema='made-up')), 'CAPTURE_INVALID')
    def wrong_expected(p):
        data = bytearray((p / 'expected.bin').read_bytes()); data[0] ^= 1
        (p / 'expected.bin').write_bytes(data)
        def edit(r): r['files']['expected.bin'].update(sha256=v.diff.sha(data), active_sha256=v.diff.sha(data))
        mutate_json(p, 'result.json', edit)
    case('self-consistent-wrong-expected', wrong_expected, 'CAPTURE_INVALID')
    def source_mismatch(p):
        data = bytearray((p / 'input.bin').read_bytes()); data[0] ^= 1
        (p / 'input.bin').write_bytes(data)
        def edit(r): r['files']['input.bin'].update(sha256=v.diff.sha(data), active_sha256=v.diff.sha(data))
        mutate_json(p, 'result.json', edit)
    case('self-consistent-wrong-input', source_mismatch, 'CAPTURE_INVALID')
    for state in ['GPU_COMMAND_FAIL', 'RESOURCE_READBACK_FAIL', 'CAPTURE_PATH_UNVERIFIED']:
        case(state, lambda p, s=state: mutate_json(p, 'result.json', lambda r: r.update(RESULT=s)), state)
    report = dict(status='CPU_ADVERSARIAL_VERIFIER_TEST_PASS', tests=tests, GPU_commands_submitted=False)
    (a.output / 'TEST-RESULT.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'], checks=len(tests), GPU_commands_submitted=False)))


if __name__ == '__main__': main()
