#!/usr/bin/env python3
"""Retain R3 and enable the existing upstream NOCCS3 on real TGL/Tahoe."""
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
GA47 = ROOT.parent.parent / 'GA47-JulioNectar-HP-Port'
WORK = ROOT / 'private/ng-r4'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def main():
    assert not subprocess.run(['git', 'status', '--porcelain'], cwd=GA47, capture_output=True, text=True, check=True).stdout
    prior = ROOT / 'private/ng-r3/source'
    report3 = json.loads((ROOT / 'reports/NG-R3-BUILD.json').read_text())
    assert sha(prior / 'src/NootedGreen/kern_gen11.cpp') == report3['source_after_sha256']
    WORK.mkdir()
    source = WORK / 'source'
    shutil.copytree(prior, source)
    path = source / 'src/NootedGreen/kern_gen11.cpp'
    text = path.read_text()
    start = text.index('\t\t\t\t// xe/noccs3 (19/10):')
    end = text.index('\t\t\t\t// xe/fmt (19/10):', start)
    definitions = text[start:end]
    apply_start = text.index('\t\t\t\tLookupPatchPlus const patchNoCCS3[]')
    apply_end = text.index('\t\t\t\t// xe/nodepth (20/10):', apply_start)
    application = text[apply_start:apply_end]
    assert 'LookupPatchPlus::applyAll(patcher, patchNoCCS3, address, size)' in application
    updated = text[:apply_start] + text[apply_end:]
    updated = updated[:start] + updated[end:]
    anchor = '\t\t\tif (!NGreen::callback->isRealTGL) {\n\t\t\t\t// RPL-only: hardcode topology and bypass BCS readiness check'
    assert updated.count(anchor) == 1
    block = ('\t\t\t// HP-R4: resolve_ccs+0xc7 also faults on real TGL with Tahoe IOAF2.\n'
             '\t\t\t// Reuse upstream NOCCS3 independently of RPL topology overrides.\n'
             '\t\t\tif (!NGreen::callback->isRealTGL || getKernelVersion() == KernelVersion::Tahoe) {\n'
             + definitions + application + '\t\t\t}\n\n')
    updated = updated.replace(anchor, block + anchor)
    path.write_text(updated)
    before, after = inventory(prior), inventory(source)
    assert before.keys() == after.keys()
    changed = [p for p in before if before[p] != after[p]]
    assert changed == ['src/NootedGreen/kern_gen11.cpp']
    assert updated.count('static const uint8_t f_noccs3[]') == 1
    assert updated.count('LookupPatchPlus const patchNoCCS3[]') == 1
    delta = ''.join(difflib.unified_diff(text.splitlines(True), updated.splitlines(True),
                    fromfile='a/src/NootedGreen/kern_gen11.cpp', tofile='b/src/NootedGreen/kern_gen11.cpp', n=0))
    patch = ROOT / 'patches/NG-R4-upstream-noccs3-tahoe.patch'
    patch.write_text(delta)
    (WORK / 'actual-source.patch').write_text(delta)
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('ga47_builder', GA47 / 'hp-port/build-offline.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.ROOT = source
    builder.OUT = WORK / 'build'
    builder.BUILD = builder.OUT / 'product'
    builder.kext('NootedGreen')
    bundle = builder.BUILD / 'NootedGreen.kext'
    binary = bundle / 'Contents/MacOS/NootedGreen'
    data = binary.read_bytes()
    find = bytes.fromhex('554889e54157415641554154534883ec48488975c0f68778')
    replace = bytes.fromhex('31c0c3e54157415641554154534883ec48488975c0f68778')
    assert find in data and replace in data and b'HP-R3: Blit3D scratch allocation' in data
    assert not subprocess.run(['git', 'status', '--porcelain'], cwd=GA47, capture_output=True, text=True, check=True).stdout
    archive = WORK / 'NootedGreen-R4.tar.gz'
    with tarfile.open(archive, 'x:gz') as tar:
        tar.add(bundle, arcname='NootedGreen.kext')
    report = {'status': 'NG_R4_CROSS_BUILD_COMPLETE_NATIVE_SIGNING_PENDING',
              'source_baseline': str(GA47), 'source_baseline_unchanged': True,
              'functional_delta': 'Retain f13b and R3 allocation alignment; move unchanged upstream NOCCS3 definitions/application out of RPL-only topology block, enabled for real TGL on Tahoe',
              'NOCCS3_semantics': 'Skip IntelAccelerator::submitCCSResolve with upstream xor eax,eax; ret; compression/AUX enable path remains present. CCS resolve correctness not verified.',
              'R4_patch_sha256': sha(patch), 'R3_source_sha256': sha(prior / 'src/NootedGreen/kern_gen11.cpp'),
              'recipe_sha256': sha(GA47 / 'hp-port/build-offline.py'), 'source_files': len(before),
              'changed_source_files': changed, 'source_after_sha256': sha(path),
              'binary_sha256_before_native_signing': sha(binary), 'binary_bytes': binary.stat().st_size,
              'archive': str(archive.relative_to(ROOT.parent)), 'archive_sha256': sha(archive),
              'native_signing_verified': False, 'runtime_fix_verified': False}
    (ROOT / 'reports/NG-R4-BUILD.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
