#!/usr/bin/env python3
"""One user-invoked macOS snapshot. No GPU submission, loop or installation."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess


def call(args, timeout=20):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {'args':args,'rc':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
    except subprocess.TimeoutExpired as exc:
        return {'args':args,'rc':None,'timeout':True,
                'stdout':(exc.stdout or b'').decode(errors='replace'),
                'stderr':(exc.stderr or b'').decode(errors='replace')}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True, help='New evidence directory')
    ap.add_argument('--boot', required=True, help='Expected kern.bootsessionuuid')
    ap.add_argument('--vmmap', action='store_true', help='One optional vmmap --summary')
    args = ap.parse_args()
    assert platform.system() == 'Darwin'
    session = call(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'])
    assert session['rc'] == 0 and session['stdout'].strip() == args.boot
    build = call(['/usr/sbin/sysctl','-n','kern.osversion'])
    assert build['stdout'].strip() == '25G83'
    args.out.mkdir(mode=0o700, parents=False, exist_ok=False)
    bundle = Path('/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle')
    def inventory(root):
        result = {}
        for p in sorted(root.rglob('*')):
            if p.is_file():
                result[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
        return result
    before = inventory(bundle)
    shutil.copytree(bundle, args.out/'installed-bundle', symlinks=True)
    assert inventory(args.out/'installed-bundle') == before
    ps = call(['/bin/ps','-axo','pid=,state=,rss=,etime=,comm='])
    ws = [line for line in ps['stdout'].splitlines() if line.endswith('/WindowServer')]
    result = {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'boot':session,'build':build,'bundle_inventory':before,'processes':ps,
        'WindowServer':ws,'rss_unit':'KiB; not physical footprint or attributed POSH allocation',
        'codesign':call(['/usr/bin/codesign','--verify','--deep','--strict','--verbose=4',str(bundle)]),
        'codesign_display':call(['/usr/bin/codesign','--display','--verbose=4',str(bundle)]),
        'memory':call(['/usr/bin/vm_stat']),
        'loaded':call(['/usr/bin/kmutil','showloaded']),
        'kernel_messages':call(['/sbin/dmesg']),
        'diagnostic_files':[{'path':str(p),'size':p.stat().st_size,'mtime':p.stat().st_mtime}
            for p in sorted(Path('/Library/Logs/DiagnosticReports').rglob('*')) if p.is_file()],
        'GPU_work_submitted':False,'driver_modified':False}
    if args.vmmap:
        assert len(ws) == 1 and not ws[0].split()[1].startswith(('U','Z'))
        result['vmmap'] = call(['/usr/bin/vmmap','--summary',ws[0].split()[0]],timeout=30)
    after = call(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'])
    assert after['stdout'].strip() == args.boot
    assert inventory(bundle) == before
    with (args.out/'snapshot.json').open('x') as f:
        json.dump(result,f,indent=2)
        f.write('\n')
    print(args.out/'snapshot.json')


if __name__ == '__main__':
    main()
