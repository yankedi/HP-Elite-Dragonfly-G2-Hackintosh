#!/usr/bin/env python3
"""Rebuild independent NG copy with exactly the upstream f13b application enabled."""
import difflib
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GA47 = ROOT.parent.parent / 'GA47-JulioNectar-HP-Port'
WORK = ROOT / 'private/ng-r2'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--finish-compiled', action='store_true', help='Finish checks on the already compiled same-source artifact')
    args = parser.parse_args()
    assert not subprocess.run(['git', 'status', '--porcelain'], cwd=GA47, capture_output=True, text=True, check=True).stdout
    WORK.mkdir(exist_ok=args.finish_compiled)
    source = WORK / 'source'
    if not args.finish_compiled:
        shutil.copytree(GA47 / 'src/NootedGreen', source / 'src/NootedGreen')
    before = {'src/NootedGreen/' + p: h for p, h in inventory(GA47 / 'src/NootedGreen').items()}
    path = source / 'src/NootedGreen/kern_gen11.cpp'
    text = (GA47 / 'src/NootedGreen/kern_gen11.cpp').read_text()
    lines = [line for line in text.splitlines(keepends=True)
             if '{activeKext, f13b, r13b, arrsize(f13b),' in line]
    assert len(lines) == 1 and lines[0].lstrip().startswith('//')
    replacement = '\t\t\t\t{activeKext, f13b, r13b, arrsize(f13b),\t1},\n'
    updated = text.replace(lines[0], replacement)
    if args.finish_compiled:
        assert path.read_text() == updated
    else:
        path.write_text(updated)
    after = inventory(source)
    changed = [p for p in before if before[p] != after[p]]
    assert changed == ['src/NootedGreen/kern_gen11.cpp'] and before.keys() == after.keys()
    delta = ''.join(difflib.unified_diff(text.splitlines(True), updated.splitlines(True),
                                       fromfile='a/src/NootedGreen/kern_gen11.cpp',
                                       tofile='b/src/NootedGreen/kern_gen11.cpp'))
    (WORK / 'actual-source.patch').write_text(delta)
    tracked = ROOT / 'patches/NG-R2-enable-upstream-f13b.patch'
    # Compare actual removed/added source lines, independent of diff hunk context.
    def edits(diff):
        return [line for line in diff.splitlines() if line[:1] in ['+', '-']
                and not line.startswith(('+++', '---'))]
    assert edits(delta) == edits(tracked.read_text())
    spec = importlib.util.spec_from_file_location('ga47_builder', GA47 / 'hp-port/build-offline.py')
    builder = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(builder)
    recipe_sha = sha(GA47 / 'hp-port/build-offline.py')
    builder.ROOT = source
    builder.OUT = WORK / 'build'
    builder.BUILD = builder.OUT / 'product'
    if not args.finish_compiled:
        builder.kext('NootedGreen')
    bundle = builder.BUILD / 'NootedGreen.kext'
    binary = bundle / 'Contents/MacOS/NootedGreen'
    data = binary.read_bytes()
    find = bytes.fromhex('ff9090010000498b0e4c89f789c6ff9138010000')
    replace = bytes.fromhex('c7c001000000498b0e4c89f789c6ff9138010000')
    assert data.count(find) >= 1 and data.count(replace) >= 1
    # The saved GA47 tree must remain byte-for-byte at its original git state.
    assert not subprocess.run(['git', 'status', '--porcelain'], cwd=GA47, capture_output=True, text=True, check=True).stdout
    archive = WORK / 'NootedGreen-R2.tar.gz'
    import tarfile
    with tarfile.open(archive, 'x:gz') as tar:
        tar.add(bundle, arcname='NootedGreen.kext')
    report = {'status': 'NG_R2_CROSS_BUILD_COMPLETE_NATIVE_SIGNING_PENDING',
              'source_baseline': str(GA47), 'source_baseline_unchanged': True,
              'functional_delta': 'Enable existing upstream f13b/r13b patch application; exactly one source line',
              'actual_source_patch_sha256': sha(WORK / 'actual-source.patch'),
              'recipe_sha256': recipe_sha, 'source_files': len(before), 'changed_source_files': changed,
              'source_before_sha256': before[changed[0]], 'source_after_sha256': after[changed[0]],
              'binary_sha256_before_native_signing': sha(binary), 'binary_bytes': binary.stat().st_size,
              'find_constant_present_in_binary': True, 'replacement_constant_present_in_binary': True,
              'archive': str(archive.relative_to(ROOT.parent)), 'archive_sha256': sha(archive),
              'native_signing_verified': False, 'runtime_fix_verified': False}
    (ROOT / 'reports/NG-R2-BUILD.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
