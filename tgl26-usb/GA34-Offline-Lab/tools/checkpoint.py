#!/usr/bin/env python3
"""Append immutable local checkpoint events, retaining original evidence hashes."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('id');p.add_argument('--observation',required=True)
    p.add_argument('--next',required=True);p.add_argument('--evidence',nargs='*',default=[]);a=p.parse_args()
    path=ROOT/'experiment-history.json';data=json.loads(path.read_text()) if path.exists() else {'schema':1,'events':[]}
    if any(e['id']==a.id for e in data['events']):raise ValueError('Checkpoint id already exists')
    evidence=[]
    for rel in a.evidence:
        f=(ROOT/rel).resolve()
        if not f.is_relative_to(ROOT):raise ValueError('Evidence path escapes lab')
        evidence.append({'path':rel,'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
    data['events'].append({'id':a.id,'date':datetime.now(timezone.utc).isoformat(),
       'observed':a.observation,'evidence':evidence,'source_img':None,'result_img':None,
       'scope':'offline only; no image, GPU, HP or historical tree changes','next_action_at_event':a.next})
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print('Appended',a.id)
if __name__=='__main__':main()
