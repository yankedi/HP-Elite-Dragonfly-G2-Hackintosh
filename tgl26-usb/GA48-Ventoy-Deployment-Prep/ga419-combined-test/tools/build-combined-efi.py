#!/usr/bin/env python3
"""Build a combined peripheral test EFI from the fresh, verified current ESP backup."""
import copy
import hashlib
import io
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT.parent
SOURCES = PREP / 'ga418-peripherals/private/sources'
BEFORE = ROOT / 'private/backup/readback/boot/EFI/OC'
OUT = ROOT / 'private/candidate/OC'
REPORTS = ROOT / 'reports'
REPORTS.mkdir(exist_ok=True)

def sha(b):
    return hashlib.sha256(b).hexdigest()

def inventory(root):
    return {str(p.relative_to(root)): sha(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file()}

def dump(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, default=lambda b: b.hex())
        f.write('\n')

def run(args):
    p = subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=90)
    if p.returncode:
        raise RuntimeError(p.stdout + p.stderr)
    return {'argv': [str(x) for x in args], 'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}

def archive_bytes(name, expected):
    p = SOURCES / name
    data = p.read_bytes()
    assert sha(data) == expected
    receipt = json.loads(p.with_suffix(p.suffix + '.receipt.json').read_text())
    assert receipt['sha256'] == expected
    return data

def copy_kext(z, bundle):
    prefix = bundle + '/'
    assert any(n.startswith(prefix) for n in z.namelist()), bundle
    dest = OUT / 'Kexts' / bundle
    if dest.exists():
        shutil.rmtree(dest)
    for name in z.namelist():
        if not name.startswith(prefix) or name.endswith('/'):
            continue
        path = Path(name)
        assert not path.is_absolute() and '..' not in path.parts
        target = OUT / 'Kexts' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(name))

def entry(bundle, min_kernel=''):
    plist = plistlib.loads((OUT / 'Kexts' / bundle / 'Contents/Info.plist').read_bytes())
    executable = plist.get('CFBundleExecutable')
    return {'Arch': 'x86_64', 'BundlePath': bundle, 'Comment': 'GA419 combined peripheral test',
            'Enabled': True, 'ExecutablePath': 'Contents/MacOS/' + executable if executable else '',
            'MaxKernel': '', 'MinKernel': min_kernel, 'PlistPath': 'Contents/Info.plist'}

assert not OUT.exists()
backup = json.loads((ROOT / 'private/backup/VERIFIED.json').read_text())
assert backup['both_copies_and_all_members_verified']
assert sha(Path(backup['local_archive']).read_bytes()) == backup['sha256']
original = inventory(BEFORE)
assert original['Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen'] == 'e44ef32745cad51bd13a2006557f8d2076f96759a0afce867547a8466ab6dbbb'
shutil.copytree(BEFORE, OUT)
config = plistlib.loads((OUT / 'config.plist').read_bytes())
baseline_config = copy.deepcopy(config)

ci = archive_bytes('i2c-6be653-ci-artifact.zip', '71a8ad60b5e05dc8d95fa405d7e3920f5f76c7664ece6d902e1efacba19500ba')
with zipfile.ZipFile(io.BytesIO(ci)) as outer:
    assert outer.testzip() is None
    release = outer.read('Release/VoodooI2C-2.9.1-RELEASE.zip')
    with zipfile.ZipFile(io.BytesIO(release)) as z:
        assert z.testzip() is None
        for bundle in ['VoodooI2C.kext', 'VoodooI2CHID.kext']:
            copy_kext(z, bundle)

bt = archive_bytes('bt-2_5_2-release.zip', 'c26140b2091e7b41aab5e5fbdd322112908efc509f9fde3d71d4e3f91396b991')
with zipfile.ZipFile(io.BytesIO(bt)) as z:
    assert z.testzip() is None
    for bundle in ['IntelBluetoothFirmware.kext', 'IntelBTPatcher.kext']:
        copy_kext(z, bundle)
