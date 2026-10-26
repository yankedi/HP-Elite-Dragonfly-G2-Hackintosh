#!/usr/bin/env python3
"""Derive native Recovery checksums from the exact SHA-verified complete backup."""
import hashlib
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SHA = '95cc69b3cc94963ba370e2103a4781d49d359df7512fd0ae856b5137717f1a33'


def main():
    archive = ROOT / 'private/GA410-backup-20261023-0830-complete.restore.zip'
    with archive.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == ARCHIVE_SHA
    rows = {}

    def add(data, expected):
        assert hashlib.sha256(data).hexdigest() == expected
        value = hashlib.md5(data).hexdigest()
        assert rows.setdefault(expected, value) == value

    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        root = 'GA410-backup-20261023-0830/'
        assert z.read(root + 'backup.rc').strip() == b'0'
        assert root + 'BACKUP-COMPLETE' in z.namelist()
        for line in z.read(root + 'SHA256SUMS').decode().splitlines():
            expected, path = line.split('  ', 1)
            add(z.read(root + path), expected)
        source = {line.split('  ', 1)[1]: line.split('  ', 1)[0] for line in z.read(root + 'SOURCE-SHA256SUMS').decode().splitlines()}
        seen = set()
        with z.open(root + 'files.pax') as stream, tarfile.open(fileobj=stream, mode='r|') as t:
            for member in t:
                if member.name in source:
                    add(t.extractfile(member).read(), source[member.name])
                    seen.add(member.name)
        assert seen == source.keys() and len(seen) == 16
    with archive.open('rb') as stream:
        rows[ARCHIVE_SHA] = hashlib.file_digest(stream, 'md5').hexdigest()
    data = ''.join(sha + '\t' + md5 + '\n' for sha, md5 in sorted(rows.items())).encode()
    assert hashlib.md5(data).hexdigest() == '3daad14eceb3f6d139b5f7ff5bf58997'
    (ROOT / 'reports/recovery-checksums.tsv').write_bytes(data)
    print('PASS: exact complete ZIP, all backup manifest entries and 16 source files; native map reproducible')


if __name__ == '__main__':
    main()
