"""Regression models for independent findings, with explicit synthetic scope.

These post-decode IR unit fixtures are NOT valid EU executables and never claim
native/GPU validation. Real-byte mutations and unequal-count CLI tests are
separate evidence. Expected statuses come from independent review R3/R4/R5.
"""
from dataclasses import asdict
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
for sub in ['tools', 'ir', 'dependency', 'validator']:
    sys.path.insert(0, str(ROOT / sub))
from common import Rejected, sha
from semantic_ir import make_instruction
from dependency_graph import build_graph
from message_ir import build_messages
from gen12_schedule_check import check
from compare_program import compare, validate_mapping


def model(decoded):
    raw = bytes(16)
    node = make_instruction('SYNTHETIC_MODEL', raw, '12p1', decoded, 0, 16, None,
                            {'tool': {'scope': 'synthetic post-decode model; not native bytes'},
                             'iga_json_sha256': '0' * 64}).as_dict()
    return {'schema_version': 1, 'shader_id': 'SYNTHETIC_MODEL', 'platform': '12p1',
            'program_sha256': sha(raw), 'byte_length': 16, 'nodes': [node],
            'coverage': 'synthetic unit, not full shader', 'hardware_validated': False}


def compare_models(source, target):
    sg, tg = build_graph(source), build_graph(target)
    witness = {'source_sha256': source['program_sha256'], 'candidate_sha256': target['program_sha256'],
               'entries': [{'source_offset': 0, 'target_byte_range': [0, 16]}]}
    reviewed = compare(source, target, witness, sg, tg, check(target, tg), build_messages(source), build_messages(target))
    return {f['layer']: f for f in reviewed['findings']}


def mov(**extra):
    return {'pc': 0, 'op': 'mov', 'es': 1, 'wren': True,
            'dst': {'kind': 'RD', 'reg': {'rn': 'r', 'r': 5}, 'rgn': {'h': 1}, 'type': 'ud'},
            'srcs': [{'kind': 'IM', 'value': '0x0', 'type': 'ud'}], **extra}


class IndependentReviewRegressions(unittest.TestCase):
    def test_r3_integer_dw_mul_implicit_acc_is_not_none(self):
        d = {'pc': 0, 'op': 'mul', 'es': 8, 'wren': True,
             'dst': {'kind': 'RD', 'reg': {'rn': 'r', 'r': 5}, 'rgn': {'h': 1}, 'type': 'ud'},
             'srcs': [{'kind': 'RD', 'reg': {'rn': 'r', 'r': r}, 'rgn': {'v': 8, 'w': 8, 'h': 1}, 'type': 'ud'} for r in [6, 7]]}
        p = model(d)
        writes = [a for a in p['nodes'][0]['register_access']['accesses'] if a['file'] == 'ACC' and a['mode'] == 'WRITE']
        self.assertTrue(writes)
        self.assertEqual(writes[0]['state'], 'UNKNOWN')
        fs = compare_models(p, model(d))
        for layer in ['accumulator_nf', 'register_dependency']:
            self.assertEqual(fs[layer]['status'], 'UNKNOWN')

    def test_r4_target_only_switch_does_not_pass(self):
        fs = compare_models(model(mov()), model(mov(opts=['Switch'])))
        for layer in ['opcode_math', 'operands_registers', 'predicate_mask', 'register_dependency']:
            self.assertEqual(fs[layer]['status'], 'UNKNOWN')

    def test_r5_zero_regdist_is_unknown_not_index_error(self):
        p = model(mov(regDist='@0'))
        result = check(p, build_graph(p))
        self.assertTrue(any(c['status'] == 'UNKNOWN' and c['rule'] == 'GEN12-SWSB-ENCODING'
                            for c in result['constraints']))

    def test_r5_bad_sbid_shape_is_unknown_not_type_error(self):
        p = model(mov(sbid='not-an-IGA-token-object'))
        self.assertTrue(any(c['status'] == 'UNKNOWN' for c in check(p, build_graph(p))['constraints']))

    def test_r6_zero_constraints_no_positive_schedule_claim(self):
        f = compare_models(model(mov()), model(mov()))['swsb_sbid']
        self.assertEqual(f['status'], 'UNKNOWN')
        self.assertIn('No local schedule constraint', f['detail'])

    def test_r7_malformed_witness_is_structured_rejection(self):
        p = model(mov())
        for witness in [None, [], {}, {'entries': [{'source_offset': []}]},
                        {'source_sha256': p['program_sha256'], 'candidate_sha256': p['program_sha256'],
                         'entries': [{'source_offset': 0, 'target_byte_range': ['zero', 16]}]}]:
            with self.assertRaises(Rejected):
                validate_mapping(p, p, witness)


if __name__ == '__main__':
    unittest.main(verbosity=2)
