#!/usr/bin/env python3
"""Create GA414+PLANES2: one boot-argument removal, byte-identical signed kexts."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga415/private/planesfix'
REPORTS = ROOT / 'ga415/reports'
NAME = 'HP-Tahoe-TGL-GA415-PLANES2.img'
GUID = '7C436110-AB2A-4BBB-A880-FE41995C9F82'
spec = importlib.util.spec_from_file_location('prior_helpers', ROOT / 'ga414/tools/common.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)


def main():
    os.umask(0o077)
    abi = json.loads((REPORTS / 'PLANES2-ABI.json').read_text())
    assert abi['status'] == 'EXACT_25G83_PLANES2_ABI_VERIFIED_RUNTIME_PENDING'
    baseline = json.loads((ROOT / 'ga414/reports/IMAGE-LOCAL.json').read_text())
    source = ROOT / baseline['image']['path']
    assert c.sha(source) == baseline['image']['sha256']
    old_path = ROOT / 'ga414/private/mtools-readback/EFI/OC/config.plist'
    original = old_path.read_bytes(); old = plistlib.loads(original)
    args = old['NVRAM']['Add'][GUID]['boot-args']; tokens = args.split()
    assert tokens.count('-ngreennoplanesfix') == 1
    assert '-ngreentgltahoe' in tokens
    assert not set(tokens) & {'-ngreenplanesxor', '-ngreenxefix', '-ngreenccs'}
    new_bytes = original.replace(b' -ngreennoplanesfix', b'', 1)
    expected = copy.deepcopy(old)
    expected['NVRAM']['Add'][GUID]['boot-args'] = ' '.join(t for t in tokens if t != '-ngreennoplanesfix')
    assert plistlib.loads(new_bytes) == expected
    assert 'boot-args' in expected['NVRAM']['Delete'][GUID], 'OC must replace inherited boot-args'
    config = WORK / 'PLANES2-config.plist'
    with config.open('xb') as f: f.write(new_bytes)
    image = WORK / NAME
    with source.open('rb') as src, image.open('xb') as dest:
        shutil.copyfileobj(src, dest); dest.flush(); os.fsync(dest.fileno())
    c.run(['mcopy', '-o', '-i', str(image) + '@@1048576', config, '::/EFI/OC/config.plist'])
    readback = WORK / 'image-readback'; readback.mkdir()
    c.run(['mcopy', '-s', '-i', str(image) + '@@1048576', '::/*', readback])
    actual = c.inventory(readback); wanted = dict(baseline['full_image_inventory'])
    wanted['EFI/OC/config.plist'] = c.sha(config)
    assert actual == wanted
    changes = [name for name in actual if actual[name] != baseline['full_image_inventory'][name]]
    assert changes == ['EFI/OC/config.plist']
    assert (readback / 'EFI/OC/config.plist').read_bytes() == new_bytes
    ng = readback / 'EFI/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen'
    assert c.sha(ng) == abi['preserved_GA414_NG']['sha256']
    validation = c.run([ROOT / 'out/ocvalidate', readback / 'EFI/OC/config.plist'])
    assert '1.0.8' in validation and 'No issues found' in validation
    with image.open('rb') as a, source.open('rb') as b: assert a.read(1048576) == b.read(1048576)
    table = json.loads(c.run(['sfdisk', '--json', image])); parts = table['partitiontable']['partitions']
    assert len(parts) == 1 and parts[0]['start'] == 2048 and parts[0]['size'] == 2621440 and parts[0]['type'] == 'ef' and parts[0]['bootable']
    partition = WORK / 'planes2-partition.fat'
    with image.open('rb') as src, partition.open('xb') as dest:
        src.seek(1048576); shutil.copyfileobj(src, dest)
    fsck = c.run(['fsck.fat', '-n', '-v', partition])
    (WORK / 'planes2-fsck.txt').write_text(fsck)
    assert c.sha(source) == baseline['image']['sha256']
    report = dict(status='PLANES2_IMAGE_BUILT_BOOT_NOT_TESTED', image=c.record(image), baseline_GA414=c.record(source),
                  name=NAME, NG_UUID=abi['NG_UUID'], NG_UUID_unchanged=True, NG_binary_sha256=c.sha(ng),
                  changed_files_vs_GA414=changes, added_files=[], removed_files=[], full_image_inventory=actual,
                  logical_config_delta='Remove exactly -ngreennoplanesfix from NVRAM/Add boot-args',
                  boot_args_before=args, boot_args_after=expected['NVRAM']['Add'][GUID]['boot-args'],
                  inherited_boot_args_deleted_by_OC=True, all_kexts_and_dependencies_byte_identical=True,
                  ocvalidate_output=validation, FAT_check=c.record(WORK / 'planes2-fsck.txt'),
                  partition_table=table, MBR_unchanged=True, ABI_verification=c.record(REPORTS / 'PLANES2-ABI.json'),
                  planes2_runtime='NOT_OBSERVED', panic_FIX_runtime='NOT_VERIFIED', GPU_submitted=False,
                  automatic_reboot=False, installed_components_or_internal_EFI_changed=False)
    with (REPORTS / 'PLANES2-IMAGE.json').open('x') as f: json.dump(report, f, indent=2); f.write('\n')
    (REPORTS / (NAME + '.sha256')).write_text(c.sha(image) + '  ' + NAME + '\n')
    print(json.dumps({k: report[k] for k in ('status', 'image', 'changed_files_vs_GA414', 'NG_UUID')}))


if __name__ == '__main__': main()
