#!/usr/bin/env python3
"""Final offline delivery integrity audit; not desktop/root-cause acceptance."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
GA = ROOT / 'ga415'


def load(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    required = ['tools/iosurface-pixel-probe.m', 'tools/desktop-capture.m', 'tools/pixel-diff.py',
                'tools/expected-pattern.py', 'tools/build-darwin.sh', 'reports/DESKTOP-ARTIFACTS.md',
                'reports/IOSURFACE-RESULT.json', 'reports/CAPTURE-COMPARISON.json', 'reports/ROOT-CAUSE-CANDIDATES.md',
                'FINAL-REPORT.md', 'README.md', 'BLIT-OBSERVER.md']
    assert all((GA / name).is_file() and (GA / name).stat().st_size > 0 for name in required)
    export = load(GA / 'reports/EVIDENCE-EXPORT.json')
    for name, record in export['files'].items():
        path = GA / name; assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], name
    a = load(GA / 'reports/INDEPENDENT-REAL-AUDIT.json')
    b = load(GA / 'private/exported-independent-audit/INDEPENDENT-AUDIT.json'); assert a == b
    result = load(GA / 'reports/IOSURFACE-RESULT.json'); assert result['root_cause'] == 'ROOT_CAUSE_UNVERIFIED'
    assert [case['RESULT'] for case in result['cases']] == ['PIXEL_PASS', 'PIXEL_FAIL', 'PIXEL_FAIL']
    for case in result['cases']:
        capture = ROOT / case['capture']
        for name, record in case['capture_files'].items(): assert sha(capture / name) == record['sha256']
        assert case['command']['status'] == 4 and case['command']['explicit_command_buffers'] == 1
        assert case['submitBlit_source_pitch'] == case['final_2D_3D_route'] == case['XE_BLITFIX_trigger'] == 'NOT_OBSERVED'
    desktop = load(GA / 'reports/CAPTURE-COMPARISON.json')
    assert desktop['movement_pixels'] == [-240, 0] and desktop['ROOT_CAUSE'] == 'ROOT_CAUSE_UNVERIFIED'
    for side in ['before', 'after']:
        for kind, suffix in [('full', '.png'), ('window', '-window.png')]:
            path = GA / 'private/desktop-layer-pair-v3/pair-v3' / (side + suffix)
            assert sha(path) == desktop['states'][side][kind]['PNG_sha256']
    assert desktop['same_window_ROI_preserved_up_to_uniform_channel_delta']['RGBA_delta'] == [0, 0, 1, 0]
    fixtures = load(GA / 'fixtures/pixel-tools/TEST-RESULT.json'); assert len(fixtures['tests']) == 24
    adversarial = load(GA / 'fixtures/verifier-adversarial-result.json'); assert len(adversarial['tests']) == 13
    build = (GA / 'reports/native-build-v2/build.stdout').read_text()
    for name in ['iosurface-pixel-probe.m', 'desktop-capture.m', 'build-darwin.sh']:
        assert sha(GA / 'tools' / name) + '  ' in build
    observer = load(GA / 'reports/BLIT-OBSERVER-AUDIT.json')
    assert observer['status'] == 'BLIT_OBSERVER_SOURCE_BUILD_SIGN_IMAGE_USB_AUDIT_PASS_RUNTIME_PENDING'
    assert observer['native_readback_files'] == 100 and observer['max_added_total_records'] == 129
    assert observer['observer_kernel_runtime'] == 'NOT_OBSERVED'
    assert load(GA / 'reports/BLIT-OBSERVER-DECODER-TEST.json')['status'] == 'CPU_DECODER_CONTRACT_PASS'
    health = load(GA / 'reports/CONTINUATION-FINAL-HEALTH.json')
    assert health['status'] == 'CURRENT_PLANES2_HEALTH_PASS_OBSERVER_NOT_BOOTED' and not health['GPU_fault_lines']
    syntax_files = []
    for path in sorted((GA / 'tools').glob('*.py')):
        compile(path.read_text(), str(path), 'exec'); syntax_files.append(str(path.relative_to(GA)))
    for path in [*sorted((GA / 'tools').glob('*.command')), GA / 'tools/build-darwin.sh']:
        subprocess.run(['bash', '-n', str(path)], check=True); syntax_files.append(str(path.relative_to(GA)))
    for path in [GA / 'README.md', GA / 'FINAL-REPORT.md', GA / 'BLIT-OBSERVER.md',
                 GA / 'reports/DESKTOP-ARTIFACTS.md', GA / 'reports/ROOT-CAUSE-CANDIDATES.md']:
        for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            if '://' not in target: assert (path.parent / target.split('#', 1)[0]).is_file(), (path, target)
    report = {'status': 'PIXEL_DELIVERABLES_INTEGRITY_AUDIT_PASS_GOAL_INCOMPLETE',
              'required_files': {name: {'bytes': (GA / name).stat().st_size, 'sha256': sha(GA / name)} for name in required},
              'exported_files_verified': len(export['files']), 'independent_real_capture_audits_identical': True,
              'native_source_hashes_match_build': True, 'syntax_files_checked': syntax_files,
              'synthetic_pixel_checks': 24, 'adversarial_verifier_checks': 13, 'new_GPU_test_submissions': 0,
              'observer_image': observer['image'], 'observer_USB_image': observer['USB_image'],
              'observer_runtime': 'NOT_OBSERVED', 'desktop_root_cause': 'ROOT_CAUSE_UNVERIFIED',
              'original_nine_questions_verbatim_mapping': 'UNVERIFIED',
              'goal_complete': False, 'pending': ['User manual BLITOBS boot and identity/health/install verification',
                                               'Fresh on-site single-case C GPU authorization and actual pitch/final-helper evidence',
                                               'Kernel-cause and desktop-resource linkage; single-factor repair acceptance if justified',
                                               'Original nine-question verbatim mapping; long-term stability remains unverified']}
    with (GA / 'reports/DELIVERY-AUDIT.json').open('x') as stream: json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps({k: report[k] for k in ['status', 'exported_files_verified', 'goal_complete', 'pending']}, indent=2))


if __name__ == '__main__':
    main()
