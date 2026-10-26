#!/usr/bin/env python3
"""Executable coverage tests for ``translator/offline_translate.py`` (GA32-ISA-Lab).

Scope and safety
----------------
Everything here is pure software exercising the *pinned* IGA build at
``tools/iga/build/IGAExe/iga64`` and the offline translator.  No GPU, device,
driver, firmware, network or third-party source tree is touched.  Temporary
directories live under ``tests/`` only.  The translator source itself is never
modified; the translator module is imported read-only.

Samples are explicitly classified as ``positive`` (a unit is expected to
round-trip validate), ``negative`` (a specific fail-closed rejection code is
expected) or ``unknown`` (an encoding IGA decodes as ``illegal``, i.e. an
unknown/invalid opcode).  None of these are hardware samples.

The module also writes ``tests/translator-coverage.json`` (from the executed
matrix) and the sample ``.asm``/``.bin`` sources under ``tests/samples/``.
"""
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

LAB = Path(__file__).resolve().parents[1]
TESTS = LAB / 'tests'
SAMPLES = TESTS / 'translator-samples'
TMP_ROOT = TESTS / '.translator-tmp'
TRANSLATOR = LAB / 'translator' / 'offline_translate.py'
IGA_EXE = LAB / 'tools' / 'iga' / 'build' / 'IGAExe' / 'iga64'
COVERAGE_FILE = TESTS / 'translator-coverage.json'

sys.path.insert(0, str(LAB / 'translator'))
import offline_translate as T  # noqa: E402

SRC_PLATFORM = '11'          # ICL / Gen11 source, fixed by the translator
TGT_PLATFORM = '12p1'        # Gen12.1 translation target, fixed by the translator

# Real captures produced by the lab (read-only inputs, not part of the test).
PS_CAPTURE = LAB / 'analysis' / 'ps-icl.bin'
VS_CAPTURE = LAB / 'analysis' / 'vs-icl.bin'
PS_SHA256 = '15e332f4f3fba0c2f20b781d78f36f29ebd4e65de02d5873de2b36aa1145e370'
VS_SHA256 = 'b02abaacf5a9f5fead7f0abb47a1d372bb0cafb5c5ed64b52a5912d18485d182'

_TMP_DIRS = []
_RESULTS = {}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    return _sha256_bytes(Path(path).read_bytes())


def _tmpdir(label):
    """Create a throw-away directory under ``tests/.translator-tmp`` (never IGA)."""
    d = Path(tempfile.mkdtemp(prefix=f'tmp-{label}-', dir=str(TMP_ROOT)))
    _TMP_DIRS.append(d)
    return d


