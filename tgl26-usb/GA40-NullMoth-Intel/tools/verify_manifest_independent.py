#!/usr/bin/env python3
"""Read-only independent verifier; does not import or call tools/seal.py."""
import hashlib
import json
import os
from pathlib import Path
import stat

ROOT=Path(__file__).resolve().parents[1]
EXCLUSIONS={'manifest.json','manifest.sha256','logs/seal-verification.json','logs/seal-verification.txt'}


def digest(p):
    with p.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def visit(directory):
    found=set()
    with os.scandir(directory) as children:
        for child in children:
            p=Path(child.path)
            if child.is_dir(follow_symlinks=False): found.update(visit(p))
            else: found.add(p.relative_to(ROOT).as_posix())
    return found


def main():
    manifest=ROOT/'manifest.json'
    pin=digest(manifest)
    assert (ROOT/'manifest.sha256').read_text()==pin+'  manifest.json\n'
    data=json.loads(manifest.read_text())
    assert data['schema']=='ga40-private-seal-v1'
    assert set(data['excluded_exact_paths'])==EXCLUSIONS
    rows={row['path']:row for row in data['entries']}
    assert len(rows)==len(data['entries']),'Duplicate manifest paths'
    assert visit(ROOT)-EXCLUSIONS==set(rows),'Missing or additional files'
    for name,row in rows.items():
        p=ROOT/name
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        info=p.lstat(); assert stat.S_IMODE(info.st_mode)==row['mode'],name
        if row['kind']=='symlink':
            assert stat.S_ISLNK(info.st_mode),name
            text=os.readlink(p); raw=os.fsencode(text)
            assert text==row['target'] and len(raw)==row['bytes'],name
            assert hashlib.sha256(raw).hexdigest()==row['sha256'],name
        else:
            assert row['kind']=='file' and stat.S_ISREG(info.st_mode),name
            assert info.st_size==row['bytes'] and digest(p)==row['sha256'],name
    external=json.loads((ROOT/'reference/external-inputs.json').read_text())['files']
    assert len(external)==data['external_files']
    for row in external:
        p=Path(row['path'])
        assert p.is_absolute() and ROOT not in p.parents
        assert p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],str(p)
    print(json.dumps({'status':'PASS','implementation':'independent verifier, no seal.py import',
                      'local_entries':len(rows),'external_files':len(external),
                      'manifest_sha256':pin,'hardware_approval':'NO'}))


if __name__=='__main__': main()
