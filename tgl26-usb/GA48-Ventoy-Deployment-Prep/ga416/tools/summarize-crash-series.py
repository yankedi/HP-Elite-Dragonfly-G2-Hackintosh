#!/usr/bin/env python3
"""Summarize retained panic evidence without treating reset wall clocks as chronology."""
import base64
import collections
import hashlib
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga416/private/crash-series'
HISTORICAL_INCIDENT = 'B8572953-6114-4FC0-94E2-0693162ACF22'


def field(text, pattern):
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1) if match else None


def main():
    source = WORK / 'snapshot-20261025T115359Z.json'
    snapshot = json.loads(source.read_text())
    recovered_source = WORK / 'post-hang-reboot-20261025T122002Z.json'
    recovered = json.loads(recovered_source.read_text())
    baseline = json.loads((ROOT / 'ga416/private/crash-investigation/initial-collection.json').read_text())
    old_hashes = {d.get('sha256') for d in baseline['diagnostics'] if d.get('sha256')}
    rows = []
    seen = set()
    for diagnostic in snapshot['diagnostics'] + recovered['panics']:
        path = Path(diagnostic['path'])
        if path.suffix != '.panic' or path.name.startswith('.'):
            continue
        header, body = [json.loads(line) for line in diagnostic['content'].splitlines()[:2]]
        incident = header['incident_id']
        if incident in seen:
            continue
        seen.add(incident)
        text = body['macOSPanicString']
        uptime_ns = int(field(text, r'^System uptime in nanoseconds: (\d+)'))
        uptime = uptime_ns / 1e9
        rows.append({
            'incident': incident, 'file': path.name, 'sha256': diagnostic['sha256'],
            'historical_comparator': incident == HISTORICAL_INCIDENT,
            'absent_from_initial_crash_snapshot': diagnostic['sha256'] not in old_hashes,
            'recorded_timestamp_not_event_time': header['timestamp'],
            'panic': text.splitlines()[0],
            'task_context_not_culprit': field(text, r'^Process name corresponding to current thread .*?: (.+)$'),
            'uptime_seconds': uptime,
            'uptime_nanoseconds': uptime_ns,
            'uptime_display': f'{int(uptime // 60)}m {uptime % 60:.3f}s',
            'os': field(text, r'^Mac OS version:\n(.+)$'),
            'kernel_uuid': field(text, r'^Kernel UUID: (.+)$'),
            'bootargs': field(text, r'^Boot args: (.+)$'),
            'shutdown_begun': field(text, r'^System shutdown begun: (.+)$'),
            'sleep_fields': field(text, r'^  Sleep\s+: (.+)$'),
            'compressor': field(text, r'^Compressor Info: (.+)$'),
            'stackshot_status': base64.b64decode(body['macOSProcessedStackshotData']).decode(),
            'NG_UUID_in_panic': '4C4C44D4-5555-3144-A13A-DFB86EFBE513' in text,
        })
    new = [r for r in rows if not r['historical_comparator']]
    assert len(new) == 4, 'Review scope if the retained incident set changes'
    values = [r['uptime_seconds'] for r in new]
    core = (WORK / 'kernelcore-20261025T1207.bin').read_bytes()
    placeholder = len(core) == 1048576 and all(
        core[i:i + 4096] == b'\0' * 4095 + b'\n' for i in range(0, len(core), 4096))
    stream_receipt = json.loads((WORK / 'passive-stream-20261025T120724Z.result.json').read_text())
    stream_path = ROOT / stream_receipt['stdout']
    stream_bytes = stream_path.read_bytes()
    assert hashlib.sha256(stream_bytes).hexdigest() == stream_receipt['stdout_sha256']
    events = [json.loads(line) for line in stream_bytes.decode().splitlines() if line.startswith('{')]
    watchdog_events = [e for e in events if Path(e.get('processImagePath', '')).name == 'watchdogd']
    sync_timeouts = [e for e in events if 'synchronize timed out' in e.get('eventMessage', '')]
    fourth_id = '6D7209BA-EF7A-4CE6-9FD8-35A33E55810D'
    fourth = next(r for r in new if r['incident'] == fourth_id)
    fourth_raw = next(d for d in recovered['panics'] if d.get('sha256') == fourth['sha256'])
    fourth_text = json.loads(fourth_raw['content'].splitlines()[1])['macOSPanicString']
    decoded = (WORK / 'post-hang-nvram-decoded-20261025T122002Z.txt').read_text()
    assert fourth_text.rstrip('\n') == decoded.rstrip('\n')
    timebase = json.loads((WORK / 'post-hang-timebase-20261025T122207Z.json').read_text())['timebase']
    assert timebase == {'rc': 0, 'numer': 1, 'denom': 1}
    gap_ns = fourth['uptime_nanoseconds'] - events[-1]['machTimestamp']
    retained_source = WORK / 'logs-20261025T115517Z.json'
    retained = json.loads(json.loads(retained_source.read_text())['unified']['stdout'])
    boots = collections.defaultdict(list)
    for event in retained:
        boots[event.get('bootUUID', 'unknown')].append(event)
    clock_jumps = []
    for boot, boot_events in boots.items():
        by_mach = sorted(boot_events, key=lambda e: e.get('machTimestamp', 0))
        early = next((e for e in by_mach if e.get('timestamp', '').startswith('2020-')), None)
        corrected = next((e for e in by_mach if e.get('timestamp', '').startswith('2026-')
                          and early and e['machTimestamp'] > early['machTimestamp']), None)
        if corrected:
            clock_jumps.append({
                'boot': boot,
                'early_wall_timestamp': early['timestamp'],
                'early_machTimestamp': early['machTimestamp'],
                'later_wall_timestamp': corrected['timestamp'],
                'later_machTimestamp': corrected['machTimestamp'],
                'limit': 'Proves wall-clock correction within the same boot, not RTC writer identity.',
            })
    result = {
        'status': 'FOUR_RECENT_PANICS_WITH_REPEATED_PMAP_ASSERTION_ROOT_CAUSE_NOT_PROVEN',
        'source': str(source.relative_to(ROOT)),
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'recovered_source': str(recovered_source.relative_to(ROOT)),
        'recovered_source_sha256': hashlib.sha256(recovered_source.read_bytes()).hexdigest(),
        'recent_count': len(new), 'historical_comparator_count': len(rows) - len(new),
        'panics_ordered_by_uptime_not_chronology': sorted(rows, key=lambda r: r['uptime_seconds']),
        'recent_uptime_statistics_seconds': {
            'min': min(values), 'max': max(values), 'median': statistics.median(values),
            'mean': statistics.mean(values),
            'limit': 'Small selected set, not a failure-rate or fixed-timer estimate.',
        },
        'shared_facts': {
            'os': sorted({r['os'] for r in new}),
            'kernel_uuid': sorted({r['kernel_uuid'] for r in new}),
            'same_bootargs': len({r['bootargs'] for r in new}) == 1,
            'shutdown_not_begun_all': all(r['shutdown_begun'] == 'NO' for r in new),
            'sleep_fields_zero_all': all(set(r['sleep_fields'].split()) == {'0x0000000000000000'} for r in new),
            'no_full_panic_stackshot_all': all('no on disk' in r['stackshot_status'] for r in new),
            'different_task_contexts': sorted({r['task_context_not_culprit'] for r in new}),
            'memory_management_assertions': 3, 'pmap_recycle_page_assertions': 2, 'watchdogd_timeout': 1,
            'retained_panic_text_does_not_identify_NG_UUID': all(not r['NG_UUID_in_panic'] for r in new),
        },
        'latest_user_observations': {
            'idle_recurrence': 'Several boots failed while waiting; elapsed time varies; no unique UI trigger established.',
            'boot_source': 'User reports current boot uses HP internal disk OpenCore; not independent path attestation.',
            'rtc': 'User reports BIOS system time lost on next boot after macOS; exact BIOS message/photo pending.',
        },
        'additional_user_confirmed_hang': {
            'boot': stream_receipt['boot_session'],
            'user_confirmation': '又卡死了 (in response to whole-desktop/touchscreen/external-mouse unresponsive choice)',
            'new_panic_recovered': True,
            'incident': fourth_id,
            'nvram_same_text_except_trailing_newlines': True,
            'nvram_exact_raw_text_match': fourth_text == decoded,
            'timebase': timebase,
            'last_stream_event_to_panic_nanoseconds': gap_ns,
            'last_stream_event_to_panic_milliseconds': gap_ns / 1e6,
            'limit': 'Temporal and user-scene correlation with the captured boot; panic text itself contains no boot-session UUID.',
            'stream_bytes': len(stream_bytes),
            'stream_sha256': stream_receipt['stdout_sha256'],
            'stream_events': len(events),
            'message_types': dict(collections.Counter(e.get('messageType', 'activity') for e in events)),
            'first_event': events[0]['timestamp'],
            'last_event': events[-1]['timestamp'],
            'last_mach_timestamp': events[-1]['machTimestamp'],
            'last_watchdogd_event': watchdog_events[-1]['timestamp'],
            'last_watchdogd_event_not_last_checkin': True,
            'WindowServer_sync_timeout_count': len(sync_timeouts),
            'WindowServer_sync_timeouts': [
                {'timestamp': e['timestamp'], 'message': e['eventMessage']} for e in sync_timeouts],
            'ssh_returncode': stream_receipt['returncode'],
            'ssh_finished_utc': stream_receipt['finished_utc'],
            'no_causal_attribution_from_last_log': True,
        },
        'kernelcore': {
            'bytes': len(core), 'sha256': hashlib.sha256(core).hexdigest(),
            'repeated_zero_pages_with_newlines': placeholder,
            'usable_kernel_dump': False if placeholder else None,
        },
        'retained_unified_log_clock_evidence': {
            'source': str(retained_source.relative_to(ROOT)),
            'events': len(retained), 'boot_count': len(boots),
            'same_boot_2020_to_2026_examples': clock_jumps,
            'six_hour_query_did_include_these_2020_records': bool(clock_jumps),
            'limit': 'Use boot identity and monotonic time; do not assume wall-clock filtering or filenames establish chronology.',
        },
        'limits': [
            'Report timestamps include 2020-01-01; cannot order incidents by filenames/mtime.',
            'Wall-clock queries need validation across RTC resets; this retained query did include early 2020 messages.',
            'Current loaded driver identity is not proof of the loaded UUID in every prior panic.',
            'OSObject/VM/IOSurface assertions identify detection sites, not the earlier corruptor.',
            'The historical WindowServer 120s panic is not one of these four recent incidents.',
        ],
    }
    output = ROOT / 'ga416/reports/L3-6-CRASH-SERIES.json'
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(output.relative_to(ROOT))
    for row in sorted(new, key=lambda r: r['uptime_seconds']):
        print(row['incident'], row['uptime_display'], row['task_context_not_culprit'])


if __name__ == '__main__':
    main()
