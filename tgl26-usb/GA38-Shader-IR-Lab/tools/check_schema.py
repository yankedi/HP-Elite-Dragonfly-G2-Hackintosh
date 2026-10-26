#!/usr/bin/env python3
"""Targeted schema recheck; does not overwrite any previous analysis artifacts."""
import argparse
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from common import ROOT, dump, load, output_root, sha
sys.path.insert(0, str(ROOT / 'reference/python-deps'))
import jsonschema

ap = argparse.ArgumentParser()
ap.add_argument('--input', type=Path, required=True)
ap.add_argument('--receipt', type=Path, required=True)
args = ap.parse_args()
schema = load(ROOT / 'ir/schema.json')
jsonschema.Draft202012Validator.check_schema(schema)
files = []
for p in sorted(args.input.glob('*.json')):
    jsonschema.validate(load(p), schema)
    files.append({'path': str(p), 'sha256': sha(p.read_bytes())})
if not files:
    raise ValueError('No IR files selected')
receipt = output_root(args.receipt)
if receipt.exists():
    raise ValueError('Refuse to overwrite a schema receipt')
dump(receipt, {'status': 'PASS', 'validator': 'jsonschema==4.23.0', 'draft': '2020-12',
               'schema_sha256': sha((ROOT / 'ir/schema.json').read_bytes()), 'files': files})
print(f'PASS {len(files)} IR schema checks')
