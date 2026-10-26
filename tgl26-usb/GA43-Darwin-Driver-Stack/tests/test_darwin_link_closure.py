#!/usr/bin/env python3
"""Real Mach-O link/name closure witnesses; no fixture is loaded or executed."""
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from darwin_link_inputs import dynamic_definitions
symbols = runpy.run_path(str(ROOT/'tools/link-darwin-anv.py'))['symbols']
cc, ld = os.environ['DARWIN_CC'], os.environ['DARWIN_LD']
sdk = os.environ['DARWIN_SDK']
nm = str(Path(os.environ['DARWIN_LLVM_BIN'])/'llvm-nm')
with tempfile.TemporaryDirectory(prefix='ga43-link-closure-', dir='/tmp/opencode') as tmp:
    d = Path(tmp)
    def obj(name, text):
        src = d/(name+'.c'); src.write_text(text)
        out = d/(name+'.o')
        subprocess.run([cc, '-target', 'x86_64-apple-macos26', '-c', str(src), '-o', str(out)], check=True)
        return out
    weak = obj('weak', 'extern int ga43_dynamic(void) __attribute__((weak_import));\nint (*slot)(void)=ga43_dynamic;\n')
    strong = obj('strong', 'int ga43_dynamic(void) {return 42;}\n')
    required = obj('required', 'extern int ga43_dynamic(void);\nint required(void) {return ga43_dynamic();}\n')
    dylib = d/'provider.dylib'
    args = [ld, '-arch', 'x86_64', '-platform_version', 'macos', '26.0', '26.5',
            '-syslibroot', sdk, '-lSystem', '-dylib', '-undefined', 'error']
    subprocess.run([*args, '-o', str(dylib), str(strong)], check=True)
    defs, weak_names, _ = symbols(nm, [weak])
    assert '_ga43_dynamic' in weak_names-defs
    defs, weak_names, _ = symbols(nm, [weak, required])
    assert '_ga43_dynamic' not in weak_names, 'a strong reference must never get a NULL fallback'
    dynamic, inspected = dynamic_definitions([*args, str(dylib)], d, nm)
    assert '_ga43_dynamic' in dynamic and dylib in inspected
    assert '_malloc' in dynamic and '_os_sync_wait_on_address' in dynamic, 'embedded libSystem reexports must be traversed'
    defs, weak_names, _ = symbols(nm, [weak])
    assert '_ga43_dynamic' not in (weak_names - defs - dynamic)
    # The actual strict linker still rejects the required symbol without its
    # provider. No permissive linker setting or fallback implementation exists.
    missing = subprocess.run([*args, '-o', str(d/'required.dylib'), str(required)], capture_output=True)
    assert missing.returncode != 0 and b'_ga43_dynamic' in missing.stderr
    subprocess.run([*args, '-o', str(d/'bound.dylib'), str(weak), str(dylib)], check=True)
    try:
        dynamic_definitions([*args, '-weak_framework', 'DoesNotExist'], d, nm)
    except ValueError: pass
    else: raise AssertionError('uninspected dynamic provider must fail closed')
print('PASS real dylib provider excluded from NULL set, embedded reexports, mixed strong reference refusal and strict missing-symbol failure; no runtime')
