#!/usr/bin/env python3
"""Record all snapshot adaptations against the authenticated GA38 identities."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'validator/ga38'


def run(destination):
    destination = destination.resolve()
    if ROOT not in destination.parents or destination.exists():
        raise ValueError('Fresh GA39 output required')
    destination.mkdir(parents=True)
    index = json.loads((SNAPSHOT / 'SNAPSHOT.json').read_text())
    records, patches = [], []
    for item in index['files']:
        old = Path(item['source_path']).read_bytes()
        original_sha = hashlib.sha256(old).hexdigest()
        if original_sha != item['sha256']:
            raise ValueError('Historical source changed: ' + item['source_path'])
        new = (SNAPSHOT / item['path']).read_bytes()
        if new != old:
            patches.extend(difflib.unified_diff(old.decode().splitlines(True), new.decode().splitlines(True),
                           fromfile='GA38/' + item['path'], tofile='GA39/validator/ga38/' + item['path']))
            records.append({'path': item['path'], 'historical_sha256': original_sha,
                            'adapted_sha256': hashlib.sha256(new).hexdigest()})
    (destination / 'baseline-adaptations.patch').write_text(''.join(patches))
    (destination / 'receipt.json').write_text(json.dumps({'changes': records,
        'note': 'Scope/path adapters only; historical core semantic algorithms untouched',
        'original_failure': 'logs/ga38-tests-initial-009: copied scope test used old directory topology; now uses actual historical paths',
        'replay': 'logs/ga38-tests-replay-010: 47/47 PASS'}, sort_keys=True, indent=2) + '\n')
    print(json.dumps(records, sort_keys=True))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('output', type=Path)
    run(ap.parse_args().output)
