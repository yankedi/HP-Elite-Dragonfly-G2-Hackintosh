#!/usr/bin/env python3
"""Rebuild only NootedGreen using the verified R6 cross-build recipe."""
import json
import plistlib
import tarfile
from common import *


def main():
    audit = json.loads((REPORTS / 'SOURCE-AND-DONOR.json').read_text())
    require(inventory(WORK / 'source') == audit['source_sha256'], 'audited source changed')
    prior = json.loads((ROOT / 'ga410/reports/NG-R6-BUILD.json').read_text())
    require(sha(RECIPE) == prior['recipe_sha256'], 'R6 build recipe changed')
    out = WORK / 'build'; out.mkdir()
    b = builder(); b.ROOT, b.OUT, b.BUILD = WORK / 'source', out, out / 'product'
    b.kext('NootedGreen')
    bundle = b.BUILD / 'NootedGreen.kext'; binary = bundle / 'Contents/MacOS/NootedGreen'
    data = binary.read_bytes(); image = macho(data)
    require(image['filetype'] == 0xb, 'not MH_KEXT_BUNDLE')
    require(image['uuid'] != json.loads((ROOT / 'ga410/reports/TGL-R6.json').read_text())['new_NG_uuid'], 'UUID did not change')
    for text in [b'GA414 NOAUX: postflight', b'XeNG NOAUX: fillSurfaceStateAuxInfo sempre AUX_NONE:',
                 b'HP-R6: real TGL/Tahoe upstream pool', b'HP-R5: native TGL topology', b'HP-R3: Blit3D scratch allocation', b'XE-NOCCS3:']:
        require(text in data, 'required feature/log string missing: ' + repr(text))
    require(FIND in data and REPLACE in data, 'NOAUX arrays missing from binary')
    info = plistlib.loads((bundle / 'Contents/Info.plist').read_bytes())
    old_info = plistlib.loads((R6 / 'native-signed/NootedGreen.kext/Contents/Info.plist').read_bytes())
    require(info == old_info, 'NG metadata or KC dependencies changed')
    symbols = run([b.LLVM_BIN / 'llvm-nm', binary])
    undefined = run([b.LLVM_BIN / 'llvm-nm', '-uj', binary]).splitlines()
    old_undefined = run([b.LLVM_BIN / 'llvm-nm', '-uj', R6 / 'native-signed/NootedGreen.kext/Contents/MacOS/NootedGreen']).splitlines()
    require(set(undefined) <= set(old_undefined), 'new unresolved import/dependency introduced')
    for symbol in ['_NootedGreen_kern_start', '_NootedGreen_kern_stop', '_kmod_info']:
        require(symbol in symbols, 'required symbol absent: ' + symbol)
    (WORK / 'build-symbols.txt').write_text(symbols)
    archive = WORK / 'NootedGreen-GA414-cross.tar.gz'
    with tarfile.open(archive, 'x:gz') as stream: stream.add(bundle, arcname='NootedGreen.kext')
    report = {'status': 'KEXT_BUILT_NATIVE_SIGNING_PENDING', 'binary': record(binary), 'MachO': image,
              'bundle_inventory': inventory(bundle), 'Info_plist_identical_to_R6': True,
              'OSBundleLibraries': info['OSBundleLibraries'], 'undefined_symbols': undefined,
              'new_undefined_symbols_vs_R6': sorted(set(undefined) - set(old_undefined)),
              'recipe': record(RECIPE), 'source_audit': record(REPORTS / 'SOURCE-AND-DONOR.json'),
              'archive': record(archive), 'symbol_dump': record(WORK / 'build-symbols.txt'),
              'native_signature_verified': False, 'runtime_applied': False}
    save(REPORTS / 'BUILD.json', report)
    print(json.dumps({'status': report['status'], 'UUID': image['uuid'], 'binary_sha256': sha(binary)}))


if __name__ == '__main__':
    main()
