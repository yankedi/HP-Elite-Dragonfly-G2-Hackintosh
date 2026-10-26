#!/usr/bin/env python3
"""Synthetic corruption fixtures only; never GPU evidence."""
import argparse
import importlib.util
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), HERE / (name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def main():
    p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    pat = load('expected-pattern'); diff = load('pixel-diff')
    w, h = 67, 17; exp = pat.generate(w, h, 'alpha'); results = []
    def check(name, actual, expected, assertion):
        r = diff.compare(actual, expected, w, h)
        assert assertion(r), (name, r['BAD_PIXELS'], r['ERROR_PATTERN'])
        dest = a.output / name; dest.mkdir()
        (dest / 'actual.bin').write_bytes(actual); (dest / 'expected.bin').write_bytes(expected)
        r['origin'] = 'SYNTHETIC_CPU_FIXTURE_NOT_GPU_RUNTIME'
        (dest / 'result.json').write_text(json.dumps(r, indent=2) + '\n')
        results.append(dict(name=name, status='PASS'))
    check('identical', exp, exp, lambda r: r['RESULT'] == 'PIXEL_PASS' and r['DIFFERENT_BYTES'] == 0)
    check('all-zero', bytes(len(exp)), exp, lambda r: r['BAD_PIXELS'] == w * h - 1 and 'ALL_RGBA_ZERO' in r['ERROR_PATTERN'])
    altered = bytearray(exp); altered[4 * (w + 3)] ^= 1
    check('single-byte', altered, exp, lambda r: r['BAD_PIXELS'] == 1 and r['DIFFERENT_BYTES'] == 1 and r['FIRST_BAD_PIXEL']['x'] == 3 and r['FIRST_BAD_PIXEL']['y'] == 1)
    altered = bytearray(exp)
    for i in range(3, len(altered), 4): altered[i] ^= 1
    check('alpha-only', altered, exp, lambda r: 'RGB_CORRECT_ALPHA_WRONG' in r['ERROR_PATTERN'])
    altered = bytearray(exp)
    for i in range(0, len(altered), 4): altered[i] ^= 1
    check('rgb-only', altered, exp, lambda r: 'ALPHA_CORRECT_RGB_WRONG' in r['ERROR_PATTERN'])
    shifted = b''.join(exp[y * w * 4:(y + 1) * w * 4][-12:] + exp[y * w * 4:(y + 1) * w * 4][:-12] for y in range(h))
    check('shift-3px', shifted, exp, lambda r: len(r['horizontal_shift_candidates']) == h and all(v['dx'] == 3 for v in r['horizontal_shift_candidates']))
    skew = b''.join(exp[y * w * 4:(y + 1) * w * 4][-4 * (y % 8 + 1):] + exp[y * w * 4:(y + 1) * w * 4][:-4 * (y % 8 + 1)] for y in range(h))
    check('row-skew', skew, exp, lambda r: 'ROW_DEPENDENT_SHIFT_CANDIDATE' in r['ERROR_PATTERN'])
    swapped = exp[w * 4:] + exp[:w * 4]
    check('row-order', swapped, exp, lambda r: len(r['row_reorder_candidates']) == h)
    repeated = bytearray(exp)
    for y in range(h): repeated[(y * w + 16) * 4:(y * w + 32) * 4] = exp[y * w * 4:(y * w + 16) * 4]
    check('repeat-16', repeated, exp, lambda r: 'ADJACENT_BLOCK_REPEAT_CANDIDATE' in r['ERROR_PATTERN'])
    premul = bytearray(exp)
    for i in range(0, len(exp), 4):
        for c in range(3): premul[i + c] = round(exp[i + c] * exp[i + 3] / 255)
    check('premultiplied', premul, exp, lambda r: 'STRAIGHT_VS_PREMULTIPLIED_CANDIDATE' in r['ERROR_PATTERN'])
    padded = pat.generate(w, h, 'alpha', bpr=320, padding=238)
    assert diff.packed(padded, w, h, 320) == exp
    for label, data, bpr in [('short', padded[:-1], 320), ('extra', padded + b'X', 320), ('bad-bpr', exp, 1)]:
        try: diff.packed(data, w, h, bpr)
        except ValueError: results.append(dict(name=label, status='PASS'))
        else: raise AssertionError('Malformed data accepted: ' + label)
    r = diff.compare(bytes(len(exp)), exp, w, h, previous=bytes(len(exp)))
    assert 'EXACT_KNOWN_PREVIOUS_FRAME' in r['ERROR_PATTERN']
    assert diff.compare(bytes(len(exp)), exp, w, h)['previous_frame_exact_match'] == 'NOT_OBSERVED'
    assert 'EXACT_KNOWN_INITIALIZATION_BYTE' in diff.compare(b'\xee' * len(exp), exp, w, h, initial=238)['ERROR_PATTERN']
    for name in pat.PATTERNS:
        data = pat.generate(w, h, name); assert len(data) == len(exp)
        assert diff.compare(data, data, w, h)['RESULT'] == 'PIXEL_PASS'
        results.append(dict(name='pattern-' + name, status='PASS'))
    # Non-random independent anchors avoid self-comparison-only testing.
    assert pat.pixel(1, 1) == (42, 18, 20, 255)
    assert pat.pixel(16, 2, 'blocks64') == (1, 2, 75, 255)
    assert pat.pixel(0, 0, 'alpha') == (0, 0, 0, 0)
    image = Image.new('RGBA', (100, 50), (12, 34, 56, 255))
    image.paste((0, 0, 0, 255), (10, 12, 90, 30))
    assert [10, 12, 80, 18] in diff.black_rectangles(image)
    image.save(a.output / 'synthetic-black-rectangle.png')
    results.append(dict(name='black-rectangle-candidate-coordinates', status='PASS'))
    tw, th = 256, 32
    reference = pat.generate(tw, th)
    for layout in ('X', 'Y0'):
        tiled = bytearray(len(reference))
        for y in range(th):
            for x in range(tw):
                addr = diff.legacy_tile_address(x, y, tw * 4, layout)
                tiled[addr:addr + 4] = reference[(y * tw + x) * 4:(y * tw + x) * 4 + 4]
        r = diff.compare(tiled, reference, tw, th)
        assert 'LEGACY_TILE_' + layout + '_CANDIDATE' in r['ERROR_PATTERN']
        (a.output / ('synthetic-tile-' + layout + '.bin')).write_bytes(tiled)
        results.append(dict(name='legacy-layout-' + layout + '-candidate', status='PASS'))
    result = dict(status='CPU_TEST_PASS', origin='SYNTHETIC_CPU_FIXTURE_NOT_GPU_RUNTIME',
                  tests=results, padding_excluded=True, known_previous_required=True, GPU_commands_submitted=False)
    (a.output / 'TEST-RESULT.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(status=result['status'], checks=len(results), GPU_commands_submitted=False)))


if __name__ == '__main__': main()
