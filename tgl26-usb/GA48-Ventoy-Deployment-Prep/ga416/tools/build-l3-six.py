#!/usr/bin/env python3
"""Build isolated GA416 L3-only experiment with the pinned GA414 toolchain."""
import contextlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga416/private/l3-six'
REPORTS = ROOT / 'ga416/reports'
SOURCE = ROOT.parent / 'GA416-L3-6-Source'
BASE_SOURCE = ROOT / 'ga414/private/source'
SPEC = importlib.util.spec_from_file_location('ga414_common', ROOT / 'ga414/tools/common.py')
c = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(c)


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    old = c.inventory(BASE_SOURCE / 'src/NootedGreen')
    new = c.inventory(SOURCE / 'src/NootedGreen')
    changed = [name for name in old if old[name] != new[name]]
    assert old.keys() == new.keys() and changed == ['kern_gen11.cpp']
    assert c.run(['git', '-C', SOURCE, 'diff', '--name-only', 'HEAD^', 'HEAD']).splitlines() == ['src/NootedGreen/kern_gen11.cpp']
    baseline = (BASE_SOURCE / 'src/NootedGreen/kern_gen11.cpp').read_text()
    current = (SOURCE / 'src/NootedGreen/kern_gen11.cpp').read_text()
    start = baseline.index('\t\t// The donor\'s L3 switch')
    end = baseline.index('\n\t\tSYSLOG("ngreen", "HP-R5: native TGL topology', start)
    now_end = current.index('\n\t\tSYSLOG("ngreen", "HP-R5: native TGL topology', start)
    assert baseline[:start] == current[:start] and baseline[end:] == current[now_end:]
    # Strip comments/logging: exactly one functional statement changes.
    def functional(text):
        return '\n'.join(l for l in text.splitlines() if not l.strip().startswith(('//', 'SYSLOG(')))
    assert functional(current[start:now_end]) == functional(baseline[start:end]).replace(
        'getMember<UInt32>(that, 0x1164) = 8;', 'getMember<UInt32>(that, 0x1164) = 6;', 1)
    assert c.run(['git', '-C', SOURCE, 'status', '--porcelain']) == ''
    commit = c.run(['git', '-C', SOURCE, 'rev-parse', 'HEAD']).strip()
    patch = c.run(['git', '-C', SOURCE, 'diff', 'HEAD^', 'HEAD', '--', 'src/NootedGreen/kern_gen11.cpp'])
    (REPORTS / 'GA416-L3-6.patch').write_text(patch)
    c.save(REPORTS / 'L3-6-SOURCE.json', {
        'status': 'SOURCE_PATCHED', 'source_worktree': str(SOURCE), 'source_commit': commit,
        'baseline_commit': c.run(['git', '-C', SOURCE, 'rev-parse', 'HEAD^']).strip(),
        'changed_source_files': changed, 'only_functional_statement': 'IGAccelDevice+0x1164 fallback 8 -> 6',
        'gate_unchanged': True, 'gate_note': 'Existing real-TGL/Tahoe/GT2/1slice/10SS/8EUperSS/80EU/nativeL3=0 gate retained exactly. This branch did not itself contain a PCI/subsystem/build gate; separate NOAUX HP/25G83 gate remains unchanged.',
        'original_call_and_early_return_unchanged': True, 'RPL_gate_unchanged': True,
        'all_other_src_files_identical_to_sealed_GA414': True,
        'source_inventory': new, 'diff': c.record(REPORTS / 'GA416-L3-6.patch'),
        'static_fuse_evidence': c.record(REPORTS / 'HP-L3-FUSE-RESULT.json'),
        'runtime_logs_use_actual_GPUInfo_fields': True, 'runtime_fuse_read_added': False})
    assert c.sha(c.RECIPE) == json.loads((ROOT / 'ga410/reports/NG-R6-BUILD.json').read_text())['recipe_sha256']
    out = WORK / 'build'; out.mkdir()
    b = c.builder(); b.ROOT, b.OUT, b.BUILD = SOURCE, out, out / 'product'
    with (WORK / 'compile.log').open('x') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        def run(*args, **kw):
            print('+', ' '.join(map(str, args)), flush=True)
            return subprocess.run(list(map(str, args)), check=True, stdout=log, stderr=log, **kw)
        b.run = run
        b.kext('NootedGreen')
    bundle = b.BUILD / 'NootedGreen.kext'; binary = bundle / 'Contents/MacOS/NootedGreen'
    data = binary.read_bytes(); macho = c.macho(data)
    old_bundle = ROOT / 'ga414/private/native-signed/NootedGreen.kext'
    old_binary = old_bundle / 'Contents/MacOS/NootedGreen'
    assert macho['filetype'] == 0xb and macho['uuid'] != c.macho(old_binary.read_bytes())['uuid']
    assert (bundle / 'Contents/Info.plist').read_bytes() == (old_bundle / 'Contents/Info.plist').read_bytes()
    for marker in [b'GA414 NOAUX: postflight', b'HP-R6: real TGL/Tahoe upstream pool',
                   b'XE-NOCCS3:', b'XeNG PLANES2:', b'HP-R5: native TGL topology',
                   b'HP-R3: Blit3D scratch allocation', b'HP-GA416: L3 override %u -> %u',
                   b'HP-GA416: effective L3BankCount = %u', b'prior static evidence, not a runtime fuse read']:
        assert marker in data, marker
    assert c.FIND in data and c.REPLACE in data
    undefined = c.run([b.LLVM_BIN / 'llvm-nm', '-uj', binary]).splitlines()
    old_undefined = c.run([b.LLVM_BIN / 'llvm-nm', '-uj', old_binary]).splitlines()
    assert set(undefined) <= set(old_undefined)
    symbols = c.run([b.LLVM_BIN / 'llvm-nm', binary]); (WORK / 'symbols.txt').write_text(symbols)
    for symbol in ['_NootedGreen_kern_start', '_NootedGreen_kern_stop', '_kmod_info']:
        assert symbol in symbols
    for label, args in [('signature-info', [b.SIGN, 'print-signature-info', bundle]),
                        ('signature-verify', [b.SIGN, 'verify', binary]),
                        ('macho-file', ['file', binary]),
                        ('macho-headers', [b.LLVM_BIN / 'llvm-objdump', '--macho', '--private-headers', binary])]:
        result = subprocess.run(list(map(str, args)), capture_output=True, text=True)
        c.save(WORK / (label+'.json'), {'command': list(map(str,args)), 'returncode': result.returncode,
                                       'stdout':result.stdout, 'stderr':result.stderr})
    archive = WORK / 'NootedGreen-GA416-L3-6-cross-signed.tar.gz'
    with tarfile.open(archive, 'x:gz') as stream: stream.add(bundle, arcname='NootedGreen.kext')
    c.save(REPORTS / 'L3-6-BUILD.json', {
        'status': 'KEXT_BUILT_CROSS_SIGNED', 'MachO': macho, 'binary': c.record(binary),
        'source_commit':commit, 'bundle_inventory': c.inventory(bundle), 'recipe': c.record(c.RECIPE),
        'compile_log': c.record(WORK/'compile.log'), 'signature_tool': c.record(b.SIGN),
        'Info_plist_identical_to_PLANES2': True, 'new_undefined_symbols': [],
        'NOAUX_NOCCS3_PLANES2_R6_R5_R3_markers_present': True,
        'archive': c.record(archive), 'native_codesign_strict': 'NOT_RUN_MACOS_UNAVAILABLE',
        'runtime': 'NOT_TESTED'})
    print(json.dumps({'status': 'KEXT_BUILT_CROSS_SIGNED', 'MachO_UUID': macho['uuid'], 'binary_sha256': c.sha(binary)}))


if __name__ == '__main__': main()
