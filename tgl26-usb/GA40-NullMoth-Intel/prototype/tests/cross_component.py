"""CPU model BO bytes -> Metal-like C adapter -> model/software Vulkan -> bytes.

This is a deliberate CPU copy across two independent contracts. No DRM handle,
Context, simulated VM identifier, or GPU VA is passed to the Vulkan device.
"""
import errno
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'drm/mock'))
from i915_model import ABI, MockI915

out=ROOT/'prototype/results/cross-component-001'
out.mkdir(exist_ok=False)
abi=ABI(); model=MockI915(abi)
def call(name,**values):
    return abi.unpack(name,model.ioctl(abi.data['requests'][name]['value'],abi.pack(name,**values)))
try: model.require_real_anv_device()
except OSError as exc: assert exc.errno==errno.ENODEV
else: raise AssertionError('fake ANV device accepted')
handle=call('I915_GEM_CREATE',size=64)['handle']
words=[i*19+7 for i in range(16)]
payload=b''.join(x.to_bytes(4,'little') for x in words)
model.cpu_bo_write(handle,0,payload)
(out/'input.bin').write_bytes(payload)
results=[]
for backend in ['model','lavapipe']:
    command=[str(ROOT/'build/cross-component/metal-like-pipeline')]
    if backend=='lavapipe': command.append('lavapipe')
    p=subprocess.run(command,input=model.cpu_bo_read(handle,0,64),capture_output=True,timeout=30)
    (out/(backend+'.stdout.json')).write_bytes(p.stdout)
    (out/(backend+'.stderr.txt')).write_bytes(p.stderr)
    assert p.returncode==0,(backend,p.stderr)
    result=json.loads(p.stdout); expected=words.copy(); expected[1]=0x11223344
    assert result['words']==expected and not result['real_gpu']
    results.append({'backend':backend,'command':command,'exit':p.returncode,'readback_equal':True})
call('GEM_CLOSE',handle=handle); model.close()
result={'status':'PASS','cases':results,'input_sha256':hashlib.sha256(payload).hexdigest(),
        'source':'explicitly copied CPU model backing bytes, NOT a mapped DRM BO',
        'software_vulkan':True,'real_intel_gpu_submitted':False,'macos_metal_accelerated':False,
        'fake_anv_rejected':True,'hardware_approval':'NO'}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
