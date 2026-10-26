#!/usr/bin/env python3
"""Read cached target KC nlists; names are not proof of KPI eligibility/C++ ABI.

No extraction, patching, target access, KDK installation or load is performed.
The caller must provide an independently recorded exact source KC SHA256.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess


def read_kc(path):
    b = path.read_bytes()
    def unpack(fmt, at):
        size = struct.calcsize(fmt)
        if at < 0 or at + size > len(b): raise ValueError('truncated Mach-O data')
        return struct.unpack_from(fmt, b, at)
    def commands(base):
        magic, cpu, _, kind, n, size, _, _ = unpack('<8I', base)
        if magic != 0xfeedfacf or cpu != 0x1000007:
            raise ValueError('requires x86_64 little-endian Mach-O')
        at, end = base + 32, base + 32 + size
        if end > len(b): raise ValueError('load commands out of bounds')
        result = []
        for _ in range(n):
            cmd, sz = unpack('<II', at)
            if sz < 8 or sz % 8 or at + sz > end: raise ValueError('invalid command')
            result.append((cmd, at, sz))
            at += sz
        if at != end: raise ValueError('load command length mismatch')
        return kind, result
    kind, cmds = commands(0)
    if kind != 12: raise ValueError('requires MH_FILESET KC')
    entries = []
    for cmd, pos, sz in cmds:
        if cmd != 0x80000035: continue
        _, off, name_off, _ = unpack('<QQII', pos+8)
        if not 32 <= name_off < sz: raise ValueError('invalid fileset name')
        name = b[pos+name_off:pos+sz].split(b'\0', 1)[0].decode()
        entries.append((name, off))
    external, local, images = {}, {}, []
    for image, off in entries:
        kind, cmds = commands(off)
        uuid, count = None, 0
        for cmd, pos, sz in cmds:
            if cmd == 0x1b: uuid = b[pos+8:pos+24].hex()
            if cmd != 2: continue
            symoff, nsyms, stroff, strsize = unpack('<IIII', pos+8)
            if stroff + strsize > len(b): raise ValueError('string table out of bounds')
            for i in range(nsyms):
                s, typ, sect, desc, value = unpack('<IBBHQ', symoff + i*16)
                if typ & 0xe0 or (typ & 0xe) not in (2, 14) or not value: continue
                if s >= strsize: raise ValueError('symbol name out of bounds')
                end = b.find(b'\0', stroff+s, stroff+strsize)
                if end < 0: raise ValueError('unterminated symbol')
                name = b[stroff+s:end].decode()
                table = external if typ & 1 else local
                table.setdefault(name, []).append(image)
                count += 1
        images.append({'id': image, 'uuid': uuid, 'defined_nlist_count': count})
    return external, local, images


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('kc', type=Path)
    p.add_argument('module', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--kc-sha256', required=True)
    p.add_argument('--nm', required=True)
    a = p.parse_args()
    actual = subprocess.check_output(['sha256sum', str(a.kc)], text=True).split()[0]
    if actual != a.kc_sha256: raise SystemExit('cached target KC source hash mismatch')
    a.out.mkdir()
    ext, local, images = read_kc(a.kc)
    imports = sorted(set(subprocess.check_output([a.nm, '-u', str(a.module)], text=True).splitlines()))
    result = {
        'kc_sha256': actual, 'module_sha256': subprocess.check_output(
            ['sha256sum', str(a.module)], text=True).split()[0],
        'source': 'GA49 target Preboot byte-readback baseline, RECOVERY-BASELINE.json',
        'imports': [{'name': n, 'external_nlist_providers': ext.get(n, []),
                     'local_nlist_only': local.get(n, []) if n not in ext else []} for n in imports],
        'missing_external_names': [n for n in imports if n not in ext],
        'images': images, 'target_exports_contract': 'NOT_VERIFIED',
        'public_KPI': 'NOT_VERIFIED', 'CXX_vtable_layout': 'NOT_VERIFIED',
        'kc_rebuild_or_runtime': 'NOT_TESTED',
        'scope': 'Exact target cached nlist name comparison only. Local/nlist presence does not grant KPI or prove ABI.',
    }
    (a.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('imports', 'images')}, indent=2))


if __name__ == '__main__': main()
