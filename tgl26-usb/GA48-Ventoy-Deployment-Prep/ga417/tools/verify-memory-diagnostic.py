#!/usr/bin/env python3
"""Offline adversarial checks for missing/corrupt memory and branch distinction.

Uses the real matched KDK header/instructions, synthetic metadata only. Does not
prove LLDB/KDP connectivity, a live capture, or a repaired kernel.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('diag',Path(__file__).with_name('panic_memory_lldb.py'))
diag=importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)


def main():
    layout=json.loads(diag.LAYOUT.read_text())
    kernel=(ROOT/'ga417/private/panic-kdk/kernel').read_bytes()
    assert hashlib.sha256(kernel).hexdigest()==layout['kernel_sha256']
    slide=0x80000
    header=int(layout['kernel_header_unslid'],16)+slide
    size=32+struct.unpack_from('<I',kernel,20)[0]
    regions={header:kernel[:size]}
    for r in layout['verification']:
        regions[int(r['address'],16)+slide]=bytes.fromhex(r['bytes'])

    def reader(address,n):
        for base,data in regions.items():
            if base<=address and address+n<=base+len(data):
                return data[address-base:address-base+n]
        raise ValueError('Synthetic capture explicitly lacks '+hex(address))

    def glob(name,value,n):
        regions[int(layout['globals'][name],16)+slide]=value.to_bytes(n,'little')

    def snap():
        return diag.Snapshot(reader,layout,slide)

    checks=[]
    snap().verify()
    checks.append('real KDK header,UUID and4 exact instruction ranges accepted at synthetic slide')
    physical=0x101311000
    ppn=physical>>12
    attr,pv=0xffffff9000000000,0xffffff9100000000
    glob('_pmap_initialized',1,4)
    glob('_last_managed_page',ppn-1,4)
    assert snap().page(physical)['predicate']=='FAIL_PPN_ABOVE_LAST_MANAGED'
    glob('_last_managed_page',ppn,4)
    glob('_pmap_phys_attributes',attr,8)
    regions[attr+ppn]=b'\0'
    assert snap().page(physical)['predicate']=='FAIL_MANAGED_ATTRIBUTE_BIT_CLEAR'
    regions[attr+ppn]=b'\x01'
    glob('_pv_head_table',pv,8)
    regions[pv+ppn*32]=struct.pack('<4Q',0,0,0x12345003,0xffffff9200000000)
    assert snap().page(physical)['predicate']=='FAIL_PV_PMAP_NONNULL'
    regions[pv+ppn*32]=bytes(32)
    assert snap().page(physical)['predicate']=='PASS_AT_SNAPSHOT_TIME'
    checks.append('3 distinct failure predicates and pass-at-snapshot distinguished')
    del regions[attr+ppn]
    s=snap()
    try:
        s.page(physical)
        raise AssertionError('Missing attribute accepted')
    except ValueError as exc:
        assert 'explicitly lacks' in str(exc) and 'hex' not in s.reads[-1]
    checks.append('missing attribute retained as error, never zero-filled/falsely classified')
    short=diag.Snapshot(lambda a,n:b'\0'*(n-1),layout,slide)
    try:
        short.page(physical)
        raise AssertionError('Short read accepted')
    except ValueError as exc:
        assert 'Short read' in str(exc)
    checks.append('short read rejected')
    corrupt=bytearray(regions[header])
    uuid_bytes=bytes.fromhex(layout['kernel_uuid'].replace('-',''))
    pos=corrupt.index(uuid_bytes)
    corrupt[pos]^=1
    regions[header]=bytes(corrupt)
    try:
        snap().verify()
        raise AssertionError('Wrong UUID accepted')
    except ValueError as exc:
        assert 'UUID' in str(exc)
    regions[header]=kernel[:size]
    first=layout['verification'][0]
    a=int(first['address'],16)+slide
    correct=regions[a]
    regions[a]=b'\x90'+correct[1:]
    try:
        snap().verify()
        raise AssertionError('Modified code accepted')
    except ValueError as exc:
        assert 'code differs' in str(exc)
    regions[a]=correct
    checks.append('wrong loaded UUID and altered verification instructions rejected')
    placeholder=ROOT/'ga416/private/crash-series/kernelcore-20261025T1207.bin'
    data=placeholder.read_bytes()
    assert len(data)==1048576 and data==(bytes(4095)+b'\n')*256
    zero=diag.Snapshot(lambda a,n:data[:n],layout,slide)
    try:
        zero.verify()
        raise AssertionError('Existing placeholder accepted')
    except ValueError as exc:
        assert 'Mach-O kernel header' in str(exc)
    checks.append('actual1MiB kernelcore placeholder (4095NUL+LF repeated256) rejected as loaded kernel memory')
    obj,vptr=0xffffff9024954b50,0xffffff9200000000
    regions[obj]=struct.pack('<Q',vptr)+bytes(56)
    for off in [8,0x28,0x50,0x90]:
        regions[vptr+off]=struct.pack('<Q',header+0x1234+off)
    info=bytearray(184)
    meta,meta_base=0xffffff9300000000,0xffffff9300000000-((obj>>8)&0xffffffff0)
    struct.pack_into('<4Q',info,0,obj&~0xfff,(obj&~0xfff)+0x1000,meta,meta+16)
    struct.pack_into('<Q',info,176,meta_base)
    regions[int(layout['globals']['_zone_info'],16)+slide]=bytes(info)
    regions[meta]=struct.pack('<H',87)+bytes(14)
    r=snap().object(obj)
    assert r['raw_zone_index']==87 and r['class_identity']=='UNPROVEN'
    checks.append('raw zone metadata index captured without inferring object class/ownership')
    report={'status':'OFFLINE_VERIFIER_PASS_NOT_A_LIVE_CAPTURE','checks':checks,
            'placeholder_sha256':hashlib.sha256(data).hexdigest(),
            'helper_sha256':hashlib.sha256(Path(spec.origin).read_bytes()).hexdigest(),
            'layout_sha256':hashlib.sha256(diag.LAYOUT.read_bytes()).hexdigest(),
            'limits':['Synthetic metadata is test data, not HP panic-time evidence.',
                      'Actual LLDB command registration/KDP or real kernel-core execution remain untested.']}
    (ROOT/'ga417/reports/MEMORY-DIAGNOSTIC-VERIFY.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
