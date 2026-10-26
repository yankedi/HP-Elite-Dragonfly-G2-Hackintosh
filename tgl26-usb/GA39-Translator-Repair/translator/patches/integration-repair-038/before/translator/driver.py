#!/usr/bin/env python3
"""Default-Strict facade around a separately built, offline research generator.

Strict refuses unproved whole shaders. Research is explicit and tagged, with
fresh decode/roundtrip/GA38 revalidation. No device or deployment backend exists.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT39 = Path(__file__).resolve().parents[1]
BASE = ROOT39 / 'validator/ga38'
for part in ['tools', 'corpus', 'ir', 'dependency', 'validator']:
    sys.path.insert(0, str(BASE / part))
from common import Rejected, dump, load, output_root, sha
from validate_candidate import run as validate_candidate
from integrity import validate_program
sys.path.insert(0, str(ROOT39 / 'translator'))
from translate_unit import invoke
spec = importlib.util.spec_from_file_location('ga39_closed_policy', ROOT39 / 'translator/strict-policy/policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def native_generator():
    """Installed only after the independent source/build receipt is integrated."""
    config = load(ROOT39 / 'translator/research-mode/generator.json')
    binary = output_root(ROOT39 / config['path'])
    if sha(binary.read_bytes()) != config['sha256']:
        raise Rejected('NATIVE_GENERATOR_HASH', str(binary))
    return binary, config


def run(shader, destination, mode='strict', baseline=None):
    if mode not in {'strict', 'research'}:
        raise Rejected('MODE_INVALID', str(mode))
    if shader not in {'PS0', 'PS-KP1', 'PS-KP2', 'VS'}:
        raise Rejected('SHADER_UNSUPPORTED', shader)
    destination = output_root(Path(destination))
    if destination.exists():
        raise Rejected('OUTPUT_EXISTS', str(destination))
    baseline = baseline or ROOT39 / 'candidates/baseline/replay-003'
    provenance = load(baseline / 'corpus/provenance.json')
    program = next(p for p in provenance['programs'] if p['shader_id'] == shader)
    # Compare against immutable GA38 corpus identities; caller JSON cannot certify bytes.
    frozen = load(ROOT39.parent / 'GA38-Shader-IR-Lab/corpus/provenance.json')
    fixed = next(p for p in frozen['programs'] if p['shader_id'] == shader)
    data = (baseline / program['source']['path']).read_bytes()
    if sha(data) != fixed['source']['sha256']:
        raise Rejected('SOURCE_IDENTITY', shader)
    source, candidate = [load(baseline / f'ir/outputs/{shader}-{side}.json') for side in ['source', 'candidate']]
    # The copied baseline integrity API rejects altered derived fields as well as bytes.
    validate_program(source)
    validate_program(candidate)
    if source['program_sha256'] != sha(data) or candidate['program_sha256'] != fixed['candidate']['sha256']:
        raise Rejected('IR_IDENTITY', shader)
    comparison = load(baseline / f'validator/outputs/{shader}-comparison.json')
    schedule = load(baseline / f'validator/outputs/{shader}-schedule.json')
    report = policy.preflight(source, candidate, comparison, schedule)
    report['mode'] = mode
    destination.mkdir(parents=True)
    (destination / 'source.bin').write_bytes(data)
    begin = time.monotonic()
    if mode == 'research':
        binary, identity = native_generator()
        work = destination / 'research-NOT_FOR_HARDWARE'
        work.mkdir()
        (work / 'NOT_FOR_HARDWARE.txt').write_text('UNPROVEN OFFLINE RESEARCH CANDIDATE; NEVER DEPLOY\n')
        output = work / 'candidate.NOT_FOR_HARDWARE.bin'
        cmd = [str(binary), 'xlate', str(destination / 'source.bin'), str(output)]
        p = subprocess.run(cmd, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), capture_output=True, timeout=30)
        (work / 'stdout.txt').write_bytes(p.stdout)
        (work / 'stderr.txt').write_bytes(p.stderr)
        dump(work / 'generation.json', {'command': cmd, 'exit': p.returncode, 'generator': identity,
             'source_sha256': sha(data), 'stdout_sha256': sha(p.stdout), 'stderr_sha256': sha(p.stderr)})
        if p.returncode or not output.is_file():
            raise Rejected('RESEARCH_GENERATOR_FAILURE', shader)
        raw = output.read_bytes()
        review = validate_candidate(shader, output, None, work / 'ga38-review')
        text = invoke(['-d', '-p=12p1', output], work / 'roundtrip/decode').stdout
        with tempfile.TemporaryDirectory(prefix='roundtrip-', dir=work) as temp:
            asm, reencoded = Path(temp) / 'target.asm', Path(temp) / 'roundtrip.bin'
            asm.write_bytes(text)
            invoke(['-a', '-p=12p1', asm, '-o', reencoded], work / 'roundtrip/encode')
            if reencoded.read_bytes() != raw:
                raise Rejected('RESEARCH_ROUNDTRIP_BYTES_DIFFER', shader)
        report.update(research_candidate_sha256=sha(raw), research_candidate_bytes=len(raw),
                      research_only=True, full_shader_emitted=True, verified_executable_program_emitted=False,
                      research_program_generated=True, candidate_equivalence_proven=False,
                      baseline_bytes_unchanged=sha(raw) == fixed['candidate']['sha256'],
                      fresh_ga38_comparison_counts=review['counts'])
    report['elapsed_seconds'] = time.monotonic() - begin
    dump(destination / 'report.json', report)
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--shader', required=True, choices=['PS0', 'PS-KP1', 'PS-KP2', 'VS'])
    ap.add_argument('--mode', choices=['strict', 'research'], default='strict')
    ap.add_argument('--output', required=True, type=Path)
    a = ap.parse_args()
    try:
        report = run(a.shader, a.output, a.mode)
        print(json.dumps({'status': report['status'], 'mode': report['mode'], 'full_shader_emitted': report['full_shader_emitted']}))
        raise SystemExit(0 if a.mode == 'research' else 2)
    except Rejected as e:
        print(json.dumps(e.as_dict(), sort_keys=True))
        raise SystemExit(2)
