#!/usr/bin/env python3
"""Audit one completed macOS shutdown -> direct Linux RTC observation."""
import hashlib
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT/'ga417/private/rtc-live'


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-existing',action='store_true')
    args=parser.parse_args()
    image_path = sorted(WORK.glob('image-after-RTC-*.json'))
    image_path = next(p for p in reversed(image_path) if not p.name.endswith('.receipt.json'))
    linux_path = WORK/'post-linux-20261026T013748Z.json'
    mac_path = WORK/'initial-20261026T013125Z.json'
    linux, mac, image = [json.loads(p.read_text()) for p in [linux_path,mac_path,image_path]]
    baseline = json.loads((ROOT/'ga417/reports/RTC-IMAGE.json').read_text())
    stream = json.loads((ROOT/'ga417/reports/RTC-LIVE-LOGGING-END.json').read_text())
    for name,digest in baseline['file_inventory'].items():
        assert image['inventory'][name]['sha256'] == digest
    added = sorted(set(image['inventory'])-set(baseline['file_inventory']))
    assert added == ['opencore-2026-10-26-012700.txt']
    log = next(r for r in image['collected_files'] if r['path']==added[0])
    assert '2026-10-26T01:27:04' in log['text_without_trailing_nuls']
    assert image['boot'] == linux['boot'] == 'REDACTED-MACHINE-ID'
    rtc = re.search(r'\[\s*([0-9.]+)\] rtc_cmos .*setting system clock to (\S+) UTC',linux['dmesg']['stdout'])
    ntp = re.search(r'\[\s*([0-9.]+)\].*Initial clock synchronization',linux['timesyncd']['stdout'])
    assert rtc and ntp and float(rtc[1]) < float(ntp[1])
    assert rtc[2] == '2026-10-26T01:34:12'
    assert 'ActiveState=active' in linux['service']['stdout']
    assert any('OpenCode-GA417' in l and 'sleep:idle:handle-lid-switch' in l and 'block' in l for l in linux['inhibitors']['stdout'].splitlines())
    bundle = next(b for b in mac['Metal_existing_bundles'] if b['path'].startswith('/Library/GPUBundles'))
    audit = json.loads((ROOT/'ga417/reports/METAL-POSH-AUDIT.json').read_text())
    expected = {k.casefold():v for k,v in audit['baseline_bundle_inventory'].items()}
    actual = {k.casefold():v for k,v in bundle['inventory'].items()}
    assert actual == expected
    report = {
        'status':'ONE_RTC_ONLY_TRIAL_USER_NO_POST_ERROR_AND_CORRECT_EARLY_LINUX_RTC',
        'user_observation':'Normal macOS shutdown then power-on directly into NixOS with no error; no local BIOS photo supplied',
        'macOS_boot':mac['boot'],'Linux_boot':linux['boot'],
        'candidate_release_sha256':baseline['image']['sha256'],
        'candidate_post_use_sha256':image['image_sha256_after_diagnostic'],
        'all_100_baseline_image_files_match':True,'only_added_file':added[0],
        'new_OC_log_sha256':log['sha256'],'OC_exit_boot_services_clock':'2026-10-26T01:27:04',
        'source_attestation':'New log on candidate IMG agrees with macOS boot01:27:08UTC; config hash remains RTC-only true. Supports candidate use, not instruction-level quirk execution proof.',
        'GPUBundles_full_inventory_matches_sealed_original':True,
        'GPUBundles_main_sha256':audit['binary']['sha256'],
        'Linux_early_rtc_UTC':rtc[2],'Linux_early_rtc_monotonic_seconds':float(rtc[1]),
        'Linux_first_NTP_monotonic_seconds':float(ntp[1]),'RTC_observed_before_NTP':True,
        'mac_stream_received_bytes':stream['uncompressed_bytes'],'mac_stream_gzip_integrity_and_hashes':'PASS',
        'mac_shutdown_evidence':'loginwindow Shutdown dialog09:33:22 and shutdown handler09:33:27, then GUI logout. Final hardware power-off not observable through SSH.',
        'unattended_awake_inhibitor':'ga417-awake.service active/running, sleep:idle:handle-lid-switch block verified',
        'limits':['Single short RTC observation, not repeated matched-initial-state AB or long-term efficacy proof.',
                  'No panic occurred in this captured short use by user report; does not prove pmap/wrong-zone fixed.',
                  'Last source NDJSON record partial at SSH disconnect; all received bytes losslessly retained.'],
        'sources':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in [linux_path,mac_path,image_path]],
    }
    output=ROOT/'ga417/reports/RTC-TRIAL-01.json'
    if args.verify_existing:
        assert json.loads(output.read_text())==report
        print('PASS: existing RTC trial report equals fresh source audit')
    else:
        with output.open('x') as f:
            json.dump(report,f,indent=2)
            f.write('\n')
        print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
