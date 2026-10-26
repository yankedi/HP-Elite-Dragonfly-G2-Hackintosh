"""Negative admission tests do not mutate tools, sources or historical inputs."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for sub in ['tools', 'corpus', 'ir', 'dependency', 'validator']:
    sys.path.insert(0, str(ROOT / sub))
from common import HISTORY, MAX_INSTRUCTIONS, Rejected, dump, frames, load, sha, write_bytes, analysis_run
from corpus import authenticated
from iga_adapter import verify_iga
from integrity import validate_program
from dependency_graph import build_graph
from gen12_schedule_check import check

RUN = analysis_run()


class AdmissionAndIdentity(unittest.TestCase):
    def test_full_commit_version_mismatch(self):
        # A synthetic git identity result, not any change to the real checkout.
        wrong = subprocess.CompletedProcess(['git'], 0, b'c36a5040000000000000000000000000000000000\n', b'')
        with patch('iga_adapter.subprocess.run', return_value=wrong):
            with self.assertRaises(Rejected) as ctx:
                verify_iga(HISTORY / 'tools/iga/build/IGAExe/iga64')
        self.assertEqual(ctx.exception.code, 'TOOL_VERSION_MISMATCH')

    def test_binary_hash_mismatch_without_changing_binary(self):
        original = Path.read_bytes
        binary = HISTORY / 'tools/iga/build/IGAExe/iga64'
        def corrupt_read(path):
            return b'synthetic corrupted tool bytes' if path == binary else original(path)
        with patch.object(Path, 'read_bytes', corrupt_read):
            with self.assertRaises(Rejected) as ctx:
                verify_iga(binary)
        self.assertEqual(ctx.exception.code, 'TOOL_HASH_MISMATCH')

    def test_source_hash_and_endian_errors(self):
        raw = (RUN / 'corpus/source/PS0.bin').read_bytes()
        swapped = b''.join(raw[i:i+4][::-1] for i in range(0, len(raw), 4))
        path = RUN / 'admission-fixtures/swapped-source.bin'
        write_bytes(path, swapped)
        with self.assertRaises(Rejected) as ctx:
            authenticated(path, sha(raw))
        self.assertEqual(ctx.exception.code, 'HASH_MISMATCH')

    def test_bounded_instruction_count(self):
        compact = (1 << 29).to_bytes(4, 'little') + bytes(4)
        with self.assertRaises(Rejected) as ctx:
            frames(compact * (MAX_INSTRUCTIONS + 1))
        self.assertEqual(ctx.exception.code, 'INSTRUCTION_RESOURCE_BOUND')

    def test_symlink_leaf_cannot_overwrite_history(self):
        original = HISTORY / 'analysis/ps-bounded.bin'
        before = sha(original.read_bytes())
        link = RUN / 'admission-fixtures/history-leaf-link.bin'
        link.parent.mkdir(parents=True, exist_ok=True)
        if not link.is_symlink():
            link.symlink_to(original)
        self.assertEqual(link.readlink(), original)
        with self.assertRaises(Rejected) as ctx:
            dump(link, {'must_never_overwrite_history': True})
        self.assertEqual(ctx.exception.code, 'OUTPUT_SCOPE')
        self.assertEqual(sha(original.read_bytes()), before)

    def test_derived_raw_identity_corruption(self):
        program = load(RUN / 'ir/outputs/PS0-source.json')
        program['program_sha256'] = '0' * 64
        with self.assertRaises(Rejected) as ctx:
            validate_program(program)
        self.assertEqual(ctx.exception.code, 'IR_RAW_HASH_MISMATCH')

    def test_deleted_graph_edge_is_rejected(self):
        program = load(RUN / 'ir/outputs/PS0-candidate.json')
        graph = build_graph(program)
        graph['edges'].pop()
        with self.assertRaises(Rejected) as ctx:
            check(program, graph)
        self.assertEqual(ctx.exception.code, 'DEPENDENCY_GRAPH_INTEGRITY')

    def test_wrong_platform_schedule_rejected(self):
        program = load(RUN / 'ir/outputs/PS0-source.json')
        with self.assertRaises(Rejected) as ctx:
            check(program, build_graph(program))
        self.assertEqual(ctx.exception.code, 'PLATFORM_UNSUPPORTED')

    def test_final_audit_n1_all_derived_semantics_reject_tampering(self):
        base = load(RUN / 'ir/outputs/VS-source.json')
        send = next(i for i, n in enumerate(base['nodes']) if n['message_effects']['is_send'])
        mutations = [
            (0, 'numeric_semantics', lambda v: v.update(accumulator=False)),
            (0, 'numeric_semantics', lambda v: v.update(nf=not v['nf'])),
            (send, 'message_effects', lambda v: v.update(is_send=False)),
            (0, 'message_effects', lambda v: v.update(eot=True)),
            (0, 'unresolved_semantics', lambda v: v.clear()),
            (0, 'evidence', lambda v: v.clear()),
        ]
        for index, field, mutate in mutations:
            program = deepcopy(base)
            mutate(program['nodes'][index][field])
            with self.subTest(field=field):
                with self.assertRaises(Rejected) as ctx:
                    validate_program(program)
                self.assertEqual(ctx.exception.code, 'IR_DERIVED_FIELD_MISMATCH')
                self.assertEqual(ctx.exception.detail, field)


if __name__ == '__main__':
    unittest.main(verbosity=2)
