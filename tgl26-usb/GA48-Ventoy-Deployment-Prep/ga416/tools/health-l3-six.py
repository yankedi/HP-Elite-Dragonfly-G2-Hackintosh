#!/usr/bin/env python3
"""Read-only checks pinned to the first actual GA416 six-bank boot."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

SESSION='REDACTED-SESSION-ID'
UUID='4C4C44D4-5555-3144-A13A-DFB86EFBE513'


def main():
    def call(*args):
        r=subprocess.run(args,capture_output=True,text=True,timeout=40)
        if r.returncode:raise RuntimeError(repr((args,r.returncode,r.stderr)))
        return r.stdout
    session=call('/usr/sbin/sysctl','-n','kern.bootsessionuuid').strip()
    boot=int(re.search(r'sec = (\d+)',call('/usr/sbin/sysctl','-n','kern.boottime'))[1])
    loaded=call('/usr/bin/kmutil','showloaded');dmesg=call('/sbin/dmesg')
    ps=call('/bin/ps','-axo','pid,state,comm')
    ws=[l for l in ps.splitlines() if '/WindowServer' in l]
    diagnostics=[]
    for p in sorted(Path('/Library/Logs/DiagnosticReports').rglob('*')):
        if not p.is_file() or not any(s in p.name.lower() for s in ['panic','gpurestart','watchdog','windowserver']):continue
        data=p.read_bytes()
        diagnostics.append({'path':str(p),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),
                            'mtime':p.stat().st_mtime,'current_session_in_content':session.encode() in data,
                            'mtime_since_boot':p.stat().st_mtime>=boot})
    faults=[l for l in dmesg.splitlines() if re.search(r'GPU.*(?:hang|reset|restart)|gpuRestart|PIPE_CONTROL|panic\(cpu',l,re.I)]
    issues=[]
    if session!=SESSION:issues.append('BOOT_CHANGED')
    if UUID not in next((l for l in loaded.splitlines() if 'com.StezzaPilot.NootedGreen ' in l),''):issues.append('NG_IDENTITY_MISMATCH')
    if call('/usr/sbin/sysctl','-n','kern.osversion').strip()!='25G83':issues.append('BUILD_MISMATCH')
    if len(ws)!=1 or ws[0].split()[0]!='197' or ws[0].split()[1].startswith(('U','Z')):issues.append('WINDOWSERVER_REPLACED_OR_UNHEALTHY')
    if faults:issues.append('KERNEL_FAULT')
    if any(d['current_session_in_content'] or d['mtime_since_boot'] for d in diagnostics):issues.append('CURRENT_BOOT_DIAGNOSTIC_REQUIRES_REVIEW')
    print(json.dumps({'status':'HEALTH_GATE_FAIL' if issues else 'HEALTH_GATE_PASS','issues':issues,
                      'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'session':session,'boot_epoch':boot,
                      'NG_UUID':UUID,'WindowServer':ws,'fault_lines':faults,'diagnostics':diagnostics},indent=2))
    return 1 if issues else 0


if __name__=='__main__':sys.exit(main())
