#!/usr/bin/env python3
"""Build two new GA410 images from retained GA48; never modify original media."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'ga410/private/firstboot-images'
GUID = '7C436110-AB2A-4BBB-A880-FE41995C9F82'
SOURCE = ROOT / 'out/HP-Tahoe-TGL-GA48.img'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def run(args):
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError((args, result.returncode, result.stdout, result.stderr))
    return result.stdout + result.stderr


def main():
    assert sha(SOURCE) == '0facaf8ec3767c0235f326ad782cb7c000e881aca8274345cde2f3f235a693e4'
    OUT.mkdir(mode=0o700)
    spec = importlib.util.spec_from_file_location('original_builder', ROOT / 'tools/build-image.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    signed = OUT / 'signed-efi'
    with tarfile.open(ROOT / 'ga410/private/efi-signed-finalprep.tar.gz') as archive:
        for member in archive.getmembers():
            path = Path(member.name)
            assert not path.is_absolute() and '..' not in path.parts
            if member.isfile() and not any(p.startswith('._') for p in path.parts):
                dest = signed / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(archive.extractfile(member).read())
    signed_expected = {}
    for line in (ROOT / 'ga410/private/SIGNED-SHA256SUMS').read_text().splitlines():
        digest, path = line.split('  ', 1)
        path = path.removeprefix('./efi-add/')
        if path.startswith(('OC/Kexts/Lilu.kext/', 'OC/Kexts/NootedGreen.kext/')):
            signed_expected[path] = digest
    assert inventory(signed) == signed_expected
    original = plistlib.loads((ROOT / 'out/stage/EFI/OC/config.plist').read_bytes())
    records = []
    for kind, name, source_efi in [
        ('tgl', 'HP-Tahoe-TGL-GA410-CSR203-AMFI.img', ROOT / 'out/stage/EFI'),
        ('recovery', 'HP-Tahoe-Recovery-GA410-CSR0.img', ROOT / 'private/vesa/EFI'),
    ]:
        stage = OUT / kind
        shutil.copytree(source_efi, stage / 'EFI')
        path = stage / 'EFI/OC/config.plist'
        before = plistlib.loads(path.read_bytes())
        config = copy.deepcopy(before)
        variables = config['NVRAM']['Add'][GUID]
        if kind == 'tgl':
            variables['csr-active-config'] = bytes.fromhex('03020000')
            variables['boot-args'] += ' amfi_get_out_of_my_way=1'
            assert '-igfxvesa' not in variables['boot-args']
            for kext in ['Lilu.kext', 'NootedGreen.kext']:
                shutil.rmtree(stage / 'EFI/OC/Kexts' / kext)
                shutil.copytree(signed / 'OC/Kexts' / kext, stage / 'EFI/OC/Kexts' / kext)
        else:
            variables['csr-active-config'] = bytes(4)
            assert '-igfxvesa' in variables['boot-args'] and 'amfi_' not in variables['boot-args']
        delete = config['NVRAM']['Delete'].setdefault(GUID, [])
        for variable in ['boot-args', 'csr-active-config']:
            if variable not in delete:
                delete.append(variable)
        assert config['NVRAM']['WriteFlash'] is False
        assert config['Misc']['Security']['SecureBootModel'] == 'Disabled'
        assert config['Misc']['Boot']['ShowPicker'] and config['Misc']['Boot']['Timeout'] == 0
        assert config['Misc']['Debug']['ApplePanic'] and config['Misc']['Debug']['Target'] & 64
        assert len(variables['boot-args'].encode()) < 228
        path.write_bytes(plistlib.dumps(config, sort_keys=False))
        enabled = builder.enabled_paths(stage / 'EFI', config)
        ids = {entry['id'] for entry in enabled}
        assert not ids & {'org.smichaud.HookCase', 'com.xxxxx.driver.AppleIntelTGLGraphics',
                          'com.xxxxx.driver.AppleIntelTGLGraphicsFramebuffer'}
        if kind == 'tgl':
            assert [e['BundlePath'] for e in enabled][:2] == ['Lilu.kext', 'NootedGreen.kext']
            assert not any(e['BundlePath'] == 'WhateverGreen.kext' for e in enabled)
            assert config['DeviceProperties'] == original['DeviceProperties']
        else:
            assert not any(e['BundlePath'] == 'NootedGreen.kext' for e in enabled)
        validation = run([ROOT / 'out/ocvalidate', path])
        image = OUT / name
        shutil.copyfile(SOURCE, image)
        run(['mdeltree', '-i', str(image) + '@@1048576', '::/EFI'])
        run(['mcopy', '-s', '-i', str(image) + '@@1048576', stage / 'EFI', '::/'])
        note = ROOT / ('ga410/reports/BOOT-IN-' + ('TGL' if kind == 'tgl' else 'RECOVERY') + '.txt')
        run(['mcopy', '-o', '-i', str(image) + '@@1048576', note, '::/FIRST-BOOT.txt'])
        readback = OUT / (kind + '-readback')
        readback.mkdir()
        run(['mcopy', '-s', '-i', str(image) + '@@1048576', '::/EFI', readback])
        assert inventory(stage / 'EFI') == inventory(readback / 'EFI')
        with SOURCE.open('rb') as a, image.open('rb') as b:
            assert a.read(1048576) == b.read(1048576)
        records.append({
            'kind': kind, 'name': name, 'local_image': str(image.relative_to(ROOT)),
            'sha256': sha(image), 'bytes': image.stat().st_size,
            'config_sha256': sha(path), 'config_delta': builder.differences(before, config),
            'csr_hex_le': variables['csr-active-config'].hex(), 'boot_args': variables['boot-args'],
            'boot_args_bytes': len(variables['boot-args'].encode()), 'enabled_kexts': enabled,
            'ocvalidate_rc': 0, 'ocvalidate_output': validation,
            'efi_inventory': inventory(stage / 'EFI'), 'mtools_full_efi_readback_equal': True,
            'first_boot_note_sha256': sha(note),
            'boot_sector_and_partition_table_unchanged': True,
        })
    assert sha(SOURCE) == '0facaf8ec3767c0235f326ad782cb7c000e881aca8274345cde2f3f235a693e4'
    report = {'status': 'LOCAL_PREBOOT_IMAGES_VERIFIED', 'source': 'retained GA48 image',
              'source_sha256': sha(SOURCE), 'images': records,
              'physical_boot_performed': False, 'policy_applied': False}
    (ROOT / 'ga410/reports/FINALPREP-IMAGES.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps([{k: r[k] for k in ['name', 'sha256', 'bytes', 'boot_args', 'csr_hex_le']}
                      for r in records], indent=2))


if __name__ == '__main__':
    main()
