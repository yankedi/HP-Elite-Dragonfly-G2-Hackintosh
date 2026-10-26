#!/usr/bin/env python3
"""Publish verified canonical outputs after archiving every prior output byte."""
from pathlib import Path
import argparse
import sys

sys.dont_write_bytecode = True
from common import ROOT, dump, output_root, sha, write_bytes
from run_checks import normalized_outputs


def publish(run, archive):
    run, archive = output_root(run), output_root(archive)
    if (ROOT / 'manifest.json').exists():
        raise ValueError('Refuse to change a sealed delivery')
    archive.mkdir(parents=True, exist_ok=False)
    # Enumeration also checks all normalized report outputs; actual files are
    # copied byte-exact, including their original run provenance paths.
    paths = sorted(normalized_outputs(run))
    previous, current = [], []
    for relative in paths:
        destination = output_root(ROOT / relative)
        if destination.exists():
            raw = destination.read_bytes()
            write_bytes(archive / 'previous' / relative, raw)
            previous.append({'path': relative, 'sha256': sha(raw), 'bytes': len(raw)})
        data = (run / relative).read_bytes()
        write_bytes(destination, data)
        current.append({'path': relative, 'sha256': sha(data), 'bytes': len(data)})
    dump(archive / 'receipt.json', {'source_run': str(run.relative_to(ROOT)),
        'archived_previous_outputs': previous, 'published': current,
        'decode_logs': str((run / 'logs/decode').relative_to(ROOT)),
        'scope': 'Only canonical derived artifacts; old outputs preserved byte-for-byte, code/history/seals untouched'})
    print(f'Published {len(current)} artifacts; archived {len(previous)} prior outputs')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--archive', type=Path, required=True)
    args = ap.parse_args()
    publish(args.run, args.archive)
