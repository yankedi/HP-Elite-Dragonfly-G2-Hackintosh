#!/usr/bin/env python3
"""Local packet reconstruction and explicitly partial whole-capture format studies.

These study files preserve opaque packets, so they never earn strict_shadow's
VALIDATED_SUBSET status. There is no submission/MMIO/driver integration.
"""
import hashlib
import json
from pathlib import Path
import command_stream as C

ROOT=Path(__file__).resolve().parents[1]

def null_stencil(source,*,resource_absent,disabled_state,depth_encoded,mocs,
                 mocs_evidence,stepping_resolved):
    if C.words(source)!=[0x78060003,0,0,0,0]:raise C.Rejected('PRESENT_OR_UNKNOWN_STENCIL_NEEDS_RESOURCE_TRANSLATION')
    if resource_absent is not True:raise C.Rejected('UNKNOWN_RESOURCE')
    required=('stencil_test','stencil_write','depth_test','depth_write','hiz','hz_operation')
    if any(disabled_state.get(k) is not True for k in required):raise C.Rejected('ACTIVE_OR_UNRESOLVED_DEPTH_STENCIL_STATE')
    if type(depth_encoded) is not int or not 0<=depth_encoded<2048:raise C.Rejected('UNRESOLVED_DEPTH_STATE')
    if type(mocs) is not int or not 1<=mocs<128 or not isinstance(mocs_evidence,str) or not mocs_evidence:
        raise C.Rejected('UNVERIFIED_TARGET_MOCS')
    if stepping_resolved is not True:raise C.Rejected('UNRESOLVED_STEPPING_WORKAROUND')
    # Caller-supplied evidence is an offline contract, not runtime validation.
    return C.binary([0x78060006,7<<29,0,0,0,(depth_encoded<<20)|mocs,0,0])

def draw_candidate(source,mode):
    dw=C.words(source)
    if len(dw)!=10 or dw[0]!=0x7b000008:raise C.Rejected('UNSUPPORTED_SOURCE_DRAW')
    if dw[0]&(1<<10):raise C.Rejected('INDIRECT_XP_REGISTERS_UNKNOWN')
    if dw[-3:]!=[0,0,0]:raise C.Rejected('NONZERO_INLINE_XP')
    if mode not in ('A','B'):raise C.Rejected('UNKNOWN_DRAW_CANDIDATE')
    dw[0]=0x7b000808 if mode=='A' else 0x7b000005
    return C.binary(dw)

def check_draw(blob,mode,target):
    if mode not in ('A','B'):raise C.Rejected('UNKNOWN_DRAW_CANDIDATE')
    if len(blob)!=40:raise C.Rejected('INVALID_DRAW_ENVELOPE')
    p=target.decode(blob)
    if p['name'] not in {'3DPRIMITIVE','3DPRIMITIVE_EXTENDED'} or bool(p['raw'][0]&(1<<11))!=(mode=='A'):
        raise C.Rejected('INVALID_DRAW_OPCODE_OR_MODE')
    expected=40 if mode=='A' else 28
    if p['length']!=expected:raise C.Rejected('TARGET_LENGTH_MISMATCH')
    if C.validate_target(p,target)['classification']=='EXPLICITLY_NONCONFORMING':raise C.Rejected('DRAW_TARGET_FORMAT_INVALID')
    if mode=='B':
        for off in (28,32,36):
            q=target.decode(blob,off)
            if q['name']!='MI_NOOP' or q['raw']!=[0]:raise C.Rejected('NON_NOOP_PADDING')
    return p

