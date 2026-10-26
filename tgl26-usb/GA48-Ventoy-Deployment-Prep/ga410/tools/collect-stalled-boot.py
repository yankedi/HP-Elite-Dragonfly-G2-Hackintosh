#!/usr/bin/env python3
"""Read-only TGL image inspection after the first stalled hardware boot."""
import hashlib
import json
from pathlib import Path
import plistlib
import shlex
import tarfile

import recovery_ssh
import remote

ROOT = remote.ROOT
BASE = '/tmp/ga410-firstboot-stall'
HASHER = '/Volumes/TARGET_VOLUME/GA410-FirstBoot-20261023/recovery-sha256'
IMAGE = '/Volumes/TARGET_VOLUME/ISO/linux/HP-Tahoe-TGL-GA410-CSR203-AMFI.img'


def main():
    recovery_ssh.configure()
    before = json.loads((ROOT / 'reports/FINALPREP-IMAGES.json').read_text())['images'][0]
    delivered = json.loads((ROOT / 'reports/FINALPREP-DELIVERY.json').read_text())['images'][0]
    r = remote.run('firstboot-stall-oc-image-attach',
                   '/usr/bin/hdiutil attach -readonly -nomount -imagekey diskimage-class=CRawDiskImage -plist ' + shlex.quote(IMAGE), timeout=60)
    entities = plistlib.loads(r['stdout'].encode())['system-entities']
    device = next(e['dev-entry'] for e in entities if e.get('content-hint') == 'FDisk_partition_scheme')
    part = next(e['dev-entry'] for e in entities if e.get('content-hint') == '0xEF')
    mount = BASE + '/tgl-first-stall-readonly'
    remote.run('firstboot-stall-oc-image-mount',
               'set -eu; /bin/mkdir ' + shlex.quote(mount) + '; /sbin/mount_msdos -o rdonly ' + shlex.quote(part) + ' ' + shlex.quote(mount), timeout=45)
    try:
        r = remote.run('firstboot-stall-oc-image-inventory',
                       '/usr/bin/find ' + shlex.quote(mount) + ' -type f -exec ' + HASHER + ' {} \\;', timeout=180)
        current = {}
        for line in r['stdout'].splitlines():
            digest, path = line.split('  ', 1)
            assert path.startswith(mount + '/')
            current[path[len(mount) + 1:]] = digest
        expected = {'EFI/' + k: v for k, v in before['efi_inventory'].items()}
        expected.update(delivered['non_EFI_payloads'])
        changed = {k: {'before': expected.get(k), 'after': current.get(k)}
                   for k in sorted(set(expected) | set(current)) if expected.get(k) != current.get(k)}
        efi_ok = {k: v for k, v in current.items() if k.startswith('EFI/')} == {k: v for k, v in expected.items() if k.startswith('EFI/')}
        assert efi_ok, changed
        assert all(k.startswith('opencore-') and k.endswith('.txt') for k in changed), changed
        remote.run('firstboot-stall-oc-archive',
                   'set -eu; cd ' + shlex.quote(mount) + '; /usr/bin/tar -cpf ' + BASE + '/oc-first-stall.pax opencore-*.txt EFI/OC/config.plist FIRST-BOOT.txt; ' + HASHER + ' ' + BASE + '/oc-first-stall.pax', timeout=60)
        local = ROOT / 'private/oc-first-stall.pax'
        remote.download(BASE + '/oc-first-stall.pax', local, timeout=60)
        logs = ROOT / 'private/first-stall-oc-logs'
        logs.mkdir()
        with tarfile.open(local) as archive:
            for item in archive.getmembers():
                if item.isfile() and item.name.startswith('opencore-') and '/' not in item.name:
                    (logs / item.name).write_bytes(archive.extractfile(item).read())
        new_text = (logs / 'opencore-2020-01-01-000104.txt').read_bytes().replace(b'\0', b'').decode(errors='replace')
        assert '#[EB|MBA:OUT]' in new_text and '#[EB|CSR:OUT] 0x00000243' in new_text
        report = {'status': 'FIRST_HARDWARE_BOOT_STALLED', 'source_image': IMAGE,
                  'installed_boot_session_uuid': 'REDACTED-SESSION-ID',
                  'collector_marker_present': True, 'collector_finished': False,
                  'collector_nonempty_command_outputs': 0,
                  'EFI_bytes_match_preboot_candidate': efi_ok, 'image_file_changes': changed,
                  'image_inventory': current,
                  'screen_observation': 'IGPU probe rejected: -allow3d is NOT set; NG framebuffer post-start and registerService visible.',
                  'old_panic_excluded': '.contents.panic contains earlier WEG/lilucpu/igfxtgl* boot-args; not evidence of this NG attempt.',
                  'complete_kernel_log_recovered': False,
                  'boot_efi_output_CSR': '0x243',
                  'boot_efi_vs_prepared_CSR_difference': '0x40 set in boot.efi output; kernel CSR not independently captured. Do not label 0x203 as observed runtime CSR.',
                  'boot_efi_confirms_AMFI_arg_and_missing_allow3d': True,
                  'policy_applied_to_failed_installed_boot': 'not independently verified',
                  'no_system_restore_or_KC_rebuild': True}
        (ROOT / 'reports/FIRSTBOOT-STALL.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({k: report[k] for k in report if k != 'image_inventory'}, indent=2))
    finally:
        remote.run('firstboot-stall-oc-image-unmount', '/sbin/umount ' + shlex.quote(mount), timeout=45)
        remote.run('firstboot-stall-oc-image-detach', '/usr/bin/hdiutil detach ' + shlex.quote(device), timeout=45)


if __name__ == '__main__':
    main()
