#!/usr/bin/env python3
"""Read-only post-test identity, diagnostics and GUI-script output snapshot on HP."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    result = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    for key, command in [
        ('session', ['/usr/sbin/sysctl', '-n', 'kern.bootsessionuuid']),
        ('identity', ['/usr/sbin/sysctl', 'kern.boottime', 'kern.osversion', 'kern.bootargs']),
        ('uptime', ['/usr/bin/uptime']),
        ('processes', ['/bin/ps', '-axo', 'pid,state,%cpu,rss,etime,comm']),
        ('dmesg', ['/sbin/dmesg']),
    ]:
        row = subprocess.run(command, capture_output=True, text=True, timeout=25)
        result[key] = {'returncode': row.returncode, 'stdout': row.stdout, 'stderr': row.stderr}
    result['diagnostics'] = []
    for path in Path('/Library/Logs/DiagnosticReports').rglob('*'):
        if path.is_file() and any(s in path.name.lower() for s in ['panic', 'gpurestart', 'watchdog', 'windowserver']):
            data = path.read_bytes()
            result['diagnostics'].append({'path': str(path), 'bytes': len(data),
                                          'sha256': hashlib.sha256(data).hexdigest()})
    base = Path('/private/tmp/ga415-avatar-repro')
    result['gui_outputs'] = []
    if base.exists():
        for path in base.rglob('*'):
            if path.is_file():
                data = path.read_bytes()
                result['gui_outputs'].append({'path': str(path.relative_to(base)), 'bytes': len(data),
                                              'sha256': hashlib.sha256(data).hexdigest(),
                                              'text': data.decode(errors='replace') if path.suffix in
                                              ('.txt', '.stdout', '.stderr', '.json', '.exit') else None})
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
