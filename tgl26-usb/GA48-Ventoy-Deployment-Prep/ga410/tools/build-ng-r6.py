#!/usr/bin/env python3
"""Enable upstream pool sizing/alignment on real TGL/Tahoe without all xefix patches."""
import difflib
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('build_helpers', Path(__file__).with_name('build-ng-r4.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
ROOT, GA47 = h.ROOT, h.GA47
WORK = ROOT / 'private/ng-r6'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rebuild-prepared', action='store_true')
    rebuild = parser.parse_args().rebuild_prepared
    assert not subprocess.run(['git', 'status', '--porcelain'], cwd=GA47, capture_output=True, text=True, check=True).stdout
    prior = ROOT / 'private/ng-r5/source'
    previous = json.loads((ROOT / 'reports/NG-R5-BUILD.json').read_text())
    assert h.sha(prior / 'src/NootedGreen/kern_gen11.cpp') == previous['source_after_sha256']
    WORK.mkdir(exist_ok=rebuild)
    source = WORK / 'source'
    if not rebuild:
        shutil.copytree(prior, source)
    rel = 'src/NootedGreen/kern_green.cpp'
    path = source / rel
    text = (prior / rel).read_text()
    anchor = '\tif (fixArg < 0) fixArg = (checkKernelArgument("-ngreenxefix") && !checkKernelArgument("-ngreennopoolfix")) ? 1 : 0;'
    assert text.count(anchor) == 2
    replacement = '''	// HP-R6: the Tahoe 4KB command-pool mismatch also affects real TGL.
	// Reuse only the upstream sizing/alignment algorithm below; preserve
	// -ngreennopoolfix and do not turn on unrelated RPL-only xefix paths.
	if (fixArg < 0) {
		const bool hpTglTahoe = NGreen::callback && NGreen::callback->getIsRealTGL() &&
			getKernelVersion() == KernelVersion::Tahoe;
		fixArg = ((checkKernelArgument("-ngreenxefix") || hpTglTahoe) &&
			!checkKernelArgument("-ngreennopoolfix")) ? 1 : 0;
		if (hpTglTahoe) IOLog("HP-R6: real TGL/Tahoe upstream pool sizing/alignment enabled=%d\\n", fixArg);
	}'''
    updated = text.replace(anchor, replacement)
    if rebuild:
        failed_source = text.replace(anchor, replacement.replace('->getIsRealTGL()', '->isRealTGL'))
        assert path.read_text() in (updated, failed_source)
    path.write_text(updated)
    before, after = h.inventory(prior), h.inventory(source)
    assert before.keys() == after.keys()
    changed = [p for p in before if before[p] != after[p]]
    assert changed == [rel]
    delta = ''.join(difflib.unified_diff(text.splitlines(True), updated.splitlines(True), fromfile='a/'+rel, tofile='b/'+rel))
    patch = ROOT / 'patches/NG-R6-upstream-pool-real-tgl-tahoe.patch'
    patch.write_text(delta)
    (WORK / 'actual-source.patch').write_text(delta)
    builder_spec = importlib.util.spec_from_file_location('ga47_builder', GA47 / 'hp-port/build-offline.py')
    builder = importlib.util.module_from_spec(builder_spec)
    builder_spec.loader.exec_module(builder)
    builder.ROOT, builder.OUT, builder.BUILD = source, WORK/'build', WORK/'build/product'
    builder.kext('NootedGreen')
    bundle = builder.BUILD / 'NootedGreen.kext'
    binary = bundle / 'Contents/MacOS/NootedGreen'
    data = binary.read_bytes()
    assert b'HP-R6: real TGL/Tahoe upstream pool' in data
    assert b'HP-R5: native TGL topology' in data and b'HP-R3: Blit3D scratch allocation' in data
    assert bytes.fromhex('31c0c3e54157415641554154534883ec48488975c0f68778') in data
    archive = WORK / 'NootedGreen-R6.tar.gz'
    with tarfile.open(archive, 'x:gz') as tar:
        tar.add(bundle, arcname='NootedGreen.kext')
    report = {
        'status': 'NG_R6_CROSS_BUILD_COMPLETE_NATIVE_SIGNING_PENDING',
        'source_baseline': str(GA47), 'source_baseline_unchanged': True,
        'functional_delta': 'Retain R5; enable unchanged upstream XE-POOL size floors and POOLALIGN 64-byte padding on real TGL/Tahoe independently of -ngreenxefix. Preserve -ngreennopoolfix.',
        'upstream_algorithms_unchanged': True,
        'size_policy': 'count<=16: minimum 0x20000 bytes; larger count: minimum 0x4000; original 0x10000 pools retained.',
        'alignment_policy': 'Original upstream getBufferPtrNoInc wrapper pads reservations >=0x400 dwords to 64 bytes when the current buffer has room.',
        'R6_patch_sha256': h.sha(patch), 'prior_source_sha256': h.sha(prior/rel),
        'prior_topology_source_sha256': h.sha(prior/'src/NootedGreen/kern_gen11.cpp'),
        'recipe_sha256': h.sha(GA47/'hp-port/build-offline.py'),
        'source_files': len(before), 'changed_source_files': changed,
        'source_after_sha256': h.sha(path), 'binary_sha256_before_native_signing': h.sha(binary),
        'binary_bytes': binary.stat().st_size, 'archive': str(archive.relative_to(ROOT.parent)),
        'archive_sha256': h.sha(archive), 'native_signing_verified': False, 'runtime_fix_verified': False,
    }
    assert not subprocess.run(['git', 'status', '--porcelain'], cwd=GA47, capture_output=True, text=True, check=True).stdout
    (ROOT/'reports/NG-R6-BUILD.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
