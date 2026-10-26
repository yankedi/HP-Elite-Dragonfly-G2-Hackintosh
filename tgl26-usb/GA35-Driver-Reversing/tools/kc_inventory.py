#!/usr/bin/env python3
import hashlib
import json
import mmap
import pathlib
from macho import Image, FormatError, safe_name, confined

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGETS = ('AppleIntelICLGraphics','AppleIntelICLLPGraphicsFramebuffer','IOAcceleratorFamily2','IOGraphicsFamily','IOGPUFamily')


def main():
    dest = ROOT/'analysis'/'kc'
    dest.mkdir(parents=True,exist_ok=True)
    trusted = {}
    for receipt in (ROOT/'logs').glob('fetch*receipt.json'):
        for r in json.loads(receipt.read_text()):
            if r.get('verified'):
                trusted[r['local']] = r['sha256']
    for path in sorted((ROOT/'inputs'/'macos-readonly').rglob('*.kc')):
        if str(path.relative_to(ROOT)) not in trusted:
            print('SKIP unverified/incomplete',path)
            continue
        with path.open('rb') as f, mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
            digest=hashlib.sha256(data).hexdigest()
            if digest!=trusted[str(path.relative_to(ROOT))]:raise FormatError('input hash mismatch')
            top = Image(data)
            result = {'source':str(path.relative_to(ROOT)), 'sha256':hashlib.sha256(data).hexdigest(),
                      'bytes':len(data),'collection':top.inventory(),'images':[]}
            for e in top.entries:
                if any(t in e['name'] for t in TARGETS) or e['name'] == 'com.apple.kernel':
                    im = Image(data,e['fileoff'],e['name'])
                    textseg=next((s for s in im.segments if s['name']=='__TEXT'),None)
                    if textseg is None or textseg['vmaddr']!=e['vmaddr'] or textseg['fileoff']!=e['fileoff']:
                        raise FormatError('fileset entry/child TEXT mismatch')
                    inv = im.inventory()
                    syms = im.symbols()
                    inv['symbol_count'] = len(syms)
                    result['images'].append(inv)
                    if e['name'] != 'com.apple.kernel':
                        confined(dest,safe_name(e['name'])+'.symbols.json').write_text(json.dumps(syms,indent=2)+'\n')
            if hashlib.sha256(data).hexdigest()!=digest:raise FormatError('input changed during parse')
            (dest/(path.name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
            print(path.name, result['sha256'], 'entries',len(top.entries),[(i['name'],i['uuid'],i['symbol_count']) for i in result['images']])


if __name__ == '__main__':
    main()
