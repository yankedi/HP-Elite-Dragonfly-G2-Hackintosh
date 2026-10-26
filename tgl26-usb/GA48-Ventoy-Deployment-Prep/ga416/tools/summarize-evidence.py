#!/usr/bin/env python3
"""CPU-only evidence audit and scene contact sheets; never connects to the HP."""
import datetime
import hashlib
import json
from pathlib import Path
import plistlib
import re

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
GA = ROOT / 'ga416'
PRIVATE = GA / 'private'
REPORTS = GA / 'reports'
IMAGES = GA / 'images'


def sha(data): return hashlib.sha256(data).hexdigest()
def load(path): return json.loads(path.read_text())
def receipt(name): return load(PRIVATE / 'commands' / (name + '.json'))
def save(path, value): path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def sheet(paths, dest, width=650):
    tiles = []
    for title, path in paths:
        image = Image.open(path).convert('RGB')
        image.thumbnail((width, 980))
        tiles.append((title, image))
    height = max(image.height for _, image in tiles) + 42
    out = Image.new('RGB', (width * len(tiles), height), '#dddddd')
    draw = ImageDraw.Draw(out)
    for n, (title, image) in enumerate(tiles):
        draw.text((width*n+8, 8), title, fill='black')
        out.paste(image, (width*n, 35))
    out.save(dest)


