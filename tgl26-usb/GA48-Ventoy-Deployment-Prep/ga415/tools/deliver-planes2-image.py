#!/usr/bin/env python3
"""Deliver a new Ventoy image and verify native readonly contents; no boot/install."""
import importlib.util
import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import sys

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga415/private/planesfix'
REPORTS = ROOT / 'ga415/reports'
sys.path.insert(0, str(ROOT / 'ga410/tools'))
import normal_ssh
import remote


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-after-baseline-drift-review', action='store_true')
    options = parser.parse_args()
    normal_ssh.configure(); remote.ROOT = ROOT / 'ga415'
    if not os.environ.get('GA410_SUDO_PASSWORD'):
        raise SystemExit('Set GA410_SUDO_PASSWORD in the caller environment')
    spec = importlib.util.spec_from_file_location('artifact_helpers', ROOT / 'ga414/tools/common.py')
    c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
    local = json.loads((REPORTS / 'PLANES2-IMAGE.json').read_text())
    image = ROOT / local['image']['path']; digest = local['image']['sha256']
    assert c.sha(image) == digest
    dest = '/Volumes/TARGET_VOLUME/ISO/linux/' + local['name']
    base = '/private/tmp/ga415-planes2-delivery'
    if options.resume_after_baseline_drift_review:
        assert not (ROOT / 'ga415/private/commands' / ('upload-' + local['name'] + '.json')).exists()
        receipt = json.loads((ROOT / 'ga415/private/commands/planesfix-protected-before.json').read_text())
        assert receipt['returncode'] == 0
        before = json.loads(receipt['stdout'])
    else:
        remote.run('planesfix-new-delivery-work', 'umask 077\nmkdir ' + base, timeout=15)
        remote.upload(ROOT / 'ga414/tools/delivery-snapshot-remote.py', base + '/snapshot.py')
        before = json.loads(remote.run('planesfix-protected-before', '/usr/bin/python3 ' + base + '/snapshot.py', timeout=240)['stdout'])
    assert before['USB_volume_UUID'] == 'REDACTED-SESSION-ID'
    assert before['boot_session'] == 'REDACTED-SESSION-ID'
    baseline_remote = '/Volumes/TARGET_VOLUME/ISO/linux/HP-Tahoe-TGL-GA414-NOAUX.img'
    prior_sha = local['baseline_GA414']['sha256']
    baseline_drift = None
    if options.resume_after_baseline_drift_review:
        receipt = json.loads((ROOT / 'ga415/private/commands/planesfix-old-image-drift-readonly.json').read_text())
        assert receipt['returncode'] == 0
        drift = json.loads(receipt['stdout'])
        known = json.loads((ROOT / 'ga414/reports/IMAGE-LOCAL.json').read_text())['full_image_inventory']
        actual_old = {p: r['sha256'] for p, r in drift['files'].items()}
        assert all(actual_old.get(p) == value for p, value in known.items())
        added = sorted(actual_old.keys() - known.keys())
        assert added and all(re.fullmatch(r'opencore-[0-9-]+\.txt', p) for p in added)
        receipt = json.loads((ROOT / 'ga415/private/commands/planesfix-old-image-hash-and-destination-absent.json').read_text())
        assert receipt['returncode'] == 0
        prior_sha = receipt['stdout'].strip().split('  ', 1)[0]
        assert re.fullmatch('[0-9a-f]{64}', prior_sha)
        baseline_drift = dict(explanation='Old image acquired OpenCore boot log; all 100 original files byte-identical',
                              added_files=added, observed_USB_sha256=prior_sha,
                              preserved_archival_baseline_sha256=local['baseline_GA414']['sha256'])
        session = remote.run('planesfix-resume-fresh-session', '/usr/sbin/sysctl -n kern.bootsessionuuid', timeout=15)
        assert session['stdout'].strip() == before['boot_session']
    check = remote.run('planesfix-reviewed-baseline-and-new-destination' if options.resume_after_baseline_drift_review else 'planesfix-old-image-hash-and-destination-absent',
                       'set -eu\ntest ! -e ' + shlex.quote(dest) + '\ntest ! -e ' + shlex.quote(dest + '.sha256') +
                       '\n/usr/bin/shasum -a 256 ' + shlex.quote(baseline_remote), timeout=120)
    assert check['stdout'].strip() == prior_sha + '  ' + baseline_remote
    remote.upload(image, dest, timeout=420)
    row = remote.run('planesfix-transfer-sync-hash', '/bin/sync\n/usr/bin/shasum -a 256 ' + shlex.quote(dest), timeout=160)
    assert row['stdout'].strip() == digest + '  ' + dest
    attach = remote.run('planesfix-native-attach-readonly',
                        '/usr/bin/hdiutil attach -readonly -nomount -imagekey diskimage-class=CRawDiskImage -plist ' + shlex.quote(dest), timeout=45)
    entities = plistlib.loads(attach['stdout'].encode())['system-entities']
    device = next(x['dev-entry'] for x in entities if x.get('content-hint') == 'FDisk_partition_scheme')
    partition = next(x['dev-entry'] for x in entities if x.get('content-hint') == '0xEF')
    assert re.fullmatch(r'/dev/disk\d+', device) and partition == device + 's1'
    assert device != '/dev/' + re.sub(r's\d+$', '', before['USB_device'])
    mount = base + '/readonly'; mounted = False
    try:
        row = remote.run('planesfix-native-mount-readonly',
                         'set -eu\nmkdir ' + mount + '\n/sbin/mount_msdos -o rdonly ' + partition + ' ' + mount + '\n/sbin/mount',
                         sudo=True, timeout=30)
        mounted = True
        assert any(line.startswith(partition + ' on ' + mount + ' ') and 'read-only' in line for line in row['stdout'].splitlines())
        row = remote.run('planesfix-native-full-inventory',
                         '/usr/bin/find ' + mount + ' -type f -exec /usr/bin/shasum -a 256 {} \\;', timeout=120)
        actual = {}
        for line in row['stdout'].splitlines():
            value, path = line.split('  ', 1); assert path.startswith(mount + '/')
            actual[path[len(mount) + 1:]] = value
        assert actual == local['full_image_inventory']
        row = remote.run('planesfix-native-signature-and-config', '''set -eu
/usr/bin/codesign --verify --strict --deep --verbose=4 MOUNT/EFI/OC/Kexts/NootedGreen.kext
/usr/bin/codesign --display --verbose=4 MOUNT/EFI/OC/Kexts/NootedGreen.kext
/usr/bin/dwarfdump --uuid MOUNT/EFI/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen
/usr/bin/plutil -lint MOUNT/EFI/OC/config.plist
'''.replace('MOUNT', mount), timeout=30)
        assert local['NG_UUID'] in row['stdout'] and 'Signature=adhoc' in row['stderr']
        config = WORK / 'native-config.plist'; remote.download(mount + '/EFI/OC/config.plist', config)
        assert config.read_bytes() == (WORK / 'PLANES2-config.plist').read_bytes()
    finally:
        if mounted: remote.run('planesfix-native-unmount', '/sbin/umount ' + mount, sudo=True, timeout=30)
        remote.run('planesfix-native-detach', '/usr/bin/hdiutil detach ' + device, timeout=30)
    row = remote.run('planesfix-final-sync-and-image-hashes', '/bin/sync\n/usr/bin/shasum -a 256 ' + shlex.quote(dest) + ' ' + shlex.quote(baseline_remote), timeout=180)
    assert row['stdout'].splitlines() == [digest + '  ' + dest, prior_sha + '  ' + baseline_remote]
    after = json.loads(remote.run('planesfix-protected-after', '/usr/bin/python3 ' + base + '/snapshot.py', timeout=240)['stdout'])
    for key in ('protected_images', 'installed_files', 'boot_session', 'USB_volume_UUID'):
        assert before[key] == after[key], key
    remote.upload(REPORTS / (local['name'] + '.sha256'), dest + '.sha256')
    remote.run('planesfix-sidecar-sync', '/bin/sync', timeout=30)
    report = dict(status='PLANES2_IMAGE_DELIVERED_BOOT_NOT_TESTED', USB_image=dest,
                  image=local['image'], baseline_GA414=local['baseline_GA414'], NG_UUID=local['NG_UUID'],
                  native_readonly_full_inventory_verified=True, file_count=len(actual),
                  native_codesign_strict_deep_verified=True, native_config_exact=True,
                  changed_files_vs_GA414=local['changed_files_vs_GA414'],
                  boot_args=local['boot_args_after'], NVRAM_boot_args_override_from_image_verified=True,
                  original_images_and_installed_stack_KC_preserved=True, internal_EFI_changed=False,
                  old_boot_session=before['boot_session'], final_boot_session=after['boot_session'],
                  USB_volume_UUID=before['USB_volume_UUID'],
                  old_USB_GA414_drift_review=baseline_drift,
                  runtime_PLANES2_applied='NOT_OBSERVED', panic_retest='NOT_RUN',
                  automatic_reboot=False, GPU_test_submitted=False,
                  required_next_step='User physically boots this image; verify GA414 UUID, PLANES2 applied, NOAUX applied and boot arguments before any retest.')
    with (REPORTS / 'PLANES2-DELIVERY.json').open('x') as f: json.dump(report, f, indent=2); f.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
