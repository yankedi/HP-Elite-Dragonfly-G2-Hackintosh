#!/usr/bin/env python3
"""Fetch immutable public i915 sources; writes only GA34/reference/track-b."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
PINS={'v5.15':'8bb7eca972ad531c9b149c0a51ab43a417385813','v6.18':'7d0a66e4bb9081d75c82ec4957c50034cb0ea449'}
PATHS=['drivers/gpu/drm/i915/intel_uncore.c','drivers/gpu/drm/i915/intel_uncore.h',
       'drivers/gpu/drm/i915/gt/intel_gt.c','drivers/gpu/drm/i915/gt/intel_reset.c',
       'drivers/gpu/drm/i915/gt/intel_gt_regs.h','drivers/gpu/drm/i915/i915_reg.h',
       'drivers/gpu/drm/i915/gt/intel_gt_types.h']
def fetch(item):
    version,path=item;url=f'https://raw.githubusercontent.com/torvalds/linux/{PINS[version]}/{path}'
    dest=ROOT/'reference/track-b'/version/path
    try:
        data=urllib.request.urlopen(url,timeout=45).read()
        if dest.exists() and dest.read_bytes()!=data:raise ValueError('existing source differs')
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        return {'version':version,'commit':PINS[version],'url':url,'path':str(dest.relative_to(ROOT)),
                'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    except urllib.error.HTTPError as e:return {'version':version,'url':url,'unavailable':e.code}
def main():
    with ThreadPoolExecutor(max_workers=6) as pool:rows=list(pool.map(fetch,[(v,p) for v in PINS for p in PATHS]))
    (ROOT/'reference/track-b/provenance.json').write_text(json.dumps({'pins':PINS,'sources':rows},indent=2)+'\n')
    print('Fetched',sum('sha256' in x for x in rows),'sources;',[(x['version'],x['url'].split('/')[-1],x.get('unavailable')) for x in rows if 'unavailable' in x])
if __name__=='__main__':main()
