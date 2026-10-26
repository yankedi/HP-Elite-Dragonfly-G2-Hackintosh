#!/usr/bin/env python3
"""Copy a new observer image to verified USB and native-readback it, without boot."""
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import sys

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga415/private/blit-observer'
REPORTS = ROOT / 'ga415/reports'
BASE = '/private/tmp/ga415-blit-observer-delivery'
SPEC = importlib.util.spec_from_file_location('ga414_common', ROOT / 'ga414/tools/common.py')
c = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(c)
sys.path.insert(0, str(ROOT / 'ga410/tools'))
import normal_ssh
import remote


def main():
    normal_ssh.configure(); remote.ROOT = ROOT / 'ga415'
    if not os.environ.get('GA410_SUDO_PASSWORD'):
        raise SystemExit('Set GA410_SUDO_PASSWORD in the caller environment')
    local = json.loads((REPORTS / 'BLIT-OBSERVER-IMAGE.json').read_text())
    image = ROOT / local['image']['path']; digest = local['image']['sha256']
    assert c.sha(image) == digest
    dest = '/Volumes/TARGET_VOLUME/ISO/linux/' + local['name']
    remote.run('blitobs-delivery-work', f'set -eu\numask 077\nmkdir {BASE}', timeout=15)
    remote.upload(ROOT / 'ga414/tools/delivery-snapshot-remote.py', BASE + '/snapshot.py')
    before = json.loads(remote.run('blitobs-protected-before', '/usr/bin/python3 ' + BASE + '/snapshot.py', timeout=240)['stdout'])
    assert before['USB_volume_UUID'] == 'REDACTED-SESSION-ID'
    assert before['boot_session'] == 'REDACTED-SESSION-ID'
    old_paths = ['/Volumes/TARGET_VOLUME/ISO/linux/HP-Tahoe-TGL-GA414-NOAUX.img', '/Volumes/TARGET_VOLUME/ISO/linux/HP-Tahoe-TGL-GA415-PLANES2.img']
    hash_command = '/usr/bin/shasum -a 256 ' + ' '.join(map(shlex.quote, old_paths))
    old_hashes = remote.run('blitobs-new-dest-and-old-images', 'set -eu\ntest ! -e ' + shlex.quote(dest) + '\ntest ! -e ' + shlex.quote(dest + '.sha256') + '\n' + hash_command, timeout=200)['stdout']
    remote.upload(image, dest, timeout=420)
    result = remote.run('blitobs-transfer-sync-hash', '/bin/sync\n/usr/bin/shasum -a 256 ' + shlex.quote(dest), timeout=180)
    assert result['stdout'].strip() == digest + '  ' + dest
    attach = remote.run('blitobs-attach-readonly', '/usr/bin/hdiutil attach -readonly -nomount -imagekey diskimage-class=CRawDiskImage -plist ' + shlex.quote(dest), timeout=45)
    entities = plistlib.loads(attach['stdout'].encode())['system-entities']
    device = next(x['dev-entry'] for x in entities if x.get('content-hint') == 'FDisk_partition_scheme')
    partition = next(x['dev-entry'] for x in entities if x.get('content-hint') == '0xEF')
    assert re.fullmatch(r'/dev/disk\d+', device) and partition == device + 's1'
    assert device != '/dev/' + re.sub(r's\d+$', '', before['USB_device'])
    mount = BASE + '/readonly'; mounted = False
    try:
        result = remote.run('blitobs-mount-readonly', 'set -eu\nmkdir ' + mount + '\n/sbin/mount_msdos -o rdonly ' + partition + ' ' + mount + '\n/sbin/mount', sudo=True, timeout=30)
        mounted = True
        assert any(line.startswith(partition + ' on ' + mount + ' ') and 'read-only' in line for line in result['stdout'].splitlines())
        result = remote.run('blitobs-full-native-inventory', '/usr/bin/find ' + mount + ' -type f -exec /usr/bin/shasum -a 256 {} \\;', timeout=120)
        actual = {}
        for line in result['stdout'].splitlines():
            value, path = line.split('  ', 1); assert path.startswith(mount + '/')
            actual[path[len(mount) + 1:]] = value
        assert actual == local['full_image_inventory']
        result = remote.run('blitobs-native-signature-config', f'''set -eu
/usr/bin/codesign --verify --strict --deep --verbose=4 {mount}/EFI/OC/Kexts/NootedGreen.kext
/usr/bin/codesign --display --verbose=4 {mount}/EFI/OC/Kexts/NootedGreen.kext
/usr/bin/dwarfdump --uuid {mount}/EFI/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen
/usr/bin/plutil -lint {mount}/EFI/OC/config.plist
''', timeout=30)
        assert local['NG_UUID'] in result['stdout'] and 'Signature=adhoc' in result['stderr']
        config = WORK / 'native-readback-config.plist'; remote.download(mount + '/EFI/OC/config.plist', config)
        assert config.read_bytes() == (WORK / 'BLITOBS-config.plist').read_bytes()
    finally:
        if mounted: remote.run('blitobs-unmount', '/sbin/umount ' + mount, sudo=True, timeout=30)
        remote.run('blitobs-detach', '/usr/bin/hdiutil detach ' + device, timeout=30)
    result = remote.run('blitobs-final-image-hashes', '/bin/sync\n/usr/bin/shasum -a 256 ' + shlex.quote(dest) + '\n' + hash_command, timeout=240)
    assert result['stdout'] == digest + '  ' + dest + '\n' + old_hashes
    after = json.loads(remote.run('blitobs-protected-after', '/usr/bin/python3 ' + BASE + '/snapshot.py', timeout=240)['stdout'])
    for key in ['protected_images', 'installed_files', 'boot_session', 'USB_volume_UUID']:
        assert after[key] == before[key], key
    remote.upload(REPORTS / (local['name'] + '.sha256'), dest + '.sha256')
    remote.run('blitobs-sidecar-sync', '/bin/sync', timeout=30)
    report = {'status': 'BLIT_OBSERVER_IMAGE_DELIVERED_BOOT_NOT_TESTED', 'USB_image': dest,
              'image': local['image'], 'NG_UUID': local['NG_UUID'], 'file_count': len(actual),
              'native_readonly_full_inventory_verified': True, 'native_codesign_strict_deep_verified': True,
              'native_config_exact': True, 'changed_files_vs_PLANES2': local['changed_files_vs_PLANES2'],
              'boot_args': local['boot_args_after'], 'all_six_prior_images_and_installed_stack_preserved': True,
              'old_boot_session': before['boot_session'], 'final_boot_session': after['boot_session'],
              'USB_volume_UUID': before['USB_volume_UUID'], 'observer_runtime': 'NOT_OBSERVED',
              'internal_EFI_changed': False, 'automatic_reboot': False, 'GPU_submitted': False,
              'next_step': 'User boots new image manually; verify identity and observer installation first. Fresh single-case GPU authorization still required.'}
    c.save(REPORTS / 'BLIT-OBSERVER-DELIVERY.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
