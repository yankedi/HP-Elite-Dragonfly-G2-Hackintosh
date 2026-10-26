"""Determinism normalization must never erase semantic/byte differences."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('delivery_determinism_tests', ROOT / 'tools/run_delivery.py')
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class DeterminismTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'tests/work').mkdir(exist_ok=True)
        t = tempfile.TemporaryDirectory(prefix='determinism-', dir=ROOT / 'tests/work')
        self.addCleanup(t.cleanup)
        self.base = Path(t.name)
        self.left, self.right = self.base / 'left', self.base / 'right'
        for root, elapsed in [(self.left, 1.0), (self.right, 2.0)]:
            for name in delivery.required_artifacts():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'{}' if name.endswith('.json') else b'synthetic')
            for s in delivery.SHADERS:
                (root / f'strict/{s}/report.json').write_text(json.dumps(
                    {'mode': 'strict', 'status': 'UNKNOWN_REJECTED', 'accepted_program': False,
                     'full_shader_emitted': False}))
                (root / f'research/{s}/report.json').write_text(json.dumps(
                    {'mode': 'research', 'accepted_program': False, 'research_program_generated': True,
                     'research_validation_state': 'MAPPED_DECODED_ROUNDTRIPPED_NOT_SEMANTICALLY_PROVEN'}))
            (root / 'strict/PS0/source.bin').write_bytes(b'original')
            (root / 'strict/PS0/report.json').write_text(json.dumps(
                {'mode': 'strict', 'status': 'UNKNOWN_REJECTED', 'accepted_program': False, 'full_shader_emitted': False,
                 'elapsed_seconds': elapsed, 'input_path': str(root / 'input'),
                 'numeric_semantics': {'rounding_mode': 'UNKNOWN'}}))

    def test_only_run_paths_and_declared_timings_normalized(self):
        out = self.base / 'same'
        delivery.compare_fresh(self.left, self.right, out)
        self.assertTrue(json.loads((out / 'determinism.json').read_text())['equal'])

    def test_false_known_survives_normalization(self):
        path = self.right / 'strict/PS0/report.json'
        obj = json.loads(path.read_text())
        obj['numeric_semantics']['rounding_mode'] = 'KNOWN'
        path.write_text(json.dumps(obj))
        out = self.base / 'different'
        with self.assertRaisesRegex(ValueError, 'Determinism failed'):
            delivery.compare_fresh(self.left, self.right, out)
        self.assertFalse(json.loads((out / 'determinism.json').read_text())['equal'])

    def test_byte_change_never_normalized(self):
        (self.right / 'strict/PS0/source.bin').write_bytes(b'mutated')
        with self.assertRaisesRegex(ValueError, 'Determinism failed'):
            delivery.compare_fresh(self.left, self.right, self.base / 'byte-difference')

    def test_shared_missing_artifact_cannot_pass(self):
        for root in [self.left, self.right]:
            (root / 'semantics/VS.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Required semantic artifacts missing'):
            delivery.compare_fresh(self.left, self.right, self.base / 'missing')

    def test_nested_elapsed_seconds_is_not_omitted(self):
        for root, value in [(self.left, 'UNKNOWN'), (self.right, 'KNOWN')]:
            p = root / 'strict/PS0/report.json'
            d = json.loads(p.read_text())
            d['numeric_semantics']['elapsed_seconds'] = value
            p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError, 'Determinism failed'):
            delivery.compare_fresh(self.left, self.right, self.base / 'nested-timing')

    def test_acceptance_is_not_hardcoded_to_zero(self):
        p = self.right / 'strict/PS0/report.json'
        d = json.loads(p.read_text())
        d.update(accepted_program=True, status='PROVEN')
        p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError, 'Unexpected strict acceptance'):
            delivery.compare_fresh(self.left, self.right, self.base / 'wrong-acceptance')


if __name__ == '__main__':
    unittest.main()
