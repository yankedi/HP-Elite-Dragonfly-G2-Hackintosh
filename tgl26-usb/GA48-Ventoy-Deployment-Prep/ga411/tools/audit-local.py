#!/usr/bin/env python3
"""Read-only source/artifact audit; write only GA4.11 derived local evidence."""
import bisect
import hashlib
import json
from pathlib import Path
import plistlib
import re
import struct
import subprocess

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / 'ga411'
OLD = REPO / 'ga410'
GA47 = REPO.parent / 'GA47-JulioNectar-HP-Port'
BASE = '6a1afb337d1fb1ff07ca032b5c1868fe2bd005ef'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.run(['git', *args], cwd=GA47, check=True, capture_output=True).stdout


def file_record(path):
    data = path.read_bytes()
    return {'path': str(path), 'sha256': sha(data), 'bytes': len(data)}


def segments(data):
    assert struct.unpack_from('<I', data)[0] == 0xfeedfacf
    result, off = [], 32
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        cmd, size = struct.unpack_from('<II', data, off)
        if cmd == 0x19:
            name, va, vs, fo, fs = struct.unpack_from('<16sQQQQ', data, off + 8)
            result.append((name.rstrip(b'\0').decode(), va, fo, fs))
        off += size
    return result


def disassemble(path, start, end):
    # The selected FB has identity VA/file offsets in these __TEXT ranges.
    data = path.read_bytes()
    for address in (start, end - 1):
        seg = next(s for s in segments(data) if s[1] <= address < s[1] + s[3])
        assert seg[1] == seg[2]
    return subprocess.run([
        'objdump', '-D', '-b', 'binary', '-m', 'i386:x86-64',
        f'--start-address={start}', f'--stop-address={end}', str(path),
    ], check=True, capture_output=True, text=True).stdout


