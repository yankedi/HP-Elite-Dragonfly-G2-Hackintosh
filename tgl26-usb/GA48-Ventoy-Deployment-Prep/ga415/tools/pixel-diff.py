#!/usr/bin/env python3
"""Exact RGBA comparison and conservative PNG anomaly candidates (Pillow)."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat

UNKNOWN = 'NOT_OBSERVED'
FIELDS = ('CASE_ID GPU_DEVICE DRIVER_UUID PIXEL_FORMAT WIDTH HEIGHT SOURCE_BPR DEST_BPR '
          'GPU_ROUTE COMMAND_STATUS BAD_PIXELS DIFFERENT_BYTES FIRST_BAD_PIXEL ERROR_PATTERN RESULT').split()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def packed(data, w, h, bpr):
    if w <= 0 or h <= 0 or bpr < w * 4 or len(data) != h * bpr:
        raise ValueError('Exact geometry/length required; padding is excluded, never guessed')
    return b''.join(data[y * bpr:y * bpr + w * 4] for y in range(h))


def legacy_tile_address(x, y, bpr, layout):
    """Legacy Intel X / Y0 address hypotheses, not observed resource layouts."""
    xb = x * 4
    if layout == 'X':
        return (y // 8) * ((bpr + 511) // 512) * 4096 + (xb // 512) * 4096 + y % 8 * 512 + xb % 512
    if layout == 'Y0':
        return (y // 32) * ((bpr + 127) // 128) * 4096 + (xb // 128) * 4096 + (xb % 128 // 16) * 512 + (y % 32) * 16 + xb % 16
    raise ValueError('Unknown legacy layout')


def tile_hypotheses(actual, expected, w, h):
    scores = []
    # Repeated/flat references cannot identify an address transform.
    distinct = len(set(expected[i:i + 4] for i in range(0, len(expected), 4)))
    for layout in ('X', 'Y0'):
        matches = tested = 0; step = max(1, w * h // 8192)
        for p in range(0, w * h, step):
            offset = legacy_tile_address(p % w, p // w, w * 4, layout)
            if offset + 4 <= len(actual):
                tested += 1; matches += actual[offset:offset + 4] == expected[p * 4:p * 4 + 4]
        coverage = tested / len(range(0, w * h, step))
        ratio = matches / tested if tested else 0
        scores.append(dict(layout=layout, checked_pixels=tested, matched_pixels=matches, coverage=coverage,
                           candidate=bool(distinct >= 128 and coverage >= 0.8 and ratio >= 0.99),
                           match_fraction=ratio, assumed_bpr=w * 4,
                           limitation='Legacy X/Y0 byte-address hypothesis only. Unknown internal padding, modifiers and modern tilings are not decoded.'))
    return scores


def compare(actual, expected, w, h, *, previous=None, initial=None):
    actual, expected = bytes(actual), bytes(expected)
    if w <= 0 or h <= 0 or len(actual) != w * h * 4 or len(expected) != len(actual):
        raise ValueError('Invalid active RGBA dimensions')
    if previous is not None and len(previous) != len(actual):
        raise ValueError('Known previous reference length mismatch')
    bad = different = 0
    first = None
    channels = [0] * 4
    bad_rows = [0] * h
    zero_rgb = zero_alpha = zero_rgba = rgb_only = alpha_only = 0
    zero_rows, identical_rows = [], []
    residue = {str(n): [0] * n for n in (64, 128, 256, 512)}
    runs, start = [], None
    for p in range(w * h):
        i = p * 4; a = actual[i:i + 4]; e = expected[i:i + 4]
        if not any(a):
            zero_rgba += 1
            if start is None:
                start = p
        elif start is not None:
            if p - start >= 16:
                runs.append(dict(first_pixel=[start % w, start // w], pixels=p - start))
            start = None
        zero_rgb += not any(a[:3]); zero_alpha += a[3] == 0
        if a != e:
            bad += 1; bad_rows[p // w] += 1
            if first is None:
                first = dict(x=p % w, y=p // w, actual=list(a), expected=list(e))
            alpha_only += a[:3] == e[:3] and a[3] != e[3]
            rgb_only += a[:3] != e[:3] and a[3] == e[3]
            for c in range(4):
                if a[c] != e[c]:
                    channels[c] += 1; different += 1
                    for n in residue:
                        residue[n][(i + c) % int(n)] += 1
    if start is not None and w * h - start >= 16:
        runs.append(dict(first_pixel=[start % w, start // w], pixels=w * h - start))
    row_map = {}
    for y in range(h):
        row_map.setdefault(expected[y * w * 4:(y + 1) * w * 4], []).append(y)
    swapped = []
    for y in range(h):
        row = actual[y * w * 4:(y + 1) * w * 4]
        if not any(row): zero_rows.append(y)
        if row == expected[y * w * 4:(y + 1) * w * 4]: identical_rows.append(y)
        elif row in row_map: swapped.append(dict(actual_row=y, matching_expected_rows=row_map[row][:8]))
    patterns = []
    if bad:
        if zero_rgba == w * h: patterns.append('ALL_RGBA_ZERO')
        if zero_rows: patterns.append('ZERO_FILLED_ROWS')
        if alpha_only == bad: patterns.append('RGB_CORRECT_ALPHA_WRONG')
        if rgb_only == bad: patterns.append('ALPHA_CORRECT_RGB_WRONG')
        if swapped: patterns.append('ROW_REORDER_OR_REPEAT_CANDIDATE')
        for c in range(4):
            if channels[c] and not any(actual[c::4]): patterns.append('CHANNEL_' + 'RGBA'[c] + '_ZERO')
    # Exact row overlaps at small offsets; no inference of internal tiled layout.
    shifts = []
    if bad and w > 32:
        for y in range(h):
            a = actual[y * w * 4:(y + 1) * w * 4]
            e = expected[y * w * 4:(y + 1) * w * 4]
            if a == e: continue
            candidates = []
            for dx in range(-16, 17):
                if not dx: continue
                lo, hi = max(0, dx), min(w, w + dx)
                if a[lo * 4:hi * 4] == e[(lo - dx) * 4:(hi - dx) * 4]: candidates.append(dx)
            if len(candidates) == 1: shifts.append(dict(y=y, dx=candidates[0]))
        if shifts:
            patterns.append('FIXED_HORIZONTAL_SHIFT_CANDIDATE' if len({v['dx'] for v in shifts}) == 1 else 'ROW_DEPENDENT_SHIFT_CANDIDATE')
    premul_matches = 0
    if bad:
        for i in range(0, len(actual), 4):
            a, e = actual[i:i + 4], expected[i:i + 4]
            if a != e and a[3] == e[3] and all(abs(a[c] - round(e[c] * e[3] / 255)) <= 1 for c in range(3)):
                premul_matches += 1
        if premul_matches == bad: patterns.append('STRAIGHT_VS_PREMULTIPLIED_CANDIDATE')
    previous_match = UNKNOWN if previous is None else actual == previous
    if previous_match is True and bad: patterns.append('EXACT_KNOWN_PREVIOUS_FRAME')
    if initial is not None and actual == bytes([initial]) * len(actual) and bad:
        patterns.append('EXACT_KNOWN_INITIALIZATION_BYTE')
    tiles = []
    if bad:
        for n in (16, 32, 64):
            matches = mismatches = 0
            for y in range(h):
                row = actual[y * w * 4:(y + 1) * w * 4]
                erow = expected[y * w * 4:(y + 1) * w * 4]
                for x in range(n, w - n + 1, n):
                    a = row[x * 4:(x + n) * 4]
                    if a != erow[x * 4:(x + n) * 4]:
                        mismatches += 1
                        matches += a == row[(x - n) * 4:x * 4]
            if matches:
                tiles.append(dict(block_width_pixels=n, repeated_bad_blocks=matches, bad_blocks=mismatches))
        if tiles: patterns.append('ADJACENT_BLOCK_REPEAT_CANDIDATE')
    layout_scores = tile_hypotheses(actual, expected, w, h) if bad else []
    for score in layout_scores:
        if score['candidate']: patterns.append('LEGACY_TILE_' + score['layout'] + '_CANDIDATE')
    result = {k: UNKNOWN for k in FIELDS}
    result.update(WIDTH=w, HEIGHT=h, PIXEL_FORMAT='RGBA8Unorm', BAD_PIXELS=bad, DIFFERENT_BYTES=different,
                  FIRST_BAD_PIXEL=first if first is not None else 'NONE',
                  ERROR_PATTERN=patterns or (['UNCLASSIFIED'] if bad else ['NONE']), RESULT='PIXEL_FAIL' if bad else 'PIXEL_PASS',
                  expected_active_sha256=sha(expected), actual_active_sha256=sha(actual),
                  per_channel_different_bytes=dict(zip('RGBA', channels)), bad_pixels_per_row=bad_rows,
                  zero_regions=dict(rgb_zero_pixels=zero_rgb, alpha_zero_pixels=zero_alpha,
                                    rgba_zero_pixels=zero_rgba, complete_zero_rows=zero_rows, linear_zero_runs=runs[:200]),
                  rgb_correct_alpha_wrong=alpha_only, alpha_correct_rgb_wrong=rgb_only,
                  horizontal_shift_candidates=shifts, row_reorder_candidates=swapped[:200],
                  adjacent_block_candidates=tiles, different_byte_residue_histograms=residue,
                  premultiplied_candidate_bad_pixels=premul_matches,
                  previous_frame_exact_match=previous_match,
                  legacy_tile_layout_hypotheses=layout_scores, tile_X_Y_layout='NOT_OBSERVED; candidate transforms are not resource metadata',
                  limits='Exact supplied reference comparison. Does not prove GPU provenance, command success, kernel route or root cause.')
    return result


def black_rectangles(image, minimum=32):
    """Merge identical horizontal exact-black RGB runs. Candidates, not errors."""
    im = image.convert('RGBA'); w, h = im.size; data = im.tobytes()
    live, rects = {}, []
    for y in range(h):
        runs = set(); x = 0
        while x < w:
            if any(data[(y * w + x) * 4:(y * w + x) * 4 + 3]):
                x += 1; continue
            x0 = x
            while x < w and not any(data[(y * w + x) * 4:(y * w + x) * 4 + 3]): x += 1
            if x - x0 >= minimum: runs.add((x0, x))
        for key in list(live):
            if key not in runs:
                y0 = live.pop(key)
                if y - y0 >= 4: rects.append([key[0], y0, key[1] - key[0], y - y0])
        for key in runs: live.setdefault(key, y)
    for key, y0 in live.items():
        if h - y0 >= 4: rects.append([key[0], y0, key[1] - key[0], h - y0])
    return sorted(rects, key=lambda r: r[2] * r[3], reverse=True)[:200]


def image_stats(image):
    im = image.convert('RGBA'); w, h = im.size
    hist = im.histogram(); n = w * h; stat = ImageStat.Stat(im)
    channels = {}
    for c, name in enumerate('RGBA'):
        counts = hist[c * 256:(c + 1) * 256]
        channels[name] = dict(min=stat.extrema[c][0], max=stat.extrema[c][1], mean=stat.mean[c],
                              zero=counts[0], full=counts[255],
                              entropy_bits=-sum(v / n * math.log2(v / n) for v in counts if v))
    data = im.tobytes()
    rows = [sha(data[y * w * 4:(y + 1) * w * 4]) for y in range(h)]
    # Exact repeated columns and rows, plus adjacent-line transition strength.
    cols = [sha(im.crop((x, 0, x + 1, h)).tobytes()) for x in range(w)]
    transitions = []
    for y in range(1, h):
        diff = ImageChops.difference(im.crop((0, y - 1, w, y)), im.crop((0, y, w, y + 1)))
        transitions.append(sum(ImageStat.Stat(diff).mean[:3]) / 3)
    rects = black_rectangles(im)
    colors = Counter(im.get_flattened_data() if hasattr(im, 'get_flattened_data') else im.getdata()).most_common(12)
    vertical = []
    for x in range(1, w):
        d = ImageChops.difference(im.crop((x - 1, 0, x, h)), im.crop((x, 0, x + 1, h)))
        vertical.append(sum(ImageStat.Stat(d).mean[:3]) / 3)
    boundaries = []
    for x, y, rw, rh in rects:
        strips = []
        if y > 0: strips.append(im.crop((x, y - 1, x + rw, y)))
        if y + rh < h: strips.append(im.crop((x, y + rh, x + rw, y + rh + 1)))
        if x > 0: strips.append(im.crop((x - 1, y, x, y + rh)))
        if x + rw < w: strips.append(im.crop((x + rw, y, x + rw + 1, y + rh)))
        boundaries.append(dict(rectangle=[x, y, rw, rh], exterior_edge_mean_RGBA=[ImageStat.Stat(s).mean for s in strips],
                               interior_RGB=[0, 0, 0], interpretation='Edge contrast only; not proof that black is invalid'))
    tile_pairs = []
    for tile in (8, 16, 32, 64):
        equal = total = informative = 0
        for y in range(0, h - tile + 1, tile):
            prior = None
            for x in range(0, w - tile + 1, tile):
                t = im.crop((x, y, x + tile, y + tile)); raw = t.tobytes()
                if prior is not None:
                    total += 1
                    if raw == prior:
                        equal += 1
                        informative += len(set(t.get_flattened_data() if hasattr(t, 'get_flattened_data') else t.getdata())) > 1
                prior = raw
        tile_pairs.append(dict(tile=tile, adjacent_pairs=total, identical_pairs=equal, nonuniform_identical_pairs=informative))
    return dict(width=w, height=h, rgba_sha256=sha(data), channels=channels,
                exact_black_rectangle_candidates=rects,
                dominant_rgba=[dict(rgba=list(c), pixels=n) for c, n in colors],
                repeated_row_groups=[dict(sha256=k, count=v) for k, v in Counter(rows).most_common(12) if v > 1],
                repeated_column_groups=[dict(sha256=k, count=v) for k, v in Counter(cols).most_common(12) if v > 1],
                adjacent_identical_rows=sum(a == b for a, b in zip(rows, rows[1:])),
                adjacent_identical_columns=sum(a == b for a, b in zip(cols, cols[1:])),
                horizontal_transition_mean_RGB=transitions,
                high_horizontal_transition_rows=sorted(range(1, h), key=lambda y: transitions[y - 1], reverse=True)[:40],
                vertical_transition_mean_RGB=vertical,
                high_vertical_transition_columns=sorted(range(1, w), key=lambda x: vertical[x - 1], reverse=True)[:40],
                black_rectangle_boundaries=boundaries,
                repeated_tiles=tile_pairs, old_frame_residue=UNKNOWN,
                interpretation='Anomaly candidates only: normal black UI, wallpaper, transparency and edges may match. No expected screenshot exists.')


def analyze_image(a):
    a.out.mkdir(parents=True, exist_ok=False)
    original = a.input.read_bytes(); src = Image.open(a.input)
    im = src.convert('RGBA')
    (a.out / 'original.png').write_bytes(original)
    result = dict(RESULT='CAPTURE_PATH_UNVERIFIED', original_file_sha256=sha(original), original_mode=src.mode,
                  icc_profile_sha256=sha(src.info['icc_profile']) if src.info.get('icc_profile') else UNKNOWN,
                  pixel_conversion='Pillow RGBA decoding only; no ICC transform. Comparisons require same capture/color path.',
                  full=image_stats(im), rois=[])
    regions = a.roi or [f'full:0,0,{im.width},{im.height}']
    for spec in regions:
        name, box = spec.split(':', 1); x, y, w, h = map(int, box.split(','))
        if not name.replace('-', '').replace('_', '').isalnum() or x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > im.width or y + h > im.height:
            raise ValueError('Invalid ROI')
        roi = im.crop((x, y, x + w, y + h)); roi.save(a.out / (name + '.png'))
        (a.out / (name + '.rgba')).write_bytes(roi.tobytes())
        stats = image_stats(roi); stats.update(name=name, bounds_pixels_top_left=[x, y, w, h])
        heat = Image.new('RGBA', roi.size, (0, 0, 0, 255)); draw = ImageDraw.Draw(heat)
        for rx, ry, rw, rh in stats['exact_black_rectangle_candidates']:
            draw.rectangle((rx, ry, rx + rw - 1, ry + rh - 1), fill=(255, 0, 0, 255))
        heat.save(a.out / (name + '-candidate-heatmap.png'))
        result['rois'].append(stats)
    if a.reference:
        ref = Image.open(a.reference).convert('RGBA')
        if ref.size != im.size: raise ValueError('Screenshot dimensions differ; register/crop first, do not silently rescale')
        diff = ImageChops.difference(im, ref)
        # Compare decoded values, do not certify screenshots against assumed GPU expected.
        result['comparison'] = compare(im.tobytes(), ref.tobytes(), im.width, im.height)
        result['comparison']['RESULT'] = 'CAPTURE_PATH_UNVERIFIED'
        result['comparison']['interpretation'] = 'Decoded screenshot differences only; normal motion/color/capture path may differ'
        diff.save(a.out / 'difference.png')
        result['reference_file_sha256'] = sha(a.reference.read_bytes())
    result['files'] = {p.name: dict(bytes=p.stat().st_size, sha256=sha(p.read_bytes())) for p in sorted(a.out.iterdir()) if p.is_file()}
    (a.out / 'analysis.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(RESULT=result['RESULT'], output=str(a.out), screenshot_size=list(im.size),
                          black_rectangle_candidates=result['full']['exact_black_rectangle_candidates'][:8])))


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='mode', required=True)
    image = sub.add_parser('image'); image.add_argument('--input', type=Path, required=True)
    image.add_argument('--reference', type=Path); image.add_argument('--roi', action='append')
    image.add_argument('--out', type=Path, required=True)
    raw = sub.add_parser('raw'); raw.add_argument('--actual', type=Path, required=True)
    raw.add_argument('--expected', type=Path, required=True); raw.add_argument('--width', type=int, required=True)
    raw.add_argument('--height', type=int, required=True); raw.add_argument('--actual-bpr', type=int, required=True)
    raw.add_argument('--expected-bpr', type=int, required=True); raw.add_argument('--previous', type=Path)
    raw.add_argument('--initial-byte', type=int); raw.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    try:
        if a.mode == 'image': analyze_image(a); return 0
        data, exp = a.actual.read_bytes(), a.expected.read_bytes()
        result = compare(packed(data, a.width, a.height, a.actual_bpr), packed(exp, a.width, a.height, a.expected_bpr),
                         a.width, a.height, previous=a.previous.read_bytes() if a.previous else None, initial=a.initial_byte)
        result.update(SOURCE_BPR=a.expected_bpr, DEST_BPR=a.actual_bpr,
                      actual_file_sha256=sha(data), expected_file_sha256=sha(exp))
        with a.output.open('x') as f: json.dump(result, f, indent=2); f.write('\n')
        print(json.dumps({k: result[k] for k in FIELDS})); return 0 if result['RESULT'] == 'PIXEL_PASS' else 1
    except (ValueError, OSError) as e:
        print(json.dumps(dict(RESULT='CAPTURE_INVALID', error=str(e))))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
