"""Seal integration negatives on dedicated synthetic trees inside the run.

Tests preservation/detection properties, not duplicated hash implementations.
Historical-source identity is tested separately by the full provenance verifier.
"""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import seal
from common import analysis_run

RUN = analysis_run()


class SealIntegrity(unittest.TestCase):
    def setUp(self):
        parent = RUN / 'seal-fixtures'
        parent.mkdir(parents=True, exist_ok=True)
        self.tree = Path(tempfile.mkdtemp(prefix='fixture-', dir=parent))
        (self.tree / 'evidence.txt').write_bytes(b'known evidence\n')
        self.root_patch = patch.object(seal, 'ROOT', self.tree)
        self.external_patch = patch.object(seal, 'external_sources', return_value=[])
        self.root_patch.start()
        self.external_patch.start()

    def tearDown(self):
        self.external_patch.stop()
        self.root_patch.stop()

    def test_same_length_content_mutation_rejected(self):
        self.assertEqual(seal.create()['status'], 'PASS')
        (self.tree / 'evidence.txt').write_bytes(b'wrong evidence\n')
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            seal.verify()

    def test_added_file_and_self_hash_tampering_rejected(self):
        seal.create()
        (self.tree / 'unexpected.txt').write_bytes(b'new')
        with self.assertRaisesRegex(ValueError, 'Artifact set changed'):
            seal.verify()
        # Preserve the added-file failure as a negative fixture; self-hash is
        # checked first and must independently fail after manifest corruption.
        with (self.tree / 'manifest.json').open('ab') as f:
            f.write(b' ')
        with self.assertRaisesRegex(ValueError, 'self hash mismatch'):
            seal.verify()

    def test_symlink_text_sealed_without_following_dangling_target(self):
        link = self.tree / 'unfollowed-link'
        link.symlink_to('/nonexistent-ga38-target-A')
        result = seal.create()
        self.assertEqual(result['local_entries'], 2)
        self.assertEqual(result['status'], 'PASS')
        link.unlink()
        link.symlink_to('/nonexistent-ga38-target-B')
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            seal.verify()


if __name__ == '__main__':
    unittest.main(verbosity=2)
