#!/usr/bin/env python3
"""Read-only HP Linux firmware/physical-memory evidence; emit JSON to stdout.

Run as root over the existing pinned SSH connection. No mounts, package changes,
device memory reads, firmware writes or stress tests are performed.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

TARGETS = (0x101311000, 0x101313000, 0x10131C000)
PAGE_BYTES = 4096


def read_file(path):
    try:
        raw = Path(path).read_bytes()
        return {'path': str(path), 'bytes': len(raw),
                'sha256': hashlib.sha256(raw).hexdigest(),
                'text': raw.decode(errors='replace')}
    except OSError as exc:
        return {'path': str(path), 'error': str(exc)}


def call(args):
    executable = shutil.which(args[0])
    if not executable:
        return {'command': args, 'unavailable': True}
    try:
        r = subprocess.run([executable] + args[1:], capture_output=True,
                           text=True, timeout=30)
        return {'command': [executable] + args[1:], 'rc': r.returncode,
                'stdout': r.stdout, 'stderr': r.stderr}
    except subprocess.TimeoutExpired as exc:
        return {'command': args, 'timeout': True,
                'stdout': (exc.stdout or b'').decode(errors='replace'),
                'stderr': (exc.stderr or b'').decode(errors='replace')}


def overlaps(start, end):
    """Both endpoints inclusive, including the whole target 4K page."""
    return [hex(p) for p in TARGETS if start <= p + PAGE_BYTES - 1 and p <= end]


def sysfs_map(root):
    base = Path(root)
    result = {'path': root, 'available': base.is_dir(), 'entries': []}
    if not base.is_dir():
        return result
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        row = {'entry': entry.name, 'fields': {}}
        for name in ('start', 'end', 'type', 'phys_addr', 'virt_addr',
                     'num_pages', 'attribute'):
            p = entry / name
            if p.is_file():
                row['fields'][name] = read_file(p)
        try:
            start = int(row['fields']['start']['text'].strip(), 0)
            end = int(row['fields']['end']['text'].strip(), 0)
            row['target_pages_overlapping'] = overlaps(start, end)
        except (KeyError, ValueError):
            pass
        result['entries'].append(row)
    return result


def main():
    assert os.geteuid() == 0, 'Root is required for unmasked physical addresses'
    assert os.uname().sysname == 'Linux'
    model = read_file('/sys/class/dmi/id/product_name')
    assert 'HP Elite Dragonfly G2' in model.get('text', ''), 'Unexpected host'
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    out = {'schema': 1, 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'epoch': time.time(), 'euid': os.geteuid(), 'boot_id': boot,
           'model': model, 'target_physical_pages': [hex(p) for p in TARGETS],
           'boot_path_note': 'User must confirm Linux was selected directly, not through OpenCore.',
           'firmware_map_limit': 'Linux boot descriptors are not the previous macOS/OpenCore final map.'}
    paths = ['/proc/iomem', '/proc/meminfo', '/proc/cmdline', '/etc/os-release',
             '/sys/firmware/efi/systab', '/sys/firmware/efi/fw_platform_size',
             '/sys/class/dmi/id/bios_vendor', '/sys/class/dmi/id/bios_version',
             '/sys/class/dmi/id/bios_date']
    out['files'] = {p: read_file(p) for p in paths}
    text = out['files']['/proc/iomem'].get('text', '')
    ranges = []
    for line in text.splitlines():
        m = re.match(r'\s*([0-9a-fA-F]+)-([0-9a-fA-F]+)\s*:\s*(.*)', line)
        if m:
            start, end = int(m[1], 16), int(m[2], 16)
            ranges.append({'start': start, 'end': end, 'label': m[3],
                           'original': line, 'target_pages_overlapping': overlaps(start, end)})
    out['iomem_addresses_unmasked'] = any(r['start'] or r['end'] for r in ranges)
    out['iomem_target_overlaps'] = [r for r in ranges if r['target_pages_overlapping']]
    out['firmware_maps'] = [sysfs_map(p) for p in
                            ('/sys/firmware/memmap', '/sys/firmware/efi/memmap',
                             '/sys/firmware/efi/runtime-map')]
    out['commands'] = {name: call(args) for name, args in {
        'uname': ['uname', '-a'], 'kernel_log': ['dmesg'],
        'pci': ['lspci', '-nnk'], 'mounts': ['findmnt', '--json'],
        'bootctl': ['bootctl', 'status', '--no-pager'],
        'boot_variables_read_only': ['efibootmgr', '-v'],
        'time': ['timedatectl', 'status']}.items()}
    out['pci_resources'] = []
    for p in sorted(Path('/sys/bus/pci/devices').glob('*/resource')):
        row = read_file(p)
        row['target_overlaps'] = []
        for index, line in enumerate(row.get('text', '').splitlines()):
            values = line.split()
            if len(values) >= 2:
                start, end = int(values[0], 16), int(values[1], 16)
                hits = overlaps(start, end)
                if hits:
                    row['target_overlaps'].append({'resource_index': index,
                                                   'line': line, 'pages': hits})
        out['pci_resources'].append(row)
    out['rtc'] = {str(p): read_file(p) for root in Path('/sys/class/rtc').glob('rtc*')
                  for name in ('name', 'date', 'time', 'since_epoch', 'hctosys')
                  for p in (root / name,) if p.is_file()}
    config = Path('/boot/EFI/OC/config.plist')
    out['deployed_config'] = read_file(config)
    out['existing_opencore_logs'] = []
    for root in (Path('/boot'), Path('/boot/EFI/OC')):
        for p in sorted(root.glob('opencore-*.txt')):
            out['existing_opencore_logs'].append(read_file(p))
    out['boot_id_after'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert out['boot_id_after'] == boot
    out['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
