import importlib.util
from fractions import Fraction
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('f32_exact', ROOT / 'numeric/oracle/f32_rational.py')
f32 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f32)


class NumericOracleTests(unittest.TestCase):
    def test_rounding_difference_exact_not_nf_claim(self):
        w = f32.rounding_witness()
        self.assertEqual(w['exact_product_plus_c'], str(-Fraction(1, 1 << 46)))
        self.assertNotEqual(w['fused_rne_bits'], w['split_rne_bits'])
        self.assertEqual(w['NF_NUMERIC_MODEL'], 'UNKNOWN')

    def test_ties_and_denormal_gradual_reference(self):
        self.assertEqual(f32.rne(Fraction(1, 1 << 150)), 0)
        self.assertEqual(f32.rne(Fraction(3, 1 << 150)), 2)
        self.assertEqual(f32.rne(Fraction(1) + Fraction(1, 1 << 24)), 0x3f800000)
        self.assertEqual(f32.rne(f32.finite(1)), 1)

    def test_special_values_do_not_become_nf_proof(self):
        for bits in [0x7f800000, 0xff800000, 0x7fc00001, 0x7f800001]:
            with self.assertRaisesRegex(ValueError, 'NONFINITE'):
                f32.finite(bits)
        self.assertEqual(f32.finite(0), f32.finite(0x80000000))
        # Rational projection loses signed-zero identity: explicitly outside theorem.


if __name__ == '__main__':
    unittest.main()
