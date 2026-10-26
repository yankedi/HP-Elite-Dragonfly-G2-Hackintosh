#!/usr/bin/env python3
"""Conservative file-level licence evidence; UNKNOWN is not cleared as MIT."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'sources/mesa'
out=ROOT/'reference/mesa-licenses'
out.mkdir(exist_ok=False)
files=json.loads((ROOT/'sources/mesa-tracked-manifest.json').read_text())
rows=[]
for item in files:
    path=source/item['path']
    if item['kind']!='file':
        rows.append(dict(item,license='NOT_CLASSIFIED_SYMLINK',evidence=[])); continue
    head=path.read_bytes()[:16384].decode('utf-8',errors='replace')
    matches=[]
    for line,text in enumerate(head.splitlines(),1):
        m=re.search(r'SPDX-License-Identifier:\s*(.+)',text)
        if m: matches.append({'line':line,'text':m.group(1).strip().rstrip('*/').strip()})
    if matches:
        label='SPDX_HEADER_PRESENT'
    elif 'Permission is hereby granted, free of charge' in head and 'THE SOFTWARE IS PROVIDED' in head:
        label='MIT_STYLE_TEXT_REQUIRES_FILE_REVIEW'
        matches=[{'line':next(i for i,t in enumerate(head.splitlines(),1) if 'Permission is hereby granted' in t),
                  'text':'MIT-style permission text; preserve full file copyright/terms'}]
    else:
        label='NOT_FOUND_OR_UNKNOWN'
    rows.append(dict(item,license=label,evidence=matches))
result={'source_commit':'31e9a6b2e95e30d84bf3177d1f497d063e59b6b2',
        'method':'File header scan first16KiB; not legal clearance; do not infer all Mesa MIT',
        'policy':'sources/mesa/docs/license.rst:25-37,50: multiple component licenses; consult per-file SPDX',
        'counts':dict(Counter(row['license'] for row in rows)),'files':rows}
(out/'file-level.json').write_text(json.dumps(result,indent=2)+'\n')
shutil.copyfile(source/'docs/license.rst',out/'mesa-license-policy.rst')
shutil.copytree(source/'licenses',out/'licenses')
print(json.dumps({'files':len(rows),'counts':result['counts'],
                  'manifest_sha256':hashlib.sha256((out/'file-level.json').read_bytes()).hexdigest()}))
