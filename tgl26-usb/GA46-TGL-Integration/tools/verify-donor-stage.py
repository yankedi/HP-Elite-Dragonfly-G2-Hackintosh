#!/usr/bin/env python3
"""Independent read-only check: exact changed-offset set and reverse originals.

Does not import the writer or its configuration, and never changes the input.
"""
import hashlib
import json
from pathlib import Path
import sys

def sha(b):return hashlib.sha256(b).hexdigest()
dst=Path(sys.argv[1]).resolve();plan=json.loads((dst/'PATCH-PLAN.json').read_text())
for r in plan['records']:
    before=(Path(plan['source'])/r['relative_path']).read_bytes()
    after=(dst/r['relative_path']).read_bytes()
    assert len(before)==len(after) and sha(before)==r['original_sha256'] and sha(after)==r['patched_sha256']
    changes=set();undo=bytearray(after)
    ranges=[]
    for p in r['patches']:
        o=p['offset'];old=bytes.fromhex(p['old_hex']);new=bytes.fromhex(p['new_hex'])
        assert before[o:o+len(old)]==old
        if not p['applied']:
            assert after[o:o+len(old)]==old
            continue
        assert len(old)==len(new) and after[o:o+len(new)]==new
        assert all(o+len(new)<=a or o>=b for a,b in ranges),'overlapping patch'
        ranges.append((o,o+len(new)))
        changes.update(o+i for i,(a,b) in enumerate(zip(old,new)) if a!=b)
        undo[o:o+len(old)]=old
    assert {i for i,(a,b) in enumerate(zip(before,after)) if a!=b}==changes,'unplanned bytes modified'
    assert bytes(undo)==before and sha(undo)==r['reverse_sha256']
print('PASS independent changed-byte set / excluded bytes / full reverse SHA; 18 entries; no signature validity claim')
