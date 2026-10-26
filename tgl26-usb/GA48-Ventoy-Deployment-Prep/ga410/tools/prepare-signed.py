#!/usr/bin/env python3
"""Create and natively sign a new experimental package, preserving original code."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
from remote import ROOT, SSH, run


def main():
    paths = json.loads((ROOT / 'private/paths.json').read_text())
    source = '/Users/Shared/GA48-preflight/package'
    dest = paths['work'] + '/package-signed'
    collect = '--collect-existing' in sys.argv
    if not collect:
        run('original-staging-before-sign', 'cd ' + source + ' && /usr/bin/shasum -a 256 -c ../PACKAGE-SHA256SUMS')
        run('copy-signing-candidate', '/bin/test ! -e ' + dest + ' && /usr/bin/ditto --rsrc --extattr --acl ' + source + ' ' + dest)
    manifest = json.loads((ROOT.parent / 'ga49/private/GA47-MANIFEST.expected.json').read_text())
    binaries = [x['path'] for x in manifest['binaries']]
    bundles = sorted({str(Path(x['path']).parents[1]) for x in manifest['inventory'] if x['path'].endswith('/Contents/Info.plist')}, key=lambda s: (-s.count('/'), s))
    operations = []
    for index, relative in enumerate(binaries + bundles):
        quoted = shlex.quote(dest + '/' + relative)
        # Preserve original explicit identifier, entitlements and flags only when
        # a real original signature exists. Never retain Apple anchor requirements.
        def operation(name, command, **kwargs):
            if collect:
                row = json.loads((ROOT / 'private/commands' / (name + '.json')).read_text())
                assert row['command'] == command
                return row
            return run(name, command, **kwargs)
        display = operation('sign-display-' + str(index), '/usr/bin/codesign --display --verbose=4 ' + quoted, check=False)
        metadata = ' --preserve-metadata=identifier,entitlements,flags' if display['returncode'] == 0 else ''
        row = operation('adhoc-sign-' + str(index), '/usr/bin/codesign --force --sign - --timestamp=none' + metadata + ' ' + quoted)
        verify = operation('adhoc-verify-' + str(index), '/usr/bin/codesign --verify --strict --deep --verbose=4 ' + quoted)
        assert row['returncode'] == verify['returncode'] == 0
        operations.append({'path': relative, 'display_before_rc': display['returncode'], 'sign_rc': row['returncode'], 'verify_rc': verify['returncode'], 'signature': 'AD_HOC_NOT_APPLE_TRUST'})
    # Download only this prepared copy as a tar for independent code-byte checks.
    remote_tar = paths['work'] + '/package-signed.tar'
    if not collect:
        run('archive-signed-candidate', '/usr/bin/tar -cf ' + remote_tar + ' -C ' + paths['work'] + ' package-signed')
    run('compress-signed-candidate', '/usr/bin/gzip -c ' + remote_tar + ' > ' + remote_tar + '.gz', timeout=90)
    from remote import download
    local = ROOT / 'private/package-signed.tar.gz'
    download(remote_tar + '.gz', local, timeout=600)
    with local.open('rb') as f:
        tar_hash = hashlib.file_digest(f, 'sha256').hexdigest()
    (ROOT / 'reports/SIGNING.json').write_text(json.dumps({'candidate': dest, 'original_staging_unchanged': True, 'signature_policy': 'Experimental ad-hoc only, not Apple or Developer ID trust; no automatic install/registration', 'operations': operations, 'signed_tar_sha256': tar_hash, 'functional_code_check': 'PENDING'}, indent=2) + '\n')
    print('Native ad-hoc signing/strict verification complete:', len(binaries), 'binaries and', len(bundles), 'bundles')


if __name__ == '__main__':
    main()
