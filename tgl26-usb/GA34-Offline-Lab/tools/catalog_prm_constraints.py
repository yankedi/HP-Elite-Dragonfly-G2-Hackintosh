#!/usr/bin/env python3
"""Archive actual packet PRM sections and literal restriction evidence.

This is a source locator, not an NLP-to-hardware-proof compiler. All extracted
prose keeps UNKNOWN validation status unless a separately implemented rule says
otherwise. LF line counting preserves the PRM extraction's form-feed characters.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
RULES=[
    {'id':'draw-length','commands':['3DPRIMITIVE','3DPRIMITIVE_EXTENDED'],'generations':['gen11','gen12'],
     'condition':'header.bit11 ? total_dwords==10 : total_dwords==7','implemented':'validate_target',
     'scope':'format only; contradictory source has no proven execution semantics'},
    {'id':'pipeline-selector-mask','commands':['PIPELINE_SELECT'],'generations':['gen11','gen12'],
     'condition':'header.bits9_8 in [0,3]','implemented':'validate_target and Parser.update per-field knownness'},
    {'id':'tgl-pipeline-reserved','commands':['PIPELINE_SELECT'],'generations':['gen12'],
     'condition':'header.bit5==0 and header.bit7==0','implemented':'validate_target',
     'xml_conflict':'pinned gen12.xml incorrectly retains Force Media Awake at bit5'},
    {'id':'stencil-surface-type','commands':['3DSTATE_STENCIL_BUFFER'],'generations':['gen12'],
     'condition':'DW1.bits31_29 in [1,3,7]','implemented':'validate_target'},
    {'id':'stencil-null','commands':['3DSTATE_STENCIL_BUFFER'],'generations':['gen12'],
     'condition':'no resource => SurfaceType7; no active stencil/HZ; resolved depth, MOCS and stepping/workaround',
     'implemented':'normalizer.null_stencil explicit evidence-contract gates',
     'runtime':'UNKNOWN; examples do not prove Apple MOCS or actual absence inventory'},
    {'id':'bbs-legacy-chain','commands':['MI_BATCH_BUFFER_START','MI_BATCH_BUFFER_END'],'generations':['gen11','gen12'],
     'condition':'legacy second-level BBS chains; it does not push another return',
     'implemented':'Parser explicit source legacy and target MI_MODE contract'},
    {'id':'bbs-nested-mode','commands':['MI_BATCH_BUFFER_START'],'generations':['gen12'],
     'condition':'MI_MODE.NestedBatchBufferEnable known; max3 levels; third-level restrictions',
     'implemented':'Parser explicit mode + max3, only NOOP/END/BBS admitted at third-level',
     'runtime':'UNKNOWN mode is refused, not inferred from bit22'},
    {'id':'bbs-address-reserved','commands':['MI_BATCH_BUFFER_START'],'generations':['gen11','gen12'],
     'condition':'address.bits1_0==0; bounded captured target; no predicate/offset/resource-streamer',
     'implemented':'Parser read-only bounded control-flow subset'},
    {'id':'end-encoding','commands':['MI_BATCH_BUFFER_END'],'generations':['gen11','gen12'],
     'condition':'strict admitted raw==0x05000000; EndContext1 requires separate proof',
     'implemented':'Parser rejects noncanonical end; validate_target reserved-mask check'},
    {'id':'bbs-prefetch','commands':['MI_BATCH_BUFFER_START'],'generations':['gen12'],
     'condition':'additional command-buffer overfetch mappings required (0.5KB); source/target pages valid',
     'implemented':None,'validation':'UNKNOWN_NO_GPU_MAPPINGS'},
    {'id':'conditional-end','commands':['MI_CONDITIONAL_BATCH_BUFFER_END'],'generations':['gen11','gen12'],
     'condition':'memory comparison and current/all-level termination must be resolved',
     'implemented':'Parser rejects unsupported conditional control flow'},
    {'id':'xml-nonzero','commands':['3DSTATE_STENCIL_BUFFER'],'generations':['gen12'],
     'condition':'explicit nonzero MOCS XML field constraint; runtime MOCS semantics separate',
     'implemented':'validate_target'}
]

def sections(path):
    text=path.read_text();heads=list(re.finditer(r'^\s*((?:(?:SW|HW) Generated )?[A-Z0-9_]+)\s*\n(?:Source:|Exists If:|Size \(in bits\):)',text,re.M));out={}
    for i,m in enumerate(heads):
        end=heads[i+1].start() if i+1<len(heads) else len(text)
        body=text[m.start():end];line=text.count('\n',0,m.start())+1
        restrictions=[];lines=body.split('\n')
        for j,s in enumerate(lines):
            if re.search(r'\b(must|shall|required|only|illegal|reserved|exists if|programming notes)\b',s,re.I):
                restrictions.append({'line':line+j,'literal_context':'\n'.join(lines[max(0,j-1):min(len(lines),j+4)]),
                                     'validation':'UNKNOWN_UNLESS_SEPARATELY_IMPLEMENTED_RULE'})
        out[m[1]]={'path':str(path.relative_to(ROOT)),'start_line':line,'end_line':line+len(lines)-1,
                   'section_sha256':hashlib.sha256(body.encode()).hexdigest(),
                   'restriction_fragments':restrictions,'complete_section_preserved_in_source':True}
    return out

def main():
    data=json.loads((ROOT/'inputs/batch-decoded.json').read_text())
    names=sorted({p['name'] for p in data['per_gen']['gen11']['chains'][0]['instructions']}|
                 {'RENDER_SURFACE_STATE','SAMPLER_STATE','BINDING_TABLE_STATE','3DPRIMITIVE_EXTENDED','MI_BATCH_BUFFER_START','MI_CONDITIONAL_BATCH_BUFFER_END'})
    catalogs={}
    for gen,prefix in [('gen11','icl'),('gen12','tgl')]:
        catalogs[gen]={}
        for vol in ('2a-command-instructions','2d-command-structures','9-render-engine'):
            path=ROOT/f'reference/track-a/{prefix}-vol{vol}.txt'
            catalogs[gen].update(sections(path))
    rows=[]
    for name in names:
        lookup='3DPRIMITIVE' if name=='3DPRIMITIVE_EXTENDED' else name
        row={'command':name,'generations':{}}
        for gen in catalogs:
            keys=(lookup,lookup+'_BODY','SW Generated '+lookup,'HW Generated '+lookup)
            refs=[catalogs[gen][key] for key in keys if key in catalogs[gen]]
            row['generations'][gen]={'sections':refs,'source_location_status':'LOCATED' if refs else 'NOT_LOCATED_BY_EXACT_HEADING',
                                    'semantic_completeness':'PARTIAL; all unimplemented prose/resource/inherited constraints UNKNOWN'}
        rows.append(row)
    doc={'schema':1,'scope':'official PRM section and restriction inventory, executable rules are a strict subset',
         'automatic_extraction_is_not_semantic_validation':True,'rules':RULES,'commands':rows}
    (ROOT/'track-a/prm-constraints.json').write_text(json.dumps(doc,indent=2)+'\n')
    for gen in catalogs:
        found=sum(bool(r['generations'][gen]['sections']) for r in rows)
        fragments=sum(len(s['restriction_fragments']) for r in rows for s in r['generations'][gen]['sections'])
        print(gen,'sections located for',found,'/',len(rows),'commands; literal restriction fragments',fragments)

if __name__=='__main__':main()
