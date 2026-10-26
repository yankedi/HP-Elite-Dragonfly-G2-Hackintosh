#!/usr/bin/env python3
"""Expanded offline symbol-bounded corpus, direct graph and register references.

Linear decode is not reachability. All indirect targets remain unresolved.
"""
import bisect
import gzip
import hashlib
import json
import mmap
import pathlib
import re
import subprocess
from macho import Image, FormatError, safe_name, confined, branch_kind, direct_target
from disassemble import Decoder

ROOT=pathlib.Path(__file__).resolve().parents[1]
REGISTER=re.compile(r'(?<![0-9a-f])0x(?:cec4|ceb8|cebc|4094|a278|a188|d84|130044)(?![0-9a-f])')
SELECT=re.compile(r'ForceWake|PowerDomain|gatherKey|checkEngineStatus|Hang|hang|[Rr]eset|[Rr]estart|CSB|Execlist|[Ww]atchdog|SafeReadRegister|SafeWriteRegister|checkGPU|handleGPU')


def main():
    dest=ROOT/'analysis/expanded';dest.mkdir(parents=True,exist_ok=True)
    inv=json.loads((ROOT/'analysis/kc/SystemKernelExtensions.kc.json').read_text())
    decoder=Decoder();edges=[];refs=[];counts=[]
    with confined(ROOT,inv['source']).open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
        digest=hashlib.sha256(data).hexdigest()
        if digest!=inv['sha256']:raise FormatError('source inventory SHA mismatch')
        for item in inv['images']:
            im=Image(data,item['header_fileoff'],item['name'])
            sections=[s for s in im.sections if s['name']=='__text']
            byva={}
            for s in im.code_symbols():
                byva.setdefault(s['value'],[]).append(s['name'])
            starts=sorted(byva);functions=[]
            demnames=[byva[a][0] for a in starts]
            dm=subprocess.run(['c++filt'],input='\n'.join(n[1:] if n.startswith('__Z') else n for n in demnames),text=True,capture_output=True,check=True).stdout.splitlines()
            for idx,va in enumerate(starts):
                sec=next(s for s in sections if s['addr']<=va<s['addr']+s['size'])
                end=min(starts[idx+1] if idx+1<len(starts) else sec['addr']+sec['size'],sec['addr']+sec['size'])
                if end-va>256*1024: raise RuntimeError('extent budget')
                off=im.va_to_offset(va,end-va);raw=bytes(data[off:off+end-va])
                insns=decoder.decode(raw,va)
                for ins in insns:
                    ins['kc_fileoff']=off+ins['va']-va
                    kind=branch_kind(ins['mnemonic'])
                    if kind in ('call','jmp'):
                        op=ins['operands']
                        edge={'image':item['name'],'from_entry':va,'from_name':dm[idx],
                              'instruction_va':ins['va'],'kc_fileoff':ins['kc_fileoff'],
                              'bytes':ins['bytes'],'kind':kind,'printed_mnemonic':ins['mnemonic'],
                              'reachability':'unproven_linear_decode'}
                        t=direct_target(op)
                        if t is not None:
                            edge.update(target_va=t,target_symbols=byva.get(t,[]))
                            ins['target_symbols']=byva.get(t,[])
                        else: edge.update(unresolved_indirect=op)
                        edges.append(edge)
                    if REGISTER.search(ins['operands']):
                        refs.append(dict(ins,image=item['name'],function_entry=va,function_name=dm[idx],
                                         classification='literal operand occurrence; not automatically MMIO or reachable'))
                functions.append({'image':item['name'],'uuid':im.uuid,'entry_va':va,'extent_end_va':end,
                                  'kc_fileoff':off,'symbols':byva[va],'name':dm[idx],
                                  'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_bytes':raw.hex(),
                                  'extent_kind':'symbol_bounded_fragment','reachability':'unproven_linear_decode',
                                  'decode_complete':sum(i['size'] for i in insns)==len(raw),
                                  'decoded_bytes':sum(i['size'] for i in insns),'instructions':insns})
            payload={'source':inv['source'],'source_sha256':inv['sha256'],'image_uuid':im.uuid,
                     'extent_basis':'next text symbol/section end; not recovered CFG',
                     'functions':functions}
            prefix=safe_name(item['name'])
            with gzip.GzipFile(filename=str(confined(dest,prefix+'.all.json.gz')),mode='wb',mtime=0) as gz:
                gz.write((json.dumps(payload,separators=(',',':'))+'\n').encode())
            selected=[fun for fun in functions if SELECT.search(fun['name'])]
            confined(dest,prefix+'.selected.json').write_text(json.dumps(dict(payload,functions=selected),indent=2)+'\n')
            lines=[f"SOURCE {inv['source']} SHA256 {inv['sha256']} UUID {im.uuid}",
                   'KC coordinate VA; symbol-bounded extents; indirect calls unresolved.']
            for fun in selected:
                lines.extend(['',f"{fun['name']} ENTRY {fun['entry_va']:#x} FILE {fun['kc_fileoff']:#x} RAW_SHA {fun['raw_sha256']}"])
                for ins in fun['instructions']:
                    labels=' ; '+','.join(ins['target_symbols']) if ins.get('target_symbols') else ''
                    lines.append(f"{ins['va']:016x} @{ins['kc_fileoff']:08x} {ins['bytes']:<32} {ins['mnemonic']:<8} {ins['operands']}{labels}")
                if fun['decoded_bytes']!=len(bytes.fromhex(fun['raw_bytes'])):lines.append('UNDECODED TAIL retained in JSON raw_bytes')
            confined(dest,prefix+'.selected.txt').write_text('\n'.join(lines)+'\n')
            counts.append({'image':item['name'],'all_functions':len(functions),'selected':len(selected),
                           'decoded_bytes':sum(f['decoded_bytes'] for f in functions),
                           'upper_bound_bytes':sum(len(bytes.fromhex(f['raw_bytes'])) for f in functions)})
        if hashlib.sha256(data).hexdigest()!=digest:raise FormatError('source changed while parsing')
    decoder.close()
    for name,obj in [('direct-and-indirect-edges.json',edges),('register-literal-occurrences.json',refs),('coverage.json',counts)]:
        (dest/name).write_text(json.dumps(obj,indent=2)+'\n')
    print(json.dumps(counts,indent=2))


if __name__=='__main__':main()
