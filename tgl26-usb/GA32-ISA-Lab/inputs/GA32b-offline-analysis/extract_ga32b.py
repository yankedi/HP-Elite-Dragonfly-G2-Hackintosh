#!/usr/bin/env python3
"""Offline THAG v2 extraction; reads only, never modifies source capture.
Usage: python extract_ga32b.py INPUT.bin OUTPUT_DIR
Exact field offsets from GA3.2 THAG-FORMAT.md; validates record content.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

RECORD = 0xC2A0
MAGIC = b'THAG'


def u32(blob, offset):
    return struct.unpack_from('<I', blob, offset)[0]


def u64(blob, offset):
    return struct.unpack_from('<Q', blob, offset)[0]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run(src, outdir):
    source = Path(src)
    data = source.read_bytes()
    if len(data) not in (RECORD, RECORD*2, RECORD*3):
        raise ValueError('unexpected THAG v2 record count/length')
    records = [data[i:i+RECORD] for i in range(0, len(data), RECORD)]
    for i,r in enumerate(records):
        if r[:4] != MAGIC or u32(r,4) != i:
            raise ValueError(f'bad THAG record {i}')
    i = next((i for i,r in enumerate(records) if u32(r,0x90)==0 and u32(r,0x90+0xc0)==255), None)
    if i is None:
        raise ValueError('no confirmed OK record with eight batch pages')
    r = records[i]
    out = Path(outdir)
    out.mkdir(exist_ok=True, parents=True)
    batch = r[0x2a0:0x82a0]
    vs = r[0x82a0:0xa2a0]
    ps = r[0xa2a0:0xc2a0]
    bb = u64(r,0x90+0x68)
    pml4 = u64(r,0x90+0x70)
    start = u64(r,0x90+0x78)
    instr = u64(r,0x90+0x118)
    vs_offset = u64(r,0x90+0x120)
    ps_offset = u64(r,0x90+0x128)
    vs_addr = u64(r,0x90+0x130)
    ps_addr = u64(r,0x90+0x138)
    if vs_addr != instr+vs_offset or ps_addr != instr+ps_offset:
        raise ValueError('Shader address does not match instruction base and offsets')
    if vs_offset>=8192 or ps_offset>=8192:
        raise ValueError('entry is outside captured window')
    # These are candidate inspection windows, not proven complete EU kernels.
    candidates = {
        'batch-8pages.bin': batch,
        'shared-eu-window-2pages.bin': vs,
        'ps-from-entry-to-next-entry-candidate.bin': ps[ps_offset:vs_offset] if ps_offset<vs_offset else ps[ps_offset:],
        'vs-from-entry-to-last-nonzero-candidate.bin': vs[vs_offset:(max(i for i,x in enumerate(vs) if x)+16)//16*16],
    }
    for name, blob in candidates.items():
        (out/name).write_bytes(blob)
    headers = []
    for name, word, offset in [('STATE_BASE_ADDRESS',0x61010014,0x69f8), ('3DSTATE_PS',0x7820000a,0x6b6c), ('3DSTATE_VS',0x78100007,0x6c00)]:
        found=u32(batch,offset)
        if found!=word:
            raise ValueError(f'{name} expected {word:#x}, found {found:#x}')
        headers.append({'kind':name,'batch_offset':hex(offset),'gpu_va':hex(start+offset),'header':hex(word),'dword_length':(word&0xff)+2})
    status=[]
    for idx,rec in enumerate(records):
        b=rec[0x2a0:0x82a0]; v=rec[0x82a0:0xa2a0];p=rec[0xa2a0:0xc2a0]
        status.append({'index':idx,'result_code':u32(rec,0x90),'attempt_reason':u32(rec,0x14),'wake_domain':u32(rec,0x10),
                       'resolve_diag':hex(u32(rec,0x80)), 'page_table_reads':u32(rec,0x90+0xc8),
                       'data_page_reads':u32(rec,0x90+0xcc),'read_bytes':u32(rec,0x90+0xd0),
                       'batch_nonzero':sum(x!=0 for x in b),'vs_window_nonzero':sum(x!=0 for x in v),'ps_window_nonzero':sum(x!=0 for x in p)})
    j={
        'source':str(source),'size':len(data),'sha256':digest(data),'record_size':RECORD,'records':status,
        'success_record':i,'bb_addr':hex(bb),'pml4_candidate':hex(pml4),'batch_start':hex(start),
        'instruction_base':hex(instr),'vs_offset':hex(vs_offset),'ps_offset':hex(ps_offset),
        'vs_entry':hex(vs_addr),'ps_entry':hex(ps_addr),'vs_ps_windows_identical':vs==ps,
        'vs_ps_first_page_same':vs[:4096]==ps[:4096],
        'entry_bytes':{
            'ps_32':ps[ps_offset:ps_offset+32].hex(),
            'vs_32':vs[vs_offset:vs_offset+32].hex()},
        'batch_headers':headers,
        'files':{k:{'size':len(v),'sha256':digest(v)} for k,v in candidates.items()},
        'note':'Slices marked candidate are NOT verified kernel boundaries or disassembled ISA.'
    }
    (out/'extraction.json').write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(j,ensure_ascii=False,indent=2))

if __name__=='__main__':
    if len(sys.argv)!=3:sys.exit(__doc__)
    run(sys.argv[1],sys.argv[2])
