"""Re-extract four bounded programs from authenticated THAG Record1, never Record0."""
from __future__ import annotations

from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common import HISTORY, ROOT, Rejected, dump, frames, load, output_root, sha, write_bytes

CAPTURE_SHA = '1622ecc2aecdcc85ae45dcf86e4219338f6e41e0243b27d5e7128a9999f13333'
PINS = {
    'iga': 'c36a504a4e6c68030c3302646aa396b8b59b22cb',
    'mesa': '863338275d915e867319c3690ffd3272b06303c3',
    'translator': '1010490d3421628c9d6fd0bd518b6c4b6f8ee33c',
}
PROGRAMS = [('PS0', 'ps', 0x40, 152, 11), ('PS-KP1', 'ps-kp1', 0x200, 440, 29),
            ('PS-KP2', 'ps-kp2', 0x100, 216, 15), ('VS', 'vs', 0x3C0, 288, 24)]


def authenticated(path: Path, expected: str) -> bytes:
    if path.stat().st_size > 1 << 28:
        raise Rejected('INPUT_LENGTH', str(path))
    data = path.read_bytes()
    if sha(data) != expected:
        raise Rejected('HASH_MISMATCH', str(path))
    return data


def historical_file(relative: str) -> tuple[Path, bytes]:
    manifest = load(HISTORY / 'manifest.json')
    entry = next(x for x in manifest['files'] if x['path'] == relative)
    path = HISTORY / relative
    data = authenticated(path, entry['sha256'])
    if len(data) != entry['bytes']:
        raise Rejected('INPUT_LENGTH', relative)
    return path, data


def extract(destination: Path) -> dict:
    destination = output_root(destination)
    capture = ROOT.parent / 'GA32/capture/tgl-hang-GA32b-crash-20261018.bin'
    raw = authenticated(capture, CAPTURE_SHA)
    if len(raw) != 99648:
        raise Rejected('CAPTURE_LENGTH', str(len(raw)))
    base = 0xC2A0  # sizeof(HangRecord v2), record1 only
    if raw[base:base + 4] != b'THAG' or struct.unpack_from('<I', raw, base + 0x90)[0] != 0:
        raise Rejected('RECORD1_INVALID', 'Expected successful THAG v2 Record1')
    window0 = raw[base + 0x90 + 0x8210:base + 0x90 + 0x8210 + 8192]
    window1 = raw[base + 0x90 + 0xA210:base + 0x90 + 0xA210 + 8192]
    if len(window0) != 8192 or window0 != window1:
        raise Rejected('SHARED_WINDOW_MISMATCH', 'Recorded VS/PS byte windows must be equal')
    facts = {'schema_version': 1, 'capture': {'path': str(capture), 'sha256': sha(raw),
              'bytes': len(raw), 'record_index': 1, 'record_base': base,
              'window_file_offset': base + 0x90 + 0x8210,
              'layout_evidence': str(HISTORY / 'tools/extract_capture.py')},
             'pins': PINS, 'programs': []}
    for ident, name, entry, length, count in PROGRAMS:
        source = window0[entry:entry + length]
        path, bounded = historical_file(f'analysis/{name}-bounded.bin')
        if source != bounded or len(frames(source)) != count:
            raise Rejected('SOURCE_BOUNDARY_MISMATCH', ident)
        target_path, target = historical_file(f'analysis/upstream-{name}-gen12.bin')
        record = {'shader_id': ident, 'historical_name': name, 'eu_window_offset': entry,
                  'source_instruction_count': count, 'source': {}, 'candidate': {}}
        for side, data, origin in [('source', source, path), ('candidate', target, target_path)]:
            relative = f'corpus/{side}/{ident}.bin'
            output = destination / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            write_bytes(output, data)
            record[side] = {'path': relative, 'original_path': str(origin), 'sha256': sha(data),
                            'bytes': len(data), 'platform': '11' if side == 'source' else '12p1',
                            'byte_range': [0, len(data)], 'frames': frames(data),
                            'extraction': 'authenticated Record1 shared window slice' if side == 'source'
                            else 'byte-exact copy of pre-existing upstream candidate; never executed'}
        facts['programs'].append(record)
    dump(destination / 'corpus/provenance.json', facts)
    return facts


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, default=ROOT)
    args = ap.parse_args()
    extract(args.output)
