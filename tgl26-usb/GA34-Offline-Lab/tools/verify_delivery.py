#!/usr/bin/env python3
"""Evidence-driven delivery audit. Does not create a manifest or approve hardware."""
import ast
import hashlib
import json
from pathlib import Path
import re
import archive

ROOT=Path(__file__).resolve().parents[1]
STATES={'COMMAND_SPEC_DIFF':'PARTIAL','STENCIL_TRANSLATION':'PARTIAL','DRAW_NORMALIZATION':'VALIDATED',
        'SHADOW_BATCH':'VALIDATED_SUBSET','FAULT_REGISTER_AUDIT':'PARTIAL','FORCEWAKE_AUDIT':'PARTIAL',
        'FAULT_CAPTURE_DESIGN':'PARTIAL','FAULT_DIAGNOSTIC_BUILD':'OFFLINE_PASS','SAFETY_REVIEW':'CONDITIONAL',
        'READY_FOR_HARDWARE_APPROVAL':'NO'}
REQUIRED=['README.md','FINAL-REPORT.md','state.json','continuation.md','experiment-history.json',
    'track-a/command_stream.py','track-a/normalizer.py','track-a/spec-diff.json','track-a/prm-constraints.json',
    'track-a/packet-audit.json','track-a/state-ir.json','track-a/stencil-proof.json','track-a/draw-proof.json',
    'track-a/reports/independent-parser-audit.md','track-a/reports/repaired-command-review.md',
    'track-a/reports/r01-r04-closure.md','track-b/fault-registers.md','track-b/forcewake-audit.md',
    'track-b/reset-timeline.md','track-b/fault-record-format.md','track-b/diagnostic-design.md',
    'track-b/diagnostic-src/kern_tglfault34.hpp','track-b/diagnostic-src/kern_tglfault34_boottext.hpp',
    'track-b/ga33-add-unattached-tglfault34.patch','track-b/reports/independent-fault-review.md',
    'track-b/reports/fault-alias-closure.md',
    'track-c/correlation-model.md','track-c/next-experiment-ranking.md','track-c/reports/correlation-fix-receipt.md',
    'logs/determinism.json','logs/historical-preservation.json','logs/repository-check.txt','logs/lab-check.txt',
    'reports/safety-integration.md','reports/test-coverage.md','reports/completion-audit.md']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    archive.originals();files=[]
    for rel in REQUIRED:
        p=ROOT/rel
        assert p.is_file() and p.stat().st_size,rel
        files.append({'path':rel,'sha256':sha(p)})
    text=(ROOT/'FINAL-REPORT.md').read_text()
    assert [int(n) for n in re.findall(r'^## (\d+)\.',text,re.M)]==list(range(1,16))
    for k,v in STATES.items():assert f'|{k}|{v}|' in text,k
    for mode,count,digest in [('A',166,'a6ab33b6d92a3e203a2ec041bde7370691d46bf38c9c3aaeddc9e80a594e5f62'),
                              ('B',178,'529565eaa7406d5283beef35753a4a6e62666135415a196ef0550ac0dad9e504')]:
        base=ROOT/f'track-a/shadow-batches/format-candidate-{mode}'
        doc=json.loads(base.with_suffix('.json').read_text())
        assert base.with_suffix('.bin').stat().st_size==4368 and sha(base.with_suffix('.bin'))==doc['output_sha256']==digest
        assert doc['source_packets']==166 and doc['target_packets_contiguously_decoded']==count
        assert doc['strict_shadow'] is False and doc['deployment_eligible'] is False and doc['gpu_executable_proven'] is False
        assert not any(p['validation']['classification']=='EXPLICITLY_NONCONFORMING' for p in doc['target_validation'])
        assert len(doc['draws'])==4 and len(doc['source_target_map'])==166
    source=json.loads((ROOT/'track-a/packet-audit.json').read_text())
    assert source['classifications']=={'UNKNOWN':105,'EXPLICITLY_NONCONFORMING':5,'VALID_TGL_PACKET_SUBSET':56}
    assert source['format_checked_count']==161 and source['complete_gpu_semantics_validated'] is False
    methods={}
    for folder in ('track-a','track-c'):
        tests=[]
        for p in (ROOT/folder/'tests').glob('test_*.py'):
            tree=ast.parse(p.read_text())
            tests.extend(f'{p.name}:{x.name}' for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name.startswith('test_'))
        methods[folder]=tests
    assert len(methods['track-a'])==64 and len(methods['track-c'])==40
    check=(ROOT/'logs/lab-check.txt').read_text()
    assert 'Ran 64 tests' in check and 'Ran 40 tests' in check and 'FAILED' not in check
    for compiler in ('clang','gcc'):
        native=json.loads((ROOT/f'logs/diagnostic-core/{compiler}-results.json').read_text())
        assert len(native['builds'])==4 and all(b['status']=='OFFLINE_PASS' and b['groups']==28 for b in native['builds'])
        assert native['hardware']=='NONE' and native['attachment']=='NONE' and native['whole_kext']=='NOT_BUILT'
    closure=json.loads((ROOT/'logs/independent-fault-closure/closure-receipt.json').read_text())
    assert closure['status']=='INDEPENDENT_R1_R2_CLOSED'
    assert closure['final_header_sha256']==sha(ROOT/'track-b/diagnostic-src/kern_tglfault34.hpp')
    for row in closure['files']:assert sha(ROOT/row['path'])==row['sha256'],row['path']
    for name in ('validPPGTT','validGGTT','valid0','DATA1MBZ','failedread'):
        for ext in ('.bin','.json'):
            a=ROOT/'track-b/samples/initial'/(name+ext);b=ROOT/'track-b/samples/post-alias-fix'/(name+ext)
            assert a.read_bytes()==b.read_bytes()
            if ext=='.bin':assert a.stat().st_size==108
    out={'schema':1,'required_artifacts':files,'question_count':15,'states':STATES,
         'test_methods':methods,'whole_kext':'NOT_BUILT','real_attachment':'NONE','source_img':None,'result_img':None,
         'scope':'artifact/hash/test-receipt checks only; hardware approval remains NO'}
    (ROOT/'logs/delivery-audit.json').write_text(json.dumps(out,indent=2)+'\n')
    print('PASS',len(files),'required artifacts;15 answers/10 states;104 Python methods;candidate hashes/bounds/statuses;native receipt scopes')
if __name__=='__main__':main()
