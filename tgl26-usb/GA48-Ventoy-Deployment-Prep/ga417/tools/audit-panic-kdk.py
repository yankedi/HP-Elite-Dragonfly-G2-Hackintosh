#!/usr/bin/env python3
"""Symbolicate retained kernel frames using matching local KDK private nlist.

This is symbol-interval lookup, not DWARF inline/source-line symbolication.
Kext frames retain their original attribution; kernel symbols are never applied
outside a kernel executable section.
"""
import bisect
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[2]
CPIO = ROOT.parent/'GA43-Darwin-Driver-Stack/build-private-kdk-001/kdk.cpio'
WORK = ROOT/'ga417/private/panic-kdk'
UUID = '39CC2C26-3F72-3565-89C4-94DFE36DFDF2'


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def extract():
    wanted = {'./System/Library/Kernels/kernel':'kernel',
              './System/Library/Kernels/kernel.dSYM/Contents/Resources/DWARF/kernel':'kernel.dwarf'}
    records = []
    with CPIO.open('rb') as f:
        while wanted:
            h = f.read(76)
            assert h[:6] == b'070707'
            ns, size = int(h[59:65],8), int(h[65:76],8)
            name = f.read(ns).rstrip(b'\0').decode()
            offset = f.tell()
            if name in wanted:
                data = f.read(size)
                assert len(data) == size
                p = WORK/wanted.pop(name)
                if p.exists():
                    assert p.read_bytes() == data
                else:
                    with p.open('xb') as out:
                        out.write(data)
                records.append({'archive_member':name,'archive_offset':offset,
                                'path':str(p.relative_to(ROOT)),'bytes':size,'sha256':sha(p)})
            f.seek(offset+size)
            assert name != 'TRAILER!!!' or not wanted
    return records


def macho(p, expected_uuid=UUID):
    data = p.read_bytes()
    assert data[:4] == b'\xcf\xfa\xed\xfe'
    off, sections, ident, symtab = 32, [], None, None
    for _ in range(struct.unpack_from('<I',data,16)[0]):
        cmd, size = struct.unpack_from('<II',data,off)
        if cmd == 0x1b:
            ident = str(uuid.UUID(bytes=data[off+8:off+24])).upper()
        if cmd == 2:
            symtab = struct.unpack_from('<IIII',data,off+8)
        if cmd == 0x19:
            for j in range(struct.unpack_from('<I',data,off+64)[0]):
                pos = off+72+80*j
                name = data[pos:pos+16].rstrip(b'\0').decode()
                addr, length = struct.unpack_from('<QQ',data,pos+32)
                file_offset = struct.unpack_from('<I',data,pos+48)[0]
                flags = struct.unpack_from('<I',data,pos+64)[0]
                sections.append({'name':name,'address':addr,'size':length,'file_offset':file_offset,
                                 'instructions':bool(flags & 0x80000400)})
        off += size
    assert ident == expected_uuid
    symbols = []
    if symtab:
        so, count, stro, strs = symtab
        strings = data[stro:stro+strs]
        for i in range(count):
            sx, ty, sn, desc, val = struct.unpack_from('<IBBHQ',data,so+16*i)
            if ty & 0xe0 or ty & 0x0e != 0x0e or not 0 < sn <= len(sections):
                continue
            if not sections[sn-1]['instructions']:
                continue
            end = strings.find(b'\0',sx)
            name = strings[sx:end].decode(errors='replace')
            symbols.append((val,name,sn))
    return ident, sections, sorted(symbols)


def main():
    WORK.mkdir(parents=True,exist_ok=True)
    extracted = extract()
    assert sha(WORK/'kernel') == '1542ae9efea6d3a212248446d610b677d66fec02da5a5bfacf2b1a67f544b47e'
    _, sections, _ = macho(WORK/'kernel')
    _, _, symbols = macho(WORK/'kernel.dwarf')
    addresses = [v[0] for v in symbols]
    assert any(n == '_pmap_recycle_page' and a == 0xffffff80003c6700 for a,n,_ in symbols)
    inputs = [ROOT/'ga416/private/crash-series/panic-inventory-20261025T124307Z.json']
    rows = json.loads(inputs[0].read_text())['panics']
    incidents, seen = [], set()
    for row in rows:
        if not row['path'].endswith('.panic'):
            continue
        header, body = [json.loads(x) for x in row['content'].splitlines()[:2]]
        incident = header['incident_id']
        if incident in seen:
            continue
        seen.add(incident)
        assert hashlib.sha256(row['content'].encode()).hexdigest() == row['sha256']
        text = body['macOSPanicString']
        assert UUID in text
        slide = int(re.search(r'^Kernel slide:\s*(0x[0-9a-f]+)',text,re.M)[1],16)
        frames = []
        for line in text.splitlines():
            m = re.match(r'^(0x[0-9a-f]+)\s*:\s*(0x[0-9a-f]+)(.*)$',line)
            if not m:
                continue
            ret = int(m[2],16)
            pc = ret-slide
            code = next((s for s in sections if s['instructions'] and s['address'] <= pc < s['address']+s['size']),None)
            frame = {'raw':line,'return_address':hex(ret),'unslid_address':hex(pc),
                     'symbolication':'NOT_IN_KERNEL_EXECUTABLE_SECTION_RETAIN_RAW_KEXT_ATTRIBUTION'}
            if code:
                ix = bisect.bisect_right(addresses,pc)-1
                assert ix >= 0
                addr, name, _ = symbols[ix]
                nextaddr = next((x for x in addresses[ix+1:] if x > addr),code['address']+code['size'])
                assert addr <= pc < nextaddr
                demangled = subprocess.check_output(['c++filt',name[1:] if name.startswith('__Z') else name],text=True).strip()
                frame.update(symbolication='MATCHING_KDK_PRIVATE_SYMBOL_INTERVAL',symbol=name,
                             demangled=demangled,symbol_address=hex(addr),offset=hex(pc-addr),
                             next_symbol_address=hex(nextaddr),section=code['name'])
            frames.append(frame)
        incidents.append({'incident':incident,'file':row['path'],'panic_sha256':row['sha256'],
                          'signature':text.splitlines()[0],'slide':hex(slide),'frames':frames,
                          'raw_panic_source':str(inputs[0].relative_to(ROOT))})
    assert len(incidents) == 6
    report = {'status':'MATCHING_KDK_PRIVATE_KERNEL_SYMBOL_INTERVALS_AUDITED',
              'kernel_uuid':UUID,'extracted':extracted,'sources':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in inputs],
              'method':'Subtract each panic Kernel slide; match nlist N_SECT instruction symbols inside matching kernel executable sections only. Return addresses retained without subtracting 1.',
              'limits':['No DWARF line or inline reconstruction; symbol intervals are not full instruction-level unwind validation.',
                        'Kext frames retain raw attribution unless independently UUID-matched.',
                        'KDK is release kernel; does not prove live patched kernel bytes equal KDK or identify first corrupter.'],
              'incidents':incidents}
    (ROOT/'ga417/reports/PANIC-KDK-SYMBOLS.json').write_text(json.dumps(report,indent=2)+'\n')
    for i in incidents:
        print(i['incident'],i['signature'])
        for f in i['frames'][7:]:
            print(' ',f.get('demangled',f['raw']),f.get('offset',''))


if __name__=='__main__':
    main()
