#!/usr/bin/env python3
"""Locally decode Apple's chunked pbzx payload to a new CPIO file; no install."""
import argparse
import lzma
from pathlib import Path
import struct

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('input', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
with a.input.open('rb') as src, a.output.open('xb') as dst:
    if src.read(4) != b'pbzx': raise SystemExit('not pbzx')
    header = src.read(8)
    if len(header) != 8: raise SystemExit('short pbzx header')
    chunk_size, = struct.unpack('>Q', header)
    if not 0 < chunk_size <= 64*1024*1024: raise SystemExit('invalid chunk size')
    chunks = size = 0
    while True:
        header = src.read(16)
        if not header: break
        if len(header) != 16: raise SystemExit('short chunk header')
        raw_len, length = struct.unpack('>QQ', header)
        if not 0 < raw_len <= chunk_size or not 0 < length <= 2*chunk_size:
            raise SystemExit('invalid chunk lengths')
        data = src.read(length)
        if len(data) != length: raise SystemExit('truncated chunk')
        if data.startswith(b'\xfd7zXZ\x00'): data = lzma.decompress(data)
        if len(data) != raw_len: raise SystemExit('decompressed chunk length mismatch')
        dst.write(data)
        chunks += 1
        size += len(data)
print(f'PASS {chunks} verified chunks, {size} bytes; local archive decode, not installation')
