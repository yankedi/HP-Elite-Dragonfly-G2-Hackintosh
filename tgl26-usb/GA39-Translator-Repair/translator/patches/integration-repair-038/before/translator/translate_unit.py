#!/usr/bin/env python3
"""Actual strict codegen for a small proven integer bit-copy fragment domain.

Output is an isolated NON-DEPLOYABLE fragment with explicit proof premises.
Full shader admission is a separate, stronger API. No NF or SEND fallback.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT39 = Path(__file__).resolve().parents[1]
BASE = ROOT39 / 'validator/ga38'
for sub in ['tools', 'ir']:
    sys.path.insert(0, str(BASE / sub))
from common import Rejected, dump, frames, output_root, sha
from iga_adapter import decode, verify_iga
spec = importlib.util.spec_from_file_location('ga39_policy', ROOT39 / 'translator/strict-policy/policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def invoke(args, directory):
    binary = ROOT39.parent / 'GA32-ISA-Lab/tools/iga/build/IGAExe/iga64'
    tool = verify_iga(binary)
    env = {k: v for k, v in os.environ.items() if k not in {'LD_PRELOAD', 'LD_AUDIT', 'LD_LIBRARY_PATH'}}
    env.update(PYTHONDONTWRITEBYTECODE='1', LD_LIBRARY_PATH=str(Path(tool['library_path']).parent))
    command = [str(binary), *map(str, args)]
    try:
        p = subprocess.run(command, env=env, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Rejected('TOOL_FAILURE', str(e)) from e
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'stdout.txt').write_bytes(p.stdout)
    (directory / 'stderr.txt').write_bytes(p.stderr)
    dump(directory / 'invocation.json', {'command': command, 'exit': p.returncode,
         'stdout_sha256': sha(p.stdout), 'stderr_sha256': sha(p.stderr), 'tool': tool})
    if p.returncode:
        raise Rejected('ENCODER_REJECTED', p.stderr.decode(errors='replace'))
    return p


def projection(ins):
    return {k: v for k, v in ins.items() if k not in {'id', 'kind', 'pc', 'opts'}} | {
        'opts': [x for x in ins.get('opts', []) if x != 'Compacted']}


def emitter(ins):
    yes, reason = policy.integer_mov_eligibility(ins)
    if not yes:
        raise Rejected(reason, 'Outside strict finite bit-copy domain', ins['pc'])
    # Narrow initial theorem: full NoMask SIMD8 contiguous DWORD transfer.
    # Extending this is a new proof obligation, not an automatic format fallback.
    dst, src = ins['dst'], ins['srcs'][0]
    if (ins['es'] != 8 or ins.get('eo', 0) != 0 or ins.get('wren') is not True
            or dst['type'] not in {'d', 'ud'} or dst.get('rgn') != {'h': 1}
            or src.get('rgn') != {'h': 1, 'v': 8, 'w': 8}
            or dst['reg'].get('sr', 0) or src['reg'].get('sr', 0)):
        raise Rejected('BITCOPY_THEOREM_SHAPE_UNSUPPORTED', 'Only full NoMask SIMD8 contiguous DWORD GRF copy')
    dr, sr = dst['reg'].get('r', 0), src['reg'].get('r', 0)
    if dr == sr:
        raise Rejected('SELF_COPY_THEOREM_NOT_REGISTERED', 'Initial theorem uses disjoint GRFs')
    return f'(W) mov (8|M0) r{dr}.0<1>:{dst["type"]} r{sr}.0<8;8,1>:{src["type"]}\n'


def translate(data, destination):
    destination = output_root(Path(destination))
    if destination.exists():
        raise Rejected('OUTPUT_EXISTS', 'Fresh destination required')
    destination.mkdir(parents=True)
    (destination / 'source.bin').write_bytes(data)
    report = {'schema': 'ga39-strict-unit/v1', 'mode': 'strict', 'status': policy.UNKNOWN,
              'source_sha256': sha(data), 'full_shader_emitted': False,
              'artifact_class': 'NOT_FOR_HARDWARE_ISOLATED_FRAGMENT', 'hardware_validated': False}
    try:
        if len(frames(data)) != 1:
            raise Rejected('ISOLATED_UNIT_REQUIRED', 'Never concatenate accepted fragments into a shader')
        decoded = decode(data, '11', destination / 'logs/source')
        ins = decoded['instructions'][0]
        asm_text = emitter(ins)
        with tempfile.TemporaryDirectory(prefix='stage-', dir=destination) as name:
            stage = Path(name)
            asm, binary = stage / 'target.asm', stage / 'target.bin'
            asm.write_text(asm_text)
            invoke(['-a', '-p=12p1', '-Xforce-no-compact', '-Xauto-deps', asm, '-o', binary], destination / 'logs/encode')
            code = binary.read_bytes()
            target = decode(code, '12p1', destination / 'logs/target')
            nodes = target['instructions']
            if len(nodes) not in {1, 2} or projection(ins) != projection(nodes[0]):
                raise Rejected('TARGET_FIELD_EQUIVALENCE_FAILED', 'Raw decoded architectural projection changed')
            for drain in nodes[1:]:
                expected = {'op': 'sync', 'subop': 'nop', 'es': 1, 'wren': True,
                            'regDist': '@1', 'srcs': [{'kind': 'RD', 'reg': {'rn': 'null'}, 'type': 'ub'}]}
                if {k: v for k, v in drain.items() if k not in {'kind', 'pc', 'id'}} != expected:
                    raise Rejected('SYNTHESIZED_WAIT_UNPROVEN', repr(drain))
            decoded_text = invoke(['-d', '-p=12p1', binary], destination / 'logs/target-text').stdout
            roundtrip_asm, roundtrip_bin = stage / 'roundtrip.asm', stage / 'roundtrip.bin'
            roundtrip_asm.write_bytes(decoded_text)
            invoke(['-a', '-p=12p1', '-Xforce-no-compact', roundtrip_asm, '-o', roundtrip_bin], destination / 'logs/roundtrip')
            if roundtrip_bin.read_bytes() != code:
                raise Rejected('ROUNDTRIP_BYTES_DIFFER', 'Target cannot reproduce exact bytes')
            (destination / 'fragment.asm').write_text(asm_text)
            # All necessary checks precede the only public target byte write.
            (destination / 'isolated-fragment.bin').write_bytes(code)
        report.update(status=policy.PROVEN, target_sha256=sha(code), source_bytes=data.hex(), target_bytes=code.hex(),
                      source_fields=ins, target_fields=nodes,
                      source_target_mapping=[{'source_offset': 0, 'target_byte_range': [0, len(code)]}],
                       proof={'rule': 'INTEGER_MOV_CONTIGUOUS_BITCOPY',
                              'conditional_claim': 'all 2^256 source register bit patterns under the listed ISA premises',
                              'machine_checked': ['finite rule eligibility', 'decoded architectural field projection',
                                                  'exact target byte roundtrip', 'optional sync.nop encoding shape'],
                              'isa_semantics_machine_proved': False,
                             'lane_equations': [f'target.dst[{i}*32 +: 32] = source.src[{i}*32 +: 32]' for i in range(8)],
                             'assumptions': ['ICL/TGL same integer MOV bit-copy architectural semantics',
                                              'isolated instruction, all channels execute, no preexisting asynchronous operation',
                                              'auto sync.nop @1 preserves the isolated GRF value projection; not a general SEND completion theorem',
                                             'unmodified pinned IGA faithfully encodes/decodes declared platforms'],
                             'temporary_grf': None, 'NF_numeric_model': 'NOT_APPLICABLE',
                             'resource_ABI': 'NOT_APPLICABLE_TO_ISOLATED_REGISTER_FUNCTION',
                             'not_a_complete_shader_or_GPU_execution_certificate': True})
    except Rejected as exc:
        report['rejection'] = exc.as_dict()
    dump(destination / 'report.json', report)
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('input', type=Path)
    ap.add_argument('output', type=Path)
    a = ap.parse_args()
    if not a.input.is_file():
        raise SystemExit('Ordinary bounded input file required')
    with a.input.open('rb') as f:
        data = f.read((1 << 20) + 1)
    result = translate(data, a.output)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['status'] == policy.PROVEN else 2)
