#!/usr/bin/env python3
"""Correlate copied KC identities with read-only loaded metadata, not RAM bytes."""
import hashlib
import json
import pathlib
import plistlib
import re

ROOT=pathlib.Path(__file__).resolve().parents[1]
RE=re.compile(r'^\s*\d+\s+\d+\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+(\S+)\s+\(([^)]+)\)\s+([0-9A-Fa-f-]{36})',re.M)
TARGETS=['com.apple.driver.AppleIntelICLGraphics','com.apple.driver.AppleIntelICLLPGraphicsFramebuffer','com.apple.iokit.IOAcceleratorFamily2']


def loaded(path):
    return {m[3]:{'address':int(m[0],16),'size':int(m[1],16),'wired_size':int(m[2],16),
                   'version':m[4],'uuid':m[5].upper()} for m in RE.findall(path.read_text())}


def main():
    live=loaded(ROOT/'logs/remote-loaded.stdout')
    postpath=ROOT/'logs/remote-loaded_postcopy.stdout'
    post=loaded(postpath) if postpath.exists() else {}
    inspect=(ROOT/'logs/remote-kc_inspect_v2.stdout').read_text()
    inventories=[json.loads(p.read_text()) for p in (ROOT/'analysis/kc').glob('*.kc.json')]
    result={'scope':'Exact on-disk 25G83 KC images vs loaded UUID/version/address metadata; NOT live instruction-byte attestation',
            'images':[],'kernel_slide_query':(ROOT/'logs/remote-slide.stdout').read_text().splitlines()[:2],
            'caveat':'Lilu/WhateverGreen loaded; in-memory patches do not change Mach-O UUID. kern.slide is not assumed equal to System KC slide.'}
    sysver=ROOT/'inputs/macos-readonly/System/Library/CoreServices/SystemVersion.plist'
    result['system_version']=plistlib.loads(sysver.read_bytes()) if sysver.exists() else None
    for target in TARGETS:
        matches=[(inv,im) for inv in inventories for im in inv['images'] if im['name']==target]
        if len(matches)!=1:
            result['images'].append({'name':target,'status':'BLOCKED','reason':'unique KC image absent'})
            continue
        inv,im=matches[0]
        entry=next(e for e in inv['collection']['entries'] if e['name']==target)
        diskplist=ROOT/'inputs/macos-readonly/System/Library/Extensions'/(target.split('.')[-1]+'.kext')/'Contents/Info.plist'
        p=plistlib.loads(diskplist.read_bytes()) if diskplist.exists() else {}
        info={'name':target,'source':inv['source'],'source_sha256':inv['sha256'],
              'kc_uuid':inv['collection']['uuid'],'image_uuid':im['uuid'],
              'entry_fileoff':entry['fileoff'],'entry_va':entry['vmaddr'],
              'segments':im['segments'],'live_pre':live.get(target),'live_post':post.get(target),
              'disk_plist_version':p.get('CFBundleVersion'),'disk_plist_executable':p.get('CFBundleExecutable'),
              'disk_executable_present':False}
        liveentry=live.get(target,{})
        checks={'uuid_matches_loaded':liveentry.get('uuid')==im['uuid'],
                'uuid_in_remote_kmutil_disk_inspect':im['uuid'] in inspect,
                'plist_matches_loaded_version':p.get('CFBundleVersion')==liveentry.get('version'),
                'postcopy_identity_stable':bool(post) and live.get(target)==post.get(target),
                'system_build_25G83':bool(result['system_version']) and result['system_version'].get('ProductBuildVersion')=='25G83'}
        info['checks']=checks
        info['derived_kc_runtime_load_bias']=liveentry['address']-entry['vmaddr'] if liveentry else None
        info['load_bias_not_kaslr_slide']='Includes KC mapping origin; random slide cannot be separated from this observation alone'
        info['status']='VERIFIED_DISK_KC_AND_LOADED_METADATA' if all(checks.values()) else 'PARTIAL'
        result['images'].append(info)
    result['runtime_bytes']='NOT_READ'
    result['driver_original_bytes']='from copied stock KC; not presumed bytes at currently patched entry'
    (ROOT/'analysis/binary-identity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