brcm = archive_bytes('brcm-2_7_2-release.zip', 'e1c1c55347526d031a8ae2fdd1f52efa3019161e497fb38e1cfa809752f8af21')
with zipfile.ZipFile(io.BytesIO(brcm)) as z:
    assert z.testzip() is None
    copy_kext(z, 'BlueToolFixup.kext')

aux = json.loads((ROOT / 'auxiliary/receipt.json').read_text())
for bundle in ['SMCBatteryManager.kext', 'ECEnabler.kext', 'BrightnessKeys.kext']:
    source = ROOT / 'auxiliary/Kexts' / bundle
    assert source.is_dir(), bundle
    assert not (OUT / 'Kexts' / bundle).exists()
    shutil.copytree(source, OUT / 'Kexts' / bundle)

# Keep existing injection order; insert the SMC plugin behind its core.
new = []
for old in config['Kernel']['Add']:
    if old['BundlePath'].startswith('VoodooI2C') and old['Enabled']:
        old = {**entry(old['BundlePath']), 'Comment': 'Official6be653a2 CI matched I2C/GPIO/HID set'}
    new.append(old)
    if old['BundlePath'] == 'VirtualSMC.kext' and old['Enabled']:
        new.append(entry('SMCBatteryManager.kext'))
config['Kernel']['Add'] = new + [entry('ECEnabler.kext'), entry('BrightnessKeys.kext'),
    entry('IntelBluetoothFirmware.kext', '21.0.0'), entry('IntelBTPatcher.kext', '21.0.0'), entry('BlueToolFixup.kext', '21.0.0')]
guid = '7C436110-AB2A-4BBB-A880-FE41995C9F82'
args = config['NVRAM']['Add'][guid]['boot-args'].split()
assert args.count('-vi2c-force-polling') == 1
args.remove('-vi2c-force-polling')
config['NVRAM']['Add'][guid]['boot-args'] = ' '.join(args)
# These values were absent in the fresh firmware snapshot; no Delete/reset.
before = json.loads((ROOT / 'private/backup/before.json').read_text())
assert not any(k.startswith('bluetooth') for k in before['variables'])
config['NVRAM']['Add'][guid]['bluetoothExternalDongleFailed'] = b'\x00'
config['NVRAM']['Add'][guid]['bluetoothInternalControllerInfo'] = b'\x00' * 14
assert config['NVRAM']['WriteFlash'] is False
config['Kernel']['Quirks']['DisableRtcChecksum'] = True

acpi = ROOT / 'private/acpi'
acpi.mkdir(parents=True)
compile_result = run(['iasl', '-p', acpi / 'SSDT-PNLF-HP-GA419', ROOT / 'acpi/SSDT-PNLF-HP-GA419.dsl'])
aml = acpi / 'SSDT-PNLF-HP-GA419.aml'
data = aml.read_bytes()
assert data[:4] == b'SSDT' and sum(data) & 255 == 0
shutil.copyfile(aml, OUT / 'ACPI' / aml.name)
config['ACPI']['Add'].append({'Comment': 'GA419 identity-only PC00.GFX0 PNLF, no MMIO', 'Enabled': True, 'Path': aml.name})
(OUT / 'config.plist').write_bytes(plistlib.dumps(config, sort_keys=False))

