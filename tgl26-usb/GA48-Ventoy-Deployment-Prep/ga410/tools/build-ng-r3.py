#!/usr/bin/env python3
"""Build an isolated R3 NG: keep f13b and page-align the real-TGL Blit3D scratch allocation."""
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[1]
GA47 = ROOT.parent.parent / 'GA47-JulioNectar-HP-Port'
WORK = ROOT / 'private/ng-r3'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def main():
    assert not subprocess.run(['git', 'status', '--porcelain'], cwd=GA47, capture_output=True, text=True, check=True).stdout
    r2 = ROOT / 'private/ng-r2/source'
    r2_report = json.loads((ROOT / 'reports/NG-R2-BUILD.json').read_text())
    assert sha(r2 / 'src/NootedGreen/kern_gen11.cpp') == r2_report['source_after_sha256']
    WORK.mkdir()
    source = WORK / 'source'
    shutil.copytree(r2, source)
    before = inventory(r2)
    path = source / 'src/NootedGreen/kern_gen11.cpp'
    text = path.read_text()
    anchor = '\tuint64_t ret = FunctionCast(IGHardwareExtendedContextinitWithOptions, callback->oIGHardwareExtendedContextinitWithOptions)(that,param_1,param_2);'
    assert text.count(anchor) == 1
    addition = '''\t// HP-R3: 25G83 + the 16.0.2 TGL accelerator faults at scratch+0xd000
\t// while copying 0x44 bytes; its static Blit3D params request 0xd240 bytes.
\t// Pass a page-rounded size to the existing allocator, retaining Apple's
\t// complete scratch shader/state initialization and its normal return value.
\t// Both initWithOptions bodies consume (and do not retain) this 0x38-byte
\t// params record; use a per-call copy so concurrent contexts share no edits.
\tuint64_t hpR3BlitParams[7];
\tconst bool hpR3Align = NGreen::callback->isRealTGL &&
\t\tgetKernelVersion() == KernelVersion::Tahoe && param_2 &&
\t\treinterpret_cast<mach_vm_address_t>(param_2) == callback->Blit3DExtendedCtxParams &&
\t\tp2f10 == 0xd240;
\tif (hpR3Align) {
\t\tmemcpy(hpR3BlitParams, param_2, sizeof(hpR3BlitParams));
\t\thpR3BlitParams[2] = 0xe000;
\t\tparam_2 = hpR3BlitParams;
\t\tSYSLOG("ngreen", "HP-R3: Blit3D scratch allocation 0xd240 -> 0xe000 ctx=%p", that);
\t}
'''
    updated = text.replace(anchor, addition + anchor + '''
\tif (hpR3Align) {
\t\tvoid *scratch = getMember<void *>(that, 0xd8);
\t\tSYSLOG("ngreen", "HP-R3: Blit3D init returned %llu scratch=%p size=0x%llx",
\t\t\t(unsigned long long)ret, scratch,
\t\t\t(unsigned long long)(scratch ? getMember<uint64_t>(scratch, 0x20) : 0));
\t}''')
    path.write_text(updated)
    after = inventory(source)
    assert before.keys() == after.keys()
    changed = [p for p in before if before[p] != after[p]]
    assert changed == ['src/NootedGreen/kern_gen11.cpp']
    patch = ''.join(difflib.unified_diff(text.splitlines(True), updated.splitlines(True),
                     fromfile='a/src/NootedGreen/kern_gen11.cpp', tofile='b/src/NootedGreen/kern_gen11.cpp', n=0))
    tracked = ROOT / 'patches/NG-R3-align-blit-scratch.patch'
    tracked.write_text(patch)
    (WORK / 'actual-source.patch').write_text(patch)
    spec = importlib.util.spec_from_file_location('ga47_builder', GA47 / 'hp-port/build-offline.py')
    builder = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(builder)
    builder.ROOT = source
    builder.OUT = WORK / 'build'
    builder.BUILD = builder.OUT / 'product'
    builder.kext('NootedGreen')
    bundle = builder.BUILD / 'NootedGreen.kext'
    binary = bundle / 'Contents/MacOS/NootedGreen'
    data = binary.read_bytes()
    assert b'HP-R3: Blit3D scratch allocation 0xd240 -> 0xe000' in data
    assert bytes.fromhex('ff9090010000498b0e4c89f789c6ff9138010000') in data
    assert bytes.fromhex('c7c001000000498b0e4c89f789c6ff9138010000') in data
    assert not subprocess.run(['git', 'status', '--porcelain'], cwd=GA47, capture_output=True, text=True, check=True).stdout
    archive = WORK / 'NootedGreen-R3.tar.gz'
    with tarfile.open(archive, 'x:gz') as tar:
        tar.add(bundle, arcname='NootedGreen.kext')
    report = {'status': 'NG_R3_CROSS_BUILD_COMPLETE_NATIVE_SIGNING_PENDING',
              'source_baseline': str(GA47), 'source_baseline_unchanged': True,
              'functional_delta': 'Keep R2 f13b; pass per-call 0x38-byte Blit3D params copy with scratch size 0xd240 -> 0xe000 on real TGL/Tahoe only',
              'all_original_scratch_initialization_preserved': True,
              'R3_patch_sha256': sha(tracked), 'R2_source_sha256': sha(r2 / 'src/NootedGreen/kern_gen11.cpp'),
              'recipe_sha256': sha(GA47 / 'hp-port/build-offline.py'),
              'source_files': len(before), 'changed_source_files': changed,
              'source_after_sha256': sha(path), 'binary_sha256_before_native_signing': sha(binary),
              'binary_bytes': binary.stat().st_size, 'archive': str(archive.relative_to(ROOT.parent)),
              'archive_sha256': sha(archive), 'native_signing_verified': False, 'runtime_fix_verified': False}
    (ROOT / 'reports/NG-R3-BUILD.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
