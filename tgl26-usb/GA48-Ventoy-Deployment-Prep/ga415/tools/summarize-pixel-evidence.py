#!/usr/bin/env python3
"""Assemble reports strictly from saved real capture/desktop/audit evidence."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
GA = ROOT / 'ga415'


def load(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases = []
    independent = load(GA / 'private/continuation-real-audit/INDEPENDENT-AUDIT.json')
    assert independent['status'] == 'INDEPENDENT_REAL_CAPTURE_AUDIT_PASS'
    for case in 'ABC':
        r = load(GA / 'reports' / ('CASE-' + case + '-PIXELS-export.json'))
        capture = GA / 'captures' / ('case-' + case) / ('gpu-' + case)
        resource, command, result = [load(capture / name) for name in ['resource.json', 'command.json', 'result.json']]
        other = next(c for c in independent['cases'] if c['case'] == case)
        stages = {}
        for name, comparison in r['comparisons'].items():
            stages[name] = {key: comparison[key] for key in ['RESULT', 'BAD_PIXELS', 'DIFFERENT_BYTES', 'FIRST_BAD_PIXEL', 'ERROR_PATTERN']}
            dump = name.removesuffix('_vs_expected')
            if dump in other['stages']:
                assert comparison['BAD_PIXELS'] == other['stages'][dump]['bad_pixels']
                assert comparison['DIFFERENT_BYTES'] == other['stages'][dump]['different_bytes']
        cases.append({'CASE_ID': case, 'RESULT': r['RESULT'], 'GPU_DEVICE': r['GPU_DEVICE'], 'DRIVER_UUID': r['DRIVER_UUID'],
                      'PIXEL_FORMAT': r['PIXEL_FORMAT'], 'WIDTH': r['WIDTH'], 'HEIGHT': r['HEIGHT'],
                      'logical_pixel_row_bytes': resource['logical_bpr'], 'actual_IOSurface_BPR': resource['iosurface_actual_bpr'],
                      'shared_readback_buffer_BPR': resource['output_bpr'], 'Metal_internal_pitch': 'NOT_OBSERVED',
                      'submitBlit_source_pitch': 'NOT_OBSERVED', 'submitBlit_destination_pitch': 'NOT_OBSERVED',
                      'final_2D_3D_route': 'NOT_OBSERVED', 'XE_BLITFIX_trigger': 'NOT_OBSERVED',
                      'first_observable_failure_boundary': r['earliest_observable_difference'],
                      'independent_expected_active_sha256': r['independent_expected_active_sha256'],
                      'source_textures': {'source': resource['source_texture'], 'target': resource['target_texture']},
                      'command': command, 'timeline': {k: result[k] for k in ['gpu_frozen_ns', 'cpu_getBytes_begin_ns', 'cpu_getBytes_end_ns']},
                      'comparisons': stages, 'capture': str(capture.relative_to(ROOT)),
                      'capture_files': {name: {'bytes': value['bytes'], 'sha256': value['sha256']} for name, value in r['files'].items()}})
    report = {'schema': 'ga415-actual-iosurface-results-v1', 'status': 'SILENT_GPU_PIXEL_ERROR_CAPTURED',
              'root_cause': 'ROOT_CAUSE_UNVERIFIED', 'test_boot_profile': 'GA414 NOAUX; PLANES2 disabled during original A/B/C',
              'pattern': 'R=(13*x+29*y)%256 G=(7*x+11*y)%256 B=(3*x+17*y)%256 A=255',
              'valid_pixels_only': True, 'padding_excluded': True, 'independent_verifiers_agree_on_actual_data': True,
              'cases': cases, 'new_GPU_submissions_this_continuation': 0,
              'API_operation_sequence': ['CPU source/independent Expected', 'IOSurface CPU upload and locked snapshot',
                                         'IOSurface texture -> shared-buffer copy proxy', 'unfiltered integer texture.read -> no-blend RGBA8 target',
                                         'target -> independent shared GPU dump; synchronize managed target',
                                         'freeze GPU dump before independent CPU getBytes snapshot'],
              'limits': ['upload-proxy.bin includes the extra texture-to-buffer copy; it is not raw tiled backing storage.',
                         'A/B/C dimensions are API dimensions, not kernel submitBlit rectangle/pitch observations.',
                         'CPU_RESULT in individual verifier reports refers to CPU source/IOSurface correctness; consult cpu.bin_vs_expected for target getBytes.',
                         'B direct-copy failure is below 128 KiB; its mechanism need not be the same as C or the upstream large-copy fault.',
                         'A single execution establishes an actual failing capture, not repeatability frequency or stability.']}
    with (GA / 'reports/IOSURFACE-RESULT.json').open('x') as stream: json.dump(report, stream, indent=2); stream.write('\n')
    desktop = load(GA / 'private/desktop-layer-analysis-v5/analysis.json')
    dock = load(GA / 'private/desktop-dock-current-v1/analysis.json')
    assert desktop['movement_pixels'] == [-240, 0]
    assert desktop['registered_before_after']['battery-label-window']['uniform_RGBA_channel_delta'] == [0, 0, 1, 0]
    desktop.update(schema='ga415-capture-comparison-v1', screenshot_origin='ACTUAL_PLANES2_NOAUX_DESKTOP',
                   independent_expected_screenshot='NOT_OBSERVED', desktop_pixel_correctness='CAPTURE_PATH_UNVERIFIED',
                   same_window_ROI_preserved_up_to_uniform_channel_delta={'ROI': 'battery-label', 'RGBA_delta': [0, 0, 1, 0], 'pixel_count': 4900,
                                                                         'meaning': 'This ROI structure followed window coordinates across -240 px movement. It does not identify why text is missing.'},
                   dock_and_full_screenshot_analysis=dock,
                   source_analysis_sha256=sha(GA / 'private/desktop-layer-analysis-v5/analysis.json'),
                   health=load(GA / 'reports/CONTINUATION-FINAL-HEALTH.json'))
    with (GA / 'reports/CAPTURE-COMPARISON.json').open('x') as stream: json.dump(desktop, stream, indent=2); stream.write('\n')
    images = GA / 'reports/desktop-roi'; images.mkdir()
    for side in ['before', 'after']:
        for roi in ['battery-label', 'display-control']:
            for kind in ['full', 'window']:
                name = f'{side}-{roi}-{kind}.png'
                shutil.copyfile(GA / 'private/desktop-layer-analysis-v5' / name, images / name)
    (GA / 'reports/INDEPENDENT-REAL-AUDIT.json').write_text(json.dumps(independent, indent=2) + '\n')
    print(json.dumps({'status': 'IOSURFACE_AND_DESKTOP_REPORTS_FROM_REAL_EVIDENCE', 'cases': [c['RESULT'] for c in cases],
                      'movement': desktop['movement_pixels'], 'new_GPU_submissions': 0}))


if __name__ == '__main__':
    main()
