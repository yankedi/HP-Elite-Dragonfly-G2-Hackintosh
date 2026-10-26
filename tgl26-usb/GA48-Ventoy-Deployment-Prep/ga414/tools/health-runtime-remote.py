#!/usr/bin/env python3
"""Read-only GA414 identity, services, installed stack and boot diagnostics gate."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

SESSION = 'REDACTED-SESSION-ID'
UUID = '4C4C44E9-5555-3144-A1E4-CB51FF5A72E6'


def main():
    commands, issues = {}, []
    def run(name, args):
        r = subprocess.run(args, capture_output=True, text=True, timeout=20)
        commands[name] = {'argv': args, 'returncode': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr}
        if r.returncode: issues.append(name + ' failed')
        return r.stdout
    session = run('session', ['/usr/sbin/sysctl', '-n', 'kern.bootsessionuuid']).strip()
    boot = run('boot', ['/usr/sbin/sysctl', '-n', 'kern.boottime'])
    args = run('bootargs', ['/usr/sbin/sysctl', '-n', 'kern.bootargs']).split()
    build = run('build', ['/usr/bin/sw_vers', '-buildVersion']).strip()
    loaded = run('loaded', ['/usr/bin/kmutil', 'showloaded'])
    igpu = run('igpu', ['/usr/sbin/ioreg', '-r', '-n', 'IGPU', '-d', '1', '-l', '-w', '0'])
    processes = run('processes', ['/bin/ps', '-axo', 'pid,state,rss,pcpu,comm'])
    if session != SESSION or build != '25G83': issues.append('boot/build mismatch')
    if any(a in args for a in ('-ngreenccs', '-ngreenxefix')): issues.append('forbidden boot argument')
    if not re.search(r'com\.StezzaPilot\.NootedGreen .*' + UUID, loaded): issues.append('GA414 NG mismatch')
    for name in ('org.smichaud.HookCase', 'com.xxxxx.driver.AppleIntelTGLGraphicsFramebuffer', 'com.xxxxx.driver.AppleIntelTGLGraphics'):
        if not re.search(re.escape(name) + r' \(', loaded): issues.append('not loaded: ' + name)
    for value in ('"device-id" = <499a0000>', '"vendor-id" = <86800000>',
                  '"subsystem-vendor-id" = <3c100000>', '"subsystem-id" = <16870000>'):
        if value not in igpu: issues.append('IGPU mismatch: ' + value)
    ws = [line.strip() for line in processes.splitlines() if line.rstrip().endswith('/WindowServer')]
    if len(ws) != 1 or ws[0].split()[0] != '197' or ws[0].split()[1] not in ('S', 'Ss', 'R', 'Rs'):
        issues.append('WindowServer absent/changed/abnormal state')
    boot_sec = int(re.search(r'sec = (\d+)', boot).group(1))
    diagnostics = []
    for path in Path('/Library/Logs/DiagnosticReports').rglob('*'):
        if not path.is_file() or not any(s in path.name.lower() for s in ('gpurestart', 'panic', 'watchdog', 'windowserver')): continue
        st = path.stat()
        diagnostics.append({'path': str(path), 'bytes': st.st_size, 'mtime_epoch': st.st_mtime,
                            'mtime_since_boot': st.st_mtime >= boot_sec})
    diagnostics.sort(key=lambda x: x['mtime_epoch'], reverse=True)
    current = [d for d in diagnostics if d['mtime_since_boot'] and d['bytes'] > 0]
    if current: issues.append('current boot diagnostic requires review; no GPU permitted')
    bundle = Path('/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS')
    expected = {'AppleIntelTGLGraphicsMTLDriver': 'e3242693959408c9cef14140df81ce98ff1e04d5dd83aa9aeaddb463271ac65d',
                'libxedrv.dylib': 'b274aa7293acc9ba4c00acaefa564b4c9367ed29042659371ce42b62dd651259'}
    hashes = {name: hashlib.sha256((bundle / name).read_bytes()).hexdigest() for name in expected}
    if hashes != expected: issues.append('installed MTLDriver/libxedrv changed')
    print(json.dumps({'status': 'HEALTH_GATE_PASS' if not issues else 'HEALTH_GATE_BLOCKED', 'issues': issues,
                     'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'session': session,
                     'boot_epoch': boot_sec, 'build': build, 'NG_UUID': UUID, 'WindowServer': ws,
                     'current_boot_diagnostics': current, 'all_diagnostics': diagnostics, 'stack_sha256': hashes,
                     'commands': commands, 'limits': 'Read-only snapshot; requires separate NOAUX dmesg proof. Not long-term stability or visual correctness.'}, indent=2))
    return 0 if not issues else 3


if __name__ == '__main__':
    sys.exit(main())
