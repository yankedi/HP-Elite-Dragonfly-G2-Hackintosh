#!/usr/bin/env python3
"""Offline ad-hoc page/special-slot verification, not Apple policy verification."""
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import struct

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT/'ga416/private/l3-six'
BUNDLE = WORK/'build/product/NootedGreen.kext'


def audit(bundle, altered=None):
    altered = altered or {}
    files = {str(p.relative_to(bundle)): altered.get(str(p.relative_to(bundle)), p.read_bytes())
             for p in bundle.rglob('*') if p.is_file()}
    assert set(files) == {'Contents/Info.plist', 'Contents/MacOS/NootedGreen', 'Contents/_CodeSignature/CodeResources'}
    resources = plistlib.loads(files['Contents/_CodeSignature/CodeResources'])
    assert not resources['files'] and not resources['files2']  # this three-file bundle has no other resources
    data = files['Contents/MacOS/NootedGreen']
    assert data[:4] == b'\xcf\xfa\xed\xfe'
    n, size = struct.unpack_from('<II',data,16); pos=32; sig=None
    for _ in range(n):
        cmd, length = struct.unpack_from('<II',data,pos)
        assert length >= 8 and pos+length <= 32+size
        if cmd == 0x1d:
            assert sig is None
            sig=struct.unpack_from('<II',data,pos+8)
        pos+=length
    assert sig and pos == 32+size
    off, length=sig; assert off+length <= len(data)
    blob=data[off:off+length]
    u32=lambda b,p:struct.unpack_from('>I',b,p)[0]
    assert u32(blob,0)==0xfade0cc0 and u32(blob,4)<=len(blob)
    count=u32(blob,8); entries={}
    for i in range(count):
        slot, bo=struct.unpack_from('>II',blob,12+8*i)
        assert slot not in entries and bo >= 12+8*count
        bl=u32(blob,bo+4); assert bl>=8 and bo+bl<=u32(blob,4)
        entries[slot]=blob[bo:bo+bl]
    assert set(entries)=={0,2,4096,65536}
    assert entries[65536]==struct.pack('>II',0xfade0b01,8)  # no CMS required by ADHOC
    result=[]
    for slot in [0,4096]:
        cd=entries[slot]; assert u32(cd,0)==0xfade0c02
        flags=u32(cd,12); ho=u32(cd,16); ident=u32(cd,20)
        ns,nc,limit=struct.unpack_from('>III',cd,24)
        hs,ht,platform,power=struct.unpack_from('4B',cd,36)
        assert flags==2 and ns==3 and limit==off and power<=30
        identifier=cd[ident:cd.index(b'\0',ident)].decode()
        assert identifier=='com.StezzaPilot.NootedGreen'
        alg={1:'sha1',2:'sha256'}[ht]
        assert hs==hashlib.new(alg).digest_size and ho+nc*hs<=len(cd)
        page=1<<power; assert nc==(limit+page-1)//page
        for j in range(nc):
            assert hashlib.new(alg,data[j*page:min((j+1)*page,limit)]).digest()==cd[ho+j*hs:ho+(j+1)*hs], ('codepage',slot,j)
        specials={1:files['Contents/Info.plist'],2:entries[2],3:files['Contents/_CodeSignature/CodeResources']}
        for j,value in specials.items():
            assert hashlib.new(alg,value).digest()==cd[ho-j*hs:ho-(j-1)*hs],('special',slot,j)
        result.append({'slot':slot,'flags':'ADHOC','algorithm':alg,'pages_verified':nc,
                       'special_slots_verified':[1,2,3],'identifier':identifier})
    return {'status':'OFFLINE_ADHOC_INTEGRITY_PASS','directories':result,
            'bundle_sha256':{name:hashlib.sha256(value).hexdigest() for name,value in files.items()},
            'native_codesign_strict_deep':'NOT_RUN_MACOS_UNAVAILABLE','CMS':'NOT_REQUIRED_ADHOC',
            'Apple_load_policy_and_runtime':'NOT_TESTED'}


def main():
    result=audit(BUNDLE)
    # Meaningful negative controls: altered code page, Info and resource envelope must be rejected.
    rejected=[]
    for name,offset in [('Contents/MacOS/NootedGreen',0x1000),('Contents/Info.plist',0),
                        ('Contents/_CodeSignature/CodeResources',0)]:
        data=bytearray((BUNDLE/name).read_bytes()); data[offset]^=1
        try: audit(BUNDLE,{name:bytes(data)})
        except (AssertionError, ValueError, plistlib.InvalidFileException): rejected.append(name)
        else: raise AssertionError('Modified signed material was accepted: '+name)
    result['corruption_controls_rejected']=rejected
    spec=importlib.util.spec_from_file_location('c',ROOT/'ga414/tools/common.py')
    c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    b=c.builder();binary=BUNDLE/'Contents/MacOS/NootedGreen'
    dis=c.run([b.LLVM_BIN/'llvm-objdump','--macho','--disassemble','--disassemble-symbols=__ZN5Gen1110getGPUInfoEPv',binary])
    (WORK/'getGPUInfo-disassembly.txt').write_text(dis)
    # x86_64 immediate store directly confirms the built +0x1164 write is six.
    assert bytes.fromhex('c7836411000006000000') in binary.read_bytes()
    result['machine_code_L3_store']={'bytes':'c7 83 64 11 00 00 06 00 00 00','meaning':'movl $6, 0x1164(%rbx)','observed':True}
    result['rcodesign_verify_error']=json.loads((WORK/'signature-verify.json').read_text())
    result['same_verifier_error_on_native_verified_baseline']=json.loads((WORK/'signature-verifier-baseline-control.json').read_text())
    (ROOT/'ga416/reports/L3-6-SIGNATURE.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','directories','machine_code_L3_store']}))


if __name__=='__main__':main()
