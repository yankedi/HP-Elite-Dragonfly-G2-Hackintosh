#!/usr/bin/env python3
"""Fetch the exact catalogued KDK locally, never copy/install it on the target."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    catalog = json.loads((ROOT / 'reports/KDK-CATALOG.json').read_text())
    entry, = catalog['exact_25G83']
    assert entry['version'] == '26.6.2' and entry['build'] == '25G83'
    dest = ROOT / 'private/Kernel_Debug_Kit_26.6.2_build_25G83.dmg'
    digest = hashlib.sha256()
    with urllib.request.urlopen(entry['url'], timeout=60) as source, dest.open('xb') as target:
        assert source.status == 200
        while chunk := source.read(8 * 1024 * 1024):
            target.write(chunk)
            digest.update(chunk)
    assert dest.stat().st_size == entry['fileSize']
    assert digest.hexdigest() == entry['sha256sum']
    report = {'local_file': str(dest.relative_to(ROOT)), 'bytes': dest.stat().st_size, 'sha256': digest.hexdigest(), 'source': entry['url'], 'build': entry['build'], 'version': entry['version'], 'catalog_kernel': entry['kernel_versions']['kernel'], 'installed_on_target': False, 'copied_to_target': False, 'apple_native_pkg_signature': 'NOT_CHECKED_LOCAL_NIXOS_FILE_NOT_NATIVE_VERIFIED'}
    (ROOT / 'reports/KDK-PACKAGE.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: exact 25G83 KDK downloaded locally and SHA256 matched catalog; no target install')


if __name__ == '__main__':
    main()
