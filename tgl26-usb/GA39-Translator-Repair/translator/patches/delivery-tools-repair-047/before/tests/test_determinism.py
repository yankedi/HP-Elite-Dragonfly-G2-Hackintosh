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
            (root / 'strict/PS0').mkdir(parents=True)
            (root / 'strict/PS0/source.bin').write_bytes(b'original')
            (root / 'strict/PS0/report.json').write_text(json.dumps(
                {'status': 'UNKNOWN_REJECTED', 'elapsed_seconds': elapsed, 'input_path': str(root / 'input'),
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


if __name__ == '__main__':
    unittest.main()
