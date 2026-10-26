#!/usr/bin/env python3
"""Native ad-hoc signing of the isolated artifact only; never install/load it."""
import json
import plistlib
import sys
import tarfile
from common import *

sys.path.insert(0, str(ROOT / 'ga410/tools'))
import normal_ssh
import remote

BASE = '/private/tmp/ga414-noaux'


def main():
    normal_ssh.configure(); remote.ROOT = ROOT / 'ga414'
    build = json.loads((REPORTS / 'BUILD.json').read_text())
    archive = ROOT / build['archive']['path']
    require(sha(archive) == build['archive']['sha256'], 'cross archive changed')
    remote.run('native-sign-work', f'set -eu\numask 077\nmkdir {BASE}\nmkdir {BASE}/signed', timeout=15)
    remote.upload(archive, BASE + '/cross.tar.gz', timeout=30)
    row = remote.run('native-adhoc-sign-strict', f'''set -eu
test "$(/usr/bin/shasum -a 256 {BASE}/cross.tar.gz | /usr/bin/awk '{{print $1}}')" = {sha(archive)}
/usr/bin/tar -xpf {BASE}/cross.tar.gz -C {BASE}/signed
/usr/bin/codesign --force --sign - --timestamp=none {BASE}/signed/NootedGreen.kext
/usr/bin/codesign --verify --strict --deep --verbose=4 {BASE}/signed/NootedGreen.kext
/usr/bin/codesign --display --verbose=4 {BASE}/signed/NootedGreen.kext
/usr/bin/dwarfdump --uuid {BASE}/signed/NootedGreen.kext/Contents/MacOS/NootedGreen
/usr/bin/file {BASE}/signed/NootedGreen.kext/Contents/MacOS/NootedGreen
/usr/bin/tar -czpf {BASE}/signed.tar.gz -C {BASE}/signed NootedGreen.kext
/usr/bin/shasum -a 256 {BASE}/signed.tar.gz
''', timeout=45)
    require('Signature=adhoc' in row['stdout'] + row['stderr'], 'not native ad-hoc')
    signed_archive = WORK / 'NootedGreen-GA414-native-signed.tar.gz'
    remote.download(BASE + '/signed.tar.gz', signed_archive, timeout=30)
    require(sha(signed_archive) in row['stdout'], 'native signed archive transfer mismatch')
    signed_root = WORK / 'native-signed'; signed_root.mkdir()
    with tarfile.open(signed_archive) as stream:
        for member in stream.getmembers():
            p = Path(member.name)
            require(not p.is_absolute() and '..' not in p.parts and not member.issym() and not member.islnk(), 'unsafe signed archive member')
            if member.isfile() and not any(part.startswith('._') for part in p.parts):
                path = signed_root / p; path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as out: out.write(stream.extractfile(member).read())
    bundle = signed_root / 'NootedGreen.kext'; binary = bundle / 'Contents/MacOS/NootedGreen'
    require(macho(binary.read_bytes()) == build['MachO'], 'native signing changed functional sections or UUID')
    cross_info = WORK / 'build/product/NootedGreen.kext/Contents/Info.plist'
    require((bundle / 'Contents/Info.plist').read_bytes() == cross_info.read_bytes(), 'native signing changed metadata/dependencies')
    save(REPORTS / 'NATIVE-SIGNATURE.json', {'status': 'NATIVE_ADHOC_STRICT_DEEP_PASS_NOT_RUNTIME',
         'native_codesign_verify_rc': row['returncode'], 'signature_type': 'adhoc', 'strict_deep': True,
         'receipt': record(WORK / 'commands/native-adhoc-sign-strict.json'),
         'executable_sections_and_UUID_unchanged_by_signing': True, 'MachO': build['MachO'],
         'bundle_inventory': inventory(bundle), 'archive': record(signed_archive), 'binary': record(binary),
         'OSBundleLibraries': plistlib.loads(cross_info.read_bytes())['OSBundleLibraries'],
         'installed': False, 'loaded': False})
    print('Native signature and functional section/UUID preservation verified:', build['MachO']['uuid'])


if __name__ == '__main__':
    main()
