#!/usr/bin/env python3
"""Authenticated GA38 code snapshot. Never writes into the historical tree."""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / 'GA38-Shader-IR-Lab'
EXPECTED = 'db30c52513df69b6aede0cab767861de137ed669a26d88cbfee61ceddbe326f8'


def main():
    raw = (SOURCE / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED:
        raise ValueError('GA38 manifest identity mismatch')
    destination = ROOT / 'validator/ga38'
    if destination.exists():
        raise ValueError('Existing snapshot preserved')
    records = []
    for entry in json.loads(raw)['files']:
        p = Path(entry['path'])
        include = (p.parts[0] in {'tools', 'corpus', 'ir', 'dependency', 'validator'}
                   and (p.suffix in {'.py', '.json'} and len(p.parts) <= 3)
                   and not any(x in p.parts for x in {'outputs', 'messages', 'graphs'}))
        include |= (p.parts[0] == 'tests' and len(p.parts) == 2 and p.suffix == '.py')
        include |= p.as_posix() in {'reference/inventory/PROVENANCE.json', 'reference/rules/RULES.json'}
        include |= p.parts[:2] == ('tests', 'oracles') and p.suffix == '.json'
        if not include or entry['kind'] != 'file':
            continue
        data = (SOURCE / p).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('GA38 source mismatch: ' + str(p))
        target = destination / p
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        records.append({'path': str(p), 'source_path': str(SOURCE / p), 'sha256': entry['sha256']})
    receipt = {'source_manifest_sha256': EXPECTED, 'files': records,
               'scope': 'Authenticated code/reference snapshot before path-only integration adaptations',
               'hardware_validated': False}
    (destination / 'SNAPSHOT.json').write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'files': len(records), 'destination': str(destination)}))


if __name__ == '__main__':
    main()
