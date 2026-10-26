#!/usr/bin/env python3
"""Exact symbol-byte evidence, not a Hook installer or trampoline builder."""
import hashlib
import json
import pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]


def main():
    image='com.apple.driver.AppleIntelICLGraphics'
    fs=json.loads((ROOT/'analysis/disassembly'/f'{image}.json').read_text())
    identity=json.loads((ROOT/'analysis/binary-identity.json').read_text())
    bias=next(i['derived_kc_runtime_load_bias'] for i in identity['images'] if i['name']==image)
    rows=[]
    for name,source_signature,arguments,ret in [
        ('__ZN20IGHardwareRingBuffer14doHangAnalysisEv','uint32_t(void *that)',{'rdi':'ring this'},'observed EAX=2 at0x13edcebe; no sret; full C++ return type not mangled'),
        ('__ZN16IntelAccelerator13SafeForceWakeEbj','void(void *that, bool enable, uint32_t domain)',{'rdi':'accelerator this','esi/sil':'bool enable','edx':'unsigned domain bitmask'},'source wrapper void; callsites ignore accumulator; no ACK status return proven'),
    ]:
        f=next(f for f in fs if name in f['symbols']);cuts=[]
        for minimum in [5,14]:
            count=0;stolen=[]
            for i in f['instructions']:
                count+=i['size'];stolen.append(i)
                if count>=minimum:break
            cuts.append({'minimum_jump_bytes':minimum,'whole_instruction_prefix_bytes':count,
                         'prefix_bytes':''.join(i['bytes'] for i in stolen),
                         'instructions':stolen,
                         'meaning':'offline prefix boundary only; not proof Lilu trampoline/routing is correct'})
        rows.append({'symbol':name,'demangled':f['demangled'],'image_uuid':f['image_uuid'],
                     'source':f['source'],'source_sha256':f['source_sha256'],
                     'entry_kc_va':f['entry_va'],'kc_fileoff':f['kc_fileoff'],
                     'entry_relative_to_image_header':f['entry_va']-0x13e9f000,
                     'runtime_metadata_derived_address':f['entry_va']+bias,
                     'runtime_bytes':'NOT_READ; existing Lilu/WhateverGreen may patch entries',
                     'source_wrapper_signature':source_signature,'arguments':arguments,'return_evidence':ret,
                     'prefixes':cuts})
    result={'scope':'x86_64 exact stock KC instruction and existing source-wrapper ABI audit, not installed Hook',
            'ga33_source_sha256':hashlib.file_digest((ROOT/'inputs/kern_igfx.cpp').open('rb'),'sha256').hexdigest(),
            'source_lines':{'routing':[1015,1016],'wrapDoHangAnalysis':[1455,1488],'wrapSafeForceWake':[1490,1517]},
            'entries':rows,'new_route_requests':0,'real_mmio_backend':'NONE',
            'unproven':['live original instruction bytes','Lilu patch/trampoline relocation in actual loaded image',
                        'all caller lock/context and lifetime contracts','atomic per-hang ownership of GA33 shared flags',
                        'power/reset exclusion at original SafeForceWake return']}
    (ROOT/'analysis/hook-abi.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps([{'symbol':r['symbol'],'entry':hex(r['entry_kc_va']),'relative':hex(r['entry_relative_to_image_header']),
                       'runtime_derived':hex(r['runtime_metadata_derived_address'])} for r in rows],indent=2))


if __name__=='__main__':main()
