#!/usr/bin/env python3
"""Run actual subprocess checks with immutable per-attempt command/hash receipts."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
from common import ROOT, dump, load, output_root, sha


def code_identity():
    return {str(p.relative_to(ROOT)): sha(p.read_bytes()) for directory in ['tools', 'corpus', 'ir', 'dependency', 'validator', 'tests']
            for p in sorted((ROOT / directory).rglob('*.py')) if '__pycache__' not in p.parts}


def command(args, folder, env=None):
    folder = output_root(folder)
    folder.mkdir(parents=True, exist_ok=False)
    proc = subprocess.run(args, capture_output=True, cwd=ROOT, timeout=300,
                          env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', **(env or {})})
    (folder / 'stdout.txt').write_bytes(proc.stdout)
    (folder / 'stderr.txt').write_bytes(proc.stderr)
    receipt = {'command': args, 'exit': proc.returncode, 'python_version': sys.version,
               'code_sha256': code_identity(), 'stdout_sha256': sha(proc.stdout), 'stderr_sha256': sha(proc.stderr)}
    dump(folder / 'receipt.json', receipt)
    if proc.returncode:
        raise RuntimeError(f'Command failed ({proc.returncode}); preserved {folder}')
    return receipt


def normalized_outputs(directory):
    # Exact deterministic content, not just instruction count. Invocation logs
    # contain the intentionally distinct fresh output directories and are kept
    # as raw evidence but not part of the reproducibility equivalence relation.
    artifacts = {str(p.relative_to(directory)): sha(p.read_bytes())
            for sub in ['corpus', 'ir', 'dependency', 'validator']
            for p in sorted((directory / sub).rglob('*')) if p.is_file() and p.suffix in {'.json', '.bin'}} | {
                'summary.json': sha((directory / 'summary.json').read_bytes())}
    for p in sorted((directory / 'reports').glob('*.md')):
        # Reports cite their originating fresh-run path. Only that provenance
        # prefix is normalized; all findings/offsets/counts/text remain exact.
        normalized = p.read_bytes().replace(str(directory.relative_to(ROOT)).encode(), b'<ANALYSIS_ROOT>')
        artifacts[str(p.relative_to(directory))] = sha(normalized)
    return artifacts


def run(root):
    root = output_root(root)
    root.mkdir(parents=True, exist_ok=False)
    for name in ['clean-a', 'clean-b']:
        dest = root / name
        command([sys.executable, '-B', str(ROOT / 'tools/analyze.py'), '--output', str(dest)], root / f'logs/{name}')
        command([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'), '-p', 'test_*.py', '-v'],
                root / f'logs/tests-{name}', {'GA38_RUN': str(dest)})
        command([sys.executable, '-B', str(ROOT / 'tools/render_reports.py'), '--run', str(dest),
                 '--output', str(dest / 'reports')], root / f'logs/reports-{name}')
    a, b = normalized_outputs(root / 'clean-a'), normalized_outputs(root / 'clean-b')
    differences = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    schema_result = 'NOT_RUN'
    sys.path.insert(0, str(ROOT / 'reference/python-deps'))
    try:
        import jsonschema
    except ImportError:
        schema_result = 'UNAVAILABLE_JSONSCHEMA'
    else:
        schema = load(ROOT / 'ir/schema.json')
        for p in (root / 'clean-a/ir/outputs').glob('*.json'):
            jsonschema.validate(load(p), schema)
        schema_result = 'PASS'
    result = {'status': 'PASS' if not differences and schema_result == 'PASS' else 'FAIL',
              'deterministic_files': len(a), 'first_output_sha256': a, 'second_output_sha256': b,
              'differences': differences, 'schema_validation': schema_result, 'code_identity': code_identity(),
              'scope': 'Python analyzer plus actual pinned native IGA calls; does not instrument Python with ASan'}
    dump(root / 'results.json', result)
    if result['status'] != 'PASS':
        raise RuntimeError(f"Verification failed: differences={differences}, schema={schema_result}; see {root / 'results.json'}")
    print(f"PASS {len(a)} deterministic artifacts, two fresh directories, schema {schema_result}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    run(args.output)
