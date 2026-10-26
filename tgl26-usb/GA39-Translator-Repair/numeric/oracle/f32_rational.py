"""Independent exact finite binary32 RNE model, explicitly NOT a Gen11 NF model.

Only a diagnostic witness showing why a rounding theorem is necessary. NaN,
infinity, signed zero propagation, denormal modes and non-RNE thread modes
require their own contracts and cannot discharge NF obligations here.
"""
from fractions import Fraction


def finite(bits):
    if type(bits) is not int or not 0 <= bits < 1 << 32:
        raise ValueError('Expected 32-bit encoding')
    sign, exponent, mantissa = bits >> 31, (bits >> 23) & 255, bits & 0x7fffff
    if exponent == 255:
        raise ValueError('NONFINITE_MODEL_UNSUPPORTED')
    value = Fraction(mantissa if exponent == 0 else (1 << 23) + mantissa)
    power = -149 if exponent == 0 else exponent - 150
    value *= Fraction(2) ** power
    return -value if sign else value


def rne(value):
    """Round exact rational to binary32 using monotone search + exact tie rule."""
    value = Fraction(value)
    negative = value < 0
    value = abs(value)
    if value > finite(0x7f7fffff):
        raise ValueError('OVERFLOW_MODEL_UNSUPPORTED')
    lo, hi = 0, 0x7f7fffff
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if finite(mid) <= value:
            lo = mid
        else:
            hi = mid - 1
    lower = lo
    if finite(lower) != value and lower < 0x7f7fffff:
        upper = lower + 1
        dl, du = value - finite(lower), finite(upper) - value
        if du < dl or (du == dl and upper % 2 == 0):
            lower = upper
    return lower | (int(negative) << 31)


def rounding_witness():
    a, b, c = 0x3f800001, 0x3f7ffffe, 0xbf800000
    product = finite(a) * finite(b)
    fused = rne(product + finite(c))
    split = rne(finite(rne(product)) + finite(c))
    assert fused == 0xa8800000 and split == 0
    return {'input_bits': [a, b, c], 'fused_rne_bits': fused, 'split_rne_bits': split,
            'exact_product_plus_c': str(product + finite(c)),
            'NF_NUMERIC_MODEL': 'UNKNOWN',
            'classification': 'COUNTEREXAMPLE_TO_UNIVERSAL_FUSED_SPLIT_F32_EQUALITY_ONLY',
            'not_evidence_of_actual_nf_behavior_or_upstream_shader_counterexample': True}
