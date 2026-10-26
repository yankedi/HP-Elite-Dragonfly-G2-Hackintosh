"""Meaningful mutation controls for the delivery seal, in a private fixture only."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ga40_seal',ROOT/'tools/seal.py')
seal=importlib.util.module_from_spec(spec); spec.loader.exec_module(seal)
output=ROOT/'prototype/results/seal-integrity-001'
output.mkdir(exist_ok=False)
fixture=output/'fixture'; fixture.mkdir()
(fixture/'reference').mkdir(); (fixture/'logs').mkdir()
external=output/'external.bin'; external.write_bytes(b'external')
target=fixture/'payload.bin'; target.write_bytes(b'original')
os.symlink('payload.bin',fixture/'pointer')
(fixture/'reference/external-inputs.json').write_text(json.dumps({'files':[
    {'path':str(external),'bytes':external.stat().st_size,'sha256':seal.sha_file(external)}]})+'\n')
seal.ROOT=fixture
old_argv=sys.argv
checks=[]


def run(mode):
    sys.argv=['seal.py',mode]
    capture=io.StringIO()
    with contextlib.redirect_stdout(capture): seal.main()
    return json.loads(capture.getvalue())


def rejected(label,callback):
    try: callback()
    except (AssertionError,ValueError,FileNotFoundError): checks.append(label)
    else: raise AssertionError('Mutation accepted: '+label)


try:
    assert run('create')['status']=='PASS'
    before={str(p.relative_to(fixture)):p.read_bytes() for p in fixture.rglob('*') if p.is_file()}
    assert run('verify')['status']=='PASS'
    assert before=={str(p.relative_to(fixture)):p.read_bytes() for p in fixture.rglob('*') if p.is_file()}
    checks.append('verify_is_read_only')
    rejected('create_cannot_overwrite',lambda:run('create'))
    target.write_bytes(b'mutated!'); rejected('changed_file',lambda:run('verify')); target.write_bytes(b'original')
    extra=fixture/'unexpected'; extra.write_bytes(b'extra')
    rejected('extra_file',lambda:run('verify')); extra.unlink()
    target.rename(fixture/'temporarily-missing')
    rejected('removed_file',lambda:run('verify')); (fixture/'temporarily-missing').rename(target)
    mode=target.stat().st_mode & 0o7777
    target.chmod(mode^0o100); rejected('changed_mode',lambda:run('verify')); target.chmod(mode)
    link=fixture/'pointer'; link.unlink(); os.symlink('missing',link)
    rejected('changed_symlink_text',lambda:run('verify')); link.unlink(); os.symlink('payload.bin',link)
    external.write_bytes(b'altered!'); rejected('changed_external_dependency',lambda:run('verify')); external.write_bytes(b'external')
    assert run('verify')['status']=='PASS'
finally:
    sys.argv=old_argv
result={'status':'PASS','controls':checks,'count':len(checks),'scope':'GA40 fixture only; original lab not sealed/modified by this test'}
(output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
