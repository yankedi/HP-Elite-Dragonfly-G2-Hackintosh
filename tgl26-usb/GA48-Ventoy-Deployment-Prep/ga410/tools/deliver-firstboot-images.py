#!/usr/bin/env python3
"""Deliver and independently mount both new images in real Recovery, read-only."""
import json
from pathlib import Path
import plistlib
import shlex

import recovery_ssh
import remote

ROOT = remote.ROOT
WORK = '/tmp/ga410-firstboot-prep'
HASHER = '/tmp/ga410-policy-prep/recovery-sha256'


def mounted_inventory(label, image, signed=False, kind=None):
    row = remote.run('recovery2222-finalprep-attach-' + label,
                     '/usr/bin/hdiutil attach -readonly -nomount -imagekey diskimage-class=CRawDiskImage -plist ' + shlex.quote(image), timeout=60)
    entities = plistlib.loads(row['stdout'].encode())['system-entities']
    device = next(e['dev-entry'] for e in entities if e.get('content-hint') == 'FDisk_partition_scheme')
    partition = next(e['dev-entry'] for e in entities if e.get('content-hint') == '0xEF')
    assert partition.startswith(device + 's')
    mount = WORK + '/verify-' + label
    remote.run('recovery2222-finalprep-mount-' + label,
               'set -eu; /bin/mkdir ' + shlex.quote(mount) + '; /sbin/mount_msdos -o rdonly ' + shlex.quote(partition) + ' ' + shlex.quote(mount), timeout=45)
    try:
        row = remote.run('recovery2222-finalprep-inventory-' + label,
                         '/usr/bin/find ' + shlex.quote(mount) + ' -type f -exec ' + HASHER + ' {} \\;', timeout=240)
        inventory = {}
        for line in row['stdout'].splitlines():
            digest, path = line.split('  ', 1)
            assert path.startswith(mount + '/') and len(digest) == 64
            inventory[path[len(mount) + 1:]] = digest
        assert inventory
        if label != 'source':
            remote.run('recovery2222-finalprep-native-plist-' + label,
                       '/usr/bin/plutil -lint ' + shlex.quote(mount + '/EFI/OC/config.plist'), timeout=30)
            local = ROOT / ('private/config-firstboot-' + label + '-readback.plist')
            remote.download(mount + '/EFI/OC/config.plist', local, timeout=30)
            staged = ROOT / ('private/firstboot-images/' + (kind or label) + '/EFI/OC/config.plist')
            assert local.read_bytes() == staged.read_bytes()
        if signed:
            for name in ['Lilu', 'NootedGreen']:
                remote.run('recovery2222-finalprep-native-signature-' + name.lower(),
                           '/usr/bin/codesign --verify --strict --deep --verbose=4 ' + shlex.quote(mount + '/EFI/OC/Kexts/' + name + '.kext'), timeout=45)
        return inventory
    finally:
        remote.run('recovery2222-finalprep-unmount-' + label, '/sbin/umount ' + shlex.quote(mount), timeout=45)
        remote.run('recovery2222-finalprep-detach-' + label, '/usr/bin/hdiutil detach ' + shlex.quote(device), timeout=45)


def main():
    recovery_ssh.configure()
    report = json.loads((ROOT / 'reports/FINALPREP-IMAGES.json').read_text())
    source = mounted_inventory('source', '/Volumes/TARGET_VOLUME/ISO/linux/HP-Tahoe-TGL-GA48.img')
    non_efi = {k: v for k, v in source.items() if not k.startswith('EFI/')}
    assert any(k.endswith('BaseSystem.dmg') for k in non_efi)
    delivered = []
    for image in report['images']:
        destination = '/Volumes/TARGET_VOLUME/ISO/linux/' + image['name']
        remote.upload(ROOT.parent / image['local_image'], destination, timeout=360)
        row = remote.run('recovery2222-finalprep-image-sha-' + image['kind'],
                         HASHER + ' ' + shlex.quote(destination), timeout=150)
        assert row['stdout'].split('  ', 1)[0] == image['sha256']
        inventory = mounted_inventory(image['kind'], destination, image['kind'] == 'tgl')
        expected_non_efi = dict(non_efi, **{'FIRST-BOOT.txt': image['first_boot_note_sha256']})
        assert {k: v for k, v in inventory.items() if not k.startswith('EFI/')} == expected_non_efi
        assert {k.removeprefix('EFI/'): v for k, v in inventory.items() if k.startswith('EFI/')} == image['efi_inventory']
        row = remote.run('recovery2222-finalprep-image-sha-after-' + image['kind'],
                         HASHER + ' ' + shlex.quote(destination), timeout=150)
        assert row['stdout'].split('  ', 1)[0] == image['sha256']
        delivered.append({'name': image['name'], 'destination': destination,
                          'sha256': image['sha256'], 'bytes': image['bytes'],
                          'native_full_inventory_matches': True,
                          'non_EFI_payloads': expected_non_efi,
                          'intentional_non_EFI_change': 'FIRST-BOOT.txt updated for actual image role',
                          'native_mount_read_only': True, 'detached_after_verification': True,
                          'native_config_readback_exact': True})
    row = remote.run('recovery2222-finalprep-originals-sha-after',
                     HASHER + ' /Volumes/TARGET_VOLUME/ISO/linux/HP-Tahoe-TGL-GA48.img /Volumes/TARGET_VOLUME/ISO/linux/HP-Tahoe-VESA-XHCI-RHUB.img', timeout=180)
    lines = row['stdout'].splitlines()
    assert lines[0].startswith('0facaf8ec3767c0235f326ad782cb7c000e881aca8274345cde2f3f235a693e4  ')
    assert lines[1].startswith('5f8c7b8257d16a7039daa42bc9e832b734f731dcc965045cde4e90aef1bbb7f9  ')
    receipt = {'status': 'DELIVERED_NATIVE_READONLY_VERIFIED_NOT_BOOTED', 'images': delivered,
               'original_images_unchanged_in_this_session': True,
               'physical_boot_performed': False, 'NVRAM_written_by_this_tool': False}
    (ROOT / 'reports/FINALPREP-DELIVERY.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
