#!/usr/bin/env python3
"""Audit the actual PLANES2 artifact and delivery receipts without contacting HP."""
import hashlib
import json
from pathlib import Path
import plistlib

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / 'ga415/reports'
WORK = ROOT / 'ga415/private/planesfix'
COMMANDS = ROOT / 'ga415/private/commands'


def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    abi = json.loads((REPORTS / 'PLANES2-ABI.json').read_text())
    image = json.loads((REPORTS / 'PLANES2-IMAGE.json').read_text())
    delivered = json.loads((REPORTS / 'PLANES2-DELIVERY.json').read_text())
    cpu = json.loads((REPORTS / 'PLANES2-CPU-LAYOUT.json').read_text())
    assert abi['status'] == 'EXACT_25G83_PLANES2_ABI_VERIFIED_RUNTIME_PENDING'
    assert delivered['status'] == 'PLANES2_IMAGE_DELIVERED_BOOT_NOT_TESTED'
    for record in [abi['IOSurface_KDK'], abi['donor'], abi['preserved_GA414_NG'], abi['preserved_source'],
                   image['image'], image['baseline_GA414'], image['FAT_check'], image['ABI_verification']]:
        p = ROOT / record['path']; assert p.stat().st_size == record['bytes'] and sha(p) == record['sha256'], str(p)
    def receipt(name):
        r = json.loads((COMMANDS / (name + '.json')).read_text()); assert r['returncode'] == 0, name
        return r
    for name in ['planesfix-transfer-sync-hash', 'planesfix-native-attach-readonly', 'planesfix-native-mount-readonly',
                 'planesfix-native-full-inventory', 'planesfix-native-signature-and-config', 'planesfix-native-unmount',
                 'planesfix-native-detach', 'planesfix-final-sync-and-image-hashes', 'planesfix-sidecar-sync',
                 'planesfix-cpu-layout-build', 'planesfix-cpu-layout-once']:
        receipt(name)
    pre, post = [json.loads(receipt('planesfix-protected-' + side)['stdout']) for side in ['before', 'after']]
    for field in ['protected_images', 'installed_files', 'boot_session', 'USB_volume_UUID']: assert pre[field] == post[field]
    assert delivered['old_boot_session'] == delivered['final_boot_session'] == pre['boot_session']
    assert image['NG_UUID'] == abi['NG_UUID'] == delivered['NG_UUID'] == '4C4C44E9-5555-3144-A1E4-CB51FF5A72E6'
    assert image['changed_files_vs_GA414'] == delivered['changed_files_vs_GA414'] == ['EFI/OC/config.plist']
    readback = {str(p.relative_to(WORK / 'image-readback')):sha(p) for p in (WORK / 'image-readback').rglob('*') if p.is_file()}
    assert readback == image['full_image_inventory']
    mount = '/private/tmp/ga415-planes2-delivery/readonly'
    native = {}
    for line in receipt('planesfix-native-full-inventory')['stdout'].splitlines():
        digest, path = line.split('  ', 1); assert path.startswith(mount + '/')
        native[path[len(mount) + 1:]] = digest
    assert native == readback and len(native) == delivered['file_count']
    assert 'read-only' in receipt('planesfix-native-mount-readonly')['stdout']
    signature = receipt('planesfix-native-signature-and-config')
    assert abi['NG_UUID'] in signature['stdout'] and 'Signature=adhoc' in signature['stderr']
    assert (WORK / 'native-config.plist').read_bytes() == (WORK / 'PLANES2-config.plist').read_bytes()
    old = plistlib.loads((ROOT / 'ga414/private/mtools-readback/EFI/OC/config.plist').read_bytes())
    new = plistlib.loads((WORK / 'native-config.plist').read_bytes()); guid = '7C436110-AB2A-4BBB-A880-FE41995C9F82'
    before_args = old['NVRAM']['Add'][guid]['boot-args']
    old['NVRAM']['Add'][guid]['boot-args'] = before_args.replace(' -ngreennoplanesfix', '')
    assert old == new and 'boot-args' in new['NVRAM']['Delete'][guid]
    assert cpu['status'] == 'CPU_IOSURFACE_LAYOUT_PASS' and not cpu['GPU_submitted'] and not cpu['Metal_device_created']
    assert [r['actual_plane_count'] for r in cpu['cases']] == [0, 2, 2]
    assert not delivered['automatic_reboot'] and not delivered['GPU_test_submitted']
    assert delivered['runtime_PLANES2_applied'] == 'NOT_OBSERVED' and delivered['panic_retest'] == 'NOT_RUN'
    digest = image['image']['sha256']; path = delivered['USB_image']
    assert receipt('planesfix-transfer-sync-hash')['stdout'].strip() == digest + '  ' + path
    assert receipt('planesfix-final-sync-and-image-hashes')['stdout'].splitlines()[0] == digest + '  ' + path
    report = dict(status='PLANES2_ABI_IMAGE_DELIVERY_AUDIT_PASS_BOOT_NOT_TESTED',
                  USB_image=path, image_sha256=digest, file_count=len(native),
                  exact_25G83_plane_count_offset_verified='0x98', only_config_boot_arg_changed=True,
                  CPU_layouts=[0, 2, 2], protected_old_images_and_installed_files_unchanged=True,
                  runtime_fix_verified=False, runtime_PLANES2_applied='NOT_OBSERVED',
                  historical_panic_direct_cause='DIVIDE_BY_ZERO_VERIFIED', desktop_pixel_fix='NOT_VERIFIED')
    with (REPORTS / 'PLANES2-FINAL-AUDIT.json').open('x') as f: json.dump(report, f, indent=2); f.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
