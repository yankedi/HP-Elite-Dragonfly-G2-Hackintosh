#!/usr/bin/env python3
"""Offline attribution of the post-deployment watchdog panic; no target execution."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import re

ROOT = Path(__file__).resolve().parents[2]
GA = ROOT / 'ga416'
WORK = GA / 'private/crash-investigation'


def load(p):
    return json.loads(p.read_text())


def rows(s):
    return json.loads(s[s.index('['):])


def main():
    initial = load(WORK / 'initial-collection.json')
    detail = load(WORK / 'detail-collection.json')
    timeline = load(WORK / 'timeline-collection.json')
    privacy = load(WORK / 'privacy-previous-boot.json')
    live = load(WORK / 'live-stacks.json')
    baseline = json.loads(load(GA / 'private/commands/l3six-initial-runtime-health.json')['stdout'])
    old_hashes = {d['sha256'] for d in baseline['diagnostics']}
    panic = next(d for d in initial['diagnostics'] if d['path'].endswith('/Kernel-2026-10-25-170545.panic'))
    assert panic['sha256'] not in old_hashes
    assert hashlib.sha256(panic['content'].encode()).hexdigest() == panic['sha256']
    header, body = [json.loads(line) for line in panic['content'].splitlines()]
    text = body['macOSPanicString']
    assert header['incident_id'] == '2A1A0C70-8653-4835-976D-9F65B7305672'
    assert 'no checkins from watchdogd in 98 seconds' in text
    spec = importlib.util.spec_from_file_location('decoder', ROOT / 'ga410/tools/decode-nvram-panic.py')
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)
    nvram = plistlib.loads(initial['nvram']['stdout'].encode())
    decoded = decoder.unpack_ascii(nvram['aapl,panic-info'])
    assert decoded == text or decoded.rstrip() == text.rstrip()
    assert 'NootedGreen' not in text and 'AppleIntelTGL' not in text
    assert 'System shutdown begun: NO' in text and 'Hibernation exit count: 0' in text
    uptime = int(re.search(r'System uptime in nanoseconds: (\d+)', text)[1])
    previous_boot = '636D5DFC-CBBB-4ECF-BFE4-65F72FE7093F'
    current_boot = initial['session']['stdout'].strip()
    assert current_boot == timeline['session']['stdout'].strip() == live['session']
    identity_path = GA / 'private/commands/crash-investigation-identity-20261025T091036Z.json'
    identity = load(identity_path)
    assert identity['returncode'] == 0 and current_boot in identity['stdout']
    assert '4C4C44D4-5555-3144-A13A-DFB86EFBE513' in next(
        line for line in identity['stdout'].splitlines() if 'com.StezzaPilot.NootedGreen ' in line)
    history = [r for r in rows(detail['unified']['stdout']) if r.get('bootUUID') == previous_boot]
    previous_watchdog = [r for r in rows(timeline['unified']['stdout'])
                         if r.get('bootUUID') == previous_boot and r.get('processImagePath', '').endswith('/watchdogd')]
    compiler = [r for r in history if r.get('processImagePath', '').endswith('/MTLCompilerService')
                and 'Compilation BEGIN (ParentProcessName=mediaanalysisd_632)' in r['eventMessage']
                and 'MTLBuildLibraryFromSourceToArchive' in r['eventMessage']]
    assert len(compiler) == 800
    settings = [r for r in privacy if r.get('processImagePath', '').endswith('/System Settings')]
    privacy_pages = [r for r in settings if 'Privacy' in r['eventMessage'] or 'Security' in r['eventMessage']]
    dmesg = initial['dmesg']['stdout']
    assert 'HP-GA416: effective L3BankCount = 6' in dmesg
    assert 'native TGL topology slices=1 subslices=10 maxEU/SS=8 totalEU=80 L3Banks=6' in dmesg
    assert all(s['rc'] == 0 for s in live['samples'])
    assert 'watchdogd service monitoring thread' in live['samples'][0]['stdout']
    stackshot = base64.b64decode(body['macOSProcessedStackshotData']).decode()
    evidence = {}
    for p in sorted(WORK.glob('*')):
        if p.is_file():
            evidence[str(p.relative_to(ROOT))] = {'bytes': p.stat().st_size,
                                                 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    result = {
        'status': 'NEW_WATCHDOG_PANIC_CONFIRMED_UNDERLYING_BLOCKER_NOT_PROVEN',
        'incident': header['incident_id'], 'panic_file': panic['path'], 'panic_sha256': panic['sha256'],
        'panic_first_line': text.splitlines()[0], 'nvram_panic_exact_decode_matches': True,
        'new_vs_previously_accepted_USB_boot': True,
        'panic_uptime_seconds': uptime / 1e9, 'panic_file_timestamp': header['timestamp'],
        'timestamp_limit': 'Report timestamp is after current reboot; do not identify it as the exact original crash time.',
        'user_reported_last_action': '打开隐私与安全性设置',
        'user_reported_end_of_event': '我最后是长按关机键强制关机的',
        'observed_sequence_limit': 'User ended the unresponsive episode by holding the power button. Automatic panic-driven reboot was not observed; exact freeze/power-button timing is unavailable.',
        'direct_mechanism': 'Kernel watchdog/AppleSMC timer panicked after watchdogd stopped checking in for 98 seconds.',
        'mechanism_is_not_root_cause': 'Missed check-ins explain why the watchdog fired, not why watchdogd stopped making progress. The saved panic does not identify a blocked thread or lock owner.',
        'backtrace_extensions': ['com.apple.driver.watchdog', 'com.apple.driver.AppleSMC'],
        'backtrace_limit': 'This is the detecting timer thread, not the blocked watchdogd thread or the original lock owner. It does not establish an AppleSMC bug.',
        'stackshot_diagnostic': stackshot,
        'underlying_root_cause': 'NOT_PROVEN; no full panic-time all-thread stackshot/lock owner available.',
        'previous_boot_from_persisted_logs': previous_boot,
        'previous_watchdog_last_retained_log': {k: previous_watchdog[-1][k] for k in ['timestamp', 'machTimestamp', 'eventMessage']},
        'previous_boot_identity_limit': 'Panic omits loaded kext UUID and L3 fields; current boot identity cannot substitute those missing previous-boot fields.',
        'background_compiler_activity': {
            'source_requests_from_mediaanalysisd': len(compiler),
            'first_retained_request': compiler[0]['timestamp'], 'last_retained_request': compiler[-1]['timestamp'],
            'request': 'MTLBuildLibraryFromSourceToArchive',
            'attribution': 'Correlated background activity only; neither GPU hang nor compiler-caused watchdog starvation is proven.',
            'completion_limit': 'Absence of a corresponding retained SUCCESS log does not by itself prove failure or an infinite loop.'},
        'settings_last_retained_event': {k: settings[-1][k] for k in ['timestamp', 'eventMessage']},
        'privacy_page_events_retained_in_Settings': len(privacy_pages),
        'settings_attribution_limit': 'User reports opening Privacy & Security; retained Settings page transition is Displays -> Trackpad before logs stop. No causal Privacy/TCC exception established.',
        'background_disk_writes': {'process': 'STExtractionService.privileged', 'MB': 2147.80,
                                   'seconds': 613, 'action_taken': 'none',
                                   'attribution': 'Resource diagnostic, not itself a process crash or proof of disk failure.'},
        'current_boot': {'session': current_boot, 'NG_UUID': 'REDACTED-SESSION-ID',
                         'L3': 6, 'EUs': 80, 'SS': 10,
                         'loaded_identity_receipt': 'ga416/private/commands/crash-investigation-identity-20261025T091036Z.json',
                         'latest_uptime': live['uptime'],
                         'watchdog_live_sample': 'Run loop and timed semaphore waits; later post-reboot sample is not the panic-time stack.',
                         'compiler_live_sample': 'Idle at final sampling; initial CPU ~90% each for two compiler services was transient.',
                         'boot_medium': 'Not independently established from loaded NG UUID alone.'},
        'relationship_to_prior_acceptance': 'Earlier L3 desktop recovery and one R8 PIXEL_PASS remain historical facts. New panic means overall stability is not established.',
        'remaining_diagnostic_need': 'Panic-time watchdogd and kernel all-thread stacks, preferably before log persistence stops, to identify wait chain/lock owner.',
        'changes_to_drivers_EFI_NVRAM': False, 'new_GPU_test_submissions': 0,
        'automatic_reboot_or_reproduction': False, 'evidence_files': evidence}
    dest = GA / 'reports/L3-6-CRASH-INVESTIGATION.json'
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['status', 'incident', 'panic_uptime_seconds', 'nvram_panic_exact_decode_matches']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
