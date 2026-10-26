"""Explicit correspondence witnesses, independent of instruction-count equality."""
import json

from common import sha
from corpus import historical_file


def archived_witness(prog, candidate):
    path, raw = historical_file('analysis/upstream-semantic-review.json')
    witness = {'state': 'LAYOUT_CORRESPONDENCE_HYPOTHESIS',
               'source_sha256': prog['source']['sha256'], 'candidate_sha256': candidate['program_sha256'],
               'evidence_path': str(path), 'evidence_sha256': sha(raw),
               'scope': 'Archived byte-anchored layout witness, not semantic equivalence', 'entries': []}
    previous = next((p for p in json.loads(raw) if p.get('name') == prog['historical_name']), None)
    if previous is None or previous.get('sha256') != candidate['program_sha256']:
        return {**witness, 'unresolved_reason': 'No archived correspondence for this actual candidate identity'}
    ends = {n['byte_range'][0]: n['byte_range'][1] for n in candidate['nodes']}
    for item in previous.get('mapping', []):
        source_pc, target_pc = item.get('source_offset'), item.get('target_offset')
        if type(source_pc) is not int or type(target_pc) is not int or target_pc not in ends:
            return {**witness, 'entries': [], 'unresolved_reason': 'Archived layout does not match the actual decoded instruction boundaries'}
        witness['entries'].append({'source_offset': source_pc, 'target_byte_range': [target_pc, ends[target_pc]]})
    return witness
