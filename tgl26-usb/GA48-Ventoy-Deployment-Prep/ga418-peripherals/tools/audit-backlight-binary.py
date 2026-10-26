#!/usr/bin/env python3
"""Inspect sealed GA416 NGreen init and direct Backlight structure references."""
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
from disassemble import Decoder

path = ROOT.parent / 'ga417/private/rtc/readback-verified/EFI/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen'
data = path.read_bytes()
image = Image(data)
assert image.uuid == '4C4C44D4-5555-3144-A13A-DFB86EFBE513'
symbols = image.symbols()
code = image.code_symbols()
addresses = sorted(set(s['value'] for s in code))
backlight = next(s['value'] for s in symbols if s['name'] == '__ZL13kextBacklight')
backlight_end = min(s['value'] for s in symbols if s['value'] > backlight and
                    s['type'] & 0xe == 0xe and not s['type'] & 0xe0)
assert backlight_end - backlight == 0x28
agdp = next(s['value'] for s in symbols if s['name'] == '__ZL8kextAGDP')
init = next(s['value'] for s in code if s['name'] == '__ZN6NGreen4initEv')
init_end = addresses[bisect.bisect_right(addresses, init)]
decoder = Decoder()
r = {'binary_path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'uuid': image.uuid,
     'backlight_structure_va': hex(backlight), 'agdp_structure_va': hex(agdp),
     'backlight_symbol_bounded_bytes': backlight_end-backlight,
     'init': {'va': hex(init), 'end_va': hex(init_end)}, 'direct_backlight_structure_references': [],
     'partially_decoded_symbol_fragments': []}
try:
    sec = next(s for s in image.sections if s['name'] == '__text')
    # Restart at each real symbol boundary. Linear decoding from section start
    # may desynchronise across alignment/embedded data even if every byte decodes.
    instructions = []
    for ix, addr in enumerate(addresses):
        end = addresses[ix+1] if ix+1 < len(addresses) else sec['addr']+sec['size']
        off = image.va_to_offset(addr, end-addr)
        decoded = decoder.decode(data[off:off+end-addr], addr)
        if sum(i['size'] for i in decoded) != end-addr:
            r['partially_decoded_symbol_fragments'].append(hex(addr))
        instructions.extend(decoded)
    init_insns = [i for i in instructions if init <= i['va'] < init_end]
    assert sum(i['size'] for i in init_insns) == init_end-init
    r['init']['instructions'] = init_insns
    r['init']['bytes_sha256'] = hashlib.sha256(data[image.va_to_offset(init):image.va_to_offset(init)+init_end-init]).hexdigest()
    r['init']['direct_agdp_structure_references'] = []
    for i in instructions:
        rip = re.search(r'\[rip ([+-]) (0x[0-9a-f]+)\]', i['operands'])
        if not rip:
            continue
        target = i['va']+i['size']+int(rip.group(2),16)*(1 if rip.group(1)=='+' else -1)
        if target == agdp and init <= i['va'] < init_end:
            r['init']['direct_agdp_structure_references'].append(i)
        # Do not include the following appleBacklightData array as KextInfo.
        if backlight <= target < backlight_end:
            ix = bisect.bisect_right(addresses,i['va'])-1
            r['direct_backlight_structure_references'].append({**i, 'structure_offset':target-backlight,
                'containing_symbols': [s['name'] for s in code if s['value']==addresses[ix]]})
    r['init']['direct_backlight_structure_references'] = [i for i in r['direct_backlight_structure_references']
                                                         if init <= i['va'] < init_end]
finally:
    decoder.close()
r['boundary'] = 'Direct RIP references in successfully decoded instructions and exact complete init fragment only; five partial symbol fragments are enumerated, no proof excluding all indirect references or runtime AppleBacklight attach'
out = ROOT / 'private/backlight-binary.json'
out.write_text(json.dumps(r,indent=2)+'\n')
print('Saved',out)
print('init direct AGDP/Backlight refs:',len(r['init']['direct_agdp_structure_references']),len(r['init']['direct_backlight_structure_references']))
print('all direct Backlight refs:',[(i['mnemonic'],i['structure_offset'],i['containing_symbols']) for i in r['direct_backlight_structure_references']])
