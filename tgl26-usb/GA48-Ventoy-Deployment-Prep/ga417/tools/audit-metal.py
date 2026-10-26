#!/usr/bin/env python3
"""Audit the sealed HP Metal binary, without target execution or modification."""
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import re
import struct

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga417/private'
REPORTS = ROOT / 'ga417/reports'
spec = importlib.util.spec_from_file_location('common', ROOT / 'ga414/tools/common.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
EXPECTED = 'e3242693959408c9cef14140df81ce98ff1e04d5dd83aa9aeaddb463271ac65d'
COMMIT = '06986480e4d9c1383e57ad4e8e89213b5f124bc9'


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    bundle = WORK / 'metal-baseline/AppleIntelTGLGraphicsMTLDriver.bundle'
    binary = bundle / 'Contents/MacOS/AppleIntelTGLGraphicsMTLDriver'
    raw = binary.read_bytes()
    assert c.sha(binary) == EXPECTED
    receipt_path = ROOT / 'ga416/private/commands/final-protected-driver-hashes.json'
    receipt = json.loads(receipt_path.read_text())
    assert receipt['returncode'] == 0
    assert EXPECTED + '  /Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsMTLDriver' in receipt['stdout']
    macho = c.macho(raw)
    assert macho['uuid'] == '2B849E57-AC6A-3216-A67B-38E080603585'
    text = macho['sections']['__TEXT,__text']
    assert text['address'] == text['offset']
    assert text['offset'] <= 0x7ed87 < text['offset'] + text['bytes']
    assert raw[0x7ed6b:0x7ed96] == bytes.fromhex(
        '488b1d3eb14100498b3c1e4885ff741b488b0526b1410041803c0600750de87afa010049c7041e00000000')
    # Verify allocation, active-buffer classification and NULL fallback in situ.
    for offset, expected in {
        0x7e9be: '488b05e3b441000f9404037450',
        0x7e9cb: 'bf10200100e839fe0100',
        0x7ea1f: '488d0dfab14100488b09488b04084885c07499',
        0x3cb00: '488b0519d1450048890c03',
    }.items():
        assert raw[offset:offset + len(bytes.fromhex(expected))] == bytes.fromhex(expected), hex(offset)
    asm = (WORK / 'metal-disassembly.txt').read_text().splitlines()
    methods, current = {}, None
    for line in asm:
        if line and not line[0].isspace() and line.endswith(':'):
            current = line[:-1]
            methods[current] = [line]
        elif current:
            methods[current].append(line)
    names = [
        '-[MTLIGAccelCommandBuffer initWithQueue:retainedReferences:synchronousDebugMode:]',
        '-[MTLIGAccelCommandBuffer dealloc]',
        '-[MTLIGAccelCommandBuffer commit]',
        '-[MTLIGAccelCommandQueue initWithDevice:maxCommandBufferCount:]',
        '-[MTLIGAccelCommandQueue dealloc]',
        '-[MTLIGAccelCommandBuffer initContextStateDescriptorForEngine:]',
    ]
    assert all(name in methods for name in names)
    excerpts = []
    for name in names:
        excerpts.extend(methods[name])
    (REPORTS / 'METAL-POSH-DISASSEMBLY.txt').write_text('\n'.join(excerpts) + '\n')
    refs = {}
    for label, symbol, wanted in [
        ('queue_shared', '_OBJC_IVAR_$_MTLIGAccelCommandQueue.m_pPoshUsedAsTarget', [0x3b897, 0x3cb00, 0x7ea1f]),
        ('buffer_private', '_OBJC_IVAR_$_MTLIGAccelCommandBuffer._pPoshUsedAsTarget', [0x7ea0e, 0x7ea32, 0x7ed6b, 0x7eee6, 0x7ef4b, 0x7f063]),
        ('only_active', '_OBJC_IVAR_$_MTLIGAccelCommandBuffer.m_isOnlyActiveCommandBuffer', [0x35bd4, 0x7e9be, 0x7ed7b]),
    ]:
        rows = []
        for method, lines in methods.items():
            for n, line in enumerate(lines):
                if symbol in line:
                    addr = int(re.match(r'\s*([0-9a-f]+):', line)[1], 16)
                    rows.append({'address': hex(addr), 'function': method, 'context': lines[max(0,n-2):n+9]})
        assert [int(row['address'],16) for row in rows] == wanted, label
        refs[label] = rows
    # Confirm ObjC ivar metadata values, not only decompiler field names.
    data = macho['sections']['__DATA,__objc_ivar']
    fields = {}
    for name, addr, expected in [('queue_shared',0x499c20,816),('buffer_private',0x499eb0,648),('only_active',0x499ea8,712)]:
        off = data['offset'] + addr - data['address']
        value = struct.unpack_from('<Q', raw, off)[0]
        assert value == expected
        fields[name] = {'ivar_address':hex(addr), 'value':value, 'object_offset_hex':hex(value)}
    upstream_path = ROOT / 'ga416/private/exa-followup-20261025/posh-fix-commit.json'
    upstream = json.loads(upstream_path.read_text())
    assert upstream['sha'] == COMMIT
    assert sorted(f['filename'] for f in upstream['files']) == ['CHANGELOG.md','macos/mtl17-patches.json','macos/patch-mtl17.py']
    patch = next(f['patch'] for f in upstream['files'] if f['filename'] == 'macos/mtl17-patches.json')
    additions = [line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++')]
    assert json.loads('[' + '\n'.join(additions[:-1]).rstrip(',\n ') + ']') == [{'off':519559,'old':'750d','new':'9090'}]
    (REPORTS / 'POSH-UPSTREAM-DIFF.txt').write_text('\n\n'.join(f['filename']+'\n'+f['patch'] for f in upstream['files'])+'\n')
    # Existing functional patches are a separate baseline, not the upstream rebuild.
    table_path = ROOT.parent / 'GA47-JulioNectar-HP-Port/macos/mtl17-patches.json'
    table = json.loads(table_path.read_text())
    preserved = []
    for entry in table:
        if entry['off'] < text['offset']:
            continue  # load-command/header entries also differ after signing
        off, new = entry['off'], bytes.fromhex(entry['new'])
        assert raw[off:off+len(new)] == new
        preserved.append({'offset':hex(off),'bytes':new.hex()})
    info = plistlib.loads((bundle / 'Contents/Info.plist').read_bytes())
    report = {
        'status':'SAME_POSH_LEAK_CODE_PATH_CONFIRMED_STATICALLY',
        'binary':c.record(binary), 'baseline_bundle_inventory':c.inventory(bundle),
        'CFBundleIdentifier':info['CFBundleIdentifier'],
        'CFBundleShortVersionString':info['CFBundleShortVersionString'],
        'CFBundleVersion':info['CFBundleVersion'], 'MachO':macho,
        'slices':[{'architecture':'x86_64','offset':0,'bytes':len(raw),'thin':True}],
        'latest_sealed_HP_hash_receipt':c.record(receipt_path),
        'receipt_utc':receipt['time_utc'],
        'fresh_installed_readback_this_turn':False,
        'fresh_readback_limit':'HP currently NixOS; sealed package bytes equal the actual macOS installed SHA256 receipt. Recheck installed hash and complete bundle before any manual deployment.',
        'HP_md5_for_upstream_comparison_only':hashlib.md5(raw).hexdigest(),
        'upstream_reported_original_md5':'5e6e9bd2ae8c00e555c33c13830005a9',
        'whole_binary_identical_to_upstream_report':False,
        'upstream_commit':COMMIT, 'upstream_raw_commit_evidence':c.record(upstream_path),
        'upstream_commit_only_functional_change':{'offset':hex(519559),'before':'750d','after':'9090'},
        'patch_location':{'file_offset':'0x7ed87','unslid_vm_address':'0x7ed87','slice_offset':0,'bytes':'750d','branch_target':'0x7ed96','method_start':'0x7ecba','method_end_exclusive':'0x7ee0a'},
        'allocation':{'new_call':'0x7e9d0','requested_bytes':0x12010,'heap_96KiB':'Upstream allocator size-class measurement, not the literal new request size; not measured on HP.'},
        'ivars':fields, 'all_symbolic_ivar_references_in_main_image':refs,
        'queue_lifetime':{'init_zero_store':'0x3cb07','dealloc_delete':'0x3b8a7','dealloc_zero_store':'0x3b8ac','only_other_reference':'0x7ea1f reads shared pointer during buffer init','nonzero_shared_store_found':False},
        'sibling_dylibs_import_POSH_ivar_symbols':False,
        'static_conclusion':'When active count is zero, flag is true; NULL queue shared pointer falls back to private operator new(0x12010). Dealloc skips delete when flag true. Commit decrements active count but never transfers ownership. No nonzero queue shared store among all symbolic references in this image; no sibling dylib imports these ivars. Exact audited build supports upstream two-byte fix.',
        'proof_boundary':'Static code audit of sealed hash-matched image, not a runtime heap measurement or proof against arbitrary external memory writes/runtime swizzling.',
        'existing_compatibility_patch_bytes_verified':preserved,
        'disassembly':c.record(REPORTS/'METAL-POSH-DISASSEMBLY.txt'),
        'dynamic_reproduction_run':False, 'installed_modified':False,
        'pmap_wrong_zone_root_cause_proven':False,
    }
    c.save(REPORTS / 'METAL-POSH-AUDIT.json', report)
    print(json.dumps({k:report[k] for k in ['status','binary','CFBundleShortVersionString','patch_location','fresh_installed_readback_this_turn']},indent=2))


if __name__ == '__main__':
    main()
