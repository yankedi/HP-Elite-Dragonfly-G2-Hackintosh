#!/usr/bin/env python3
"""Final evidence audit. It does not execute GPU APIs or regenerate artifacts."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
STATES={
 'NULLMOTH_SOURCE':{'VERIFIED','PARTIAL','BLOCKED'},
 'METAL_PLUGIN_REUSE':{'VERIFIED_SUBSET','PARTIAL','BLOCKED'},
 'AIR_SPIRV_PATH':{'VERIFIED_SUBSET','PARTIAL','BLOCKED'},
 'BACKEND_ABSTRACTION':{'IMPLEMENTED','PARTIAL','BLOCKED'},
 'VULKAN_CPU_PROTOTYPE':{'PASS','PARTIAL','BLOCKED'},
 'MESA_ANV_SOURCE':{'VERIFIED','PARTIAL','BLOCKED'},
 'INTEL_COMPILER':{'BUILT','PARTIAL','BLOCKED'},
 'GEN12_NATIVE_SHADER':{'GENERATED','NOT_GENERATED','BLOCKED'},
 'ANV_MACOS_BUILD':{'PASS','PARTIAL','BLOCKED'},
 'NMDRM_I915_UAPI':{'PARTIAL','MOCK_ONLY','BLOCKED'},
 'INTEL_GPU_SUBMISSION':{'NOT_TESTED'},
 'INTEL_DISPLAY_ACCELERATION':{'NOT_TESTED'},
 'MACOS_METAL_ACCELERATION':{'NOT_TESTED'},
 'INDEPENDENT_AUDIT':{'PASS','CONDITIONAL','BLOCKED'},
 'READY_FOR_HARDWARE_APPROVAL':{'NO'},
}
REQUIRED=['README.md','FINAL-REPORT.md','state.json','history.json','continuation.md',
 'sources/provenance.json','metal/API-DEPENDENCY.md','metal/VULKAN-BACKEND-AUDIT.md',
 'metal/backend-adapter/README.md','metal/translator-prototype/REPORT.md',
 'intel/ANV-BUILD-REPORT.md','intel/GEN12-COMPILER-REPORT.md',
 'drm/NMDRM-AUDIT.md','drm/I915-UAPI-MATRIX.md','drm/mock/README.md',
 'display/NMINTELFB-AUDIT.md','reports/REUSE-MATRIX.md',
 'reports/DEVICE-INIT-BLOCKERS.md','reports/INTEL-NATIVE-PORT-PLAN.md',
 'reports/OLD-VS-NEW-ROUTE.md','reports/GA41-NEXT-STEPS.md',
 'reports/FINAL-STATUS.json','reports/AUDIT-CLOSURE.json','reference/external-inputs.json',
 'reports/REQUIREMENT-CHECKLIST.md','reports/PRIVATE-MIGRATION.md']


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    for name in REQUIRED:
        p=ROOT/name; assert p.is_file() and p.stat().st_size>0,name
    status=json.loads((ROOT/'reports/FINAL-STATUS.json').read_text())
    assert set(status)==set(STATES)|{'GA41_DIRECTION'}
    for key,allowed in STATES.items(): assert status[key]['value'] in allowed,key
    assert status['GA41_DIRECTION']['value'].strip()
    for key,row in status.items():
        assert row['evidence'],key
        for name in row['evidence']:
            p=(ROOT/name).resolve(); assert p.is_relative_to(ROOT) and p.exists(),(key,name)
    state=json.loads((ROOT/'state.json').read_text())
    assert state['final_status_path']=='reports/FINAL-STATUS.json'
    assert state['final_status_sha256']==sha(ROOT/state['final_status_path'])
    for key in ['INTEL_GPU_SUBMISSION','INTEL_DISPLAY_ACCELERATION','MACOS_METAL_ACCELERATION','READY_FOR_HARDWARE_APPROVAL']:
        assert state[key]==status[key]['value'],key
    history=json.loads((ROOT/'history.json').read_text())
    assert history[-1]['id']==state['last_history_event']
    assert len({e['id'] for e in history})==len(history)
    for event in history:
        for name in event.get('evidence',[]): assert (ROOT/name).exists(),(event['id'],name)
    provenance=json.loads((ROOT/'sources/provenance.json').read_text())
    for name,source in provenance['sources'].items():
        path=ROOT/'sources'/name
        actual=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        assert actual==source['commit']
        assert not subprocess.check_output(['git','-C',str(path),'status','--porcelain']).strip()
        manifest=ROOT/source['tracked_manifest']; assert sha(manifest)==source['tracked_manifest_sha256']
        for row in json.loads(manifest.read_text()):
            p=path/row['path']
            if row['kind']=='file': assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
    closure=json.loads((ROOT/'reports/AUDIT-CLOSURE.json').read_text())
    assert closure['status']=='CLOSED'
    assert closure['mustfix_open']==0
    assert {r['track'] for r in closure['reviews']}=={'G1','G2','G3'}
    for review in closure['reviews']:
        assert review['status']=='CLOSED'
        assert (ROOT/review['report']).is_file()
        assert (ROOT/review['result']).is_file()
        assert review['mustfix_open']==0
        for name,value in review['bindings'].items(): assert sha(ROOT/name)==value,(review['track'],name)
    assert status['INDEPENDENT_AUDIT']['value']=='PASS'
    for name in state['required_success_receipts']:
        row=json.loads((ROOT/name).read_text()); assert row['exit']==0,name
        for stream in ['stdout','stderr']:
            p=(ROOT/name).parent/(stream+'.txt')
            assert sha(p)==row[stream+'_sha256'],(name,stream)
    for name in state['current_build_receipts']:
        row=json.loads((ROOT/name).read_text()); assert row['exit']==0,name
        inputs=row.get('source_sha256',row.get('inputs'))
        assert inputs,(name,'missing source bindings')
        for source,value in inputs.items(): assert sha(ROOT/source)==value,(name,source)
        if 'probe_exit' in row: assert row['probe_exit']==0,name
        if 'binary_sha256' in row:
            command=row['command']; binary=Path(command[command.index('-o')+1])
            if not binary.is_absolute(): binary=ROOT/binary
            assert sha(binary)==row['binary_sha256'],name
    native=json.loads((ROOT/'build/native-packet-probe/receipt.json').read_text())
    assert native['generator_exit']==native['compiler_exit']==native['run_exit']==0
    for name,value in native['source_sha256'].items(): assert sha(ROOT/name)==value,name
    # Deliberately preserved original failures and real pre-edit evidence.
    failed=json.loads((ROOT/'logs/uapi-model-tests-015/receipt.json').read_text())
    assert failed['exit']!=0
    for folder in ['api-license-001','api-license-002','drm-safety-001']:
        before=ROOT/'reference/repairs'/folder
        for name,value in json.loads((before/'before.json').read_text()).items():
            assert sha(before/name)==value,(folder,name)
    assert sha(ROOT/'drm/mock/i915_model.py')!=sha(ROOT/'reference/repairs/drm-safety-001/drm/mock/i915_model.py')
    for line in (ROOT/'metal/translator-prototype/results/SHA256SUMS').read_text().splitlines():
        value,name=line.split(None,1); assert sha(ROOT/name)==value,name
    compiler=json.loads((ROOT/'reference/intel-build/manifest.json').read_text())
    for row in compiler['artifacts']:
        p=ROOT/row['path']; assert sha(p)==row['sha256'] and p.stat().st_size==row['size'],row['path']
    for folder in ['tools','drm/mock','drm/tests','prototype/tests']:
        for p in (ROOT/folder).glob('*.py'): ast.parse(p.read_text(),filename=str(p))
    print(json.dumps({'status':'PASS','required_files':len(REQUIRED),'states':len(status),
                      'history_events':len(history),'independent_tracks':3,'mustfix_open':0,
                      'source_trees':'pristine tracked SHA verified','hardware_approval':'NO'}))


if __name__=='__main__': main()
