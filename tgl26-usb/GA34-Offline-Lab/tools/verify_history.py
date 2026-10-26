#!/usr/bin/env python3
"""Read-only end-of-work audit of the sealed historical Lab and GA3.3 copies."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def main():
    old=ROOT.parent/'GA32-ISA-Lab';manifest=old/'manifest.json'
    expected='6527515adfde14011a604c2caea7aa0abb6aedb53e9269a7951c194559b656fe'
    assert sha(manifest)==expected
    data=json.loads(manifest.read_text())
    for row in data['files']+data['external_inputs']:
        p=Path(row['path']);p=p if p.is_absolute() else old/p
        assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],str(p)
    for dep in data['dependencies']:
        p=old/dep['path']
        assert subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()==dep['commit']
        assert not subprocess.check_output(['git','-C',str(p),'status','--porcelain'],text=True)
    source=json.loads((ROOT/'reference/ga33-source-provenance.json').read_text())
    for row in source['files']:
        assert sha(Path(row['source']))==sha(ROOT/row['copy'])==row['sha256']
    out={'historical_manifest_sha256':expected,'historical_local_files_verified':len(data['files']),
         'historical_external_inputs_verified':len(data['external_inputs']),'clean_source_pins':data['dependencies'],
         'ga33_copies_unchanged':len(source['files']),'hardware_or_media_access':'NONE'}
    (ROOT/'logs/historical-preservation.json').write_text(json.dumps(out,indent=2)+'\n')
    print('PASS historical',len(data['files']),'local +',len(data['external_inputs']),'external;2 clean pins;4 GA3.3 source copies unchanged')
if __name__=='__main__':main()
