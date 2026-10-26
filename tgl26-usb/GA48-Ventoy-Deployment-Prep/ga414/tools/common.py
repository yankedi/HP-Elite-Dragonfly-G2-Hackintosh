#!/usr/bin/env python3
"""GA414 artifact helpers; no installation, boot changes or GPU submission."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga414/private'
REPORTS = ROOT / 'ga414/reports'
R6 = ROOT / 'ga410/private/ng-r6'
RECIPE = ROOT.parent / 'GA47-JulioNectar-HP-Port/hp-port/build-offline.py'
FIND = bytes.fromhex('f68691000000028b4218750b83e0f8894218')
REPLACE = bytes.fromhex('f68691000000028b4218909083e0f8894218')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*')) if p.is_file()}


def record(path):
    return {'path': os.path.relpath(path, ROOT), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def save(path, value):
    content = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(content)


def run(args, timeout=180):
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=timeout)
    require(result.returncode == 0, f'{args}: rc={result.returncode}\n{result.stdout}\n{result.stderr}')
    return result.stdout + result.stderr


def builder():
    spec = importlib.util.spec_from_file_location('ga414_prior_build_recipe', RECIPE)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def macho(data):
    require(data[:4] == bytes.fromhex('cffaedfe') and struct.unpack_from('<I', data, 4)[0] == 0x01000007,
            'expected thin x86_64 Mach-O')
    cursor, sections, identifier = 32, {}, None
    count, command_bytes = struct.unpack_from('<II', data, 16)
    for _ in range(count):
        cmd, size = struct.unpack_from('<II', data, cursor)
        require(size >= 8 and cursor + size <= 32 + command_bytes, 'invalid Mach-O load command')
        if cmd == 0x1b:
            identifier = str(uuid.UUID(bytes=data[cursor + 8:cursor + 24])).upper()
        if cmd == 0x19:
            segment = data[cursor + 8:cursor + 24].rstrip(b'\0').decode()
            for i in range(struct.unpack_from('<I', data, cursor + 64)[0]):
                p = cursor + 72 + 80 * i
                section = data[p:p + 16].rstrip(b'\0').decode()
                address, length, offset = struct.unpack_from('<QQI', data, p + 32)
                flags = struct.unpack_from('<I', data, p + 64)[0]
                if flags & 0xff not in (1, 0xc, 0x12):
                    require(offset + length <= len(data), 'section outside file')
                    sections[segment + ',' + section] = {'address': address, 'bytes': length,
                        'offset': offset, 'sha256': hashlib.sha256(data[offset:offset + length]).hexdigest()}
        cursor += size
    require(identifier and sections and cursor == 32 + command_bytes, 'missing UUID/sections or bad load-command size')
    return {'uuid': identifier, 'filetype': struct.unpack_from('<I', data, 12)[0], 'sections': sections}
