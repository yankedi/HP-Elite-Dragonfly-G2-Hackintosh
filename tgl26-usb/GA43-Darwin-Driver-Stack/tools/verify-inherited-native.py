#!/usr/bin/env python3
"""Verify the four unchanged native objects, not just record unexpected hashes.

Offline, read-only historical inputs. SHA computation uses GNU sha256sum.
Fresh GA43 ABI-affected objects are compiled by link-xnu.sh in one invocation.
"""
from pathlib import Path
import re
import subprocess
import sys

if not __debug__:
    raise SystemExit('Evidence contracts require Python assertions; optimized Python is rejected')

root = Path(__file__).resolve().parents[1]
old = root.parent / 'GA42-Intel-Darwin-Integration'
kit = root.parent / 'GA41-i915-XNU/sources/mackernelsdk'
assert len(sys.argv) == 3
assert Path(sys.argv[1]).resolve() == (old/'artifacts/native-final-001').resolve(), 'unverified object directory'
assert Path(sys.argv[2]).resolve() == kit.resolve(), 'unverified kernel kit'
def run(argv, **kw):
    return subprocess.check_output(list(map(str, argv)), text=True, **kw)
def digest(path, expected):
    assert run(['sha256sum', path]).split()[0] == expected, str(path)
digest(old/'logs/seal-verification/receipt.json', 'fe3534a314a9cbab7442f8d02db1438f4192183e56fc33ce23496f75709f34af')
digest(old/'evidence-manifest/SHA256SUMS', '4d5545d57ca56656acb4e34562a0c531794c43c59a085846ee4233660a3bf90f')
run(['sha256sum', '--quiet', '--check', 'SHA256SUMS'], cwd=old/'evidence-manifest')
assert run(['git', '-C', old, 'rev-parse', 'HEAD']).strip() == 'ebc63b2bf254cc867b544ad7232ed7860580cb3f'
assert not run(['git', '--no-optional-locks', '-C', old, 'status', '--porcelain'])
names = ['xnu_memory', 'xnu_copy', 'gx_exec_validate', 'module']
manifest = (old/'evidence-manifest/local.sha256').read_text().splitlines()
selected = []
for name in names:
    suffix = f'./artifacts/native-final-001/{name}.o'
    lines = [line for line in manifest if line[66:] == suffix]
    assert len(lines) == 1, f'missing sealed object {name}'
    selected += lines
run(['sha256sum', '--quiet', '--check', '-'], input='\n'.join(selected)+'\n', cwd=old)
run(['sha256sum', '--quiet', '--check', 'evidence-manifest/kernel-headers.sha256'], cwd=old)
for relative in ['os-compat/xnu_memory.cpp', 'os-compat/xnu_copy.cpp',
                 'drm/gx_exec_validate.c', 'native/module.c', 'include/gx_ioctl.h', 'include/gx_xnu.h']:
    assert (root/'i915-xnu'/relative).read_bytes() == (old/'i915-xnu'/relative).read_bytes(), relative
# The unchanged units use opaque device pointers and these exact public value
# layouts, not struct gx_client. New function declarations do not alter them.
new = (root/'i915-xnu/include/gx_gem.h').read_text()
prior = (old/'i915-xnu/include/gx_gem.h').read_text()
for name in ['gx_ops', 'gx_map_result', 'gx_stats']:
    pattern = r'struct '+name+r'\s*\{.*?\};'
    a, b = re.search(pattern, new, re.S), re.search(pattern, prior, re.S)
    assert a and b and a.group() == b.group(), f'inherited ABI changed: {name}; rebuild required'
print('PASS pinned inherited objects, unchanged sources/public layouts and kernel-kit seal')
