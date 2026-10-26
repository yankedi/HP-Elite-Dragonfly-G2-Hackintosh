#!/usr/bin/env python3
"""Offline CodeDirectory page hashes; NOT CMS certificate/trust verification."""
import hashlib
import json
from pathlib import Path
import struct
import sys

def audit(path):
    data=Path(path).read_bytes()
    assert data[:4]==b'\xcf\xfa\xed\xfe','thin Mach-O64 required'
    def u32(b,o):return struct.unpack_from('>I',b,o)[0]
    n,sz=struct.unpack_from('<II',data,16);pos=32;signature=None
    for _ in range(n):
        cmd,size=struct.unpack_from('<II',data,pos)
        assert size>=8 and pos+size<=32+sz
        if cmd==0x1d:signature=struct.unpack_from('<II',data,pos+8)
        pos+=size
    assert signature is not None,'no signature command'
    off,length=signature;assert off+length<=len(data)
    blob=data[off:off+length]
    assert u32(blob,0)==0xfade0cc0 and u32(blob,4)<=len(blob)
    directories=[]
    for i in range(u32(blob,8)):
        slot,bo=struct.unpack_from('>II',blob,12+i*8)
        assert bo+8<=len(blob)
        if u32(blob,bo)!=0xfade0c02:continue
        cd=blob[bo:bo+u32(blob,bo+4)]
        assert len(cd)>=44
        version=u32(cd,8);ho=u32(cd,16);slots=u32(cd,28);limit=u32(cd,32)
        hs,ht,platform,power=struct.unpack_from('4B',cd,36)
        if version>=0x20300 and limit==0:limit=struct.unpack_from('>Q',cd,56)[0]
        assert limit<=off and power<=30 and ho+slots*hs<=len(cd)
        page=1<<power if power else limit
        assert page>0 and slots==(limit+page-1)//page
        alg={1:'sha1',2:'sha256',3:'sha256',4:'sha384'}[ht]
        mismatch=[]
        for j in range(slots):
            got=hashlib.new(alg,data[j*page:min((j+1)*page,limit)]).digest()[:hs]
            if got!=cd[ho+j*hs:ho+(j+1)*hs]:mismatch.append(j)
        directories.append(dict(slot=slot,algorithm=alg,hash_size=hs,pages=slots,page_size=page,
                                mismatched_pages=mismatch,page_hashes_match=not mismatch))
    assert directories,'no CodeDirectory'
    return dict(path=str(Path(path).resolve()),sha256=hashlib.sha256(data).hexdigest(),
                directories=directories,cms_trust='NOT_VERIFIED')

if __name__=='__main__':
    print(json.dumps([audit(p) for p in sys.argv[1:]],indent=2))
