#!/usr/bin/env python3
"""Copy sealed GA414 source and add an opt-in, bounded passive Blit observer."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga415/private/blit-observer'
SPEC = importlib.util.spec_from_file_location('ga414_common', ROOT / 'ga414/tools/common.py')
c = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(c)


def main():
    original = ROOT / 'ga414/private/source'
    audited = json.loads((ROOT / 'ga414/reports/SOURCE-AND-DONOR.json').read_text())['source_sha256']
    assert c.inventory(original) == audited
    donor = ROOT / 'ga414/private/AppleIntelTGLGraphics-25G83'
    assert c.sha(donor) == '14e21de55f2923c3c46a33731ab2f7a71e1baf472f88d1fd8c702e821c171393'
    data = donor.read_bytes()
    src = bytes.fromhex('8b470889c1c1e90284d20f44c8')
    dst = bytes.fromhex('8b475089c1c1e9024584c00f44c8')
    route = bytes.fromhex('410fb68ea00000004883f9100f94c0480fafd14881fa01100500')
    assert all(data.count(pattern) == 1 for pattern in (src, dst, route))
    builder = c.builder()
    symbols = subprocess.check_output([str(builder.LLVM_BIN / 'llvm-nm'), '-n', str(donor)], text=True)
    wanted = {
        '__Z17blt2d_source_copyP23IGHardwareBlit2DContextP15blit3d_params_tRK8IGVectorI11rect_pair_t25IGIOMallocAllocatorPolicyEP9_WA_TABLE': 0x30430,
        '__Z15blt2d_fast_copyP23IGHardwareBlit2DContextP15blit3d_params_tRK8IGVectorI11rect_pair_t25IGIOMallocAllocatorPolicyEP9_WA_TABLE': 0x30970,
        '__Z22blit3d_submit_commandsP23IGHardwareBlit3DContextP15blit3d_params_tRK8IGVectorI11rect_pair_t25IGIOMallocAllocatorPolicyE': 0x325b6,
    }
    for symbol, address in wanted.items():
        assert any(line.split() == [f'{address:016x}', 'T', symbol] for line in symbols.splitlines())
    WORK.mkdir(mode=0o700)
    source = WORK / 'source'; shutil.copytree(original, source)
    target = source / 'src/NootedGreen/kern_gen11.cpp'; text = target.read_text()
    marker = '// ==== 6 kextInfos:'
    assert text.count(marker) == 1
    text = text.replace(marker, '#include "ga415_blit_observer.hpp"\n\n' + marker, 1)
    marker = '\tconst uint32_t xeRs = param_1 ? ((reinterpret_cast<uint8_t *>(param_1)[0xA2] >> 3U) & 0x3U) : 9;'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '\n\tga415ObsLog("SUBMIT", param_1, param_2);', 1)
    block = '''
			// GA415: passive observation on exact HP/25G83 only. No other XE features enabled.
			if (hpNoAux && checkKernelArgument("-ngreen415obs")) {
				static const uint8_t srcPitchABI[] = {SRC};
				static const uint8_t dstPitchABI[] = {DST};
				static const uint8_t routeABI[] = {ROUTE};
				const auto *image = reinterpret_cast<const uint8_t *>(address);
				const bool abi = hpGa414PatternCount(image, size, srcPitchABI, sizeof(srcPitchABI)) == 1 &&
					hpGa414PatternCount(image, size, dstPitchABI, sizeof(dstPitchABI)) == 1 &&
					hpGa414PatternCount(image, size, routeABI, sizeof(routeABI)) == 1;
				bool installed = false;
				if (abi) {
					RouteRequestPlus observer[] = {
						{"SOURCE", ga415ObsSourceCopy, gGa415OrgSourceCopy},
						{"FAST", ga415ObsFastCopy, gGa415OrgFastCopy},
						{"THREE", ga415Obs3D, gGa415Org3D},
					};
					installed = RouteRequestPlus::routeAll(patcher, index, observer, address, size);
					if (!installed) patcher.clearError();
				}
				gGa415ObsEnabled = abi && installed;
				IOLog("GA415OBS install: gate=1 abi=%u hooks=%u enabled=%u budgets=16/16/96 route_changes=0\\n",
					abi, installed, gGa415ObsEnabled);
			}
'''
    for name, val in [('SRC', src), ('DST', dst), ('ROUTE', route)]:
        block = block.replace(name, ','.join(f'0x{v:02x}' for v in val))
    for name, val in zip(['SOURCE', 'FAST', 'THREE'], wanted): block = block.replace(name, val)
    marker = '\n\t\t\tif (!NGreen::callback->isRealTGL) {\n\t\t\t\t// RPL-only: hardcode topology and bypass BCS readiness check'
    assert text.count(marker) == 1
    text = text.replace(marker, block + marker, 1); target.write_text(text)
    shutil.copyfile(ROOT / 'ga415/kernel/ga415_blit_observer.hpp', target.with_name('ga415_blit_observer.hpp'))
    actual = c.inventory(source)
    changed = [name for name in audited if actual[name] != audited[name]]
    added = sorted(actual.keys() - audited.keys())
    assert changed == ['src/NootedGreen/kern_gen11.cpp'] and added == ['src/NootedGreen/ga415_blit_observer.hpp']
    diff = subprocess.run(['diff', '-u', str(original / changed[0]), str(source / changed[0])], capture_output=True, text=True)
    assert diff.returncode == 1
    (WORK / 'source.patch').write_text(diff.stdout)
    assert c.inventory(original) == audited
    report = {'status': 'BLIT_OBSERVER_SOURCE_PREPARED_BUILD_PENDING', 'source_inventory': actual,
              'changed_files': changed, 'added_files': added, 'donor': c.record(donor),
              'symbols_VA': {name: hex(va) for name, va in wanted.items()},
              'verified_fields': {'source_pitch': '0x08', 'destination_pitch': '0x50', 'source_tiling': '0x0c',
                                  'destination_tiling': '0x54', 'source_offset': '0x2c', 'destination_offset': '0x74',
                                  'bytes_per_element': '0xa0', 'entry_route_selector': 'bits3:4 at 0xa2',
                                  'rect_count': 'vector+0x00', 'rect_data': 'vector+0x10', 'rect_stride': '0x20'},
              'max_added_log_lines': 128, 'opt_in_boot_arg': '-ngreen415obs',
              'route_changes': False, 'replaced_existing_guard_logic': False, 'kernel_or_GPU_executed': False,
              'note': 'Final COPY2D/FAST2D/COPY3D calls observed, not guessed from routeSel. First rect float bits only; no kernel FP or unbounded list dump.'}
    c.save(ROOT / 'ga415/reports/BLIT-OBSERVER-SOURCE.json', report)
    print(json.dumps({k: report[k] for k in ['status', 'changed_files', 'added_files', 'max_added_log_lines']}))


if __name__ == '__main__':
    main()
