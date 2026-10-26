"""Pinned IGA CLI JSON adapter with exact raw framing and strict source anchoring."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common import HISTORY, ROOT, Rejected, dump, frames, load, output_root, sha, write_bytes

BRANCHES = {'jmpi', 'if', 'else', 'endif', 'while', 'break', 'cont', 'call', 'ret',
            'halt', 'goto', 'brd', 'brc', 'join', 'do', 'calla'}
PIN = 'c36a504a4e6c68030c3302646aa396b8b59b22cb'


def verify_iga(binary: Path) -> dict:
    tree = HISTORY / 'tools/iga/source'
    proc = subprocess.run(['git', '-C', str(tree), 'rev-parse', 'HEAD'],
                          capture_output=True, timeout=15, check=True)
    if proc.stdout.decode().strip() != PIN:
        raise Rejected('TOOL_VERSION_MISMATCH', str(tree))
    relative = str(binary.relative_to(HISTORY))
    archived = load(HISTORY / 'manifest.json')['files']
    entry = next((e for e in archived if e['path'] == relative), None)
    if entry is None or sha(binary.read_bytes()) != entry['sha256']:
        raise Rejected('TOOL_HASH_MISMATCH', str(binary))
    library = binary.parents[1] / 'IGALibrary/libiga64.so'
    libentry = next((e for e in archived if e['path'] == str(library.relative_to(HISTORY))), None)
    if libentry is None:
        # GA32's historical manifest excludes this shared library. Its present
        # bytes were independently collected in GA38, not retroactively sealed
        # as GA32 evidence. Preserve the distinction in the tool receipt.
        identities = load(ROOT / 'reference/inventory/PROVENANCE.json')['tool_identity']
        libentry = next((v for v in identities.values()
                         if v.get('path') == str(library.relative_to(ROOT.parent))), None)
    if libentry is None or sha(library.read_bytes()) != libentry['sha256']:
        raise Rejected('TOOL_LIBRARY_HASH_MISMATCH', str(library))
    return {'binary_path': str(binary), 'binary_sha256': entry['sha256'], 'source_commit': PIN,
            'library_path': str(library), 'library_sha256': libentry['sha256'],
            'platforms': ['11', '12p1'], 'api': 'IGA CLI -Xprint-json',
            'identity_scope': 'GA32-archived executable hash, independently collected GA38 library hash and source commit; not a rebuilt-binary attestation'}


def decode(data: bytes, platform: str, directory: Path, binary: Path | None = None) -> dict:
    if platform not in {'11', '12p1'}:
        raise Rejected('PLATFORM_UNSUPPORTED', platform)
    expected = frames(data)
    directory = output_root(directory)
    binary = binary or HISTORY / 'tools/iga/build/IGAExe/iga64'
    tool = verify_iga(binary)
    directory.mkdir(parents=True, exist_ok=True)
    inp = directory / 'input.bin'
    write_bytes(inp, data)
    command = [str(binary), '-d', '-p=' + platform, '-Xprint-json', '-Xprint-pc', str(inp)]
    try:
        env = {k: v for k, v in os.environ.items() if k not in {'LD_PRELOAD', 'LD_AUDIT', 'LD_LIBRARY_PATH'}}
        env.update(PYTHONDONTWRITEBYTECODE='1', LD_LIBRARY_PATH=str(Path(tool['library_path']).parent))
        proc = subprocess.run(command, capture_output=True, timeout=30, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Rejected('TOOL_FAILURE', str(exc)) from exc
    write_bytes(directory / 'iga.stdout.json', proc.stdout)
    write_bytes(directory / 'iga.stderr.txt', proc.stderr)
    dump(directory / 'invocation.json', {'command': command, 'exit': proc.returncode,
         'input_sha256': sha(data), 'stdout_sha256': sha(proc.stdout),
         'stderr_sha256': sha(proc.stderr), 'tool': tool})
    if proc.returncode:
        raise Rejected('ILLEGAL_ENCODING', proc.stderr.decode(errors='replace'))
    try:
        obj = json.loads(proc.stdout)
        ins = [i for i in obj['elems'] if i['kind'] == 'I']
        if len(ins) != len(expected) or [i['pc'] for i in ins] != [p for p, _ in expected]:
            raise Rejected('DECODE_BOUNDARY_MISMATCH', 'IGA PC set differs from raw compact framing')
        for i in ins:
            if i['op'] in BRANCHES:
                raise Rejected('CONTROL_FLOW_UNSUPPORTED', i['op'], i['pc'])
            if not isinstance(i['op'], str) or type(i.get('es')) is not int:
                raise Rejected('DECODER_SCHEMA', 'Missing opcode/execution size', i['pc'])
    except (ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, Rejected):
            raise
        raise Rejected('DECODER_SCHEMA', str(exc)) from exc
    return {'instructions': ins, 'frames': expected, 'tool': tool,
            'json_sha256': sha(proc.stdout), 'platform': platform}