# Verify that all enabled binaries exist, are unique, and plugin dependencies
# are present earlier in the injection list. Apple kext dependencies are native.
ids = {}
kexts = []
for item in config['Kernel']['Add']:
    if not item['Enabled']:
        continue
    root = OUT / 'Kexts' / item['BundlePath']
    pl = plistlib.loads((root / item['PlistPath']).read_bytes())
    bundle_id = pl['CFBundleIdentifier']
    assert bundle_id not in ids, bundle_id
    for dependency, version in pl.get('OSBundleLibraries', {}).items():
        if dependency.startswith(('as.vit9696.', 'com.alexandred.', 'org.coolstar.', 'me.kishorprins.')):
            assert dependency in ids, (bundle_id, dependency)
    if item['ExecutablePath']:
        binary = root / item['ExecutablePath']
        assert binary.is_file() and binary.read_bytes()[:4] in [b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe']
    ids[bundle_id] = pl.get('CFBundleVersion')
    kexts.append({'path': item['BundlePath'], 'bundle_id': bundle_id, 'version': pl.get('CFBundleVersion'), 'dependencies': pl.get('OSBundleLibraries', {})})
for item in config['ACPI']['Add']:
    if item['Enabled']:
        assert (OUT / 'ACPI' / item['Path']).is_file()

expected = inventory(OUT)
protected = [p for p in original if p.startswith(('Kexts/NootedGreen.kext/', 'Kexts/Lilu.kext/', 'Kexts/AirportItlwm.kext/', 'Kexts/VirtualSMC.kext/', 'Drivers/')) or p == 'OpenCore.efi']
assert all(expected[p] == original[p] for p in protected)
validation = run([PREP / 'out/ocvalidate', OUT / 'config.plist'])
assert 'No issues found' in validation['stdout']
archive = ROOT / 'private/GA419-OC.tar.gz'
with tarfile.open(archive, 'x:gz') as t:
    t.add(OUT, arcname='OC')
with tarfile.open(archive) as t:
    members = {m.name[3:]: sha(t.extractfile(m).read()) for m in t if m.isfile()}
assert members == expected

changes = []
def diff(old, new, path=''):
    if type(old) != type(new):
        changes.append({'path': path, 'before': old, 'after': new})
    elif isinstance(old, dict):
        for key in sorted(old.keys() | new.keys()):
            if key not in old or key not in new:
                changes.append({'path': path + '/' + key, 'before': old.get(key), 'after': new.get(key)})
            else:
                diff(old[key], new[key], path + '/' + key)
    elif old != new:
        changes.append({'path': path, 'before': old, 'after': new})
diff(baseline_config, config)
report = {'status': 'COMBINED_EFI_BUILT_STATICALLY_VALIDATED_NOT_BOOT_TESTED', 'backup_sha256': backup['sha256'],
    'archive': str(archive), 'archive_sha256': sha(archive.read_bytes()), 'archive_bytes': archive.stat().st_size,
    'OC_inventory': expected, 'enabled_kexts': kexts, 'semantic_changes': changes,
    'changed_files': [p for p in original if p in expected and original[p] != expected[p]],
    'added_files': [p for p in expected if p not in original], 'removed_files': [p for p in original if p not in expected],
    'protected_core_graphics_wifi_OC_files_equal': protected, 'acpi_compile': compile_result, 'ocvalidate': validation,
    'input': 'official6be653a2 Release + fixed matched GPIO/HID; force-polling removed; native resource methods retained',
    'bluetooth': '2.5.2 firmware+patcher/2.7.2 BlueToolFixup; two previously absent zero-valued vars Add only, WriteFlashfalse; no Delete/reset',
    'brightness': 'PNLF identity+BrightnessKeys only, no GPU register writes or NGreen rebuild; actual brightness contract unproven',
    'battery': 'SMCBatteryManager+ECEnabler based on actual16bitEC/BIX',
    'not_installed_without_qualified_implementation': ['UVC global patches', 'AppleHDA root restoration', 'TGL NHI/USB4 ID spoof', 'ISH/DMIC/fingerprint', 'unmeasured full USB map', 'legacy WiFi root patch'],
    'source_IMG': None, 'result_IMG': None}
dump(REPORTS / 'BUILD.json', report)
print(json.dumps({'status': report['status'], 'enabled_kexts': len(kexts), 'archive_sha256': report['archive_sha256'],
     'changed_file_count': len(report['changed_files']), 'added_file_count': len(report['added_files']),
     'ocvalidate': validation['stdout']}, indent=2))
