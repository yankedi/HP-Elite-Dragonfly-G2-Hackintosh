#!/usr/bin/env python3
"""Authenticate the original tar, reject unsafe members, check every payload byte."""
import hashlib
import json
import posixpath
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parents[1] / 'GA47-JulioNectar-HP-Port'
ARCHIVE = OLD / 'build/ga47/GA47-HP-TGL-25G83-offline.tar.gz'


def main():
    assert ARCHIVE.resolve().is_file()
    with ARCHIVE.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    assert digest == '51aaffade75da6d5076071e304e4634aefe60e68d7e0cdd12d79981e31f1b143'
    manifest_path = OLD / 'build/ga47/ARTIFACT-MANIFEST.json'
    raw = manifest_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '293e9a962c1deca138573ca913cc2a23522a9f28d49714af13e84488c86623a5'
    manifest = json.loads(raw)
    expected = {x['path']: x for x in manifest['inventory']}
    assert len(expected) == 246 and manifest['mach_o_count'] == 31
    links, checked, receipts = {}, set(), {}
    extras = {'hp-config-delta.json', 'UPSTREAM-FUNCTIONAL.patch', 'nootedgreen-build.log', 'hookcase-build.log', 'userland-build-002.log', 'nootedgreen-hp-build-003.log', 'ocvalidate-hp-linux.log', 'ocvalidate-vesa-linux.log', 'verify-sealed.log'}
    with tarfile.open(ARCHIVE) as t:
        members = t.getmembers()
        assert len({x.name for x in members}) == len(members)
        for m in members:
            p = PurePosixPath(m.name)
            assert not p.is_absolute() and '..' not in p.parts
            assert m.isdir() or m.isfile() or m.issym(), (m.name, m.type)
            assert not m.islnk()  # No special/device entries or hardlink surprises.
            if m.name == 'ARTIFACT-MANIFEST.json':
                assert m.isfile() and t.extractfile(m).read() == raw
                continue
            if m.name in extras:
                assert m.isfile()
                data = t.extractfile(m).read()
                assert data == (OLD / 'build/ga47' / m.name).read_bytes()
                receipts[m.name] = hashlib.sha256(data).hexdigest()
                continue
            assert p.parts[0] == 'package', m.name
            if m.isdir():
                continue
            rel = '/'.join(p.parts[1:])
            i = expected[rel]
            checked.add(rel)
            if m.issym():
                assert m.linkname == i['symlink'] and not m.linkname.startswith('/')
                resolved = posixpath.normpath(posixpath.join(str(p.parent), m.linkname))
                assert resolved == 'package' or resolved.startswith('package/')
                links[m.name] = m.linkname
            else:
                assert m.size == i['bytes']
                assert hashlib.sha256(t.extractfile(m).read()).hexdigest() == i['sha256']
        assert checked == expected.keys()
        assert receipts.keys() == extras
        for m in members:
            assert not any(str(parent) in links for parent in PurePosixPath(m.name).parents)
    changed = subprocess.check_output(['git', 'diff', '--name-only', 'UPSTREAM_BASE', '--', 'src', 'macos', 'build-nootedgreen.sh', 'build-hookcase.sh'], cwd=OLD, text=True).splitlines()
    assert changed == ['src/NootedGreen/kern_gen11.cpp']
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=OLD)
    report = {'archive': str(ARCHIVE), 'bytes': ARCHIVE.stat().st_size, 'sha256': digest, 'manifest_sha256': hashlib.sha256(raw).hexdigest(), 'inventory_entries': len(checked), 'mach_o': 31, 'safe_tar_paths': True, 'symlinks': links, 'additional_top_level_receipts': receipts, 'hardlinks_or_special_entries': 0, 'functional_source_delta': changed, 'upstream_base': manifest['upstream_base'], 'staging_authorization': 'User explicitly approved limited new APFS directory, original archive/manifests, safe extraction and native read-only checks; no installation/signing/loading/KC/security/reboot.'}
    (ROOT / 'reports/PACKAGE-PREFLIGHT.json').write_text(json.dumps(report, indent=2) + '\n')
    (ROOT / 'private/GA47-MANIFEST.expected.json').write_bytes(raw)
    (ROOT / 'private/PACKAGE-SHA256SUMS').write_text(''.join(i['sha256'] + '  ' + i['path'] + '\n' for i in manifest['inventory'] if 'sha256' in i))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
