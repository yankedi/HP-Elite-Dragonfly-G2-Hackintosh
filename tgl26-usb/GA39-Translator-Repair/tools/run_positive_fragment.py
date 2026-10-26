#!/usr/bin/env python3
"""Persist a genuine accepted finite lowering example, never a full shader."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'translator'))
from translate_unit import invoke, translate, policy


def run(destination):
    destination = destination.resolve()
    if ROOT not in destination.parents or destination.exists():
        raise ValueError('Fresh GA39 output required')
    destination.mkdir(parents=True)
    asm, binary = destination / 'source.asm', destination / 'source.bin'
    asm.write_text('(W) mov (8|M0) r10.0<1>:ud r11.0<8;8,1>:ud\n')
    invoke(['-a', '-p=11', '-Xforce-no-compact', asm, '-o', binary], destination / 'source-encode')
    result = translate(binary.read_bytes(), destination / 'strict-unit')
    if result['status'] != policy.PROVEN:
        raise RuntimeError('Positive control rejected; inspect retained source and target evidence')
    print(json.dumps({'status': result['status'], 'source_sha256': result['source_sha256'],
                      'target_sha256': result['target_sha256'], 'full_shader_emitted': False}, sort_keys=True))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('output', type=Path)
    run(ap.parse_args().output)
