#!/usr/bin/env python3
"""Final offline audit: real boot, a single original probe CB, pixels and limitations."""
import importlib.util
import json
import re
from common import *


def main():
    def load(path): return json.loads(path.read_bytes())
    result = load(REPORTS / 'R8-RESULT.json')
    boot = load(REPORTS / 'RUNTIME-BOOT.json')
    health = load(REPORTS / 'RUNTIME-HEALTH.json')
    desktop = load(REPORTS / 'DESKTOP-OBSERVATION.json')
    capture = WORK / 'r8-legacy-capture'
    metadata = load(capture / 'result.json')
    command = metadata['commands'][0]
    require(command == load(capture / 'command.json') == result['CB'], 'command receipts disagree')
    spec = importlib.util.spec_from_file_location('ga414_original_verifier', ROOT / 'ga412/tools/verify-pixel-dump.py')
    verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
    verified, code = verifier.audit(capture)
    require(code == 0 and json.loads(json.dumps(verified)) == load(REPORTS / 'R8-LEGACY-PIXEL-VERIFY.json'), 'pixel evidence not reproducible')
    require(result['status'] == 'GA414_NOAUX_R8_PIXEL_PASS' and result['NOAUX_runtime_confirmed'] and not result['GPU_copy_regression'], 'strict result conditions failed')
    require(boot['status'] == 'NOAUX_RUNTIME_CONFIRMED' and boot['session'] == result['boot_session'], 'runtime identity mismatch')
    require(all(not c['differing_bytes'] and not c['bad_pixels'] for c in result['comparisons'].values()), 'pixel mismatches')
    once = load(WORK / 'r8-once-started.json')
    require(once['maximum_execution_attempts'] == 1, 'invalid once contract')
    execution_files = list((WORK / 'commands').glob('runtime-r8-once-execution.json'))
    require(len(execution_files) == 1, 'execution record missing or repeated')
    execution = load(execution_files[0])
    require(execution['returncode'] == 0 and execution['stdout'].count('ONCE_CLAIM_CREATED') == 1, 'execution did not complete once')
    require(execution['command'] == '/bin/bash -c ' + __import__('shlex').quote(once['remote_script']), 'execution/once script differs')
    for name, digest in once['binary_sha256'].items():
        require(sha(ROOT / 'ga412/private/native-build-v2' / name) == digest, 'original probe/tracer changed')
    preflight = load(WORK / 'commands/runtime-immediate-preflight-original-binaries.json')
    require(preflight['returncode'] == 0 and all(h in preflight['stdout'] for h in once['binary_sha256'].values()), 'actual uploaded binary preflight hash mismatch')
    events = [json.loads(line[len('PROBE_EVENT '):]) for line in (capture / 'probe.stdout').read_text().splitlines() if line.startswith('PROBE_EVENT ')]
    require(sum(e['event'] == 'command_created' for e in events) == 1, 'more than one explicit CB')
    observed = next(e for e in events if e['event'] == 'command_wait_returned')
    require({k: observed[k] for k in command} == command, 'stdout command lifecycle inconsistent')
    require(not desktop['screenshot_available'] and desktop['screenshot_returncode'] == 1,
            'unexpected screenshot evidence; review desktop claim')
    require(desktop['status'] == 'DESKTOP_ARTIFACTS_REMAIN' and result['stability'] == 'STABILITY_UNVERIFIED', 'overclaimed desktop/stability')
    require(not desktop['current_dmesg_fault_matches'] and health['status'] == 'NO_NEW_RESET_PANIC_WATCHDOG_REPORT_OBSERVED', 'unreviewed fault evidence')
    require(desktop['screenshot_vs_physical_screen_comparison'].startswith('NOT_AVAILABLE'), 'missing screenshot limitation')
    attempt_time = load(WORK / 'commands/runtime-r8-once-execution.json')['time_utc']
    for name in ('desktop-processes-and-existing-logs', 'desktop-screenshot-once', 'desktop-existing-xedrv-and-power', 'desktop-existing-session-fault-log'):
        require(load(WORK / 'commands' / (name + '.json'))['time_utc'] > attempt_time, 'desktop check preceded R8')
    count = 0
    def walk(value):
        nonlocal count
        if isinstance(value, dict):
            if {'path', 'bytes', 'sha256'} <= value.keys():
                p = ROOT / value['path']
                require(p.stat().st_size == value['bytes'] and sha(p) == value['sha256'], 'evidence record changed: ' + value['path'])
                count += 1
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    for name in ('R8-RESULT.json', 'RUNTIME-BOOT.json', 'RUNTIME-HEALTH.json', 'DESKTOP-OBSERVATION.json',
                 'R8-VERIFICATION-RECEIPT.json', 'TRACE-COMPARISON.json'):
        walk(load(REPORTS / name))
    for p in (ROOT / 'ga414').glob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)', p.read_text()):
            if '://' not in link: require((p.parent / link).exists(), 'broken document link: ' + link)
    report = {'status': 'FINAL_EXPERIMENT_AUDIT_PASS', 'experiment_result': result['status'],
              'artifact_records_verified': count, 'single_probe_execution_and_single_CB_verified': True,
              'actual_NOAUX_confirmed': True, 'all_three_active_pixel_comparisons_zero': True,
              'old_CPU_bad_pixels': 16705, 'new_CPU_bad_pixels': 0,
              'desktop': 'DESKTOP_ARTIFACTS_REMAIN', 'screenshot': 'UNAVAILABLE_ATTEMPT_FAILED',
              'stability': 'STABILITY_UNVERIFIED', 'resource_specific_kernel_AUX': 'NOT_OBSERVED',
              'scope': 'GA414 single-factor experiment fulfilled; whole-desktop repair is not achieved or claimed.',
              'requirements_checklist': record(ROOT / 'ga414/REQUIREMENTS-AUDIT.md')}
    path = REPORTS / 'FINAL-AUDIT.json'
    if path.exists(): require(load(path) == report, 'final audit differs')
    else: save(path, report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
