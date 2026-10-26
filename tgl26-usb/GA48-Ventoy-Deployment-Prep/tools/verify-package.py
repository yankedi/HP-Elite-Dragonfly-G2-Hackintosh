#!/usr/bin/env python3
"""Recheck the immutable GA47 archive in a new private directory, no target IO."""
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / 'GA47-JulioNectar-HP-Port'
OUT = ROOT / 'private/package-check'
EXPECTED = '51aaffade75da6d5076071e304e4634aefe60e68d7e0cdd12d79981e31f1b143'


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    archive = OLD / 'build/ga47/GA47-HP-TGL-25G83-offline.tar.gz'
    assert sha(archive) == EXPECTED
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=OLD, text=True).strip() == 'a9ae966cd56075db59cc6ff2878e3958022d91b7'
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=OLD)
    manifest_path = OLD / 'build/ga47/ARTIFACT-MANIFEST.json'
    assert sha(manifest_path) == '293e9a962c1deca138573ca913cc2a23522a9f28d49714af13e84488c86623a5'
    m = json.loads(manifest_path.read_text())
    if not OUT.exists():
        OUT.mkdir()
        with tarfile.open(archive) as t:
            t.extractall(OUT, filter='data')
    package = OUT / 'package'
    actual = {str(p.relative_to(package)) for p in package.rglob('*') if p.is_file() or p.is_symlink()}
    # The embedded receipt is intentionally outside its own inventory.
    assert actual == {i['path'] for i in m['inventory']}
    assert (OUT / 'ARTIFACT-MANIFEST.json').read_bytes() == manifest_path.read_bytes()
    assert len(m['inventory']) == 246
    for i in m['inventory']:
        p = package / i['path']
        if 'symlink' in i:
            assert p.is_symlink() and str(p.readlink()) == i['symlink']
        else:
            assert p.stat().st_size == i['bytes'] and sha(p) == i['sha256'], p
    spec = importlib.util.spec_from_file_location('ga47check', OLD / 'hp-port/verify-offline.py')
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    binaries, pages, versions = [], 0, []
    for i in m['inventory']:
        p = package / i['path']
        if p.is_symlink() or p.read_bytes()[:4] not in (bytes.fromhex('cffaedfe'), bytes.fromhex('cafebabe')):
            continue
        x = v.audit.inspect(p)
        signed = v.code_pages(p, required=False)
        pages += sum(d['pages'] for d in signed)
        if x['header']['filetype'] == 11:
            v.audit.validate_kext(x)
        binaries.append({'path': i['path'], 'sha256': sha(p), 'filetype': x['header']['filetype'], 'libraries': x['libraries'], 'code_directories': signed})
    assert len(binaries) == 31 and pages == 51898
    for p in package.rglob('*.kext/Contents/Info.plist'):
        d = plistlib.loads(p.read_bytes())
        versions.append({'path': str(p.relative_to(package)), 'id': d['CFBundleIdentifier'], 'version': d['CFBundleVersion'], 'compatible': d.get('OSBundleCompatibleVersion'), 'dependencies': d.get('OSBundleLibraries', {}), 'personalities': list(d.get('IOKitPersonalities', {}))})
    ng = next(x for x in versions if x['id'] == 'com.StezzaPilot.NootedGreen')
    lilu = next(x for x in versions if x['id'] == 'as.vit9696.Lilu')
    assert lilu['version'] == '1.7.2'
    assert ng['dependencies']['as.vit9696.Lilu'] <= lilu['version']
    xe = package / 'payload/System/Library/Caches/xe.bundle/Contents'
    adapter = v.audit.inspect(xe / 'MacOS/libMTLIGCCompilerPlugin.dylib')
    old = v.audit.inspect(xe / 'MacOS/libMTLIGCCompilerPluginOld.dylib')
    assert '_MTLCompilerBuildRequestWithSerializedBitcode' in {x['name'] for x in adapter['exports']}
    assert '_MTLCompilerBuildRequestWithOptions' in {x['name'] for x in old['exports']}
    assert b'TGLLP' in (xe / 'MacOS/libigc.dylib').read_bytes()
    mtl = package / 'payload/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents'
    patches = {
        'MTL': v.compare_code(v.DONOR / 'sle_Internal/sle/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsMTLDriver', mtl / 'MacOS/AppleIntelTGLGraphicsMTLDriver', OLD / 'macos/mtl17-patches.json'),
        'old_plugin': v.compare_code(v.DONOR / 'sle_Internal/sle/AppleIntelGraphicsShared.bundle/Contents/MacOS/libMTLIGCCompilerPlugin.dylib', xe / 'MacOS/libMTLIGCCompilerPluginOld.dylib', OLD / 'macos/plugin-old-patches.json', skip=(1864,))}
    resources = []
    for p in (v.DONOR / 'sle_Internal/sle/AppleIntelGraphicsShared.bundle/Contents/Resources').iterdir():
        assert sha(p) == sha(xe / 'Resources' / p.name)
        resources.append(p.name)
    assert sha(v.DONOR / 'sle_Internal/sle/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/Resources/runtime.gpuencode.split') == sha(xe / 'Resources/runtime.gpuencode.split')
    resources.append('runtime.gpuencode.split')
    changed = subprocess.check_output(['git', 'diff', '--name-only', 'UPSTREAM_BASE', '--', 'src', 'macos', 'build-nootedgreen.sh', 'build-hookcase.sh'], cwd=OLD, text=True).splitlines()
    assert changed == ['src/NootedGreen/kern_gen11.cpp']
    for rel in ['efi-add', 'payload/Library/Extensions', 'payload/Library/GPUBundles', 'payload/System/Library/Caches/xe.bundle', 'config-proposal']:
        assert (package / rel).is_dir()
    report = {'status': 'STATIC_PACKAGE_RECHECK_PASS_NOT_RUNTIME', 'archive_bytes': archive.stat().st_size, 'archive_sha256': EXPECTED, 'files_and_links': 246, 'embedded_manifest_additional': 1, 'mach_o_count': len(binaries), 'code_pages': pages, 'kexts': versions, 'binaries': binaries, 'patches': patches, 'resources': resources, 'functional_source_delta': changed, 'dependency_inventory': m['dependency_inventory'], 'native_package_codesign': 'NOT_PERFORMED_PACKAGE_NOT_ON_TARGET_NO_REMOTE_WRITE_AUTHORIZATION'}
    (ROOT / 'reports/PACKAGE.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print('PASS: archive, 246 inventory entries + embedded receipt, 31 Mach-O, 51898 pages, upstream patch tables/resources/source preservation')


if __name__ == '__main__':
    main()
