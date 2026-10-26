#!/usr/bin/env python3
"""Ordered state snapshots, not GPU-state or retirement claims."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def main():
    data=json.loads((ROOT/'analysis/batch-decoded.json').read_text())
    chain=next(x for x in data['per_gen']['gen11']['chains'] if x['start']==0x6000)
    state={};draws=[]
    for ins in chain['instructions']:
        name=ins.get('name','')
        if name.startswith('3DSTATE_') or name in {'STATE_BASE_ADDRESS','PIPELINE_SELECT'}:
            state[name]={'offset':ins['offset'],'fields':ins.get('fields',[]),'groups':ins.get('groups',[]),
                         'raw_dwords':ins.get('raw_dwords',[]),'validation_level':ins.get('validation_level')}
        elif name in {'3DPRIMITIVE','3DPRIMITIVE_EXTENDED'}:
            draws.append({'offset':ins['offset'],'raw_dwords':ins['raw_dwords'],
                          'fields':ins['fields'],'length_semantics_validated':ins.get('length_semantics_validated'),
                          'state_at_packet_boundary':dict(state),
                          'claim':'Gen11 declared-length ordering only; not a validated TGL execution path'})
    assert len(draws)==4
    required=['PIPELINE_SELECT','STATE_BASE_ADDRESS','3DSTATE_VS','3DSTATE_PS','3DSTATE_PS_EXTRA',
              '3DSTATE_WM','3DSTATE_SF','3DSTATE_CLIP','3DSTATE_VERTEX_BUFFERS','3DSTATE_VERTEX_ELEMENTS',
              '3DSTATE_URB_VS','3DSTATE_URB_HS','3DSTATE_URB_DS','3DSTATE_URB_GS',
              '3DSTATE_PUSH_CONSTANT_ALLOC_VS','3DSTATE_PUSH_CONSTANT_ALLOC_PS',
              '3DSTATE_CONSTANT_VS','3DSTATE_CONSTANT_PS','3DSTATE_BINDING_TABLE_POINTERS_VS',
              '3DSTATE_BINDING_TABLE_POINTERS_PS','3DSTATE_SAMPLER_STATE_POINTERS_VS','3DSTATE_SAMPLER_STATE_POINTERS_PS']
    final=draws[-1]['state_at_packet_boundary']
    summary={n:{'present':n in final,'packet_offset':final[n]['offset'] if n in final else None,
                'fields':final[n]['fields'] if n in final else [],
                'groups':final[n]['groups'] if n in final else []} for n in required}
    out={'scope':'minimal ordered packet state, not actual GPU state',
         'source':'batch-decoded.json Gen11 bounded-length chain from ring-linked 0x6000',
         'draws':draws,'required_state_summary':summary,
         'unknown':['surface/binding/sampler heap contents not captured',
                    'dynamic/struct group elements unsupported; raw words retained',
                    'modify-enable=0 base fields do not overwrite prior GPU state: prior value unknown',
                    'Gen12 stencil packet length mismatch precedes draw packets',
                    'draw extended flag/length mismatch means packet legality unproven',
                    'ring and THAG are correlated, not an atomic execution trace']}
    (ROOT/'analysis/pipeline-snapshots.json').write_text(json.dumps(out,indent=2)+'\n')
    lines=['# 逐draw的最小管线状态（补充report06）','',
           '来自Gen11声明长度顺序，不是TGL已生效状态。所有字段与未知组保留于 `pipeline-snapshots.json`。',
           '','|状态包|最后出现偏移|非header简单字段|未知组|','|---|---|---|---|']
    headers={'DWord Length','3D Command Sub Opcode','3D Command Opcode','Command SubType','Command Type','MI Command Opcode'}
    for n,s in summary.items():
        fields=[]
        for f in s['fields']:
            if f['name'] in headers or not f.get('present'):continue
            value=f.get('value_hex',f.get('byte_offset_hex',f.get('value',f.get('raw'))))
            fields.append(f'{f["name"]}={value}')
        groups=', '.join(g.get('status','unknown') for g in s['groups'])
        lines.append('|'+n+'|'+(hex(s['packet_offset']) if s['present'] else 'UNKNOWN')+'|'+'; '.join(fields)+'|'+groups+'|')
    lines+=['','四条draw packet偏移：'+', '.join(hex(x['offset']) for x in draws)+'.',
            '此表不能将Modify Enable=0的0地址当作已生效零base；不能把动态组/heap缺失填零。']
    (ROOT/'analysis/pipeline-summary.md').write_text('\n'.join(lines)+'\n')
    print('4 ordered draw snapshots;',len(required),'required state-packet families; unknown heaps/groups explicit')
if __name__=='__main__':main()
