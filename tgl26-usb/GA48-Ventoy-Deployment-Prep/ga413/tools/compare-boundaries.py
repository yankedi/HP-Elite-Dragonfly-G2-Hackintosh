#!/usr/bin/env python3
"""Independent legacy/staged capture audits and full error-location comparison."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = load('legacy_audit', ROOT / 'ga412/tools/verify-pixel-dump.py')
staged = load('staged_audit', ROOT / 'ga413/tools/verify-pixel-dump.py')


def pattern(directory):
    data = {name: (directory / f'{name}.bin').read_bytes() for name in ('gpu', 'cpu', 'expected')}
    active = {name: legacy.packed(value) for name, value in data.items()}
    e, c = active['expected'], active['cpu']
    offsets = {i for i, (a, b) in enumerate(zip(c, e)) if a != b}
    physical = {i // (257 * 4) * 1280 + i % (257 * 4) for i in offsets}
    pixels = {i // 4 for i in offsets}
    periods = {}
    for period in (64, 128, 256, 512):
        counts = [0] * period
        for offset in physical:
            counts[offset % period] += 1
        periods[str(period)] = counts
    rows = [sum(row * 1028 <= i < (row + 1) * 1028 for i in offsets) for row in range(65)]
    channels = [sum(i % 4 == c for i in offsets) for c in range(4)]
    # Set is serialized deterministically; complete position evidence, not just first 32 differences.
    mask = bytes(int(i in offsets) for i in range(66820))
    return active, offsets, pixels, {'row_error_bytes': rows, 'channel_error_bytes_RGBA': channels,
                                   'physical_offset_residue_histograms': periods,
                                   'full_packed_byte_error_mask_sha256': hashlib.sha256(mask).hexdigest()}


def compare(old_directory, new_directory):
    old, _ = legacy.audit(old_directory)
    new, _ = staged.audit(new_directory)
    oa, oe, op, old_pattern = pattern(old_directory)
    na, ne, np, new_pattern = pattern(new_directory)
    legacy.require(oa['expected'] == na['expected'], 'expected image changed')
    pixel_pass = new['comparisons']['cpu_vs_expected']['bad_pixels'] == 0
    gpu_pass = new['comparisons']['gpu_vs_expected']['bad_pixels'] == 0
    if pixel_pass and gpu_pass:
        interpretation = 'Three-CB grouping/waits improved this case relative to the historical legacy failure; not proof of NOCCS3 cause or desktop repair.'
    elif gpu_pass and new['comparisons']['cpu_vs_expected']['bad_pixels'] == 16705:
        interpretation = 'Three completed boundaries are insufficient: GPU proxy correct, CPU still wrong everywhere. Next: correlate locked backing, offsets and compression/resolve state for the same resource.'
    else:
        interpretation = 'No clean all-pixel restoration established; inspect full GPU/CPU deltas and external health before choosing another experiment.'
    same_errors = oe & ne
    return {'status': 'VALID_HISTORICAL_BOUNDARY_COMPARISON', 'legacy': old, 'staged_boundary': new,
            'pattern_comparison': {'legacy': old_pattern, 'staged': new_pattern,
                'bad_byte_positions_common': len(same_errors), 'legacy_only': len(oe - ne), 'staged_only': len(ne - oe),
                'bad_pixel_positions_common': len(op & np), 'legacy_only_pixels': len(op - np), 'staged_only_pixels': len(np - op),
                'identical_error_location_mask': oe == ne,
                'identical_wrong_values_at_common_error_positions': sum(oa['cpu'][i] == na['cpu'][i] for i in same_errors),
                'CPU_active_bytes_changed_between_runs': sum(a != b for a, b in zip(oa['cpu'], na['cpu']))},
            'interpretation': interpretation,
            'limits': ['Legacy is the saved GA4.12 run, not rerun concurrently in this boot.',
                       'Hash equality and unchanged workload do not prove identical private GPU state across boots.',
                       'External stack hashes/identity/health and trace receipts remain required.']}


def main():
    if len(sys.argv) != 3:
        print('usage: compare-boundaries.py LEGACY_DIRECTORY STAGED_DIRECTORY', file=sys.stderr); return 2
    try:
        result, code = compare(Path(sys.argv[1]), Path(sys.argv[2])), 0
    except (ValueError, KeyError, TypeError, OSError, IndexError) as error:
        result, code = {'status': 'INVALID', 'error': str(error)}, 2
    print(json.dumps(result, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
