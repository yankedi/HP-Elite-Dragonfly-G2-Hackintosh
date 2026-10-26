#!/usr/bin/env python3
"""Read exact stock XNU CAS implementation; no atomic operation on real state."""
import hashlib
import json
import mmap
import pathlib
from macho import Image, FormatError
from disassemble import Decoder

ROOT=pathlib.Path(__file__).resolve().parents[1]


def main():
    inv=json.loads((ROOT/'analysis/kc/BootKernelExtensions.kc.json').read_text())
    item=next(i for i in inv['images'] if i['name']=='com.apple.kernel')
    with (ROOT/inv['source']).open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
        if hashlib.sha256(data).hexdigest()!=inv['sha256']:raise FormatError('source SHA mismatch')
        im=Image(data,item['header_fileoff']);symbols=im.code_symbols()
        s=next(s for s in symbols if s['name']=='_OSCompareAndSwap')
        end=min(sym['value'] for sym in symbols if sym['value']>s['value'])
        off=im.va_to_offset(s['value'],end-s['value']);raw=bytes(data[off:off+end-s['value']])
        dec=Decoder()
        try:ins=dec.decode(raw,s['value'])
        finally:dec.close()
        for i in ins:i['kc_fileoff']=off+i['va']-s['value']
        result={'source':inv['source'],'source_sha256':inv['sha256'],'uuid':im.uuid,'symbol':s['name'],
                'entry_va':s['value'],'kc_fileoff':off,'raw_bytes':raw.hex(),
                'raw_sha256':hashlib.sha256(raw).hexdigest(),'instructions':ins,
                'interpretation':'lock cmpxchg stores when expected matches; sete returns1 when ZF=1 (successful compare/exchange)',
                'source_application':'inputs/kern_igfx.cpp:1578 returns on successful0->1, leaves flag1; this is an existing GA33 source defect, not a GA35 mock defect or attested installed binary'}
        (ROOT/'analysis/atomic-semantics.json').write_text(json.dumps(result,indent=2)+'\n')
        for i in ins:print(hex(i['va']),i['bytes'],i['mnemonic'],i['operands'])


if __name__=='__main__':main()
