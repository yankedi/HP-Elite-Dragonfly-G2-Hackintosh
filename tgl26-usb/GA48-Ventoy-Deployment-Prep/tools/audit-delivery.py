#!/usr/bin/env python3
"""Final local evidence audit; no image mutation or target execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def load(name):
    return json.loads((ROOT / 'reports' / name).read_text())


def main():
    image, media, package, esp = [load(x) for x in ['IMAGE.json', 'MEDIA.json', 'PACKAGE.json', 'ESP-COMPARISON.json']]
    expected = '0facaf8ec3767c0235f326ad782cb7c000e881aca8274345cde2f3f235a693e4'
    for p in [ROOT / image['image'], Path(media['usb']['path'])]:
        assert p.is_file() and p.stat().st_size == 1343225856 and sha(p) == expected
    assert image['sha256'] == media['image_sha256'] == expected
    assert esp['internal_esp_before_equals_after'] and esp['current_config_sha256'] == 'efc18fb4cbd93688295c8ceaa74a044698afa2b1b1219a1f82a14b1d27313a6e'
    assert media['vesa_ng_independent'] and media['root_non_efi_files_unchanged']
    assert all(v['returncode'] == 0 for v in media['fat'].values())
    for name, digest in media['protected_images_after'].items():
        assert sha(Path(media['usb']['path']).parent / name) == digest
    assert package['files_and_links'] == 246 and package['mach_o_count'] == 31 and package['code_pages'] == 51898
    binary = {x['path']: x for x in package['binaries']}
    for name in ['NootedGreen', 'HookCase']:
        k = next(x for x in binary.values() if x['path'].endswith('/MacOS/' + name))
        assert k['filetype'] == 11
    for name in ['libxedrv.dylib', 'libLLVMbridge.dylib', 'libMTLIGCCompilerPlugin.dylib']:
        assert any(x['path'].endswith('/' + name) and x['filetype'] == 6 for x in binary.values())
    assert package['patches']['MTL']['patches'] == 10 and package['patches']['old_plugin']['patches'] == 12 and len(package['resources']) == 6
    assert any('/3802/' in key for key in package['dependency_inventory']) and any('/3902/' in key for key in package['dependency_inventory'])
    old = ROOT.parent / 'GA47-JulioNectar-HP-Port'
    spec = importlib.util.spec_from_file_location('ga47', old / 'hp-port/verify-offline.py')
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    p = ROOT / 'private/package-check/package'
    hook = v.audit.inspect(p / 'payload/Library/Extensions/HookCase.kext/Contents/MacOS/HookCase')
    assert '_strnstr' in {x['name'] for x in hook['exports']}
    xe = p / 'payload/System/Library/Caches/xe.bundle/Contents/MacOS'
    for file, suffix in [('libMTLIGCCompilerPlugin.dylib', '/libMTLIGCCompilerPluginOld.dylib'), ('libLLVMbridge.dylib', '/32023/Libraries/libLLVM.dylib')]:
        x = v.audit.inspect(xe / file)
        assert any(d['command'] == 0x8000001f and d['name'].endswith(suffix) for d in x['libraries'])
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=old)
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=old, text=True).strip() == 'a9ae966cd56075db59cc6ff2878e3958022d91b7'
    args = image['boot_args'].split()
    assert '-ngreennoplanesfix' in args and '-ngreentgltahoe' in args and not any('amfi' in x for x in args)
    assert image['boot_args_bytes_excluding_nul'] == 167 and len(image['enabled_kexts']) == 13
    assert media['ga48_total_files'] == 99 and media['ga48_efi_files'] == 85
    subprocess.run(['bash', '-n', 'tools/deployment-review.sh', 'tools/recovery-review.sh', 'tools/recovery-kc-review.sh'], cwd=ROOT, check=True)
    for name, rc in [('codesign-control', 0), ('native-codesign', 1), ('inspect-aux', 0), ('inspect-system', 0), ('target-tgl', 1), ('kdk', 1)]:
        assert json.loads((ROOT / 'private/native' / (name + '.json')).read_text())['returncode'] == rc
    docs = ['CONFIG-DIFF.md', 'PACKAGE-CHECK.md', 'TARGET-PREFLIGHT.md', 'SECURITY.md', 'VESA-RECOVERY.md', 'DEPLOYMENT.md', 'FIRST-BOOT.md', 'RESULTS.md', 'ACCEPTANCE.md']
    for name in docs:
        assert (ROOT / 'reports' / name).stat().st_size > 300
    # Native staging integrity file: generated from the archive's pinned receipt.
    receipt = json.loads((ROOT / 'private/package-check/ARTIFACT-MANIFEST.json').read_text())
    lines = []
    for item in receipt['inventory']:
        if 'sha256' in item:
            assert sha(p / item['path']) == item['sha256']
            lines.append(item['sha256'] + '  ' + item['path'])
    (ROOT / 'out/PACKAGE-SHA256SUMS').write_text('\n'.join(lines) + '\n')
    artifact = {'status': 'GA48_MEDIA_AND_AUTHORIZED_PREFLIGHT_DELIVERED_ACCELERATION_BLOCKED', 'image_bytes': 1343225856, 'image_sha256': expected, 'local_image': image['image'], 'ventoy_image': media['usb']['path'], 'package_sha256': package['archive_sha256'], 'protected_images': media['protected_images_after'], 'internal_esp_unchanged': esp['internal_esp_after_sha256'], 'native_package_codesign': 'NOT_PERFORMED_NO_REMOTE_STAGING_AUTHORIZATION', 'target_install_or_KC_registration': 'NOT_PERFORMED', 'physical_boot_or_GPU_test': 'NOT_PERFORMED', 'script_verification': 'bash -n plus manual path/order/failure/recovery review; NOT EXECUTED', 'documents': {name: sha(ROOT / 'reports' / name) for name in docs}, 'evidence': {name: sha(ROOT / 'reports' / name) for name in ['IMAGE.json', 'MEDIA.json', 'PACKAGE.json', 'DEPENDENCIES.json', 'NATIVE-COMMANDS.json', 'ESP-COMPARISON.json']}}
    (ROOT / 'reports/ARTIFACTS.json').write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + '\n')
    print('PASS: image/local+USB, protected media, raw ESP, package/kext/dylib/reexports/resources, native evidence, script syntax and all delivery documents')


if __name__ == '__main__':
    main()
