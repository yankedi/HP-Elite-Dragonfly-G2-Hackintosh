#!/usr/bin/env python3
"""Render a bounded graph of actual decoded callsites, keeping indirect unknowns."""
import json
import pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
NAMES=('SafeForceWake','doHangAnalysis','debugGraphicsEngine','resetGraphicsEngine',
       'getHardwareDiagnosisReport','resetHardwareAndReplay','IOAccelFIFOChannel2::restart()',
       'IOAccelEventMachine2::hardwareErrorEvent','IOAccelEventMachine2::restart_channel',
       'IOAccelEventMachineFast2::checkGPUProgress','IOAccelEventMachine2::signalHardwareError')


def main():
    inv=json.loads((ROOT/'analysis/kc/SystemKernelExtensions.kc.json').read_text())
    edges=json.loads((ROOT/'analysis/expanded/direct-and-indirect-edges.json').read_text())
    fix=json.loads((ROOT/'analysis/cache-fixups.json').read_text())
    stubs={s['stub_va']:s for s in fix['stubs']}
    selected=[]
    for e in edges:
        if not any(n in e['from_name'] for n in NAMES):continue
        e=dict(e)
        if e.get('target_va') in stubs:
            e['validated_static_stub']=stubs[e['target_va']]
        selected.append(e)
    result={'source':inv['source'],'source_sha256':inv['sha256'],
            'images':{i['name']:i['uuid'] for i in inv['images']},
            'scope':'Symbol-bounded linear decoded call/jmp edges; reachability and dynamic receiver unproved',
            'edges':selected,
            'vtable_candidates':fix['vtables'],
            'vtable_caveat':'Static class slots are candidate dispatch targets, not edges proving runtime receiver identity'}
    (ROOT/'analysis/safety-callgraph.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['digraph GA35 {','rankdir=LR;','node [shape=box];']
    for e in selected:
        source=f"{e['from_name']} @ {e['from_entry']:#x}"
        target=' / '.join(e.get('target_symbols',[]))
        if e.get('validated_static_stub'):target=' / '.join(e['validated_static_stub']['target_symbols'])
        if not target:target=f"{e['target_va']:#x}" if 'target_va' in e else 'UNRESOLVED '+e['unresolved_indirect']
        style='dashed' if 'unresolved_indirect' in e else 'solid'
        label=f"{e['instruction_va']:#x}: {e['kind']}"
        lines.append(f'{json.dumps(source)} -> {json.dumps(target)} [label={json.dumps(label)},style={style}];')
    lines.append('}')
    (ROOT/'analysis/safety-callgraph.dot').write_text('\n'.join(lines)+'\n')
    print(f'PASS actual_callsites={len(selected)}; indirect edges remain unresolved; no runtime CFG claim')


if __name__=='__main__':main()