def study_candidate(mode,source_packets,base=0x50000000):
    """Frozen-capture format study, intentionally NOT a strict semantic converter."""
    if mode not in ('A','B'):raise C.Rejected('UNKNOWN_DRAW_CANDIDATE')
    if type(base) is not int or not 0<=base<C.VA_END:raise C.Rejected('INVALID_STUDY_BASE')
    if base%4096:raise C.Rejected('TARGET_ALIGNMENT')
    frozen=(ROOT/'inputs/batch.bin').read_bytes()[0x6000:0x7104]
    C.checked_add(base,len(frozen)+12,C.VA_END)
    if not isinstance(source_packets,(list,tuple)) or len(source_packets)!=166:raise C.Rejected('STUDY_INPUT_PROVENANCE_MISMATCH')
    # Never accept caller labels/fields as packet or capture-provenance evidence.
    canonical=C.Parser(C.Model('gen11'),{0x426fd000:frozen}).parse(0x426fd000)
    for supplied,verified in zip(source_packets,canonical):
        if (not isinstance(supplied,dict) or supplied.get('name')!=verified['name']
            or type(supplied.get('source_va')) is not int or supplied['source_va']!=verified['source_va']
            or not isinstance(supplied.get('raw'),list)
            or any(type(x) is not int for x in supplied['raw']) or supplied['raw']!=verified['raw']):
            raise C.Rejected('STUDY_INPUT_PROVENANCE_MISMATCH')
    source_packets=canonical
    target=C.Model('gen12');output=bytearray();layout=[];references=[];draws=[]
    for p in source_packets:
        raw=C.binary(p['raw']);scope='OPAQUE_PRESERVED_UNPROVEN'
        if p['name']=='3DSTATE_STENCIL_BUFFER':
            raw=null_stencil(raw,resource_absent=True,disabled_state=dict.fromkeys(
                ('stencil_test','stencil_write','depth_test','depth_write','hiz','hz_operation'),True),
                depth_encoded=0,mocs=4,mocs_evidence='CONDITIONAL Mesa TGL local example; NOT Apple runtime verified',stepping_resolved=True)
            scope='CONDITIONAL_NULL_EXAMPLE_NOT_RUNTIME_PROVEN'
        if p['name']=='3DPRIMITIVE':
            raw=draw_candidate(raw,mode);check_draw(raw,mode,target);scope='DRAW_DEFINED_FIELDS_CHECKED'
            draws.append({'source_va':p['source_va'],'target_va':base+len(output),'bytes_le':raw.hex()})
        layout.append({'source_va':p['source_va'],'source_length':p['length'],
                       'target_va':base+len(output),'target_length':len(raw),'scope':scope})
        for f in C.all_fields(p):
            if f['type'] in ('address','offset'):
                references.append({'source_va':p['source_va'],'field':f['name'],'kind':f['type'],
                                   'value':f['value'],'action':'PRESERVED_NOT_RELOCATED','status':'RESOURCE_OR_BASE_SEMANTICS_UNPROVEN'})
        output.extend(raw)
        if len(output)>C.MAX_BYTES:raise C.Rejected('OUTPUT_LIMIT')
    blob=bytes(output);decoded=[];off=0
    while off<len(blob):
        p=target.decode(blob,off);p['target_va']=base+off
        decoded.append({'name':p['name'],'target_offset':off,'length':p['length'],
                        'validation':C.validate_target(p,target)})
        off+=p['length']
    if off!=len(blob):raise C.Rejected('OUTPUT_BOUNDARY_MISMATCH')
    boundaries={base+p['target_offset'] for p in decoded}
    if any(row['target_va'] not in boundaries for row in layout):raise C.Rejected('LOST_PACKET_BOUNDARY')
    # No captured BBS in this input; no unverified control-flow target is rewritten.
    if any(p['name']=='MI_BATCH_BUFFER_START' for p in source_packets):raise C.Rejected('STUDY_BBS_REQUIRES_STRICT_RELOCATION')
    if len(draws)!=4:raise C.Rejected('UNEXPECTED_CAPTURE_DRAW_COUNT')
    return blob,{'schema':1,'candidate':mode,'status':'PARTIAL_FORMAT_STUDY',
        'strict_shadow':False,'gpu_executable_proven':False,'deployment_eligible':False,
        'source_semantic_equivalence':'NOT_CLAIMED_MALFORMED_SOURCE',
        'input_provenance':'exact frozen bytes/order/names/VAs checked; fields independently redecoded',
        'null_context':'captured ordered state; stencil-proof.json',
        'unverified_assumptions':['Explicit absence inventory not captured','Mesa MOCS4 is only local example, Apple MOCS unknown',
            'Stepping workaround omitted for this conditional format study','Opaque commands/resources preserved without proof',
            'No resource addresses remapped to these offline study VAs; heaps and inherited states missing',
            'No GPU prefetch padding/mappings; output is not a submission buffer'],
        'source_sha256':hashlib.sha256(b''.join(C.binary(p['raw']) for p in source_packets)).hexdigest(),
        'output_sha256':hashlib.sha256(blob).hexdigest(),'bytes':len(blob),'draws':draws,
        'source_packets':len(source_packets),'target_packets_contiguously_decoded':len(decoded),
        'source_target_map':layout,'typed_resource_inventory':references,'target_validation':decoded}

def main():
    out=ROOT/'track-a/shadow-batches';out.mkdir(exist_ok=True)
    source=(ROOT/'inputs/batch.bin').read_bytes()[0x6000:0x7104]
    packets=C.Parser(C.Model('gen11'),{0x426fd000:source}).parse(0x426fd000)
    for mode in ('A','B'):
        blob,receipt=study_candidate(mode,packets)
        (out/f'format-candidate-{mode}.bin').write_bytes(blob)
        (out/f'format-candidate-{mode}.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(mode,receipt['bytes'],receipt['target_packets_contiguously_decoded'],receipt['output_sha256'])
    example=C.strict_shadow({0x1000:C.binary([0,0x05000000])},0x1000,{0x1000:0x100000},
                            {'MI_NOOP':lambda p:C.binary([0]*1025)})
    blob=example.pop('segments')[0x100000];(out/'strict-noop-growth.bin').write_bytes(blob)
    example['output_sha256']=hashlib.sha256(blob).hexdigest()
    (out/'strict-noop-growth.json').write_text(json.dumps(example,indent=2)+'\n')

if __name__=='__main__':main()
