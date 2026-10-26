#!/usr/bin/env python3
"""Summarize archived upstream claims and HP resets. Offline/read-only inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def record(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def parse_reset(path):
    text = path.read_text()
    def match(pattern):
        found = re.search(pattern, text, re.M)
        require(found is not None, f'{path.name}: missing {pattern}')
        return found.group(1)
    stamp_text = text.split('Index  Submitted    Returned', 1)[1].split('Scheduler Status', 1)[0]
    stamps = {int(index): (int(submitted, 16), int(returned, 16))
              for index, submitted, returned in re.findall(r'^\s*(\d+):\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)', stamp_text, re.M)}
    require(all(index in stamps for index in range(24, 32)), 'missing compute stamp records')
    ring_text = text.split('Offset       Value', 1)[1].split('Aublist command line:', 1)[0]
    words = {int(offset, 16): int(value, 16)
             for offset, value in re.findall(r'^(0x[0-9a-f]+)\s*:\s*(0x[0-9a-f]+)', ring_text, re.M)}
    controls = [{'ring_offset': hex(offset), 'header': hex(word), 'dw1': hex(words[offset + 4]),
                 'tile_cache_flush_bit28': bool(words[offset + 4] & (1 << 28))}
                for offset, word in words.items() if word == 0x7a000004 and offset + 4 in words]
    batch = [{'ring_offset': hex(offset), 'header': hex(word), 'address_low': words.get(offset + 4),
              'address_high': words.get(offset + 8)}
             for offset, word in words.items() if word == 0x18900101]
    acthd = int(match(r'^\s*ACTHD\s*=\s*(0x[0-9a-f]+)'), 16)
    require(len(batch) == 1 and batch[0]['address_high'] == 0, 'unexpected batch-start layout')
    return {'evidence': record(path), 'target_local_time': text.splitlines()[0],
            'application': match(r'^Application:\s*(.+)$'),
            'context': int(match(r'Processing hang for hardware context ID\[(\d+)\]')),
            'IPEHR': match(r'\(IPEHR=(0x[0-9a-f]+)\)'), 'ACTHD': hex(acthd),
            'EIR': match(r'^\s*EIR\s*=\s*(0x[0-9a-f]+)'),
            'batch_start_commands': batch, 'ACTHD_minus_batch_start': hex(acthd - batch[0]['address_low']),
            'ring_PIPE_CONTROL_commands': controls,
            'compute_stamps_24_31': {str(i): {'submitted': stamps[i][0], 'returned': stamps[i][1]} for i in range(24, 32)},
            'compute_stamp_backlog_observed': any(stamps[i][0] != stamps[i][1] for i in range(24, 32)),
            'CCS_compute_ring_reported_disabled': 'CCS Ring is:\t - NOT enabled - idle' in text,
            'active_DSS_0_4_shader_samplers_done': all(
                re.search(rf'DualSubslice:{i}\s+INSTDONE_ROW \(=0xffffffff\): Not done=\s+INSTDONE_SAMPLER \(=0xffffffff\): Not done=', text)
                is not None for i in range(5)),
            'DSS5_read_marked_unreliable': 'INSTDONE_ROW (=0x00000000)' in text and 'Data could be unreliable!' in text,
            'not_observed': ['batch contents at ACTHD', 'RCU_MODE before/after reset', 'per-resource AUX/dirty flags']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    require(not args.report.exists(), 'preserve earlier analysis report')
    snapshot_path = ROOT / 'ga412/reports/UPSTREAM-ISSUES-SNAPSHOT.json'
    snapshot = json.loads(snapshot_path.read_text())
    for entry in snapshot['entries']:
        require('error' not in entry, 'upstream snapshot contains a failed fetch')
        path = ROOT / entry['path']
        require(hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], f'snapshot hash mismatch {path}')
    public = ROOT / 'ga412/private/upstream-issues-v1'
    issues = json.loads((public / 'issues.json').read_text())
    issue_index = {issue['number']: issue for issue in issues}
    require(len(issues) < 10, 'issue listing may be truncated')
    comments = {n: json.loads((public / f'issue-{n}-comments.json').read_text()) for n in [2, 3, 4, 5, 6]}
    require(all(len(value) < 10 and len(value) == issue_index[n]['comments'] for n, value in comments.items()),
            'comments were truncated or changed between snapshot requests')
    index = [{'number': issue['number'], 'title': issue['title'], 'state': issue['state'],
              'url': issue['html_url'], 'updated_at': issue['updated_at'],
              'comments_archived': [{'url': c['html_url'], 'author': c['user']['login'],
                                      'updated_at': c['updated_at']} for c in comments.get(issue['number'], [])]}
             for issue in issues]
    receipt_path = ROOT / 'ga412/private/commands/offline-followup-readonly-state.json'
    receipt = json.loads(receipt_path.read_text())
    require(receipt['returncode'] == 0, 'read-only followup SSH failed')
    require('REDACTED-SESSION-ID' in receipt['stdout'], 'unexpected boot session')
    observed_resets = re.findall(r'(Kernel_2026-10-24-\d+_host\.gpuRestart)', receipt['stdout'])
    resets = [parse_reset(ROOT / 'ga412/private/followup-readonly' / name)
              for name in ['gpuRestart-103225.txt', 'gpuRestart-110746.txt']]
    require(all(r['context'] == 5 and r['IPEHR'] == '0x7a000004' and r['ACTHD_minus_batch_start'] == '0x7e4' for r in resets),
            'reset family differs from expected evidence; re-evaluate conclusions')
    latest_source = public / 'blitfix-kern_gen11.cpp'
    source = latest_source.read_text()
    r6_path = ROOT / 'ga410/private/ng-r6/source/src/NootedGreen/kern_gen11.cpp'
    r6 = r6_path.read_text()
    require('if (!NGreen::callback->isRealTGL) {' in source and
            'if (okba && !checkKernelArgument("-ngreennoblitfix"))' in source, 'BLITFIX gate changed')
    require('if (!NGreen::callback->isRealTGL) xeGpuRecInstall(patcher, index, address, size);' in source, 'GPUREC gate changed')
    require('if (!NGreen::callback->isRealTGL || getKernelVersion() == KernelVersion::Tahoe)' in r6, 'R6 NOCCS3 gate changed')
    report = {'classification': 'ARCHIVED_PUBLIC_CLAIMS_AND_HP_READONLY_OBSERVATIONS',
              'public_snapshot_source': record(snapshot_path), 'issue_index': index,
              'not_a_continuous_monitor': True, 'upstream_installed_or_rebased': False,
              'fixed_HP_source_base': '6a1afb337d1fb1ff07ca032b5c1868fe2bd005ef',
              'HP_followup': {'same_boot_session': 'REDACTED-SESSION-ID',
                               'receipt': record(receipt_path), 'visible_reset_files_at_least': len(set(observed_resets)),
                               'visible_reset_names': observed_resets, 'representative_reports': resets,
                               'caffeinate_PIDs_991_1082_still_present_in_receipt': False,
                               'WindowServer_RSS_KiB_in_receipt': 8442272,
                               'long_term_stability_proven': False},
              'applicability': [
                  {'issue': 6, 'candidate': 'XE-BLITFIX df7ab78', 'upstream_claim': 'Author reports controlled image-copy FAIL to PASS on XPS',
                   'HP_R8_baseline': 'not the stated trigger: plain Managed target, 66820 active bytes, pitches 512/1280/1536 are 64 aligned',
                   'unobserved_pitch_1040': 'internal alternate field, not observed actual submitBlit pitch',
                   'gate': 'inside !isRealTGL and successful BLITALIGN block; does not directly install on native HP',
                   'HP_desktop_relevance': 'possible separate IOSurface path; untested, cannot substitute for CPU readback diagnosis'},
                  {'issue': 3, 'candidate': '80EU topology',
                   'upstream_claim': 'Non-TGL hardcoded 96EU count is wrong; 80EU opt-in planned, not validated there',
                   'HP_applicability': 'Native TGL 80EU/10SS/5 dispatcher already observed; do not reapply RPL topology diagnosis'},
                  {'issue': 2, 'candidate': 'XE-GPUREC v2',
                   'upstream_claim': 'RPL reset clears RCU_MODE compute enable; submitted compute stamps stop returning',
                   'HP_applicability': 'native gate excludes HP; two new reports have no 24-31 stamp backlog and IPEHR is PIPE_CONTROL, not dummy-page pattern',
                   'important_names': 'CCS compute command streamer/RCU_MODE is distinct from color-control-surface compression CCS'},
                  {'issue': 5, 'candidate': 'real TGL-H untested path',
                   'upstream_claim': 'Author has no real-TGL test machine and no proven H-series fix',
                   'HP_applicability': 'HP is TGL-UP3 and reaches desktop/Metal; H-series boot freeze is not this symptom'}],
              'evidence': [record(p) for p in [latest_source, r6_path, Path(__file__),
                                               ROOT / 'ga412/private/followup-readonly/xedrv-WindowServer.log',
                                               ROOT / 'ga410/private/r4-code-evidence/tgl-accelerator.asm',
                                               ROOT / 'ga410/private/r4-code-evidence/mtl-driver.asm']],
              'scope': {'GPU_experiments': 0, 'new_driver_or_EFI_test': False, 'reboot_or_recovery': False,
                        'public_issue_comments_posted': 0},
              'conclusion': 'HP has a CPU readback/representation failure plus recurring RCS PIPE_CONTROL hangs; a common cause is plausible, not established.'}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'public_issues': len(index), 'comments': sum(map(len, comments.values())),
                      'HP_visible_reset_reports_at_least': len(set(observed_resets)),
                      'HP_parsed_reset_reports': len(resets), 'GPU_experiments': 0}))


if __name__ == '__main__':
    main()
