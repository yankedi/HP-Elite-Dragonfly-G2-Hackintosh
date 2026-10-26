#!/usr/bin/env python3
"""Native ad-hoc sign isolated observer artifact; never install or load it."""
import importlib.util
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga415/private/blit-observer'
BASE = '/private/tmp/ga415-blit-observer-sign'
SPEC = importlib.util.spec_from_file_location('ga414_common', ROOT / 'ga414/tools/common.py')
c = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(c)
sys.path.insert(0, str(ROOT / 'ga410/tools'))
import normal_ssh
import remote


def main():
    normal_ssh.configure(); remote.ROOT = ROOT / 'ga415'
    build = json.loads((ROOT / 'ga415/reports/BLIT-OBSERVER-BUILD.json').read_text())
    archive = ROOT / build['archive']['path']
    assert c.sha(archive) == build['archive']['sha256']
    remote.run('blitobs-sign-work', f'set -eu\numask 077\nmkdir {BASE}\nmkdir {BASE}/signed', timeout=15)
    remote.upload(archive, BASE + '/cross.tar.gz', timeout=30)
    row = remote.run('blitobs-native-sign', f'''set -eu
test "$(/usr/sbin/sysctl -n kern.bootsessionuuid)" = REDACTED-SESSION-ID
test "$(/usr/bin/shasum -a 256 {BASE}/cross.tar.gz | /usr/bin/awk '{{print $1}}')" = {c.sha(archive)}
/usr/bin/tar -xpf {BASE}/cross.tar.gz -C {BASE}/signed
/usr/bin/codesign --force --sign - --timestamp=none {BASE}/signed/NootedGreen.kext
/usr/bin/codesign --verify --strict --deep --verbose=4 {BASE}/signed/NootedGreen.kext
/usr/bin/codesign --display --verbose=4 {BASE}/signed/NootedGreen.kext
/usr/bin/dwarfdump --uuid {BASE}/signed/NootedGreen.kext/Contents/MacOS/NootedGreen
/usr/bin/tar -czpf {BASE}/signed.tar.gz -C {BASE}/signed NootedGreen.kext
/usr/bin/shasum -a 256 {BASE}/signed.tar.gz
''', timeout=50)
    assert 'Signature=adhoc' in row['stderr'] + row['stdout'] and build['MachO']['uuid'] in row['stdout']
    signed = WORK / 'NootedGreen-GA415-BLITOBS-native-signed.tar.gz'
    remote.download(BASE + '/signed.tar.gz', signed, timeout=30)
    assert c.sha(signed) in row['stdout']
    dest = WORK / 'native-signed'; dest.mkdir()
    with tarfile.open(signed) as stream: stream.extractall(dest, filter='data')
    bundle = dest / 'NootedGreen.kext'; binary = bundle / 'Contents/MacOS/NootedGreen'
    assert (bundle / 'Contents/Info.plist').read_bytes() == (WORK / 'build/product/NootedGreen.kext/Contents/Info.plist').read_bytes()
    macho = c.macho(binary.read_bytes())
    assert macho['uuid'] == build['MachO']['uuid'] and macho['sections'] == build['MachO']['sections']
    c.save(ROOT / 'ga415/reports/BLIT-OBSERVER-SIGNED.json',
           {'status': 'BLIT_OBSERVER_NATIVE_ADHOC_SIGNATURE_VERIFIED_NOT_LOADED',
            'binary': c.record(binary), 'archive': c.record(signed), 'MachO': macho,
            'bundle_inventory': c.inventory(bundle), 'native_receipt': c.record(ROOT / 'ga415/private/commands/blitobs-native-sign.json'),
            'all_MachO_sections_unchanged_by_signing': True, 'installed_or_loaded': False, 'GPU_submitted': False})
    print(json.dumps({'status': 'NATIVE_SIGNED_SECTIONS_VERIFIED', 'UUID': macho['uuid'], 'sha256': c.sha(binary)}))


if __name__ == '__main__':
    main()