def _assemble(asm_text, platform=SRC_PLATFORM, extra=None):
    """Assemble Gen11 text with the pinned IGA binary; return raw bytes."""
    d = _tmpdir('asm')
    asm = d / 'sample.asm'
    out = d / 'sample.bin'
    asm.write_text(asm_text)
    cmd = [str(IGA_EXE), '-a', f'-p={platform}']
    if extra:
        cmd.extend(extra)
    cmd += [str(asm), '-o', str(out)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode or not out.exists():
        raise AssertionError(
            f'IGA failed to assemble sample ({r.returncode}): '
            f'{(r.stdout + r.stderr).decode(errors="replace").strip()[:400]}'
        )
    return out.read_bytes()


def _translate(data, label):
    """Return ``(report, rejected)``; exactly one is ``None``."""
    dest = _tmpdir('tr-' + label)
    try:
        return T.translate(data, dest), None
    except T.Rejected as exc:
        return None, exc


def _decoded_unit(data):
    return T.decode(data, SRC_PLATFORM, _tmpdir('dec'))


def _write_sample(relpath, data):
    p = SAMPLES / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def _report_codes(report):
    return [(u['source_offset'], u['status'], u.get('code')) for u in report['instructions']]


# --------------------------------------------------------------------------- #
# canonical synthetic sample matrix (single source of truth)
# --------------------------------------------------------------------------- #
# positive: IGA-assembled Gen11 that the translator must round-trip validate.
POSITIVE = {
    'mov_native_f': (
        'mov (8|M0) r1.0<1>:f r2.0<8;8,1>:f\n',
        ['ordinary-native', 'opcode-mov', 'type-f', 'region', 'region-8x8', 'simd', 'simd-8', 'native']),
    'mov_compact_f': (
        'mov (8|M0) r124.0<1>:f r5.0<8;8,1>:f {Compacted}\n',
        ['compact', 'opcode-mov', 'type-f', 'region-8x8', 'simd-8']),
    'mov_imm_f': (
        'mov (8|M0) r1.0<1>:f 1.0:f\n',
        ['opcode-mov', 'type-f', 'immediate', 'simd-8']),
    'mov_imm_ud': (
        'mov (8|M0) r1.0<1>:ud 0x3f800000:ud\n',
        ['opcode-mov', 'type-integer-width', 'immediate', 'simd-8']),
    'mov_type_ud': (
        'mov (8|M0) r1.0<1>:ud r2.0<8;8,1>:ud\n',
        ['opcode-mov', 'type-integer-width', 'simd-8']),
    'mov_type_d': (
        'mov (8|M0) r1.0<1>:d r2.0<8;8,1>:d\n',
        ['opcode-mov', 'type-integer-width', 'simd-8']),
    'mov_type_w': (
        'mov (8|M0) r1.0<1>:w r2.0<8;8,1>:w\n',
        ['opcode-mov', 'type-integer-width', 'simd-8']),
    'mov_type_uw': (
        'mov (8|M0) r1.0<1>:uw r2.0<8;8,1>:uw\n',
        ['opcode-mov', 'type-integer-width', 'simd-8']),
    'add_f': (
        'add (8|M0) r1.0<1>:f r2.0<8;8,1>:f r3.0<8;8,1>:f\n',
        ['opcode-add', 'type-f', 'region', 'region-8x8', 'simd', 'simd-8']),
    'add_imm_f': (
        'add (8|M0) r1.0<1>:f r2.0<8;8,1>:f 1.0:f\n',
        ['opcode-add', 'type-f', 'immediate', 'simd-8']),
    'mul_f': (
        'mul (8|M0) r1.0<1>:f r2.0<0;1,0>:f r3.0<8;8,1>:f\n',
        ['opcode-mul', 'type-f', 'region-scalar', 'simd-8']),
    'simd1_mov': (
        'mov (1|M0) r1.0<1>:f r2.0<0;1,0>:f\n',
        ['opcode-mov', 'simd-1']),
    'simd4_mov': (
        'mov (4|M0) r1.0<1>:f r2.0<4;4,1>:f\n',
        ['opcode-mov', 'simd-4', 'region-4x4']),
    'simd16_add': (
        'add (16|M0) r1.0<1>:f r2.0<16;16,1>:f r3.0<16;16,1>:f\n',
        ['opcode-add', 'simd-16', 'region-16x16']),
    'region_scalar': (
        'add (8|M0) r1.0<1>:f r2.0<0;1,0>:f r3.0<8;8,1>:f\n',
        ['opcode-add', 'region-scalar', 'simd-8']),
    'region_4x4': (
        'add (8|M0) r1.0<1>:f r2.0<4;4,1>:f r3.0<8;8,1>:f\n',
        ['opcode-add', 'region-4x4', 'simd-8']),
    'dst_region': (
        'mov (8|M0) r1.0<2>:f r2.0<8;8,1>:f\n',
        ['opcode-mov', 'region-dst', 'simd-8']),
    'predicate_f': (
        '(f0.0) mov (8|M0) r1.0<1>:f r2.0<8;8,1>:f\n',
        ['opcode-mov', 'predicate', 'simd-8']),
    'write_enable_W': (
        '(W) mov (8|M0) r1.0<1>:f r2.0<8;8,1>:f\n',
        ['opcode-mov', 'predicate', 'write-enable', 'simd-8']),
    'pred_write_enable': (
        '(W&f0.0) mov (8|M0) r1.0<1>:f r2.0<8;8,1>:f\n',
        ['opcode-mov', 'predicate', 'write-enable', 'simd-8']),
    'sat_add': (
        'add (8|M0) (sat)r1.0<1>:f r2.0<8;8,1>:f r3.0<8;8,1>:f\n',
        ['opcode-add', 'flag-modifier', 'simd-8']),
    'mixed_stream': (
        'mov (8|M0) r124.0<1>:f r5.0<8;8,1>:f {Compacted}\n'
        'add (8|M0) r1.0<1>:f r2.0<8;8,1>:f r3.0<8;8,1>:f\n'
        'mov (8|M0) r125.0<1>:f r6.0<8;8,1>:f {Compacted}\n',
        ['mixed', 'compact', 'ordinary-native', 'opcode-mov', 'opcode-add']),
}

# negative: assembled Gen11 that must be rejected with the named code.
NEGATIVE = {
    'opcode_mac': (
        'mac (8|M0) r1.0<1>:f r2.0<8;8,1>:f r3.0<8;8,1>:f\n',
        'OPCODE_UNSUPPORTED', ['opcode-unsupported']),
    'opcode_mad': (
        'mad (8|M0) r0.0<1>:f acc0.0<4;1>:nf r3.0<8;1>:f r4.1<0>:f\n',
        'OPCODE_UNSUPPORTED', ['opcode-unsupported']),
    'special_acc': (
        'mov (8|M0) acc0.0<1>:f r2.0<8;8,1>:f\n',
        'SPECIAL_REGISTER_UNSUPPORTED', ['special-register']),
    'execoption_switch': (
        'mov (1|M0) dbg0.0<1>:ud 0:w {Switch}\n',
        'EXECUTION_OPTION_UNSUPPORTED', ['execution-option']),
    'type_ub': (
        'mov (8|M0) r1.0<1>:ub r2.0<8;8,1>:ub\n',
        'TYPE_UNSUPPORTED', ['type-unsupported']),
    'int_add': (
        'add (8|M0) r1.0<1>:ud r2.0<8;8,1>:ud r3.0<8;8,1>:ud\n',
        'INTEGER_ALU_UNPROVEN', ['type-conversion', 'opcode-add']),
    'typeconv_mov': (
        'mov (8|M0) r1.0<1>:f r2.0<8;8,1>:ud\n',
        'TYPE_CONVERSION_UNPROVEN', ['type-conversion']),
    'operand_indirect': (
        'mov (8|M0) r1.0<1>:f r[a0.0]<8;8,1>:f\n',
        'OPERAND_UNSUPPORTED', ['operand']),
    'imm_inf': (
        'mov (8|M0) r1.0<1>:f inf:f\n',
        'IMMEDIATE_BITS_UNPROVEN', ['immediate-nonfinite']),
    'imm_qnan': (
        'mov (8|M0) r1.0<1>:f 0x7fc00000:f\n',
        'IMMEDIATE_BITS_UNPROVEN', ['immediate-nonfinite']),
    'send_no_eot': (
        'sends (8|M0) null:ud r1 r2 0x0 0x0\n',
        'SEND_EOT_SEMANTICS_UNPROVEN', ['send-eot-rejection']),
    'send_eot': (
        'sendsc (8|M0) null:ud r1 null 0x25 0x08031400 {EOT}\n',
        'SEND_EOT_SEMANTICS_UNPROVEN', ['send-eot-rejection']),
    'branch_jmpi': (
        'jmpi (1|M0) 0x10\n',
        'BRANCH_RELOCATION_UNSUPPORTED', ['branch']),
    'branch_brd': (
        'brd (8|M0) L1\nL1:\n',
        'BRANCH_RELOCATION_UNSUPPORTED', ['branch']),
    'branch_brc': (
        'brc (8|M0) L1\nL1:\n',
        'BRANCH_RELOCATION_UNSUPPORTED', ['branch']),
    'branch_if': (
        'if (8|M0) L1 L2\nL1:\nL2:\n',
        'BRANCH_RELOCATION_UNSUPPORTED', ['branch']),
    'branch_else': (
        'else (8|M0) L1 L2\nL1:\nL2:\n',
        'BRANCH_RELOCATION_UNSUPPORTED', ['branch']),
    'branch_call': (
        'call (1|M0) r1.0<1>:f L1\nL1:\n',
        'BRANCH_RELOCATION_UNSUPPORTED', ['branch']),
    'branch_halt': (
        'halt (1|M0) L1 L2\nL1:\nL2:\n',
        'BRANCH_RELOCATION_UNSUPPORTED', ['branch']),
    'branch_goto': (
        'goto (1|M0) L1 L2\nL1:\nL2:\n',
        'BRANCH_RELOCATION_UNSUPPORTED', ['branch']),
}

# appends a dependency-drain tail so exe=0/wren=1/regDist=@1 drains exist in every
# validated target.  Real samples cover this too (see TestRealShaders).
VALIDATED_TARGET_MIN_BYTES = 16

MOCK_CASES = {
    'mock_semantic_roundtrip': ('SEMANTIC_ROUNDTRIP_MISMATCH', 'roundtrip-mock-injection'),
    'mock_binary_roundtrip': ('BINARY_ROUNDTRIP_MISMATCH', 'roundtrip-mock-injection'),
    'mock_drain_regdist': ('UNEXPECTED_SWSB_SYNTHESIS', 'swsb-drains'),
    'mock_drain_sync_operand': ('UNEXPECTED_SYNC_OPERAND', 'swsb-drains'),
    'mock_target_decode_empty': ('TARGET_DECODE_FAILED', 'target-decode-gate'),
}

REQUIRED_CATEGORIES = {
    'framing-length', 'ordinary-native', 'compact', 'mixed',
    'opcode-mov', 'opcode-add', 'opcode-mul', 'opcode-unsupported',
    'type-f', 'type-integer-width', 'type-unsupported', 'type-conversion',
    'region', 'region-8x8', 'region-scalar', 'immediate', 'immediate-nonfinite',
    'predicate', 'simd',
    'simd-1', 'simd-4', 'simd-8', 'simd-16',
    'branch', 'branch-out-of-range', 'send-eot-rejection', 'swsb-drains',
    'unknown-invalid-opcode', 'roundtrip-mock-injection',
    'real-ps-shader', 'real-vs-shader',
}


# --------------------------------------------------------------------------- #
# module setup / teardown
# --------------------------------------------------------------------------- #
def setUpModule():
    if not IGA_EXE.is_file() or not os.access(IGA_EXE, os.X_OK):
        raise RuntimeError(f'pinned IGA binary missing/not executable: {IGA_EXE}')
    # fresh, namespaced temp root; also clears any stale dirs from a crashed run
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    # only our own namespaced sample subtrees are rewritten
    for sub in ('positive', 'negative', 'raw'):
        shutil.rmtree(SAMPLES / sub, ignore_errors=True)
    (SAMPLES / 'positive').mkdir(parents=True, exist_ok=True)
    (SAMPLES / 'negative').mkdir(parents=True, exist_ok=True)
    (SAMPLES / 'raw').mkdir(parents=True, exist_ok=True)
    for sid, (asm, _tags) in POSITIVE.items():
        _write_sample(f'positive/{sid}.asm', asm.encode())
    for sid, (asm, _code, _tags) in NEGATIVE.items():
        _write_sample(f'negative/{sid}.asm', asm.encode())
    # raw byte samples whose text form is not assemblable
    _write_sample('raw/unknown_invalid_opcode.bin', b'\x00' * 16)
    near = _assemble('jmpi (1|M0) 0x10\n')
    patched = bytearray(near)
    patched[-4:] = (0x4000).to_bytes(4, 'little')     # target far after sample end
    _write_sample('raw/branch_jmpi_out_of_range.bin', bytes(patched))


def tearDownModule():
    observed = {k: v for k, v in _RESULTS.items() if k != 'coverage_manifest'}
    COVERAGE_FILE.write_text(json.dumps(_build_manifest(observed), indent=2, sort_keys=False) + '\n')
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def _result(sample_id, **kw):
    _RESULTS.setdefault(sample_id, {}).update(kw)


# --------------------------------------------------------------------------- #
# framing / length
# --------------------------------------------------------------------------- #
class TestFraming(unittest.TestCase):
    def test_compact_and_native_split(self):
        mixed = _assemble(POSITIVE['mixed_stream'][0])
        self.assertEqual(T.frames(mixed), [(0, 8), (8, 16), (24, 8)])
        _result('framing_mixed', observed=T.frames(mixed))

    def test_compact_single_is_eight_bytes(self):
        data = _assemble(POSITIVE['mov_compact_f'][0])
        self.assertEqual(len(data), 8)
        self.assertTrue(int.from_bytes(data[:4], 'little') & (1 << 29))
        self.assertEqual(T.frames(data), [(0, 8)])

    def test_native_single_is_sixteen_bytes(self):
        data = _assemble(POSITIVE['mov_native_f'][0])
        self.assertEqual(len(data), 16)
        self.assertEqual(T.frames(data), [(0, 16)])

    def test_zero_length_rejected(self):
        with self.assertRaises(T.Rejected) as cm:
            T.frames(b'')
        self.assertEqual(cm.exception.code, 'INVALID_LENGTH')

    def test_oversize_rejected(self):
        with self.assertRaises(T.Rejected) as cm:
            T.frames(b'\x00' * (T.MAX_BYTES + 1))
        self.assertEqual(cm.exception.code, 'INVALID_LENGTH')

    def test_truncated_tail_rejected(self):
        # compact (8 bytes) followed by a 4-byte remainder
        data = _assemble(POSITIVE['mov_compact_f'][0]) + b'\x00' * 4
        with self.assertRaises(T.Rejected) as cm:
            T.frames(data)
        self.assertEqual((cm.exception.code, cm.exception.offset), ('TRUNCATED', 8))


# --------------------------------------------------------------------------- #
# eligibility whitelist (executable unit tests on synthetic IR dicts)
# --------------------------------------------------------------------------- #
def _mk_ins(op='mov', opts=None, dst=None, srcs=None, pc=0):
    if dst is None:
        dst = {'kind': 'RD', 'reg': {'rn': 'r', 'r': 1}, 'type': 'f'}
    if srcs is None:
        srcs = [{'kind': 'RD', 'reg': {'rn': 'r', 'r': 2}, 'type': 'f'}]
    d = {'op': op, 'pc': pc, 'opts': opts or [], 'dst': dst, 'srcs': srcs}
    return d


class TestEligibility(unittest.TestCase):
    def test_branch_rejected(self):
        with self.assertRaises(T.Rejected) as cm:
            T.eligibility(_mk_ins(op='jmpi'))
        self.assertEqual(cm.exception.code, 'BRANCH_RELOCATION_UNSUPPORTED')

    def test_send_opcode_rejected(self):
        with self.assertRaises(T.Rejected) as cm:
            T.eligibility(_mk_ins(op='sends'))
        self.assertEqual(cm.exception.code, 'SEND_EOT_SEMANTICS_UNPROVEN')

    def test_eot_option_rejected(self):
        with self.assertRaises(T.Rejected) as cm:
            T.eligibility(_mk_ins(op='mov', opts=['EOT']))
        self.assertEqual(cm.exception.code, 'SEND_EOT_SEMANTICS_UNPROVEN')

    def test_unknown_opcode_rejected(self):
        with self.assertRaises(T.Rejected) as cm:
            T.eligibility(_mk_ins(op='illegal'))
        self.assertEqual(cm.exception.code, 'OPCODE_UNSUPPORTED')

    def test_execution_option_rejected(self):
        with self.assertRaises(T.Rejected) as cm:
            T.eligibility(_mk_ins(op='mov', opts=['Switch']))
        self.assertEqual(cm.exception.code, 'EXECUTION_OPTION_UNSUPPORTED')

    def test_operand_kind_rejected(self):
        dst = {'kind': 'DA', 'type': 'f'}
        with self.assertRaises(T.Rejected) as cm:
            T.eligibility(_mk_ins(dst=dst))
        self.assertEqual(cm.exception.code, 'OPERAND_UNSUPPORTED')

    def test_special_register_rejected(self):
        dst = {'kind': 'RD', 'reg': {'rn': 'acc', 'r': 0}, 'type': 'f'}
        with self.assertRaises(T.Rejected) as cm:
            T.eligibility(_mk_ins(dst=dst))
        self.assertEqual(cm.exception.code, 'SPECIAL_REGISTER_UNSUPPORTED')

    def test_type_rejected(self):
        dst = {'kind': 'RD', 'reg': {'rn': 'r', 'r': 1}, 'type': 'q'}
        with self.assertRaises(T.Rejected) as cm:
            T.eligibility(_mk_ins(dst=dst))
        self.assertEqual(cm.exception.code, 'TYPE_UNSUPPORTED')

    def test_nonfinite_float_immediate_rejected(self):
        for value in ('inf', 'qnan(0x0)', '-nan(0x123)'):
            with self.subTest(value=value):
                src = [{'kind': 'IM', 'value': value, 'type': 'f'}]
                with self.assertRaises(T.Rejected) as cm:
                    T.eligibility(_mk_ins(op='mov', srcs=src))
                self.assertEqual(cm.exception.code, 'IMMEDIATE_BITS_UNPROVEN')

    def test_integer_alu_rejected(self):
        src = [{'kind': 'RD', 'reg': {'rn': 'r', 'r': 2}, 'type': 'ud'},
               {'kind': 'RD', 'reg': {'rn': 'r', 'r': 3}, 'type': 'ud'}]
        with self.assertRaises(T.Rejected) as cm:
            T.eligibility(_mk_ins(op='add', srcs=src))
        self.assertEqual(cm.exception.code, 'INTEGER_ALU_UNPROVEN')

    def test_type_conversion_rejected(self):
        src = [{'kind': 'RD', 'reg': {'rn': 'r', 'r': 2}, 'type': 'ud'}]
        with self.assertRaises(T.Rejected) as cm:
            T.eligibility(_mk_ins(op='mov', srcs=src))
        self.assertEqual(cm.exception.code, 'TYPE_CONVERSION_UNPROVEN')


# --------------------------------------------------------------------------- #
# synthetic positive samples
# --------------------------------------------------------------------------- #
class TestSyntheticPositive(unittest.TestCase):
    def _run_one(self, sid):
        asm, tags = POSITIVE[sid]
        data = _assemble(asm)
        report, rejected = _translate(data, sid)
        self.assertIsNone(rejected, f'{sid}: unexpected rejection {rejected and rejected.code}')
        self.assertEqual(report['status'], 'ROUNDTRIP_VALIDATED', sid)
        self.assertEqual(report['unsupported_units'], 0, sid)
        self.assertEqual(report['validated_units'], len(report['instructions']), sid)
        self.assertFalse(report['full_shader_emitted'])
        self.assertFalse(report['hardware_execution_validated'])
        for unit in report['instructions']:
            self.assertEqual(unit['status'], 'ROUNDTRIP_VALIDATED', sid)
            self.assertEqual(len(bytes.fromhex(unit['target_bytes'])), unit['target_length'], sid)
            self.assertGreaterEqual(unit['target_length'], VALIDATED_TARGET_MIN_BYTES, sid)
            off = unit['source_offset']
            n = len(unit['source_bytes']) // 2
            self.assertEqual(data[off:off + n].hex(), unit['source_bytes'], sid)
        _result(sid, sample_class='positive', tags=tags,
                source_bytes=len(data), source_sha256=_sha256_bytes(data),
                observed='ROUNDTRIP_VALIDATED', units=len(report['instructions']),
                target_lengths=[u['target_length'] for u in report['instructions']],
                drains=sum(len(u['synthesized_dependency_drains'])
                           for u in report['instructions']))
        return data, report

    def test_all_positive_samples(self):
        for sid in POSITIVE:
            with self.subTest(sample=sid):
                self._run_one(sid)

    def test_compact_sample_is_eight_byte_source(self):
        asm, _ = POSITIVE['mov_compact_f']
        data = _assemble(asm)
        self.assertEqual(len(data), 8)
        _, report = self._run_one('mov_compact_f')
        self.assertEqual(len(report['instructions']), 1)
        # the translator must not transplant the source compaction bit
        self.assertNotIn('{Compacted}', report['instructions'][0]['target_asm'])

    def test_mixed_stream_has_three_units(self):
        data, report = self._run_one('mixed_stream')
        self.assertEqual(T.frames(data), [(0, 8), (8, 16), (24, 8)])
        self.assertEqual(len(report['instructions']), 3)
        self.assertEqual(report['validated_units'], 3)
        self.assertEqual([u['source_offset'] for u in report['instructions']], [0, 8, 24])

    def test_emitted_target_redecodes_identically(self):
        for sid in ('mov_native_f', 'mov_compact_f', 'add_f', 'mul_f', 'simd16_add'):
            with self.subTest(sample=sid):
                _, report = self._run_one(sid)
                unit = report['instructions'][0]
                target = bytes.fromhex(unit['target_bytes'])
                dec = T.decode(target, TGT_PLATFORM, _tmpdir('re-' + sid))
                self.assertEqual(dec['exit'], 0)
                self.assertTrue(dec['instructions'])
                self.assertEqual(T.normalized(dec['instructions'][0]),
                                 T.normalized(unit['target']))

    def test_artifact_written_and_matches_target(self):
        dest = _tmpdir('art')
        data = _assemble(POSITIVE['mov_native_f'][0])
        report = T.translate(data, dest)
        unit = report['instructions'][0]
        artifact = dest / unit['artifact']
        self.assertTrue(artifact.is_file())
        self.assertEqual(artifact.read_bytes().hex(), unit['target_bytes'])
        self.assertEqual(unit['target_segment'], unit['artifact'])


# --------------------------------------------------------------------------- #
# synthetic negative samples
# --------------------------------------------------------------------------- #
class TestSyntheticNegative(unittest.TestCase):
    def test_all_negative_samples(self):
        for sid, (asm, code, tags) in NEGATIVE.items():
            with self.subTest(sample=sid):
                data = _assemble(asm)
                dest = _tmpdir('neg-' + sid)
                try:
                    report = T.translate(data, dest)
                except T.Rejected as exc:
                    self.fail(f'{sid}: top-level {exc.code}, expected per-unit {code}')
                self.assertEqual(report['status'], 'UNSUPPORTED', sid)
                self.assertEqual(report['validated_units'], 0, sid)
                self.assertEqual(report['unsupported_units'], 1, sid)
                self.assertFalse(report['full_shader_emitted'])
                self.assertFalse(report['hardware_execution_validated'])
                unit = report['instructions'][0]
                self.assertEqual(unit['status'], 'UNSUPPORTED', sid)
                self.assertEqual(unit['code'], code, f'{sid}: {unit}')
                self.assertEqual(unit['source_offset'], 0, sid)
                # fail-closed: no fragment written for a rejected unit
                self.assertEqual(list(dest.glob('unit-*.bin')), [], sid)
                _result(sid, sample_class='negative', tags=tags,
                        source_bytes=len(data), source_sha256=_sha256_bytes(data),
                        observed='UNSUPPORTED', code=unit['code'])

    def test_unknown_invalid_opcode_is_opcode_unsupported(self):
        """16 zero bytes decode (exit 0) to an IGA ``illegal`` op -> rejected."""
        data = (SAMPLES / 'raw' / 'unknown_invalid_opcode.bin').read_bytes()
        dec = _decoded_unit(data)
        self.assertEqual(dec['exit'], 0)
        self.assertEqual([i['op'] for i in dec['instructions']], ['illegal'])
        report, rejected = _translate(data, 'unknown')
        self.assertIsNone(rejected)
        self.assertEqual(report['status'], 'UNSUPPORTED')
        self.assertEqual(report['instructions'][0]['code'], 'OPCODE_UNSUPPORTED')
        _result('unknown_invalid_opcode', sample_class='unknown',
                tags=['unknown-invalid-opcode'], source_bytes=len(data),
                source_sha256=_sha256_bytes(data), observed='UNSUPPORTED',
                code='OPCODE_UNSUPPORTED', decoded_op='illegal')


# --------------------------------------------------------------------------- #
# branch out-of-range
# --------------------------------------------------------------------------- #
class TestBranchOutOfRange(unittest.TestCase):
    def test_out_of_range_branch_is_rejected(self):
        data = (SAMPLES / 'raw' / 'branch_jmpi_out_of_range.bin').read_bytes()
        self.assertEqual(len(data), 16)
        # IGA itself refuses the out-of-range target (decode exit non-zero) ...
        dec = _decoded_unit(data)
        self.assertNotEqual(dec['exit'], 0)
        # ... and the translator fail-closes before any relocation attempt.
        report, rejected = _translate(data, 'oob')
        self.assertIsNotNone(rejected)
        self.assertEqual(rejected.code, 'SOURCE_INVALID')
        self.assertIn('targets after kernel end', rejected.detail)
        d = rejected.as_dict()
        self.assertEqual(d['status'], 'UNSUPPORTED')
        self.assertEqual(d['code'], 'SOURCE_INVALID')
        _result('branch_jmpi_out_of_range', sample_class='negative',
                tags=['branch-out-of-range'], source_bytes=len(data),
                source_sha256=_sha256_bytes(data), observed='REJECTED',
                code='SOURCE_INVALID')

    def test_in_range_branch_still_rejected_by_relocation_gate(self):
        data = _assemble(NEGATIVE['branch_jmpi'][0])
        report, rejected = _translate(data, 'inrange')
        self.assertIsNone(rejected)
        self.assertEqual(report['instructions'][0]['code'], 'BRANCH_RELOCATION_UNSUPPORTED')


# --------------------------------------------------------------------------- #
# lengths through the public entry point
# --------------------------------------------------------------------------- #
class TestLengthRejection(unittest.TestCase):
    CASES = [
        ('len_zero', b'', 'INVALID_LENGTH', None),
        ('len_oversize', b'\x00' * (1 << 20), 'INVALID_LENGTH', None),  # filled below
        ('len_trunc_4', b'\x00' * 4, 'TRUNCATED', 0),
        ('len_trunc_native_8', b'\x01\x00\x60\x00' + b'\x00' * 4, 'TRUNCATED', 0),
        ('len_trunc_compact_12', b'\x01\x0b\x01\x20\x07\x7c\x05\x00' + b'\x00' * 4, 'TRUNCATED', 8),
    ]

    def test_all(self):
        for sid, data, code, off in self.CASES:
            if sid == 'len_oversize':
                data = b'\x00' * (T.MAX_BYTES + 1)
            with self.subTest(case=sid):
                report, rejected = _translate(data, sid)
                self.assertIsNone(report, sid)
                self.assertEqual(rejected.code, code, sid)
                self.assertEqual(rejected.offset, off, sid)
                _result(sid, sample_class='negative', tags=['framing-length'],
                        source_bytes=len(data), observed='REJECTED', code=code,
                        offset=off)


# --------------------------------------------------------------------------- #
# SWSB auto-deps drains
# --------------------------------------------------------------------------- #
class TestSwsbDrains(unittest.TestCase):
    def _validated_units(self):
        units = []
        for sid in ('mov_native_f', 'mov_compact_f', 'add_f', 'mul_f', 'simd16_add'):
            data = _assemble(POSITIVE[sid][0])
            report, rejected = _translate(data, 'drain-' + sid)
            self.assertIsNone(rejected)
            units.append((sid, report['instructions'][0]))
        return units

    def test_drain_shape_is_expected(self):
        total = 0
        for sid, unit in self._validated_units():
            self.assertGreaterEqual(unit['target_length'], 16 + 16 * len(unit['synthesized_dependency_drains']),
                                    sid)
            for drain in unit['synthesized_dependency_drains']:
                self.assertEqual((drain.get('op'), drain.get('subop'), drain.get('es'),
                                  drain.get('wren'), drain.get('regDist'), drain.get('sbid')),
                                 ('sync', 'nop', 1, True, '@1', None), f'{sid}: {drain}')
                self.assertEqual(drain.get('srcs'),
                                 [{'kind': 'RD', 'reg': {'rn': 'null'}, 'type': 'ub'}],
                                 f'{sid}: {drain}')
                total += 1
        self.assertGreater(total, 0, 'no auto-deps drains observed at all')
        _result('swsb_drains', observed=f'{total} drains validated',
                code='nop', tag='swsb-drains')

    def test_dependency_policy_reported(self):
        data = _assemble(POSITIVE['add_f'][0])
        report, rejected = _translate(data, 'policy')
        self.assertIsNone(rejected)
        unit = report['instructions'][0]
        self.assertIn('swsb', unit)
        self.assertIn('auto-deps', unit['swsb']['policy'])
        self.assertIn(unit['swsb']['regDist'], (None, '@1'))


# --------------------------------------------------------------------------- #
# mock-injected round-trip / drain / decode failures
# --------------------------------------------------------------------------- #
class TestMockInjections(unittest.TestCase):
    @staticmethod
    def _mov():
        return _assemble(POSITIVE['mov_native_f'][0])

    def _mutating_decode(self, mutate):
        real = T.decode

        def wrapper(data, platform, directory):
            r = real(data, platform, directory)
            if platform == TGT_PLATFORM:
                r = mutate(r)
            return r
        return wrapper

    def test_semantic_roundtrip_mismatch(self):
        """Mutate a *decoded target operand*; the operand compare must fire."""
        def mutate(r):
            r = dict(r)
            r['instructions'] = [copy.deepcopy(i) for i in r['instructions']]
            r['instructions'][0]['dst']['reg']['r'] += 1
            return r
        with mock.patch.object(T, 'decode', self._mutating_decode(mutate)):
            report, rejected = _translate(self._mov(), 'mock-sem')
        self.assertIsNone(rejected)
        self.assertEqual(report['status'], 'UNSUPPORTED')
        self.assertEqual(report['instructions'][0]['code'], 'SEMANTIC_ROUNDTRIP_MISMATCH')
        _result('mock_semantic_roundtrip', sample_class='negative',
                tags=['roundtrip-mock-injection'], observed='UNSUPPORTED',
                code='SEMANTIC_ROUNDTRIP_MISMATCH')

    def test_binary_roundtrip_mismatch(self):
        """Corrupt the bytes the re-encoder writes; the byte compare must fire."""
        real = T.invoke

        def fake(args):
            rc, so, se = real(args)
            if '-a' in args and '-Xauto-deps' not in args and '-o' in args:
                Path(args[args.index('-o') + 1]).write_bytes(b'\xde\xad\xbe\xef')
            return rc, so, se
        with mock.patch.object(T, 'invoke', fake):
            report, rejected = _translate(self._mov(), 'mock-bin')
        self.assertIsNone(rejected)
        self.assertEqual(report['status'], 'UNSUPPORTED')
        self.assertEqual(report['instructions'][0]['code'], 'BINARY_ROUNDTRIP_MISMATCH')
        _result('mock_binary_roundtrip', sample_class='negative',
                tags=['roundtrip-mock-injection'], observed='UNSUPPORTED',
                code='BINARY_ROUNDTRIP_MISMATCH')

    def test_drain_regdist_mismatch(self):
        def mutate(r):
            r = dict(r)
            r['instructions'] = [copy.deepcopy(i) for i in r['instructions']]
            if len(r['instructions']) > 1:
                r['instructions'][1]['regDist'] = '@2'
            return r
        with mock.patch.object(T, 'decode', self._mutating_decode(mutate)):
            report, rejected = _translate(self._mov(), 'mock-drain')
        self.assertIsNone(rejected)
        self.assertEqual(report['instructions'][0]['code'], 'UNEXPECTED_SWSB_SYNTHESIS')
        _result('mock_drain_regdist', sample_class='negative', tags=['swsb-drains'],
                observed='UNSUPPORTED', code='UNEXPECTED_SWSB_SYNTHESIS')

    def test_drain_sync_operand_mismatch(self):
        def mutate(r):
            r = dict(r)
            r['instructions'] = [copy.deepcopy(i) for i in r['instructions']]
            if len(r['instructions']) > 1:
                r['instructions'][1]['srcs'] = [
                    {'kind': 'RD', 'reg': {'rn': 'r', 'r': 1}, 'type': 'ub'}]
            return r
        with mock.patch.object(T, 'decode', self._mutating_decode(mutate)):
            report, rejected = _translate(self._mov(), 'mock-sync')
        self.assertIsNone(rejected)
        self.assertEqual(report['instructions'][0]['code'], 'UNEXPECTED_SYNC_OPERAND')
        _result('mock_drain_sync_operand', sample_class='negative', tags=['swsb-drains'],
                observed='UNSUPPORTED', code='UNEXPECTED_SYNC_OPERAND')

    def test_empty_target_decode_fails_closed(self):
        def mutate(r):
            r = dict(r)
            r['instructions'] = []
            return r
        with mock.patch.object(T, 'decode', self._mutating_decode(mutate)):
            report, rejected = _translate(self._mov(), 'mock-empty')
        self.assertIsNone(rejected)
        self.assertEqual(report['instructions'][0]['code'], 'TARGET_DECODE_FAILED')
        _result('mock_target_decode_empty', sample_class='negative',
                tags=['target-decode-gate'], observed='UNSUPPORTED',
                code='TARGET_DECODE_FAILED')


# --------------------------------------------------------------------------- #
# real PS/VS captures
# --------------------------------------------------------------------------- #
class TestRealShaders(unittest.TestCase):
    PS_CODES = {0: 'OPCODE_UNSUPPORTED', 16: 'EXECUTION_OPTION_UNSUPPORTED',
                32: 'OPCODE_UNSUPPORTED', 48: 'OPCODE_UNSUPPORTED',
                64: 'OPCODE_UNSUPPORTED', 80: 'SEND_EOT_SEMANTICS_UNPROVEN',
                136: 'SEND_EOT_SEMANTICS_UNPROVEN'}
    VS_CODES = {0: 'SPECIAL_REGISTER_UNSUPPORTED', 32: 'OPCODE_UNSUPPORTED',
                40: 'OPCODE_UNSUPPORTED', 56: 'OPCODE_UNSUPPORTED',
                72: 'OPCODE_UNSUPPORTED', 216: 'SPECIAL_REGISTER_UNSUPPORTED',
                240: 'EXECUTION_OPTION_UNSUPPORTED',
                256: 'SEND_EOT_SEMANTICS_UNPROVEN',
                272: 'SEND_EOT_SEMANTICS_UNPROVEN'}

    def _check(self, path, sha, validated, unsupported, codes, tag):
        self.assertTrue(path.is_file(), f'missing capture {path}')
        data = path.read_bytes()
        self.assertEqual(_sha256_bytes(data), sha, f'{path} changed')
        dest = _tmpdir('real-' + tag)
        report = T.translate(data, dest)
        self.assertEqual(report['status'], 'UNSUPPORTED')
        self.assertFalse(report['full_shader_emitted'])
        self.assertFalse(report['hardware_execution_validated'])
        self.assertEqual(report['validated_units'], validated)
        self.assertEqual(report['unsupported_units'], unsupported)
        by_off = {u['source_offset']: u for u in report['instructions']}
        for off, code in codes.items():
            self.assertEqual(by_off[off]['code'], code, f'{tag} +0x{off:x}')
        # every validated unit has a real artifact and a decoded target
        for u in report['instructions']:
            if u['status'] == 'ROUNDTRIP_VALIDATED':
                art = dest / u['artifact']
                self.assertTrue(art.is_file())
                self.assertEqual(art.read_bytes().hex(), u['target_bytes'])
                self.assertGreaterEqual(u['target_length'], 16)
                dec = T.decode(art.read_bytes(), TGT_PLATFORM, _tmpdir('realred-' + tag))
                self.assertEqual(T.normalized(dec['instructions'][0]), T.normalized(u['target']))
        _result(tag, sample_class='real', tags=[f'real-{tag}-shader'],
                source_bytes=len(data), source_sha256=sha, observed=report['status'],
                validated_units=report['validated_units'],
                unsupported_units=report['unsupported_units'],
                rejected_codes=codes, whole_program_rejected=True)
        return report

    def test_ps_shader_whole_rejected(self):
        self._check(PS_CAPTURE, PS_SHA256, 4, 7, self.PS_CODES, 'ps')

    def test_vs_shader_whole_rejected(self):
        self._check(VS_CAPTURE, VS_SHA256, 15, 9, self.VS_CODES, 'vs')


# --------------------------------------------------------------------------- #
# report shape / whitelist completeness
# --------------------------------------------------------------------------- #
class TestReportShape(unittest.TestCase):
    def test_report_and_rejection_shapes(self):
        data = _assemble(POSITIVE['mov_native_f'][0])
        dest = _tmpdir('shape')
        report = T.translate(data, dest)
        for key in ('status', 'full_shader_emitted', 'scope', 'source_sha256',
                    'source_bytes', 'instructions', 'validated_units',
                    'unsupported_units', 'hardware_execution_validated'):
            self.assertIn(key, report)
        self.assertFalse(report['full_shader_emitted'])
        self.assertEqual(report['source_sha256'], _sha256_bytes(data))
        self.assertEqual(report['source_bytes'], len(data))
        self.assertTrue((dest / 'report.json').is_file())
        # ad-hoc rejection dict
        with self.assertRaises(T.Rejected) as cm:
            T.frames(b'')
        self.assertEqual(set(cm.exception.as_dict()),
                         {'status', 'code', 'detail', 'source_offset'})

    def test_required_categories_covered(self):
        covered = set()
        for _sid, (_asm, tags) in POSITIVE.items():
            covered.update(tags)
        for _sid, (_asm, _code, tags) in NEGATIVE.items():
            covered.update(tags)
        covered.update(['framing-length', 'branch-out-of-range',
                        'unknown-invalid-opcode', 'send-eot-rejection',
                        'swsb-drains', 'roundtrip-mock-injection',
                        'real-ps-shader', 'real-vs-shader'])
        missing = REQUIRED_CATEGORIES - covered
        self.assertEqual(missing, set(), f'uncovered categories: {sorted(missing)}')


# --------------------------------------------------------------------------- #
# coverage manifest
# --------------------------------------------------------------------------- #
def _build_manifest(observed):
    categories = {}

    def add(cat, sid):
        categories.setdefault(cat, [])
        if sid not in categories[cat]:
            categories[cat].append(sid)

    def sample_entry(sid, cls, tags, relpath):
        asm_or_bin = (SAMPLES / relpath)
        raw = asm_or_bin.read_bytes() if asm_or_bin.is_file() else b''
        return {
            'id': sid, 'class': cls, 'categories': tags, 'file': str(relpath),
            'file_sha256': _sha256_bytes(raw),
        }

    samples = []
    for sid, (asm, tags) in POSITIVE.items():
        for c in tags:
            add(c, sid)
        e = sample_entry(sid, 'positive', tags, f'positive/{sid}.asm')
        e['expected'] = {'unit_status': 'ROUNDTRIP_VALIDATED', 'whole_report': 'ROUNDTRIP_VALIDATED'}
        e.update(observed.get(sid, {}))
        samples.append(e)
    for sid, (asm, code, tags) in NEGATIVE.items():
        for c in tags:
            add(c, sid)
        e = sample_entry(sid, 'negative', tags, f'negative/{sid}.asm')
        e['expected'] = {'unit_status': 'UNSUPPORTED', 'code': code}
        e.update(observed.get(sid, {}))
        samples.append(e)

    # raw/unknown + out-of-range
    add('unknown-invalid-opcode', 'unknown_invalid_opcode')
    e = sample_entry('unknown_invalid_opcode', 'unknown', ['unknown-invalid-opcode'],
                     'raw/unknown_invalid_opcode.bin')
    e['expected'] = {'unit_status': 'UNSUPPORTED', 'code': 'OPCODE_UNSUPPORTED',
                     'decoded_opcode': 'illegal'}
    e.update(observed.get('unknown_invalid_opcode', {}))
    samples.append(e)

    add('branch-out-of-range', 'branch_jmpi_out_of_range')
    e = sample_entry('branch_jmpi_out_of_range', 'negative', ['branch-out-of-range'],
                     'raw/branch_jmpi_out_of_range.bin')
    e['expected'] = {'top_level': 'REJECTED', 'code': 'SOURCE_INVALID'}
    e.update(observed.get('branch_jmpi_out_of_range', {}))
    samples.append(e)

    # length cases
    length_cases = []
    for sid, _data, code, off in TestLengthRejection.CASES:
        add('framing-length', sid)
        length_cases.append({'id': sid, 'expected_code': code, 'expected_offset': off,
                             **observed.get(sid, {})})

    # eligibility unit cases
    elig = []
    for name, code in [
        ('branch', 'BRANCH_RELOCATION_UNSUPPORTED'),
        ('send', 'SEND_EOT_SEMANTICS_UNPROVEN'),
        ('eot', 'SEND_EOT_SEMANTICS_UNPROVEN'),
        ('unknown_opcode', 'OPCODE_UNSUPPORTED'),
        ('execution_option', 'EXECUTION_OPTION_UNSUPPORTED'),
        ('operand_kind', 'OPERAND_UNSUPPORTED'),
        ('special_register', 'SPECIAL_REGISTER_UNSUPPORTED'),
        ('type', 'TYPE_UNSUPPORTED'),
        ('immediate_nonfinite', 'IMMEDIATE_BITS_UNPROVEN'),
        ('integer_alu', 'INTEGER_ALU_UNPROVEN'),
        ('type_conversion', 'TYPE_CONVERSION_UNPROVEN'),
    ]:
        elig.append({'id': f'eligibility_{name}', 'expected_code': code})

    mock_cases = []
    for sid, (code, cat) in MOCK_CASES.items():
        add(cat, sid)
        mock_cases.append({'id': sid, 'expected_code': code, 'category': cat,
                           **observed.get(sid, {})})

    # positive SWSB drain-shape validation is observed, not a sample
    swsb_validation = dict(observed.get('swsb_drains', {}))
    if swsb_validation:
        add('swsb-drains', 'swsb_drain_validation')
        swsb_validation['id'] = 'swsb_drain_validation'
        swsb_validation['expected_code'] = 'AUTO_DEPS_DRAIN_SHAPE'
        swsb_validation.setdefault('tags', ['swsb-drains'])

    real = []
    for tag, sha, val, uns in [('ps', PS_SHA256, 4, 7), ('vs', VS_SHA256, 15, 9)]:
        add(f'real-{tag}-shader', tag)
        real.append({'id': tag, 'capture_sha256': sha,
                     'expected_validated_units': val,
                     'expected_unsupported_units': uns,
                     'whole_program_rejected': True,
                     **observed.get(tag, {})})

    return {
        'schema': 'ga32-isa-lab/translator-coverage/1',
        'description': 'Executable coverage of the fail-closed IGA-backed instruction '
                       'subset translator. Pure software; no hardware, GPU or device.',
        'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'hardware_execution_validated': False,
        'translator': {'path': str(TRANSLATOR.relative_to(LAB)),
                       'sha256': _sha256_file(TRANSLATOR)},
        'iga': {'path': str(IGA_EXE.relative_to(LAB)), 'sha256': _sha256_file(IGA_EXE)},
        'platforms': {'source': SRC_PLATFORM, 'target': TGT_PLATFORM},
        'required_categories': sorted(REQUIRED_CATEGORIES),
        'categories': {k: categories[k] for k in sorted(categories)},
        'synthetic_samples': samples,
        'length_cases': length_cases,
        'eligibility_cases': elig,
        'mock_injection_cases': mock_cases,
        'swsb_drain_validation': swsb_validation,
        'real_shaders': real,
        'observed': observed,
    }


if __name__ == '__main__':
    unittest.main(verbosity=2)
