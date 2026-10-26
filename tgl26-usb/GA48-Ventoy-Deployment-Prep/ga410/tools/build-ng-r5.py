#!/usr/bin/env python3
"""Build R5 from R4: preserve the real TGL fuse-derived GPU topology."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('r4_builder', Path(__file__).with_name('build-ng-r4.py'))
r4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r4)
ROOT, GA47 = r4.ROOT, r4.GA47
WORK = ROOT / 'private/ng-r5'


def main():
    assert not subprocess.run(['git', 'status', '--porcelain'], cwd=GA47,
                              capture_output=True, text=True, check=True).stdout
    prior = ROOT / 'private/ng-r4/source'
    report4 = json.loads((ROOT / 'reports/NG-R4-BUILD.json').read_text())
    rel = 'src/NootedGreen/kern_gen11.cpp'
    assert r4.sha(prior / rel) == report4['source_after_sha256']
    WORK.mkdir()
    source = WORK / 'source'
    shutil.copytree(prior, source)
    path = source / rel
    text = path.read_text()
    anchor = '\tFunctionCast(getGPUInfo, callback->ogetGPUInfo)(that);\n'
    assert text.count(anchor) == 1
    addition = '''
	// HP-R5: getGPUInfo already reads TGL's fuse-derived topology and computes
	// its dispatch limits. The RPL override below changed 80 EU / 10 SS into
	// 96 EU / 12 SS after those limits were computed (R4 boot + client trace).
	// Keep the native fields, mirrors, frequencies and masks on real TGL.
	if (NGreen::callback->isRealTGL) {
		const UInt32 slices = getMember<UInt32>(that, 0x115c);
		const UInt32 subslices = getMember<UInt32>(that, 0x1158);
		const UInt32 euPerSS = getMember<UInt32>(that, 0x116c);
		const UInt32 totalEU = getMember<UInt32>(that, 0x1124);
		const UInt32 nativeL3 = getMember<UInt32>(that, 0x1164);
		// The donor's L3 switch accepts 12 SS or a special 4-SS SKU, but
		// leaves L3=0 for this verified 10-SS GT2. Retain R4's existing
		// upstream 8-bank compatibility value only for that exact case.
		// This is a fallback, not a fuse measurement or new EU override.
		if (getKernelVersion() == KernelVersion::Tahoe &&
			getMember<UInt32>(that, 0x1120) == 2 && slices == 1 &&
			subslices == 10 && euPerSS == 8 && totalEU == 80 && nativeL3 == 0) {
			getMember<UInt32>(that, 0x1164) = 8;
			SYSLOG("ngreen", "HP-R5: TGL 80EU donor L3 fallback 0 -> 8 (retained R4 value)");
		}
		SYSLOG("ngreen", "HP-R5: native TGL topology slices=%u subslices=%u maxEU/SS=%u totalEU=%u L3Banks=%u nativeL3=%u mirrors=%u/%u dispatchers=%u",
			slices, subslices, euPerSS, totalEU, getMember<UInt32>(that, 0x1164),
			nativeL3, getMember<UInt32>(that, 0x0dd8), getMember<UInt32>(that, 0x0ddc),
			getMember<UInt32>(that, 0x114c));
		return;
	}
'''
    updated = text.replace(anchor, anchor + addition)
    path.write_text(updated)
    before, after = r4.inventory(prior), r4.inventory(source)
    assert before.keys() == after.keys()
    changed = [p for p in before if before[p] != after[p]]
    assert changed == [rel]
    delta = ''.join(difflib.unified_diff(text.splitlines(True), updated.splitlines(True),
                                       fromfile='a/' + rel, tofile='b/' + rel))
    patch = ROOT / 'patches/NG-R5-preserve-real-tgl-topology.patch'
    patch.write_text(delta)
    (WORK / 'actual-source.patch').write_text(delta)
    builder_spec = importlib.util.spec_from_file_location('ga47_builder', GA47 / 'hp-port/build-offline.py')
    builder = importlib.util.module_from_spec(builder_spec)
    builder_spec.loader.exec_module(builder)
    builder.ROOT, builder.OUT, builder.BUILD = source, WORK / 'build', WORK / 'build/product'
    builder.kext('NootedGreen')
    bundle = builder.BUILD / 'NootedGreen.kext'
    binary = bundle / 'Contents/MacOS/NootedGreen'
    data = binary.read_bytes()
    assert b'HP-R5: native TGL topology' in data
    assert b'HP-R3: Blit3D scratch allocation' in data
    assert bytes.fromhex('31c0c3e54157415641554154534883ec48488975c0f68778') in data
    assert not subprocess.run(['git', 'status', '--porcelain'], cwd=GA47,
                              capture_output=True, text=True, check=True).stdout
    archive = WORK / 'NootedGreen-R5.tar.gz'
    with tarfile.open(archive, 'x:gz') as tar:
        tar.add(bundle, arcname='NootedGreen.kext')
    report = {
        'status': 'NG_R5_CROSS_BUILD_COMPLETE_NATIVE_SIGNING_PENDING',
        'source_baseline': str(GA47), 'source_baseline_unchanged': True,
        'functional_delta': 'Retain R4; real TGL returns after native getGPUInfo, preserving fuse-derived EU/SS topology, mirrors and dispatch limits. Exact Tahoe GT2 1x10x8/80EU L3=0 retains R4 upstream L3=8 fallback.',
        'L3_fallback_is_not_a_hardware_measurement': True,
        'R5_patch_sha256': r4.sha(patch), 'R4_source_sha256': r4.sha(prior / rel),
        'recipe_sha256': r4.sha(GA47 / 'hp-port/build-offline.py'),
        'source_files': len(before), 'changed_source_files': changed,
        'source_after_sha256': r4.sha(path), 'binary_sha256_before_native_signing': r4.sha(binary),
        'binary_bytes': binary.stat().st_size, 'archive': str(archive.relative_to(ROOT.parent)),
        'archive_sha256': r4.sha(archive), 'native_signing_verified': False,
        'runtime_fix_verified': False,
    }
    (ROOT / 'reports/NG-R5-BUILD.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
