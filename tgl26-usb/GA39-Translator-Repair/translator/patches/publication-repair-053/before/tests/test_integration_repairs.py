"""Grounded regressions for Audit3 original counterexamples, not hardware claims."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


driver = module('driver_repairs_test', 'translator/driver.py')
unit = module('unit_repairs_test', 'translator/translate_unit.py')
lower = module('lower_repairs_test', 'numeric/proofs/lowering.py')


class IntegrationRepairs(unittest.TestCase):
    def setUp(self):
        (ROOT / 'tests/work').mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix='integration-', dir=ROOT / 'tests/work')
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)

    def test_native_receipts_are_binding_and_missing_binary_is_structured(self):
        original = driver.load
        config = original(ROOT / 'translator/research-mode/generator.json')
        forged = config | {'source_pin': 'BOGUS'}
        with patch.object(driver, 'load', return_value=forged):
            with self.assertRaises(driver.Rejected) as ctx:
                driver.native_generator()
        self.assertEqual(ctx.exception.code, 'NATIVE_SOURCE_PIN')
        with patch.object(driver, 'load', return_value=config | {'path': 'tests/work/absent-native'}):
            with self.assertRaises(driver.Rejected) as ctx:
                driver.native_generator()
        self.assertEqual(ctx.exception.code, 'NATIVE_IDENTITY_IO_OR_SCHEMA')

    def test_forged_findings_and_derived_nf_cannot_change_evidence(self):
        baseline = ROOT / 'candidates/baseline/replay-003'
        forged = self.work / 'baseline'
        shutil.copytree(baseline, forged, symlinks=True)
        target = forged / 'validator/outputs/PS0-comparison.json'
        obj = json.loads(target.read_text())
        obj['findings'] = []
        target.write_text(json.dumps(obj))
        with self.assertRaises(driver.Rejected) as ctx:
            driver.run('PS0', self.work / 'forged', baseline=forged)
        self.assertEqual(ctx.exception.code, 'BASELINE_EVIDENCE_IDENTITY')
        self.assertFalse((self.work / 'forged').exists())
        source, candidate = [json.loads((baseline / f'ir/outputs/PS0-{side}.json').read_text()) for side in ['source', 'candidate']]
        witness = json.loads((baseline / 'validator/outputs/PS0-comparison.json').read_text())['mapping_witness']
        altered = copy.deepcopy(source)
        for node in altered['nodes']:
            node['numeric_semantics'].update(nf=False, accumulator=False)
        with self.assertRaises(driver.Rejected) as ctx:
            lower.prove(altered, candidate, witness)
        self.assertEqual(ctx.exception.code, 'IR_DERIVED_FIELD_MISMATCH')

    def test_verify_iga_failure_is_structured_and_no_fragment(self):
        with patch.object(unit, 'verify_iga', side_effect=FileNotFoundError('missing git')):
            with self.assertRaises(unit.Rejected) as ctx:
                unit.invoke(['-h'], self.work / 'invocation')
        self.assertEqual(ctx.exception.code, 'TOOL_FAILURE')
        raw = (ROOT / 'candidates/patched/positive-fragment-033/source.bin').read_bytes()
        with patch.object(unit, 'decode', side_effect=subprocess.TimeoutExpired('git', 15)):
            result = unit.translate(raw, self.work / 'unit')
        self.assertEqual(result['status'], 'UNKNOWN_REJECTED')
        self.assertEqual(result['rejection']['code'], 'UNIT_INPUT_OR_TOOL_FAILURE')
        self.assertFalse((self.work / 'unit/isolated-fragment.bin').exists())

    def test_research_timeout_and_failed_generator_never_publish(self):
        raw = (ROOT / 'candidates/baseline/replay-003/corpus/candidate/PS0.bin').read_bytes()
        out = self.work / 'timeout'
        with patch.object(driver.subprocess, 'run', side_effect=subprocess.TimeoutExpired('generator', 30)):
            result = driver.run('PS0', out, 'research')
        self.assertEqual(result['research_validation_state'], 'FAILED_NOT_PUBLISHED')
        self.assertTrue((out / 'report.json').exists())
        self.assertFalse((out / 'research-NOT_FOR_HARDWARE').exists())

        def fail_after_bytes(cmd, **kwargs):
            Path(cmd[-1]).write_bytes(raw)
            return SimpleNamespace(returncode=1, stdout=b'', stderr=b'injected failure')
        out = self.work / 'exit1'
        with patch.object(driver.subprocess, 'run', side_effect=fail_after_bytes):
            result = driver.run('PS0', out, 'research')
        self.assertEqual(result['rejection']['code'], 'RESEARCH_GENERATOR_FAILURE')
        self.assertFalse(result['full_shader_emitted'])
        self.assertFalse((out / 'research-NOT_FOR_HARDWARE').exists())
        self.assertEqual((out / 'rejected-NOT_FOR_HARDWARE/candidate.NOT_FOR_HARDWARE.bin').read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
