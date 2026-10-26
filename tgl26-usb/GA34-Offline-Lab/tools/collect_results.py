#!/usr/bin/env python3
"""Summarize actual receipts, preserving their identities and scope."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
def load(rel):return json.loads((ROOT/rel).read_text())
def main():
    log=(ROOT/'logs/lab-check.txt').read_text()
    counts=[int(x) for x in re.findall(r'Ran (\d+) tests',log)]
    assert counts==[64,40] and 'FAILED' not in log
    core=[];pack=[]
    for compiler in ('clang','gcc'):
        core.extend(load(f'logs/diagnostic-core/{compiler}-results.json')['builds'])
        pack.extend(load(f'logs/pack-{compiler}-results.json')['builds'])
    source=load('track-a/packet-audit.json')
    out={'schema':1,'python_test_methods':{'command':counts[0],'correlation':counts[1],'total':sum(counts)},
         'native_core':{'executables':len(core),'group_invocations':sum(b['groups'] for b in core),
                        'groups_per_executable':sorted({b['groups'] for b in core}),'all_offline_pass':all(b['status']=='OFFLINE_PASS' for b in core)},
         'native_pack':{'executables':len(pack),'all_pass':all(b['status']=='PASS' for b in pack)},
         'packet_audit':{k:v for k,v in source.items() if k!='packets'},
         'determinism':load('logs/determinism.json'),'historical_preservation':load('logs/historical-preservation.json'),
         'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
             'track-a/command_stream.py','track-a/normalizer.py','track-b/diagnostic-src/kern_tglfault34.hpp','track-c/correlate.py')},
         'real_gpu_experiments':0,'real_hook_attachment':'NONE','whole_kext':'NOT_BUILT','ready_for_hardware_approval':False}
    (ROOT/'logs/results-summary.json').write_text(json.dumps(out,indent=2)+'\n')
    print('Python',sum(counts),'nativecore',len(core),'builds /',sum(b['groups'] for b in core),'groups;pack',len(pack),'builds; hardwareapprovalNO')
if __name__=='__main__':main()
