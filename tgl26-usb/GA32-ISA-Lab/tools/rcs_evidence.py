#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
GEN=ROOT/'tools/mesa-eu/source/src/intel/genxml/gen11.xml'

def fields(name, words, generation=11):
    xml=GEN if generation==11 else GEN.with_name('gen12.xml')
    cmd=ET.parse(xml).getroot().find(f"instruction[@name='{name}']")
    bits=int.from_bytes(b''.join(x.to_bytes(4,'little') for x in words),'little');out={}
    for f in cmd.findall('field'):
        a,b=int(f.attrib['start']),int(f.attrib['end'])
        if b>=len(words)*32:continue
        v=(bits>>a)&((1<<(b-a+1))-1)
        if f.attrib['type'] in {'address','offset'}:v <<= a%32
        out[f.attrib['name']]=v
    return out

def main():
    records=[]
    for stage in ['GA2','GA31','GA32']:
        archived=ROOT/'inputs/gpuRestart'/stage
        directory=archived if archived.is_dir() else ROOT.parent/stage/'reports'
        for f in sorted(directory.glob('*.gpuRestart')):
            if f.name.startswith('._'):
                continue  # AppleDouble metadata, not a GPU restart report.
            text=f.read_text(errors='replace')
            r={'stage':stage,'path':str(f),'original_path':str(ROOT.parent/stage/'reports'/f.name),
               'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
            for n in ['RING_HEAD','RING_TAIL','RING_START','BB_ADDR','ACTHD','IPEIR']:
                m=re.search(r'\b'+n+r'\s*=\s*(0x[0-9a-fA-F]+)',text);r[n]=int(m[1],16) if m else None
            for key,pat in [('IPEHR',r'IPEHR=(0x[0-9a-fA-F]+)'),('INSTDONE',r'INSTDONE \(=(0x[0-9a-fA-F]+)')]:
                m=re.search(pat,text);r[key]=int(m[1],16) if m else None
            m=re.search(r'hardware context ID\[(\d+)\]',text);r['context_id']=int(m[1]) if m else None
            ring=text.split('Dumping RCS ring buffer contents:')[-1].split('AubList command line:')[0]
            words={int(m[1],16):int(m[2],16) for m in re.finditer(r'^(0x[0-9a-fA-F]+)\s*:\s*(0x[0-9a-fA-F]+)',ring,re.M)}
            head=r['RING_HEAD'];r['head_pipe_control']=None
            if head in words and words[head]==0x7a000004 and all(head+i*4 in words for i in range(6)):
                raw=[words[head+i*4] for i in range(6)]
                r['head_pipe_control']={'offset':head,'raw_dwords':raw,'fields':fields('PIPE_CONTROL',raw),
                                        'target_gen12_fields':fields('PIPE_CONTROL',raw,12)}
            r['pipe_controls']=[]
            for o,w in words.items():
                if w==0x7a000004 and all(o+i*4 in words for i in range(6)):
                    raw=[words[o+i*4] for i in range(6)]
                    r['pipe_controls'].append({'offset':o,'raw_dwords':raw,
                                              'source_gen11_fields':fields('PIPE_CONTROL',raw),
                                              'target_gen12_fields':fields('PIPE_CONTROL',raw,12)})
            r['ring_batch_starts']=[]
            for o,w in words.items():
                if w & 0xff800000 == 0x18800000 and o+4 in words and o+8 in words:
                    raw=[w,words[o+4],words[o+8]]
                    r['ring_batch_starts'].append({'offset':o,'raw':raw,'fields':fields('MI_BATCH_BUFFER_START',raw)})
            r['actual_gen12_fault_register_captured']=bool(re.search(r'\[0x0*cec4\]',text,re.I))
            records.append(r)
    (ROOT/'analysis/rcs-evidence.json').write_text(json.dumps(records,indent=2)+'\n')
    for r in records:
        print(r['stage'],Path(r['path']).name,'ctx',r['context_id'],'head',hex(r['RING_HEAD'] or 0),
              'PC',r['head_pipe_control']['raw_dwords'] if r['head_pipe_control'] else None)
if __name__=='__main__':main()
