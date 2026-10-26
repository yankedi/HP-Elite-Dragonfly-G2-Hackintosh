#!/usr/bin/env python3
"""Private artifact seal; verify is read-only and never follows fixture symlinks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True
from common import ROOT, dump, load, sha

EXCLUSIONS = {'manifest.json', 'manifest.sha256', 'logs/seal-verification.json', 'logs/seal-verification.txt'}


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1 << 20), b''):
            digest.update(part)
    return digest.hexdigest()


def describe(path, relative=None):
    info = path.lstat()
    item = {'path': str(relative if relative is not None else path)}
    if stat.S_ISLNK(info.st_mode):
        target = os.readlink(path)
        data = os.fsencode(target)
        return {**item, 'kind': 'symlink', 'target': target, 'bytes': len(data), 'sha256': sha(data)}
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f'Non-regular artifact: {path}')
    return {**item, 'kind': 'file', 'bytes': info.st_size, 'sha256': file_hash(path)}


def local_paths():
    result = []
    for parent, directories, files in os.walk(ROOT, followlinks=False):
        for name in list(directories):
            path = Path(parent) / name
            if path.is_symlink():
                result.append(path)
                directories.remove(name)
        result.extend(Path(parent) / name for name in files)
    return sorted(p for p in result if str(p.relative_to(ROOT)) not in EXCLUSIONS)


def external_sources():
    expected = {}

    def add(path, digest):
        path = Path(path)
        key = str(path)
        if key in expected and expected[key] != digest:
            raise ValueError('Conflicting provenance hash: ' + key)
        expected[key] = digest

    inv = load(ROOT / 'reference/inventory/PROVENANCE.json')
    for group in inv['frozen_baseline']['groups'].values():
        for item in group:
            add(ROOT.parent / item['path'], item['sha256'])
    track_e = ROOT.parent / 'GA37-Engineering-Closure/track-e/evidence/INPUTS.json'
    for item in load(track_e)['files']:
        add(item['path'], item['sha256'])
    rules = load(ROOT / 'reference/rules/RULES.json')
    for item in rules.get('prm_sources', []):
        add(item['path'], item['sha256'])
    mesa_root = next(Path(i['repo']) for i in rules['mesa_sources'] if 'repo' in i)
    for item in rules.get('mesa_sources', []):
        if 'sha256' in item:
            add(mesa_root / item['path'], item['sha256'])
    iga_root = ROOT.parent / 'GA32-ISA-Lab/tools/iga/source/visa/iga'
    for item in rules.get('iga_source_index', []):
        source = iga_root / item['path']
        raw = source.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if blob != item['git_blob_sha1']:
            raise ValueError('Pinned IGA source blob mismatch: ' + str(source))
        add(source, sha(raw))
    # Executable + shared-library pin are checked separately from source pins.
    for item in inv['tool_identity'].values():
        if 'path' in item and 'sha256' in item:
            add(ROOT.parent / item['path'], item['sha256'])
    result = []
    for path, digest in sorted(expected.items()):
        item = describe(Path(path))
        if item['sha256'] != digest:
            raise ValueError('External provenance mismatch: ' + path)
        result.append(item)
    return result


def verify():
    manifest = ROOT / 'manifest.json'
    expected_self = (ROOT / 'manifest.sha256').read_text().split()[0]
    if file_hash(manifest) != expected_self:
        raise ValueError('Manifest self hash mismatch')
    data = load(manifest)
    actual = {str(p.relative_to(ROOT)) for p in local_paths()}
    declared = {x['path'] for x in data['files']}
    if actual != declared:
        raise ValueError(f'Artifact set changed: added={sorted(actual-declared)}, removed={sorted(declared-actual)}')
    for key, base in [('files', ROOT), ('external_sources', Path('/'))]:
        for item in data[key]:
            path = base / item['path']
            current = describe(path, item['path'])
            if current != item:
                raise ValueError('Artifact bytes/link identity changed: ' + str(path))
    return {'status': 'PASS', 'manifest_sha256': expected_self, 'local_entries': len(data['files']),
            'external_sources': len(data['external_sources']), 'symlink_semantics': 'hash link text, never follow',
            'scope': 'Artifact integrity only; not hardware semantic validation'}


def create():
    manifest, selfhash = ROOT / 'manifest.json', ROOT / 'manifest.sha256'
    if manifest.exists() or selfhash.exists():
        raise ValueError('Existing seal is immutable; use verify')
    data = {'schema_version': 1, 'scope': 'Private GA38 offline shader analysis, sources, native builds, tests and evidence',
            'exclusions': sorted(EXCLUSIONS), 'files': [describe(p, p.relative_to(ROOT)) for p in local_paths()],
            'external_sources': external_sources(), 'hardware_validated': False}
    dump(manifest, data)
    selfhash.write_text(file_hash(manifest) + '  manifest.json\n')
    return verify()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['create', 'verify'])
    args = ap.parse_args()
    print(json.dumps(create() if args.command == 'create' else verify(), sort_keys=True))
