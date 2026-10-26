#!/usr/bin/env python3
"""Audit recorded crash reproduction and bounded repaired-system GUI retest offline."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = ROOT / 'ga415/private/commands'
REPORTS = ROOT / 'ga415/reports'
WORK = ROOT / 'ga415/private/planes2-postboot'
SESSION = 'REDACTED-SESSION-ID'
NG_UUID = '4C4C44E9-5555-3144-A1E4-CB51FF5A72E6'
DONOR_UUID = 'BA3AA1C0-FE6B-33B3-9D85-73F848394E3D'


def receipt(name):
    value = json.loads((COMMANDS / (name + '.json')).read_text())
    assert value['returncode'] == 0, name
    return value


def snapshot(name):
    return json.loads(receipt(name)['stdout'])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def diagnostics(state):
    return {row['path']: row['sha256'] for row in state['diagnostics']}


def process_pid(state, suffix):
    lines = [line for line in state['processes']['stdout'].splitlines() if line.endswith(suffix)]
    assert len(lines) == 1, (suffix, lines)
    return int(lines[0].split()[0])


def output(state, path):
    return next(row for row in state['gui_outputs'] if row['path'] == path)


def main():
    before = snapshot('avatar-repro-preflight-v1')
    pre = snapshot('planes2-postboot-preflight-v1')
    nav = snapshot('planes2-retest-same-navigation-result-v1')
    coordinate = snapshot('planes2-avatar-panel-result-v1')
    button = snapshot('planes2-avatar-button-result-v1')
    final = snapshot('planes2-retest-final-health-v1')
    evidence = json.loads((REPORTS / 'PLANES2-PRETEST.json').read_text())
    assert before['session']['stdout'].strip() == 'REDACTED-SESSION-ID'
    assert '4C4C44D0-5555-3144-A111-5710B37AE86F' in before['loaded']['stdout']
    assert NG_UUID in pre['loaded']['stdout'] and DONOR_UUID in pre['loaded']['stdout']
    changed = [row for row in pre['diagnostics'] if row['path'] not in diagnostics(before)
               and row['path'].endswith('.panic')]
    assert len(changed) == 1
    crash = changed[0]
    assert digest(crash['text'].encode()) == crash['sha256'] == evidence['new_panic']['sha256']
    assert (WORK / 'reproduced-r6.panic').read_bytes() == crash['text'].encode()
    text = json.loads(crash['text'].splitlines()[1])['macOSPanicString']
    assert text == (WORK / 'reproduced-r6-panic.txt').read_text()
    assert 'Kernel trap at 0xffffff7f96718bcd, type = 0=divide error' in text
    assert 'pid 1510: AvatarPickerMemojiPicker' in text and re.search(r'R15: 0x0+\b', text)
    assert DONOR_UUID in text and ' -ngreennoplanesfix ' in text
    spec = importlib.util.spec_from_file_location('panic_decoder', ROOT / 'ga410/tools/decode-nvram-panic.py')
    decoder = importlib.util.module_from_spec(spec); spec.loader.exec_module(decoder)
    decoded = decoder.unpack_ascii((WORK / 'nvram-reproduced-packed.bin').read_bytes())
    assert decoded == (WORK / 'nvram-reproduced-decoded.txt').read_text()
    assert decoded.rstrip() == text.rstrip()
    assert digest(decoded.encode()) == evidence['decoded_sha256']
    ns = int(re.search(r'System uptime in nanoseconds: (\d+)', text)[1])
    boot = int(re.search(r'sec = (\d+)', before['boot']['stdout'])[1])
    panic_time = datetime.datetime.fromtimestamp(boot + ns / 1e9, datetime.timezone.utc)
    launch = receipt('avatar-repro-inspect-launch-v1')
    loss = json.loads((COMMANDS / 'avatar-repro-inspect-result-v1.json').read_text())
    assert loss['returncode'] == 255 and 'Connection timed out' in loss['stderr']
    assert datetime.datetime.fromisoformat(launch['time_utc']) < panic_time < datetime.datetime.fromisoformat(loss['time_utc'])
    script = ROOT / 'ga415/tools/avatar-ui-inspect.command'
    assert digest(script.read_bytes()) == '6794a94f00bea8d043f087a64350a977776432dbd78cace782fc7eea2603949c'
    assert output(nav, 'avatar-ui-inspect.command')['sha256'] == digest(script.read_bytes())
    states = [pre, nav, coordinate, button, final]
    for state in states:
        assert state['session']['stdout'].strip() == SESSION
        args = state['identity']['stdout'].split('kern.bootargs: ', 1)[1].split()
        assert '-ngreentgltahoe' in args
        assert not set(args) & {'-ngreennoplanesfix', '-ngreenplanesxor', '-ngreenxefix', '-ngreenccs'}
        logs = state['dmesg']['stdout']
        assert 'IOSurface+0x98: aplicado' in logs
        assert 'GA414 NOAUX: postflight original=0 patched=1 verified=1 expected=0/1' in logs
        assert 'XE-NOCCS3:' in logs and 'retorno imediato: aplicado' in logs
        assert not re.search(r'GPU.*(?:hang|reset|restart)|gpuRestart|PIPE_CONTROL|panic\(cpu', logs, re.I)
        assert diagnostics(state) == diagnostics(pre)
        assert process_pid(state, '/WindowServer') == 197
    assert output(nav, 'inspect/run.stdout')['text'] == 'INSPECTION_COMPLETE\n'
    assert output(nav, 'inspect/run.stderr')['text'] == ''
    assert output(coordinate, 'panel/run.stdout')['text'].endswith('PANEL_CHECK_COMPLETE\n')
    assert output(button, 'avatar-button/run.stdout')['text'].endswith('AVATAR_BUTTON_CHECK_COMPLETE\n')
    assert output(button, 'avatar-button/run.stderr')['text'] == ''
    assert 'position:1252, 134' in output(button, 'avatar-button/action.txt')['text']
    assert all(process_pid(state, '/AvatarPickerMemojiPicker') == 893 for state in [nav, coordinate, button, final])
    assert process_pid(button, '/AvatarPickerPosePicker') == process_pid(final, '/AvatarPickerPosePicker')
    assert process_pid(button, '/AvatarPickerMemojiEditor') == process_pid(final, '/AvatarPickerMemojiEditor')
    screenshots = []
    for state, remote, local in [
        (nav, 'inspect/desktop.png', 'same-navigation.png'),
        (coordinate, 'panel/desktop.png', 'avatar-panel-coordinate.png'),
        (button, 'avatar-button/desktop.png', 'avatar-button.png'),
    ]:
        data = (WORK / local).read_bytes()
        assert digest(data) == output(state, remote)['sha256'] and data.startswith(b'\x89PNG\r\n\x1a\n')
        screenshots.append({'path': str((WORK / local).relative_to(ROOT)), 'sha256': digest(data)})
    start = datetime.datetime.fromisoformat(receipt('planes2-retest-same-navigation-launch-v1')['time_utc'])
    end = datetime.datetime.fromisoformat(final['utc'])
    observed = (end - start).total_seconds()
    assert observed >= 120
    result = {
        'status': 'PLANES2_TARGETED_PANIC_RETEST_PASS',
        'scope': 'One identical Users & Groups navigation, then bounded avatar-panel actions; not a stress/stability or pixel-correctness acceptance.',
        'before': {'NG_UUID': '4C4C44D0-5555-3144-A111-5710B37AE86F',
                   'PLANES2_disabled': True, 'result': 'SAME_DIVIDE_BY_ZERO_PANIC_CONFIRMED',
                   'panic_path': crash['path'], 'panic_sha256': crash['sha256'], 'RIP': '0xffffff7f96718bcd',
                   'instruction': 'div r15d', 'divisor': 0, 'process': 'AvatarPickerMemojiPicker',
                   'actual_panic_utc': panic_time.isoformat(), 'NVRAM_roundtrip_and_text_content_match': True},
        'after': {'NG_UUID': NG_UUID, 'boot_session': SESSION, 'PLANES2_applied': True,
                  'NOAUX_verified': True, 'NOCCS3_applied': True, 'same_navigation_script_SHA256': digest(script.read_bytes()),
                  'same_navigation_completed': True, 'coordinate_click_opened_panel': False,
                  'actual_AX_avatar_button_pressed_once': True, 'Memoji_panel_screenshot_observed': True,
                  'MemojiPicker_PID': 893, 'MemojiPicker_PID_unchanged': True,
                  'MemojiEditor_PID': process_pid(final, '/AvatarPickerMemojiEditor'),
                  'PosePicker_PID': process_pid(final, '/AvatarPickerPosePicker'),
                  'WindowServer_PID': 197, 'WindowServer_PID_unchanged': True,
                  'diagnostic_count': len(final['diagnostics']), 'new_or_changed_diagnostics': [],
                  'kernel_GPU_fault_matches': [], 'observation_seconds_from_navigation_launch': observed,
                  'final_observation_utc': final['utc']},
        'screenshots': screenshots, 'desktop_and_Memoji_rendering': 'VISIBLE_CORRUPTION_REMAINS',
        'PIXEL_PASS': False, 'long_term_stability': 'NOT_VERIFIED',
        'comparison_limit': 'Immediate before is R6, after is GA414+PLANES2. Earlier GA414 with identical NOAUX binary also panicked at this exact instruction; image audit proves only boot-arg delta from GA414.',
        'automatic_reboot_or_trigger_loop': False,
    }
    with (REPORTS / 'PLANES2-RUNTIME-RESULT.json').open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
