#!/usr/bin/env python3
"""Resolve only validated format11 x86_64 KC chained-pointer locations.

Layout: pinned Apple dyld reference/dyld/fixup-chains.h. This does not apply
fixups, read RAM or prove the dynamic class of any live receiver.
"""
import hashlib
import json
import mmap
import pathlib
import struct
from macho import Image, FormatError, region, unpack, confined

ROOT=pathlib.Path(__file__).resolve().parents[1]


def pointer(raw):
    if raw>>63 or ((raw>>32)&0x7ffff):
        raise FormatError('authenticated/reserved x86 cache pointer')
    return {'raw':raw,'target_offset':raw&0x3fffffff,'cache_level':(raw>>30)&3,
            'next_stride_bytes':(raw>>51)&0xfff,'format':11}


def walk(data,image):
    cur=image.offset+32;count=unpack(data,'<I',image.offset+16)[0];commands=[]
    for _ in range(count):
        cmd,size=unpack(data,'<II',cur)
        if cmd==0x80000034:
            if size!=16:raise FormatError('fixup command size')
            commands.append(unpack(data,'<II',cur+8))
        cur+=size
    if not commands:return {}
    if len(commands)!=1:raise FormatError('duplicate chained fixup command')
    off,size=commands[0];region(data,off,size)
    if size<32:raise FormatError('truncated fixup header/starts')
    version,starts_off,imports_off,symbols_off,imports_count,imports_format,symbols_format=unpack(data,'<7I',off)
    if (version!=0 or imports_count!=0 or starts_off<28 or starts_off>size-4 or
        (imports_off!=0 and not 28<=imports_off<=size) or
        (symbols_off!=0 and not 28<=symbols_off<=size) or
        imports_format not in (0,1) or symbols_format!=0):
        raise FormatError('unsupported fixup header')
    starts=off+starts_off;end=off+size
    segcount=unpack(data,'<I',starts)[0]
    if segcount!=len(image.segments) or starts+4+segcount*4>end:
        raise FormatError('fixup segment count mismatch')
    bases=[s['vmaddr'] for s in image.segments if s['vmsize'] and s['name']!='__PAGEZERO']
    if not bases:raise FormatError('no mapped segments for chained fixups')
    base=min(bases)
    out={}
    for index in range(segcount):
        so=unpack(data,'<I',starts+4+index*4)[0]
        if not so:continue
        pos=starts+so
        if pos<starts+4+segcount*4 or pos+22>end:raise FormatError('fixup starts bounds')
        length,pagesize,fmt,segoff,maxvalid,pages=unpack(data,'<IHHQIH',pos)
        if length<22+2*pages or pos+length>end or pagesize!=4096 or fmt!=11 or maxvalid!=0:
            raise FormatError('unsupported page format')
        seg=image.segments[index]
        if base+segoff!=seg['vmaddr']:raise FormatError('segment coordinate mismatch')
        if pages*pagesize>seg['vmsize']+pagesize-1:raise FormatError('page count out of segment')
        for page in range(pages):
            start=unpack(data,'<H',pos+22+2*page)[0]
            if start==0xffff:continue
            if start&0x8000:raise FormatError('multi-start page unsupported, refuse')
            if start>pagesize-8:raise FormatError('page start bounds')
            within=start;visited=set()
            while True:
                if within in visited or len(visited)>4096:raise FormatError('fixup loop/budget')
                visited.add(within)
                va=base+segoff+page*pagesize+within
                loc=image.va_to_offset(va,8)
                p=pointer(unpack(data,'<Q',loc)[0])
                if loc in out:raise FormatError('duplicate fixup location')
                out[loc]=dict(p,location_fileoff=loc,location_va=va)
                step=p['next_stride_bytes']
                if step==0:break
                if within+step>pagesize-8:raise FormatError('chain crosses page')
                within+=step
    return out


