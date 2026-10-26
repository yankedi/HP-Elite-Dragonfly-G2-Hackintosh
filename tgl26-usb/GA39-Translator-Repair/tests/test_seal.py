"""Seal must detect byte/set/link tampering without traversing fixture links."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('seal_test_module', ROOT / 'tools/seal.py')
seal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seal)


class SealTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'tests/work').mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix='seal-', dir=ROOT / 'tests/work')
        self.addCleanup(temp.cleanup)
        self.oldroot, self.oldexternal = seal.ROOT, seal.external_sources
        self.addCleanup(setattr, seal, 'ROOT', self.oldroot)
        self.addCleanup(setattr, seal, 'external_sources', self.oldexternal)
        seal.ROOT = Path(temp.name)
        seal.external_sources = lambda: []
        (seal.ROOT / 'file.txt').write_text('original\n')

    def test_file_byte_change_rejected_and_reseal_forbidden(self):
        self.assertEqual(seal.create()['status'], 'PASS')
        with self.assertRaisesRegex(ValueError, 'immutable'):
            seal.create()
        (seal.ROOT / 'file.txt').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            seal.verify()

    def test_new_artifact_cannot_hide_after_seal(self):
        seal.create()
        (seal.ROOT / 'unexpected.bin').write_bytes(b'new')
        with self.assertRaisesRegex(ValueError, 'set changed'):
            seal.verify()

    def test_symlink_text_is_sealed_without_following(self):
        link = seal.ROOT / 'fixture-link'
        link.symlink_to('/not/an/existing/path')
        self.assertEqual(seal.create()['status'], 'PASS')
        link.unlink()
        link.symlink_to('/another/nonexistent/path')
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            seal.verify()


if __name__ == '__main__':
    unittest.main()
