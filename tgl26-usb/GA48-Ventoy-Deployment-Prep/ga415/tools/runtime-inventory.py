#!/usr/bin/env python3
"""Run on HP: bounded read-only runtime inventory; no Metal workload."""
import datetime
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess


def main():
    records = {}
    def run(key, argv, timeout=25):
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
            records[key] = dict(argv=argv, returncode=r.returncode, stdout=r.stdout, stderr=r.stderr)
        except subprocess.TimeoutExpired:
            records[key] = dict(argv=argv, error='TIMEOUT')
    for key, argv in {
        'date': ['/bin/date'], 'uptime': ['/usr/bin/uptime'],
        'build': ['/usr/bin/sw_vers'], 'session': ['/usr/sbin/sysctl', 'kern.bootsessionuuid', 'kern.boottime', 'kern.bootargs'],
        'loaded': ['/usr/bin/kmutil', 'showloaded'],
        'displays': ['/usr/sbin/system_profiler', 'SPDisplaysDataType', '-json'],
        'framebuffer': ['/usr/sbin/ioreg', '-r', '-c', 'IOFramebuffer', '-l', '-w', '0'],
        'processes': ['/bin/ps', '-axo', 'pid,state,rss,pcpu,etime,comm'],
        'assertions': ['/usr/bin/pmset', '-g', 'assertions'],
        'developer_dir': ['/usr/bin/xcode-select', '-p'],
        'clang': ['/usr/bin/clang', '--version'],
        'capture_tools': ['/bin/sh', '-c', 'command -v xcrun; xcrun --find metal; xcrun --find xctrace; xcrun --find swift'],
        'runtime_libraries': ['/usr/sbin/lsof', '-n', '-p', '197'],
    }.items():
        run(key, argv)
    base = Path('/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents')
    stack = {}
    for p in (base / 'MacOS').glob('*'):
        if p.is_file():
            stack[p.name] = dict(bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    info = plistlib.loads((base / 'Info.plist').read_bytes()) if (base / 'Info.plist').exists() else {}
    print(json.dumps(dict(schema='ga415-runtime-inventory-v1', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         commands=records, installed_stack=stack, bundle_info=info,
                         limits='Read-only identity/capability inventory; not visual correctness or GPU-test authorization.'),
                     indent=2, default=str))


if __name__ == '__main__':
    main()
