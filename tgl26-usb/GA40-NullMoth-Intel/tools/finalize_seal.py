#!/usr/bin/env python3
"""Create immutable manifest and record actual read-only dual verification.

Only the two explicitly excluded final receipt paths are written by this
controller. It never repeats builds/tests and never overwrites an old seal.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
transcript=ROOT/'logs/seal-verification.txt'
receipt=ROOT/'logs/seal-verification.json'


def main():
    assert not any(p.exists() for p in [ROOT/'manifest.json',ROOT/'manifest.sha256',transcript,receipt]),'Seal or final receipt exists; never overwrite'
    state=json.loads((ROOT/'state.json').read_text())
    audit=ROOT/state['final_integrity']['delivery_audit']
    assert json.loads(audit.read_text())['exit']==0,'Final delivery audit must actually pass first'
    commands=[
        [sys.executable,'-B','tools/seal.py','create'],
        [sys.executable,'-B','tools/seal.py','verify'],
        [sys.executable,'-B','tools/verify_manifest_independent.py'],
        ['sha256sum','-c','manifest.sha256'],
    ]
    results=[]
    status='FAIL'
    with transcript.open('x') as log:
        for command in commands:
            start=time.monotonic()
            try:
                run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=240,
                                   env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
                row={'command':command,'exit':run.returncode,'stdout':run.stdout,'stderr':run.stderr,
                     'elapsed_seconds':time.monotonic()-start}
            except (OSError,subprocess.TimeoutExpired) as exc:
                row={'command':command,'exit':None,'error':str(exc),'elapsed_seconds':time.monotonic()-start}
            results.append(row)
            log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush();os.fsync(log.fileno())
            if row['exit']!=0: break
        if len(results)==4 and all(row['exit']==0 for row in results): status='PASS'
    pin=(ROOT/'manifest.sha256').read_text().split()[0] if (ROOT/'manifest.sha256').exists() else None
    final={'status':status,'manifest_sha256':pin,'delivery_audit':str(audit.relative_to(ROOT)),
           'commands':results,'scope':'Private offline artifact integrity; no GPU or macOS acceleration claim',
           'hardware_approval':'NO','next_action':'STOP; await explicit GA41 decision' if status=='PASS' else 'Preserve failure; do not overwrite seal or claim success'}
    with receipt.open('x') as out:
        json.dump(final,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
    print(json.dumps({'status':status,'manifest_sha256':pin,'receipt':str(receipt.relative_to(ROOT)),
                      'commands_passed':sum(row['exit']==0 for row in results),'hardware_approval':'NO'}))
    return 0 if status=='PASS' else 1


if __name__=='__main__': raise SystemExit(main())
