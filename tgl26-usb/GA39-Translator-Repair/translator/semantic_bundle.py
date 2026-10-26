"""Join independent analyses without turning evidence presence into acceptance."""
from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def build(source, target, source_messages, target_messages, witness):
    lower = module('ga39_lower', 'numeric/proofs/lowering.py')
    scratch = module('ga39_scratch', 'numeric/scratch-liveness/liveness.py')
    debug = module('ga39_debug', 'debug/switch-elimination/guard.py')
    scheduling = module('ga39_completion', 'scheduling/completion.py')
    fields = module('ga39_send_fields', 'messages/field_mapping.py')
    if source['program_sha256'] != witness.get('source_sha256') or target['program_sha256'] != witness.get('candidate_sha256'):
        raise ValueError('Semantic bundle mapping identity mismatch')
    mapping = {}
    for entry in witness.get('entries', []):
        lo, hi = entry['target_byte_range']
        for node in target['nodes']:
            pc, end = node['byte_range']
            if lo <= pc and end <= hi:
                if pc in mapping:
                    raise ValueError('Duplicate target mapping')
                mapping[pc] = entry['source_offset']
    # Numeric proof builder independently enforces complete, disjoint framing.
    proofs = lower.prove(source, target, witness)
    replacements = sorted({r['temporary_grf'] for p in proofs['proofs'] for r in p['operand_replacements']})
    scratches = [scratch.scratch_contract(source, target, register, mapping) for register in replacements]
    return {'schema': 'ga39-semantic-bundle/v1', 'shader_id': source['shader_id'],
            'source_sha256': source['program_sha256'], 'target_sha256': target['program_sha256'],
            'nf_acc': proofs, 'source_liveness': scratch.analyze(source),
            'target_liveness': scratch.analyze(target), 'scratch_contracts': scratches,
            'debug_switch': debug.audit(source, target, witness),
            'completion': scheduling.build_obligations(target, target_messages),
            'send_fields': fields.field_contracts(source_messages, target_messages, source, target),
            'strict_status': 'UNKNOWN_REJECTED', 'accepted_program': False,
            'hardware_validated': False,
            'note': 'Field encoding checks, register projections and compiler rules do not discharge NF, resource ABI or message hardware completion'}
