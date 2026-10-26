#!/usr/bin/env python3
"""Reproducible offline pipeline; every output must stay inside the new GA38 lab."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
from common import ROOT, dump, load, output_root, sha
for sub in ['corpus', 'ir', 'dependency', 'validator']:
    sys.path.insert(0, str(ROOT / sub))
from corpus import authenticated, extract, historical_file
from iga_adapter import decode
from semantic_ir import build_program
from dependency_graph import build_graph
from message_ir import build_messages
from gen12_schedule_check import check
from compare_program import compare
from mapping import archived_witness


def run(destination):
    destination = output_root(destination)
    provenance = extract(destination)
    summary = {'schema_version': 1, 'programs': [], 'hardware_validated': False}
    for prog in provenance['programs']:
        ident = prog['shader_id']
        record = {'shader_id': ident}
        programs, graphs, messages = {}, {}, {}
        for side in ['source', 'candidate']:
            info = prog[side]
            data = authenticated(destination / info['path'], info['sha256'])
            decoded = decode(data, info['platform'], destination / f'logs/decode/{ident}/{side}')
            ir = build_program(ident, data, decoded, prog['eu_window_offset'] if side == 'source' else None)
            graph = build_graph(ir)
            message = build_messages(ir)
            dump(destination / f'ir/outputs/{ident}-{side}.json', ir)
            dump(destination / f'dependency/graphs/{ident}-{side}.json', graph)
            dump(destination / f'ir/messages/{ident}-{side}.json', message)
            programs[side], graphs[side], messages[side] = ir, graph, message
            record[side] = {'sha256': info['sha256'], 'instructions': len(ir['nodes']),
                            'graph_edges': len(graph['edges']), 'unknown_edges': graph['unknown_dependency_count']}
        schedule = check(programs['candidate'], graphs['candidate'])
        dump(destination / f'validator/outputs/{ident}-schedule.json', schedule)
        witness = archived_witness(prog, programs['candidate'])
        review = compare(programs['source'], programs['candidate'], witness, graphs['source'], graphs['candidate'],
                         schedule, messages['source'], messages['candidate'])
        dump(destination / f'validator/outputs/{ident}-comparison.json', review)
        record['message_count'] = len(messages['source']['messages'])
        record['schedule'] = schedule['counts']
        record['comparison'] = review['counts']
        summary['programs'].append(record)
    dump(destination / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, default=ROOT)
    args = ap.parse_args()
    result = run(args.output)
    print('source_nodes=' + str(sum(p['source']['instructions'] for p in result['programs'])))
    print('candidate_nodes=' + str(sum(p['candidate']['instructions'] for p in result['programs'])))
