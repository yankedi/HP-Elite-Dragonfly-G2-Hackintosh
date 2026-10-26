#!/usr/bin/env python3
"""Re-read all emitted instruction bytes/coordinates from the immutable KC copy."""
import gzip
import hashlib
import json
import mmap
import pathlib
from macho import Image, FormatError

ROOT=pathlib.Path(__file__).resolve().parents[1]


def verify_function(image, fun):
    entry=fun.get('entry_va',fun.get('entry_kc_va'))
    raw=bytes.fromhex(fun['raw_bytes'])
    off=image.va_to_offset(entry,len(raw))
    if off!=fun['kc_fileoff'] or bytes(image.data[off:off+len(raw)])!=raw:
        raise FormatError('fragment coordinate/raw mismatch')
    if hashlib.sha256(raw).hexdigest()!=fun['raw_sha256']:
        raise FormatError('fragment hash mismatch')
    cursor=entry
    for ins in fun['instructions']:
        b=bytes.fromhex(ins['bytes'])
        if ins['va']!=cursor or ins['size']!=len(b) or ins['kc_fileoff']!=off+cursor-entry:
            raise FormatError('instruction coverage/offset mismatch')
        if bytes(image.data[ins['kc_fileoff']:ins['kc_fileoff']+len(b)])!=b:
            raise FormatError('instruction bytes mismatch')
        cursor+=len(b)
    if cursor-entry!=fun['decoded_bytes'] or cursor>entry+len(raw):
        raise FormatError('decode coverage mismatch')
    return len(fun['instructions'])


def main():
    inv=json.loads((ROOT/'analysis/kc/SystemKernelExtensions.kc.json').read_text())
    path=ROOT/inv['source']
    if hashlib.file_digest(path.open('rb'),'sha256').hexdigest()!=inv['sha256']:
        raise FormatError('KC SHA mismatch')
    result={'source':inv['source'],'source_sha256':inv['sha256'],'functions':0,'instructions':0,'images':[]}
    with path.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
        for item in inv['images']:
            image=Image(data,item['header_fileoff'],item['name'])
            corpus=json.load(gzip.open(ROOT/'analysis/expanded'/(item['name']+'.all.json.gz')))
            if corpus['image_uuid']!=image.uuid or corpus['source_sha256']!=inv['sha256']:
                raise FormatError('corpus identity mismatch')
            for fun in corpus['functions']:
                if fun['uuid']!=image.uuid:raise FormatError('function UUID mismatch')
                result['instructions']+=verify_function(image,fun);result['functions']+=1
            result['images'].append({'name':item['name'],'uuid':image.uuid,'functions':len(corpus['functions'])})
    result['status']='PASS_BYTES_AND_COORDINATES_ONLY'
    (ROOT/'logs/fragment-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
