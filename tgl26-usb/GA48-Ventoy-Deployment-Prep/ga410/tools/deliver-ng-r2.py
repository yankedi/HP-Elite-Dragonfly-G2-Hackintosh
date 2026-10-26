#!/usr/bin/env python3
"""Native-sign rebuilt NG, publish separate experiment IMG, verify native readback."""
import hashlib
import json
from pathlib import Path
import plistlib
import shlex
import shutil
import struct
import subprocess
import tarfile
import uuid

import recovery_ssh
import remote

ROOT = remote.ROOT
REPO = ROOT.parent
HASHER = '/Volumes/TARGET_VOLUME/GA410-FirstBoot-20261023/recovery-sha256'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(args):
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError((args, result.returncode, result.stdout, result.stderr))
    return result.stdout + result.stderr


def macho(data):
    assert data[:4] == bytes.fromhex('cffaedfe')
    assert struct.unpack_from('<I', data, 4)[0] == 0x01000007
    cursor, section_hashes, identifier = 32, {}, None
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        cmd, size = struct.unpack_from('<II', data, cursor)
        if cmd == 0x1b:
            identifier = str(uuid.UUID(bytes=data[cursor + 8:cursor + 24])).upper()
        if cmd == 0x19:
            segment = data[cursor + 8:cursor + 24].rstrip(b'\0').decode()
            for i in range(struct.unpack_from('<I', data, cursor + 64)[0]):
                p = cursor + 72 + 80 * i
                section = data[p:p + 16].rstrip(b'\0').decode()
                _, length, offset = struct.unpack_from('<QQI', data, p + 32)
                flags = struct.unpack_from('<I', data, p + 64)[0]
                if flags & 0xff not in [1, 0xc, 0x12]:
                    section_hashes[segment + ',' + section] = hashlib.sha256(data[offset:offset + length]).hexdigest()
        cursor += size
    assert identifier and section_hashes
    return {'uuid': identifier, 'section_sha256': section_hashes}


