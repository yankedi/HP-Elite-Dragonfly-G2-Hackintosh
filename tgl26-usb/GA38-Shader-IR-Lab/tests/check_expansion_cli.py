#!/usr/bin/env python3
"""Actual unequal-count CLI case with a hand-authored one-to-many witness."""
from pathlib import Path
import os
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
for sub in ['tools', 'ir']:
    sys.path.insert(0, str(ROOT / sub))
from common import dump, load, output_root, sha, write_bytes
from iga_adapter import verify_iga
from run_checks import command

destination = output_root(Path(sys.argv[1]))
destination.mkdir(parents=True, exist_ok=False)
binary = ROOT.parent / 'GA32-ISA-Lab/tools/iga/build/IGAExe/iga64'
tool = verify_iga(binary)
asm = destination / 'prefix.asm'
write_bytes(asm, b'(W) sync.nop (1|M0) null\n')
env = {k: v for k, v in os.environ.items() if k not in {'LD_PRELOAD', 'LD_AUDIT', 'LD_LIBRARY_PATH'}}
env['LD_LIBRARY_PATH'] = str(Path(tool['library_path']).parent)
args = [str(binary), '-a', '-p=12p1', str(asm), '-o', str(destination / 'prefix.bin')]
proc = subprocess.run(args, capture_output=True, env=env, timeout=30)
write_bytes(destination / 'assemble.stdout', proc.stdout)
write_bytes(destination / 'assemble.stderr', proc.stderr)
dump(destination / 'assemble-receipt.json', {'command': args, 'exit': proc.returncode,
    'input_sha256': sha(asm.read_bytes()), 'stdout_sha256': sha(proc.stdout), 'stderr_sha256': sha(proc.stderr), 'tool': tool})
assert proc.returncode == 0, proc.stderr
prefix = (destination / 'prefix.bin').read_bytes()
assert len(prefix) == 16, 'Fixture requires one native SYNC'
original = (ROOT / 'corpus/candidate/PS0.bin').read_bytes()
candidate = destination / 'expanded-candidate.bin'
write_bytes(candidate, prefix + original)
# Hand-derived from the frozen PS0 PC table, not produced by the parser under test.
pairs = [(0, 0, 32), (16, 32, 48), (32, 48, 64), (48, 64, 80), (64, 80, 96),
         (80, 96, 112), (96, 112, 128), (112, 128, 136), (120, 136, 144),
         (128, 144, 152), (136, 152, 168)]
mapping = destination / 'mapping.json'
dump(mapping, [{'source_offset': s, 'target_byte_range': [lo, hi]} for s, lo, hi in pairs])
for label, witness in [('mapped', mapping), ('unmapped', None)]:
    args = [sys.executable, '-B', str(ROOT / 'tools/validate_candidate.py'), '--shader', 'PS0',
            '--candidate', str(candidate), '--output', str(destination / label)]
    if witness is not None:
        args.extend(['--mapping', str(witness)])
    command(args, destination / f'logs/{label}')
    src = load(destination / label / 'analysis/source-ir.json')
    tgt = load(destination / label / 'analysis/candidate-ir.json')
    review = load(destination / label / 'analysis/comparison.json')
    assert len(src['nodes']) == 11 and len(tgt['nodes']) == 12
    if label == 'mapped':
        assert review['mapping_failure'] is None
        assert review['findings'][0]['target_offsets'] == [0, 16]
    else:
        assert review['mapping_failure'] is not None
        assert len(review['unmapped_target_offsets']) == 12
        assert all(f['status'] == 'UNKNOWN' for f in review['findings'])
dump(destination / 'results.json', {'status': 'PASS', 'source_nodes': 11, 'target_nodes': 12,
    'explicit_one_to_many': 'source+0 -> target[0,32) (SYNC plus MAD)',
    'unknown_without_witness': 'all source layers UNKNOWN and all 12 target offsets explicitly unmapped',
    'candidate_sha256': sha(candidate.read_bytes()), 'mapping_sha256': sha(mapping.read_bytes()),
    'hardware_validated': False})
print('PASS actual 11-to-12 instruction CLI, explicit one-to-many and absent-witness UNKNOWN')
