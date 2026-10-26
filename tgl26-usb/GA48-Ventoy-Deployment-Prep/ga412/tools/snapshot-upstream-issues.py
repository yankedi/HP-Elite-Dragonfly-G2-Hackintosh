#!/usr/bin/env python3
"""Archive public issue/source bytes for offline analysis. No write APIs or SSH."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

REPO = 'JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe'
BLITFIX = 'df7ab78f79d08a8a792292982b46d2bcf110f052'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    if args.report.exists():
        raise FileExistsError(args.report)
    entries = []

    def fetch(url, name):
        request = urllib.request.Request(url, headers={'User-Agent': 'GA412-offline-evidence',
                                                       'Accept': 'application/vnd.github+json' if 'api.github.com' in url else '*/*'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
                status = response.status
                etag = response.headers.get('ETag')
        except (OSError, urllib.error.URLError) as error:
            entries.append({'url': url, 'error': str(error), 'retried': False})
            return None
        with (args.directory / name).open('xb') as stream:
            stream.write(data)
        entries.append({'url': url, 'path': str(args.directory / name), 'status': status,
                        'retrieved_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'etag': etag})
        return data

    fetch(f'https://api.github.com/repos/{REPO}/issues?state=all&per_page=10&sort=updated&direction=desc', 'issues.json')
    for number in [2, 3, 4, 5, 6]:
        fetch(f'https://api.github.com/repos/{REPO}/issues/{number}/comments?per_page=10', f'issue-{number}-comments.json')
    fetch(f'https://api.github.com/repos/{REPO}/commits/{BLITFIX}', 'blitfix-commit.json')
    fetch(f'https://raw.githubusercontent.com/{REPO}/{BLITFIX}/src/NootedGreen/kern_gen11.cpp', 'blitfix-kern_gen11.cpp')
    ref = fetch('https://api.github.com/repos/intel/gmmlib/git/ref/heads/master', 'gmmlib-ref.json')
    sha = json.loads(ref)['object']['sha'] if ref else None
    if sha:
        for name in ['CpuSwizzleBlt.c', 'assert.h']:
            fetch(f'https://raw.githubusercontent.com/intel/gmmlib/{sha}/Source/GmmLib/Utility/CpuSwizzleBlt/{name}', name)
    report = {'purpose': 'Public claims/source snapshots, not HP validation',
              'repository': REPO, 'fixed_HP_upstream_unchanged': '6a1afb337d1fb1ff07ca032b5c1868fe2bd005ef',
              'new_public_candidate_commit': BLITFIX, 'gmmlib_commit': sha,
              'entries': entries, 'public_write_operations': 0, 'SSH_operations': 0}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps({'fetched': sum('sha256' in e for e in entries),
                      'errors': sum('error' in e for e in entries), 'gmmlib_commit': sha}))


if __name__ == '__main__':
    main()
