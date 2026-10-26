#!/usr/bin/env python3
"""Read-only GA417 stopped-kernel/core memory capture, loaded with LLDB.

This helper does not attach, evaluate target expressions, call target functions,
resume, or write target memory. A real stopped target or usable kernel core and
the exact matching loaded kernel module are prerequisites.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shlex
import struct
import uuid

ROOT=Path(__file__).resolve().parents[2]
LAYOUT=ROOT/'ga417/reports/MEMORY-DIAGNOSTIC-LAYOUT.json'


def canonical(va):
    return 0 <= va < (1<<64) and va>>47 == 0x1ffff


class Snapshot:
    def __init__(self,reader,layout,slide):
        if slide<0 or slide & 0xfff:
            raise ValueError('Invalid kernel slide')
        self.reader,self.layout,self.slide=reader,layout,slide
        self.reads=[]

    def read(self,va,n,purpose):
        row={'address':hex(va),'size':n,'purpose':purpose}
        self.reads.append(row)
        try:
            if not canonical(va) or not canonical(va+n-1) or not 0<n<=1048576:
                raise ValueError('Invalid/bounded kernel memory range')
            data=self.reader(va,n)
            if len(data)!=n:
                raise ValueError('Short read; missing bytes cannot be filled with zero')
            row['hex']=data.hex()
            return data
        except Exception as exc:
            row['error']=str(exc)
            raise

    def integer(self,va,n,purpose):
        return int.from_bytes(self.read(va,n,purpose),'little')

    def global_value(self,name,n):
        return self.integer(int(self.layout['globals'][name],16)+self.slide,n,name)

    def verify(self):
        base=int(self.layout['kernel_header_unslid'],16)+self.slide
        header=self.read(base,32,'loaded kernel Mach-O header')
        magic,cpu,_,_,count,size,_,_=struct.unpack('<8I',header)
        if magic!=0xfeedfacf or cpu!=0x01000007 or not 0<count<=1024 or not 8<=size<=1048576:
            raise ValueError('Not a bounded x86_64 Mach-O kernel header')
        commands=self.read(base+32,size,'loaded kernel load commands')
        off=0
        found=[]
        for _ in range(count):
            if off+8>len(commands):
                raise ValueError('Truncated load command')
            cmd,n=struct.unpack_from('<II',commands,off)
            if n<8 or off+n>len(commands):
                raise ValueError('Malformed load command')
            if cmd==0x1b:
                if n!=24:
                    raise ValueError('Invalid LC_UUID')
                found.append(str(uuid.UUID(bytes=commands[off+8:off+24])).upper())
            off+=n
        if found!=[self.layout['kernel_uuid']]:
            raise ValueError('Loaded memory UUID differs from exact KDK')
        for v in self.layout['verification']:
            expected=bytes.fromhex(v['bytes'])
            if self.read(int(v['address'],16)+self.slide,len(expected),'verify '+v['symbol'])!=expected:
                raise ValueError('Loaded code differs: '+v['symbol'])

    def page(self,physical):
        if physical<0 or physical & 0xfff or physical>>12>0x7fffffff:
            raise ValueError('Expected aligned physical page, PPN <= 0x7fffffff')
        ppn=physical>>12
        r={'physical':hex(physical),'ppn':hex(ppn)}
        initialized=self.global_value('_pmap_initialized',4)
        r['pmap_initialized']=initialized
        if not initialized:
            r['predicate']='BYPASS_NOT_INITIALIZED'
            return r
        last=self.global_value('_last_managed_page',4)
        r['last_managed_page']=hex(last)
        if ppn>last:
            r['predicate']='FAIL_PPN_ABOVE_LAST_MANAGED'
            return r
        attr=self.global_value('_pmap_phys_attributes',8)
        r['attribute']=self.integer(attr+ppn,1,'phys_attributes[ppn]')
        if not r['attribute'] & 1:
            r['predicate']='FAIL_MANAGED_ATTRIBUTE_BIT_CLEAR'
            return r
        pv=self.global_value('_pv_head_table',8)
        address=pv+ppn*self.layout['pv_entry_size']
        raw=self.read(address,self.layout['pv_entry_size'],'pv_rooted_entry[ppn]')
        r.update(pv_address=hex(address),pv_raw=raw.hex(),
                 pv_next=hex(int.from_bytes(raw[:8],'little')),
                 pv_prev=hex(int.from_bytes(raw[8:16],'little')),
                 pv_va_and_flags=hex(int.from_bytes(raw[16:24],'little')),
                 pv_pmap=hex(int.from_bytes(raw[24:32],'little')))
        r['predicate']='FAIL_PV_PMAP_NONNULL' if int(r['pv_pmap'],16) else 'PASS_AT_SNAPSHOT_TIME'
        return r

    def object(self,address):
        # Raw evidence only: a freed/corrupt vptr is not a reliable class identity.
        raw=self.read(address,64,'reported wrong-zone object bytes')
        vptr=int.from_bytes(raw[:8],'little')
        r={'object':hex(address),'raw64':raw.hex(),'vptr':hex(vptr),'class_identity':'UNPROVEN'}
        if canonical(vptr):
            for off in [8,0x28,0x50,0x90]:
                r['vtable_'+hex(off)]=hex(self.integer(vptr+off,8,'raw vtable slot '+hex(off)))
        else:
            r['vptr_error']='Noncanonical kernel pointer; do not dereference'
        zi=self.read(int(self.layout['globals']['_zone_info'],16)+self.slide,self.layout['zone_info_size'],'zone_info raw')
        low,high=struct.unpack_from('<QQ',zi)
        r['zone_map_range']=[hex(low),hex(high)]
        if low<=address<high:
            meta_base=struct.unpack_from('<Q',zi,self.layout['zone_meta_base_offset'])[0]
            meta=(meta_base+((address>>8)&int(self.layout['zone_meta_address_mask'],16)))&((1<<64)-1)
            meta_low,meta_high=struct.unpack_from('<QQ',zi,16)
            r['metadata_address']=hex(meta)
            if meta_low<=meta and meta+self.layout['zone_meta_record_size']<=meta_high:
                md=self.read(meta,self.layout['zone_meta_record_size'],'raw object page zone metadata')
                r['metadata_raw']=md.hex()
                r['raw_zone_index']=int.from_bytes(md[:2],'little')&int(self.layout['zone_index_mask'],16)
                r['zone_index_limit']='Raw page record; secondary-chunk resolution and allocation ownership not inferred'
            else:
                r['metadata_error']='Computed metadata outside reported meta_range'
        else:
            r['metadata_error']='Object outside reported zone map range'
        return r


def command(debugger,command,result,internal_dict):
    import lldb
    parser=argparse.ArgumentParser(prog='ga417-memory',exit_on_error=False)
    parser.add_argument('--page',type=lambda s:int(s,0),action='append',default=[])
    parser.add_argument('--object',type=lambda s:int(s,0))
    parser.add_argument('--out',required=True,type=Path)
    try:
        args=parser.parse_args(shlex.split(command))
        if not args.page and args.object is None:
            raise ValueError('Provide current panic physical --page or wrong-zone --object')
        if len(args.page)>8:
            raise ValueError('At most8 physical pages per capture')
        if args.out.exists():
            raise FileExistsError('Preserve existing evidence: output already exists')
        target=debugger.GetSelectedTarget()
        process=target.GetProcess()
        if process.GetState() not in [lldb.eStateStopped,lldb.eStateCrashed]:
            raise ValueError('Requires already-stopped kernel/core; helper never stops/resumes targets')
        layout=json.loads(LAYOUT.read_text())
        modules=[m for m in target.module_iter() if (m.GetUUIDString() or '').upper()==layout['kernel_uuid']]
        if len(modules)!=1:
            raise ValueError('Exactly one UUID-matching kernel module must already be loaded')
        base=modules[0].GetObjectFileHeaderAddress().GetLoadAddress(target)
        if base==lldb.LLDB_INVALID_ADDRESS:
            raise ValueError('Kernel load address is unavailable')
        slide=base-int(layout['kernel_header_unslid'],16)

        def reader(va,n):
            err=lldb.SBError()
            data=process.ReadMemory(va,n,err)
            if not err.Success():
                raise ValueError(str(err))
            return data

        snap=Snapshot(reader,layout,slide)
        report={'status':'NOT_VERIFIED','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'kernel_uuid':layout['kernel_uuid'],'slide':hex(slide),
                'layout_sha256':hashlib.sha256(LAYOUT.read_bytes()).hexdigest(),
                'limits':'Stopped snapshot only; no first-corrupter/ownership history or PTE interpretation. Not a fix.',
                'reads':snap.reads,'pages':[]}
        try:
            snap.verify()
            report['status']='VERIFIED_IDENTITY_AND_CODE'
            for page in args.page:
                report['pages'].append(snap.page(page))
            if args.object is not None:
                report['object']=snap.object(args.object)
            report['status']='READ_ONLY_SNAPSHOT_COMPLETE'
        except Exception as exc:
            report['status']='INCOMPLETE_NO_MISSING_BYTES_ASSUMED'
            report['error']=str(exc)
        with args.out.open('x') as f:
            json.dump(report,f,indent=2)
            f.write('\n')
        result.AppendMessage(report['status']+'; saved local evidence '+str(args.out))
    except (Exception,SystemExit) as exc:
        result.SetError(str(exc))


def __lldb_init_module(debugger,internal_dict):
    debugger.HandleCommand('command script add -f '+__name__+'.command ga417-memory')
