#!/usr/bin/env python3
"""Second, independent packed-RGBA audit of immutable real A/B/C captures."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from PIL import Image


def digest(data): return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--capture-root', type=Path, help='Optional exported captures/ directory instead of private/')
    p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False); cases = []
    for case, w, h in [('A', 640, 100), ('B', 642, 32), ('C', 642, 100)]:
        base = (a.capture_root or a.root / 'private') / ('case-' + case); capture = base / ('gpu-' + case)
        r = json.loads((capture / 'resource.json').read_text())
        c = json.loads((capture / 'command.json').read_text())
        manifest = json.loads((capture / 'result.json').read_text())
        assert (base / ('gpu-' + case + '.exit')).read_text().strip() == '0'
        assert c['status'] == 4 and not c['error'] and c['error_code'] == 0 and c['wait_returned'] and not c['timeout']
        assert r['pattern'] == 'affine' and r['width'] == w and r['height'] == h
        # Separate linear-index construction; imports neither primary verifier nor expected generator.
        reference = bytearray()
        for k in range(w * h):
            x, y = k % w, k // w
            reference.extend(((13*x + 29*y) % 256, (7*x + 11*y) % 256, (3*x + 17*y) % 256, 255))
        reference = bytes(reference); stages = {}; packed = {}
        dest = a.output / case; dest.mkdir()
        for name in ['input.bin', 'expected.bin', 'iosurface-before.bin', 'iosurface-after.bin', 'upload-proxy.bin', 'gpu.bin', 'cpu.bin']:
            full = (capture / name).read_bytes(); entry = manifest['files'][name]; pitch = entry['bpr']
            assert digest(full) == entry['sha256'] and len(full) == entry['bytes'] == pitch * h
            pixels = b''.join(memoryview(full)[pitch*y:pitch*y + 4*w] for y in range(h))
            assert digest(pixels) == entry['active_sha256']; packed[name] = pixels
            pairs = list(zip(struct.iter_unpack('4B', pixels), struct.iter_unpack('4B', reference)))
            bad = sum(actual != expected for actual, expected in pairs)
            different = sum(a != b for a, b in zip(pixels, reference))
            first = next((dict(x=k % w, y=k // w, actual=list(v[0]), expected=list(v[1]))
                          for k, v in enumerate(pairs) if v[0] != v[1]), 'NONE')
            stages[name] = dict(RESULT='PIXEL_FAIL' if bad else 'PIXEL_PASS', bad_pixels=bad, different_bytes=different,
                                first_bad_pixel=first, full_sha256=digest(full), active_sha256=digest(pixels),
                                bpr=pitch, valid_pixel_bytes=len(pixels), padding_bytes_excluded=len(full)-len(pixels),
                                active_byte_values=sorted(set(pixels)))
            Image.frombytes('RGBA', (w, h), pixels).save(dest / (name + '.png'))
            heat = bytes(v for actual, expected in pairs for v in ((255, 0, 0, 255) if actual != expected else (0, 0, 0, 255)))
            Image.frombytes('RGBA', (w, h), heat).save(dest / (name + '-error-map.png'))
        assert packed['input.bin'] == packed['expected.bin'] == reference
        assert packed['iosurface-before.bin'] == packed['iosurface-after.bin'] == reference
        primary = json.loads((a.root / 'reports' / ('CASE-' + case + '-PIXELS-v2.json')).read_text())
        for name in stages:
            if name == 'expected.bin': continue
            pc = primary['comparisons'][name + '_vs_expected']
            assert stages[name]['bad_pixels'] == pc['BAD_PIXELS']
            assert stages[name]['different_bytes'] == pc['DIFFERENT_BYTES']
        case_result = dict(case=case, width=w, height=h, actual_surface_bpr=r['iosurface_actual_bpr'],
                           driver_uuid=r['driver_uuid'], command_status=c['status'], explicit_command_buffers=c['explicit_command_buffers'],
                           independently_expected_sha256=digest(reference), stages=stages,
                           CPU_vs_GPU_exact=packed['cpu.bin'] == packed['gpu.bin'],
                           both_verifiers_agree=True, root_cause='ROOT_CAUSE_UNVERIFIED')
        (dest / 'audit.json').write_text(json.dumps(case_result, indent=2) + '\n'); cases.append(case_result)
    assert all(v['stages']['gpu.bin']['RESULT'] == 'PIXEL_PASS' for v in cases[:2])
    assert cases[1]['stages']['upload-proxy.bin']['active_byte_values'] == [238]
    assert cases[2]['stages']['gpu.bin']['active_byte_values'] == [0]
    report = dict(status='INDEPENDENT_REAL_CAPTURE_AUDIT_PASS', cases=cases,
                  origin='REAL_HP_GPU_CAPTURES; no new GPU work performed by this auditor',
                  classified_root_cause='ROOT_CAUSE_UNVERIFIED')
    (a.output / 'INDEPENDENT-AUDIT.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status=report['status'], C_bad_pixels=cases[2]['stages']['gpu.bin']['bad_pixels'],
                          B_direct_copy_bad_pixels=cases[1]['stages']['upload-proxy.bin']['bad_pixels'], GPU_submissions_by_auditor=0)))


if __name__ == '__main__': main()
