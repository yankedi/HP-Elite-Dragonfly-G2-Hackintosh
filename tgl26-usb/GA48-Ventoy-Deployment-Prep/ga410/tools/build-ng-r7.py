#!/usr/bin/env python3
"""Fix the demonstrated Tahoe legacy-surface mode check on native TGL."""
import difflib
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
WORK = ROOT / 'private/ng-r7'


def main():
    assert not subprocess.run(['git', 'status', '--porcelain'], cwd=GA47, capture_output=True, text=True, check=True).stdout
    prior = ROOT/'private/ng-r6/source'
    previous = json.loads((ROOT/'reports/NG-R6-BUILD.json').read_text())
    rel = 'src/NootedGreen/kern_green.cpp'
    assert h.sha(prior/rel) == previous['source_after_sha256']
    assert h.sha(prior/'src/NootedGreen/kern_gen11.cpp') == previous['prior_topology_source_sha256']
    probe = json.loads((ROOT/'private/commands/r6-live-surface-mode-control-check.json').read_text())
    assert probe['returncode'] == 0 and 'SURFACE_MODE_SOFTWARE_VALIDATION_MISMATCH_CONFIRMED' in probe['stdout']
    assert 'mode=0x224 result=0xe00002c2' in probe['stdout'] and 'mode=0x24 result=0x0' in probe['stdout']
    WORK.mkdir()
    source = WORK/'source'
    shutil.copytree(prior, source)
    path = source/rel
    text = path.read_text()
    anchor = '''// V500: IOAccelLegacySurface::set_id_mode(uint32_t id, uint32_t mode) active fix.
// Hardware rejects mode bits covered by 0xff8073c0 with kIOReturnUnsupported.
// On non-TGL (RPL-P spoofed as TGL), strip those bits before the call so the
// GPU task gets a valid scheduling mode instead of silently failing.'''
    comment = '''// V500: IOAccelLegacySurface::set_id_mode(uint32_t id, uint32_t mode).
// Tahoe IOAF2 rejects mode & 0xff8073c0 in software with kIOReturnBadArgument,
// before any hardware access. Preserve the upstream spoofed-CPU normalization.
// HP-R7 additionally handles the exact 0x224 native-TGL/Tahoe mismatch below.'''
    assert text.count(anchor) == 1
    updated = text.replace(anchor, comment)
    anchor = '''    if (NGreen::callback && !NGreen::callback->getIsRealTGL())
        patchedMode = mode & ~0xff8073c0u;  // strip TGL-only preemption/mode bits

    IOReturn ret = FunctionCast(wrapSetIdMode, orgSetIdMode)(that, id, patchedMode);'''
    replacement = '''    if (NGreen::callback && !NGreen::callback->getIsRealTGL())
        patchedMode = mode & ~0xff8073c0u;  // retain the upstream spoofed-CPU behavior
    else if (NGreen::callback && NGreen::callback->getIsRealTGL() &&
             getKernelVersion() == KernelVersion::Tahoe && mode == 0x224u) {
        // The live control probe rejects 0x224 and accepts 0x24 on the same GPU.
        // Clear only rejected bit 9; preserve windowed bit 5 and color depth 4.
        // Call the real implementation and propagate its actual result.
        patchedMode = mode & ~0x200u;
    }

    IOReturn ret = FunctionCast(wrapSetIdMode, orgSetIdMode)(that, id, patchedMode);
    static unsigned int hpModeLogCount = 0;
    if (mode == 0x224u && patchedMode == 0x24u && hpModeLogCount++ < 16)
        SYSLOG("ngreen", "HP-R7: IOAF2 legacy surface mode 0x224->0x24 id=0x%x ret=0x%x", id, ret);'''
    assert updated.count(anchor) == 1
    updated = updated.replace(anchor, replacement)
    path.write_text(updated)
    before, after = h.inventory(prior), h.inventory(source)
    assert before.keys() == after.keys()
    changed = [p for p in before if before[p] != after[p]]
    assert changed == [rel]
    delta = ''.join(difflib.unified_diff(text.splitlines(True), updated.splitlines(True), fromfile='a/'+rel, tofile='b/'+rel))
    patch = ROOT/'patches/NG-R7-native-tgl-tahoe-legacy-surface-mode.patch'
    patch.write_text(delta)
    (WORK/'actual-source.patch').write_text(delta)
    builder_spec = importlib.util.spec_from_file_location('ga47_builder', GA47/'hp-port/build-offline.py')
    builder = importlib.util.module_from_spec(builder_spec)
    builder_spec.loader.exec_module(builder)
    builder.ROOT, builder.OUT, builder.BUILD = source, WORK/'build', WORK/'build/product'
    builder.kext('NootedGreen')
    bundle = builder.BUILD/'NootedGreen.kext'
    binary = bundle/'Contents/MacOS/NootedGreen'
    data = binary.read_bytes()
    assert b'HP-R7: IOAF2 legacy surface mode' in data and b'HP-R6: real TGL/Tahoe upstream pool' in data
    assert b'HP-R5: native TGL topology' in data and b'HP-R3: Blit3D scratch allocation' in data
    assert bytes.fromhex('31c0c3e54157415641554154534883ec48488975c0f68778') in data
    archive = WORK/'NootedGreen-R7.tar.gz'
    with tarfile.open(archive, 'x:gz') as tar:
        tar.add(bundle, arcname='NootedGreen.kext')
    report = {
        'status':'NG_R7_CROSS_BUILD_COMPLETE_NATIVE_SIGNING_PENDING',
        'source_baseline':str(GA47), 'source_baseline_unchanged':True,
        'functional_delta':'Retain R6; on native TGL/Tahoe only, normalize exact IOAF2 legacy surface mode 0x224 to 0x24 before the real set_id_mode call. Propagate its actual result. Other native modes unchanged; upstream spoofed mode mask preserved.',
        'R7_patch_sha256':h.sha(patch), 'prior_source_sha256':h.sha(prior/rel),
        'prior_topology_source_sha256':h.sha(prior/'src/NootedGreen/kern_gen11.cpp'),
        'recipe_sha256':h.sha(GA47/'hp-port/build-offline.py'),
        'control_probe_receipt_sha256':h.sha(ROOT/'private/commands/r6-live-surface-mode-control-check.json'),
        'source_files':len(before), 'changed_source_files':changed, 'source_after_sha256':h.sha(path),
        'binary_sha256_before_native_signing':h.sha(binary), 'binary_bytes':binary.stat().st_size,
        'archive':str(archive.relative_to(ROOT.parent)), 'archive_sha256':h.sha(archive),
        'native_signing_verified':False, 'runtime_fix_verified':False,
    }
    assert not subprocess.run(['git', 'status', '--porcelain'], cwd=GA47, capture_output=True, text=True, check=True).stdout
    (ROOT/'reports/NG-R7-BUILD.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