def main():
    REPORTS.mkdir(exist_ok=True); IMAGES.mkdir(exist_ok=True)
    initial_receipt = next((PRIVATE / 'commands').glob('boot-health-*.json'))
    initial = json.loads(load(initial_receipt)['stdout'])
    dmesg = initial['dmesg']['stdout']
    topology_lines = [l for l in dmesg.splitlines() if any(s in l for s in
        ['HWCAPS - NumSlices:', 'HWCAPS - NumSubSlices:', 'HWCAPS - MaxEUPerSubSlice:',
         'HWCAPS - L3BankCount:', 'HP-R5:', 'GA414 NOAUX:', 'XeNG NOAUX:', 'XE-NOCCS3:', 'XeNG PLANES2:'])]
    assert 'HP-R5: native TGL topology slices=1 subslices=10 maxEU/SS=8 totalEU=80 L3Banks=8 nativeL3=0' in dmesg
    source = ROOT.parent / 'GA414-Native-NOAUX-Source/src/NootedGreen/kern_gen11.cpp'
    topology = {'status': 'ACTUAL_PLANES2_OLD_L3_FALLBACK_CONFIRMED',
        'build': '25G83', 'session': 'REDACTED-SESSION-ID',
        'NG_UUID': '4C4C44E9-5555-3144-A1E4-CB51FF5A72E6', 'PCI': '8086:9A49',
        'NumSlices': 1, 'NumSubSlices': 10, 'ExecutionUnitCount': 80, 'MaxEUPerSubSlice': 8,
        'SliceCountFuse': '0x1', 'DualSubSliceCountFuse': '0x1f', 'EUDisableFuses': '0x0',
        'effective_reported_L3Banks': 8, 'donor_native_L3Banks': 0,
        'L3_source': 'HP-R5 hardcoded compatibility fallback; NOT A FUSE MEASUREMENT',
        'fuse_correct_L3Banks': 'NOT_OBSERVED', 'new_L3_experiment_loaded': False,
        'NOAUX_install_verified': True, 'NOCCS3_install_verified': True, 'PLANES2_install_verified': True,
        'per_resource_aux_or_CCS_kernel_state': 'NOT_OBSERVED; install evidence is not a resource-level counter',
        'counter_command': receipt('requested-ioreg-counter-check'), 'runtime_lines': topology_lines,
        'source': {'path': str(source), 'sha256': sha(source.read_bytes()), 'lines': '6371-6414',
                   'binding': 'Existing GA414 source/delivery lineage and matching runtime log; no source edit this run'},
        'limits': 'Counter absence proves neither PASS nor FAIL. 10SS/80EU fuses do not alone establish the L3 bank count.'}
    save(REPORTS / 'RUNTIME-TOPOLOGY.json', topology)

    # Independent second Expected construction: packed linear index, no imports from primary auditor/generator.
    capture = PRIVATE / 'captures/r8-capture'
    raw = {n: (capture / (n + '.bin')).read_bytes() for n in ('input', 'expected', 'gpu', 'cpu')}
    expected = bytes(c for k in range(257*65) for c in ((13*(k%257)+29*(k//257))%256, 0, 0, 255))
    packed = {n: b''.join(data[y*1280:y*1280+1028] for y in range(65)) for n, data in raw.items() if n != 'input'}
    assert len(raw['input']) == 512*65
    assert all(raw['input'][(k//257)*512+k%257] == expected[k*4] for k in range(257*65))
    assert all(len(raw[n]) == 1280*65 for n in packed)
    assert packed['expected'] == expected
    comparisons = {}
    for label, a, b in [('gpu_vs_expected', packed['gpu'], expected),
                        ('cpu_vs_expected', packed['cpu'], expected), ('cpu_vs_gpu', packed['cpu'], packed['gpu'])]:
        comparisons[label] = {'bad_pixels': sum(a[i:i+4] != b[i:i+4] for i in range(0, len(a), 4)),
                              'differing_bytes': sum(x != y for x, y in zip(a, b)), 'total_pixels': 257*65}
    primary = load(PRIVATE / 'R8-PIXEL-AUDIT.json')
    assert primary['status'] == 'PIXEL_PASS'
    for name, stats in comparisons.items():
        assert stats['bad_pixels'] == primary['comparisons'][name]['bad_pixels'] == 0
        assert stats['differing_bytes'] == primary['comparisons'][name]['differing_bytes'] == 0
    baseline = load(ROOT / 'ga414/reports/R8-RESULT.json')
    result = {'status': 'PIXEL_PASS', 'second_auditor_agrees': True, 'comparisons': comparisons,
              'active_sha256': {n: sha(data) for n, data in packed.items()},
              'matches_GA414_active_hashes': all(sha(packed[n]) == baseline['active_sha256'][n+'.bin'] for n in packed),
              'full_sha256': {n: sha(data) for n, data in raw.items()},
              'metadata': load(capture / 'result.json'), 'execution_attempts': 1,
              'authorization': load(PRIVATE / 'r8-once-authorized.json'),
              'limits': 'R8 PASS is specific to this managed RT case, not a desktop or L3 causal PASS.'}
    save(REPORTS / 'R8-RESULT.json', result)

    current = PRIVATE / 'captures/desktop'
    finder = PRIVATE / 'captures/finder-scene'
    baseline_full = ROOT / 'ga415/private/desktop-native-v1.png'
    baseline_window = ROOT / 'ga415/private/desktop-layer-pair-v3/pair-v3/after-window.png'
    sheet([('GA414 boot / GA415 captured About (2026-10-24)', baseline_full),
           ('Current PLANES2 About (2026-10-25)', current / 'settings.png')], IMAGES / 'about-desktop-comparison.png', 960)
    sheet([('Prior PLANES2 About: dark, 723x960', baseline_window),
           ('Current PLANES2 About: light, 723x960', current / 'settings-window.png')], IMAGES / 'about-window-comparison.png', 723)
    sheet([('Finder full desktop, sequential capture', finder / 'desktop.png'),
           ('Finder independent window, sequential capture', finder / 'window.png')], IMAGES / 'finder-capture-paths.png', 960)
    # Preserve pixel coordinates in lossless crops, not an error map or generated reference.
    Image.open(current / 'settings.png').crop((759, 71, 982, 1031)).save(IMAGES / 'settings-sidebar-current.png')
    Image.open(finder / 'desktop.png').crop((500, 162, 720, 922)).save(IMAGES / 'finder-sidebar-current.png')
    for label, file in [('GA414', baseline_full), ('current', current / 'settings.png')]:
        Image.open(file).crop((100, 990, 1820, 1080)).save(IMAGES / ('dock-' + label + '.png'))
    metadata = load(current / 'settings-metadata/windows.json')
    window = next(w for w in metadata if w['kCGWindowNumber'] == 30)
    scenes = {'status': 'DESKTOP_ARTIFACTS_REMAIN', 'Settings_window': window,
        'actual_capture_paths': {'metadata': 'Existing GA415 desktop-capture --metadata-only',
                                 'images': 'system screencapture -x and -x -o -l ID, graphical Terminal'},
        'ScreenCaptureKit_image_capture_this_run': 'NOT_EXECUTED; metadata only, no SCK image claim',
        'observations': {'Settings': 'Missing/cut sidebar text and partial icons/widgets in both full and independent screenshots; exact affected labels differ between sequential captures.',
                         'Finder': 'Black rectangles over sidebar labels in full capture; missing Desktop folder icon / other label fragments in independent capture. Not a reference-pixel classification.',
                         'Dock': 'Full Dock region retained. Color/stripe candidates exist, but translucency, wallpaper and app-layout differences prevent a certified unchanged-error or exact disappearance metric.'},
        'GA414_comparison': {'image': str(baseline_full.relative_to(ROOT)),
                            'identity_evidence': 'ga415/private/commands/initial-health.json and terminal-native-screenshot-launch.json; captured before PLANES2 boot on2026-10-24',
                            'same_scene': 'System Settings About + Dock',
                            'exact_AB': False, 'limits': 'Different boot, position, focus, appearance/transparency and live content; no clean desktop Expected. Finder matching old scene unavailable.'},
        'PLANES2_comparison': {'image': str(baseline_window.relative_to(ROOT)), 'same_window_dimensions': [723, 960],
                              'exact_AB': False, 'limits': 'Dark vs light appearance and redraw, not a single-factor L3 comparison.'},
        'automation_exception': 'Initial Finder Apple Events returned-1712. Read-only sample showed main event loop idle; subsequent LaunchServices Finder scene succeeded. Original stderr preserved.',
        'physical_screen_same_frame': 'NOT_OBSERVED', 'root_cause': 'ROOT_CAUSE_UNVERIFIED'}
    save(REPORTS / 'DESKTOP-COMPARISON.json', scenes)

    health = []
    for path in sorted((PRIVATE / 'commands').glob('*health*.json')):
        if path == initial_receipt: continue
        row = load(path)
        try: body = json.loads(row['stdout'])
        except (ValueError, KeyError): continue
        if 'status' in body:
            health.append({'receipt': str(path.relative_to(ROOT)), 'returncode': row['returncode'],
                          **{k: body[k] for k in ['status', 'utc', 'session', 'boot_epoch', 'issues']},
                          'diagnostic_count': len(body['diagnostics']),
                          'diagnostic_hashes': {r['path']: r['sha256'] for r in body['diagnostics']}})
    assert health and all(h['status'] == 'HEALTH_GATE_PASS' for h in health)
    assert all(h['diagnostic_hashes'] == health[0]['diagnostic_hashes'] for h in health)
    raw_manifest = json.loads(receipt('raw-diagnostic-archive')['stdout'])
    for row in raw_manifest['files']:
        p = PRIVATE / 'diagnostics' / str(Path(row['path']).relative_to('/Library/Logs/DiagnosticReports'))
        assert sha(p.read_bytes()) == row['sha256']
    panic_path = PRIVATE / 'diagnostics/Kernel-2020-01-01-081848.panic'
    panic = json.loads(panic_path.read_text().splitlines()[1])['macOSPanicString']
    decoded = (PRIVATE / 'nvram-panic-decoded.txt').read_text()
    assert decoded.rstrip('\n') == panic.rstrip('\n')
    uptime = int(re.search(r'System uptime in nanoseconds: (\d+)', decoded)[1])/1e9
    prior_boot = 1792837763
    inferred_panic = datetime.datetime.fromtimestamp(prior_boot + uptime, datetime.timezone.utc).isoformat()
    watchdog_ips = []
    for p in sorted((PRIVATE / 'diagnostics').glob('WindowServer-2026-10-25-*.ips')):
        uuids = re.findall(r'"bootSessionUUID"\s*:\s*"([A-F0-9-]+)"', p.read_text())
        watchdog_ips.append({'file': str(p.relative_to(ROOT)), 'bootSessionUUID': uuids})
    nvram = plistlib.loads((PRIVATE / 'nvram.xml').read_bytes())
    diagnostics = {'status': 'NO_NEW_CURRENT_BOOT_DIAGNOSTICS_OBSERVED', 'health_gates': health,
        'raw_archive': {k: raw_manifest[k] for k in ['archive_sha256', 'archive_bytes']},
        'raw_files_verified': len(raw_manifest['files']), 'current_boot_added_files': [],
        'current_boot_hash_changes': [], 'unified_fault_log': receipt('current-boot-unified-fault-log'),
        'previous_boot_watchdog_ips': watchdog_ips,
        'panic': {'file': str(panic_path.relative_to(ROOT)), 'incident': 'REDACTED-SESSION-ID',
                  'first_line': decoded.splitlines()[0], 'uptime_seconds': uptime,
                  'NVRAM_decoded_text_matches_panic_file_except_trailing_newlines': True,
                  'decoded_characters': len(decoded), 'panic_text_characters': len(panic),
                  'packed_NVRAM_sha256': sha(nvram['aapl,panic-info']), 'decoded_sha256': sha(decoded.encode()),
                  'boot_UUID_in_panic': 'NOT_PRESENT', 'prior_boot_candidate': 'REDACTED-SESSION-ID',
                  'candidate_panic_time_UTC_if_prior_boot': inferred_panic,
                  'attribution': 'Strong prior-boot inference from69977s uptime, matching preceding old-boot watchdog IPS and identical boot args; panic itself lacks boot UUID. Filename2020 is not event date evidence.'},
        'limits': 'Bounded healthy observation, not long-term stability. Previous diagnostics may rotate/rewrite; current-run comparison uses whole-file hashes collected within this boot.'}
    save(REPORTS / 'HEALTH-AND-PREVIOUS-FAILURE.json', diagnostics)
    # Index all retained new raw artifacts, generated analysis, images, and execution scripts.
    paths = [p for p in GA.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name != 'EVIDENCE-MANIFEST.json']
    save(REPORTS / 'EVIDENCE-MANIFEST.json', {'files': {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())} for p in sorted(paths)},
         'old_evidence_files_unchanged_by_this_script': True, 'CPU_only_analysis': True})
    print(json.dumps({'topology': topology['status'], 'R8': 'PIXEL_PASS', 'desktop': scenes['status'],
                      'diagnostics': diagnostics['status'], 'raw_diagnostics_verified': len(raw_manifest['files']),
                      'current_health_receipts': len(health), 'evidence_files': len(paths)}))


if __name__ == '__main__':
    main()
