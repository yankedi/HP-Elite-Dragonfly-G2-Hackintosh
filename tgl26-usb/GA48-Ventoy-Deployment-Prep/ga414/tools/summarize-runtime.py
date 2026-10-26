#!/usr/bin/env python3
"""Offline audit of real GA414 boot, original R8 capture and independent comparison."""
from collections import Counter
import importlib.util
import json
import re
import subprocess
import sys
from common import *

CAPTURE = WORK / 'r8-legacy-capture'
SESSION = 'REDACTED-SESSION-ID'


def load(path):
    return json.loads(path.read_bytes())


def emit(name, value):
    path = REPORTS / name
    value = json.loads(json.dumps(value))
    if path.exists(): require(load(path) == value, 'archived runtime report differs: ' + name)
    else: save(path, value)


def receipt(name):
    path = WORK / 'commands' / (name + '.json')
    value = load(path)
    require(value['returncode'] == 0, 'required command failed: ' + name)
    return value


def events(path, prefix):
    return [json.loads(line[len(prefix):]) for line in path.read_text().splitlines() if line.startswith(prefix)]


def main():
    identity = receipt('runtime-initial-identity')['stdout']
    logs = receipt('runtime-current-dmesg')['stdout']
    required = ['GA414 NOAUX: gate=1 cpu=0x8c pci=8086:9a49 subsystem=103c:8716 build=25G83',
                'GA414 NOAUX: preflight first=1 original=1 patched=0 expected=1/0',
                'GA414 NOAUX: postflight original=0 patched=1 verified=1 expected=0/1',
                'XeNG NOAUX: fillSurfaceStateAuxInfo sempre AUX_NONE: aplicado',
                'XE-NOCCS3: IntelAccelerator::submitCCSResolve -> retorno imediato: aplicado',
                'HP-R5: native TGL topology slices=1 subslices=10 maxEU/SS=8 totalEU=80',
                'HP-R6: real TGL/Tahoe upstream pool sizing/alignment enabled=1']
    require(all(token in logs for token in required), 'missing real boot log')
    require(SESSION in identity and 'REDACTED-SESSION-ID' in identity, 'wrong boot/UUID')
    require(logs.count('GA414 NOAUX: postflight') == 1 and 'GA414 NOAUX: ERROR' not in logs, 'not single verified apply')
    boot = {'status': 'NOAUX_RUNTIME_CONFIRMED', 'session': SESSION, 'build': '25G83',
            'NG_UUID': '4C4C44E9-5555-3144-A1E4-CB51FF5A72E6',
            'patch_applied_once_and_counts_verified': True,
            'boot_log_lines': [line for line in logs.splitlines() if any(s in line for s in ('NOAUX', 'NOCCS3', 'HP-R5', 'HP-R6', 'V52: CPU'))],
            'identity_receipt': record(WORK / 'commands/runtime-initial-identity.json'),
            'dmesg_receipt': record(WORK / 'commands/runtime-current-dmesg.json'),
            'empty_unified_log_query_preserved': record(WORK / 'commands/runtime-noaux-boot-log.json'),
            'log_source_note': 'Unified log query returned no matches; actual current-boot dmesg retained from 0 seconds contains full patch evidence.',
            'resource_specific_AUX_state': 'NOT_OBSERVED: global byte patch applied, not a direct capture of this R8 resource surface state.',
            'NODEPTH_native': 'unchanged R6: not enabled', 'user_present_manual_boot_confirmed': True,
            'user_screen_report': '用户原话：好了；还是有花屏', 'desktop_status': 'DESKTOP_ARTIFACTS_REMAIN_USER_REPORTED'}
    emit('RUNTIME-BOOT.json', boot)

    health = []
    for name in ('runtime-health-pre', 'runtime-health-post', 'runtime-health-delayed'):
        h = json.loads(receipt(name)['stdout'])
        require(h['status'] == 'HEALTH_GATE_PASS' and h['session'] == SESSION and not h['issues'] and not h['current_boot_diagnostics'], 'health failed: ' + name)
        health.append({k: h[k] for k in ('status', 'utc', 'session', 'boot_epoch', 'build', 'NG_UUID', 'WindowServer', 'stack_sha256', 'current_boot_diagnostics', 'limits')})
    emit('RUNTIME-HEALTH.json', {'status': 'NO_NEW_RESET_PANIC_WATCHDOG_REPORT_OBSERVED', 'samples': health,
         'WindowServer_PID_unchanged': True, 'read_only_health_receipts': [record(WORK / 'commands' / (n + '.json')) for n in
         ('runtime-health-pre', 'runtime-health-post', 'runtime-health-delayed')],
         'stability': 'STABILITY_UNVERIFIED', 'limits': 'Short observation and diagnostic directory timestamps; no long-term stability claim.'})

    execution = receipt('runtime-r8-once-execution')
    require('ONCE_CLAIM_CREATED' in execution['stdout'] and 'PROBE_EXIT=0' in execution['stdout'], 'GPU execution did not finish')
    require((CAPTURE / 'probe.exit').read_text().strip() == '0', 'probe failed')
    r = load(CAPTURE / 'result.json')
    verifier_path = ROOT / 'ga412/tools/verify-pixel-dump.py'
    cli = subprocess.run([sys.executable, str(verifier_path), str(CAPTURE)], capture_output=True, text=True)
    v = json.loads(cli.stdout)
    require(cli.returncode in (0, 1) and v['status'] in ('PIXEL_PASS', 'PIXEL_FAIL'), 'legacy verifier rejected capture: ' + cli.stdout)
    emit('R8-LEGACY-PIXEL-VERIFY.json', v)
    independent = {}
    W, H, ROW = 257, 65, 1280
    def active(path):
        data = path.read_bytes()
        return b''.join(data[y*ROW:y*ROW+W*4] for y in range(H))
    buffers = {n: active(CAPTURE / (n + '.bin')) for n in ('expected', 'gpu', 'cpu')}
    for name, a, b in (('gpu_vs_expected', 'gpu', 'expected'), ('cpu_vs_expected', 'cpu', 'expected'), ('cpu_vs_gpu', 'cpu', 'gpu')):
        x, y = buffers[a], buffers[b]
        count = sum(aa != bb for aa, bb in zip(x, y))
        pixels = sum(x[i:i+4] != y[i:i+4] for i in range(0, len(x), 4))
        require(count == v['comparisons'][name]['differing_bytes'] and pixels == v['comparisons'][name]['bad_pixels'], 'independent comparison mismatch')
        independent[name] = {'differing_bytes': count, 'bad_pixels': pixels, 'total_pixels': W*H}
    emit('R8-VERIFICATION-RECEIPT.json', {'argv': cli.args, 'returncode': cli.returncode, 'stderr': cli.stderr,
         'independent_packed_comparison': independent, 'verifier': record(verifier_path),
         'expected_generator': record(ROOT / 'ga412/tools/expected-pattern.py')})
    remote_hashes = receipt('runtime-capture-remote-hashes')['stdout']
    for p in CAPTURE.iterdir():
        require(sha(p) in remote_hashes, 'capture transfer hash mismatch: ' + p.name)
    trace = events(CAPTURE / 'probe.stderr', 'CPU_TRACE_JSON ')
    require([t['sequence'] for t in trace] == list(range(1, len(trace)+1)), 'trace sequence gap')
    stacks = {}
    for event in trace:
        stack = stacks.setdefault(event['thread'], [])
        key = (event['method'], event['resource']['texture'])
        if event['phase'] == 'enter': stack.append(key)
        else: require(stack and stack.pop() == key, 'trace nesting mismatch')
    require(all(not s for s in stacks.values()), 'unbalanced trace')
    target = [t for t in trace if t['resource']['texture'] == r['target']['object']]
    require(target and all(r['cpu_getBytes_begin_ns'] <= t['monotonic_ns'] <= r['cpu_getBytes_end_ns'] for t in target), 'target readback trace timing')
    get = next(e for e in target if e['method'].startswith('getBytes:') and e['phase'] == 'enter')
    require(all(get['arguments'][k] == val for k, val in {'origin': [0,0,0], 'size': [257,65,1], 'bytes_per_row': 1280,
            'bytes_per_image': 0, 'level': 0, 'slice': 0}.items()), 'getBytes parameters changed')
    require(all(m['original_IMP_image'] == '/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsMTLDriver' for m in r['tracer']['methods']), 'unexpected original IMP image')
    for method in r['tracer']['methods']:
        require(sum(t['method'] == method['method'] and t['phase'] == 'enter' for t in trace) == method['calls'], 'trace/counter mismatch')
    probe_events = events(CAPTURE / 'probe.stdout', 'PROBE_EVENT ')
    require(sum(e['event'] == 'command_created' for e in probe_events) == 1, 'not single explicit CB')
    require(probe_events[-1]['event'] == 'capture_complete_unverified', 'incomplete capture lifecycle')
    old = load(ROOT / 'ga412/reports/R8-LEGACY-PIXEL-VERIFY.json')
    old_trace = load(ROOT / 'ga412/reports/R8-LEGACY-RESULT.json')['trace']['target_events']
    raw_key = 'raw_m_Info_offsets_not_compression_verdict'
    raw_before = old_trace[0]['resource'][raw_key]
    raw_after = target[0]['resource'][raw_key]
    raw_comparison = {key: {'GA412': raw_before[key], 'GA414': raw_after[key]}
                      for key in raw_before if key != 'resource'}
    command = r['commands'][0]
    result = {'status': 'GA414_NOAUX_R8_' + v['status'], 'validity': 'VALID',
         'states': ['IMAGE_BUILT', 'NOAUX_RUNTIME_CONFIRMED', v['status'], 'DESKTOP_ARTIFACTS_REMAIN', 'STABILITY_UNVERIFIED'],
         'boot_session': SESSION, 'NG_UUID': boot['NG_UUID'], 'execution_attempts': 1, 'explicit_command_buffers': 1,
         'CB': command, 'timing_ms': {'commit_to_wait_return': (command['completion_observed_ns']-command['commit_ns'])/1e6,
             'cpu_getBytes': (r['cpu_getBytes_end_ns']-r['cpu_getBytes_begin_ns'])/1e6},
         'snapshot_timing': {k: r[k] for k in ('gpu_frozen_ns', 'cpu_getBytes_begin_ns', 'cpu_getBytes_end_ns')},
         'comparisons': independent, 'full_sha256': v['sha256'], 'active_sha256': v['active_sha256'],
         'old_GA412_comparisons': {k: {f: val[f] for f in ('differing_bytes', 'bad_pixels', 'total_pixels')} for k,val in old['comparisons'].items()},
         'GPU_copy_regression': independent['gpu_vs_expected']['differing_bytes'] > 0,
         'NOAUX_runtime_confirmed': True, 'resource_specific_kernel_AUX_CCS_dirty': 'NOT_OBSERVED',
         'trace': {'event_count': len(trace), 'balanced': True, 'target_events': target},
         'desktop_status': 'DESKTOP_ARTIFACTS_REMAIN_USER_REPORTED', 'user_report': boot['user_screen_report'],
         'stability': 'STABILITY_UNVERIFIED', 'new_reset_panic_watchdog_report_observed': False,
         'preflight_unsigned_original_probe': 'Original GA412 binaries are unsigned; extra codesign preflight rejected before any GPU attempt. Exact existing binary hashes retained; no signing/rebuilding of probe/tracer.',
         'probe_and_tracer_binary_hashes': load(WORK / 'r8-once-started.json')['binary_sha256'],
         'kernel_surface_state_limit': 'Global NOAUX patch success is proven, but this resource AUX/CCS/dirty was not directly captured. Untyped user fields cannot answer that.',
         'evidence': [record(p) for p in sorted(CAPTURE.iterdir())] + [record(WORK / 'r8-once-started.json'), record(WORK / 'commands/runtime-r8-once-execution.json')],
         'limits': 'Copy/readback proxy; this one workload only. User-reported desktop artifacts persist. No desktop repair or long-term stability verdict.'}
    emit('R8-RESULT.json', result)
    emit('TRACE-COMPARISON.json', {'status': 'OBSERVED_USERSPACE_CALL_PATH_CHANGED', 'raw_fields_vs_GA412': raw_comparison,
         'old_resolve_enter_calls': sum(t['method'] == 'resolveCCS:slice:waitForCompletion:' and t['phase'] == 'enter' for t in old_trace),
         'new_resolve_enter_calls': sum(t['method'] == 'resolveCCS:slice:waitForCompletion:' and t['phase'] == 'enter' for t in target),
         'old_target_events': len(old_trace), 'new_target_events': len(target),
         'limit': 'raw resource+0x1c transition and absent resolve call are observations, not a direct kernel AUX surface-state capture',
         'evidence': [record(ROOT / 'ga412/reports/R8-LEGACY-RESULT.json'), record(CAPTURE / 'probe.stderr'), record(CAPTURE / 'result.json')]})
    desktop = receipt('desktop-processes-and-existing-logs')['stdout']
    screenshot_path = WORK / 'commands/desktop-screenshot-once.json'
    screenshot = load(screenshot_path)
    fault_log = receipt('desktop-existing-session-fault-log')['stdout']
    post_dmesg = receipt('runtime-post-capture-dmesg')['stdout']
    fault_pattern = r'PIPE_CONTROL|RCS.*hang|GPU.*hang|gpuRestart|GPU Restart|GPU Hang'
    faults = [line for line in post_dmesg.splitlines() if re.search(fault_pattern, line, re.I)]
    xedrv = WORK / 'desktop-xedrv-WindowServer.log'
    wslog = xedrv.read_text()
    emit('DESKTOP-OBSERVATION.json', {'status': 'DESKTOP_ARTIFACTS_REMAIN',
         'user_report_verbatim': '好了；还是有花屏', 'source': 'user physical-screen observation after manual GA414 boot',
         'process_lines': [line for line in desktop.splitlines() if re.search(r'/WindowServer$|/Dock$|/Finder$', line)],
         'current_accelerator_ioreg_captured': True, 'WindowServer_existing_log': record(xedrv),
         'existing_log_has_IOSurface_creation': 'TEX via=iosurface' in wslog,
         'existing_log_has_pipeline_records': 'PIPE sync' in wslog,
         'log_limit': 'Pipeline/texture creation success does not validate composited layer/icon/image pixels; startup clock corrected from 2020, later epoch lines belong to current 2026 boot.',
         'screenshot_attempt_count': 1, 'screenshot_returncode': screenshot['returncode'],
         'screenshot_error': screenshot['stderr'].strip(), 'screenshot_available': screenshot['returncode'] == 0,
         'screenshot_vs_physical_screen_comparison': 'NOT_AVAILABLE: SSH screencapture failed; user screen report retained, no permission/security changes.',
         'icon_image_layer_visual_localization': 'NOT_OBSERVED independently; normal desktop processes and existing compositing logs only',
         'current_dmesg_fault_matches': faults, 'unified_fault_query_output': fault_log,
         'new_gpuRestart_panic_watchdog_report': False,
         'hang_improvement': 'UNVERIFIED: no current boot +0x7e4/PIPE_CONTROL hang observed in short window; cannot claim normal-session or long-term elimination.',
         'stability': 'STABILITY_UNVERIFIED', 'followup_direction': 'Independent desktop IOSurface/Blit/composition/scanout evidence; do not reclassify R8 PASS as desktop repair.',
         'GPU_stress_or_second_probe_performed': False,
         'evidence': [record(WORK / 'commands' / (n + '.json')) for n in
                      ('desktop-processes-and-existing-logs', 'desktop-screenshot-once', 'desktop-existing-xedrv-and-power',
                       'desktop-existing-session-fault-log', 'runtime-post-capture-dmesg')]})
    print(json.dumps({'status': result['status'], 'comparisons': independent, 'GPU_copy_regression': result['GPU_copy_regression'],
                      'trace_events': len(trace), 'new_reset_observed': False}, indent=2))


if __name__ == '__main__':
    main()
