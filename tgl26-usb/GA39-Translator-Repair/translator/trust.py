"""Authenticate diagnostic inputs against the immutable GA38 seal, not callers."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for part in ['tools', 'ir']:
    sys.path.insert(0, str(ROOT / 'validator/ga38' / part))
from common import Rejected, sha
from integrity import validate_program

HISTORY = ROOT.parent / 'GA38-Shader-IR-Lab'
MANIFEST_SHA256 = 'db30c52513df69b6aede0cab767861de137ed669a26d88cbfee61ceddbe326f8'


def bounded(path, limit=16 << 20):
    with Path(path).open('rb') as f:
        raw = f.read(limit + 1)
    if len(raw) > limit:
        raise Rejected('INPUT_RESOURCE_BOUND', str(path))
    return raw


def manifest():
    raw = bounded(HISTORY / 'manifest.json')
    if sha(raw) != MANIFEST_SHA256:
        raise Rejected('BASELINE_MANIFEST_IDENTITY', str(HISTORY))
    return {x['path']: x for x in json.loads(raw)['files']}


def sealed_json(path, relative, entries):
    raw = bounded(path)
    # Validate derived flags first, to expose the exact corruption rather than
    # interpreting a digest mismatch as a new semantic result.
    obj = json.loads(raw)
    if relative.startswith('ir/outputs/'):
        validate_program(obj)
    if relative not in entries or sha(raw) != entries[relative]['sha256']:
        raise Rejected('BASELINE_EVIDENCE_IDENTITY', relative)
    return obj


def baseline_inputs(baseline, shader):
    entries = manifest()
    fixed = sealed_json(HISTORY / 'corpus/provenance.json', 'corpus/provenance.json', entries)
    program = next(p for p in fixed['programs'] if p['shader_id'] == shader)
    data = bounded(baseline / f'corpus/source/{shader}.bin', 1 << 20)
    if sha(data) != program['source']['sha256']:
        raise Rejected('SOURCE_IDENTITY', shader)
    source, target = [sealed_json(baseline / (p := f'ir/outputs/{shader}-{side}.json'), p, entries)
                      for side in ['source', 'candidate']]
    if source['program_sha256'] != sha(data) or target['program_sha256'] != program['candidate']['sha256']:
        raise Rejected('IR_IDENTITY', shader)
    comparison, schedule = [sealed_json(baseline / (p := f'validator/outputs/{shader}-{kind}.json'), p, entries)
                            for kind in ['comparison', 'schedule']]
    messages = [sealed_json(baseline / (p := f'ir/messages/{shader}-{side}.json'), p, entries)
                for side in ['source', 'candidate']]
    return data, source, target, comparison, schedule, messages, program
