import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ga39_driver', ROOT / 'translator/driver.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class DriverTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'tests/work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='driver-', dir=ROOT / 'tests/work')
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def test_default_strict_never_invokes_research_generator(self):
        original = driver.native_generator
        driver.native_generator = lambda: self.fail('Strict reached native research generator')
        self.addCleanup(setattr, driver, 'native_generator', original)
        for shader, count in [('PS0', 11), ('PS-KP1', 29), ('PS-KP2', 15), ('VS', 24)]:
            out = self.work / shader
            result = driver.run(shader, out)
            self.assertEqual(result['mode'], 'strict')
            self.assertEqual(result['status'], 'UNKNOWN_REJECTED')
            self.assertEqual(len(result['obligations']), count)
            self.assertFalse(result['accepted_program'])
            self.assertFalse(result['full_shader_emitted'])
            self.assertEqual(sorted(p.name for p in out.iterdir()), ['report.json', 'source.bin'])

    def test_bad_mode_and_existing_destination_refused(self):
        for mode in ['STRICT', '', None, 'skip-validation']:
            with self.assertRaises(driver.Rejected):
                driver.run('PS0', self.work / 'new', mode)
        with self.assertRaises(driver.Rejected) as ctx:
            driver.run('PS0', self.work)
        self.assertEqual(ctx.exception.code, 'OUTPUT_EXISTS')

    def test_full_identity_rejects_modified_source(self):
        baseline = self.work / 'fake-baseline'
        baseline.mkdir()
        (baseline / 'corpus').mkdir()
        actual = ROOT / 'candidates/baseline/replay-003'
        obj = json.loads((actual / 'corpus/provenance.json').read_text())
        program = next(p for p in obj['programs'] if p['shader_id'] == 'PS0')
        f = baseline / program['source']['path']
        f.parent.mkdir(parents=True, exist_ok=True)
        raw = bytearray((actual / program['source']['path']).read_bytes())
        raw[-1] ^= 1
        f.write_bytes(raw)
        program['source']['sha256'] = driver.sha(raw)
        (baseline / 'corpus/provenance.json').write_text(json.dumps(obj))
        with self.assertRaises(driver.Rejected) as ctx:
            driver.run('PS0', self.work / 'out', baseline=baseline)
        self.assertEqual(ctx.exception.code, 'SOURCE_IDENTITY')
        self.assertFalse((self.work / 'out').exists())


if __name__ == '__main__':
    unittest.main()
