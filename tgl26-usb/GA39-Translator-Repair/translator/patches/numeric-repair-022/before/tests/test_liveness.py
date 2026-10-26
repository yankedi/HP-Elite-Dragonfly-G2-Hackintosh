"""Literal byte expectations, independent of GA38 region/parser helpers."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('live', ROOT / 'numeric/scratch-liveness/liveness.py')
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


def access(mode, lo, hi, conditional=False):
    return {'file': 'GRF', 'mode': mode, 'state': 'CONDITIONAL' if conditional else 'KNOWN',
            'elements': [{'byte_start': lo, 'byte_end': hi, 'lane': 0}], 'role': 'TEST',
            'condition': 'predicate' if conditional else 'all instruction channels execute'}


def program(rows):
    return {'shader_id': 'TEST', 'program_sha256': 'synthetic', 'nodes': [
        {'byte_range': [i * 16, i * 16 + 16], 'raw_hex': '00' * 16,
         'register_access': {'accesses': row}} for i, row in enumerate(rows)]}


class LivenessTests(unittest.TestCase):
    def test_partial_write_kills_only_four_bytes(self):
        p = program([[access('WRITE', 0, 4)], [access('READ', 0, 8)]])
        r = live.analyze(p)
        self.assertEqual(r['records'][0]['live_before'], [[4, 8]])
        self.assertEqual(r['records'][0]['live_after'], [[0, 8]])

    def test_predicate_write_kills_nothing(self):
        p = program([[access('WRITE', 0, 4, True)], [access('READ', 0, 8)]])
        self.assertEqual(live.analyze(p)['records'][0]['live_before'], [[0, 8]])

    def test_symbolic_indirect_is_not_none(self):
        p = program([[{'file': 'ANY', 'mode': 'READ', 'state': 'UNKNOWN', 'elements': None}]])
        r = live.analyze(p)
        self.assertEqual(len(r['symbolic_grf_accesses']), 1)
        self.assertEqual(r['external_thread_payload_abi'], 'UNKNOWN')

    def test_direct_collision_and_unknown_abi(self):
        s = program([[access('READ', 32, 36)]])
        t = program([[access('WRITE', 32, 36)]])
        r = live.scratch_contract(s, t, 1, {0: 0})
        self.assertEqual(r['allocation_status'], 'REFUTED_WITH_COUNTEREXAMPLE')
        self.assertEqual(r['static_collisions'][0]['bytes'], [[32, 36]])
        s = program([[access('READ', 0, 4)]])
        r = live.scratch_contract(s, t, 1, {0: 0})
        self.assertEqual(r['static_collisions'], [])
        self.assertEqual(r['allocation_status'], 'UNKNOWN_REJECTED')
        self.assertIn('THREAD_PAYLOAD_EXTERNAL_LIVE_IN', r['unmet_obligations'])

    def test_future_read_interferes_with_scratch_write(self):
        s = program([[access('READ', 0, 4)], [access('READ', 32, 36)]])
        t = program([[access('WRITE', 32, 36)], [access('READ', 0, 4)]])
        r = live.scratch_contract(s, t, 1, {0: 0, 16: 16})
        self.assertTrue(any(e['kind'] == 'MAY_LIVE_INTERFERENCE' for e in r['interference_graph']))
        self.assertEqual(r['allocation_status'], 'UNKNOWN_REJECTED')


if __name__ == '__main__':
    unittest.main()
