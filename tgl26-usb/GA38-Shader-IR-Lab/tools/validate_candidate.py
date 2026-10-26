#!/usr/bin/env python3
"""Analyze an offline candidate with an optional explicit one-to-many witness.

Unknown correspondence is retained. No instruction-count zip is inferred.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from common import ROOT, Rejected, dump, load, output_root, sha, write_bytes
for sub in ['corpus', 'ir', 'dependency', 'validator']:
    sys.path.insert(0, str(ROOT / sub))
from corpus import extract, authenticated
from iga_adapter import decode
from semantic_ir import build_program
from message_ir import build_messages
from dependency_graph import build_graph
from gen12_schedule_check import check
from compare_program import compare
from mapping import archived_witness


def run(shader, candidate_path, mapping_path, destination):
    destination = output_root(destination)
    if destination.exists():
        raise Rejected('OUTPUT_EXISTS', 'A candidate review requires a fresh output directory')
    candidate_path = output_root(candidate_path)
    if not candidate_path.is_file() or candidate_path.stat().st_size > 1 << 20:
        raise Rejected('CANDIDATE_INPUT', 'Expected an ordinary candidate file of at most 1MiB inside GA38')
    candidate_bytes = candidate_path.read_bytes()
    provenance = extract(destination)
    prog = next(p for p in provenance['programs'] if p['shader_id'] == shader)
    source_bytes = authenticated(destination / prog['source']['path'], prog['source']['sha256'])
    write_bytes(destination / 'input/candidate.bin', candidate_bytes)
    dump(destination / 'input/provenance.json', {'source': prog['source'],
         'candidate': {'original_path': str(candidate_path), 'sha256': sha(candidate_bytes), 'bytes': len(candidate_bytes)},
         'historical_candidates_scope': 'Baseline files copied for provenance; reviewed target is input/candidate.bin',
         'hardware_validated': False})
    programs, graphs, messages = {}, {}, {}
    for side, raw, platform in [('source', source_bytes, '11'), ('candidate', candidate_bytes, '12p1')]:
        decoded = decode(raw, platform, destination / f'logs/decode/{side}')
        programs[side] = build_program(shader, raw, decoded, prog['eu_window_offset'] if side == 'source' else None)
        graphs[side] = build_graph(programs[side])
        messages[side] = build_messages(programs[side])
        dump(destination / f'analysis/{side}-ir.json', programs[side])
        dump(destination / f'analysis/{side}-graph.json', graphs[side])
        dump(destination / f'analysis/{side}-messages.json', messages[side])
    schedule = check(programs['candidate'], graphs['candidate'])
    if mapping_path is None:
        witness = archived_witness(prog, programs['candidate'])
    else:
        mapping_path = output_root(mapping_path)
        supplied = load(mapping_path)
        witness = {'state': 'EXPLICIT_CALLER_LAYOUT_HYPOTHESIS',
                   'source_sha256': programs['source']['program_sha256'],
                   'candidate_sha256': programs['candidate']['program_sha256'],
                   'evidence_path': str(mapping_path), 'evidence_sha256': sha(mapping_path.read_bytes()),
                   'scope': 'Caller correspondence validated geometrically, never used as a semantic oracle',
                   **({'entries': supplied} if isinstance(supplied, list) else supplied)}
    comparison = compare(programs['source'], programs['candidate'], witness, graphs['source'], graphs['candidate'],
                         schedule, messages['source'], messages['candidate'])
    dump(destination / 'analysis/schedule.json', schedule)
    dump(destination / 'analysis/comparison.json', comparison)
    return comparison


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--shader', choices=['PS0', 'PS-KP1', 'PS-KP2', 'VS'], required=True)
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--mapping', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    result = run(args.shader, args.candidate, args.mapping, args.output)
    print(result['counts'])
