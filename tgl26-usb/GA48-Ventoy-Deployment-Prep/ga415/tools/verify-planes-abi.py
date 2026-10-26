#!/usr/bin/env python3
"""Verify the exact 25G83 IOSurface ABI and existing GA414 PLANES2 patch offline."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga415/private/planesfix'
REPORT = ROOT / 'ga415/reports/PLANES2-ABI.json'
spec = importlib.util.spec_from_file_location('prior_helpers', ROOT / 'ga414/tools/common.py')
common = importlib.util.module_from_spec(spec); spec.loader.exec_module(common)


def sha(data): return hashlib.sha256(data).hexdigest()


def thin(data):
    if data[:4] == bytes.fromhex('cffaedfe'): return data
    assert data[:4] == bytes.fromhex('cafebabe')
    count = struct.unpack_from('>I', data, 4)[0]
    for i in range(count):
        cpu, _, offset, size, _ = struct.unpack_from('>5I', data, 8 + i * 20)
        if cpu == 0x1000007:
            part = data[offset:offset + size]
            assert len(part) == size and part[:4] == bytes.fromhex('cffaedfe')
            return part
    raise ValueError('No x86_64 slice')


def image(data):
    data = thin(data); cursor = 32; segments = []; identity = None
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        cmd, size = struct.unpack_from('<II', data, cursor)
        assert size >= 8 and cursor + size <= len(data)
        if cmd == 0x1b: identity = str(uuid.UUID(bytes=data[cursor + 8:cursor + 24])).upper()
        if cmd == 0x19:
            va, vsize, offset, length = struct.unpack_from('<4Q', data, cursor + 24)
            segments.append((va, offset, length))
        cursor += size
    def get(va, size):
        for start, offset, length in segments:
            if start <= va and va + size <= start + length:
                return data[offset + va - start:offset + va - start + size]
        raise ValueError('VA outside file-backed segment')
    return identity, get


def main():
    kdk = WORK / 'IOSurface-25G83-kdk'; data = kdk.read_bytes()
    assert sha(data) == 'c96e1eb230412a963f4f5953583d3f4aebeb75d1983d8551269f353b901bd377'
    identity, get = image(data)
    assert identity == '8E1FFEDA-8C53-336F-B59B-776024E3B66D'
    receipt = json.loads((ROOT / 'ga415/private/commands/planesfix-iosurface-kdk-identity.json').read_text())
    assert receipt['returncode'] == 0
    observed = json.loads(receipt['stdout'])
    assert identity in observed['loaded']['stdout'] and observed['sha256'] == sha(data)
    b = common.builder()
    nm = subprocess.check_output([str(b.LLVM_BIN / 'llvm-nm'), '-n', '--arch=x86_64', str(kdk)], text=True)
    symbol = '__ZNK9IOSurface13getPlaneCountEv'
    address = next(int(line.split()[0], 16) for line in nm.splitlines() if line.endswith(' ' + symbol))
    body = get(address, 12)
    assert body == bytes.fromhex('554889e58b87980000005dc3'), body.hex()
    donor = ROOT / 'ga414/private/AppleIntelTGLGraphics-25G83'; donor_data = donor.read_bytes()
    assert sha(donor_data) == '14e21de55f2923c3c46a33731ab2f7a71e1baf472f88d1fd8c702e821c171393'
    donor_uuid, donor_at = image(donor_data)
    assert donor_uuid == 'BA3AA1C0-FE6B-33B3-9D85-73F848394E3D'
    find = bytes.fromhex('8b83b000000085c0ba01000000')
    replacement = bytes.fromhex('8b839800000085c0ba01000000')
    assert donor_data.count(find) == 1 and donor_data.count(replacement) == 0
    assert donor_at(0x7287d, len(find)) == find
    assert donor_at(0x72bcd, 3) == bytes.fromhex('41f7f7')
    assert [i for i, (a, b) in enumerate(zip(find, replacement)) if a != b] == [2]
    ng = ROOT / 'ga414/private/native-signed/NootedGreen.kext/Contents/MacOS/NootedGreen'
    assert find in ng.read_bytes() and replacement in ng.read_bytes()
    signed = json.loads((ROOT / 'ga414/reports/NATIVE-SIGNATURE.json').read_text())
    assert common.sha(ng) == signed['binary']['sha256']
    source = ROOT / 'ga414/private/source/src/NootedGreen/kern_gen11.cpp'
    source_text = source.read_text()
    assert 'if (!checkKernelArgument("-ngreennoplanesfix"))' in source_text
    assert 'checkKernelArgument("-ngreenplanesxor") ? r_planes_xor : r_planes_98' in source_text
    assert 'if (!NGreen::callback->isRealTGL || checkKernelArgument("-ngreentgltahoe"))' in source_text
    assert 'LookupPatchPlus const patchPlanes[] = {{activeKext, f_planes, r_planes, arrsize(f_planes), 1}}' in source_text
    assert common.sha(source) == json.loads((ROOT / 'ga414/reports/SOURCE-AND-DONOR.json').read_text())['source_sha256']['src/NootedGreen/kern_gen11.cpp']
    report = dict(status='EXACT_25G83_PLANES2_ABI_VERIFIED_RUNTIME_PENDING',
                  IOSurface_KDK=common.record(kdk), IOSurface_UUID=identity, UUID_matches_running_and_panic=True,
                  getPlaneCount_symbol=symbol, getPlaneCount_VA=hex(address), getPlaneCount_hex=body.hex(),
                  verified_plane_count_offset='0x98', donor=common.record(donor), donor_UUID=donor_uuid,
                  donor_plane_count_read_VA='0x7287d', donor_wrong_offset='0xb0',
                  donor_find_hex=find.hex(), existing_replacement_hex=replacement.hex(),
                  original_count=1, replacement_count_before=0, changed_instruction_bytes=[2],
                  fault_VA='0x72bcd', fault_instruction='div r15d', fault_divisor_from_panic=0,
                  preserved_GA414_NG=common.record(ng), NG_UUID=signed['MachO']['uuid'],
                  preserved_source=common.record(source), patch_application_count=1,
                  required_native_arg='-ngreentgltahoe', remove_only_arg='-ngreennoplanesfix',
                  planesxor_enabled=False, all_planes_forced_to_zero=False,
                  normalization_examples=[dict(actual_plane_count=n, resource_table_planes=n or 1) for n in (0, 1, 2, 3)],
                  GPU_submitted=False, kernel_memory_read=False, runtime_patch_confirmed=False,
                  limitation='Exact accessor ABI and original patch bytes verified. Actual failing IOSurface metadata was not dumped; physical boot and resource-path validation remain required.')
    with REPORT.open('x') as f: json.dump(report, f, indent=2); f.write('\n')
    print(json.dumps({k: report[k] for k in ('status', 'IOSurface_UUID', 'verified_plane_count_offset', 'remove_only_arg', 'NG_UUID')}))


if __name__ == '__main__': main()
