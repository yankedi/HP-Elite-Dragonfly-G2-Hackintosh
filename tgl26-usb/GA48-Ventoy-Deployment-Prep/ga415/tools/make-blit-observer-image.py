#!/usr/bin/env python3
"""New isolated Ventoy image: PLANES2 baseline plus passive Blit observations."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga415/private/blit-observer'
REPORTS = ROOT / 'ga415/reports'
NAME = 'HP-Tahoe-TGL-GA415-BLITOBS.img'
GUID = '7C436110-AB2A-4BBB-A880-FE41995C9F82'
SPEC = importlib.util.spec_from_file_location('ga414_common', ROOT / 'ga414/tools/common.py')
c = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(c)


def main():
    os.umask(0o077)
    baseline = json.loads((REPORTS / 'PLANES2-IMAGE.json').read_text())
    signed = json.loads((REPORTS / 'BLIT-OBSERVER-SIGNED.json').read_text())
    source = ROOT / baseline['image']['path']
    assert c.sha(source) == baseline['image']['sha256']
    bundle = WORK / 'native-signed/NootedGreen.kext'
    assert c.inventory(bundle) == signed['bundle_inventory']
    original = (ROOT / 'ga415/private/planesfix/PLANES2-config.plist').read_bytes()
    old = plistlib.loads(original); args = old['NVRAM']['Add'][GUID]['boot-args']
    assert args == baseline['boot_args_after'] and '-ngreen415obs' not in args
    tokens = args.split()
    assert not set(tokens) & {'-ngreennoplanesfix', '-ngreenplanesxor', '-ngreenxefix', '-ngreenccs'}
    expected = copy.deepcopy(old); new_args = args + ' -ngreen415obs'
    expected['NVRAM']['Add'][GUID]['boot-args'] = new_args
    new_bytes = original.replace(args.encode(), new_args.encode(), 1)
    assert plistlib.loads(new_bytes) == expected and 'boot-args' in expected['NVRAM']['Delete'][GUID]
    config = WORK / 'BLITOBS-config.plist'; config.write_bytes(new_bytes)
    image = WORK / NAME
    with source.open('rb') as src, image.open('xb') as dest:
        shutil.copyfileobj(src, dest); dest.flush(); os.fsync(dest.fileno())
    c.run(['mcopy', '-o', '-i', str(image) + '@@1048576', config, '::/EFI/OC/config.plist'])
    for path in sorted(bundle.rglob('*')):
        if path.is_file():
            c.run(['mcopy', '-o', '-i', str(image) + '@@1048576', path,
                   '::/EFI/OC/Kexts/NootedGreen.kext/' + str(path.relative_to(bundle))])
    readback = WORK / 'image-readback'; readback.mkdir()
    c.run(['mcopy', '-s', '-i', str(image) + '@@1048576', '::/*', readback])
    actual = c.inventory(readback); wanted = dict(baseline['full_image_inventory'])
    wanted['EFI/OC/config.plist'] = c.sha(config)
    for name, digest in signed['bundle_inventory'].items(): wanted['EFI/OC/Kexts/NootedGreen.kext/' + name] = digest
    assert actual == wanted
    changes = sorted(name for name in actual if actual[name] != baseline['full_image_inventory'][name])
    assert all(name == 'EFI/OC/config.plist' or name.startswith('EFI/OC/Kexts/NootedGreen.kext/') for name in changes)
    assert len(changes) == 2  # Native ad-hoc signature is embedded; CodeResources/Info remain identical.
    validation = c.run([ROOT / 'out/ocvalidate', readback / 'EFI/OC/config.plist'])
    assert 'No issues found' in validation
    with image.open('rb') as a, source.open('rb') as b: assert a.read(1048576) == b.read(1048576)
    table = json.loads(c.run(['sfdisk', '--json', image])); parts = table['partitiontable']['partitions']
    assert len(parts) == 1 and parts[0]['start'] == 2048 and parts[0]['size'] == 2621440 and parts[0]['type'] == 'ef' and parts[0]['bootable']
    partition = WORK / 'observer-partition.fat'
    with image.open('rb') as src, partition.open('xb') as dest:
        src.seek(1048576); shutil.copyfileobj(src, dest)
    fsck = c.run(['fsck.fat', '-n', '-v', partition]); (WORK / 'fsck.txt').write_text(fsck)
    assert c.sha(source) == baseline['image']['sha256']
    report = {'status': 'BLIT_OBSERVER_IMAGE_BUILT_BOOT_NOT_TESTED', 'name': NAME,
              'image': c.record(image), 'baseline_PLANES2': c.record(source), 'NG_UUID': signed['MachO']['uuid'],
              'NG_binary_sha256': signed['binary']['sha256'], 'changed_files_vs_PLANES2': changes,
              'added_files': [], 'removed_files': [], 'full_image_inventory': actual,
              'boot_args_before': args, 'boot_args_after': new_args, 'ocvalidate_output': validation,
              'FAT_check': c.record(WORK / 'fsck.txt'), 'partition_table': table,
              'MBR_unchanged': True, 'route_changes': False, 'PLANES2_NOAUX_NOCCS3_preserved': True,
              'runtime_observer': 'NOT_OBSERVED', 'desktop_fix': 'NOT_VERIFIED', 'automatic_reboot': False}
    c.save(REPORTS / 'BLIT-OBSERVER-IMAGE.json', report)
    (REPORTS / (NAME + '.sha256')).write_text(c.sha(image) + '  ' + NAME + '\n')
    print(json.dumps({k: report[k] for k in ['status', 'image', 'NG_UUID', 'changed_files_vs_PLANES2']}))


if __name__ == '__main__':
    main()
