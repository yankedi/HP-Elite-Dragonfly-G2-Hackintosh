import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'candidates/baseline/replay-003'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class ProofContracts(unittest.TestCase):
    def test_all_actual_acc_offsets_have_carrying_rejection(self):
        lower = module('lower_for_test', 'numeric/proofs/lowering.py')
        expected = {'PS0': [0, 32, 48, 64],
                    'PS-KP1': [0, 32, 48, 64, 80, 96, 112, 128, 144, 160, 176, 192, 208, 240, 256, 272],
                    'PS-KP2': [0, 32, 48, 64, 80, 96, 112, 128], 'VS': [0, 32, 40, 216]}
        for shader, offsets in expected.items():
            source, target = [json.loads((BASELINE / f'ir/outputs/{shader}-{side}.json').read_text()) for side in ['source', 'candidate']]
            witness = json.loads((BASELINE / f'validator/outputs/{shader}-comparison.json').read_text())['mapping_witness']
            result = lower.prove(source, target, witness)
            self.assertEqual([p['source_instruction']['offset'] for p in result['proofs']], offsets)
            self.assertTrue(all(p['status'] == 'UNKNOWN_REJECTED' for p in result['proofs']))
            self.assertTrue(all(p['source_instruction']['raw_hex'] and p['target_sequence'] and p['unmet_conditions'] for p in result['proofs']))
            if shader == 'VS':
                self.assertFalse(any(p['operand_replacements'] for p in result['proofs']))
            witness['entries'] = witness['entries'][:-1]
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                lower.prove(source, target, witness)

    def test_debug_explicit_deadness_does_not_discharge_switch(self):
        guard = module('debug_for_test', 'debug/switch-elimination/guard.py')
        for shader, pc in [('PS0', 16), ('PS-KP1', 16), ('PS-KP2', 16), ('VS', 240)]:
            source, target = [json.loads((BASELINE / f'ir/outputs/{shader}-{side}.json').read_text()) for side in ['source', 'candidate']]
            witness = json.loads((BASELINE / f'validator/outputs/{shader}-comparison.json').read_text())['mapping_witness']
            result = guard.audit(source, target, witness)
            self.assertEqual(len(result['records']), 1)
            record = result['records'][0]
            self.assertEqual(record['source_offset'], pc)
            self.assertEqual(record['conditions']['no_later_explicit_dbg_read'], 'KNOWN')
            self.assertEqual(record['status'], 'DEBUG_ELIMINATION_UNKNOWN')
            self.assertFalse(record['strict_admission'])


if __name__ == '__main__':
    unittest.main()
