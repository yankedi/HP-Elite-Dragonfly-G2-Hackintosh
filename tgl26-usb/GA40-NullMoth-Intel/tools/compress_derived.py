#!/usr/bin/env python3
"""Losslessly archive completed GA40 Rust test build outputs, one file at a time.

No source, logs, test inputs/results or historical artifact is removed.
Each original is replaced only after its gzip bytes decompress to the same SHA.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'build/translator-test'
receipt=ROOT/'logs/translator-build-compression-001.jsonl'
if receipt.exists(): raise SystemExit('Fresh immutable compression receipt required')
files=sorted((p for p in base.rglob('*') if p.is_file() and not p.is_symlink() and p.stat().st_size>1024*1024),key=lambda p:p.stat().st_size)
def digest(stream):
    h=hashlib.sha256()
    for chunk in iter(lambda:stream.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
with receipt.open('x') as journal:
    for p in files:
        out=p.with_name(p.name+'.ga40.gz')
        if out.exists(): raise RuntimeError('Refuse overwrite')
        st=p.stat()
        with p.open('rb') as src: original=digest(src)
        try:
            with p.open('rb') as src, out.open('xb') as raw:
                with gzip.GzipFile(filename='',mode='wb',fileobj=raw,compresslevel=6,mtime=0) as gz:
                    shutil.copyfileobj(src,gz,1024*1024)
                raw.flush(); os.fsync(raw.fileno())
            with gzip.open(out,'rb') as check: assert digest(check)==original
            with p.open('rb') as src: assert digest(src)==original
            row={'original':str(p.relative_to(ROOT)),'original_bytes':st.st_size,
                 'original_sha256':original,'original_mode':st.st_mode,'archive':str(out.relative_to(ROOT)),
                 'archive_bytes':out.stat().st_size,'decompressed_sha256_verified':True}
            with out.open('rb') as src: row['archive_sha256']=digest(src)
            journal.write(json.dumps(row)+'\n'); journal.flush(); os.fsync(journal.fileno())
            p.unlink()
        except BaseException:
            if p.exists() and out.exists(): out.unlink()
            raise
        if shutil.disk_usage(ROOT).free>=3*1024**3: break
print(json.dumps({'free_bytes':shutil.disk_usage(ROOT).free,'receipt':str(receipt)}))
