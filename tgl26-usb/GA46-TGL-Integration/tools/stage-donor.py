#!/usr/bin/env python3
"""Hash-pinned, reversible, private-only staging of the inherited 18 patches.

Only the three linkage/path edits are applied to an experiment copy. Native
GPU compression/AUX/clear/display patches remain excluded, even if they match.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'GA45-AppleTGL-Native-Port'
CONFIG=ROOT.parent/'GA43-AppleTGL-Tahoe/configs/tgl-9a49-25G83.json'
DONOR=BASE/'staging/private/donor'
SELECTED={'mtl.header.ncmds_sizeofcmds','mtl.header.load_libxedrv','mtl.compiler.plugin_path'}
spec=importlib.util.spec_from_file_location('macho',ROOT/'tools/macho-audit.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def digest(b):return hashlib.sha256(b).hexdigest()

def prepare():
    config=json.loads(CONFIG.read_text())['binaries']
    baseline=json.loads((ROOT/'manifests/donor-audit-18.json').read_text())
    records=[];payloads={}
    for entry in baseline['binaries']:
        key=entry['key'];cfg=config[key];rel=cfg['relative_path'];source=DONOR/rel
        raw=source.read_bytes();assert digest(raw)==entry['sha256'], f'input hash {key}'
        data=bytearray(raw);patches=[]
        assert {p['id'] for p in entry['patches']}=={p['id'] for p in cfg['patches']}
        for p in cfg['patches']:
            old=bytes.fromhex(p.get('old_hex',p.get('pattern_hex','')))
            new=bytes.fromhex(p.get('new_hex',p.get('replace_hex','')))
            assert old and len(old)==len(new), f'length {p["id"]}'
            matches=[];pos=raw.find(old)
            while pos>=0:
                matches.append(pos);pos=raw.find(old,pos+1)
            if 'offset' in p:
                off=p['offset'];assert raw[off:off+len(old)]==old, p['id']
                condition='whole-file SHA + fixed offset + exact bytes (short/padding bytes need not be globally unique)'
            else:
                assert len(matches)==p['expected_matches']==1, p['id']
                off=matches[0];condition='whole-file SHA + one exact pattern occurrence'
            selected=p['id'] in SELECTED
            if selected:data[off:off+len(new)]=new
            patches.append(dict(id=p['id'],offset=off,old_hex=old.hex(),new_hex=new.hex(),
                                global_match_count=len(matches),unique_condition=condition,applied=selected,
                                safety='OFFLINE_LINKAGE_EXPERIMENT_ONLY' if selected else 'EXCLUDED_UNVERIFIED_OR_RPL',
                                reason=p.get('reason',''),reversible=True))
        undo=bytearray(data)
        for p in reversed(patches):
            if p['applied']:
                off=p['offset'];new=bytes.fromhex(p['new_hex']);old=bytes.fromhex(p['old_hex'])
                assert undo[off:off+len(new)]==new;undo[off:off+len(old)]=old
        assert undo==raw,'reverse hash'
        payloads[rel]=bytes(data)
        records.append(dict(key=key,relative_path=rel,original_sha256=digest(raw),
                            patched_sha256=digest(data),reverse_sha256=digest(undo),patches=patches,
                            signature='INVALID_AFTER_MODIFICATION' if data!=raw else 'UNCHANGED_NOT_VERIFIED'))
    assert sum(len(r['patches']) for r in records)==18
    return records,payloads

def stage(destination):
    destination=destination.absolute()
    private=(ROOT/'staging').resolve()
    assert private in destination.resolve().parents,'output must be under GA46 staging'
    assert not destination.exists(),'refuse overwrite'
    records,payloads=prepare() # preflight the entire transaction before copying
    shutil.copytree(DONOR,destination,symlinks=True)
    for rel,data in payloads.items():
        target=destination/rel
        assert destination.resolve() in target.resolve().parents,'symlink escape'
        target.write_bytes(data)
        parsed=m.inspect(target)
        if parsed['header']['filetype']==11:m.validate_kext(parsed)
        assert parsed['header']['filetype']==m.inspect(DONOR/rel)['header']['filetype'],'filetype change forbidden'
    result=dict(schema=1,source=str(DONOR),output=str(destination),
                source_config_sha256=digest(CONFIG.read_bytes()),records=records,
                status='PRIVATE_OFFLINE_STAGED_NOT_DEPLOYABLE',applied=sorted(SELECTED),
                review='independent reverse/diff verifier required; byte match is not semantic ABI approval',
                install_name='/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib',
                deployment='DEPLOYMENT_BLOCKED',gpu='GPU_NOT_TESTED')
    (destination/'PATCH-PLAN.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('destination',type=Path);a=p.parse_args()
    print(json.dumps(stage(a.destination),indent=2))
