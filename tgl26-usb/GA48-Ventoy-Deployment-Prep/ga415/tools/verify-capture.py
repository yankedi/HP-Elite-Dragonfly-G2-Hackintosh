#!/usr/bin/env python3
"""Fail-closed offline verification of actual GA415 stage dumps; no GPU."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), HERE / (name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


diff = load('pixel-diff')
patterns = load('expected-pattern')


def verify(path):
    result = json.loads((path / 'result.json').read_text())
    if result.get('schema') != 'ga415-iosurface-v1':
        raise ValueError('Unexpected schema')
    state = result.get('RESULT')
    if state in ('GPU_COMMAND_FAIL', 'RESOURCE_READBACK_FAIL', 'CAPTURE_INVALID', 'CAPTURE_PATH_UNVERIFIED'):
        return dict(RESULT=state, reason=result.get('reason', diff.UNKNOWN), root_cause='ROOT_CAUSE_UNVERIFIED')
    cpu_only = result.get('cpu_only')
    if type(cpu_only) is not bool or state != ('CPU_CAPTURE_COMPLETE_UNVERIFIED' if cpu_only else 'CAPTURE_COMPLETE_UNVERIFIED'):
        raise ValueError('Capture state/mode invalid')
    resource = json.loads((path / 'resource.json').read_text())
    command = json.loads((path / 'command.json').read_text())
    case, pattern = result['case'], result['pattern']
    w, h = patterns.CASES[case]
    if resource['case'] != case or resource['pattern'] != pattern or resource['width'] != w or resource['height'] != h:
        raise ValueError('Resource/result geometry mismatch')
    if resource['pixel_format'] != 'RGBA8Unorm' or resource['logical_bpr'] != w * 4 or resource['input_bpr'] != w * 4:
        raise ValueError('Unexpected pixel format or input layout')
    pitch, row = resource['iosurface_actual_bpr'], resource['output_bpr']
    if type(pitch) is not int or type(row) is not int or pitch < w * 4 or row < w * 4 or row % 256:
        raise ValueError('Invalid actual surface/readback pitches')
    required = {'input.bin': w * 4, 'expected.bin': w * 4, 'iosurface-before.bin': pitch, 'iosurface-after.bin': pitch}
    if not cpu_only:
        required.update({'upload-proxy.bin': row, 'gpu.bin': row, 'cpu.bin': row})
    records = result['files']
    for name in (*required, 'resource.json', 'command.json', 'intent.json'):
        if name not in records: raise ValueError('Missing artifact record: ' + name)
    all_files = {}
    for name, record in records.items():
        if Path(name).name != name: raise ValueError('Unsafe artifact name')
        data = (path / name).read_bytes()
        if len(data) != record['bytes'] or diff.sha(data) != record['sha256']:
            raise ValueError('File hash/length mismatch: ' + name)
        all_files[name] = record
    active = {}
    for name, bpr in required.items():
        data = (path / name).read_bytes()
        active[name] = diff.packed(data, w, h, bpr)
        if records[name]['bpr'] != bpr or diff.sha(active[name]) != records[name]['active_sha256']:
            raise ValueError('Active hash/pitch mismatch: ' + name)
    expected = patterns.generate(w, h, pattern)
    if active['expected.bin'] != expected:
        raise ValueError('Recorded expected.bin does not match independently regenerated expected')
    comparisons = {}
    for name in required:
        if name == 'expected.bin': continue
        initial = {'upload-proxy.bin': 238, 'gpu.bin': 221, 'cpu.bin': 204}.get(name)
        comparisons[name + '_vs_expected'] = diff.compare(active[name], expected, w, h, initial=initial)
    if comparisons['input.bin_vs_expected']['RESULT'] != 'PIXEL_PASS':
        raise ValueError('CPU source input invalid; cannot certify GPU reproduction')
    if cpu_only:
        if command.get('submitted') is not False or command.get('status') != diff.UNKNOWN:
            raise ValueError('CPU-only capture claims GPU command')
        gpu_result, command_status = 'CAPTURE_PATH_UNVERIFIED', diff.UNKNOWN
    else:
        if command.get('submitted') is not True or command.get('explicit_command_buffers') != 1 or command.get('wait_returned') is not True:
            raise ValueError('Missing explicit single command completion')
        if command.get('status') != 4 or command.get('error') != '' or command.get('error_code') != 0 or command.get('timeout') is not False:
            return dict(RESULT='GPU_COMMAND_FAIL', command=command, root_cause='ROOT_CAUSE_UNVERIFIED')
        t = [command['created_ns'], command['commit_ns'], command['completion_observed_ns'], result['gpu_frozen_ns'],
             result['cpu_getBytes_begin_ns'], result['cpu_getBytes_end_ns']]
        if not all(type(v) is int and v > 0 for v in t) or t != sorted(t) or result.get('snapshots_independent') is not True:
            raise ValueError('Snapshot independence/timeline invalid')
        for name, storage, usage in [('source_texture', 0, 1), ('target_texture', 1, 5)]:
            tex = resource[name]
            if any(tex[k] != v for k, v in dict(width=w, height=h, pixel_format=70, storage_mode=storage,
                                               usage=usage, samples=1, mips=1).items()):
                raise ValueError('Unexpected actual Metal texture descriptor: ' + name)
        if resource['readback_buffer_storage'] != 0:
            raise ValueError('Readback buffer is not shared')
        comparisons['cpu_vs_gpu'] = diff.compare(active['cpu.bin'], active['gpu.bin'], w, h)
        gpu_result = 'PIXEL_FAIL' if any(c['RESULT'] != 'PIXEL_PASS' for c in comparisons.values()) else 'PIXEL_PASS'
        command_status = command['status']
    cpu_result = 'PIXEL_PASS' if all(comparisons[n + '_vs_expected']['RESULT'] == 'PIXEL_PASS'
                                    for n in ('input.bin', 'iosurface-before.bin', 'iosurface-after.bin')) else 'PIXEL_FAIL'
    earliest = diff.UNKNOWN
    boundaries = [('iosurface-before.bin', 'CPU upload -> IOSurface CPU bytes'),
                  ('upload-proxy.bin', 'IOSurface CPU bytes -> source texture direct-copy proxy (includes device-cache/pageon and proxy copy)'),
                  ('gpu.bin', 'Source read proxy -> integer texture.read + render + target copy proxy; this interval contains multiple operations'),
                  ('cpu.bin', 'GPU copy proxy -> synchronized managed CPU getBytes (different readback paths)')]
    for name, boundary in boundaries:
        if name in active and active[name] != expected:
            earliest = boundary; break
    if earliest == diff.UNKNOWN and active['iosurface-after.bin'] != expected:
        earliest = 'Source IOSurface changed after GPU work; exact time of mutation NOT_OBSERVED'
    if not cpu_only and active['upload-proxy.bin'] != expected and active['gpu.bin'] == expected and active['cpu.bin'] == expected:
        earliest = 'IOSurface texture -> shared buffer direct-copy operation fails; subsequent shader-render path from the same texture passes (API-path divergence)'
    output = {k: diff.UNKNOWN for k in diff.FIELDS}
    output.update(CASE_ID=case, GPU_DEVICE=resource.get('device', diff.UNKNOWN), DRIVER_UUID=resource.get('driver_uuid', diff.UNKNOWN),
                  PIXEL_FORMAT='RGBA8Unorm', WIDTH=w, HEIGHT=h, SOURCE_BPR=pitch, DEST_BPR=row,
                  GPU_ROUTE=resource.get('Metal_API_route', diff.UNKNOWN), COMMAND_STATUS=command_status,
                  RESULT=gpu_result, CPU_RESULT=cpu_result, cpu_only=cpu_only,
                  earliest_observable_difference=earliest, root_cause='ROOT_CAUSE_UNVERIFIED',
                  actual_surface_bpr_64_aligned=pitch % 64 == 0, requested_bpr=resource['requested_surface_bpr'],
                  XE_BLITFIX_trigger='NOT_OBSERVED', submitBlit_source_pitch='NOT_OBSERVED', submitBlit_destination_pitch='NOT_OBSERVED',
                  independent_expected_active_sha256=diff.sha(expected), files=all_files, comparisons=comparisons,
                  artifact_reproduction='NOT_OBSERVED' if cpu_only else ('ARTIFACT_REPRODUCED' if gpu_result == 'PIXEL_FAIL' else 'ARTIFACT_NOT_REPRODUCED'),
                  limits='CPU-only PASS never certifies a GPU path. Proxy copies are additional GPU operations. Surface BPR does not prove submitBlit route.')
    if not cpu_only:
        summary = next((name for name, c in comparisons.items() if c['RESULT'] == 'PIXEL_FAIL'), 'gpu.bin_vs_expected')
        failed = comparisons[summary]; output['SUMMARY_COMPARISON'] = summary
        for k in ('BAD_PIXELS', 'DIFFERENT_BYTES', 'FIRST_BAD_PIXEL', 'ERROR_PATTERN'): output[k] = failed[k]
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('capture', type=Path)
    p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    try:
        result = verify(a.capture)
    except (ValueError, OSError, KeyError, TypeError) as e:
        result = dict(RESULT='CAPTURE_INVALID', reason=str(e), root_cause='ROOT_CAUSE_UNVERIFIED')
    with a.output.open('x') as f: json.dump(result, f, indent=2); f.write('\n')
    print(json.dumps({k: result.get(k, diff.UNKNOWN) for k in (*diff.FIELDS, 'CPU_RESULT', 'earliest_observable_difference')}))
    return 0 if result['RESULT'] == 'PIXEL_PASS' or (result.get('cpu_only') and result.get('CPU_RESULT') == 'PIXEL_PASS') else 1


if __name__ == '__main__': raise SystemExit(main())
