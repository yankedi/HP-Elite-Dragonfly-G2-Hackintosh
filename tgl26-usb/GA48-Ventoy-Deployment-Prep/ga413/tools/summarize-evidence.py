#!/usr/bin/env python3
"""Audit saved runtime evidence and emit shareable GA4.13 summaries offline."""
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PRIVATE = ROOT / 'ga413/private'
CAPTURE = PRIVATE / 'r8-staged-boundary-capture'
REPORTS = ROOT / 'ga413/reports'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_bytes())


def record(path):
    return {'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def events(path, prefix):
    return [json.loads(line[len(prefix):]) for line in path.read_text().splitlines() if line.startswith(prefix)]


def save(name, value):
    path = REPORTS / name
    # Reproducible; never silently replace different archived evidence.
    content = json.dumps(value, indent=2, ensure_ascii=False) + '\n'
    if path.exists():
        require(path.read_text() == content, 'archived report would change: ' + name)
    else:
        path.write_text(content)


def main():
    spec = importlib.util.spec_from_file_location('boundary_comparison', HERE / 'compare-boundaries.py')
    comparison = importlib.util.module_from_spec(spec); spec.loader.exec_module(comparison)
    live_compare = comparison.compare(ROOT / 'ga412/private/r8-legacy-capture', CAPTURE)
    require(json.loads(json.dumps(live_compare)) == read(REPORTS / 'BOUNDARY-COMPARISON.json'),
            'saved comparison differs from recomputation')
    r = read(CAPTURE / 'result.json')
    require((CAPTURE / 'probe.exit').read_text().strip() == '0', 'probe did not exit normally')
    once = read(PRIVATE / 'commands/staged-boundary-once.json')
    require(once['returncode'] == 0 and 'probe_exit=0 post_health_exit=0' in once['stdout'], 'once wrapper failed')
    trace = events(CAPTURE / 'probe.stderr', 'CPU_TRACE_JSON ')
    require([e['sequence'] for e in trace] == list(range(1, 13)), 'trace missing/reordered')
    target = [e for e in trace if e['resource']['texture'] == r['target']['object']]
    expected_methods = [0, 1, 2, 2, 1, 3, 3, 0]
    methods = [entry['method'] for entry in r['tracer']['methods']]
    require([e['method'] for e in target] == [methods[i] for i in expected_methods], 'target call nesting changed')
    require([e['phase'] for e in target] == ['enter', 'enter', 'enter', 'exit', 'exit', 'enter', 'exit', 'exit'], 'target trace phases')
    require(all(r['cpu_getBytes_begin_ns'] <= e['monotonic_ns'] <= r['cpu_getBytes_end_ns'] for e in target), 'target trace outside getBytes')
    args = target[0]['arguments']
    require(all(args[key] == value for key, value in {'origin': [0, 0, 0], 'size': [257, 65, 1],
            'bytes_per_row': 1280, 'bytes_per_image': 0, 'level': 0, 'slice': 0}.items()), 'getBytes arguments changed')
    old_target = read(ROOT / 'ga412/reports/R8-LEGACY-RESULT.json')['trace']['target_events']
    raw_key = 'raw_m_Info_offsets_not_compression_verdict'
    raw = target[0]['resource'][raw_key]
    raw_equal = {k: v for k, v in raw.items() if k != 'resource'} == {
        k: v for k, v in old_target[0]['resource'][raw_key].items() if k != 'resource'}
    require(raw_equal, 'raw observed target fields differ from legacy')
    probe_events = events(CAPTURE / 'probe.stdout', 'PROBE_EVENT ')
    require(sum(e['event'] == 'command_created' for e in probe_events) == 3, 'not three command creations')
    for command in r['commands']:
        observed = [e for e in probe_events if e.get('id') == command['id']]
        require(Counter(e['event'] for e in observed) == Counter([
            'command_created', 'command_commit', 'command_wait_begin', 'command_completed_callback', 'command_wait_returned']),
            'incomplete command event lifecycle')
        receipt = next(e for e in observed if e['event'] == 'command_wait_returned')
        require({k: receipt[k] for k in command} == command, 'stdout/JSON command mismatch')
    require(probe_events[-1]['event'] == 'capture_complete_unverified', 'capture did not finish')

    health_paths = [CAPTURE / 'pre-health.json', CAPTURE / 'post-health.json']
    delayed_path = PRIVATE / 'commands/post-capture-delayed-readonly-health.json'
    delayed_receipt = read(delayed_path)
    require(delayed_receipt['returncode'] == 0, 'delayed health command failed')
    samples = [read(p) for p in health_paths] + [json.loads(delayed_receipt['stdout'])]
    for h in samples:
        require(h['status'] == 'HEALTH_GATE_PASS' and not h['issues'] and not h['current_boot_gpuRestart_reports'], 'health blocked')
        require(h['session'] == 'REDACTED-SESSION-ID', 'boot changed')
    fields = ['status', 'utc', 'issues', 'session', 'boot_epoch', 'build', 'WindowServer', 'uptime',
              'stack_sha256', 'rollback_media', 'current_boot_gpuRestart_reports', 'limits']
    health = {'status': 'NO_NEW_RESET_REPORT_OBSERVED_IN_CAPTURE_WINDOW',
              'samples': [{k: h[k] for k in fields} for h in samples],
              'latest_historical_reset': samples[-1]['all_gpuRestart_reports'][0],
              'receipts': [record(p) for p in health_paths + [delayed_path]],
              'limit': 'Short observation, report-directory mtime and service checks; not a long-term stability verdict.'}
    save('HEALTH-WINDOW.json', health)
    preflight_path = PRIVATE / 'commands/final-preflight-health.json'
    preflight_receipt = read(preflight_path)
    require(preflight_receipt['returncode'] == 0, 'preflight command failed')
    preflight = json.loads(preflight_receipt['stdout'])
    require(preflight['status'] == 'HEALTH_GATE_PASS', 'preflight failed')
    save('PREFLIGHT-HEALTH.json', {'sample': {k: preflight[k] for k in fields},
                                   'full_raw_receipt': record(preflight_path)})

    cpu_trace = events(PRIVATE / 'native-cpu-test.stderr', 'CPU_TRACE_JSON ')
    require(len(cpu_trace) == 128 and len({e['thread'] for e in cpu_trace}) == 4, 'native CPU concurrency coverage incomplete')
    require('CPU_TEST_PASS' in (PRIVATE / 'native-cpu-test.stdout').read_text(), 'native CPU test failed')
    require('CPU_TEST_PASS ABI rejected without partial installation' in (PRIVATE / 'native-bad-abi-test.stdout').read_text(), 'bad ABI test failed')
    abi = read(PRIVATE / 'native-abi.json')
    require(abi['tracer']['installed'] == 1 and abi['GPU_commands_submitted'] is False, 'native ABI inspection failed')
    build = read(PRIVATE / 'commands/native-strict-build-and-cpu.json')
    require(build['returncode'] == 0, 'native build failed')
    native = {'status': 'NATIVE_STRICT_BUILD_CPU_AND_ABI_PASS', 'build_receipt': record(PRIVATE / 'commands/native-strict-build-and-cpu.json'),
              'compiler_flags': ['-fobjc-arc', '-fno-modules', '-Wall', '-Wextra', '-Werror', '-framework Foundation', '-framework Metal'],
              'ABI': abi, 'CPU_events': len(cpu_trace), 'CPU_threads': 4,
              'CPU_result': (PRIVATE / 'native-cpu-test.stdout').read_text().strip(),
              'bad_ABI_result': (PRIVATE / 'native-bad-abi-test.stdout').read_text().strip(),
              'artifacts': [record(PRIVATE / name) for name in ['native-managed-rt-probe', 'native-trace-managed-cpu.dylib',
                  'native-inspect-texture-abi', 'native-abi.json', 'native-cpu-test.stdout', 'native-cpu-test.stderr',
                  'native-bad-abi-test.stdout', 'native-bad-abi-test.stderr']],
              'sources': [record(ROOT / p) for p in ['ga413/tools/managed-rt-probe.m', 'ga413/tools/build-darwin.sh',
                  'ga412/tools/trace-managed-cpu.m', 'ga412/tools/inspect-texture-abi.m', 'ga412/tools/test-trace-cpu.m']]}
    save('NATIVE-BUILD.json', native)
    result = {'validity': 'VALID', 'pixel_status': live_compare['staged_boundary']['status'],
              'root_cause': 'ROOT_CAUSE_UNVERIFIED', 'goal_id': 'REDACTED-SESSION-ID',
              'boot_session': samples[0]['session'], 'NG_UUID': 'REDACTED-SESSION-ID',
              'probe_execution_attempts': 1, 'explicit_probe_command_buffers': 3,
              'hidden_driver_operations': 'not independently counted',
              'start_utc_receipt': (CAPTURE / 'start.utc').read_text().strip(),
              'end_utc_receipt': (CAPTURE / 'end.utc').read_text().strip(),
              'commands': r['commands'],
              'timing_ms': [{'ordinal': c['ordinal'], 'stage': c['stage'],
                    'commit_to_wait_return': (c['completion_observed_ns'] - c['commit_ns']) / 1e6,
                    'completion_callback_to_wait_return': (c['completion_observed_ns'] - c['completed_callback_ns']) / 1e6}
                  for c in r['commands']],
              'snapshot_timing': {k: r[k] for k in ('gpu_frozen_ns', 'cpu_getBytes_begin_ns', 'cpu_getBytes_end_ns')},
              'trace': {'total_events': len(trace), 'target_events': target, 'observed_raw_fields_match_legacy': raw_equal,
                        'locked_address_return': target[4]['arguments']['return_u64'],
                        'resolve_return': target[3]['arguments']['return_i8'],
                        'limits': 'Address return and untyped raw fields only. Locked bytes, offsets and kernel AUX/CCS/dirty state not captured.'},
              'comparisons': live_compare['staged_boundary']['comparisons'],
              'sha256': live_compare['staged_boundary']['sha256'],
              'active_sha256': live_compare['staged_boundary']['active_sha256'],
              'health': {'new_reset_report_observed': False, 'samples_utc': [h['utc'] for h in samples],
                         'last_WindowServer': samples[-1]['WindowServer'], 'limit': health['limit']},
              'stack_sha256': samples[0]['stack_sha256'],
              'interpretation': live_compare['interpretation'],
              'next_single_step': 'Design bounded own-process capture of the same target locked backing at lock return, map level/slice/base offsets and correlate actual compression/resolve state; offline decode first. A new native/GPU experiment requires its own health/once gates.',
              'evidence': [record(p) for p in sorted(CAPTURE.iterdir()) if p.is_file()] +
                          [record(PRIVATE / 'GPU-ONCE-ATTEMPT.json'), record(PRIVATE / 'commands/staged-boundary-once.json')]}
    save('R8-STAGED-RESULT.json', result)
    print(json.dumps({'validity': result['validity'], 'pixel_status': result['pixel_status'],
                      'explicit_CBs': 3, 'trace_events': len(trace), 'new_reset_report_observed': False,
                      'CPU_bad_pixels': result['comparisons']['cpu_vs_expected']['bad_pixels']}))


if __name__ == '__main__':
    main()
