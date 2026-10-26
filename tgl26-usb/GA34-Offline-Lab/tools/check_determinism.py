#!/usr/bin/env python3
"""Regenerate CPU analysis twice, check bytes and native cross-build receipts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import shutil
import time

ROOT=Path(__file__).resolve().parents[1]
FILES=['track-a/spec-diff.json','track-a/prm-constraints.json','track-a/state-ir.json',
       'track-a/packet-audit.json','track-a/strict-shadow-result.json',
       'track-a/shadow-batches/format-candidate-A.bin','track-a/shadow-batches/format-candidate-A.json',
       'track-a/shadow-batches/format-candidate-B.bin','track-a/shadow-batches/format-candidate-B.json',
       'track-a/shadow-batches/strict-noop-growth.bin','track-a/shadow-batches/strict-noop-growth.json',
       'track-c/reports/synthetic-correlation-fixed.json','track-b/source-audit.json']
SCRIPTS=['tools/catalog_prm_constraints.py','track-a/command_stream.py','track-a/normalizer.py',
         'track-c/correlate.py','tools/audit_fault_sources.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if (ROOT/'logs/determinism.json').exists():
        old=ROOT/'logs/determinism-previous'/str(time.time_ns());old.mkdir(parents=True)
        for name in ('determinism.json','determinism-run-1.txt','determinism-run-2.txt','determinism-check.txt'):
            p=ROOT/'logs'/name
            if p.exists():shutil.copyfile(p,old/name)
    runs=[]
    for iteration in (1,2):
        with (ROOT/f'logs/determinism-run-{iteration}.txt').open('w') as out:
            for script in SCRIPTS:
                result=subprocess.run([sys.executable,'-B',script],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT)
                if result.returncode:raise SystemExit(f'failed {script}, run{iteration}')
        runs.append({p:sha(ROOT/p) for p in FILES})
    if runs[0]!=runs[1]:raise SystemExit('analysis artifacts nondeterministic')
    native=[]
    for group in ('diagnostic-core','pack'):
        builds=[]
        for compiler in ('clang','gcc'):
            path=ROOT/(f'logs/diagnostic-core/{compiler}-results.json' if group=='diagnostic-core' else f'logs/pack-{compiler}-results.json')
            receipt=json.loads(path.read_text())
            for b in receipt['builds']:
                expected=b.get('executable_sha256',b.get('sha256'))
                if sha(ROOT/b['executable'])!=expected:raise SystemExit('native binary hash mismatch')
                builds.append(b)
            for p,s in receipt['source_sha256'].items():
                q=ROOT/'track-b/diagnostic-src'/p if group=='diagnostic-core' else ROOT/p
                if sha(q)!=s:raise SystemExit('native tested source hash mismatch '+str(q))
        stdout={b['stdout_sha256'] for b in builds}
        if len(builds)!=8 or len(stdout)!=1:raise SystemExit('cross-build output mismatch')
        native.append({'group':group,'builds':len(builds),'stdout_sha256':next(iter(stdout)),
                       'tested_source_hashes_verified':True,'executable_hashes_verified':True})
    receipt={'schema':1,'analysis_regenerations':2,'identical_artifacts':runs[0],
             'native_cross_build_groups':native,'scope':'deterministic CPU output, no GPU semantic proof'}
    (ROOT/'logs/determinism.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS:13 analysis artifacts identical over2 regenerations;16 native executable/source hashes and2 cross-build stdout groups verified')
if __name__=='__main__':main()
