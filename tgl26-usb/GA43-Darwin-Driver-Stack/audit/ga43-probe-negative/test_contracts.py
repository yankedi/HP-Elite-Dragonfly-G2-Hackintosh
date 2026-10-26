#!/usr/bin/env python3
"""Binary contract negative witnesses ONLY; never load any mutated image.

Use the actual diagnostic link as a carrier. Hide its known binder symbol
only to isolate lazy-dependency and rpath checks. This does NOT make the
carrier loadable or a strict linker success; original bytes/logs stay intact.
"""
import importlib.util
from pathlib import Path
import struct

root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('contract', root/'tools/inspect-darwin-probe.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
out = root/'artifacts/probe-contract-mutants-001'
out.mkdir()
data = bytearray((root/'artifacts/darwin-probes-002/DIAGNOSTIC_ONLY.dylib').read_bytes())
ncmd, size = struct.unpack_from('<II', data, 16)
pos = 32
for _ in range(ncmd):
    cmd, length = struct.unpack_from('<II', data, pos)
    if cmd == 2:
        symoff, nsym = struct.unpack_from('<II', data, pos+8)
        for i in range(nsym):
            offset = symoff+i*16+4
            if data[offset] & 0xf == 1:
                data[offset] &= ~1 # test isolation, NOT a production fix
    pos += length
def save_and_check(name, command, expected):
    mutated = bytearray(data)
    if command:
        end = 32+size
        assert not any(mutated[end:end+len(command)]), 'no load-command padding'
        mutated[end:end+len(command)] = command
        struct.pack_into('<II', mutated, 16, ncmd+1, size+len(command))
    path = out/name
    path.write_bytes(mutated)
    try:
        contract.inspect(path, 'dylib', install_name='@rpath/DIAGNOSTIC_ONLY.dylib',
                         rpath='@loader_path', exports=['_ga43_checked_add'])
    except AssertionError as error:
        assert not expected, str(error)
        print(name, 'correctly rejected:', error)
    else:
        assert expected, 'unsafe dependency/search-path contract accepted'
        print(name, 'isolated carrier parsed (NOT LINK/LOAD SUCCESS)')
def command(cmd, name, fixed):
    encoded = name.encode()+b'\0'
    length = (fixed+len(encoded)+7)&~7
    return struct.pack('<III', cmd, length, fixed)+bytes(fixed-12)+encoded+bytes(length-fixed-len(encoded))
save_and_check('NOT_FOR_LOADING-carrier', b'', True)
save_and_check('NOT_FOR_LOADING-lazy', command(0x20, '/tmp/unapproved.dylib', 24), False)
save_and_check('NOT_FOR_LOADING-rpath', command(0x8000001c, '/tmp/unapproved', 12), False)
print('PASS isolated lazy dependency and extra-rpath rejection; no SDK/link/runtime success claimed')
