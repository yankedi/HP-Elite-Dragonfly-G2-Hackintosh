#!/usr/bin/env python3
"""Persist the final evidence bundle on NixOS, target Data and Ventoy, hash-checked."""
import datetime
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
PRIVATE = ROOT / 'private'
STAGE = PRIVATE / 'firstboot-handoff'
USB = '/Volumes/TARGET_VOLUME/GA410-FirstBoot-20261023'
DATA = '/Volumes/TARGET_DATA_VOLUME/Users/Shared/GA410-work-20261023-0820/firstboot-prep-20261023'
HASHER = '/tmp/ga410-policy-prep/recovery-sha256'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_record(name):
    return json.loads((PRIVATE / 'commands' / (name + '.json')).read_text())


def main():
    recovery_ssh.configure()
    assert not STAGE.exists()
    baseline = read_record('recovery2222-kc-repair-final-nvram')
    final = read_record('recovery2222-finalprep-closeout-nvram')
    assert baseline['returncode'] == final['returncode'] == 0
    assert plistlib.loads(baseline['stdout'].encode()) == plistlib.loads(final['stdout'].encode())
    capture = json.loads((PRIVATE / 'FINALPREP-RECOVERY-CAPTURE.json').read_text())
    access = json.loads((PRIVATE / 'FINALPREP-ACCESS-POLICY.json').read_text())
    images = json.loads((ROOT / 'reports/FINALPREP-DELIVERY.json').read_text())
    for name in ['recovery2222-finalprep-recovery-verify-latest',
                 'recovery2222-finalprep-install-capture',
                 'recovery2222-finalprep-collect-baseline-pax-fixed',
                 'recovery2222-finalprep-closeout-live']:
        assert read_record(name)['returncode'] == 0
    assert not read_record('recovery2222-finalprep-collect-baseline-pax-fixed')['stderr']
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    state = {
        'evidence_through_utc': final['time_utc'],
        'receipt_created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope': 'All operations possible before the next user-arranged physical boot',
        'status': 'PREBOOT_PREP_COMPLETE',
        'ready_for_user_first_test_boot': True,
        'completed_statuses': ['BACKUP_COMPLETE', 'KDK_INSTALLED', 'SYSTEM_COMPONENTS_INSTALLED',
                               'KC_REGISTERED', 'PREBOOT_PREP_COMPLETE'],
        'policy_applied': False,
        'INSTALL_READY': False,
        'INSTALL_READY_note': 'Strict runtime policy/load prerequisites are unverified until a physical boot; preboot work is complete.',
        'runtime_trusted_kext_loading_verified': False,
        'Metal_Shader_GPU_verified': False,
        'prepared_policy': {'csr': '0x203', 'csr_little_endian_hex': '03020000',
                            'amfi_boot_argument': 'amfi_get_out_of_my_way=1',
                            'authenticated_root_disabled': False,
                            'upstream_evidence': 'FIRSTBOOT-SECURITY.md'},
        'images': [{k: entry[k] for k in ['name', 'destination', 'sha256', 'bytes']}
                   for entry in images['images']],
        'images_native_readonly_inventory_and_config_verified': True,
        'installed_aux_sha256': '38f58293b7636dc7867168e670bb51a66958b10b54de515148a5e0d796543da5',
        'installed_aux_uuid': '604F5C97-83A1-FBB1-B9FD-9EFD343C47F5',
        'component_SHA256_reverified_files': 204,
        'original_backup_SHA256_reverified_files': 22,
        'original_KC_unchanged_other_than_published_AuxKC': 15,
        'capture_job_installed': True,
        'capture_job_bootstrapped_in_Recovery': False,
        'capture_marker_exists': False,
        'capture_results_directory_empty_before_boot': True,
        'capture_runs_Metal_or_GPU_workload': False,
        'capture_job_keepalive': False,
        'recovery_nondestructive_verify_rc': 0,
        'recovery_collect_baseline': capture,
        'recovery_destructive_restore_exercised': False,
        'access_offline_checks': access,
        'current_Recovery_CSR_raw': '00000000',
        'current_authenticated_root': 'enabled',
        'NVRAM_dictionary_unchanged_variables': 11,
        'current_boot_session_uuid': 'REDACTED-SESSION-ID',
        'internal_EFI_written': False,
        'original_GA48_and_VESA_images_modified': False,
        'default_boot_entry_changed': False,
        'Reset_NVRAM_performed': False,
        'shutdown_or_reboot_executed': False,
        'machine_left_powered_on_with_SSH': True,
        'next_step': 'User-arranged boot: new TGL IMG -> installed Tahoe, then inspect control-plane evidence over port 22.',
        'recovery_route': 'New CSR0 Recovery IMG -> embedded Recovery, not installed Tahoe.',
        'source_tools_commit': commit,
        'local_only_no_push': True,
        'handoff_verification_receipt': 'HANDOFF-DELIVERY.json',
    }
    (ROOT / 'reports/FIRSTBOOT-STATE.json').write_text(json.dumps(state, indent=2) + '\n')
    STAGE.mkdir(mode=0o700)
    files = {
        'restore-firstboot-recovery.sh': ROOT / 'tools/restore-firstboot-recovery.sh',
        'restore-recovery-native.sh': ROOT / 'tools/restore-recovery.sh',
        'recovery-checksums.tsv': ROOT / 'reports/recovery-checksums.tsv',
        'INSTALLED-SHA256SUMS': PRIVATE / 'INSTALL-SHA256SUMS',
        'target.plist': PRIVATE / 'target-finalprep.plist',
        'recovery-sha256': PRIVATE / 'recovery-sha256',
        'csr-readonly-probe': PRIVATE / 'csr-readonly-probe',
    }
    for name in ['FIRST-BOOT.md', 'SSH-ACCESS.md', 'FIRSTBOOT-SECURITY.md', 'FIRSTBOOT-OPERATIONS.md',
                 'FIRSTBOOT-STATE.json', 'FINALPREP-IMAGES.json', 'FINALPREP-DELIVERY.json',
                 'BOOT-IN-TGL.txt', 'BOOT-IN-RECOVERY.txt', 'KC-REPAIR.md', 'KC-REPAIR-STATE.json']:
        files[name] = ROOT / ('reports/' + name)
    for name in ['collect-firstboot.sh', 'com.ga410.firstboot.plist', 'install-firstboot-capture.sh',
                 'prepare-firstboot-images.py', 'deliver-firstboot-images.py', 'amend-firstboot-notes.py',
                 'recovery-sha256.c', 'csr-readonly-probe.c', 'finalize-firstboot-handoff.py']:
        files['sources/' + name] = ROOT / ('tools/' + name)
    for name, source in files.items():
        target = STAGE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    selected = []
    for path in sorted((PRIVATE / 'commands').glob('*.json')):
        row = json.loads(path.read_text())
        # Include all operations from the new request onwards, including rc!=0.
        stamp = row.get('time_utc', '')
        if 'finalprep' in path.name or stamp >= '2026-10-23T08:00:00':
            selected.append(path)
    selected.extend(PRIVATE / name for name in [
        'FINALPREP-ACCESS-POLICY.json', 'FINALPREP-RECOVERY-CAPTURE.json',
        'FINALPREP-IMAGES-before-note-fix.json', 'FINALPREP-DELIVERY-before-note-fix.json'])
    for name in ['upload-collect-firstboot.sh.json', 'upload-com.ga410.firstboot.plist.json',
                 'upload-install-firstboot-capture.sh.json', 'upload-restore-firstboot-recovery.sh.json',
                 'upload-restore-firstboot-recovery-v2.sh.json', 'upload-restore-firstboot-recovery-v3.sh.json',
                 'download-normal-system-host-ed25519.pub.json']:
        path = PRIVATE / 'commands' / name
        if path not in selected:
            selected.append(path)
    with tarfile.open(STAGE / 'operation-evidence.tar.gz', 'w:gz') as archive:
        for path in selected:
            assert path.is_file()
            archive.add(path, arcname=str(path.relative_to(PRIVATE)), recursive=False)
    manifest = ''.join(sha(path) + '  ' + str(path.relative_to(STAGE)) + '\n'
                       for path in sorted(STAGE.rglob('*')) if path.is_file())
    (STAGE / 'HANDOFF-SHA256SUMS').write_text(manifest)
    bundle = PRIVATE / 'GA410-firstboot-handoff-20261023.tar.gz'
    with tarfile.open(bundle, 'x:gz') as archive:
        for path in sorted(STAGE.rglob('*')):
            if path.is_file():
                archive.add(path, arcname=str(path.relative_to(STAGE)), recursive=False)
    remote_bundle = '/tmp/ga410-firstboot-prep/GA410-firstboot-handoff-20261023.tar.gz'
    remote.upload(bundle, remote_bundle, timeout=90)
    manifest_hash = sha(STAGE / 'HANDOFF-SHA256SUMS')
    stage_remote = '/tmp/ga410-firstboot-prep/handoff-final'
    command = ['set -eu', 'value=$(' + HASHER + ' ' + shlex.quote(remote_bundle) + ')',
               '[ "${value%% *}" = ' + sha(bundle) + ' ]',
               '/bin/mkdir ' + shlex.quote(stage_remote),
               '/usr/bin/tar -xpf ' + shlex.quote(remote_bundle) + ' -C ' + shlex.quote(stage_remote),
               'cd ' + shlex.quote(stage_remote), HASHER + ' -c HANDOFF-SHA256SUMS']
    remote.run('recovery2222-finalprep-handoff-stage-verified', '; '.join(command), timeout=90)
    checks = []
    for label, destination in [('Ventoy', USB), ('Data', DATA)]:
        # Existing bytes must match exactly; preserve the records/ directory.
        commands = ['set -eu']
        for path in sorted(STAGE.rglob('*')):
            if not path.is_file():
                continue
            relative = str(path.relative_to(STAGE))
            target = destination + '/' + relative
            parent = str(Path(target).parent)
            commands.extend([
                '/bin/mkdir -p ' + shlex.quote(parent),
                'if [ -e ' + shlex.quote(target) + ' ]; then value=$(' + HASHER + ' ' + shlex.quote(target) + '); '
                '[ "${value%% *}" = ' + sha(path) + ' ]; '
                'else /bin/cat ' + shlex.quote(stage_remote + '/' + relative) + ' > ' + shlex.quote(target) + '; fi',
            ])
        commands += ['/bin/chmod 755 ' + shlex.quote(destination + '/recovery-sha256') + ' ' + shlex.quote(destination + '/csr-readonly-probe'),
                     'cd ' + shlex.quote(destination), HASHER + ' -c HANDOFF-SHA256SUMS',
                     HASHER + ' HANDOFF-SHA256SUMS', '/bin/sync']
        row = remote.run('recovery2222-finalprep-handoff-deliver-' + label.lower(), '; '.join(commands), timeout=150)
        assert row['returncode'] == 0 and manifest_hash in row['stdout']
        checks.append({'copy': label, 'directory': destination, 'manifest_sha256': manifest_hash,
                       'native_verify_rc': row['returncode'], 'all_manifest_files_verified': True})
    receipt = {'status': 'HANDOFF_DELIVERED_AND_NATIVE_SHA256_VERIFIED',
               'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'local_directory': str(STAGE.relative_to(ROOT.parent)),
               'bundle_sha256': sha(bundle), 'bundle_bytes': bundle.stat().st_size,
               'manifest_sha256': manifest_hash, 'manifest_files': len(manifest.splitlines()),
               'evidence_files_in_operation_archive': len(selected), 'copies': checks,
               'source_tools_commit': commit, 'no_physical_boot_or_shutdown_performed': True}
    receipt_path = ROOT / 'reports/HANDOFF-DELIVERY.json'
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    remote_path = '/tmp/ga410-firstboot-prep/HANDOFF-DELIVERY.json'
    remote.upload(receipt_path, remote_path, timeout=30)
    commands = ['set -eu']
    for destination in [USB, DATA]:
        path = destination + '/HANDOFF-DELIVERY.json'
        commands += ['/bin/test ! -e ' + shlex.quote(path),
                     '/bin/cat ' + shlex.quote(remote_path) + ' > ' + shlex.quote(path),
                     'value=$(' + HASHER + ' ' + shlex.quote(path) + ')',
                     '[ "${value%% *}" = ' + sha(receipt_path) + ' ]']
    commands.append('/bin/sync')
    remote.run('recovery2222-finalprep-handoff-receipt-two-copies', '; '.join(commands), timeout=45)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
