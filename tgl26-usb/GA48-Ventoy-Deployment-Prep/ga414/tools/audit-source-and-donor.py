#!/usr/bin/env python3
"""Audit the complete R6 source delta and the actual 25G83 Apple donor."""
import difflib
import json
import plistlib
import re
from common import *


def array(text, name):
    match = re.search(r'static const uint8_t ' + name + r'\[\] = \{([^}]+)\};', text)
    require(match is not None, 'array must remain static const: ' + name)
    require(text.count('uint8_t ' + name + '[]') == 1, 'duplicate array: ' + name)
    return bytes(int(x, 16) for x in re.findall(r'0x[0-9a-fA-F]+', match.group(1)))


def main():
    before = inventory(R6 / 'source'); after = inventory(WORK / 'source')
    require(before == json.loads((REPORTS / 'R6-SOURCE-INVENTORY.json').read_text()), 'sealed R6 source changed')
    require(before.keys() == after.keys(), 'source files added/removed')
    changed = [name for name in before if before[name] != after[name]]
    rel = 'src/NootedGreen/kern_gen11.cpp'
    require(changed == [rel], 'more than the sole NOAUX source changed')
    old = (R6 / 'source' / rel).read_text(); new = (WORK / 'source' / rel).read_text()
    require(array(old, 'f_noaux') == array(new, 'f_noaux') == FIND, 'find bytes changed')
    require(array(old, 'r_noaux') == array(new, 'r_noaux') == REPLACE, 'replacement bytes changed')
    require([i for i, (a, b) in enumerate(zip(FIND, REPLACE)) if a != b] == [10, 11], 'not only jne→nop')
    require(new.count('LookupPatchPlus const patchNoAux[]') == 1 and
            new.count('LookupPatchPlus::applyAll(patcher, patchNoAux, address, size)') == 1, 'duplicate patch application')
    # All original source remains byte-identical after removing the relocated NOAUX blocks and new-only helpers.
    old_arrays_start = old.index('\t\t\t\t// xe/noaux (19/10):')
    old_arrays_end = old.index('\t\t\t\t// xe/notcf (19/10):', old_arrays_start)
    old_apply_start = old.index('\t\t\t\tif (!checkKernelArgument("-ngreenccs")) {')
    old_apply_end = old.index('\t\t\t\t// xe/rcpolicy (21/10', old_apply_start)
    stripped_old = old[:old_apply_start] + old[old_apply_end:]
    stripped_old = stripped_old[:old_arrays_start] + stripped_old[old_arrays_end:]
    stripped_new = new
    comment = '\t\t\t\t// XE-NOAUX definitions/application moved above; other RPL-only patches stay here.\n'
    stripped_new = stripped_new.replace(comment, '')
    start = stripped_new.index('\t\t\t// GA414: pair the existing NOAUX')
    end = stripped_new.index('\t\t\tif (!NGreen::callback->isRealTGL) {\n\t\t\t\t// RPL-only:', start)
    stripped_new = stripped_new[:start] + stripped_new[end:]
    start = stripped_new.index('\n// GA414: exact-match guard only;')
    end = stripped_new.index('\n// ==== 6 kextInfos:', start)
    stripped_new = stripped_new[:start] + stripped_new[end:]
    require(stripped_old == stripped_new, 'non-NOAUX source changed, including R6 fixes/NODEPTH/RPL logic')
    patch = ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile='a/' + rel, tofile='b/' + rel))
    patch_path = ROOT / 'ga414/patches/GA414-NOAUX-vs-R6.patch'
    if patch_path.exists(): require(patch_path.read_text() == patch, 'archived diff changed')
    else: patch_path.write_text(patch)
    donor = WORK / 'AppleIntelTGLGraphics-25G83'; data = donor.read_bytes()
    info = plistlib.loads((WORK / 'donor-Info.plist').read_bytes())
    require(info['CFBundleShortVersionString'] == '16.0.32' and info['CFBundleVersion'] == '16.0.2', 'unexpected actual donor versions')
    require(data.count(FIND) == 1 and data.count(REPLACE) == 0, 'donor original pattern not unique or already patched')
    b = builder(); symbols = run([b.LLVM_BIN / 'llvm-nm', '-n', donor])
    lines = symbols.splitlines(); symbol = '__ZN15IGAccelResource23fillSurfaceStateAuxInfoEPNS_17ResourceInfoEntryER22SGfxRenderSurfaceState6Intent'
    line = next(line for line in lines if line.endswith(' ' + symbol))
    va = int(line.split()[0], 16); file_offset = data.index(FIND)
    image = macho(data)
    section = next(v for v in image['sections'].values() if v['offset'] <= file_offset < v['offset'] + v['bytes'])
    pattern_va = section['address'] + file_offset - section['offset']
    next_va = min(int(s.split()[0], 16) for s in lines if len(s.split()) >= 3 and re.fullmatch('[0-9a-fA-F]+', s.split()[0]) and int(s.split()[0], 16) > va)
    require(va <= pattern_va and pattern_va + len(FIND) <= next_va, 'pattern outside target function')
    assembly = run([b.LLVM_BIN / 'llvm-objdump', '--disassemble', '--x86-asm-syntax=intel',
                    '--start-address=' + hex(va), '--stop-address=' + hex(next_va), donor])
    (WORK / 'noaux-donor-function.asm').write_text(assembly)
    simulate = bytearray(data); simulate[file_offset:file_offset + len(FIND)] = REPLACE
    require(simulate.count(FIND) == 0 and simulate.count(REPLACE) == 1 and
            [i for i, (x, y) in enumerate(zip(data, simulate)) if x != y] == [file_offset + 10, file_offset + 11], 'offline patch changed extra bytes')
    r6_image = R6 / 'HP-Tahoe-TGL-GA410-R6-POOL.img'
    sealed = json.loads((ROOT / 'ga410/reports/TGL-R6.json').read_text())
    require(sha(r6_image) == sealed['sha256'], 'sealed R6 IMG hash mismatch')
    r = {'status': 'SOURCE_SCOPE_AND_ACTUAL_DONOR_PASS_NOT_RUNTIME', 'changed_files': changed,
         'source_file_count': len(before), 'source_sha256': after, 'baseline_inventory': record(REPORTS / 'R6-SOURCE-INVENTORY.json'),
         'patch': record(patch_path), 'all_non_NOAUX_source_preserved': True, 'NODEPTH_native': 'unchanged: not enabled',
         'const_arrays_verified': True, 'one_application_site': True, 'find': FIND.hex(' '), 'replace': REPLACE.hex(' '),
         'native_gate': 'realTGL, CPU 0x8c, PCI 8086:9a49, subsystem 103c:8716, Tahoe, exact kernel _osversion 25G83',
         'native_runtime_guards': 'atomic first attempt, pre original/patched=1/0, apply count1, post=0/1; original -ngreenccs disables',
         'donor': record(donor), 'donor_version_short': info['CFBundleShortVersionString'], 'donor_version_bundle': info['CFBundleVersion'],
         'donor_UUID': image['uuid'], 'original_count': data.count(FIND), 'replacement_count': data.count(REPLACE),
         'pattern_file_offset': hex(file_offset), 'pattern_virtual_address': hex(pattern_va),
         'target_function': symbol, 'function_start': hex(va), 'function_end_next_symbol': hex(next_va),
         'branch_patch_virtual_address': hex(pattern_va + 10), 'actual_function_assembly': record(WORK / 'noaux-donor-function.asm'),
         'offline_simulation_only_two_bytes_changed': True, 'R6_image': record(r6_image),
         'kernel_build_symbol_receipt': record(WORK / 'commands/kernel-build-symbol-and-volume.json'),
         'runtime_applied': False}
    path = REPORTS / 'SOURCE-AND-DONOR.json'
    if path.exists(): require(json.loads(path.read_text()) == r, 'saved audit differs')
    else: save(path, r)
    print(json.dumps({k: r[k] for k in ['status', 'changed_files', 'original_count', 'pattern_file_offset', 'branch_patch_virtual_address', 'native_gate']}))


if __name__ == '__main__':
    main()
