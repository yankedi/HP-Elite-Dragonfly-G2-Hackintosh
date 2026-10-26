#!/usr/bin/env python3
"""Real historical bytes -> unchanged core -> owned adapter -> actual POSIX transaction."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
LOG=ROOT/'integration/logs'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
LOG.mkdir(parents=True,exist_ok=False)
source=ROOT.parent/'GA32/capture/tgl-hang-GA32b-crash-20261018.bin'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='1622ecc2aecdcc85ae45dcf86e4219338f6e41e0243b27d5e7128a9999f13333'
gcc=shutil.which('g++') or str(sorted(Path('/nix/store').glob('*gcc-wrapper-*/bin/g++'))[-1])
compilers={'clang':shutil.which('clang++'),'gcc':gcc}
rows=[]
for name,compiler in compilers.items():
    for mode,flags in [('debug',['-O0','-g']),('release',['-O2']),('asan-ubsan',['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer'])]:
        stem=name+'-'+mode;binary=LOG/stem;target=LOG/(stem+'-files')
        cmd=[compiler,'-std=c++17','-pthread','-DGA37_TEST_FAULTS','-Wall','-Wextra','-Werror',*flags,'-I',str(ROOT/'track-b/include'),str(ROOT/'integration/pipeline_writer.cpp'),*[str(p) for p in sorted((ROOT/'track-b/src').glob('*.cpp'))],'-o',str(binary)]
        build=subprocess.run(cmd,capture_output=True,text=True,timeout=120,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        (LOG/(stem+'-build.txt')).write_text('$ '+' '.join(cmd)+'\nexit='+str(build.returncode)+'\n'+build.stdout+build.stderr);build.check_returncode()
        run=subprocess.run([str(binary),str(source),str(target)],capture_output=True,text=True,timeout=60)
        (LOG/(stem+'-run.txt')).write_text('$ '+str(binary)+' '+str(source)+' '+str(target)+'\nexit='+str(run.returncode)+'\n'+run.stdout+run.stderr);run.check_returncode();assert not run.stderr
        files=[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size} for p in sorted(target.rglob('*.snap'))]
        assert any(f['sha256']=='1622ecc2aecdcc85ae45dcf86e4219338f6e41e0243b27d5e7128a9999f13333' for f in files)
        rows.append({'name':stem,'compile_exit':build.returncode,'run_exit':run.returncode,'snapshots':files,'stdout':run.stdout})
result={'status':'PASS','scope':'Hosted actual GA36 Pipeline + owned GA37 executor + nominal callback bridge + POSIX usermode transactional backend, historical THAG2 bytes unchanged. No XNU or GPU execution.','runs':rows,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'log_directory':str(LOG)}
(LOG/'results.json').write_text(json.dumps(result,indent=2)+'\n');(ROOT/'integration/results.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS actualPipeline/executor/transaction integration',len(rows),'builds; final snapshot byte-identical to original THAG; failed new write preserves old revision')
