import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ga39_unit', ROOT / 'translator/translate_unit.py')
unit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(unit)


class StrictUnitTests(unittest.TestCase):
    def setUp(self):
        work = ROOT / 'tests/work'
        work.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='unit-', dir=work)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def assemble(self, line):
        asm, binary = self.root / 'input.asm', self.root / 'input.bin'
        asm.write_text(line + '\n')
        unit.invoke(['-a', '-p=11', '-Xforce-no-compact', asm, '-o', binary], self.root / 'encode-source')
        return binary.read_bytes()

    def test_integer_mov_real_codegen_and_proof(self):
        raw = self.assemble('(W) mov (8|M0) r10.0<1>:ud r11.0<8;8,1>:ud')
        result = unit.translate(raw, self.root / 'translated')
        self.assertEqual(result['status'], unit.policy.PROVEN)
        self.assertFalse(result['full_shader_emitted'])
        self.assertEqual(len(result['proof']['lane_equations']), 8)
        self.assertEqual((self.root / 'translated/isolated-fragment.bin').read_bytes().hex(), result['target_bytes'])

    def test_float_is_not_accepted_by_integer_theorem(self):
        raw = self.assemble('(W) mov (8|M0) r10.0<1>:f r11.0<8;8,1>:f')
        result = unit.translate(raw, self.root / 'rejected')
        self.assertEqual(result['status'], unit.policy.UNKNOWN)
        self.assertFalse((self.root / 'rejected/isolated-fragment.bin').exists())

    def test_nf_debug_send_and_whole_shaders_rejected(self):
        baseline = ROOT / 'candidates/baseline/replay-003'
        for shader in ['PS0', 'PS-KP1', 'PS-KP2', 'VS']:
            raw = (baseline / f'corpus/source/{shader}.bin').read_bytes()
            result = unit.translate(raw, self.root / shader)
            self.assertEqual(result['rejection']['code'], 'ISOLATED_UNIT_REQUIRED')
            self.assertFalse((self.root / shader / 'isolated-fragment.bin').exists())
        raw = (baseline / 'corpus/source/PS0.bin').read_bytes()[:16]
        result = unit.translate(raw, self.root / 'nf')
        self.assertEqual(result['status'], unit.policy.UNKNOWN)
        self.assertFalse((self.root / 'nf/isolated-fragment.bin').exists())

    def test_injected_roundtrip_failure_never_commits_fragment(self):
        raw = self.assemble('(W) mov (8|M0) r10.0<1>:ud r11.0<8;8,1>:ud')
        original = unit.invoke

        def corrupt(args, directory):
            p = original(args, directory)
            if directory.name == 'roundtrip':
                Path(args[-1]).write_bytes(b'\0' * 16)
            return p

        unit.invoke = corrupt
        self.addCleanup(setattr, unit, 'invoke', original)
        result = unit.translate(raw, self.root / 'corrupt')
        self.assertEqual(result['rejection']['code'], 'ROUNDTRIP_BYTES_DIFFER')
        self.assertFalse((self.root / 'corrupt/isolated-fragment.bin').exists())


if __name__ == '__main__':
    unittest.main()
