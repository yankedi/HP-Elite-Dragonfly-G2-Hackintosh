#!/usr/bin/env python3
"""Fail-closed Mach-O probe artifact contract, independently of linker flags.

Use alongside LLVM raw inspection, never to infer runtime/GPU capability.
Imports require a real, approved LC_LOAD_DYLIB ordinal; flat/dynamic lookup
and executable/self ordinals are rejected even if MH_NOUNDEFS is present.
"""
import argparse
import json
from pathlib import Path
import struct

if not __debug__:
    raise SystemExit('Evidence contracts require Python assertions; optimized Python is rejected')

def inspect(path, kind, allow=(), required=(), install_name=None, rpath=None, exports=()):
    data = Path(path).read_bytes()
    assert len(data) >= 32, 'absent/truncated Mach-O output'
    magic, cpu, subtype, filetype, ncmd, cmdsize, flags, reserved = struct.unpack_from('<8I', data)
    assert magic == 0xfeedfacf and cpu == 0x1000007, 'not thin x86_64 Mach-O'
    assert filetype == {'object': 1, 'dylib': 6}[kind], 'wrong output file type'
    assert cmdsize <= len(data)-32 and ncmd <= cmdsize//8, 'invalid load commands'
    libs, ids, rpaths, symbols = [], [], [], None
    def string(start, end):
        assert 0 <= start < end <= len(data), 'invalid string offset'
        nul = data.find(b'\0', start, end)
        assert nul >= 0, 'unterminated string'
        return data[start:nul].decode('utf-8')
    pos = 32
    for _ in range(ncmd):
        cmd, size = struct.unpack_from('<II', data, pos)
        assert size >= 8 and size % 8 == 0 and pos+size <= 32+cmdsize, 'invalid command size'
        # Strong/weak/reexport/upward dylibs all consume import ordinals.
        if cmd in (0xc, 0x20, 0x80000018, 0x8000001f, 0x80000023, 0xd, 0x8000001c):
            assert size >= (12 if cmd == 0x8000001c else 24)
            offset = struct.unpack_from('<I', data, pos+8)[0]
            assert offset >= (12 if cmd == 0x8000001c else 24)
            name = string(pos+offset, pos+size)
            (ids if cmd == 0xd else rpaths if cmd == 0x8000001c else libs).append(name)
        if cmd == 2:
            assert size == 24 and symbols is None, 'missing/duplicate symbol contract'
            symbols = struct.unpack_from('<4I', data, pos+8)
        pos += size
    assert pos == 32+cmdsize and symbols is not None, 'incomplete load commands/symbol table'
    imports, defined = [], set()
    symoff, nsym, stroff, strsize = symbols
    assert symoff <= len(data) and nsym <= (len(data)-symoff)//16
    assert stroff <= len(data) and strsize <= len(data)-stroff
    for i in range(nsym):
        strx, typ, sect, desc, value = struct.unpack_from('<IBBHQ', data, symoff+i*16)
        assert strx < strsize, 'invalid symbol name'
        name = string(stroff+strx, stroff+strsize)
        if typ & 0xe0 or not typ & 1: # debug/non-external symbols
            continue
        if typ & 0xe == 0:
            ordinal = desc >> 8
            imports.append({'name': name, 'ordinal': ordinal})
            if kind == 'dylib':
                assert value == 0 and 1 <= ordinal <= len(libs), f'unbound import {name}, ordinal {ordinal}'
        elif typ & 0xe == 0xe and sect:
            defined.add(name)
    if kind == 'dylib':
        assert set(libs) <= set(allow), f'unapproved dependencies {libs}'
        assert set(required) <= set(libs), f'missing required dependencies {required}'
        if install_name is not None:
            assert ids == [install_name], f'wrong install_name {ids}'
        assert rpaths == ([] if rpath is None else [rpath]), f'unapproved rpaths {rpaths}'
        assert set(exports) <= defined, f'missing exports {set(exports)-defined}'
    return {'file': str(Path(path).resolve()), 'kind': kind, 'imports': imports,
            'dependencies': libs, 'install_names': ids, 'rpaths': rpaths,
            'required_exports': list(exports), 'validated': True}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('path')
    p.add_argument('--kind', choices=['object', 'dylib'], required=True)
    p.add_argument('--allow', action='append', default=[])
    p.add_argument('--require', action='append', default=[])
    p.add_argument('--export', action='append', default=[])
    p.add_argument('--id')
    p.add_argument('--rpath')
    a = p.parse_args()
    print(json.dumps(inspect(a.path, a.kind, a.allow, a.require, a.id, a.rpath, a.export), indent=2))
