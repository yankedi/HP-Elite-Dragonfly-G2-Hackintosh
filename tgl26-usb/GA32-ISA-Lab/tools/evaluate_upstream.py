#!/usr/bin/env python3
"""Cross-check experimental Mesa translator output with independent Intel IGA."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'translator'))
from offline_translate import decode, normalized, IGA

def main():
    reports=[]
    for name in ['ps','vs','ps-kp1','ps-kp2']:
        src=(ROOT/f'analysis/{name}-bounded.bin').read_bytes()
        target=ROOT/f'analysis/upstream-{name}-gen12.bin'
        args=[str(ROOT/'tools/mesa-eu/adapter/build/g11to12'),'xlate',str(ROOT/f'analysis/{name}-bounded.bin'),str(target)]
        c=subprocess.run(args,capture_output=True,timeout=30)
        (ROOT/f'logs/upstream-{name}-xlate.stdout').write_bytes(c.stdout)
        (ROOT/f'logs/upstream-{name}-xlate.stderr').write_bytes(c.stderr)
        work=ROOT/f'analysis/upstream-{name}-review';work.mkdir(exist_ok=True)
        s=decode(src,'11',work);t=decode(target.read_bytes(),'12p1',work)
        if c.returncode or s['exit'] or t['exit']:
            raise ValueError(name+': translation/source/target decoder failed; mapping not accepted')
        if len(s['instructions'])!=len(t['instructions']):
            raise ValueError(name+': reference mapping requires 1:1 instruction count; do not silently zip')
        asm=work/'target.asm';asm.write_text(t['asm']);rt=work/'roundtrip.bin'
        r=subprocess.run([str(IGA),'-a','-p=12p1',str(asm),'-o',str(rt)],capture_output=True)
        (ROOT/f'logs/upstream-{name}-roundtrip.stderr').write_bytes(r.stderr)
        mapping=[]
        for i,j in zip(s['instructions'],t['instructions']):
            keys=sorted(k for k in set(normalized(i))|set(normalized(j)) if normalized(i).get(k)!=normalized(j).get(k))
            mapping.append({'source_offset':i['pc'],'target_offset':j['pc'],'source':i,'target':j,
                            'differing_architectural_fields':keys,
                            'semantic_status':'UNPROVEN' if keys else 'OPERAND_FIELDS_MATCH_ONLY'})
        reports.append({'name':name,'upstream_exit':c.returncode,'source_bytes':len(src),
                        'target_bytes':target.stat().st_size,'source_instructions':len(s['instructions']),
                        'target_instructions':len(t['instructions']),'iga_target_decode_exit':t['exit'],
                        'target_roundtrip_exit':r.returncode,
                        'binary_roundtrip_identical':r.returncode==0 and rt.read_bytes()==target.read_bytes(),
                        'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'mapping':mapping,
                        'full_shader_semantics_validated':False,
                        'reasons':['Debug ARF Switch becomes MOV null; original effect not preserved',
                                   'NF accumulator becomes GRF temporary (PS); precision/rounding equivalence unproven',
                                   'SEND descriptors/payload and per-instruction @1/SBID scheduling require semantic proof']})
    (ROOT/'analysis/upstream-semantic-review.json').write_text(json.dumps(reports,indent=2)+'\n')
    for r in reports: print(r['name'],r['source_instructions'],r['target_instructions'],r['target_bytes'],r['iga_target_decode_exit'],r['binary_roundtrip_identical'])
if __name__=='__main__':main()
