#!/usr/bin/env python3
"""Run real native backends with GCC/Clang/ASan+UBSan; receipts include failures."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def main():
    results=[]
    samples=ROOT/'tests/native-samples';samples.mkdir(exist_ok=True)
    for n,b in [('zero',bytes(16)),('unknown',bytes.fromhex('7f000000')+bytes(12)),
                ('truncated',bytes.fromhex('61000300')+bytes(7)),('compact-short',bytes.fromhex('41000020'))]:
        (samples/(n+'.bin')).write_bytes(b)
    shaders=['ps','vs','ps-kp1','ps-kp2']
    inputs=[(ROOT/f'analysis/{s}-bounded.bin','11','positive') for s in shaders]
    inputs += [(ROOT/f'analysis/{s}-bounded.bin','12p1','negative-target-encoding') for s in shaders]
    inputs += [(ROOT/f'analysis/upstream-{s}-gen12.bin','12p1','upstream-structure-only') for s in shaders]
    inputs += [(p,gen,'negative') for p in sorted(samples.glob('*.bin')) for gen in ['11','12p1']]
    for variant in ['build','build-gcc','build-sanitize']:
        exe=ROOT/'tools/iga'/variant/'IGAExe/iga64'
        if not exe.exists():
            results.append({'variant':variant,'status':'UNAVAILABLE'});continue
        for f,p,classification in inputs:
            args=[str(exe),'-d','-p='+p,'--output-on-fail','-Xprint-json',str(f)]
            env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            r=subprocess.run(args,capture_output=True,env=env,timeout=30)
            stem=f'{variant}-{f.stem}-{p}'
            (ROOT/'logs'/f'native-{stem}.stdout').write_bytes(r.stdout)
            (ROOT/'logs'/f'native-{stem}.stderr').write_bytes(r.stderr)
            results.append({'variant':variant,'file':str(f.relative_to(ROOT)),'platform':p,
                            'class':classification,'exit':r.returncode,
                            'sanitizer_diagnostic':any(k in r.stderr for k in
                            [b'AddressSanitizer',b'runtime error:',b'LeakSanitizer']),
                            'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),
                            'stderr_bytes':len(r.stderr),'argv':args})
    for s in shaders:
        exe=ROOT/'tools/mesa-eu/adapter/build-sanitize/g11to12'
        args=[str(exe),'xlate',str(ROOT/f'analysis/{s}-bounded.bin')]
        r=subprocess.run(args,capture_output=True,timeout=30,
                         env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'))
        (ROOT/f'logs/mesa-sanitize-{s}.stdout').write_bytes(r.stdout)
        (ROOT/f'logs/mesa-sanitize-{s}.stderr').write_bytes(r.stderr)
        results.append({'variant':'mesa-upstream-sanitize','shader':s,'exit':r.returncode,
                        'sanitizer_diagnostic':any(k in r.stderr for k in [b'AddressSanitizer',b'runtime error:',b'LeakSanitizer']),
                        'stderr_bytes':len(r.stderr),'argv':args})
    (ROOT/'analysis/native-matrix.json').write_text(json.dumps(results,indent=2)+'\n')
    print('runs',len(results),'sanitizer diagnostics',sum(x.get('sanitizer_diagnostic',False) for x in results))
    assert not any(x.get('sanitizer_diagnostic') for x in results), 'native sanitizer failure'
    for x in results:
        if x.get('class') in {'positive','upstream-structure-only'}:
            assert x['exit']==0, x
        if x.get('class')=='negative-target-encoding':
            assert x['exit']!=0, x
        if x['variant']=='mesa-upstream-sanitize':
            assert x['exit']==0, x
    grouped={}
    for x in results:
        if 'file' in x:
            grouped.setdefault((x['file'],x['platform']),set()).add(x['stdout_sha256'])
    assert all(len(v)==1 for v in grouped.values()), 'cross-compiler decoder mismatch'
    print('positive decode, raw cross-generation rejection, and cross-build output assertions passed')
    for r in results:
        if r.get('sanitizer_diagnostic'):print(r)
if __name__=='__main__':main()
