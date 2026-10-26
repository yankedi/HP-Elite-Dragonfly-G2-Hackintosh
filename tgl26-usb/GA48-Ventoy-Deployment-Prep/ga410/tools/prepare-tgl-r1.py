#!/usr/bin/env python3
"""Single-delta R1 image, native readback, and preserved/rearmed boot capture."""
import hashlib
import json
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import tarfile

import recovery_ssh
import remote

ROOT = remote.ROOT
REPO = ROOT.parent
BASE = '/tmp/ga410-firstboot-stall'
HASHER = '/Volumes/TARGET_VOLUME/GA410-FirstBoot-20261023/recovery-sha256'
NAME = 'HP-Tahoe-TGL-GA410-R1-3D.img'
# NVRAM analysis found an additional, precisely matched FB panic after the
# parameter candidate was built. Future reproductions remain hidden from Ventoy.
DEST = '/Volumes/TARGET_VOLUME/ISO/linux/' + NAME + '.HOLD-FB-PANIC'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(args):
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError((args, result.returncode, result.stdout, result.stderr))
    return result.stdout + result.stderr


def main():
    recovery_ssh.configure()
    work = ROOT / 'private/tgl-r1'
    work.mkdir()
    original = ROOT / 'private/firstboot-images/HP-Tahoe-TGL-GA410-CSR203-AMFI.img'
    assert sha(original) == '60c1ec00070e11823f2abb4fd1050764ed338c9a90a38388723d3d2612b02370'
    image = work / NAME
    shutil.copyfile(original, image)
    config = plistlib.loads((ROOT / 'private/firstboot-images/tgl/EFI/OC/config.plist').read_bytes())
    before = config['NVRAM']['Add']['REDACTED-MACHINE-ID']['boot-args']
    args = before + ' -allow3d -disablegfxfirmware'
    assert len(args.encode()) < 228 and '-igfxvesa' not in args
    config['NVRAM']['Add']['REDACTED-MACHINE-ID']['boot-args'] = args
    path = work / 'config.plist'
    path.write_bytes(plistlib.dumps(config, sort_keys=False))
    validation = run([REPO / 'out/ocvalidate', path])
    run(['mcopy', '-o', '-i', str(image) + '@@1048576', path, '::/EFI/OC/config.plist'])
    note = ROOT / 'reports/BOOT-IN-TGL-R1.txt'
    run(['mcopy', '-o', '-i', str(image) + '@@1048576', note, '::/FIRST-BOOT.txt'])
    readback = work / 'readback'
    readback.mkdir()
    run(['mcopy', '-s', '-i', str(image) + '@@1048576', '::/EFI', readback])
    expected = dict(json.loads((ROOT / 'reports/FINALPREP-IMAGES.json').read_text())['images'][0]['efi_inventory'])
    expected['OC/config.plist'] = sha(path)
    actual = {str(p.relative_to(readback / 'EFI')): sha(p) for p in (readback / 'EFI').rglob('*') if p.is_file()}
    assert expected == actual
    remote.upload(image, DEST, timeout=360)
    r = remote.run('firstboot-r1-delivered-full-sha256', HASHER + ' ' + shlex.quote(DEST), timeout=150)
    assert r['stdout'].startswith(sha(image) + '  ')
    r = remote.run('firstboot-r1-native-attach', '/usr/bin/hdiutil attach -readonly -nomount -imagekey diskimage-class=CRawDiskImage -plist ' + shlex.quote(DEST), timeout=60)
    entities = plistlib.loads(r['stdout'].encode())['system-entities']
    device = next(e['dev-entry'] for e in entities if e.get('content-hint') == 'FDisk_partition_scheme')
    part = next(e['dev-entry'] for e in entities if e.get('content-hint') == '0xEF')
    mount = BASE + '/r1-native-readonly'
    remote.run('firstboot-r1-native-mount', 'set -eu; /bin/mkdir ' + shlex.quote(mount) + '; /sbin/mount_msdos -o rdonly ' + shlex.quote(part) + ' ' + shlex.quote(mount), timeout=45)
    try:
        r = remote.run('firstboot-r1-native-inventory', '/usr/bin/find ' + shlex.quote(mount) + ' -type f -exec ' + HASHER + ' {} \\;', timeout=180)
        inventory = {}
        for line in r['stdout'].splitlines():
            digest, name = line.split('  ', 1)
            assert name.startswith(mount + '/')
            inventory[name[len(mount) + 1:]] = digest
        all_expected = {'EFI/' + k: v for k, v in expected.items()}
        all_expected.update(json.loads((ROOT / 'reports/FINALPREP-DELIVERY.json').read_text())['images'][0]['non_EFI_payloads'])
        all_expected['FIRST-BOOT.txt'] = sha(note)
        assert inventory == all_expected
        remote.run('firstboot-r1-native-config-lint', '/usr/bin/plutil -lint ' + shlex.quote(mount + '/EFI/OC/config.plist'), timeout=30)
        remote.download(mount + '/EFI/OC/config.plist', work / 'native-config-readback.plist', timeout=30)
        assert (work / 'native-config-readback.plist').read_bytes() == path.read_bytes()
    finally:
        remote.run('firstboot-r1-native-unmount', '/sbin/umount ' + shlex.quote(mount), timeout=45)
        remote.run('firstboot-r1-native-detach', '/usr/bin/hdiutil detach ' + shlex.quote(device), timeout=45)
    remote.upload(ROOT / 'tools/collect-firstboot.sh', BASE + '/collect-firstboot-r1.sh', timeout=30)
    old_collector = sha(ROOT / 'private/firstboot-handoff/sources/collect-firstboot.sh')
    old_marker = 'ga410-firstboot-once.failed-91FA7AAF-AE29-486E-BEE5-7F946FF512B9'
    data = '/Volumes/TARGET_DATA_VOLUME'
    installed = data + '/Library/Application Support/GA410/collect-firstboot.sh'
    commands = ['set -eu', '/bin/bash -n ' + BASE + '/collect-firstboot-r1.sh',
                'value=$(' + HASHER + ' ' + shlex.quote(installed) + ')',
                '[ "${value%% *}" = ' + old_collector + ' ]',
                '/bin/cp ' + shlex.quote(installed) + ' ' + shlex.quote(installed + '.before-r1'),
                '/bin/cat ' + BASE + '/collect-firstboot-r1.sh > ' + shlex.quote(installed + '.new'),
                '/usr/sbin/chown root:wheel ' + shlex.quote(installed + '.new'),
                '/bin/chmod 755 ' + shlex.quote(installed + '.new'),
                '/bin/mv ' + shlex.quote(installed + '.new') + ' ' + shlex.quote(installed),
                '/bin/bash ' + shlex.quote(installed) + ' --check',
                '/bin/test ! -e ' + shlex.quote(data + '/private/var/db/' + old_marker),
                '/bin/mv ' + shlex.quote(data + '/private/var/db/ga410-firstboot-once') + ' ' + shlex.quote(data + '/private/var/db/' + old_marker),
                '/bin/test ! -e ' + shlex.quote(data + '/private/var/db/ga410-firstboot-once'), '/bin/sync']
    remote.run('firstboot-r1-preserve-and-rearm-capture', '; '.join(commands), timeout=60)
    remote.run('firstboot-r1-components-and-kc-verify', '/bin/bash /Volumes/TARGET_VOLUME/GA410-FirstBoot-20261023/restore-firstboot-recovery.sh --verify', timeout=180)
    r = remote.run('firstboot-r1-final-image-sha256', HASHER + ' ' + shlex.quote(DEST), timeout=150)
    assert r['stdout'].startswith(sha(image) + '  ')
    report = {'status': 'R1_HELD_NOT_CLEARED_FOR_BOOT', 'name': NAME, 'destination': DEST,
              'cleared_for_physical_boot': False,
              'known_remaining_panic': 'probePortState+0x207 __cxa_pure_virtual; upstream f13b disabled',
              'sha256': sha(image), 'bytes': image.stat().st_size,
              'boot_args_before': before, 'boot_args_after': args, 'boot_args_bytes': len(args.encode()),
              'only_config_change': 'append -allow3d -disablegfxfirmware',
              'ocvalidate_rc': 0, 'ocvalidate_output': validation,
              'mtools_full_EFI_readback_matches': True, 'native_full_image_sha256_matches': True,
              'native_all_files_inventory_matches': True, 'native_config_readback_exact': True,
              'config_sha256': sha(path), 'image_inventory': inventory,
              'collector_rearmed_without_deleting_prior_outputs': True,
              'previous_marker_saved_as': '/private/var/db/' + old_marker,
              'capture_progress_markers_added': True, 'capture_kernel_args_prioritized': True,
              'components_204_and_backup_22_reverified': True,
              'KC_rebuilt_or_republished': False, 'driver_source_or_binary_changed': False,
              'physical_boot_performed': False, 'fix_proven_at_runtime': False,
              'machine_left_powered_on_with_Recovery_SSH': True}
    (ROOT / 'reports/TGL-R1.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ['image_inventory', 'ocvalidate_output']}, indent=2))


if __name__ == '__main__':
    main()