def main(version=2):
    assert version in (2, 3, 4)
    tag = f'R{version}'
    work = ROOT / f'private/ng-r{version}'
    BASE = f'/tmp/ga410-r{version}'
    NAME = f'HP-Tahoe-TGL-GA410-{tag}-' + {2: 'F13B', 3: 'BLIT-ALIGN', 4: 'CCS'}[version] + '.img'
    DEST = '/Volumes/TARGET_VOLUME/ISO/linux/' + NAME
    TARGET_WORK = f'/Volumes/TARGET_DATA_VOLUME/Users/Shared/GA410-work-20261023-0820/ng-r{version}'
    cross_name = f'NootedGreen-{tag}-crossbuild.tar.gz'
    signed_name = f'NootedGreen-{tag}-native-signed.tar.gz'

    def record(label, *args, **kwargs):
        assert label.startswith('r2-')
        return remote.run(f'r{version}-' + label[3:], *args, **kwargs)

    recovery_ssh.configure()
    build = json.loads((ROOT / f'reports/NG-{tag}-BUILD.json').read_text())
    archive = REPO / build['archive']
    assert sha(archive) == build['archive_sha256']
    before_binary = work / 'build/product/NootedGreen.kext/Contents/MacOS/NootedGreen'
    sections = macho(before_binary.read_bytes())
    record('r2-create-native-signing-work', 'set -eu; /bin/mkdir ' + BASE + '; /bin/mkdir ' + shlex.quote(TARGET_WORK), timeout=30)
    remote.upload(archive, BASE + '/' + cross_name, timeout=90)
    command = ('set -eu; value=$(' + HASHER + ' ' + BASE + '/' + cross_name + '); '
               '[ "${value%% *}" = ' + sha(archive) + ' ]; '
               '/usr/bin/tar -xpf ' + BASE + '/' + cross_name + ' -C ' + shlex.quote(TARGET_WORK) + '; '
               '/usr/bin/codesign --force --sign - --timestamp=none ' + shlex.quote(TARGET_WORK + '/NootedGreen.kext') + '; '
               '/usr/bin/codesign --verify --strict --deep --verbose=4 ' + shlex.quote(TARGET_WORK + '/NootedGreen.kext') + '; '
               '/usr/bin/codesign --display --verbose=4 ' + shlex.quote(TARGET_WORK + '/NootedGreen.kext') + '; '
               '/usr/bin/tar -czpf ' + BASE + '/' + signed_name + ' -C ' + shlex.quote(TARGET_WORK) + ' NootedGreen.kext; '
               + HASHER + ' ' + BASE + '/' + signed_name)
    native_sign = record('r2-native-sign-and-strict-verify', command, timeout=120)
    assert 'Signature=adhoc' in native_sign['stderr'] + native_sign['stdout']
    signed_archive = work / signed_name
    remote.download(BASE + '/' + signed_name, signed_archive, timeout=90)
    assert sha(signed_archive) in native_sign['stdout']
    signed_root = work / 'native-signed'
    signed_root.mkdir()
    with tarfile.open(signed_archive) as tar:
        for member in tar.getmembers():
            p = Path(member.name)
            assert not p.is_absolute() and '..' not in p.parts
            if member.isfile() and not any(part.startswith('._') for part in p.parts):
                dest = signed_root / p
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(tar.extractfile(member).read())
    signed_bundle = signed_root / 'NootedGreen.kext'
    signed_binary = signed_bundle / 'Contents/MacOS/NootedGreen'
    assert macho(signed_binary.read_bytes()) == sections, 'Native signing changed executable sections or UUID'
    local = work / NAME
    if version == 2:
        source = ROOT / 'private/tgl-r1/HP-Tahoe-TGL-GA410-R1-3D.img'
        assert sha(source) == '388db904f8af3cf911a99438e8789548e33cd38124142a34f51889a8f7bc9eae'
    elif version == 3:
        source = ROOT / 'private/ng-r2/HP-Tahoe-TGL-GA410-R2-F13B.img'
        assert sha(source) == json.loads((ROOT / 'reports/TGL-R2.json').read_text())['sha256']
    else:
        source = ROOT / 'private/ng-r3/HP-Tahoe-TGL-GA410-R3-BLIT-ALIGN.img'
        assert sha(source) == json.loads((ROOT / 'reports/TGL-R3.json').read_text())['sha256']
    shutil.copyfile(source, local)
    run(['mdeltree', '-i', str(local) + '@@1048576', '::/EFI/OC/Kexts/NootedGreen.kext'])
    run(['mcopy', '-s', '-i', str(local) + '@@1048576', signed_bundle, '::/EFI/OC/Kexts/'])
    note = ROOT / f'reports/BOOT-IN-TGL-{tag}.txt'
    run(['mcopy', '-o', '-i', str(local) + '@@1048576', note, '::/FIRST-BOOT.txt'])
    config_path = ROOT / 'private/tgl-r1/config.plist'
    config = plistlib.loads(config_path.read_bytes())
    args = config['NVRAM']['Add']['REDACTED-MACHINE-ID']['boot-args']
    assert '-allow3d' in args and '-disablegfxfirmware' in args and len(args.encode()) == 221
    validation = run([REPO / 'out/ocvalidate', config_path])
    expected = dict(json.loads((ROOT / f'reports/TGL-R{version - 1}.json').read_text())['image_inventory'])
    expected = {p: h for p, h in expected.items() if not p.startswith('EFI/OC/Kexts/NootedGreen.kext/')}
    for p in signed_bundle.rglob('*'):
        if p.is_file():
            expected['EFI/OC/Kexts/NootedGreen.kext/' + str(p.relative_to(signed_bundle))] = sha(p)
    expected['FIRST-BOOT.txt'] = sha(note)
    readback = work / 'mtools-readback'
    readback.mkdir()
    run(['mcopy', '-s', '-i', str(local) + '@@1048576', '::/EFI', readback])
    actual = {'EFI/' + str(p.relative_to(readback / 'EFI')): sha(p) for p in (readback / 'EFI').rglob('*') if p.is_file()}
    assert actual == {p: h for p, h in expected.items() if p.startswith('EFI/')}
    remote.upload(local, DEST, timeout=360)
    r = record('r2-native-full-image-hash-before-mount', HASHER + ' ' + shlex.quote(DEST), timeout=150)
    assert r['stdout'].startswith(sha(local) + '  ')
    r = record('r2-native-image-attach', '/usr/bin/hdiutil attach -readonly -nomount -imagekey diskimage-class=CRawDiskImage -plist ' + shlex.quote(DEST), timeout=60)
    entities = plistlib.loads(r['stdout'].encode())['system-entities']
    device = next(e['dev-entry'] for e in entities if e.get('content-hint') == 'FDisk_partition_scheme')
    part = next(e['dev-entry'] for e in entities if e.get('content-hint') == '0xEF')
    mount = BASE + '/image-readonly'
    record('r2-native-image-mount', 'set -eu; /bin/mkdir ' + mount + '; /sbin/mount_msdos -o rdonly ' + shlex.quote(part) + ' ' + mount, timeout=45)
    try:
        r = record('r2-native-full-image-file-inventory', '/usr/bin/find ' + mount + ' -type f -exec ' + HASHER + ' {} \\;', timeout=180)
        actual = {}
        for line in r['stdout'].splitlines():
            digest, name = line.split('  ', 1)
            assert name.startswith(mount + '/')
            actual[name[len(mount) + 1:]] = digest
        assert actual == expected
        record('r2-native-image-ng-signature-and-plist',
                   'set -eu; /usr/bin/codesign --verify --strict --deep --verbose=4 ' + mount + '/EFI/OC/Kexts/NootedGreen.kext; /usr/bin/plutil -lint ' + mount + '/EFI/OC/config.plist', timeout=60)
        config_readback = work / 'native-image-config.plist'
        remote.download(mount + '/EFI/OC/config.plist', config_readback, timeout=30)
        assert config_readback.read_bytes() == config_path.read_bytes()
    finally:
        record('r2-native-image-unmount', '/sbin/umount ' + mount, timeout=45)
        record('r2-native-image-detach', '/usr/bin/hdiutil detach ' + shlex.quote(device), timeout=45)
    helper = 'restore-firstboot-recovery-r3.sh' if version >= 4 else 'restore-firstboot-recovery.sh'
    record('r2-original-components-and-kc-verify', '/bin/bash /Volumes/TARGET_VOLUME/GA410-FirstBoot-20261023/' + helper + ' --verify', timeout=180)
    record('r2-final-image-and-ready-capture-state',
               'set -eu; ' + HASHER + ' ' + shlex.quote(DEST) + '; /bin/test ! -e "/Volumes/TARGET_DATA_VOLUME/private/var/db/ga410-firstboot-once"; /usr/sbin/sysctl -n kern.bootsessionuuid; /bin/sync', timeout=150)
    report = {'status': f'{tag}_DELIVERED_VERIFIED_READY_FOR_USER_TEST_BOOT', 'image': DEST,
              'name': NAME, 'sha256': sha(local), 'bytes': local.stat().st_size,
              'source_delta': build['functional_delta'],
              'new_NG_binary_sha256': sha(signed_binary), 'new_NG_uuid': sections['uuid'],
              'native_codesign_strict_deep_rc': 0, 'native_signature_type': 'adhoc experimental, not Apple trust',
              'signing_preserved_all_executable_sections_and_UUID': True,
              'ocvalidate_rc': 0, 'ocvalidate_output': validation,
              'boot_args': args, 'boot_args_bytes': len(args.encode()),
              'configuration_identical_to_R1': True, 'native_entire_file_inventory_matches': True,
              'native_config_readback_exact': True, 'mtools_entire_EFI_readback_matches': True,
              'installed_components_and_KC_unchanged_and_verified': True,
              'capture_marker_absent_and_ready': True, 'old_attempt_logs_preserved': True,
              'new_native_signed_NG_backup_on_Data': TARGET_WORK,
              'internal_EFI_changed': False, 'original_images_overwritten': False,
              'NVRAM_written': False, 'shutdown_or_reboot_executed': False,
              'physical_boot_performed': False, 'runtime_fix_verified': False,
              'image_inventory': expected}
    (ROOT / f'reports/TGL-{tag}.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ['image_inventory', 'ocvalidate_output']}, indent=2))


if __name__ == '__main__':
    main()
