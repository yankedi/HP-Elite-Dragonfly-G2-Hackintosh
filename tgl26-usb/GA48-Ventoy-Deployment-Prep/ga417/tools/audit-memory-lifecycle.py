#!/usr/bin/env python3
"""Audit exact KDK return-address DWARF, allocator imports and selected ABI slots.

No target commands or writes. Relocatable kext branch placeholders are resolved
from their relocation tables; zero-displacement calls are not runtime targets.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT/'ga417/private/panic-kdk'
SPEC = importlib.util.spec_from_file_location('kdk',Path(__file__).with_name('audit-panic-kdk.py'))
KDK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(KDK)


def run(argv, **kwargs):
    return subprocess.run([str(x) for x in argv],capture_output=True,text=True,check=True,**kwargs).stdout


def macho(path):
    data=path.read_bytes()
    assert data[:4]==b'\xcf\xfa\xed\xfe'
    off=32
    for _ in range(struct.unpack_from('<I',data,16)[0]):
        cmd,size=struct.unpack_from('<II',data,off)
        if cmd==0x1b:
            ident=str(uuid.UUID(bytes=data[off+8:off+24])).upper()
        if cmd==2:
            so,count,st,ss=struct.unpack_from('<IIII',data,off+8)
        off+=size
    _,sections,code=KDK.macho(path,ident)
    strings=data[st:st+ss]
    symbols={}
    for j in range(count):
        x,ty,_,_,v=struct.unpack_from('<IBBHQ',data,so+j*16)
        if ty & 0xe0 or ty & 0x0e != 0x0e:
            continue
        symbols[strings[x:strings.find(b'\0',x)].decode()]=v
    return data,ident,sections,code,symbols


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llvm-bin',required=True,type=Path)
    args=parser.parse_args()
    llvm=args.llvm_bin
    sources={
        'kernel':WORK/'kernel',
        'TGL':ROOT/'ga414/private/AppleIntelTGLGraphics-25G83',
        'IOAF2':ROOT/'ga410/private/r4-code-evidence/IOAcceleratorFamily2-kdk',
    }
    functions={
        'kernel':['_pmap_verify_free','_pmap_recycle_page','_vm_page_free_unlocked','_vm_page_free_list',
                  '_vm_free_delayed_pages','_vm_page_release','_vm_page_create_canonical',
                  '_vm_free_delayed_pages_contig','_vm_page_free_prepare_object','_vm_page_free',
                  '_OSObject_typed_operator_new','_OSObject_typed_operator_delete',
                  '__ZN10IOMachPort4freeEv','__ZNK8OSObject13taggedReleaseEPKv','__ZNK8OSObject13taggedReleaseEPKvi',
                  '_mach_zone_get_zlog_zones','_mach_zone_get_btlog_records'],
        'TGL':['__ZN15IGAccelResource9MetaClassC1Ev','__ZN15IGAccelResourcenwEm','__ZN15IGAccelResourcedlEPvm',
               '__ZN15IGAccelResource4freeEv','__ZN15IGAccelResource6pageonEP12IOAccelEventby',
               '__ZN15IGAccelResource7pageoffEP12IOAccelEventbPby','__ZN15IGAccelResource10initializeEP22IOAccelNewResourceArgsy'],
        'IOAF2':['__ZN16IOAccelResource29MetaClassC1Ev','__ZN16IOAccelResource2nwEm','__ZN16IOAccelResource2dlEPvm',
                 '__ZN16IOAccelResource24freeEv','__ZN16IOAccelResource25unmapEv','__ZN16IOAccelResource23mapEv',
                 '__ZN16IOAccelResource27prepareEv','__ZN16IOAccelResource28completeEv',
                 '__ZN16IOAccelMemoryMap4freeEv','__ZN16IOAccelMemoryMap15remove_resourceEP16IOAccelResource2',
                 '__ZN16IOAccelSysMemory4freeEv','__ZN24IOAccelEventMachineFast211finishEventEP12IOAccelEvent'],
    }
    inventory,extracted,vtables={},[],{}
    current_capture=ROOT/'ga417/private/rtc-live/initial-20261026T013125Z.json'
    current=json.loads(current_capture.read_text())
    for tag,path in sources.items():
        data,ident,sections,code,symbols=macho(path)
        if tag=='kernel':
            _,_,_,code,symbols=macho(WORK/'kernel.dwarf')
            assert ident==KDK.UUID and KDK.sha(path)=='1542ae9efea6d3a212248446d610b677d66fec02da5a5bfacf2b1a67f544b47e'
        inventory[tag]={'path':str(path.relative_to(ROOT)),'sha256':KDK.sha(path),'uuid':ident}
        if tag!='kernel':
            lines=[l for l in current['loaded_kexts']['stdout'].splitlines() if ident in l]
            assert len(lines)==1
            inventory[tag]['observed_loaded_UUID_line']=lines[0]
            inventory[tag]['loaded_capture']=str(current_capture.relative_to(ROOT))
            inventory[tag]['loaded_capture_sha256']=KDK.sha(current_capture)
        relocation={}
        if tag!='kernel':
            text=run([llvm/'llvm-objdump','--macho','--reloc',path])
            (WORK/(tag+'-relocations.txt')).write_text(text)
            relocation={int(m[1],16):m[2] for m in re.finditer(r'^([0-9a-f]{8})\s+.*?False\s+(\S+)\s*$',text,re.M)}

        def read_va(va,n):
            s=next(s for s in sections if s['address']<=va and va+n<=s['address']+s['size'])
            off=s['file_offset']+va-s['address']
            return data[off:off+n]

        for name in functions[tag]:
            start=symbols[name]
            end=min(v for v,_,_ in code if v>start)
            raw=read_va(start,end-start)
            binpath=WORK/('lifecycle-'+tag+'-'+name+'.bin')
            binpath.write_bytes(raw)
            dis=run(['objdump','-D','-b','binary','-m','i386:x86-64','--adjust-vma='+hex(start),binpath])
            # Preserve full raw disassembly plus explicit import/local relocations.
            rel={hex(k):v for k,v in relocation.items() if start<=k<end}
            txt=binpath.with_suffix('.txt')
            txt.write_text(dis+'\nRelocations (operand locations, not instruction start):\n'+json.dumps(rel,indent=2)+'\n')
            extracted.append({'binary':tag,'symbol':name,'start':hex(start),'end':hex(end),
                              'machine_code_sha256':hashlib.sha256(raw).hexdigest(),
                              'disassembly':str(txt.relative_to(ROOT)),'disassembly_sha256':KDK.sha(txt),'relocations':rel})
        if tag!='kernel':
            reverse={v:k for k,v in symbols.items()}
            for cls in (['IGAccelResource'] if tag=='TGL' else ['IOAccelResource2','IOAccelEventMachineFast2']):
                base=symbols['__ZTV'+str(len(cls))+cls]+16
                slots={hex(i):relocation.get(base+i,reverse.get(struct.unpack('<Q',read_va(base+i,8))[0],'UNRESOLVED')) for i in range(0,0x290,8)}
                vtables[cls]={'binary':tag,'address_point':hex(base),'slots':slots}
    assert vtables['IGAccelResource']['slots']['0x8']=='__ZN15IGAccelResourceD0Ev'
    assert vtables['IGAccelResource']['slots']['0x90']=='__ZN15IGAccelResource4freeEv'
    assert vtables['IOAccelResource2']['slots']['0x90']=='__ZN16IOAccelResource24freeEv'
    assert vtables['IOAccelEventMachineFast2']['slots']['0x188']=='__ZN24IOAccelEventMachineFast211finishEventEP12IOAccelEvent'
    assert vtables['IOAccelResource2']['slots']['0x50']=='__ZNK8OSObject13taggedReleaseEPKv'
    byname={r['symbol']:r for r in extracted}
    assert byname['__ZN15IGAccelResourcenwEm']['relocations']['0x6e7c8']=='__ZN8OSObjectnwEm'
    assert byname['__ZN15IGAccelResourcedlEPvm']['relocations']['0x6e734']=='__ZN8OSObjectdlEPvm'
    assert byname['__ZN15IGAccelResource4freeEv']['relocations']['0x6f71c']=='_IOFree'
    assert byname['__ZN15IGAccelResource4freeEv']['relocations']['0x6f793']=='_IOFree'
    for n in ['_mach_zone_get_zlog_zones','_mach_zone_get_btlog_records']:
        p=WORK/('lifecycle-kernel-'+n+'.bin')
        assert p.read_bytes().startswith(bytes.fromhex('554889e5b8050000005dc3'))
    # Enumerate this exact compiler-emitted recycle-panic reference form in all
    # executable sections. Validate every match against complete function decode.
    kd,_,ks,_,_=macho(sources['kernel'])
    _,_,_,kc,kall=macho(WORK/'kernel.dwarf')
    recycle_name=0xffffff8000b784bf
    s=next(s for s in ks if s['address']<=recycle_name<s['address']+s['size'])
    pos=s['file_offset']+recycle_name-s['address']
    assert kd[pos:pos+18]==b'pmap_recycle_page\0'
    refs=[]
    for s in ks:
        if not s['instructions']:
            continue
        raw=kd[s['file_offset']:s['file_offset']+s['size']]
        pos=0
        while True:
            p=raw.find(b'\x48\x8d\x35',pos)
            if p<0:
                break
            pos=p+1
            pc=s['address']+p
            if pc+7+struct.unpack_from('<i',raw,p+3)[0]!=recycle_name:
                continue
            containing=max((x for x in kc if x[0]<=pc),key=lambda x:x[0])[1]
            row=byname[containing]
            text=(ROOT/row['disassembly']).read_text()
            assert re.search(r'^\s*'+format(pc,'x')+r':.*\blea\b',text,re.M)
            candidates=[]
            for q in range(p+7,min(p+80,len(raw)-4)):
                addr=s['address']+q
                if raw[q]==0xe8 and addr+5+struct.unpack_from('<i',raw,q+1)[0]==kall['_panic']:
                    if re.search(r'^\s*'+format(addr,'x')+r':.*\bcall\b',text,re.M):
                        candidates.append((addr,raw[q:q+5].hex()))
            assert candidates
            call,code=candidates[0]
            refs.append({'containing_symbol':containing,'routine_name_LEA':hex(pc),
                         'panic_call':hex(call),'call_bytes':code,'saved_RA':hex(call+5)})
    assert len(refs)==11 and len({r['panic_call'] for r in refs})==9
    assert any(r['panic_call']=='0xffffff800037a1e9' and r['call_bytes']=='e8eee87300' for r in refs)
    assert any(r['panic_call']=='0xffffff800037f096' and r['call_bytes']=='e8419a7300' for r in refs)
    (ROOT/'ga417/reports/PMAP-FAILURE-SITES.json').write_text(json.dumps({
        'kernel_uuid':KDK.UUID,'kernel_sha256':KDK.sha(sources['kernel']),
        'method':'All executable-section LEA RSI references to exact recycle routine-name literal, followed by direct panic call within80bytes; each reference/call confirmed on full containing-function instruction boundaries.',
        'reference_count':len(refs),'unique_panic_calls':9,'references':refs,
        'limits':'Exhaustive for the observed emitted instruction form and fixed binary only; not a proof that every possible semantically equivalent pmap failure has this encoding.'},indent=2)+'\n')
    old=json.loads((ROOT/'ga417/reports/PANIC-KDK-SYMBOLS.json').read_text())
    pcs=sorted({int(f['unslid_address'],16) for i in old['incidents'] for f in i['frames'] if f['symbolication']=='MATCHING_KDK_PRIVATE_SYMBOL_INTERVAL'})
    # Exact PCs are retained separately. Minus-one is only a caller-location lookup
    # for saved return addresses, not a claim to reconstruct the saved register RIP.
    for delta,label in [(0,'exact'),(-1,'caller-minus-one')]:
        raw=run([llvm/'llvm-symbolizer','--obj='+str(WORK/'kernel.dwarf'),'--inlines','--output-style=JSON'],input='\n'.join(hex(pc+delta) for pc in pcs)+'\n')
        rows=[json.loads(l) for l in raw.splitlines()]
        assert len(rows)==len(pcs)
        (WORK/('lifecycle-DWARF-'+label+'.json')).write_text(json.dumps([{'saved_address':hex(pc),'lookup_address':hex(pc+delta),'symbols':r['Symbol']} for pc,r in zip(pcs,rows)],indent=2)+'\n')
    for name in ['IOMachPort','pv_rooted_entry','zone_info','zone_page_metadata']:
        (WORK/('lifecycle-DWARF-'+name+'.txt')).write_text(run([llvm/'llvm-dwarfdump','--name='+name,'--show-children',WORK/'kernel.dwarf']))
    (WORK/'lifecycle-DWARF-zone_info-layout.txt').write_text(run([llvm/'llvm-dwarfdump','--debug-info=0x2fb398','--show-children',WORK/'kernel.dwarf']))
    # Read-only future debugger helper is pinned to the exact kernel bytes too.
    _,_,_,_,kernel_symbols=macho(WORK/'kernel.dwarf')
    verification=[]
    for name in ['_pmap_verify_free','_vm_page_free_unlocked','_vm_page_free_list','_OSObject_typed_operator_delete']:
        row=byname[name]
        verification.append({'symbol':name,'address':row['start'],
                             'bytes':(WORK/('lifecycle-kernel-'+name+'.bin')).read_bytes().hex()})
    layout={
        'schema_version':1,'kernel_uuid':KDK.UUID,'kernel_sha256':inventory['kernel']['sha256'],
        'kernel_header_unslid':'0xffffff8000200000','verification':verification,
        'globals':{n:hex(kernel_symbols[n]) for n in ['_pmap_initialized','_last_managed_page','_pmap_phys_attributes','_pv_head_table','_zone_info']},
        'pv_entry_size':32,'pv_va_and_flags_offset':16,'pv_pmap_offset':24,
        'zone_info_size':184,'zone_meta_base_offset':176,'zone_meta_record_size':16,
        'zone_meta_address_mask':'0xffffffff0','zone_index_mask':'0x3ff',
        'provenance':'Matching KDK instruction bytes and DWARF in MEMORY-LIFECYCLE-AUDIT.json. Layout only; no live memory capture or kext installed.',
    }
    (ROOT/'ga417/reports/MEMORY-DIAGNOSTIC-LAYOUT.json').write_text(json.dumps(layout,indent=2)+'\n')
    report={
        'status':'EXACT_BINARY_ALLOC_FREE_AND_LOCAL_ABI_AUDITED_NO_CAUSAL_FIX_PROVEN',
        'tools':{'llvm_version':run([llvm/'llvm-symbolizer','--version']).splitlines()[0]},
        'binaries':inventory,'functions':extracted,'vtables':vtables,
        'observations':[
            'KDK DWARF IOMachPort size0x28; member object:OSObject* offset0x20. Caller RA0xffffff8000a15895 minus1 attributes IOUserClient.cpp:409; actual preceding call is taggedRelease at vtable+0x50 on that member.',
            'OSObject typed-delete RA0xffffff8000933be1 minus1 expands kfree_type_impl_external(kalloc.c3034) -> kern_os_typed_free(kalloc.c3632) -> OSObject_typed_operator_delete(OSObject.cpp378). Exact RA maps to a later line382.',
            'TGL IGAccelResource legacy new/delete imports are paired OSObject::operator new/delete. IOAF2 IOAccelResource2 uses typed allocation/free with the same class ktv; no demonstrated cross-allocator free at these class operators.',
            'TGL resource metadata size0x260; IOAF2 base resource size0x180; selected private table pointer+0x250 and size+0x258 fit the declared subclass size. This is not validation of all inherited member offsets.',
            'Actual TGL free uses40-byte entries, count u16 at+0x18, pointer+0x20 and IOFree(pointer,count*8), followed by IOFree(table,this+0x258). Source RESFREE offsets agree locally with this binary.',
            'Fresh TGL initialize branch at0x6eb0a bounds faces<=6 and baseLOD+levels<=15, then IOMalloc(faces*(baseLOD+levels)*40) at0x6eb53; nested IOMalloc(count*8) at0x6ec5b pairs the free at0x6f71b. Last used entry is faces*levels+baseLOD-1, which is below faces*(baseLOD+levels) when faces>0. Positive baseLOD alone does not prove table-allocation OOB. Zero-count/nonNULL source-pointer failure clears destination pointer at0x6ef9c.',
            'Source xePageon guard checks/iterates faces*levels entries starting0; original TGL indexes i*levels+j with j startingbaseLOD. For baseLOD>0, trailing used entries can be outside that guard coverage even though inside original allocation. This is a local guard coverage gap, not evidence that it caused any HP pmap/wrong-zone panic; no new mainline patch or trial enabled.',
            'PageSync selected call slot+0x188 resolves to finishEvent in exact IOAF2 event machine vtable. This does not prove receiver lifetime or event completion correctness.',
            'IOAF2 resource unmap removes this from memoryMap+0xa0 array/count+0xb0, releases resource+0x40 and clears+0x40/+0x70/+0x20; complete decrements prepare_count+0x28 and for type1 follows the same release sequence at zero. Map free releases backing+0x18 and typed-frees the resource-pointer array. These stages need resource/map/descriptor identity and event history at failure before attributing missing PV removal.',
            'pmap_verify_free reads pmap_initialized, sentinel PPN0xfffffffe, last_managed_page, phys_attributes[ppn]&1 and pv_head_table[ppn].pmap. pv_rooted_entry DWARF size0x20 with va_and_flags+0x10,pmap+0x18.',
            'Both Mach zone log enumeration/retrieval RPCs in this release kernel are unconditional return5 stubs. Do not promise that zlog plus user-space retrieval will provide allocation history on this kernel.',
        ],
        'limits':[
            'Binary inventories preserve actual local files; KDK UUID identity is not runtime patched-byte equivalence.',
            'No panic-time member object/vtable/ktv, allocator history, page attributes, PV or PTE were captured. No object class or first corrupter can be inferred from early.kalloc.48 or process name.',
            'Selected vtable and metadata checks do not certify the entire old TGL/Tahoe IOAF2 ABI.',
            'Raw relocatable kext disassembly contains unresolved import placeholders; relocation tables above are authoritative for those targets.',
        ],
    }
    (ROOT/'ga417/reports/MEMORY-LIFECYCLE-AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS:',len(extracted),'complete selected functions;3 vtables;6 incident caller-DWARF input; no target changes')


if __name__=='__main__':
    main()
