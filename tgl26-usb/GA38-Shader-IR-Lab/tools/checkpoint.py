#!/usr/bin/env python3
"""Capture a non-overwriting source checkpoint before audit-driven repair."""
import argparse
from pathlib import Path
import shutil

from common import ROOT, dump, output_root, sha

ap = argparse.ArgumentParser()
ap.add_argument('--output', type=Path, required=True)
args = ap.parse_args()
destination = output_root(args.output)
destination.mkdir(parents=True, exist_ok=False)
captured = []
for directory in ['tools', 'corpus', 'ir', 'dependency', 'validator', 'tests']:
    for source in sorted((ROOT / directory).rglob('*.py')):
        if any(p in {'__pycache__', 'historical-regression', 'oracles', 'mutants'} for p in source.parts):
            continue
        relative = source.relative_to(ROOT)
        data = source.read_bytes()
        target = destination / 'source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        captured.append({'path': str(relative), 'sha256': sha(data), 'bytes': len(data)})
for relative in ['ir/schema.json', 'state.json', 'history.json', 'continuation.md']:
    data = (ROOT / relative).read_bytes()
    target = destination / 'source' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    captured.append({'path': relative, 'sha256': sha(data), 'bytes': len(data)})
dump(destination / 'SOURCE-CHECKPOINT.json', {'files': captured,
     'scope': 'Exact selected source/state bytes. Dependencies, native tools and original run outputs remain at their evidence paths; not a standalone historical environment image.'})
print(f'PASS {len(captured)} exact source/state captures')
