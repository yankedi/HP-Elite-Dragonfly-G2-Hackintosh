#!/usr/bin/env python3
"""Audit preserved MmapDump descriptors and timings; no target access."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import statistics

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga416/private/oc-memory-debug'
LOG = WORK / 'post-mmap-extracted/opencore-2026-10-25-131626.txt'
TARGETS = (0x101311000, 0x101313000, 0x10131c000)
ROW = re.compile(r'OCMM: (.+?)\s+\[([^]]+)\] 0x([0-9A-F]+)-0x([0-9A-F]+) -> 0x([0-9A-F]+)')
STAMP = re.compile(r'^(\d+):(\d+)\s+(\d+):(\d+)')


def stamp(line):
    m = STAMP.match(line)
    assert m, line
    return int(m[1]) + int(m[2]) / 1000


def overlaps(a, b):
    return a['start'] <= b['end'] and b['start'] <= a['end']


def main():
    raw = LOG.read_bytes()
    lines = raw.rstrip(b'\0').decode().splitlines()
    names = iter(['initial_mat', 'original_map', 'rebuilt_mat', 'split_map', 'shrunken_map'])
    sections, current = {}, None
    for index, line in enumerate(lines, 1):
        if 'OCMM: MemoryAttributesTable:' in line or 'OCMM: MemoryMap:' in line:
            name = next(names)
            current = {'line': index, 'timestamp': stamp(line), 'entries': []}
            sections[name] = current
        if current is None:
            continue
        m = re.search(r'OCMM:\s+(NumberOfEntries|DescriptorSize|Version|Size)\s+- 0x([0-9A-F]+)', line)
        if m:
            current[m[1]] = int(m[2], 16)
        m = ROW.search(line)
        if m:
            flags = [v.strip() for v in m[2].split('|') if v.strip()]
            current['entries'].append({'line': index, 'timestamp': stamp(line),
                                       'type': m[1].strip(), 'flags': flags,
                                       'start': int(m[3], 16), 'end': int(m[4], 16),
                                       'virtual': int(m[5], 16)})
    assert len(sections) == 5
    for name, section in sections.items():
        entries = section['entries']
        assert len(entries) == section['NumberOfEntries'], name
        assert section['DescriptorSize'] == 48
        if 'Size' in section:
            assert section['Size'] == len(entries) * section['DescriptorSize']
        assert all(e['start'] % 4096 == 0 and (e['end'] + 1) % 4096 == 0 and e['end'] >= e['start'] for e in entries)
        section['overlapping_descriptors'] = [
            [a['line'], b['line']] for i, a in enumerate(entries) for b in entries[i + 1:] if overlaps(a, b)]
        assert not section['overlapping_descriptors'], name
        section['type_counts'] = dict(Counter(e['type'] for e in entries))
        section['target_page_overlaps'] = {
            hex(t): [e for e in entries if overlaps(e, {'start': t, 'end': t + 4095})] for t in TARGETS}
        if name.endswith('_map'):
            for rows in section['target_page_overlaps'].values():
                assert len(rows) == 1 and rows[0]['type'] == 'Available' and 'RUN' not in rows[0]['flags']
        else:
            assert not any(section['target_page_overlaps'].values())
    def signature(e):
        return {k: v for k, v in e.items() if k not in ('line', 'timestamp')}
    mat_equal = ([signature(e) for e in sections['initial_mat']['entries']] ==
                 [signature(e) for e in sections['rebuilt_mat']['entries']])
    mat_coverage = []
    for entry in sections['initial_mat']['entries']:
        matches = [e for e in sections['original_map']['entries'] if overlaps(e, entry)]
        contained = len(matches) == 1 and matches[0]['start'] <= entry['start'] and matches[0]['end'] >= entry['end']
        assert contained and 'RUN' in matches[0]['flags']
        assert 'RUN' in entry['flags'] and (('RO' in entry['flags']) != ('XP' in entry['flags']))
        mat_coverage.append({'mat_line': entry['line'], 'memory_map_lines': [e['line'] for e in matches],
                             'contained_in_runtime_descriptor': contained})
    def event(needle, which=0):
        rows = [(i, l) for i, l in enumerate(lines, 1) if needle in l]
        i, line = rows[which]
        return {'line': i, 'timestamp': stamp(line), 'text': line}
    markers = {
        'first_menu': event('OCB: Showing menu...'),
        'tool_start': event('MMDD: OpenRuntime r12'),
        'original_map': event('MMDD: Dumping the original memory map'),
        'rebuilt_attributes': event('MMDD: Dumping patched attributes'),
        'split_map': event('MMDD: Dumping patched memory map'),
        'shrunken_map': event('MMDD: Dumping shrinked memory map'),
        'tool_return': event('OCB: Restored mode'),
        'second_menu': event('OCB: Showing menu...', 1)}
    menu_line = markers['first_menu']['line']
    delays = []
    for line in lines[:menu_line]:
        m = STAMP.match(line)
        if m:
            delays.append(int(m[3]) + int(m[4]) / 1000)
    extraction = json.loads((WORK / 'post-mmap-image-20261025T132852Z.json').read_text())
    baseline = json.loads((ROOT / 'ga416/reports/OC-MEMORY-DEBUG-IMAGE.json').read_text())
    actual = {p.casefold(): row['sha256'] for p, row in extraction['inventory'].items()}
    differences = [p for p, digest in baseline['full_image_inventory'].items() if actual.get(p.casefold()) != digest]
    assert not differences
    for row in extraction['collected_files']:
        p = WORK / 'post-mmap-extracted' / row['path']
        assert p.stat().st_size == row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest() == row['sha256']
    rtc = json.loads((WORK / 'post-mmap-rtc-context-20261025T133306Z.data.json').read_text())
    report = {
        'status': 'OC_DIAGNOSTIC_BOOT_LOGS_COLLECTED_AND_AUDITED_ROOT_CAUSE_NOT_PROVEN',
        'log': str(LOG.relative_to(ROOT)), 'log_sha256': hashlib.sha256(raw).hexdigest(),
        'log_bytes': len(raw), 'non_nul_bytes': len(raw.rstrip(b'\0')),
        'log_has_unused_trailing_space': raw.endswith(b'\0'),
        'linux_boot_after_tool': extraction['boot'],
        'image_sha256_after_diagnostic': extraction['image_sha256_after_diagnostic'],
        'baseline_file_changes': differences, 'extracted_file_count': len(extraction['collected_files']),
        'new_file_count': len(set(actual) - {p.casefold() for p in baseline['full_image_inventory']}),
        'MAT_unchanged_by_tool': mat_equal, 'MAT_structural_checks_pass': True,
        'MAT_entries_covered_by_original_runtime_map': mat_coverage,
        'MAT_RW_XP_policy_caveat': 'RT Code plus XP subregions are interpreted by the split operation as runtime data; not by themselves proof of invalid firmware. Printed capabilities WB/WT/WC/UC are not simultaneous active CPU cache modes.',
        'sections': sections, 'timing_markers': markers,
        'seconds_to_first_menu': markers['first_menu']['timestamp'],
        'seconds_in_tool': round(markers['tool_return']['timestamp'] - markers['tool_start']['timestamp'], 3),
        'pre_menu_largest_logged_gap_seconds': max(delays),
        'pre_menu_median_logged_gap_seconds': statistics.median(delays),
        'timing_interpretation': 'Distributed latency during diagnostics/logging and scan. File logging safe mode rewrites full log buffer per emission in OC1.0.8. No A/B timing attribution to an individual device, console or file I/O.',
        'RTC_after_tool_early_kernel_lines': [l for l in rtc['dmesg']['stdout'].splitlines() if 'rtc_cmos' in l],
        'RTC_interpretation': 'This Linux -> OC diagnostic -> Linux sequence starts with a correct 2026 date. Previous post-macOS Linux boot started in 2020. Supports sequence-dependent follow-up, does not identify writer or prove absent POST005.',
        'macOS_final_handoff_map_obtained': False,
        'limitations': ['MmapDump original is taken with OC and OpenRuntime loaded, not pristine firmware.',
                        'Split/shrunken maps are diagnostic tool copies, not a captured final macOS handoff.',
                        'No crash-time managed-page attributes, reverse maps, PTEs or valid kernel core.',
                        'Structural MAT checks do not validate runtime service executable behavior.'],
        'next_action': 'Do not repeat MmapDump. Current evidence does not justify declaring the forum Quirks group a fix. Any comparison changing boot memory policy remains a separately authorized rollback-capable experiment.'}
    output = ROOT / 'ga416/reports/OC-MEMORY-DEBUG-RESULT.json'
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: report[k] for k in ('status', 'log_sha256', 'new_file_count', 'MAT_unchanged_by_tool',
                                            'seconds_to_first_menu', 'seconds_in_tool', 'pre_menu_largest_logged_gap_seconds')}, indent=2))
    print('Descriptor counts:', {k: v['NumberOfEntries'] for k, v in sections.items()})


if __name__ == '__main__':
    main()
