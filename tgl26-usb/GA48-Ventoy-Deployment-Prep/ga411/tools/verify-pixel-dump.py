#!/usr/bin/env python3
"""Independently audit a managed-rt-probe dump; stdout is JSON, rc0 only for pixels+commands PASS."""
import hashlib
import json
from pathlib import Path
import sys

W, H, ROW = 257, 65, 1280


def compare(left, right):
    changed_bytes = changed_pixels = 0
    first = []
    for y in range(H):
        for x in range(W):
            bad = False
            for channel in range(4):
                i = y * ROW + x * 4 + channel
                if left[i] != right[i]:
                    bad = True
                    changed_bytes += 1
                    if len(first) < 32:
                        first.append({'offset': i, 'x': x, 'y': y, 'channel': channel,
                                      'a': left[i], 'b': right[i]})
            changed_pixels += bad
    return {'differing_bytes': changed_bytes, 'bad_pixels': changed_pixels,
            'total_pixels': W * H, 'first_differences': first}


def audit(directory):
    result = json.loads((directory / 'result.json').read_text())
    case, mode = result['case'], result['mode']
    assert case in ('R8', 'RGBA8', 'BGRA8') and mode in ('legacy', 'staged')
    assert result['width'] == W and result['height'] == H and result['output_pitch'] == ROW
    bpp = 1 if case == 'R8' else 4
    pitch = (W * bpp + 255) & ~255
    assert result['input_pitch'] == pitch and result['input_bpp'] == bpp
    assert all(result['target'][k] == value for k, value in {
        'width': W, 'height': H, 'format': 70, 'storage': 1, 'usage': 4,
        'samples': 1, 'mips': 1, 'array_length': 1,
    }.items()), 'unexpected target attributes'
    assert result['source']['format'] == {'R8': 10, 'RGBA8': 70, 'BGRA8': 80}[case]
    assert result['source']['storage'] == 0 and result['source']['usage'] == 1
    assert all(result['source'][k] == value for k, value in {
        'width': W, 'height': H, 'samples': 1, 'mips': 1, 'array_length': 1,
    }.items()), 'unexpected source geometry'
    raw = {name: (directory / f'{name}.bin').read_bytes() for name in ['input', 'expected', 'gpu', 'cpu']}
    assert len(raw['input']) == pitch * H
    assert all(len(raw[n]) == ROW * H for n in ('expected', 'gpu', 'cpu'))
    expected = bytearray(ROW * H)
    for y in range(H):
        for x in range(W):
            for c in range(bpp):
                assert raw['input'][y * pitch + x * bpp + c] == (x * 13 + y * 29 + c * 61) % 256
            for c in range(4):
                value = (255 if c == 3 else 0) if bpp == 1 and c > 0 else (
                    x * 13 + y * 29 + (2 - c if case == 'BGRA8' and c < 3 else c) * 61
                ) % 256
                expected[y * ROW + x * 4 + c] = value
    assert raw['expected'] == expected, 'expected.bin disagrees with independent pattern reconstruction'
    comparisons = {
        'gpu_vs_expected': compare(raw['gpu'], expected),
        'cpu_vs_expected': compare(raw['cpu'], expected),
        'cpu_vs_gpu': compare(raw['cpu'], raw['gpu']),
    }
    required_stages = ['legacy_render_sync_copy']
    if mode == 'staged':
        required_stages = ['render', 'gpu_copy_before_explicit_sync', 'explicit_sync', 'gpu_copy_after_explicit_sync']
        raw['gpu-before-sync'] = (directory / 'gpu-before-sync.bin').read_bytes()
        assert len(raw['gpu-before-sync']) == ROW * H
        comparisons['gpu_before_vs_expected'] = compare(raw['gpu-before-sync'], expected)
    commands_ok = ([c['stage'] for c in result['commands']] == required_stages and
                   all(c['status'] == 4 and not c['error'] for c in result['commands']))
    reported_agrees = all(
        all(result[k][field] == v[field] for field in ('differing_bytes', 'bad_pixels', 'total_pixels'))
        for k, v in comparisons.items()
    )
    pixel_pass = not comparisons['gpu_vs_expected']['differing_bytes'] and not comparisons['cpu_vs_expected']['differing_bytes']
    if mode == 'staged':
        pixel_pass = pixel_pass and not comparisons['gpu_before_vs_expected']['differing_bytes']
    passed = commands_ok and reported_agrees and pixel_pass and result['status'] == 'PIXEL_PASS'
    return {
        'status': 'PIXEL_AND_COMMANDS_PASS' if passed else 'FAIL', 'case': case, 'mode': mode,
        'commands_ok': commands_ok, 'reported_metrics_agree': reported_agrees,
        'comparisons': comparisons,
        'sha256': {name + '.bin': hashlib.sha256(data).hexdigest() for name, data in raw.items()},
        'result_json_sha256': hashlib.sha256((directory / 'result.json').read_bytes()).hexdigest(),
        'limits': 'No kernel AUX/CCS/rc1474 validation, no desktop or stability acceptance; identity/trace receipts must accompany dump.',
    }, passed


def main():
    if len(sys.argv) != 2:
        print('usage: verify-pixel-dump.py DIRECTORY', file=sys.stderr)
        return 2
    try:
        result, passed = audit(Path(sys.argv[1]))
    except (AssertionError, KeyError, TypeError, ValueError, OSError) as error:
        print(json.dumps({'status': 'INVALID_OR_INCOMPLETE', 'error': str(error)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
