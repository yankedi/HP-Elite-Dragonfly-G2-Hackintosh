#!/usr/bin/env python3
"""Summarize direct evidence; distinguish signature validity, trust and reachability."""
import json
from pathlib import Path
import plistlib

ROOT = Path(__file__).resolve().parents[1]


def native(name):
    return json.loads((ROOT / 'private/readonly' / (name + '.json')).read_text())


def main():
    package = json.loads((ROOT / 'private/GA47-MANIFEST.expected.json').read_text())
    native_bundles = json.loads((ROOT / 'reports/NATIVE-BUNDLES.json').read_text())
    assert native_bundles['bundle_count'] == 13 and native_bundles['binary_count'] == 31
    assert all(x['otool_returncode'] == 0 for x in native_bundles['binaries'])
    assert native('firmlinks-requested')['stdout'].strip() == '/System/Library/Caches\tSystem/Library/Caches'
    stats = [line.split()[:2] for line in native('caches-stat')['stdout'].splitlines()]
    assert len(stats) == 2 and stats[0] == stats[1]
    data = plistlib.loads(native('data-info')['stdout'].encode())
    assert data['DeviceIdentifier'] == 'disk1s1' and data['WritableVolume']
    cachemap = native('llvm-cache-map')['stdout']
    assert '/32023/Libraries/libLLVM.dylib' in cachemap
    assert '/3802/' not in cachemap and '/3902/' not in cachemap
    for version in ['3802', '3902']:
        r = native('llvm' + version + '-native')
        assert 'file not found' in r['stderr']
    assert '-linked_dylibs:' in native('llvm32023-native')['stdout']
    providers = {}
    for kind in ['inspect-system', 'inspect-aux']:
        for line in native(kind)['stdout'].splitlines():
            fields = line.split('\t')
            if len(fields) >= 3:
                providers[fields[0]] = {'version': fields[1], 'path': fields[2], 'source': kind}
    bundles = native_bundles['bundles']
    own = {b['info']['CFBundleIdentifier']: b['info'] for b in bundles if b.get('info', {}).get('CFBundleIdentifier')}
    dependencies = []
    for b in bundles:
        for name, requested in (b.get('info', {}).get('OSBundleLibraries') or {}).items():
            row = {'consumer': b['path'], 'identifier': name, 'requested': requested}
            if name in own:
                row.update({'provider': 'STAGED_NOT_INSTALLED', 'version': own[name]['CFBundleVersion'], 'compatible': own[name]['OSBundleCompatibleVersion']})
            elif name in providers:
                row['provider'] = providers[name]
            else:
                row['provider'] = 'NOT_IN_KC_ID_INVENTORY_NATIVE_RESOLVER_NOT_RUN'
            dependencies.append(row)
    binaries = package['binaries']
    installed = {'/' + b['path'].removeprefix('payload/'): b for b in binaries if b['path'].startswith('payload/')}
    entry = '/System/Library/Caches/xe.bundle/Contents/MacOS/libMTLIGCCompilerPlugin.dylib'
    reachable, todo = set(), [entry]
    while todo:
        path = todo.pop()
        if path in reachable:
            continue
        reachable.add(path)
        todo.extend(d['name'] for d in installed[path]['libraries'] if d['command'] != 13 and d['name'] in installed)
    legacy = [{'consumer': b['path'], 'dependency': d['name'], 'load_command': d['command'], 'required_not_weak': d['command'] == 12, 'reachable_from_adapter_via_static_edges': '/' + b['path'].removeprefix('payload/') in reachable} for b in binaries for d in b['libraries'] if '/3802/' in d['name'] or '/3902/' in d['name']]
    assert len(legacy) == 5 and all(x['required_not_weak'] for x in legacy)
    report = {'status': 'PREINSTALL_AUDIT_COMPLETE_NOT_INSTALL_READY', 'caches': {'firmlink': native('firmlinks-requested')['stdout'].strip(), 'logical_and_data_same_device_inode': stats, 'data_volume': data['DeviceIdentifier'], 'data_volume_writable': data['WritableVolume'], 'root_access_evidence': 'ROOT-ACCESS.json', 'ssv_change_required_by_caches': False}, 'bundle_structural_pass': [b['path'] for b in bundles if b['verify_returncode'] == 0], 'bundle_structural_fail': [{'path': b['path'], 'returncode': b['verify_returncode'], 'error': b['verify_stderr']} for b in bundles if b['verify_returncode']], 'codesign_pass_does_not_imply_kext_or_platform_trust': True, 'kext_dependency_rows': dependencies, 'adapter_static_package_closure': sorted(reachable), 'legacy_llvm_required_edges': legacy, 'legacy_llvm_on_target': {'3802': False, '3902': False, '32023': True, 'dyld_info_legacy_returncode_caveat': 'rc0 despite file-not-found on stderr; semantic result is absence'}, 'legacy_runtime_conclusion': 'Loading any of the five retained consumers requires missing LLVM and is a real dyld blocker for that load. None is on the adapter static reexport closure; dynamic-path use is not proven without executing compiler/Metal code, which was not authorized.', 'sandbox': {'profile': '/System/Library/Sandbox/Profiles/com.apple.MTLCompilerService.sb', 'system_library_file_map_rule_present': True, 'GPUBundles_allow_in_profile_is_apple_internal_conditional': True, 'runtime_entitlements_extensions_library_validation': 'NOT_EXECUTED_NOT_PROVEN'}, 'native_kext_link_or_KC_registration': 'NOT_ATTEMPTED_NO_AUTHORIZATION'}
    (ROOT / 'reports/PREREQUISITES.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: corrected firmlink; native 13 bundles/31 binaries; provider IDs and required missing legacy LLVM edges classified without loading')


if __name__ == '__main__':
    main()
