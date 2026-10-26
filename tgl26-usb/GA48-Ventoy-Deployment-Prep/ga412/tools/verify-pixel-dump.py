#!/usr/bin/env python3
"""Independent, fail-closed R8 legacy dump audit. No assertions used as gates."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

W, H, ROW, INPUT_ROW = 257, 65, 1280, 512
PERIODS = (64, 128, 256, 512)
METHODS = (
    'getBytes:bytesPerRow:bytesPerImage:fromRegion:mipmapLevel:slice:',
    'lockForCPUAccess:readOnly:level:slice:',
    'resolveCCS:slice:waitForCompletion:', 'unlockForCPUAccess:readOnly:',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_generator():
    spec = importlib.util.spec_from_file_location('expected_pattern', Path(__file__).with_name('expected-pattern.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate


def packed(data):
    return b''.join(data[y * ROW:y * ROW + W * 4] for y in range(H))


def compare(left, right):
    errors, pixels, first = set(), set(), []
    channels, rows = [0] * 4, [0] * H
    for y in range(H):
        for x in range(W):
            for c in range(4):
                offset = y * ROW + x * 4 + c
                if left[offset] != right[offset]:
                    errors.add(offset); pixels.add((x, y)); channels[c] += 1; rows[y] += 1
                    if len(first) < 32:
                        first.append({'offset': offset, 'packed_offset': (y * W + x) * 4 + c,
                                      'x': x, 'y': y, 'channel': c, 'a': left[offset], 'b': right[offset]})
    periods = {}
    for period in PERIODS:
        residues = [0] * period
        for offset in errors:
            residues[offset % period] += 1
        periods[str(period)] = {
            'error_pairs_at_lag': sum(offset + period in errors for offset in errors),
            'nonzero_residues': sum(count > 0 for count in residues),
            'top_residues': sorted(enumerate(residues), key=lambda pair: (-pair[1], pair[0]))[:16],
        }
    return {'differing_bytes': len(errors), 'bad_pixels': len(pixels), 'total_pixels': W * H,
            'first_differences': first, 'channel_error_bytes_RGBA': channels, 'row_error_bytes': rows,
            'physical_offset_period_statistics': periods, 'padding_excluded': True,
            'interpretation': 'descriptive periodicity only; not an Intel tile-format identification'}


def layout(data):
    active = packed(data)
    repeats = {}
    for block in PERIODS:
        matches = total = 0
        for y in range(H):
            row = data[y * ROW:y * ROW + W * 4]
            for start in range(block, len(row) - block + 1, block):
                total += 1
                matches += row[start:start + block] == row[start - block:start]
        repeats[str(block)] = {'adjacent_equal_blocks': matches, 'compared_blocks': total}
    return {'all_zero': not any(active), 'all_FF': all(b == 255 for b in active),
            'repeats_previous_active_row': sum(
                data[y * ROW:y * ROW + W * 4] == data[(y - 1) * ROW:(y - 1) * ROW + W * 4]
                for y in range(1, H)),
            'adjacent_block_statistics': repeats,
            'old_frame_detection': 'NOT_OBSERVABLE_WITHOUT_A_REFERENCE_FRAME'}


def validate_metadata(r):
    require(r['schema'] == 'ga412-managed-rt-v1', 'unknown capture schema')
    require(r['status'] == 'CAPTURE_COMPLETE_UNVERIFIED', 'capture did not finish normally')
    for key, value in {'case': 'R8', 'mode': 'legacy', 'width': W, 'height': H,
                       'output_pitch': ROW, 'input_pitch': INPUT_ROW, 'input_bpp': 1,
                       'full_snapshot_bytes': ROW * H, 'active_pixel_bytes': W * H * 4}.items():
        require(r[key] == value, f'unexpected {key}')
    for name, fmt, storage, usage in [('source', 10, 0, 1), ('target', 70, 1, 4)]:
        for key, value in {'width': W, 'height': H, 'format': fmt, 'storage': storage,
                           'usage': usage, 'samples': 1, 'mips': 1, 'array_length': 1}.items():
            require(r[name][key] == value, f'unexpected {name}.{key}')
    require(r['snapshots_disjoint'] is True, 'capture did not establish independent snapshots')
    require(len(r['commands']) == 1, 'legacy requires exactly one command buffer')
    c = r['commands'][0]
    require(c['stage'] == 'legacy_render_sync_copy' and bool(c['id']), 'wrong command stage/identity')
    require(c['status'] == 4 and not c['error'] and not c['error_domain'] and c['error_code'] == 0,
            'command did not complete without error')
    require(c['wait_returned'] is True and c['timeout'] is False, 'command wait incomplete/timed out')
    times = [c[k] for k in ('created_ns', 'commit_ns', 'wait_begin_ns', 'completion_observed_ns')]
    require(all(type(t) is int and t > 0 for t in times) and times == sorted(times), 'invalid command times')
    callback = c['completed_callback_ns']
    require(type(callback) is int and times[1] <= callback <= times[-1], 'missing/inconsistent completion callback')
    captures = [r[k] for k in ('gpu_frozen_ns', 'cpu_getBytes_begin_ns', 'cpu_getBytes_end_ns')]
    require(all(type(t) is int and t > 0 for t in captures) and captures == sorted(captures)
            and captures[0] >= times[-1], 'GPU snapshot must precede CPU getBytes after completion')
    tracer = r['tracer']
    require(tracer['installed'] == 1 and [m['method'] for m in tracer['methods']] == list(METHODS),
            'four-method observer not installed')
    require(all(type(m['calls']) is int and m['calls'] >= 0 for m in tracer['methods']), 'invalid observer counts')
    require(tracer['methods'][0]['calls'] > 0, 'getBytes was not observed')


def audit(directory):
    metadata_bytes = (directory / 'result.json').read_bytes()
    result = json.loads(metadata_bytes)
    validate_metadata(result)
    raw, inodes = {}, set()
    for name in ('input', 'expected', 'gpu', 'cpu'):
        path = directory / f'{name}.bin'
        require(not path.is_symlink(), f'{name}.bin is a symlink')
        stat = path.stat(); identity = (stat.st_dev, stat.st_ino)
        require(identity not in inodes, 'dump files alias the same inode')
        inodes.add(identity); raw[name] = path.read_bytes()
        require(len(raw[name]) == (INPUT_ROW if name == 'input' else ROW) * H, f'{name}.bin wrong size')
    source, expected = load_generator()()
    require(raw['input'] == source, 'input.bin disagrees with independent source pattern')
    require(raw['expected'] == expected, 'expected.bin disagrees with independent expected pattern')
    comparisons = {'gpu_vs_expected': compare(raw['gpu'], expected),
                   'cpu_vs_expected': compare(raw['cpu'], expected),
                   'cpu_vs_gpu': compare(raw['cpu'], raw['gpu'])}
    passed = all(v['differing_bytes'] == 0 for v in comparisons.values())
    return {'status': 'PIXEL_PASS' if passed else 'PIXEL_FAIL', 'commands_ok': True,
            'comparisons': comparisons, 'layout_statistics': {n: layout(raw[n]) for n in ('gpu', 'cpu')},
            'sha256': {n + '.bin': hashlib.sha256(d).hexdigest() for n, d in raw.items()},
            'active_sha256': {n + '.bin': hashlib.sha256(packed(raw[n])).hexdigest() for n in ('expected', 'gpu', 'cpu')},
            'result_json_sha256': hashlib.sha256(metadata_bytes).hexdigest(),
            'origin': result.get('origin', 'requires accompanying real runtime receipts'),
            'limits': 'Copy proxy only; external identity/health/trace receipts required. No kernel compression verdict, desktop fix or stability claim.'}, (0 if passed else 1)


def main():
    if len(sys.argv) != 2:
        print('usage: verify-pixel-dump.py DIRECTORY', file=sys.stderr); return 2
    try:
        result, code = audit(Path(sys.argv[1]))
    except (ValueError, KeyError, TypeError, OSError, IndexError) as error:
        result, code = {'status': 'INVALID', 'error': str(error)}, 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
