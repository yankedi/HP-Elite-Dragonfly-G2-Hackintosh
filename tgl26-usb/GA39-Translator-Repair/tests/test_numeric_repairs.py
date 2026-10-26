"""Regressions for independently observed A1-A8; no NF semantics invented."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


live = module('live_repair', 'numeric/scratch-liveness/liveness.py')
policy = module('policy_repair', 'translator/strict-policy/policy.py')


def access(mode, file='GRF', state='KNOWN'):
    return {'file': file, 'mode': mode, 'state': state, 'condition': 'all instruction channels execute',
            'role': 'TEST', 'elements': [{'byte_start': 32, 'byte_end': 36, 'lane': 0}] if state == 'KNOWN' else None}


def program(row, fields=None):
    node = {'byte_range': [0, 16], 'raw_hex': '00' * 16, 'register_access': {'accesses': row}}
    if fields is not None:
        node['iga_fields'] = fields
    return {'shader_id': 'SYNTHETIC', 'program_sha256': 'synthetic', 'nodes': [node]}


class NumericRepairs(unittest.TestCase):
    def test_missing_or_masked_execution_evidence_cannot_kill(self):
        for fields in [None, {}, {'wren': False, 'pred': None, 'es': 8},
                       {'wren': True, 'pred': {'ctrl': '+'}, 'es': 8}]:
            p = program([access('WRITE')], fields)
            result = live.analyze(p, range(32, 36))
            self.assertEqual(result['records'][0]['must_kill'], [])
            self.assertEqual(result['records'][0]['live_before'], [[32, 36]])
        p = program([access('WRITE')], {'wren': True, 'pred': None, 'es': 8})
        self.assertEqual(live.analyze(p, range(32, 36))['records'][0]['must_kill'], [[32, 36]])

    def test_target_only_any_is_a_blocking_obligation(self):
        s, t = program([]), program([access('READ', 'ANY', 'UNKNOWN')])
        result = live.scratch_contract(s, t, 1, {0: 0})
        self.assertIn('SYMBOLIC_OR_INDIRECT_GRF_ACCESS', result['unmet_obligations'])
        self.assertEqual(result['allocation_status'], 'UNKNOWN_REJECTED')

    def test_read_modify_write_cannot_reach_itself(self):
        result = live.scratch_contract(program([]), program([access('WRITE'), access('READ')]), 1, {0: 0})
        self.assertFalse(any(e.get('producer') == e.get('consumer') for e in result['interference_graph']))

    def test_policy_matches_emitter_shape(self):
        ins = {'op': 'mov', 'es': 8, 'eo': 0, 'wren': True,
               'dst': {'kind': 'RD', 'reg': {'rn': 'r', 'r': 10}, 'type': 'ud', 'rgn': {'h': 1}},
               'srcs': [{'kind': 'RD', 'reg': {'rn': 'r', 'r': 11}, 'type': 'ud', 'rgn': {'h': 1, 'v': 8, 'w': 8}}]}
        self.assertTrue(policy.integer_mov_eligibility(ins)[0])
        for field, value in [('es', 4), ('eo', 4), ('wren', False)]:
            changed = copy.deepcopy(ins)
            changed[field] = value
            self.assertFalse(policy.integer_mov_eligibility(changed)[0])
        for operand in ['dst', 'srcs']:
            changed = copy.deepcopy(ins)
            (changed['dst'] if operand == 'dst' else changed['srcs'][0]).pop('rgn')
            self.assertFalse(policy.integer_mov_eligibility(changed)[0])


if __name__ == '__main__':
    unittest.main()
