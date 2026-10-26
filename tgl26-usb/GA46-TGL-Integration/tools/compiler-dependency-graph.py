#!/usr/bin/env python3
"""Inventory actual Mach-O imports/exports, preserving two-level ordinals.

Unknown shared-cache exports are not classified as absent. An existing name
does not certify a C++ object's ABI. No Apple bytes are emitted into the graph.
"""
import argparse
import collections
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'GA45-AppleTGL-Native-Port'
EV=ROOT.parent/'GA44-TGL-25G83-Evidence'
spec=importlib.util.spec_from_file_location('macho',ROOT/'tools/macho-audit.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def graph(new=None):
    donor=BASE/'staging/private/donor/AppleIntelGraphicsShared.bundle/Contents/MacOS'
    sources={
        'ga45_adapter':BASE/'logs/build/compiler-001/libMTLIGCCompilerPluginOld.dylib',
        'ga45_bridge':BASE/'logs/build/compiler-001/libLLVMbridge.dylib',
        'donor_plugin':donor/'libMTLIGCCompilerPlugin.dylib',
        'donor_igc':donor/'libigc.dylib',
        'tahoe_plugin':EV/'input/tahoe-frameworks/apple-intel-graphics-shared/libMTLIGCCompilerPlugin.dylib',
        'tahoe_igc':EV/'input/tahoe-frameworks/apple-intel-graphics-shared/libigc.dylib',
        'gpucompiler_32023':EV/'input/tahoe-frameworks/gpucompiler-32023/libGPUCompilerImplLazy.dylib',
    }
    if new:
        sources.update(ga46_adapter=new/'libMTLIGCCompilerPlugin.dylib',ga46_bridge=new/'libLLVMbridge.dylib')
    # Historical build output locations are explicit and must not be guessed.
    if not sources['ga45_adapter'].exists():
        sources['ga45_adapter']=BASE/'logs/build/darwin-linked/libMTLIGCCompilerPluginOld.dylib'
    if not sources['ga45_bridge'].exists():
        sources['ga45_bridge']=BASE/'logs/build/darwin-linked/libLLVMbridge.dylib'
    images={k:m.inspect(p) for k,p in sources.items()}
    exports={k:{s['name'] for s in x['exports']} for k,x in images.items()}
    mtlexports={'_MTLCodeGenServiceBuildRequest','_MTLCodeGenServiceCreate',
                '_MTLCodeGenServiceDestroy','_MTLCodeGenServiceSetPluginPath'}
    nodes=[];edges=[]
    for k,x in images.items():
        deps=[v for v in x['libraries'] if v['command']!=0xd]
        nodes.append(dict(id=k,path=str(sources[k]),sha256=x['sha256'],
                          cpu_subtype=x['header']['subtype'],imports=sum(s['undefined'] for s in x['symbols']),
                          exports=sorted(exports[k]),libraries=x['libraries']))
        for s in x['symbols']:
            if not s['undefined']:continue
            n=s['name'];ordinal=s['descriptor']>>8
            provider=deps[ordinal-1]['name'] if 0<ordinal<=len(deps) else 'dyld dynamic/flat lookup'
            providers=[j for j,ex in exports.items() if j!=k and n in ex]
            cpp_llvm=n.startswith(('__ZN4llvm','__ZNK4llvm','__ZTVN4llvm','__ZTIN4llvm','__ZTSN4llvm'))
            status='LINK_RESOLVED' if providers and ordinal not in (0xfe,0xff,0) else 'RUNTIME_RESOLUTION_REQUIRED'
            reason='encoded two-level import; target runtime export inventory unavailable'
            if providers:reason='export exists in listed exact local image(s); load routing still required'
            if cpp_llvm and k.startswith('donor'):
                status='ABI_MISMATCH'
                reason='donor LLVM3902 C++ objects cannot be passed to LLVM32023 by name-only forwarding'
            edges.append(dict(referrer=k,symbol=n,mangling='Itanium C++' if n.startswith('__Z') else 'C/ObjC',
                              library_ordinal=ordinal,expected_provider=provider,
                              actual_export_providers=providers,export_present=bool(providers) if providers else None,
                              status=status,abi='3902->32023' if cpp_llvm and k.startswith('donor') else 'UNVERIFIED',
                              reason=reason,load_order='dependencies before plugin; exact-handle lookup, no RTLD_GLOBAL fallback',
                              safe_failure='loader rejects missing bound symbol; GA46 private-ABI entry is fail-stop'))
    nodes.extend([
        dict(id='tahoe_libLLVM_shared_cache',install_name='/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/32023/Libraries/libLLVM.dylib',
             export_inventory=None,status='RUNTIME_RESOLUTION_REQUIRED',reason='no offline shared-cache image/export table; dlopen by install name requires separately authorized probe'),
        dict(id='mtlcompiler_373_7',exports=sorted(mtlexports),version_current='32024',evidence=str(EV/'evidence/raw/probe-009-raw.txt'))])
    for name in ['_MTLCompilerBuildRequestWithOptions','_MTLCompilerBuildRequestWithSerializedBitcode','_getSerializedModule']:
        edges.append(dict(referrer='ga45_bridge' if name=='_getSerializedModule' else 'request_mapping',symbol=name,
                          expected_provider='mtlcompiler_373_7',actual_export_providers=[],export_present=False,
                          status='SYMBOL_ABSENT',abi='UNVERIFIED',reason='absent from actual complete four-entry MTLCompiler export table; plugin APIs are in plugin, not framework',
                          load_order='no signature-scan substitute',safe_failure='no call to guessed private address'))
    if new:
        for name in ['LLVMContextCreate','LLVMContextDispose',
                     'LLVMCreateMemoryBufferWithMemoryRangeCopy','LLVMParseBitcodeInContext',
                     'LLVMDisposeModule','LLVMDisposeMemoryBuffer','LLVMDisposeMessage',
                     'LLVMWriteBitcodeToMemoryBuffer','LLVMGetBufferStart','LLVMGetBufferSize']:
            edges.append(dict(referrer='ga46_bridge',symbol='_'+name,mangling='C',
                expected_provider='tahoe_libLLVM_shared_cache',actual_export_providers=[],
                export_present=None,status='RUNTIME_RESOLUTION_REQUIRED',abi='same-image C API only',
                load_order='pthread_once exact install-name RTLD_LOCAL before diagnostic request',
                safe_failure='return project-owned error1 and no bytes if any symbol is missing or image owners differ'))
        removed=sorted(exports['ga45_bridge']-exports['ga46_bridge'])
        for name in removed:
            if not name.startswith(('__ZN','__ZTV','__ZTI')):continue
            edges.append(dict(referrer='donor_plugin',symbol=name,mangling='Itanium C++',
                expected_provider='ga46_bridge',actual_export_providers=[],export_present=False,
                status='SYMBOL_ABSENT',abi='legacy unsafe shim intentionally removed',
                load_order='donor must fail binding until real LLVM3902 provider exists',
                safe_failure='dyld rejection; no fabricated destructor/Twine/stream implementation'))
    return dict(schema=1,nodes=nodes,edges=edges,counts=dict(collections.Counter(e['status'] for e in edges)),
                caveats=['LINK_RESOLVED means exact export exists plus encoded binding; not process runtime proof',
                         'export_present null is unknown, not absent',
                         'GA45 self-built adapter was misnamed Old; GA46 uses plugin name, reserving Old for Apple donor',
                         'C API serialization of current bitcode does not implement Apple MTL bitcode3902 downgrade'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--new',type=Path);a=p.parse_args()
    print(json.dumps(graph(a.new),indent=2))
