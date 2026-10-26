#!/usr/bin/env python3
"""Audit completed R5 evidence if SSH is lost after native image verification."""
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('delivery', Path(__file__).with_name('deliver-ng-r5.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def receipt(name, expected_rc=0):
    path = d.ROOT / 'private/commands' / (name + '.json')
    value = json.loads(path.read_text())
    assert value['returncode'] == expected_rc, name
    return value


def main():
    build = json.loads((d.ROOT / 'reports/NG-R5-BUILD.json').read_text())
    previous = json.loads((d.ROOT / 'reports/TGL-R4.json').read_text())
    image = d.WORK / d.NAME
    bundle = d.WORK / 'native-signed/NootedGreen.kext'
    binary = bundle / 'Contents/MacOS/NootedGreen'
    source = d.WORK / 'source/src/NootedGreen/kern_gen11.cpp'
    assert d.sha(source) == build['source_after_sha256']
    expected = {p: h for p, h in previous['image_inventory'].items()
                if not p.startswith('EFI/OC/Kexts/NootedGreen.kext/')}
    for p in bundle.rglob('*'):
        if p.is_file():
            expected['EFI/OC/Kexts/NootedGreen.kext/' + str(p.relative_to(bundle))] = d.sha(p)
    expected['FIRST-BOOT.txt'] = d.sha(d.ROOT / 'reports/BOOT-IN-TGL-R5.txt')
    mount = d.BASE + '/image-readonly'
    readback = receipt('r5-native-full-image-file-inventory')
    actual = {}
    for line in readback['stdout'].splitlines():
        digest, name = line.split('  ', 1)
        assert name.startswith(mount + '/')
        actual[name[len(mount) + 1:]] = digest
    assert actual == expected
    receipt('r5-native-image-ng-signature-and-plist')
    receipt('r5-native-image-msdos-readonly-mount')
    sign = receipt('r5-native-sign-and-strict-verify')
    assert 'Signature=adhoc' in sign['stdout'] + sign['stderr']
    assert d.sha(d.WORK / 'NootedGreen-R5-native-signed.tar.gz') in sign['stdout']
    sections = d.macho(binary.read_bytes())
    assert sections == d.macho((d.WORK / 'build/product/NootedGreen.kext/Contents/MacOS/NootedGreen').read_bytes())
    config = d.ROOT / 'private/tgl-r1/config.plist'
    assert config.read_bytes() == (d.WORK / 'native-image-config.plist').read_bytes()
    validation = d.run([d.REPO / 'out/ocvalidate', config])
    image_sha = d.sha(image)
    assert receipt('r5-native-full-image-hash-before-mount')['stdout'].strip() == image_sha + '  ' + d.DEST
    local = d.WORK / 'mtools-readback-finish'
    local_inventory = {str(p.relative_to(local)): d.sha(p) for p in local.rglob('*') if p.is_file()}
    assert local_inventory == {p: h for p, h in expected.items() if p.startswith('EFI/') or p == 'FIRST-BOOT.txt'}
    detach = receipt('r5-native-image-detach', 16)
    reconnect = receipt('r5-finalize-after-ssh-timeout', 255)
    report = {
        'status': 'R5_IMAGE_DELIVERED_VERIFIED_SSH_LOST_FINAL_CLEANUP_UNCONFIRMED',
        'image': d.DEST, 'name': d.NAME, 'sha256': image_sha, 'bytes': image.stat().st_size,
        'source_delta': build['functional_delta'],
        'new_NG_binary_sha256': d.sha(binary), 'new_NG_uuid': sections['uuid'],
        'native_codesign_strict_deep_rc': 0, 'native_signature_type': 'adhoc experimental, not Apple trust',
        'signing_preserved_all_executable_sections_and_UUID': True,
        'ocvalidate_rc': 0, 'ocvalidate_output': validation,
        'configuration_identical_to_R4': True,
        'native_entire_file_inventory_matches': True, 'native_inventory_file_count': len(actual),
        'native_config_readback_exact': True, 'native_entire_image_hash_matches_local': True,
        'native_hash_timing': 'After upload, before read-only attach; final post-detach hash was blocked by lost SSH.',
        'mtools_entire_EFI_and_boot_note_readback_matches': True,
        'native_readback_mount': 'hdiutil attach -readonly -nomount; mount_msdos -o rdonly',
        'native_readback_detach_confirmed': False, 'final_sync_confirmed': False,
        'cleanup_blocker': detach['stderr'].strip() + '\n' + reconnect['stderr'].strip(),
        'capture_marker_rearmed': False,
        'collector_rearm_blocker': 'sudo -n requires a password; GUI was stuck, marker rename not executed.',
        'R4_USB_image_after_verification_checked': False,
        'new_native_signed_NG_backup_on_Data': d.TARGET_WORK,
        'internal_EFI_changed': False, 'installed_components_or_KC_written': False,
        'original_images_overwritten': False, 'NVRAM_written': False,
        'shutdown_or_reboot_executed': False, 'physical_boot_performed': False,
        'runtime_fix_verified': False, 'image_inventory': expected,
    }
    (d.ROOT / 'reports/TGL-R5.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ['image_inventory', 'ocvalidate_output']}, indent=2))


if __name__ == '__main__':
    main()
