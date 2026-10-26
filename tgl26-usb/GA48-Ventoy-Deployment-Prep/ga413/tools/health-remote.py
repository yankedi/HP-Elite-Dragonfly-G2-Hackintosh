#!/usr/bin/env python3
"""Read-only pre/post health inventory on the R6 Mac; never submits Metal work."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

SESSION = 'REDACTED-SESSION-ID'
BUNDLE = Path('/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS')
HASHES = {'AppleIntelTGLGraphicsMTLDriver': 'e3242693959408c9cef14140df81ce98ff1e04d5dd83aa9aeaddb463271ac65d',
          'libxedrv.dylib': 'b274aa7293acc9ba4c00acaefa564b4c9367ed29042659371ce42b62dd651259'}


def main():
    commands = {}
    issues = []

    def run(name, args):
        result = subprocess.run(args, capture_output=True, text=True, timeout=15)
        commands[name] = {'argv': args, 'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
        if result.returncode:
            issues.append(name + ' failed')
        return result.stdout

    session = run('session', ['/usr/sbin/sysctl', '-n', 'kern.bootsessionuuid']).strip()
    boot = run('boottime', ['/usr/sbin/sysctl', '-n', 'kern.boottime'])
    build = run('build', ['/usr/bin/sw_vers', '-buildVersion']).strip()
    loaded = run('loaded', ['/usr/bin/kmutil', 'showloaded'])
    igpu = run('igpu', ['/usr/sbin/ioreg', '-r', '-n', 'IGPU', '-d', '1', '-l', '-w', '0'])
    processes = run('processes', ['/bin/ps', '-axo', 'pid,state,rss,pcpu,comm'])
    uptime = run('uptime', ['/usr/bin/uptime'])
    if session != SESSION or build != '25G83': issues.append('boot/build changed')
    if not re.search(r'com\.StezzaPilot\.NootedGreen .*4C4C44D0-5555-3144-A111-5710B37AE86F', loaded):
        issues.append('R6 NG identity mismatch')
    if '"device-id" = <499a0000>' not in igpu or '"vendor-id" = <86800000>' not in igpu:
        issues.append('IGPU identity mismatch')
    ws = [line.strip() for line in processes.splitlines() if line.rstrip().endswith('/WindowServer')]
    if len(ws) != 1 or ws[0].split()[0] != '197' or ws[0].split()[1] not in ('S', 'Ss', 'R', 'Rs'):
        issues.append('WindowServer absent/changed/abnormal state')
    boot_sec = int(re.search(r'sec = (\d+)', boot).group(1))
    diagnostics = []
    for path in Path('/Library/Logs/DiagnosticReports').glob('*.gpuRestart'):
        st = path.stat()
        diagnostics.append({'name': path.name, 'mtime_epoch': st.st_mtime, 'bytes': st.st_size,
                            'mtime_since_boot': st.st_mtime >= boot_sec})
    diagnostics.sort(key=lambda item: item['mtime_epoch'], reverse=True)
    current = [item for item in diagnostics if item['mtime_since_boot']]
    if current: issues.append('gpuRestart report modified during this boot')
    hashes = {name: hashlib.sha256((BUNDLE / name).read_bytes()).hexdigest() for name in HASHES}
    if hashes != HASHES: issues.append('MTLDriver/libxedrv changed')
    media = []
    for name in ('HP-Tahoe-Recovery-GA410-CSR0.img', 'HP-Tahoe-VESA-XHCI-RHUB.img'):
        path = Path('/Volumes/TARGET_VOLUME/ISO/linux') / name
        exists = path.is_file()
        size = path.stat().st_size if exists else None
        media.append({'path': str(path), 'exists': exists, 'bytes': size,
                      'limit': 'presence/size only; not boot-tested or rehashed in this experiment'})
        if size != 1343225856: issues.append('rollback file missing/size changed')
    print(json.dumps({'status': 'HEALTH_GATE_PASS' if not issues else 'HEALTH_GATE_BLOCKED',
                      'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'issues': issues,
                      'session': session, 'boot_epoch': boot_sec, 'build': build, 'WindowServer': ws,
                      'uptime': uptime, 'stack_sha256': hashes, 'rollback_media': media,
                      'current_boot_gpuRestart_reports': current, 'all_gpuRestart_reports': diagnostics,
                      'commands': commands,
                      'limits': 'Read-only service/identity/report checks, not proof of GPU stability or UI response.'}, indent=2))
    return 0 if not issues else 3


if __name__ == '__main__':
    sys.exit(main())
