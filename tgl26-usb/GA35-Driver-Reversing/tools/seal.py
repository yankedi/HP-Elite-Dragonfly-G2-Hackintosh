#!/usr/bin/env python3
"""Create or verify the private GA35 file manifest. No SSH or historical writes."""
import argparse
import hashlib
import json
import pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
EXCLUDED={'manifest.json','manifest.sha256','logs/manifest-verification.txt','logs/seal-create.txt'}


def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def files():
    rows=[]
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT).as_posix()
        if p.is_symlink():raise ValueError(f'symlink not allowed: {rel}')
        if p.is_file() and rel not in EXCLUDED:
            rows.append({'path':rel,'bytes':p.stat().st_size,'sha256':digest(p)})
    return rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['create','verify']);args=ap.parse_args()
    path=ROOT/'manifest.json'
    if args.action=='create':
        if path.exists():raise SystemExit('refuse overwriting sealed manifest')
        rows=files()
        path.write_text(json.dumps({'schema_version':1,'scope':'Private GA35 deliverable only; Apple proprietary input stays local',
                                  'excluded_self_and_receipts':sorted(EXCLUDED),'files':rows},indent=2)+'\n')
        (ROOT/'manifest.sha256').write_text(digest(path)+'  manifest.json\n')
        print('CREATED',len(rows),'files',digest(path))
    else:
        expected=json.loads(path.read_text())
        if expected['excluded_self_and_receipts']!=sorted(EXCLUDED):raise SystemExit('unexpected exclusions')
        if (ROOT/'manifest.sha256').read_text()!=digest(path)+'  manifest.json\n':raise SystemExit('manifest self digest mismatch')
        if expected['files']!=files():raise SystemExit('manifest content/size/digest or file set mismatch')
        print('PASS_PRIVATE_MANIFEST',len(expected['files']),'files','SHA256',digest(path))


if __name__=='__main__':main()
