#!/usr/bin/env python3
"""Fail-closed IGA-backed *instruction subset* translation. Never emits a partial shader.

No GPU/device/file mapping. Successful isolated units are not complete programs.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
IGA = ROOT / 'tools/iga/build/IGAExe/iga64'
MAX_BYTES = 1 << 20
BRANCHES = {'jmpi','if','else','endif','while','break','cont','call','ret','halt','goto','brd','brc','join','do'}

class Rejected(Exception):
    def __init__(self, code, detail, offset=None):
        super().__init__(detail)
        self.code, self.detail, self.offset = code, detail, offset
    def as_dict(self):
        return {'status':'UNSUPPORTED','code':self.code,'detail':self.detail,'source_offset':self.offset}

def frames(data):
    if not data or len(data) > MAX_BYTES:
        raise Rejected('INVALID_LENGTH','Input empty or above 1MiB')
    o = 0; out = []
    while o < len(data):
        if len(data)-o < 8:
            raise Rejected('TRUNCATED','Less than compact instruction',o)
        n = 8 if int.from_bytes(data[o:o+4],'little') & (1<<29) else 16
        if n > len(data)-o:
            raise Rejected('TRUNCATED','Truncated native instruction',o)
        out.append((o,n));o += n
    return out

def invoke(args):
    try:
        r = subprocess.run([str(IGA), *args],capture_output=True,timeout=30)
    except subprocess.TimeoutExpired as exc:
        raise Rejected('TOOL_TIMEOUT','IGA exceeded 30 second bound') from exc
    except OSError as exc:
        raise Rejected('TOOL_UNAVAILABLE',str(exc)) from exc
    return r.returncode, r.stdout, r.stderr

def decode(data, platform, directory):
    f = directory/'input.bin';f.write_bytes(data)
    c,j,e=invoke(['-d','-p='+platform,'-Xprint-json','-Xprint-pc','--output-on-fail',str(f)])
    a,t,ae=invoke(['-d','-p='+platform,'-Xprint-pc','--output-on-fail',str(f)])
    try:
        obj=json.loads(j)
        if not isinstance(obj,dict) or not isinstance(obj.get('elems'),list):
            raise ValueError('Missing elems array')
        if any(not isinstance(i,dict) or 'kind' not in i for i in obj['elems']):
            raise ValueError('Malformed IGA element')
        ins=[i for i in obj['elems'] if i['kind']=='I']
        if any(not isinstance(i.get('pc'),int) or not isinstance(i.get('op'),str) for i in ins):
            raise ValueError('Missing instruction PC/opcode')
    except (ValueError,TypeError,UnicodeDecodeError) as exc:
        raise Rejected('DECODER_FAILURE',str(exc)+': '+e.decode(errors='replace')) from exc
    lines={int(m[1],16):m[2].split('//')[0].strip() for line in t.decode().splitlines()
           if (m:=re.match(r'/\* \[([0-9a-fA-F]+)\]\s*\*/\s*(.*)',line))}
    return {'exit':c,'instructions':ins,'asm':t.decode(),'json':obj,'lines':lines,
            'stderr':(e+ae).decode(errors='replace')}

def normalized(i):
    """Compare architectural execution/operand fields, excluding generation-specific scheduling.

    The target main instruction must have no unexpected SWSB, and any auto-deps
    drain is separately checked. Whole-shader dependency equivalence is unproven.
    """
    return {k:v for k,v in i.items() if k not in
            {'kind','id','pc','comment','regDist','sbid','opts'}} | {
            'opts':[v for v in i.get('opts',[]) if v != 'Compacted']}

def eligibility(i):
    op=i['op'];pc=i['pc']
    if op in BRANCHES:
        raise Rejected('BRANCH_RELOCATION_UNSUPPORTED','Refuse all control flow; no branch silently copied',pc)
    if op.startswith('send') or 'EOT' in i.get('opts',[]):
        raise Rejected('SEND_EOT_SEMANTICS_UNPROVEN','Message/payload/URB/RT conversion not proven',pc)
    if op not in {'mov','add','mul'}:
        raise Rejected('OPCODE_UNSUPPORTED','Supported opcodes: mov/add/mul only',pc)
    if set(i.get('opts',[]))-{'Compacted'}:
        raise Rejected('EXECUTION_OPTION_UNSUPPORTED','Legacy dependency/debug/special options not dropped',pc)
    operands=[i.get('dst',{}),*i.get('srcs',[])]
    for o in operands:
        if o.get('kind') not in {'RD','IM'}:
            raise Rejected('OPERAND_UNSUPPORTED','Direct GRF or immediate only',pc)
        if o.get('kind')=='RD' and o.get('reg',{}).get('rn') != 'r':
            raise Rejected('SPECIAL_REGISTER_UNSUPPORTED','No accumulator/debug/ARF translation',pc)
        if o.get('type') not in {'f','ud','d','uw','w'}:
            raise Rejected('TYPE_UNSUPPORTED','Type outside checked subset',pc)
        if o.get('kind')=='IM' and o.get('type')=='f':
            try: finite=math.isfinite(float(o.get('value','')))
            except ValueError: finite=False
            if not finite:
                raise Rejected('IMMEDIATE_BITS_UNPROVEN','Nonfinite/opaque float literal may lose NaN payload bits',pc)
    if op in {'add','mul'} and any(o.get('type')!='f' for o in operands):
        raise Rejected('INTEGER_ALU_UNPROVEN','ALU subset float only; integer width/overflow not inferred',pc)
    if op=='mov' and len({o['type'] for o in operands})!=1:
        raise Rejected('TYPE_CONVERSION_UNPROVEN','MOV conversion semantics outside subset',pc)

def translate_unit(data, ins, line, directory):
    eligibility(ins)
    # Compaction is decoded by IGA. Do not transplant source bits or replace opcodes.
    clean=re.sub(r'\{Compacted\}','',line).strip()
    asm=directory/'target.asm';out=directory/'target.bin'
    asm.write_text(clean+'\n')
    c,stdout,stderr=invoke(['-a','-p=12p1','-Xforce-no-compact','-Xauto-deps',str(asm),'-o',str(out)])
    if c: raise Rejected('ENCODER_REJECTED',stderr.decode(errors='replace'),ins['pc'])
    code=out.read_bytes();target=decode(code,'12p1',directory)
    if target['exit'] or not target['instructions']:
        raise Rejected('TARGET_DECODE_FAILED',target['stderr'],ins['pc'])
    t=target['instructions'][0]
    if t.get('regDist') or t.get('sbid'):
        raise Rejected('UNEXPECTED_MAIN_SWSB',json.dumps(t),ins['pc'])
    # Auto-deps appends a dependency drain at block exit. Account for it explicitly.
    drains=target['instructions'][1:]
    for drain in drains:
        if (drain.get('op'),drain.get('subop'),drain.get('es'),drain.get('wren')) != ('sync','nop',1,True) or drain.get('regDist')!='@1' or drain.get('sbid'):
            raise Rejected('UNEXPECTED_SWSB_SYNTHESIS',json.dumps(drain),ins['pc'])
        if drain.get('srcs') != [{'kind':'RD','reg':{'rn':'null'},'type':'ub'}]:
            raise Rejected('UNEXPECTED_SYNC_OPERAND',json.dumps(drain),ins['pc'])
    if normalized(ins)!=normalized(t):
        raise Rejected('SEMANTIC_ROUNDTRIP_MISMATCH',json.dumps({'source':normalized(ins),'target':normalized(t)}),ins['pc'])
    rtasm=directory/'roundtrip.asm';rtbin=directory/'roundtrip.bin'
    rtasm.write_text(target['asm'])
    c,_,err=invoke(['-a','-p=12p1','-Xforce-no-compact',str(rtasm),'-o',str(rtbin)])
    if c or rtbin.read_bytes()!=code:
        raise Rejected('BINARY_ROUNDTRIP_MISMATCH',err.decode(errors='replace'),ins['pc'])
    return code,{'status':'ROUNDTRIP_VALIDATED','source_offset':ins['pc'],'source_bytes':data.hex(),
                 'target_offset':0,'target_length':len(code),'target_bytes':code.hex(),
                 'target':t,'source':ins,'target_asm':target['asm'],'synthesized_dependency_drains':drains,
                 'swsb':{'policy':'IGA auto-deps in isolated instruction, not shader schedule',
                         'regDist':t.get('regDist'),'sbid':t.get('sbid')},
                 'limits':'Operand equivalence checked in isolation; no SEND/branch/whole-shader proof'}

def translate(data, destination):
    layout=frames(data);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='iga-',dir=destination) as tmp:
        d=Path(tmp);src=decode(data,'11',d)
        if src['exit'] or len(src['instructions'])!=len(layout):
            raise Rejected('SOURCE_INVALID',src['stderr'])
        if [i['pc'] for i in src['instructions']] != [o for o,n in layout]:
            raise Rejected('SOURCE_BOUNDARY_MISMATCH','IGA and framing disagree')
        if any(o not in src['lines'] for o,n in layout):
            raise Rejected('SOURCE_ASSEMBLY_MISSING','IGA JSON/text instruction boundaries disagree')
        results=[]
        for ins,(offset,n) in zip(src['instructions'],layout):
            try:
                code,r=translate_unit(data[offset:offset+n],ins,src['lines'][offset],d)
                # Isolated fragment only. Unsupported neighbors are never dropped to form a shader.
                name=f'unit-{offset:04x}.bin';(destination/name).write_bytes(code)
                r['artifact']=name;r['target_segment']=name;results.append(r)
            except Rejected as e: results.append(e.as_dict())
        report={'status':'UNSUPPORTED' if any(x['status']=='UNSUPPORTED' for x in results) else 'ROUNDTRIP_VALIDATED',
                'full_shader_emitted':False,'scope':'isolated instruction subset, not executable shader',
                'source_sha256':hashlib.sha256(data).hexdigest(),'source_bytes':len(data),'instructions':results,
                'validated_units':sum(x['status']=='ROUNDTRIP_VALIDATED' for x in results),
                'unsupported_units':sum(x['status']=='UNSUPPORTED' for x in results),
                'hardware_execution_validated':False}
        (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n');return report

def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    try:
        # Read bounded amount, so malicious huge files cannot exhaust memory.
        with a.input.open('rb') as f: data=f.read(MAX_BYTES+1)
        r=translate(data,a.output);print(json.dumps(r,indent=2))
        return 0 if r['status']!='UNSUPPORTED' else 1
    except Rejected as e: print(json.dumps(e.as_dict()));return 1
    except OSError as e:
        print(json.dumps(Rejected('IO_ERROR',str(e)).as_dict()));return 1
if __name__=='__main__': raise SystemExit(main())
