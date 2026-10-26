#!/usr/bin/env python3
"""Read-only precise NHI HAL function fragments from sealed25G83 KC."""
import bisect
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
GA35 = ROOT.parents[1] / 'GA35-Driver-Reversing'
sys.dont_write_bytecode = True
sys.path.insert(0, str(GA35 / 'tools'))
from macho import Image
from disassemble import Decoder, LIB

path = GA35 / 'inputs/macos-readonly/System/Library/KernelCollections/BootKernelExtensions.kc'
data = path.read_bytes()
root = Image(data)
entry = next(e for e in root.entries if e['name'] == 'com.apple.driver.AppleThunderboltNHI')
image = Image(data, entry['fileoff'], entry['name'])
assert image.uuid == '12CDD634-0946-3FCE-89CC-3901A975E66C'
syms = image.code_symbols()
addresses = sorted(set(s['value'] for s in syms))
names = {}
for s in image.symbols():
    if s['type'] & 0xe != 0xe or s['type'] & 0xe0:
        continue
    names.setdefault(s['value'], []).append(s['name'])
decoder = Decoder()
report = {'kc_path': str(path), 'kc_sha256': hashlib.sha256(data).hexdigest(),
          'nhi_uuid': image.uuid, 'decoder_library_sha256': hashlib.sha256(LIB.read_bytes()).hexdigest(),
          'scope': 'Linear symbol-bounded fragments; not complete CFG, register validation or HP execution',
          'functions': []}
try:
    for s in syms:
        if s['name'] not in ['__ZN19AppleThunderboltHAL5startEP9IOService',
                             '__ZN19AppleThunderboltHAL9createNHIEv',
                             '__ZN24AppleThunderboltHALType45startEP9IOService',
                             '__ZN24AppleThunderboltHALType49createNHIEv',
                             '__ZN27AppleThunderboltIntelPCIHAL5startEP9IOService',
                             '__ZN26AppleThunderboltGenericHAL5startEP9IOService',
                             '__ZN26AppleThunderboltGenericHAL9createNHIEv',
                             '__ZN27AppleThunderboltIntelPCIHAL14unpoweredStartEv',
                             '__ZN26AppleThunderboltGenericHAL5probeEP9IOServicePi',
                             '__ZN26AppleThunderboltGenericHAL14unpoweredStartEv']:
            continue
        idx = bisect.bisect_right(addresses, s['value'])
        sec = next(sec for sec in image.sections if sec['name'] == '__text' and
                   sec['addr'] <= s['value'] < sec['addr'] + sec['size'])
        end = min(addresses[idx] if idx < len(addresses) else sec['addr'] + sec['size'], sec['addr'] + sec['size'])
        start = image.va_to_offset(s['value'], end - s['value'])
        code = data[start:start + end - s['value']]
        instructions = decoder.decode(code, s['value'])
        assert sum(i['size'] for i in instructions) == len(code)
        for i in instructions:
            rip = re.search(r'\[rip ([+-]) (0x[0-9a-f]+)\]', i['operands'])
            if rip:
                target = i['va'] + i['size'] + int(rip.group(2), 16) * (1 if rip.group(1) == '+' else -1)
                i['rip_target_va'] = hex(target)
                if target in names:
                    i['rip_target_symbols'] = names[target]
                cstring = next((sec for sec in image.sections if sec['name'] == '__cstring' and
                    sec['addr'] <= target < sec['addr'] + sec['size']), None)
                if cstring:
                    off = image.va_to_offset(target)
                    end_string = data.find(b'\0', off, off + min(1024, cstring['addr'] + cstring['size'] - target))
                    if end_string >= off:
                        i['rip_target_cstring'] = data[off:end_string].decode('utf-8', 'replace')
            if i['operands'].startswith('0x'):
                try:
                    target = int(i['operands'], 16)
                except ValueError:
                    continue
                if target in names:
                    i['target_symbols'] = names[target]
        report['functions'].append({'symbol': s['name'], 'va': hex(s['value']), 'fileoff': start,
            'length': len(code), 'sha256': hashlib.sha256(code).hexdigest(), 'instructions': instructions})
finally:
    decoder.close()
assert len(report['functions']) == 10
type4 = next(f for f in report['functions'] if f['symbol'] == '__ZN24AppleThunderboltHALType49createNHIEv')
ops = [(i['mnemonic'], i['operands']) for i in type4['instructions']]
assert ('mov', 'eax, 0xffff75f3') in ops and ('add', 'eax, dword ptr [rdi + 0x90]') in ops
assert ('cmp', 'eax, 0xa') in ops and ('mov', 'ecx, 0x405') in ops and ('bt', 'ecx, eax') in ops
selector_values = [v for v in range(0x10000)
                   if (v + 0xffff75f3) & 0xffffffff <= 0xa
                   and (0x405 >> ((v + 0xffff75f3) & 0xffffffff)) & 1]
assert selector_values == [0x8a0d, 0x8a0f, 0x8a17]
report['type4_createNHI_selector'] = {
    'this_field_offset': '0x90', 'accepted_16bit_values': [hex(v) for v in selector_values],
    '9a1b_enters_specialized_allocation_branch': 0x9a1b in selector_values,
    'field_source': 'GenericHAL::unpoweredStart reads provider device-id OSData into this+0x90; vendor-id into+0x94',
    'specialized_metaclass': 'AppleThunderboltNHIType4::metaClass',
    'fallback_vtable': 'AppleThunderboltIntelPCIHAL',
    'boundary': 'Property source and direct metaclass/vtable symbols verified; no proof of all indirect targets, hardware registers or HP functionality',
}
generic_init = next(f for f in report['functions'] if 'GenericHAL14unpoweredStart' in f['symbol'])
assert any(i.get('rip_target_cstring') == 'device-id' for i in generic_init['instructions'])
assert any(i['mnemonic'] == 'mov' and i['operands'] == 'dword ptr [rbx + 0x90], eax' for i in generic_init['instructions'])
assert any('__ZN24AppleThunderboltNHIType49metaClassE' in i.get('rip_target_symbols', []) for i in type4['instructions'])
out = ROOT / 'private/nhi-function-fragments.json'
out.write_text(json.dumps(report, indent=2) + '\n')
print('Saved', out)
for f in report['functions']:
    print(f['symbol'], f['length'], 'bytes')
