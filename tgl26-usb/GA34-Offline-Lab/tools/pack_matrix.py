#!/usr/bin/env python3
"""Cross-toolchain upstream pack proof, compared to independent source receipt."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label',choices=('clang','gcc'),required=True);args=ap.parse_args()
    compiler=json.loads((ROOT/f'logs/diagnostic-core/{args.label}-results.json').read_text())['compiler']
    compiler=compiler.removesuffix('++') if args.label=='clang' else compiler # g++ also compiles C with -x c
    build=ROOT/f'track-a/build/pack-{args.label}';build.mkdir(parents=True,exist_ok=True)
    log=ROOT/f'logs/pack-{args.label}-matrix.txt';rows=[]
    mesa=ROOT.parent/'GA32-ISA-Lab/tools/mesa-eu/source'
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1:abort_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    env['NIX_HARDENING_ENABLE']=' '.join(x for x in env.get('NIX_HARDENING_ENABLE','').split() if x not in ('fortify','fortify3'))
    with log.open('w') as out:
        def run(cmd):
            out.write('$ '+shlex.join(map(str,cmd))+'\n');out.flush()
            p=subprocess.run(cmd,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            out.write(p.stdout+f'\nEXIT {p.returncode}\n');out.flush()
            if p.returncode:raise SystemExit(f'failed {log}')
            return p.stdout
        version=run([compiler,'--version'])
        for mode,flags in [('Debug',['-O0','-g3']),('Release',['-O2','-g','-DNDEBUG'])]:
            for sanitize in (False,True):
                name=mode+('-asan-ubsan' if sanitize else '-plain');exe=build/name
                cmd=[compiler,'-x','c','-std=c11','-Wall','-Wextra','-U_FORTIFY_SOURCE',
                    '-DUTIL_ARCH_LITTLE_ENDIAN=1','-DUTIL_ARCH_BIG_ENDIAN=0',f'-I{mesa}/src',f'-I{mesa}/include']+flags
                if sanitize:cmd+=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer']
                run(cmd+[str(ROOT/'tools/pack_matrix_probe.c'),'-lm','-o',str(exe)])
                stdout=run([str(exe)])
                if stdout!=(ROOT/'reference/track-a/pack-proof.log').read_text():raise SystemExit('independent pack stdout differs')
                rows.append({'mode':mode,'sanitized':sanitize,'status':'PASS','executable':str(exe.relative_to(ROOT)),
                             'sha256':digest(exe),'stdout_sha256':hashlib.sha256(stdout.encode()).hexdigest()})
    data={'compiler':compiler,'version':version,'builds':rows,'source_sha256':{
        p:digest(ROOT/p) for p in ['tools/pack_matrix_probe.c','tools/pack_matrix.py','reference/track-a/pack-proof.c','reference/track-a/gen12-pack-proof.h']},
        'scope':'upstream generated pack and numeric stencil/draw checks, NOT GPU execution'}
    (ROOT/f'logs/pack-{args.label}-results.json').write_text(json.dumps(data,indent=2)+'\n')
    print(args.label,'4 builds verified against independent pack output; sanitizer diagnostics 0')
if __name__=='__main__':main()
