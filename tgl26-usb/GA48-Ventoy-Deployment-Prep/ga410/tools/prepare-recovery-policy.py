#!/usr/bin/env python3
"""Prepare a separate VESA CSR3 image on the attached USB; never boot it here."""
import copy
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shlex
import subprocess
import sys

import recovery_ssh
import remote

ROOT = remote.ROOT
GUID = '7C436110-AB2A-4BBB-A880-FE41995C9F82'
SOURCE = '/Volumes/TARGET_VOLUME/ISO/linux/HP-Tahoe-VESA-XHCI-RHUB.img'
DEST = '/Volumes/TARGET_VOLUME/ISO/linux/HP-Tahoe-VESA-GA410-CSR3.img'
WORK = '/tmp/ga410-policy-prep'


def digest_stream(name, path):
    """Hash exact remote bytes locally, without writing a second huge image."""
    command = '/bin/cat ' + shlex.quote(path)
    process = subprocess.Popen(remote.SSH + [command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digest = hashlib.sha256()
    size = 0
    while chunk := process.stdout.read(1024 * 1024):
        digest.update(chunk)
        size += len(chunk)
    error = process.stderr.read().decode(errors='replace')
    rc = process.wait()
    row = {'command': command, 'returncode': rc, 'stderr': error, 'bytes': size, 'sha256': digest.hexdigest(), 'method': 'SHA256 of complete SSH byte stream on NixOS'}
    (ROOT / 'private/commands' / (name + '.json')).write_text(json.dumps(row, indent=2) + '\n')
    assert rc == 0 and size == 1343225856, row
    return row


def finish_candidate(path, device, md5):
    mount = WORK + '/candidate'
    inventories = []
    for label, base in [('source', WORK + '/source'), ('candidate', mount)]:
        name = 'recovery2222-files-md5-' + label
        command = '/usr/bin/find ' + base + ' -type f -exec /sbin/md5 {} \\;'
        log = ROOT / 'private/commands' / (name + '.json')
        if log.exists():
            row = json.loads(log.read_text())
            assert row['command'] == command and row['returncode'] == 0
        else:
            row = remote.run(name, command, timeout=180)
        matches = re.findall(r'^MD5 \((.*)\) = ([0-9a-f]{32})$', row['stdout'], re.M)
        assert len(matches) == len(row['stdout'].splitlines()) and matches
        inventories.append({name.removeprefix(base + '/'): value for name, value in matches})
    a, b = inventories
    assert a.keys() <= b.keys()
    extra_metadata = sorted(b.keys() - a.keys())
    assert all(name == '.fseventsd/fseventsd-uuid' for name in extra_metadata), extra_metadata
    assert [name for name in a if a[name] != b[name]] == ['EFI/OC/config.plist']
    remote.download(mount + '/EFI/OC/config.plist', ROOT / 'private/config-VESA-GA410-CSR3-readback.plist', timeout=30)
    assert path.read_bytes() == (ROOT / 'private/config-VESA-GA410-CSR3-readback.plist').read_bytes()
    remote.run('recovery2222-policy-unmount', '/sbin/umount ' + mount, timeout=45)
    remote.run('recovery2222-policy-detach', '/usr/bin/hdiutil detach ' + device, timeout=45)
    remote.run('recovery2222-source-unmount', '/sbin/umount ' + WORK + '/source', timeout=45)
    remote.run('recovery2222-source-detach', '/usr/bin/hdiutil detach /dev/disk5', timeout=45)
    final_md5 = remote.run('recovery2222-original-image-md5-after', '/sbin/md5 ' + SOURCE, timeout=90)['stdout'].strip()
    assert md5 == final_md5
    record = {'status': 'PREPARED_NOT_BOOTED_NOT_POLICY_APPLIED', 'image': DEST, 'source': SOURCE, 'csr_hex_le': '03000000', 'only_config_changes': ['Add csr-active-config: 00000000 -> 03000000', 'Delete: add csr-active-config so existing CSR0 cannot win'], 'WriteFlash': False, 'csr_persistence': 'Deletion can affect a persistent variable; new Add has WriteFlash=false. Do not assume CSR3 survives a different boot chain. A future TGL image must explicitly carry the same CSR3 policy.', 'AMFI_arg_added': False, 'authenticated_root_disabled': False, 'source_config_matches_prior_VESA': True, 'all_original_file_paths_preserved': True, 'new_native_mount_metadata_files': extra_metadata, 'original_file_count': len(a), 'all_original_non_config_files_native_md5_equal': True, 'new_config_readback_exact': True, 'new_config_ocvalidate_rc': 0, 'source_native_md5_before_after': md5, 'source_and_candidate_attached_images_detached': True, 'reboot_or_shutdown_executed': False, 'final_image_sha256': 'PENDING'}
    report_path = ROOT / 'reports/RECOVERY-SSH.json'
    report_path.write_text(json.dumps(record, indent=2) + '\n')
    row = digest_stream('recovery2222-policy-image-sha256', DEST)
    record['final_image_sha256'] = row['sha256']
    record['image_bytes'] = row['bytes']
    report_path.write_text(json.dumps(record, indent=2) + '\n')
    print('Prepared separate VESA policy image:', DEST, row['sha256'], flush=True)


def main():
    recovery_ssh.configure()
    if '--finish-existing' in sys.argv:
        row = json.loads((ROOT / 'private/commands/recovery2222-policy-image-attach.json').read_text())
        entities = plistlib.loads(row['stdout'].encode())['system-entities']
        device = next(item['dev-entry'] for item in entities if item.get('content-hint') == 'FDisk_partition_scheme')
        md5 = json.loads((ROOT / 'private/commands/recovery2222-original-image-md5-before.json').read_text())['stdout'].strip()
        finish_candidate(ROOT / 'private/config-VESA-GA410-CSR3.plist', device, md5)
        return
    before = plistlib.loads((ROOT / 'private/vesa-live-Recovery-source.plist').read_bytes())
    original = (ROOT.parent / 'private/vesa/EFI/OC/config.plist').read_bytes()
    assert plistlib.loads(original) == before
    after = copy.deepcopy(before)
    assert '-igfxvesa' in after['NVRAM']['Add'][GUID]['boot-args']
    assert all('NootedGreen' not in item['BundlePath'] for item in after['Kernel']['Add'])
    assert before['NVRAM']['Add'][GUID]['csr-active-config'] == bytes(4)
    after['NVRAM']['Add'][GUID]['csr-active-config'] = bytes.fromhex('03000000')
    after['NVRAM']['Delete'].setdefault(GUID, []).append('csr-active-config')
    assert after['NVRAM']['WriteFlash'] is False
    assert after['Misc']['Security']['SecureBootModel'] == 'Disabled'
    path = ROOT / 'private/config-VESA-GA410-CSR3.plist'
    with path.open('xb') as stream:
        plistlib.dump(after, stream, sort_keys=False)
    result = subprocess.run([str(ROOT.parent / 'out/ocvalidate'), str(path)], capture_output=True, text=True)
    (ROOT / 'private/ocvalidate-VESA-CSR3.txt').write_text(result.stdout + result.stderr)
    assert result.returncode == 0
    remote.upload(path, WORK + '/config-VESA-GA410-CSR3.plist', timeout=30)
    md5 = remote.run('recovery2222-original-image-md5-before', '/sbin/md5 ' + SOURCE, timeout=90)['stdout'].strip()
    remote.run('recovery2222-clone-new-policy-image', 'set -eu; /bin/test ! -e ' + DEST + '; set -C; /bin/cat ' + SOURCE + ' > ' + DEST, timeout=180)
    clone_md5 = remote.run('recovery2222-clone-md5-before-edit', '/sbin/md5 ' + DEST, timeout=90)['stdout'].strip()
    assert md5.rsplit(' = ', 1)[-1] == clone_md5.rsplit(' = ', 1)[-1]
    attach = remote.run('recovery2222-policy-image-attach', '/usr/bin/hdiutil attach -readwrite -nomount -imagekey diskimage-class=CRawDiskImage -plist ' + DEST, timeout=60)
    entities = plistlib.loads(attach['stdout'].encode())['system-entities']
    partition = next(item['dev-entry'] for item in entities if item.get('content-hint') == '0xEF')
    device = next(item['dev-entry'] for item in entities if item.get('content-hint') == 'FDisk_partition_scheme')
    assert partition.startswith(device + 's') and device != '/dev/disk5'
    mount = WORK + '/candidate'
    remote.run('recovery2222-policy-fat-mount', '/bin/mkdir ' + mount + '; /sbin/mount_msdos ' + partition + ' ' + mount, timeout=45)
    remote.run('recovery2222-only-policy-config-write', 'set -eu; /bin/cp ' + WORK + '/config-VESA-GA410-CSR3.plist ' + mount + '/EFI/OC/config.plist; /usr/bin/plutil -lint ' + mount + '/EFI/OC/config.plist; /bin/sync', timeout=45)
    finish_candidate(path, device, md5)


if __name__ == '__main__':
    main()
