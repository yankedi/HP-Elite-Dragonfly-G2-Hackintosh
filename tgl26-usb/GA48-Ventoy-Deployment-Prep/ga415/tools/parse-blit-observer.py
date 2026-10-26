#!/usr/bin/env python3
"""Offline decoder for actual GA415OBS lines; no GPU submission or route guessing."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import struct

RECORD = re.compile(r'GA415OBS kind=(SUBMIT|COPY2D|FAST2D|COPY3D) cls=([PUG]) n=(\d+) tag=([0-9a-f]{8}) sp=(\d+) dp=(\d+) st=(\d+) dt=(\d+) sb=([0-9a-f]{8}) so=([0-9a-f]{8}) db=([0-9a-f]{8}) do=([0-9a-f]{8}) bpe=(\d+) rs=(\d+) f3=([01])/([01]) aux=([01])/([01]) rects=(\d+) r=([0-9a-f,]+)(?:\s|$)')


def decode(text):
    rows = []
    for line in text.splitlines():
        if 'GA415OBS kind=' not in line: continue
        m = RECORD.search(line)
        if not m: raise ValueError('Truncated or unrecognized GA415OBS record')
        kind, category, number, tag, sp, dp, st, dt, sb, so, db, do, bpe, rs, sf, df, sa, da, count, rect = m.groups()
        words = rect.split(',')
        if len(words) != 8 or any(len(w) != 8 for w in words): raise ValueError('Invalid rectangle bits')
        values = [struct.unpack('<f', bytes.fromhex(w)[::-1])[0] for w in words]
        rect_data = values if all(math.isfinite(v) for v in values) else 'NONFINITE_RECT_BITS'
        sp, dp, bpe, count = int(sp), int(dp), int(bpe), int(count)
        first_area_bytes = 'NOT_OBSERVED'
        if count == 1 and isinstance(rect_data, list) and bpe > 0 and rect_data[2] >= 0 and rect_data[3] >= 0:
            first_area_bytes = rect_data[2] * rect_data[3] * bpe
        rows.append({'kind': kind, 'category': category, 'sequence': int(number), 'lossy_params_tag': tag,
                     'source_pitch': sp, 'destination_pitch': dp, 'source_pitch_mod64': sp % 64, 'destination_pitch_mod64': dp % 64,
                     'source_tiling_raw': int(st), 'destination_tiling_raw': int(dt),
                     'source_base_plus_offset_mod64': (int(sb, 16) + int(so, 16)) % 64,
                     'destination_base_plus_offset_mod64': (int(db, 16) + int(do, 16)) % 64,
                     'bytes_per_element_raw': bpe, 'entry_route_selector': int(rs), 'force3d_bits': [int(sf), int(df)],
                     'aux_nonzero': [int(sa), int(da)], 'rect_count': count, 'first_rect_float_bits': words,
                     'first_rect_floats': rect_data, 'single_rect_source_area_bytes': first_area_bytes,
                     'upstream_pitch_predicate_only': bool((sp | dp) & 63),
                     'final_helper_observed': kind if kind != 'SUBMIT' else 'NOT_OBSERVED',
                     'XE_BLITFIX_applied_or_triggered': 'NOT_OBSERVED'})
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('log', type=Path); p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    raw = a.log.read_bytes(); rows = decode(raw.decode('utf-8', errors='strict'))
    result = {'status': 'OBSERVER_RECORDS_DECODED' if rows else 'NOT_OBSERVED',
              'input_origin': 'USER_SUPPLIED_LOG_PROVENANCE_REQUIRES_RECEIPT',
              'input_sha256': hashlib.sha256(raw).hexdigest(), 'record_count': len(rows),
              'by_kind': dict(Counter(row['kind'] for row in rows)), 'records': rows,
              'limits': ['Entry selector is not the final helper.', 'Pointer tag is lossy and can be reused; it is not an IOSurface ID.',
                         'Logging is bounded and sampled; missing records do not prove missing commands.',
                         'Geometry/tag/time are candidate correlations, not proof of a probe or WindowServer resource match.',
                         'Read-only observer does not contain XE-BLITFIX; pitch predicate alone cannot establish the fault cause.']}
    with a.output.open('x') as stream: json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'status': result['status'], 'record_count': len(rows), 'by_kind': result['by_kind']}))


if __name__ == '__main__':
    main()
