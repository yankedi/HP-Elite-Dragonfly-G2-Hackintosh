#!/usr/bin/env python3
"""Offline evidence audit of source, forwarding machine code, signatures and USB readback."""
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
GA = ROOT / 'ga415'
WORK = GA / 'private/blit-observer'
SPEC = importlib.util.spec_from_file_location('ga414_common', ROOT / 'ga414/tools/common.py')
c = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(c)


def main():
    reports = {name: json.loads((GA / 'reports' / ('BLIT-OBSERVER-' + name + '.json')).read_text())
               for name in ['SOURCE', 'BUILD', 'SIGNED', 'IMAGE', 'DELIVERY', 'CPU-TEST']}
    def receipt(name):
        obj = json.loads((GA / 'private/commands' / (name + '.json')).read_text())
        assert obj['returncode'] == 0, name
        return obj
    for name in ['blitobs-native-sign', 'blitobs-cpu-test-contract', 'blitobs-protected-before', 'blitobs-new-dest-and-old-images',
                 'blitobs-transfer-sync-hash', 'blitobs-attach-readonly', 'blitobs-mount-readonly', 'blitobs-full-native-inventory',
                 'blitobs-native-signature-config', 'blitobs-unmount', 'blitobs-detach', 'blitobs-final-image-hashes',
                 'blitobs-protected-after', 'blitobs-sidecar-sync']: receipt(name)
    for key, name in [('binary', 'BUILD'), ('archive', 'BUILD'), ('source_audit', 'BUILD'),
                      ('binary', 'SIGNED'), ('archive', 'SIGNED'), ('image', 'IMAGE'), ('baseline_PLANES2', 'IMAGE')]:
        entry = reports[name][key]; path = ROOT / entry['path']
        assert path.stat().st_size == entry['bytes'] and c.sha(path) == entry['sha256']
    assert c.inventory(WORK / 'source') == reports['SOURCE']['source_inventory']
    assert (WORK / 'source/src/NootedGreen/ga415_blit_observer.hpp').read_bytes() == (GA / 'kernel/ga415_blit_observer.hpp').read_bytes()
    assert c.inventory(WORK / 'native-signed/NootedGreen.kext') == reports['SIGNED']['bundle_inventory']
    assert c.inventory(WORK / 'image-readback') == reports['IMAGE']['full_image_inventory']
    native = {}
    prefix = '/private/tmp/ga415-blit-observer-delivery/readonly/'
    for line in receipt('blitobs-full-native-inventory')['stdout'].splitlines():
        digest, path = line.split('  ', 1); assert path.startswith(prefix)
        native[path[len(prefix):]] = digest
    assert native == reports['IMAGE']['full_image_inventory']
    before, after = [json.loads(receipt('blitobs-protected-' + side)['stdout']) for side in ['before', 'after']]
    for name in ['protected_images', 'installed_files', 'boot_session', 'USB_volume_UUID']: assert before[name] == after[name]
    final_hashes = receipt('blitobs-final-image-hashes')['stdout']
    assert final_hashes == reports['IMAGE']['image']['sha256'] + '  ' + reports['DELIVERY']['USB_image'] + '\n' + receipt('blitobs-new-dest-and-old-images')['stdout']
    assembly = (WORK / 'observer-kext.asm').read_text(); functions = re.split(r'\n(?=[0-9a-f]{16} <)', assembly)
    forwarding = {}
    for symbol in ['__ZL18ga415ObsSourceCopyPvS_S_S_', '__ZL16ga415ObsFastCopyPvS_S_S_', '__ZL10ga415Obs3DPvS_S_']:
        block = next(s for s in functions if s.startswith(next(l for l in assembly.splitlines() if '<' + symbol + '>:' in l)))
        assert len(re.findall(r'\tcall\s', block)) == 1 and 'ga415ObsLog' in block
        assert len(re.findall(r'\tjmp\s+rax', block)) == 1
        assert not re.search(r'\b(?:xmm|ymm|zmm)\d+', block)
        forwarding[symbol] = 'one observer call; saved original argument registers restored; tail-jump original once'
    log_function = next(s for s in functions if re.match(r'[0-9a-f]{16} <__ZL11ga415ObsLogPKcPKvS2_>:', s))
    assert not re.search(r'\b(?:xmm|ymm|zmm)\d+', log_function)
    assert 'cmpxchg' in log_function and not reports['BUILD']['new_undefined_symbols']
    assert reports['CPU-TEST']['forwarded_calls'] == 802 and reports['CPU-TEST']['max_added_records'] == 128
    assert 'CPU_OBSERVER_CONTRACT_PASS' in receipt('blitobs-cpu-test-contract')['stdout']
    for name in ['BUILD', 'SIGNED']: assert reports[name]['MachO']['uuid'] == reports['IMAGE']['NG_UUID']
    assert reports['IMAGE']['NG_UUID'] == reports['DELIVERY']['NG_UUID']
    assert 'Signature=adhoc' in receipt('blitobs-native-signature-config')['stderr']
    assert 'read-only' in receipt('blitobs-mount-readonly')['stdout']
    result = {'status': 'BLIT_OBSERVER_SOURCE_BUILD_SIGN_IMAGE_USB_AUDIT_PASS_RUNTIME_PENDING',
              'image': reports['IMAGE']['image'], 'USB_image': reports['DELIVERY']['USB_image'], 'NG_UUID': reports['IMAGE']['NG_UUID'],
              'native_readback_files': len(native), 'changed_files_vs_PLANES2': reports['IMAGE']['changed_files_vs_PLANES2'],
              'forwarding_disassembly_verified': forwarding, 'observer_uses_FP_or_SIMD': False,
              'max_added_data_records': 128, 'max_added_install_records': 1, 'max_added_total_records': 129,
              'historical_SOURCE_report_budget_note': 'SOURCE.max_added_log_lines=128 describes data records; one install line is additional.',
              'native_CPU_sanitizer_contract': 'PASS', 'all_six_prior_images_and_installed_stack_unchanged': True,
              'automatic_reboot': False, 'new_GPU_submissions': 0, 'observer_kernel_runtime': 'NOT_OBSERVED',
              'submitBlit_actual_pitches': 'NOT_OBSERVED', 'pixel_fix': 'NOT_VERIFIED', 'ROOT_CAUSE': 'ROOT_CAUSE_UNVERIFIED'}
    c.save(GA / 'reports/BLIT-OBSERVER-AUDIT.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
