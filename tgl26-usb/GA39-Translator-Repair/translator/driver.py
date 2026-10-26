#!/usr/bin/env python3
"""Default-Strict facade around a separately built, offline research generator.

Strict refuses unproved whole shaders. Research is explicit and tagged, with
fresh decode/roundtrip/GA38 revalidation. No device or deployment backend exists.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT39 = Path(__file__).resolve().parents[1]
BASE = ROOT39 / 'validator/ga38'
for part in ['tools', 'corpus', 'ir', 'dependency', 'validator']:
    sys.path.insert(0, str(BASE / part))
from common import Rejected, dump, load, output_root, sha
from validate_candidate import run as validate_candidate
sys.path.insert(0, str(ROOT39 / 'translator'))
from translate_unit import invoke
from trust import baseline_inputs, bounded
from semantic_bundle import build as semantic_bundle
spec = importlib.util.spec_from_file_location('ga39_closed_policy', ROOT39 / 'translator/strict-policy/policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def native_generator():
    """Bind executable, selected build cell, source receipt and exact source pins."""
    try:
        config = load(ROOT39 / 'translator/research-mode/generator.json')
        pins = {'source_pin': '1010490d3421628c9d6fd0bd518b6c4b6f8ee33c',
                'mesa_pin': '863338275d915e867319c3690ffd3272b06303c3'}
        if any(config.get(k) != v for k, v in pins.items()):
            raise Rejected('NATIVE_SOURCE_PIN', 'Unexpected translator or Mesa source pin')
        receipts = {}
        for key in ['provenance', 'build_receipt']:
            path = output_root(ROOT39 / config[key])
            raw = bounded(path)
            if sha(raw) != config[key + '_sha256']:
                raise Rejected('NATIVE_RECEIPT_HASH', key)
            receipts[key] = json.loads(raw)
        origin = receipts['provenance']['pins']
        if origin['translator_commit'] != pins['source_pin'] or origin['mesa_commit'] != pins['mesa_pin']:
            raise Rejected('NATIVE_PROVENANCE_PIN', 'Receipt does not match source pins')
        binary = output_root(ROOT39 / config['path'])
        if sha(bounded(binary)) != config['sha256']:
            raise Rejected('NATIVE_GENERATOR_HASH', str(binary))
        cells = [c for c in receipts['build_receipt']['cells'] if c['cell'] == config['cell']]
        if len(cells) != 1 or cells[0]['exit'] != 0 or cells[0]['binary_sha256'] != config['sha256']:
            raise Rejected('NATIVE_BUILD_BINDING', 'Selected successful build does not bind binary')
        return binary, config
    except Rejected:
        raise
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise Rejected('NATIVE_IDENTITY_IO_OR_SCHEMA', str(exc)) from exc


def run(shader, destination, mode='strict', baseline=None):
    if mode not in {'strict', 'research'}:
        raise Rejected('MODE_INVALID', str(mode))
    if shader not in {'PS0', 'PS-KP1', 'PS-KP2', 'VS'}:
        raise Rejected('SHADER_UNSUPPORTED', shader)
    destination = output_root(Path(destination))
    if destination.exists():
        raise Rejected('OUTPUT_EXISTS', str(destination))
    baseline = baseline or ROOT39 / 'candidates/baseline/replay-003'
    try:
        data, source, candidate, comparison, schedule, messages, fixed = baseline_inputs(baseline, shader)
    except Rejected:
        raise
    except (OSError, KeyError, TypeError, ValueError, StopIteration) as exc:
        raise Rejected('BASELINE_SCHEMA_OR_IO', str(exc)) from exc
    report = policy.preflight(source, candidate, comparison, schedule)
    report['mode'] = mode
    destination.mkdir(parents=True)
    (destination / 'source.bin').write_bytes(data)
    begin = time.monotonic()
    stage = destination / '.research-stage-NOT_FOR_HARDWARE'
    work = destination / 'research-NOT_FOR_HARDWARE'
    try:
        bundle = semantic_bundle(source, candidate, *messages, comparison['mapping_witness'])
        dump(destination / 'semantic-bundle.json', bundle)
        report['semantic_bundle'] = 'semantic-bundle.json'
        report['semantic_bundle_sha256'] = sha((destination / 'semantic-bundle.json').read_bytes())
        if mode == 'research':
            binary, identity = native_generator()
            stage.mkdir()
            (stage / 'NOT_FOR_HARDWARE.txt').write_text('UNPROVEN OFFLINE RESEARCH CANDIDATE; NEVER DEPLOY\n')
            output = stage / 'candidate.NOT_FOR_HARDWARE.bin'
            cmd = [str(binary), 'xlate', str(destination / 'source.bin'), str(output)]
            env = {k: v for k, v in os.environ.items() if k not in {'LD_PRELOAD', 'LD_AUDIT', 'LD_LIBRARY_PATH'}}
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            p = subprocess.run(cmd, env=env, capture_output=True, timeout=30)
            (stage / 'stdout.txt').write_bytes(p.stdout)
            (stage / 'stderr.txt').write_bytes(p.stderr)
            dump(stage / 'generation.json', {'command': cmd, 'exit': p.returncode, 'generator': identity,
                 'source_sha256': sha(data), 'stdout_sha256': sha(p.stdout), 'stderr_sha256': sha(p.stderr)})
            if p.returncode or not output.is_file():
                raise Rejected('RESEARCH_GENERATOR_FAILURE', shader)
            raw = bounded(output, 1 << 20)
            review = validate_candidate(shader, output, None, stage / 'ga38-review')
            report['mapping_failure'] = review.get('mapping_failure')
            report['mapping_unresolved_reason'] = review['mapping_witness'].get('unresolved_reason')
            if report['mapping_failure'] or report['mapping_unresolved_reason']:
                raise Rejected('RESEARCH_MAPPING_UNPROVEN', str(report['mapping_failure'] or report['mapping_unresolved_reason']))
            fresh = stage / 'ga38-review/analysis'
            current_bundle = semantic_bundle(load(fresh / 'source-ir.json'), load(fresh / 'candidate-ir.json'),
                                            load(fresh / 'source-messages.json'), load(fresh / 'candidate-messages.json'),
                                            review['mapping_witness'])
            dump(stage / 'semantic-bundle.json', current_bundle)
            text = invoke(['-d', '-p=12p1', output], stage / 'roundtrip/decode').stdout
            asm, reencoded = stage / 'target.asm', stage / 'roundtrip.bin'
            asm.write_bytes(text)
            invoke(['-a', '-p=12p1', asm, '-o', reencoded], stage / 'roundtrip/encode')
            if reencoded.read_bytes() != raw:
                raise Rejected('RESEARCH_ROUNDTRIP_BYTES_DIFFER', shader)
            report.update(research_candidate_sha256=sha(raw), research_candidate_bytes=len(raw),
                       research_only=True, full_shader_emitted=True, verified_executable_program_emitted=False,
                       research_program_generated=True, candidate_equivalence_proven=False,
                       research_validation_state='MAPPED_DECODED_ROUNDTRIPPED_NOT_SEMANTICALLY_PROVEN',
                       baseline_bytes_unchanged=sha(raw) == fixed['candidate']['sha256'],
                       fresh_ga38_comparison_counts=review['counts'])
            report['elapsed_seconds'] = time.monotonic() - begin
            # All fallible report writes precede the single publication rename.
            # No post-publication root write can invalidate a committed bundle.
            dump(stage / 'report.json', report)
            dump(destination / 'report.json', report)
            stage.rename(work)
        else:
            report['elapsed_seconds'] = time.monotonic() - begin
            dump(destination / 'report.json', report)
    except (Rejected, OSError, subprocess.SubprocessError, KeyError, TypeError, ValueError) as exc:
        rejection = exc if isinstance(exc, Rejected) else Rejected('RESEARCH_OR_ANALYSIS_FAILURE', str(exc))
        report.update(rejection=rejection.as_dict(), full_shader_emitted=False,
                      research_program_generated=False, verified_executable_program_emitted=False,
                      research_validation_state='FAILED_NOT_PUBLISHED', elapsed_seconds=time.monotonic() - begin)
        errors = []
        # Best-effort independent failure records. Persistent failure of the root
        # report path must not escape or leave a success report in quarantine.
        for partial in [stage, work]:
            if not partial.exists():
                continue
            quarantine = destination / 'rejected-NOT_FOR_HARDWARE'
            try:
                dump(partial / 'report.json', report)
            except OSError as error:
                errors.append({'path': str(partial / 'report.json'), 'error': str(error)})
                try:
                    (partial / 'report.json').unlink(missing_ok=True)
                except OSError as unlink_error:
                    errors.append({'path': str(partial / 'report.json'), 'error': str(unlink_error)})
            try:
                partial.rename(quarantine)
            except OSError as error:
                errors.append({'path': str(partial), 'error': str(error)})
        if errors:
            report['failure_record_io_errors'] = errors
        try:
            dump(destination / 'report.json', report)
        except OSError as error:
            errors.append({'path': str(destination / 'report.json'), 'error': str(error)})
            report['failure_record_io_errors'] = errors
            try:
                dump(destination / 'failure-report.json', report)
            except OSError as fallback_error:
                errors.append({'path': str(destination / 'failure-report.json'), 'error': str(fallback_error)})
                # The in-memory result remains structured even if all storage
                # writes fail. No claim of a persisted failure record is made.
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--shader', required=True, choices=['PS0', 'PS-KP1', 'PS-KP2', 'VS'])
    ap.add_argument('--mode', choices=['strict', 'research'], default='strict')
    ap.add_argument('--output', required=True, type=Path)
    a = ap.parse_args()
    try:
        report = run(a.shader, a.output, a.mode)
        print(json.dumps({'status': report['status'], 'mode': report['mode'], 'full_shader_emitted': report['full_shader_emitted']}))
        raise SystemExit(0 if a.mode == 'research' and report.get('research_program_generated') else 2)
    except Rejected as e:
        print(json.dumps(e.as_dict(), sort_keys=True))
        raise SystemExit(2)
