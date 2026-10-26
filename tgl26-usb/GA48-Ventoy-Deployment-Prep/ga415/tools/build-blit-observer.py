#!/usr/bin/env python3
"""Cross-build only the isolated passive-observer NG; no deployment or execution."""
import importlib.util
import json
from pathlib import Path
import plistlib
import tarfile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga415/private/blit-observer'
SPEC = importlib.util.spec_from_file_location('ga414_common', ROOT / 'ga414/tools/common.py')
c = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(c)


def main():
    audit = json.loads((ROOT / 'ga415/reports/BLIT-OBSERVER-SOURCE.json').read_text())
    assert c.inventory(WORK / 'source') == audit['source_inventory']
    assert c.sha(c.RECIPE) == json.loads((ROOT / 'ga410/reports/NG-R6-BUILD.json').read_text())['recipe_sha256']
    out = WORK / 'build'; out.mkdir()
    builder = c.builder(); builder.ROOT, builder.OUT, builder.BUILD = WORK / 'source', out, out / 'product'
    builder.kext('NootedGreen')
    bundle = builder.BUILD / 'NootedGreen.kext'; binary = bundle / 'Contents/MacOS/NootedGreen'
    data = binary.read_bytes(); macho = c.macho(data)
    baseline = ROOT / 'ga414/private/native-signed/NootedGreen.kext'
    assert macho['filetype'] == 0xb and macho['uuid'] != c.macho((baseline / 'Contents/MacOS/NootedGreen').read_bytes())['uuid']
    assert (bundle / 'Contents/Info.plist').read_bytes() == (baseline / 'Contents/Info.plist').read_bytes()
    for value in [b'GA414 NOAUX: postflight', b'HP-R6: real TGL/Tahoe upstream pool', b'XE-NOCCS3:',
                  b'XeNG PLANES2:', b'GA415OBS install:', b'GA415OBS kind=', b'-ngreen415obs',
                  b'COPY2D', b'FAST2D', b'COPY3D']:
        assert value in data, value
    assert c.FIND in data and c.REPLACE in data
    undefined = c.run([builder.LLVM_BIN / 'llvm-nm', '-uj', binary]).splitlines()
    old = c.run([builder.LLVM_BIN / 'llvm-nm', '-uj', baseline / 'Contents/MacOS/NootedGreen']).splitlines()
    assert set(undefined) <= set(old), sorted(set(undefined) - set(old))
    symbols = c.run([builder.LLVM_BIN / 'llvm-nm', binary]); (WORK / 'build-symbols.txt').write_text(symbols)
    for name in ['ga415ObsLog', 'ga415ObsSourceCopy', 'ga415ObsFastCopy', 'ga415Obs3D']:
        assert name in symbols
    assembly = c.run([builder.LLVM_BIN / 'llvm-objdump', '--disassemble', '--x86-asm-syntax=intel', binary])
    (WORK / 'observer-kext.asm').write_text(assembly)
    archive = WORK / 'NootedGreen-GA415-BLITOBS-cross.tar.gz'
    with tarfile.open(archive, 'x:gz') as stream: stream.add(bundle, arcname='NootedGreen.kext')
    c.save(ROOT / 'ga415/reports/BLIT-OBSERVER-BUILD.json',
           {'status': 'BLIT_OBSERVER_BUILT_NATIVE_SIGNING_PENDING', 'binary': c.record(binary), 'MachO': macho,
            'bundle_inventory': c.inventory(bundle), 'archive': c.record(archive), 'source_audit': c.record(ROOT / 'ga415/reports/BLIT-OBSERVER-SOURCE.json'),
            'Info_plist_identical_to_GA414': True, 'new_undefined_symbols': [], 'undefined_symbols': undefined,
            'OSBundleLibraries': plistlib.loads((bundle / 'Contents/Info.plist').read_bytes())['OSBundleLibraries'],
            'route_changes': False, 'native_signed': False, 'runtime_executed': False})
    print(json.dumps({'status': 'BLIT_OBSERVER_BUILT_NATIVE_SIGNING_PENDING', 'UUID': macho['uuid'], 'sha256': c.sha(binary)}))


if __name__ == '__main__':
    main()
