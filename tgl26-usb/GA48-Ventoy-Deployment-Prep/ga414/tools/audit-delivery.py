#!/usr/bin/env python3
"""Offline completion audit of actual GA414 image-delivery evidence, no SSH/GPU."""
import json
import plistlib
import re
from common import *


def main():
    delivery = json.loads((REPORTS / 'DELIVERY.json').read_text())
    local = json.loads((REPORTS / 'IMAGE-LOCAL.json').read_text())
    build = json.loads((REPORTS / 'BUILD.json').read_text())
    signed = json.loads((REPORTS / 'NATIVE-SIGNATURE.json').read_text())
    source = json.loads((REPORTS / 'SOURCE-AND-DONOR.json').read_text())
    guards = json.loads((REPORTS / 'GUARD-TESTS.json').read_text())
    require(delivery['states'] == ['IMAGE_BUILT', 'BOOT_NOT_TESTED', 'STABILITY_UNVERIFIED'], 'incorrect preboot state')
    require(delivery['pixel_status'] == 'NOT_RUN' and delivery['NOAUX_runtime_confirmed'] is False,
            'preboot build must not claim runtime/pixel success')
    require(delivery['changed_files_vs_R6'] == ['EFI/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen']
            and not delivery['added_files_vs_R6'] and not delivery['removed_files_vs_R6'], 'non-NG image changes')
    require(inventory(WORK / 'source') == source['source_sha256'], 'source changed since audit/build')
    require(inventory(R6 / 'source') == json.loads((REPORTS / 'R6-SOURCE-INVENTORY.json').read_text()), 'sealed R6 changed')
    require(sha(ROOT / local['source_R6']['path']) == local['source_R6']['sha256'], 'sealed source IMG changed')
    require(sha(ROOT / delivery['local_image']['path']) == delivery['sha256'] == local['image']['sha256'], 'local image hash differs')
    require(inventory(WORK / 'mtools-readback') == local['full_image_inventory'], 'local image readback differs')
    require(inventory(WORK / 'native-signed/NootedGreen.kext') == signed['bundle_inventory'], 'signed kext changed')
    require(macho((WORK / 'native-signed/NootedGreen.kext/Contents/MacOS/NootedGreen').read_bytes()) == build['MachO'] == signed['MachO'], 'sections/UUID inconsistent')
    require(delivery['new_NG_UUID'] == build['MachO']['uuid'] and guards['cases'] == 22, 'UUID/guard coverage mismatch')
    require(not build['new_undefined_symbols_vs_R6'], 'new imported dependencies')

    def receipt(name):
        row = json.loads((WORK / ('commands/' + name + '.json')).read_text())
        require(row['returncode'] == 0, 'failed required receipt: ' + name)
        return row

    for name in ['native-adhoc-sign-strict', 'new-image-sync-and-full-hash', 'native-image-attach-readonly',
                 'native-image-mount-readonly', 'native-image-complete-file-hashes', 'native-mounted-image-signature',
                 'native-image-unmount-direct', 'native-image-detach', 'new-image-final-sync-rehash',
                 'delivery-protected-before', 'delivery-protected-after', 'checksum-sidecar-sync']:
        receipt(name)
    mount = '/private/tmp/ga414-noaux/image-readonly'
    mounted = receipt('native-image-mount-readonly')['stdout']
    require(any(' on ' + mount + ' ' in line and 'read-only' in line for line in mounted.splitlines()), 'no actual read-only mount proof')
    actual = {}
    for line in receipt('native-image-complete-file-hashes')['stdout'].splitlines():
        digest, path = line.split('  ', 1)
        require(path.startswith(mount + '/'), 'inventory path mismatch')
        actual[path[len(mount) + 1:]] = digest
    require(actual == local['full_image_inventory'], 'native complete inventory differs')
    for name in ['new-image-sync-and-full-hash', 'new-image-final-sync-rehash']:
        require(receipt(name)['stdout'].strip() == delivery['sha256'] + '  ' + delivery['USB_image'], 'native USB hash mismatch')
    pre, post = [json.loads(receipt(name)['stdout']) for name in ('delivery-protected-before', 'delivery-protected-after')]
    for key in ('protected_images', 'installed_files', 'boot_session', 'USB_volume_UUID'):
        require(pre[key] == post[key], 'protected state changed: ' + key)
    require(pre['protected_images'] == delivery['protected_images_unchanged_before_after'], 'protected images report mismatch')
    require(pre['installed_files'] == delivery['installed_files_and_KC_unchanged_before_after'], 'installed hashes report mismatch')
    require(delivery['boot_args'] == local['boot_args'] and '-ngreenccs' not in local['boot_args'].split()
            and '-ngreenxefix' not in local['boot_args'].split(), 'wrong boot args')
    require((WORK / 'native-image-config.plist').read_bytes() == (WORK / 'mtools-readback/EFI/OC/config.plist').read_bytes(), 'native config mismatch')
    # Resolve every nested artifact record in the public evidence reports.
    artifact_records = 0

    def walk(value):
        nonlocal artifact_records
        if isinstance(value, dict):
            if {'path', 'bytes', 'sha256'} <= value.keys():
                path = ROOT / value['path']
                require(path.stat().st_size == value['bytes'] and sha(path) == value['sha256'], 'artifact hash mismatch: ' + value['path'])
                artifact_records += 1
            for item in value.values(): walk(item)
        elif isinstance(value, list):
            for item in value: walk(item)
    for value in [delivery, local, build, signed, source, guards]: walk(value)
    for path in (ROOT / 'ga414').glob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            if '://' not in link: require((path.parent / link).exists(), 'broken report link: ' + link)
    result = {'status': 'DELIVERY_AUDIT_PASS_BOOT_NOT_TESTED', 'artifact_records_verified': artifact_records,
              'full_image_files_verified': len(actual), 'states': delivery['states'],
              'image_sha256': delivery['sha256'], 'new_NG_UUID': delivery['new_NG_UUID'],
              'GPU_commands_submitted': False, 'runtime_confirmation': 'NOT_OBSERVED_WAIT_USER_PHYSICAL_BOOT',
              'checks': ['sealed R6 source/image preserved', 'only NG executable changed', 'same source/build/native signature UUID/sections',
                         'OC/FAT/Enabled dependencies evidence present', 'native readonly full file inventory matches',
                         'sync-after-transfer and sync-after-detach image hashes match', 'protected images and installed stack/AuxKC unchanged',
                         'exact boot args and native config readback', 'every recorded artifact hash and document link valid'],
              'known_non_success_receipts_preserved': ['legacy pseudo-library preflight rejection, unchanged loaded consumers verified',
                                                     'diskutil unmount failure, targeted direct umount/detach succeeded']}
    output = REPORTS / 'DELIVERY-AUDIT.json'
    if output.exists(): require(json.loads(output.read_text()) == result, 'archived delivery audit differs')
    else: save(output, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
