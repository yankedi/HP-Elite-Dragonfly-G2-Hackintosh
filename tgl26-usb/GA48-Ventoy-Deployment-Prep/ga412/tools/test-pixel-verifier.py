#!/usr/bin/env python3
"""CPU fixtures, including command failure and malformed captures; no GPU."""
import copy
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('verifier', HERE / 'verify-pixel-dump.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def baseline():
    geometry = {'width': 257, 'height': 65, 'samples': 1, 'mips': 1, 'array_length': 1}
    return {'schema': 'ga412-managed-rt-v1', 'origin': 'SYNTHETIC_CPU_FIXTURE_NOT_GPU_RUNTIME',
            'status': 'CAPTURE_COMPLETE_UNVERIFIED', 'case': 'R8', 'mode': 'legacy',
            'width': 257, 'height': 65, 'input_pitch': 512, 'input_bpp': 1, 'output_pitch': 1280,
            'source': dict(geometry, format=10, storage=0, usage=1),
            'target': dict(geometry, format=70, storage=1, usage=4),
            'full_snapshot_bytes': 83200, 'active_pixel_bytes': 66820, 'snapshots_disjoint': True,
            'gpu_frozen_ns': 60, 'cpu_getBytes_begin_ns': 70, 'cpu_getBytes_end_ns': 80,
            'commands': [{'id': 'synthetic-cb-1', 'stage': 'legacy_render_sync_copy', 'status': 4,
                          'error': '', 'error_domain': '', 'error_code': 0, 'created_ns': 10,
                          'commit_ns': 20, 'wait_begin_ns': 30, 'completed_callback_ns': 40,
                          'completion_observed_ns': 50, 'wait_returned': True, 'timeout': False}],
            'tracer': {'installed': 1, 'methods': [{'method': m, 'calls': 1} for m in verifier.METHODS]}}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'ga412/out' / ('pixel-fixtures-' + uuid.uuid4().hex[:12]))
    parser.add_argument('--report', type=Path, default=ROOT / 'ga412/reports/SYNTHETIC-VALIDATION.json')
    args = parser.parse_args()
    out = args.output
    if out.exists():
        raise FileExistsError('Preserve previous tests; choose a fresh checkout/output directory')
    out.mkdir(parents=True)
    source, expected = verifier.load_generator()()
    # Known independent coordinate checks, including the non-aligned final pixel.
    require(expected[:8] == bytes((0, 0, 0, 255, 13, 0, 0, 255)), 'first pixels')
    require(expected[1280:1284] == bytes((29, 0, 0, 255)), 'second row')
    require(expected[82944:82948] == bytes((64, 0, 0, 255)), 'last pixel')
    cases = []

    def run(name, mutate=None, code=0, check=None):
        directory = out / name; directory.mkdir()
        data = {'input': bytearray(source), 'expected': bytearray(expected),
                'gpu': bytearray(expected), 'cpu': bytearray(expected)}
        metadata = copy.deepcopy(baseline())
        if mutate:
            mutate(data, metadata)
        for key, value in data.items():
            if value is not None:
                (directory / f'{key}.bin').write_bytes(value)
        (directory / 'result.json').write_text(json.dumps(metadata))
        if name == 'aliased-file':
            (directory / 'gpu.bin').unlink()
            (directory / 'gpu.bin').symlink_to('expected.bin')
        results = []
        for optimized in (False, True):
            command = [sys.executable] + (['-O'] if optimized else []) + [str(HERE / 'verify-pixel-dump.py'), str(directory)]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            suffix = 'optimized' if optimized else 'normal'
            (directory / f'{suffix}.stdout.json').write_text(completed.stdout)
            (directory / f'{suffix}.stderr').write_text(completed.stderr)
            require(completed.returncode == code, f'{name}/{suffix}: rc={completed.returncode}, {completed.stdout[:300]}')
            report = json.loads(completed.stdout)
            require(report['status'] == {0: 'PIXEL_PASS', 1: 'PIXEL_FAIL', 2: 'INVALID'}[code], name)
            if check:
                check(report)
            results.append(report)
        require(results[0] == results[1], name + ': Python -O changed acceptance')
        cases.append({'fixture': name, 'exit_code': code, 'status': results[0]['status'],
                      'normal_and_optimized_identical': True,
                      'report_sha256': hashlib.sha256((directory / 'normal.stdout.json').read_bytes()).hexdigest()})

    run('clean')
    def padding(d, r):
        for y in range(65):
            d['gpu'][y * 1280 + 1028:(y + 1) * 1280] = b'\xee' * 252
            d['cpu'][y * 1280 + 1028:(y + 1) * 1280] = b'\xdd' * 252
    def padding_check(r):
        require(len(set(r['active_sha256'].values())) == 1, 'padding changed active hash')
        require(len({r['sha256'][n] for n in ('gpu.bin', 'cpu.bin', 'expected.bin')}) == 3, 'full hashes lost padding')
    run('padding-only', padding, check=padding_check)
    def one_check(r):
        c = r['comparisons']['cpu_vs_expected']; require(c['differing_bytes'] == c['bad_pixels'] == 1, 'one-byte count')
    run('cpu-one-byte', lambda d, r: d['cpu'].__setitem__(0, 1), 1, one_check)
    def last_check(r):
        f = r['comparisons']['gpu_vs_expected']['first_differences'][0]
        require((f['offset'], f['x'], f['y'], f['channel'], f['a'], f['b']) == (82946, 256, 64, 2, 1, 0), 'last-pixel address')
    run('gpu-last-pixel', lambda d, r: d['gpu'].__setitem__(82946, 1), 1, last_check)
    def same_wrong(d, r):
        d['gpu'][:] = bytes(83200); d['cpu'][:] = bytes(83200)
    def same_check(r):
        require(r['comparisons']['cpu_vs_gpu']['differing_bytes'] == 0, 'same wrong fixture differs')
        require(r['comparisons']['gpu_vs_expected']['bad_pixels'] == 16705, 'both-wrong not rejected')
        require(r['layout_statistics']['gpu']['all_zero'], 'all-zero detection')
    run('both-same-wrong', same_wrong, 1, same_check)
    run('all-FF', lambda d, r: d['cpu'].__setitem__(slice(None), b'\xff' * 83200), 1,
        lambda r: require(r['layout_statistics']['cpu']['all_FF'], 'all-FF detection'))
    run('missing-gpu', lambda d, r: d.__setitem__('gpu', None), 2)
    run('truncated-cpu', lambda d, r: d.__setitem__('cpu', d['cpu'][:-1]), 2)
    run('wrong-stride', lambda d, r: r.__setitem__('output_pitch', 1028), 2)
    run('wrong-geometry', lambda d, r: r['target'].__setitem__('width', 256), 2)
    run('tampered-expected', lambda d, r: d['expected'].__setitem__(0, 5), 2)
    run('tampered-input', lambda d, r: d['input'].__setitem__(0, 5), 2)
    run('command-failed', lambda d, r: r['commands'][0].update(status=5, error='GPU fault', error_domain='MTLCommandBufferErrorDomain', error_code=1), 2)
    run('wait-not-returned', lambda d, r: r['commands'][0].update(wait_returned=False), 2)
    run('command-timeout', lambda d, r: r['commands'][0].update(timeout=True), 2)
    run('missing-command', lambda d, r: r.update(commands=[]), 2)
    run('missing-completion', lambda d, r: r['commands'][0].update(completed_callback_ns=0), 2)
    run('wrong-freeze-order', lambda d, r: r.update(gpu_frozen_ns=90), 2)
    run('tracer-not-installed', lambda d, r: r['tracer'].update(installed=0), 2)
    run('aliased-file', code=2)
    for period in (64, 128, 256, 512):
        def periodic(d, r, period=period):
            for offset in range(0, 83200, period):
                if offset % 1280 < 1028:
                    d['cpu'][offset] ^= 1
        def periodic_check(r, period=period):
            stats = r['comparisons']['cpu_vs_expected']['physical_offset_period_statistics'][str(period)]
            require(stats['nonzero_residues'] == 1 and stats['top_residues'][0][0] == 0, 'periodic residue statistic')
        run(f'period-{period}', periodic, 1, periodic_check)
    run('previous-row-repeat', lambda d, r: d['cpu'].__setitem__(slice(1280, 2308), d['cpu'][:1028]), 1,
        lambda r: require(r['layout_statistics']['cpu']['repeats_previous_active_row'] == 1, 'row-repeat detection'))
    run('previous-block-repeat', lambda d, r: d['cpu'].__setitem__(slice(64, 128), d['cpu'][:64]), 1,
        lambda r: require(r['layout_statistics']['cpu']['adjacent_block_statistics']['64']['adjacent_equal_blocks'] > 0, 'block-repeat detection'))
    def channel(d, r):
        for y in range(65):
            for x in range(257): d['cpu'][y * 1280 + x * 4 + 1] = 1
    run('fixed-green-channel', channel, 1,
        lambda r: require(r['comparisons']['cpu_vs_expected']['channel_error_bytes_RGBA'] == [0, 16705, 0, 0], 'fixed-channel detection'))
    summary = {'status': 'CPU_TEST_PASS', 'GPU_commands_submitted': False, 'fixture_count': len(cases),
               'CLI_invocations': len(cases) * 2, 'cases': cases,
               'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in [Path(__file__), HERE / 'verify-pixel-dump.py', HERE / 'expected-pattern.py']}}
    destination = args.report
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: summary[k] for k in ('status', 'fixture_count', 'CLI_invocations', 'GPU_commands_submitted')}))


if __name__ == '__main__':
    main()