def main():
    assert not git('status', '--porcelain'), 'GA47 baseline is not clean'
    assert git('rev-parse', 'UPSTREAM_BASE').decode().strip() == BASE
    rel = 'src/NootedGreen/kern_gen11.cpp'
    upstream = git('show', BASE + ':' + rel)
    current_path = OLD / 'private/ng-r6/source' / rel
    current = current_path.read_bytes()
    green = OLD / 'private/ng-r6/source/src/NootedGreen/kern_green.cpp'
    build = json.loads((OLD / 'reports/NG-R6-BUILD.json').read_text())
    assert sha(current) == build['prior_topology_source_sha256']
    assert sha(green.read_bytes()) == build['source_after_sha256']
    lib = GA47 / 'macos/src/libxedrv.m'
    assert lib.read_bytes() == git('show', BASE + ':macos/src/libxedrv.m')
    source = current.decode()
    donor = OLD / 'private/r2-postboot-capture/AppleIntelTGLGraphics'
    binary = donor.read_bytes()
    asm_path = OLD / 'private/r4-code-evidence/tgl-accelerator.asm'
    symbol_starts, symbol_names, pending = [], [], None
    for line in asm_path.read_text().splitlines():
        if line.endswith(':') and not line[0].isdigit():
            pending = line[:-1]
        elif pending and re.match(r'^[0-9a-f]{16}\s', line):
            addr = int(line[:16], 16)
            if not symbol_starts or addr > symbol_starts[-1]:
                symbol_starts.append(addr)
                symbol_names.append(pending)
            pending = None
    patterns = {}
    for name in ['f_noccs3', 'f_nodepth', 'f_noaux', 'f_rcstart', 'f_rcset',
                 'f_fmt', 'f_planes', 'f_ba_src', 'f_ba_dst', 'f_ba_rota']:
        match = re.search(r'static const uint8_t ' + name + r'\[\]\s*=\s*\{([^}]+)\}', source)
        assert match, name
        pattern = bytes(int(x, 16) for x in re.findall(r'0x([0-9a-fA-F]+)', match[1]))
        assert pattern and binary.count(pattern) == 1, name
        off = binary.index(pattern)
        seg = next(s for s in segments(binary) if s[2] <= off < s[2] + s[3])
        va = seg[1] + off - seg[2]
        ix = bisect.bisect_right(symbol_starts, va) - 1
        patterns[name] = {
            'source_line': source[:match.start()].count('\n') + 1,
            'find_hex': pattern.hex(), 'matches_in_original_donor': 1,
            'file_offset': hex(off), 'virtual_address': hex(va),
            'enclosing_symbol': symbol_names[ix],
            'offset_in_symbol': hex(va - symbol_starts[ix]),
            'meaning': 'Exact target applicability only; not proof of runtime patch or pixel correctness',
        }
    initial = OLD / 'private/r6-live/GA410-R6-live-initial'
    dmesg = (initial / 'dmesg.txt').read_text(errors='replace')
    session = (initial / 'session.txt').read_text()
    assert 'REDACTED-SESSION-ID' in session
    assert '-ngreenxefix' not in session
    logs = {}
    for key in ['XE-FMT:', 'XE-NOCCS3:', 'XE-NOCCS:', 'RCPOLICY:', 'NOAUX:',
                'XE-NODEPTH:', 'PLANES2:', 'BLITALIGN:', 'PAGESYNC',
                'skipping MultiForceWakeSelect', 'rc1474=']:
        logs[key] = [l for l in dmesg.splitlines() if key in l]
    xedrv = (initial / 'xedrv-WindowServer.log').read_text()
    xedrv_lines = [l for l in xedrv.splitlines() if any(k in l for k in [
        'sem compressão:', 'nocopyfix:', 'fillfix:', 'NOCOPY ', 'FILL ', 'COPIA '])]
    fb = OLD / 'private/r6-live/firstboot/20200101T000904Z-49C2714E-5FB9-49BC-932A-4DCAB42A4771'
    pci = (fb / 'ioreg-pci.stdout').read_text()
    assert '"YTiling"=1' in pci
    probe_receipt_path = OLD / 'private/commands/r4-render-probe-managed-target-cpu-read.json'
    probe = json.loads(probe_receipt_path.read_text())
    assert probe['returncode'] == 1 and '16705/16705' in probe['stdout']
    tracer_path = OLD / 'private/commands/r4-evidence-writable-target-resource-flags.json'
    tracer = json.loads(tracer_path.read_text())
    assert tracer['returncode'] == 1 and 'resolveCCS_result=1 wait=1' in tracer['stderr']
    controls = {}
    control_files = []
    for name in ['r4-render-probe-odd-size-upload-sample', 'r4-render-probe-iosurface-cpu-source',
                 'r4-render-probe-managed-source', 'r4-evidence-managed-target-cpu-call-chain']:
        path = OLD / 'private/commands' / (name + '.json')
        receipt = json.loads(path.read_text())
        expected_rc = 1 if 'cpu-call-chain' in name else 0
        assert receipt['returncode'] == expected_rc
        assert ('16705/16705' if expected_rc else 'bad_pixels=0/16705') in receipt['stdout']
        controls[name] = {'returncode': receipt['returncode'], 'stdout': receipt['stdout'],
                          'stderr': receipt['stderr']}
        control_files.append(path)
    plist = GA47 / 'build/ga47/package/payload/Library/Extensions/AppleIntelTGLGraphics.kext/Contents/Info.plist'
    development = plistlib.loads(plist.read_bytes())['IOKitPersonalities']['Gen7']['Development']
    fb_binary = GA47 / 'build/ga47/package/payload/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext/Contents/MacOS/AppleIntelTGLGraphicsFramebuffer'
    fb_bytes = fb_binary.read_bytes()
    assert fb_bytes[0x1046da:0x1046ec] == b'renderCompression\0'
    fb_evidence = {
        'renderCompression_symbol_initialization': disassemble(fb_binary, 0x3d70a, 0x3d71d),
        'setDisplayMode_policy_call': disassemble(fb_binary, 0x47db0, 0x47e2d),
        'caveat': 'Static caller + setter support a possible framebuffer rewrite, not proof that this call executed or what +0x1474 held in R6.',
    }
    mtl_path = OLD / 'private/r4-code-evidence/AppleIntelTGLGraphicsMTLDriver'
    mtl_bytes = mtl_path.read_bytes()
    mtl15 = bytes.fromhex('31c990')
    assert mtl_bytes[0x18c28:0x18c2b] == mtl15
    docs = {}
    for name in ['docs/EXPERIMENTS.md', 'docs/CATALOG.md', 'docs/HISTORY.md']:
        data = git('show', BASE + ':' + name)
        lines = data.decode().splitlines()
        docs[name] = {'sha256': sha(data), 'selected_lines': [
            {'line': i + 1, 'text': line} for i, line in enumerate(lines)
            if any(s in line for s in ['RenderCompressionMode` only', 'does **not** disable',
                                      'Result: no effect — the TGL', 'Compression was not the cause',
                                      '**not** the cause', 'MTL15', 'XE-RCPOLICY'])
        ]}
    live_property_path = OLD / 'private/commands/ga411-readonly-accelerator-late-properties.json'
    live_property = json.loads(live_property_path.read_text())
    assert live_property['returncode'] == 0
    live_lines = live_property['stdout'].splitlines()
    live_development = next(line for line in live_lines if '"Development" =' in line)
    assert '"AllowIOSurfaceRenderCompression"=1' in live_development
    assert 'RenderCompressionMode' not in live_property['stdout']
    records = [current_path, green, lib, donor, asm_path, OLD / 'tools/render-probe.m',
               OLD / 'tools/trace-texture-cpu.m', initial / 'dmesg.txt', initial / 'session.txt',
               initial / 'xedrv-WindowServer.log', fb / 'ioreg-pci.stdout', fb / 'ioreg-accelerator.stdout',
               probe_receipt_path, tracer_path, OLD / 'reports/GA410-CONSOLIDATED-REPORT.md',
               plist, fb_binary, mtl_path, OLD / 'private/r4-code-evidence/mtl-driver.asm',
               OLD / 'reports/R5-RUNTIME.json', OLD / 'reports/R6-RUNTIME.json',
               live_property_path, *control_files]
    result = {
        'status': 'LOCAL_SOURCE_AND_EXISTING_EVIDENCE_AUDIT_NOT_RUNTIME_FIX',
        'upstream_commit': BASE, 'upstream_gen11_sha256': sha(upstream),
        'GA47_commit': git('rev-parse', 'HEAD').decode().strip(), 'GA47_clean': True,
        'R6_gen11_sha256': sha(current), 'R6_green_sha256': sha(green.read_bytes()),
        'R7_untouched': True, 'driver_source_patch_or_new_image_created': False,
        'native_TGL_R6_session': '49C2714E-5FB9-49BC-932A-4DCAB42A4771',
        'original_donor_pattern_matches': patterns, 'R6_kernel_log_matches': logs,
        'R6_WindowServer_libxedrv_evidence': xedrv_lines,
        'R6_YTiling_property': 1,
        'R6_captured_accelerator_ioreg_bytes': (fb / 'ioreg-accelerator.stdout').stat().st_size,
        'packaged_Development_AllowIOSurfaceRenderCompression': development.get('AllowIOSurfaceRenderCompression'),
        'packaged_Development_RenderCompressionMode': development.get('RenderCompressionMode'),
        'properties_caveat': 'Packaged defaults and code gates are not a runtime config/+0x1474 memory read.',
        'GA411_live_registry_property_observation': {
            'receipt': str(live_property_path), 'time_utc': live_property['time_utc'],
            'accelerator': live_lines[0], 'Development_AllowIOSurfaceRenderCompression': 1,
            'RenderCompressionMode_visible': False,
            'Development_raw_line': live_development,
            'caveat': 'Live registry proves the NOCCS zero property policy is absent; still no accel+0x1190/+0x1474 memory trace.',
        },
        'framebuffer_static_chain': fb_evidence,
        'captured_MTL15_present': {'file_offset': '0x18c28', 'bytes': mtl15.hex(),
                                 'effect': 'm_Info+0x160 receives zero instead of resource+0x18 in IOSurface initializer'},
        'fixed_upstream_documentation': docs,
        'R4_managed_target_receipt': {'returncode': probe['returncode'], 'stdout': probe['stdout']},
        'R4_tracer_receipt': {'returncode': tracer['returncode'], 'stdout': tracer['stdout'], 'stderr': tracer['stderr']},
        'R4_historical_pixel_controls': controls,
        'historical_probe_gap': 'managed==2 overwrites out.contents with CPU getBytes before known-pixel validation; GPU and CPU each need separate expected-byte validation.',
        'files': [file_record(p) for p in records],
    }
    path = ROOT / 'reports/LOCAL-EVIDENCE.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(path)
    print('Exact original-donor matches:', len(patterns))
    for name, p in patterns.items():
        print(name, p['virtual_address'], p['enclosing_symbol'], p['offset_in_symbol'])


if __name__ == '__main__':
    main()
