#!/usr/bin/env python3
"""Evidence-level delivery acceptance; no GPU interaction or claims of execution."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
FILES=['README.md','FINAL-REPORT.md','analysis/extraction.json','analysis/isa-diff.json',
       'analysis/batch-decoded.json','analysis/rcs-evidence.json','analysis/upstream-semantic-review.json',
       'analysis/native-matrix.json','analysis/mesa-gcc-comparison.json','analysis/ps-variants.json',
       'analysis/pipeline-snapshots.json',
       'tests/translator-coverage.json','logs/test-all.txt',
       'logs/repository-check.txt','reports/11-independent-audit.md']
REPORTS=['01-capture-integrity','02-disassembler-environment','03-shader-boundaries',
         '04-gen11-gen12-diff','05-batch-command-stream','06-pipeline-state',
         '07-rcs-hang-root-cause','08-upstream-translator-evaluation',
          '09-translator-design','10-test-report','12-command-format-crosscheck','FINAL-REPORT']
STATES={'SHADER_DECODE_ICL':'COMPLETE','SHADER_DECODE_TGL':'PARTIAL','BATCH_DECODE':'PARTIAL',
        'ISA_INCOMPATIBILITY':'CONFIRMED','OFFLINE_TRANSLATOR':'VALIDATED_SUBSET',
        'GPU_HANG_ROOT_CAUSE':'PARTIAL','READY_FOR_NEXT_HARDWARE_EXPERIMENT':'NO'}

def main():
    checked=[]
    for rel in FILES+['reports/'+s+'.md' for s in REPORTS]:
        p=ROOT/rel
        assert p.is_file() and p.stat().st_size>0, rel
        checked.append(rel)
    report=(ROOT/'reports/FINAL-REPORT.md').read_text()
    questions=[int(x) for x in re.findall(r'^\| (\d+) \|',report,re.M)]
    assert questions==list(range(1,23)),questions
    for field,status in STATES.items():
        assert re.search(r'^'+field+r'\s*=\s*'+status+r'\s*$',report,re.M),field
    diff=json.loads((ROOT/'analysis/isa-diff.json').read_text())['programs']
    diff+=json.loads((ROOT/'analysis/ps-variants.json').read_text())['programs']
    for name,n,count in [('ps',152,11),('vs',288,24),('ps-kp1',440,29),('ps-kp2',216,15)]:
        p=next(x for x in diff if x['name']==name)
        code=(ROOT/f'analysis/{name}-bounded.bin').read_bytes()
        assert len(code)==n and len(p['instructions'])==count
        assert hashlib.sha256(code).hexdigest()==p['sha256']
        assert not p['boundary']['branches']
        assert 'EOT' in p['boundary']['eot']['opts'] and not p['boundary']['eot'].get('pred')
    for name,count in [('ps',4),('vs',15),('ps-kp1',8),('ps-kp2',4)]:
        p=json.loads((ROOT/f'analysis/translated-{name}/report.json').read_text())
        assert p['status']=='UNSUPPORTED' and not p['full_shader_emitted'] and p['validated_units']==count
        for unit in p['instructions']:
            if unit['status']=='ROUNDTRIP_VALIDATED':
                assert (ROOT/f'analysis/translated-{name}'/unit['artifact']).read_bytes().hex()==unit['target_bytes']
            else:assert unit['code'] and unit['source_offset'] is not None
    for p in json.loads((ROOT/'analysis/upstream-semantic-review.json').read_text()):
        assert p['iga_target_decode_exit']==0 and p['binary_roundtrip_identical']
        assert p['full_shader_semantics_validated'] is False
    native=json.loads((ROOT/'analysis/native-matrix.json').read_text())
    assert len(native)==64 and not any(x.get('sanitizer_diagnostic') for x in native)
    assert all(x.get('exit') in {0,1} for x in native), 'native crash or unavailable backend'
    gcc=json.loads((ROOT/'analysis/mesa-gcc-comparison.json').read_text())
    assert len(gcc)==2 and all(x['exit']==0 and x['same_as_clang_target'] for x in gcc)
    coverage=json.loads((ROOT/'tests/translator-coverage.json').read_text())
    assert coverage['translator']['sha256']==hashlib.sha256((ROOT/'translator/offline_translate.py').read_bytes()).hexdigest()
    tests=(ROOT/'logs/test-all.txt').read_text()
    assert re.search(r'Ran \d+ tests',tests) and tests.rstrip().endswith('OK'),tests[-500:]
    repo=(ROOT/'logs/repository-check.txt').read_text()
    assert repo.rstrip().endswith('[make check exit=0]'),repo[-500:]
    receipts={'scope':'offline acceptance, not GPU execution','required_artifacts':checked,
              'questions':questions,'statuses':STATES,'checks':['nonempty deliverables','22 numbered answers',
              '7 status fields','actual instruction byte/hash/EOT consistency','31 target-unit bytes and refusal policy',
              'upstream decode and roundtrip with semantics unproven','64 native runs no sanitizer diagnostics',
              'coverage translator hash matches current source','unittest and repository check logs'],
              'hardware_execution_validated':False}
    (ROOT/'analysis/delivery-audit.json').write_text(json.dumps(receipts,indent=2)+'\n')
    print('Accepted:',len(checked),'required artifacts, 22 answers, 7 states; no hardware execution claim')
if __name__=='__main__':main()
