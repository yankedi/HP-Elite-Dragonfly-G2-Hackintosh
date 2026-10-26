#!/usr/bin/env python3
"""Bounds-checked offline x86_64 Mach-O inventory and kext relocation audit.

This validates stored structure, not kernel execution or ABI compatibility.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def inspect(path):
    raw = Path(path).read_bytes()
    data = raw
    if raw[:4] == b"\xca\xfe\xba\xbe":
        count = struct.unpack_from(">I", raw, 4)[0]
        assert 8 + 20 * count <= len(raw), "fat header bounds"
        slices = [struct.unpack_from(">IIIII", raw, 8 + 20*i) for i in range(count)]
        choices = [s for s in slices if s[0] == 0x1000007]
        assert choices, "no x86_64 slice"
        _, _, off, size, _ = choices[0]
        assert off + size <= len(raw), "fat slice bounds"
        data = raw[off:off+size]

    def unpack(fmt, off):
        assert 0 <= off <= len(data) - struct.calcsize(fmt), f"bounds {off:x} {fmt}"
        return struct.unpack_from(fmt, data, off)

    def string(off, end):
        assert 0 <= off < end <= len(data), "string bounds"
        stop = data.find(b"\0", off, end)
        assert stop >= 0, "unterminated string"
        return data[off:stop].decode(errors="replace")

    magic, cpu, subtype, kind, count, cmdbytes, flags, _ = unpack("<8I", 0)
    assert magic == 0xfeedfacf and cpu == 0x1000007, "not x86_64 Mach-O64"
    assert 32 + cmdbytes <= len(data), "command bounds"
    segments, sections, cmds, symbols, libraries = [], [], [], [], []
    symtab = dysym = None
    export_range = None
    cursor = 32
    for _ in range(count):
        cmd, size = unpack("<II", cursor)
        assert size >= 8 and size % 8 == 0 and cursor + size <= 32 + cmdbytes, "command size"
        cmds.append(cmd)
        if cmd == 0x19:
            s = unpack("<II16sQQQQiiII", cursor)
            _, _, name, va, vs, off, fs, maxp, initp, ns, sf = s
            assert off + fs <= len(data), "segment file bounds"
            assert 72 + 80 * ns == size, "section count"
            name = name.rstrip(b"\0").decode()
            segments.append(dict(name=name, vmaddr=va, vmsize=vs, fileoff=off,
                                 filesize=fs, maxprot=maxp, initprot=initp, flags=sf))
            for i in range(ns):
                n, sn, a, z, o, al, ro, nr, fl, r1, r2, r3 = unpack("<16s16sQQ8I", cursor+72+80*i)
                assert va <= a <= a+z <= va+vs, "section VM bounds"
                if fl & 0xff not in (1, 0xc, 0x12):
                    assert off <= o <= o+z <= off+fs, "section file bounds"
                assert ro + nr * 8 <= len(data), "section reloc bounds"
                sections.append(dict(index=len(sections)+1, name=n.rstrip(b"\0").decode(),
                                     segment=sn.rstrip(b"\0").decode(), address=a, size=z,
                                     offset=o, alignment=al, flags=fl, nreloc=nr))
        elif cmd == 2:
            assert symtab is None, "duplicate symtab"
            symtab = unpack("<6I", cursor)[2:]
        elif cmd == 0xb:
            assert dysym is None, "duplicate dysymtab"
            dysym = unpack("<20I", cursor)[2:]
        elif cmd in (0x22,0x80000022):
            ec=unpack("<12I",cursor)
            export_range=(ec[10],ec[11])
        elif cmd == 0x80000033:
            export_range=unpack("<4I",cursor)[2:]
        elif cmd in (0xc, 0xd, 0x80000018, 0x8000001f, 0x80000023):
            no, timestamp, current, compatibility = unpack("<4I", cursor+8)
            libraries.append(dict(command=cmd, name=string(cursor+no,cursor+size),
                                  current_version=current, compatibility_version=compatibility))
        cursor += size
    assert cursor == 32+cmdbytes, "load command sum"
    if symtab:
        so, ns, st, ss = symtab
        assert so + ns*16 <= len(data) and st+ss <= len(data), "symbol bounds"
        for i in range(ns):
            si, typ, sec, desc, val = unpack("<IBBHQ", so+16*i)
            assert si < ss and sec <= len(sections), "symbol index"
            symbols.append(dict(index=i, name=string(st+si,st+ss), type=typ,
                                section=sec, descriptor=desc, value=val,
                                undefined=(typ & 0xe)==0, external=bool(typ & 1)))
    relocations = []
    if dysym:
        assert len(symbols) >= max(dysym[0]+dysym[1], dysym[2]+dysym[3], dysym[4]+dysym[5]), "dysym partitions"
        for label, off, n, external in [("external",dysym[14],dysym[15],1),("local",dysym[16],dysym[17],0)]:
            assert off+n*8 <= len(data), "dynamic relocation bounds"
            if n:
                le = next(s for s in segments if s['name']=='__LINKEDIT')
                assert le['fileoff'] <= off and off+n*8 <= le['fileoff']+le['filesize'], "relocs outside LINKEDIT"
            for i in range(n):
                addr, word = unpack("<II", off+i*8)
                symbol, pc, ln, ext, typ = word & 0xffffff, (word>>24)&1, (word>>25)&3, (word>>27)&1, word>>28
                assert not addr & 0x80000000, "scattered or negative reloc unsupported"
                assert ext == external, "wrong relocation table"
                assert symbol < len(symbols) if ext else symbol <= len(sections), "reloc target index"
                base = segments[0]['vmaddr']
                matches = [s for s in sections if s['address'] <= base+addr and base+addr+(1<<ln) <= s['address']+s['size']]
                assert len(matches)==1, "reloc source not in section"
                s = matches[0]
                loc = s['offset']+base+addr-s['address']
                value = int.from_bytes(data[loc:loc+(1<<ln)],'little',signed=bool(pc))
                relocations.append(dict(table=label,address=addr,pcrel=pc,length=ln,
                                        external=ext,type=typ,symbol=symbol,
                                        target=symbols[symbol]['name'] if ext else symbol,
                                        source_section=s['name'],stored_value=value))
    exports = []
    if export_range and export_range[1]:
        eo, ez=export_range
        assert eo+ez<=len(data), 'export trie bounds'
        trie=data[eo:eo+ez]
        def uleb(pos):
            n=shift=0
            while True:
                assert pos<len(trie) and shift<=63, 'bad ULEB'
                b=trie[pos];pos+=1;n|=(b&127)<<shift
                if b<128:return n,pos
                shift+=7
        def node(pos,prefix,ancestors):
            assert pos not in ancestors and len(ancestors)<1024, 'export trie cycle'
            terminal, p=uleb(pos); end=p+terminal
            assert end<len(trie), 'export terminal bounds'
            if terminal:
                ef,q=uleb(p)
                exports.append(dict(name=prefix,flags=ef))
            p=end;children=trie[p];p+=1
            for _ in range(children):
                e=trie.find(b'\0',p);assert e>=0, 'export child string'
                label=trie[p:e].decode(errors='replace');child,p=uleb(e+1)
                node(child,prefix+label,ancestors|{pos})
        node(0,'',set())
    elif kind==0xb:
        exports=[dict(name=s['name'],flags=0) for s in symbols if s['external'] and not s['undefined'] and not s['type']&0x10]
    return dict(path=str(Path(path).resolve()), sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw), header=dict(cpu=cpu, subtype=subtype, filetype=kind, flags=flags),
                commands=cmds,segments=segments,sections=sections,libraries=libraries,
                symbols=symbols,exports=exports,dysymtab=dysym,relocations=relocations)


def validate_kext(x):
    assert x['header']['filetype'] == 0xb, "MH_KEXT_BUNDLE required"
    assert x['dysymtab'] is not None and x['symbols'], "symtab/dysymtab required"
    forbidden = {0xc,0xd,0xe,0x22,0x80000022,0x80000028,0x80000034}
    assert not forbidden.intersection(x['commands']), "userspace load commands"
    assert not x['libraries'], "dylib dependency in kext"
    assert '__LINKEDIT' in [s['name'] for s in x['segments']]
    assert all((s['flags']&0xff) not in (0x11,0x12,0x13,0x14,0x15) for s in x['sections']), "TLV in kernel"
    for r in x['relocations']:
        assert (r['type'],r['length'],r['pcrel']) in {(0,3,0),(2,2,1)}, "unsupported kernel reloc"
        if not r['external']:
            assert (r['type'],r['length'],r['pcrel']) == (0,3,0), "local relocation kind"
            if r['symbol']:
                dest = x['sections'][r['symbol']-1]
                assert dest['address'] <= r['stored_value'] <= dest['address']+dest['size'], "local relocation addend"
    # __stack_chk_{fail,guard} are kernel exports too (present in pinned Lilu),
    # so their presence is a provider-audit question, not a userspace verdict.
    bad = ['___cxa_atexit','___cxa_thread_atexit','_dyld_stub_binder']
    assert not set(bad).intersection(s['name'] for s in x['symbols'] if s['undefined']), "wrong runtime"
    x['structural_status'] = ['KEXT_FILETYPE_VALID','KEXT_RELOCATIONS_VALID']
    x['runtime_status'] = 'GPU_NOT_TESTED'


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--kext',action='store_true')
    a=p.parse_args();x=inspect(a.binary)
    if a.kext: validate_kext(x)
    print(json.dumps(x,indent=2))
