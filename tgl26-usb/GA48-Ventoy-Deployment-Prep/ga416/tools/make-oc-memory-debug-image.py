#!/usr/bin/env python3
"""Build a separate GA416 OC DEBUG baseline; never deploy an installed EFI."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import struct
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga416/private/oc-memory-debug'
spec = importlib.util.spec_from_file_location('common', ROOT / 'ga414/tools/common.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
ASSET_SHA = '3f5f42b85703cf2c08e8dcd9245a52fb4326c9f4ef335c75b49f516cbbe131c6'
NAME = 'HP-Tahoe-GA416-OCDBG-BASELINE.img'


def pe_x64(raw):
    assert raw[:2] == b'MZ'
    off = struct.unpack_from('<I', raw, 0x3c)[0]
    assert raw[off:off + 4] == b'PE\0\0'
    assert struct.unpack_from('<H', raw, off + 4)[0] == 0x8664


def main():
    os.umask(0o077)
    baseline = json.loads((ROOT / 'ga416/reports/L3-6-IMAGE.json').read_text())
    source = ROOT / baseline['image']['path']
    assert c.sha(source) == baseline['image']['sha256']
    package = WORK / 'OpenCore-1.0.8-DEBUG.zip'
    assert c.sha(package) == ASSET_SHA
    stage = WORK / 'stage'
    stage.mkdir()
    config_path = ROOT / 'ga416/private/l3-six/image-readback/EFI/OC/config.plist'
    assert c.sha(config_path) == baseline['full_image_inventory']['EFI/OC/config.plist']
    before = plistlib.loads(config_path.read_bytes())
    config = plistlib.loads(config_path.read_bytes())
    config['Misc']['Debug'].update({'SysReport': True, 'DisplayLevel': 0x80000042,
                                    'LogModules': '*', 'Target': 0x43})
    assert not before['Misc']['Tools']
    config['Misc']['Tools'].append({
        'Arguments': '', 'Auxiliary': False, 'Comment': 'Diagnostic only: dump MAT/maps, then reboot before OS comparison',
        'Enabled': True, 'Flavour': 'Auto', 'FullNvramAccess': False,
        'Name': 'GA416 Memory Map Diagnostic', 'Path': 'MmapDump.efi',
        'RealPath': False, 'TextMode': True})
    assert config['Booter'] == before['Booter']
    assert config['Kernel'] == before['Kernel']
    assert config['UEFI'] == before['UEFI']
    assert config['NVRAM'] == before['NVRAM']
    assert config['ACPI'] == before['ACPI']
    files = ['EFI/BOOT/BOOTx64.efi', 'EFI/OC/OpenCore.efi',
             'EFI/OC/Drivers/OpenRuntime.efi', 'EFI/OC/Tools/MmapDump.efi']
    with zipfile.ZipFile(package) as z:
        for name in files:
            raw = z.read('X64/' + name)
            pe_x64(raw)
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
    path = stage / 'EFI/OC/config.plist'
    path.write_bytes(plistlib.dumps(config, sort_keys=False))
    validation = c.run([ROOT / 'out/ocvalidate', path])
    assert 'No issues found' in validation
    image = WORK / NAME
    with source.open('rb') as src, image.open('xb') as dst:
        shutil.copyfileobj(src, dst)
        dst.flush()
        os.fsync(dst.fileno())
    disk = str(image) + '@@1048576'
    c.run(['mmd', '-i', disk, '::/EFI/OC/Tools'])
    for path in sorted(stage.rglob('*')):
        if path.is_file():
            c.run(['mcopy', '-o', '-i', disk, path, '::/' + str(path.relative_to(stage))])
    readback = WORK / 'readback'
    readback.mkdir()
    c.run(['mcopy', '-s', '-i', disk, '::/*', readback])
    wanted = dict(baseline['full_image_inventory'])
    for name, digest in c.inventory(stage).items():
        wanted[name] = digest
    actual = c.inventory(readback)
    assert actual == wanted
    changed = sorted(k for k in baseline['full_image_inventory']
                     if actual[k] != baseline['full_image_inventory'][k])
    added = sorted(set(actual) - set(baseline['full_image_inventory']))
    assert set(changed) <= set(files + ['EFI/OC/config.plist'])
    assert added == ['EFI/OC/Tools/MmapDump.efi']
    assert c.sha(readback / 'EFI/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen') == baseline['NG_binary_sha256']
    with source.open('rb') as src, image.open('rb') as dst:
        assert src.read(1048576) == dst.read(1048576)
    fd, temporary = tempfile.mkstemp(prefix='ga416-ocdbg-', suffix='.fat', dir='/tmp/opencode')
    try:
        with os.fdopen(fd, 'wb') as dst, image.open('rb') as src:
            src.seek(1048576)
            shutil.copyfileobj(src, dst)
        fat_check = c.run(['fsck.fat', '-n', '-v', temporary])
    finally:
        Path(temporary).unlink()
    assert c.sha(source) == baseline['image']['sha256']
    report = {
        'status': 'OC_DEBUG_DIAGNOSTIC_BASELINE_BUILT_NOT_BOOTED', 'image': c.record(image),
        'baseline_image': baseline['image'], 'upstream_debug_asset': c.record(package),
        'official_asset_digest_verified': ASSET_SHA, 'changed_files': changed,
        'added_files': added, 'removed_files': [], 'full_image_inventory': actual,
        'Booter_Kernel_UEFI_NVRAM_ACPI_unchanged': True,
        'all_kext_files_unchanged': True, 'NG_UUID': baseline['NG_UUID'],
        'NG_binary_sha256': baseline['NG_binary_sha256'], 'ocvalidate_output': validation,
        'fat_check': fat_check, 'MBR_unchanged': True,
        'debug_settings': config['Misc']['Debug'], 'tool': config['Misc']['Tools'][0],
        'mmap_tool_limit': 'MmapDump reconstructs in-memory MAT attributes while comparing maps; diagnostic-only boot, manually reboot before OS comparison. Not an exact final macOS handoff map.',
        'persistent_nvram_logging': False, 'deployed': False, 'booted': False,
        'internal_efi_modified': False, 'linux_evidence': 'ga416/private/memory-map/linux-memory-context-20261025T130022Z.json'}
    c.save(ROOT / 'ga416/reports/OC-MEMORY-DEBUG-IMAGE.json', report)
    (WORK / (NAME + '.sha256')).write_text(c.sha(image) + '  ' + NAME + '\n')
    print(json.dumps({k: report[k] for k in ['status', 'image', 'changed_files', 'added_files']}, indent=2))


if __name__ == '__main__':
    main()
