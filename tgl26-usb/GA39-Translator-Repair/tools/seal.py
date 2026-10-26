#!/usr/bin/env python3
"""Private GA39 integrity seal. Verification is read-only, not a semantic proof."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
EXCLUSIONS = {'manifest.json', 'manifest.sha256', 'logs/seal-verification.json', 'logs/seal-verification.txt'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def describe(path, relative=None):
    info = path.lstat()
    row = {'path': str(path if relative is None else relative)}
    if stat.S_ISLNK(info.st_mode):
        text = os.readlink(path)
        raw = os.fsencode(text)
        return row | {'kind': 'symlink', 'target': text, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Non-regular artifact: ' + str(path))
    return row | {'kind': 'file', 'bytes': info.st_size, 'sha256': digest(path)}


def paths():
    result = []
    for parent, dirs, files in os.walk(ROOT, followlinks=False):
        for name in list(dirs):
            p = Path(parent) / name
            if p.is_symlink():
                result.append(p)
                dirs.remove(name)
        result.extend(Path(parent) / f for f in files)
    return sorted(p for p in result if str(p.relative_to(ROOT)) not in EXCLUSIONS)


def external_sources():
    expected = {}

    def add(path, sha):
        key = str(path)
        if key in expected and expected[key] != sha:
            raise ValueError('Conflicting external identity: ' + key)
        expected[key] = sha

    inv = json.loads((ROOT / 'reference/inventory/PROVENANCE.json').read_text())
    # Preserve the complete already sealed GA38 evidence closure privately.
    prior = ROOT.parent / 'GA38-Shader-IR-Lab'
    pin = inv['history_manifests']['GA38-Shader-IR-Lab']['sha256']
    if digest(prior / 'manifest.json') != pin:
        raise ValueError('GA38 manifest identity changed')
    old = json.loads((prior / 'manifest.json').read_text())
    add(prior / 'manifest.json', pin)
    for item in old['files']:
        add(prior / item['path'], item['sha256'])
    for item in old['external_sources']:
        add(Path(item['path']), item['sha256'])

    def walk(obj):
        if isinstance(obj, dict):
            if {'path', 'bytes', 'sha256'} <= obj.keys():
                add(Path(obj['path']), obj['sha256'])
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)
    walk(inv)
    for item in inv['history_manifests'].values():
        path = Path(item['manifest'])
        add(path, item['sha256'])
        if digest(path) != item['sha256']:
            raise ValueError('Historical manifest changed: ' + str(path))
        historical = json.loads(path.read_text())
        for row in historical['files']:
            add(path.parent / row['path'], row['sha256'])
        for row in historical.get('external_sources', []):
            add(Path(row['path']), row['sha256'])
    out = []
    for path, sha in sorted(expected.items()):
        p = Path(path)
        if not p.is_absolute() or ROOT == p or ROOT in p.parents:
            raise ValueError('Invalid external provenance path: ' + path)
        row = describe(p)
        if row['sha256'] != sha:
            raise ValueError('External input changed: ' + path)
        out.append(row)
    return out


def verify():
    pin = (ROOT / 'manifest.sha256').read_text().split()[0]
    if digest(ROOT / 'manifest.json') != pin:
        raise ValueError('Manifest self hash mismatch')
    data = json.loads((ROOT / 'manifest.json').read_text())
    actual = {str(p.relative_to(ROOT)) for p in paths()}
    declared = {r['path'] for r in data['files']}
    if len(declared) != len(data['files']) or actual != declared:
        raise ValueError(f'Artifact set changed: added={sorted(actual-declared)}, removed={sorted(declared-actual)}')
    for key, base in [('files', ROOT), ('external_sources', Path('/'))]:
        for row in data[key]:
            if describe(base / row['path'], row['path']) != row:
                raise ValueError('Artifact identity changed: ' + row['path'])
    return {'status': 'PASS', 'manifest_sha256': pin, 'local_entries': len(data['files']),
            'external_sources': len(data['external_sources']), 'hardware_validated': False,
            'scope': 'Artifact integrity only; all unproved semantics remain unproved',
            'symlink_semantics': 'hash link text; never follow fixture symlinks'}


def create():
    manifest, selfhash = ROOT / 'manifest.json', ROOT / 'manifest.sha256'
    if manifest.exists() or selfhash.exists():
        raise ValueError('Existing seal is immutable; use verify')
    data = {'schema_version': 1, 'scope': 'Private GA39 CPU-only translator repair and audit evidence',
            'files': [describe(p, p.relative_to(ROOT)) for p in paths()],
            'external_sources': external_sources(), 'exclusions': sorted(EXCLUSIONS), 'hardware_validated': False}
    manifest.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')
    selfhash.write_text(digest(manifest) + '  manifest.json\n')
    return verify()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['create', 'verify'])
    a = ap.parse_args()
    print(json.dumps(create() if a.command == 'create' else verify(), sort_keys=True))