def main():
    sysinv=json.loads((ROOT/'analysis/kc/SystemKernelExtensions.kc.json').read_text())
    bootinv=json.loads((ROOT/'analysis/kc/BootKernelExtensions.kc.json').read_text())
    with confined(ROOT,bootinv['source']).open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as boot:
        if hashlib.sha256(boot).hexdigest()!=bootinv['sha256']:raise FormatError('BootKC inventory SHA mismatch')
        kernelitem=next(i for i in bootinv['images'] if i['name']=='com.apple.kernel')
        kernel=Image(boot,kernelitem['header_fileoff'],'com.apple.kernel')
        base0=min(s['vmaddr'] for s in kernel.segments if s['vmsize'] and s['name']!='__PAGEZERO')
        syms0={}
        for s in kernel.symbols():
            if s['type']&0xe==0xe and not s['type']&0xe0:syms0.setdefault(s['value'],[]).append(s['name'])
        if hashlib.sha256(boot).hexdigest()!=bootinv['sha256']:raise FormatError('BootKC changed during parse')
    result={'source':sysinv['source'],'source_sha256':sysinv['sha256'],'format':11,
            'layout_source':'reference/dyld/fixup-chains.h','kernel_static_base':base0,
            'caveat':'Static cache-level target only; no live receiver/vtable or runtime patched byte attestation',
            'stubs':[],'vtables':[],'chains':[]}
    with confined(ROOT,sysinv['source']).open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
        if hashlib.sha256(data).hexdigest()!=sysinv['sha256']:raise FormatError('SystemKC inventory SHA mismatch')
        top=Image(data);allsyms={};images={}
        for item in sysinv['images']:
            im=Image(data,item['header_fileoff'],item['name']);images[item['name']]=im
            for s in im.symbols():
                if s['type']&0xe==0xe and not s['type']&0xe0:allsyms.setdefault(s['value'],[]).append(s['name'])
        def resolve(p):
            lv=p['cache_level'];target=p['target_offset']
            if lv==0:return dict(p,target_va=base0+target,target_symbols=syms0.get(base0+target,[]))
            if lv==1:return dict(p,target_va=target,target_symbols=allsyms.get(target,[]))
            return dict(p,unresolved_reason='cache level not modelled')
        topfix=walk(data,top)
        for va in range(0xc000,0x20000):
            try:loc=top.va_to_offset(va,6)
            except FormatError:continue
            if data[loc:loc+2]!=b'\xff\x25':continue
            slotva=va+6+unpack(data,'<i',loc+2)[0]
            try:slot=top.va_to_offset(slotva,8)
            except FormatError:continue
            if slot not in topfix:continue
            result['stubs'].append(dict(resolve(topfix[slot]),stub_va=va,stub_fileoff=loc,stub_bytes=data[loc:loc+6].hex()))
        for name,im in images.items():
            fix=walk(data,im)
            result['chains'].append({'image':name,'locations':len(fix)})
            symbols=im.symbols()
            defined_starts=sorted({s['value'] for s in symbols if s['type']&0xe==0xe and not s['type']&0xe0})
            for s in symbols:
                if s['name'] not in ['__ZTV18IGAccelFIFOChannel','__ZTV20IGHardwareRingBuffer','__ZTV12IGScheduler5','__ZTV11IGScheduler','__ZTV19IOAccelFIFOChannel2'] or not s['value']:continue
                slots=[]
                bound=next((v for v in defined_starts if v>s['value']),s['value'])
                for off in range(0x140,0x230,8):
                    v=s['value']+16+off
                    if v+8>bound:continue
                    loc=im.va_to_offset(v,8)
                    if loc not in fix:continue
                    slots.append(dict(resolve(fix[loc]),vptr_byte_offset=off))
                result['vtables'].append({'image':name,'symbol':s['name'],'symbol_va':s['value'],
                                          'symbol_extent_upper_bound':bound,
                                          'address_point':s['value']+16,'slots':slots,
                                          'address_point_basis':'Itanium primary vtable +16; no claim all live receivers use this class'})
        result['top_fixup_locations']=len(topfix)
        if hashlib.sha256(data).hexdigest()!=sysinv['sha256']:raise FormatError('SystemKC changed during parse')
    (ROOT/'analysis/cache-fixups.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'stubs':len(result['stubs']),'chains':result['chains'],'vtables':len(result['vtables'])},indent=2))


if __name__=='__main__':main()
