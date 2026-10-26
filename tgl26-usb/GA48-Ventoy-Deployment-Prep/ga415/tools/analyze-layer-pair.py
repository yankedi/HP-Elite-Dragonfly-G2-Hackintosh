#!/usr/bin/env python3
"""Offline registered full/window screenshot differences, not GPU truth labels."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageChops

SPEC = importlib.util.spec_from_file_location('pixel_diff', Path(__file__).with_name('pixel-diff.py'))
pd = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(pd)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def changes(a, b):
    assert a.size == b.size
    aa, bb = a.convert('RGBA').tobytes(), b.convert('RGBA').tobytes()
    bad = sum(aa[i:i + 4] != bb[i:i + 4] for i in range(0, len(aa), 4))
    delta = ImageChops.difference(a.convert('RGB'), b.convert('RGB'))
    pixels = [max(abs(aa[i + c] - bb[i + c]) for c in range(3)) for i in range(0, len(aa), 4)]
    histogram = {str(t): sum(v > t for v in pixels) for t in (1, 2, 8, 32, 64)}
    uniform = []
    for c in range(4):
        deltas = {y - x for x, y in zip(aa[c::4], bb[c::4])}
        uniform.append(next(iter(deltas)) if len(deltas) == 1 else 'NOT_UNIFORM')
    return {'different_pixels': bad, 'different_fraction': bad / (a.width * a.height),
            'different_bytes': sum(x != y for x, y in zip(aa, bb)),
            'different_bytes_by_channel': {name: sum(x != y for x, y in zip(aa[c::4], bb[c::4])) for c, name in enumerate('RGBA')},
            'RGB_max_channel_delta_exceeds': histogram,
            'uniform_RGBA_channel_delta': uniform,
            'small_delta_limit': 'Large exact-difference counts can include one-level color/capture/rounding changes. Threshold counts are descriptive, not error labels.',
            'RGB_difference_bounds': delta.getbbox(),
            'interpretation': 'Decoded screenshot differences; neither image is an independent Expected.'}, delta


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pair', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); a.output.mkdir(parents=True, exist_ok=False)
    pair = a.pair
    assert (pair / 'run.stdout').read_text().endswith('LAYER_PAIR_COMPLETE\n')
    assert (pair / 'run.stderr').read_text() == ''
    window_id = int(next(s.split('=')[1] for s in (pair / 'run.stdout').read_text().splitlines() if s.startswith('WINDOW_ID=')))
    states = {}; records = {}; regions = {}
    for side in ('before', 'after'):
        meta = json.loads((pair / (side + '-metadata/capture.json')).read_text())
        window = next(w for w in json.loads((pair / (side + '-metadata/windows.json')).read_text()) if w['kCGWindowNumber'] == window_id)
        assert window['kCGWindowOwnerName'] == 'System Settings'
        display = next(d for d in meta['displays'] if d['main'])
        assert display['scale_x'] == 1
        full = Image.open(pair / (side + '.png')).convert('RGBA')
        direct = Image.open(pair / (side + '-window.png')).convert('RGBA')
        b = window['kCGWindowBounds']; x, y, w, h = (int(b[k]) for k in ['X', 'Y', 'Width', 'Height'])
        assert direct.size == (w, h) and full.size == (display['framebuffer_width'], display['framebuffer_height'])
        states[side] = {'window_id': window_id, 'title': window.get('kCGWindowName', 'NOT_OBSERVED'),
                        'bounds': [x, y, w, h], 'display': display}
        records[side] = {'full': full, 'window': direct}
        for kind, image in [('full', full), ('window', direct)]:
            source = pair / (side + ('.png' if kind == 'full' else '-window.png'))
            source_image = Image.open(source)
            states[side][kind] = {'PNG_sha256': sha(source.read_bytes()), 'RGBA_sha256': sha(image.tobytes()),
                                  'ICC_sha256': sha(source_image.info['icc_profile']) if source_image.info.get('icc_profile') else 'NOT_OBSERVED',
                                  'size': list(image.size), 'black_candidates': pd.black_rectangles(image)}
        rois = [('sidebar', (15, 65, 190, 840)), ('content', (240, 60, 460, 840)),
                ('battery-label', (62, 260, 140, 35)), ('display-control', (550, 650, 145, 30))]
        for label, (rx, ry, rw, rh) in rois:
            assert x + rx + rw <= full.width and y + ry + rh <= full.height
            on_screen = full.crop((x + rx, y + ry, x + rx + rw, y + ry + rh))
            offscreen = direct.crop((rx, ry, rx + rw, ry + rh))
            regions[side, label, 'full'] = on_screen
            regions[side, label, 'window'] = offscreen
            entry = {'bounds_window_pixels': [rx, ry, rw, rh], 'bounds_screen_pixels': [x + rx, y + ry, rw, rh],
                     'capture_path_comparison': changes(on_screen, offscreen)[0]}
            for kind, image in [('full', on_screen), ('window', offscreen)]:
                prefix = side + '-' + label + '-' + kind
                image.save(a.output / (prefix + '.png'))
                (a.output / (prefix + '.rgba')).write_bytes(image.tobytes())
                entry[kind] = pd.image_stats(image)
            changes(on_screen, offscreen)[1].save(a.output / (side + '-' + label + '-capture-difference.png'))
            states[side].setdefault('ROIs', {})[label] = entry
    old, new = states['before']['bounds'], states['after']['bounds']
    assert old[2:] == new[2:] and states['before']['title'] == states['after']['title']
    movement = [new[0] - old[0], new[1] - old[1]]
    comparisons = {}
    for label in ('sidebar', 'content', 'battery-label', 'display-control'):
        for kind in ('full', 'window'):
            value, diff = changes(regions['before', label, kind], regions['after', label, kind])
            key = label + '-' + kind; comparisons[key] = value
            diff.save(a.output / (key + '-movement-difference.png'))
    result = {'status': 'ACTUAL_PAIRED_SCREENSHOTS_ANALYZED', 'window_id': window_id,
              'movement_pixels': movement, 'capture_methods': {'full': 'system screencapture -x', 'window': 'system screencapture -x -o -l WINDOW_ID'},
              'states': states, 'registered_before_after': comparisons,
              'same_exact_error_follows_window': 'NOT_PROVEN; artifacts change on redraw and between sequential captures',
              'capture_path_limits': 'Full and individual captures are sequential, not simultaneous. Neither is an Expected image. Alpha/color, compositing, redraw and capture operations can differ.',
              'scanout_only_cause': 'Insufficient explanation: corruption is present in stored full and individual window PNGs.',
              'ROOT_CAUSE': 'ROOT_CAUSE_UNVERIFIED'}
    result['output_files'] = {str(f.relative_to(a.output)): {'bytes': f.stat().st_size, 'sha256': sha(f.read_bytes())}
                              for f in sorted(a.output.iterdir()) if f.is_file()}
    (a.output / 'analysis.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'movement_pixels': movement,
                      'registered_before_after': comparisons}, indent=2))


if __name__ == '__main__':
    main()
