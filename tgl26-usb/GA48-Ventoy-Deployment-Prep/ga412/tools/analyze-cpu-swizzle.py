#!/usr/bin/env python3
"""Offline binary/trace/layout audit; no SSH, no Metal, no GPU submission."""
import argparse
import collections
import ctypes
import hashlib
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
W, H, ROW = 257, 65, 1280


def require(condition, message):
    if not condition:
        raise ValueError(message)


class MachO:
    def __init__(self, path):
        self.path = path
        self.data = path.read_bytes()
        require(struct.unpack_from('<I', self.data)[0] == 0xfeedfacf, 'thin little-endian Mach-O64 required')
        self.segments = []
        offset = 32
        for _ in range(struct.unpack_from('<I', self.data, 16)[0]):
            command, size = struct.unpack_from('<II', self.data, offset)
            require(size >= 8 and offset + size <= len(self.data), 'truncated load command')
            if command == 0x19:
                _, va, _, file_offset, file_size = struct.unpack_from('<16sQQQQ', self.data, offset + 8)
                self.segments.append((va, file_offset, file_size))
            offset += size

    def at(self, address, size):
        for va, start, length in self.segments:
            if va <= address and address + size <= va + length:
                result = self.data[start + address - va:start + address - va + size]
                require(len(result) == size, 'truncated segment')
                return result
        raise ValueError(f'VA {address:#x}+{size} is not file backed')


def deposit(value, mask):
    result = 0
    while mask:
        bit = mask & -mask
        if value & 1:
            result |= bit
        value >>= 1
        mask -= bit
    return result


def swizzle(masks, pitch, x, y):
    mx, my, mz = masks
    require(mz == 0 and (mx & my) == 0 and (mx | my) < 65536, 'only disjoint 2D masks supported')
    xb, yb = mx.bit_count(), my.bit_count()
    require(pitch % (1 << xb) == 0, 'pitch must be a multiple of tile width')
    tile = ((y >> yb) * (pitch >> xb) + (x >> xb)) << (xb + yb)
    return tile + deposit(x & ((1 << xb) - 1), mx) + deposit(y & ((1 << yb) - 1), my)


def file_record(path):
    data = path.read_bytes()
    resolved = path.resolve()
    return {'path': str(resolved.relative_to(ROOT)) if resolved.is_relative_to(ROOT) else str(resolved),
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path, default=ROOT / 'ga412/private/followup-readonly/GPUBundles-MTLDriver')
    parser.add_argument('--intel-source', type=Path, default=ROOT / 'ga412/private/upstream-issues-v1/CpuSwizzleBlt.c')
    parser.add_argument('--capture', type=Path, default=ROOT / 'ga412/private/r8-legacy-capture')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists() and not args.report.exists(), 'preserve earlier analysis output')
    args.output.mkdir(parents=True)
    image = MachO(args.driver)
    donor = ROOT / 'ga410/private/r4-code-evidence/AppleIntelTGLGraphicsMTLDriver'
    require(image.data == donor.read_bytes(), 'installed image differs from the image behind archived disassembly')
    # Resolve the actual RIP-relative load and selected pointer, not an assumed enum mapping.
    instruction = image.at(0x19f8f, 7)
    require(instruction[:3] == bytes.fromhex('488d15'), 'getBytes table LEA changed')
    table = 0x19f96 + struct.unpack_from('<i', instruction, 3)[0]
    capture = json.loads((args.capture / 'result.json').read_text())
    trace = [json.loads(line.split(' ', 1)[1]) for line in (args.capture / 'probe.stderr').read_text().splitlines()
             if line.startswith('CPU_TRACE_JSON ')]
    target = [e for e in trace if e['resource']['texture'] == capture['target']['object']]
    raw = target[0]['resource']['raw_m_Info_offsets_not_compression_verdict']
    require(all(e['resource']['raw_m_Info_offsets_not_compression_verdict'] == raw for e in target), 'target metadata changed')
    require(raw['0x1ac'] & 4, 'swizzle branch was not selected')
    enum = raw['0x134']
    require(1 <= enum <= 11, 'table index out of range')
    descriptor = struct.unpack('<Q', image.at(table + (enum - 1) * 8, 8))[0]
    masks = struct.unpack('<III', image.at(descriptor, 12))
    pitch = raw['0x108']
    # Decode source swizzle labels from the independently archived public source.
    import re
    definitions = {}
    for name, pattern in re.findall(r'SWIZZLE\(\(\s*(INTEL_\w+)\s+([oXYZS ]+)\)\)', args.intel_source.read_text()):
        bits = pattern.split()
        if len(bits) != 16 or 'S' in bits or 'Z' in bits:
            continue
        definitions[name] = tuple(sum(1 << (15 - i) for i, letter in enumerate(bits) if letter == axis) for axis in ('X', 'Y', 'Z'))
    names = [name for name, value in definitions.items() if value == masks]
    require(names == ['INTEL_TILE_Y'], 'selected descriptor did not match Intel Tile Y')
    library = args.output / 'intel-swizzle-reference.so'
    command = ['cc', '-O2', '-shared', '-fPIC', '-msse4.1',
               '-DGA412_INTEL_SWIZZLE_SOURCE="' + str(args.intel_source.resolve()) + '"',
               str(ROOT / 'ga412/tools/swizzle-reference.c'), '-o', str(library)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    (args.output / 'build.json').write_text(json.dumps({'command': command, 'returncode': completed.returncode,
                                                     'stdout': completed.stdout, 'stderr': completed.stderr}, indent=2) + '\n')
    require(completed.returncode == 0, 'native Intel reference compilation failed; inspect build.json')
    reference = ctypes.CDLL(str(library.resolve()))
    reference.ga412_reference_offset.argtypes = [ctypes.POINTER(ctypes.c_uint32)] + [ctypes.c_int] * 3
    reference.ga412_reference_offset.restype = ctypes.c_int
    reference.ga412_reference_read.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_int,
                                              ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    reference.ga412_reference_read.restype = None
    tests = []
    for name in ['INTEL_TILE_Y', 'INTEL_TILE_X', 'INTEL_TILE_YF_32', 'INTEL_TILE_YS_32']:
        values = definitions[name]
        cmasks = (ctypes.c_uint32 * 3)(*values)
        addresses = [swizzle(values, pitch, x, y) for y in range(H) for x in range(W * 4)]
        c_addresses = [reference.ga412_reference_offset(cmasks, pitch, x, y) for y in range(H) for x in range(W * 4)]
        require(addresses == c_addresses and len(set(addresses)) == W * H * 4, name + ': offset reference mismatch/alias')
        # Fully defined synthetic allocation, not a replacement for real backing evidence.
        tiled = ctypes.create_string_buffer(max(addresses) + 4096)
        linear = ctypes.create_string_buffer(ROW * H)
        for i, at in enumerate(addresses):
            tiled[at] = bytes(((i * 17 + (i // 1028) * 7) % 256,))
        reference.ga412_reference_read(cmasks, pitch, tiled, linear, ROW, W * 4, H)
        require(all(linear[y * ROW + x][0] == ((y * W * 4 + x) * 17 + y * 7) % 256
                    for y in range(H) for x in range(W * 4)), name + ': CpuSwizzleBlt synthetic read mismatch')
        tests.append({'descriptor': name, 'masks': [hex(v) for v in values], 'offsets_checked': len(addresses),
                      'CPU_reference': 'unmodified Intel SwizzleOffset AND CpuSwizzleBlt', 'result': 'CPU_PASS'})
    data = {name: (args.capture / (name + '.bin')).read_bytes() for name in ['cpu', 'gpu', 'expected']}
    require(all(len(value) == ROW * H for value in data.values()), 'capture truncated')
    require(all(data['gpu'][y * ROW:y * ROW + W * 4] == data['expected'][y * ROW:y * ROW + W * 4]
                for y in range(H)), 'this analysis requires the known GPU-correct baseline')
    actual = [data['cpu'][y * ROW + x] for y in range(H) for x in range(W * 4)]
    # A correct read of any valid RGBA texel must have G=0, B=0, A=255 in this R8 workload.
    channel_invariants = {channel: sum(actual[i] != value for i in range(index, len(actual), 4))
                          for channel, index, value in [('G_nonzero', 1, 0), ('B_nonzero', 2, 0), ('A_not_255', 3, 255)]}
    # Compare alternative uncompressed tilings only where both mappings reference observed active texels.
    # Never fill unknown allocation/padding with zeros to inflate a match rate.
    chosen_addresses = [swizzle(masks, pitch, x, y) for y in range(H) for x in range(W * 4)]
    candidates = []
    for name in ['LINEAR', 'INTEL_TILE_Y', 'INTEL_TILE_X', 'INTEL_TILE_YF_32', 'INTEL_TILE_YS_32']:
        for candidate_pitch in sorted(set([1040, 1280, 1536])):
            if name != 'LINEAR' and candidate_pitch % (1 << definitions[name][0].bit_count()):
                continue
            defined = {}
            for y in range(H):
                for x in range(W * 4):
                    address = y * candidate_pitch + x if name == 'LINEAR' else swizzle(definitions[name], candidate_pitch, x, y)
                    defined[address] = data['expected'][y * ROW + x]
            overlap = [(i, defined[address]) for i, address in enumerate(chosen_addresses) if address in defined]
            mismatches = sum(actual[i] != value for i, value in overlap)
            candidates.append({'hypothesis': 'zero-origin uncompressed ' + name, 'candidate_pitch': candidate_pitch,
                               'defined_bytes_compared': len(overlap), 'mismatches': mismatches,
                               'unobserved_backing_bytes_not_assumed': len(actual) - len(overlap),
                               'result': 'REJECTED_UNDER_STATED_ORIGIN_MODEL' if mismatches else 'NOT_REJECTED'})
    # Invert only the selected address mapping. No claim that these are decompressed/raw GPU pixels.
    recovered = dict(zip(chosen_addresses, actual))
    first = bytes(recovered[i] for i in range(16))
    report = {'classification': 'OFFLINE_BINARY_TRACE_AND_CPU_REFERENCE_CONFIRMED',
              'GPU_or_driver_test_executed': False, 'root_cause': 'UNVERIFIED',
              'installed_driver_equals_archived_disassembly_image': True,
              'selected_path': {'getBytes_swizzle_branch_test_VA': '0x19eed', 'observed_m_Info_0x1ac': hex(raw['0x1ac']),
                                'linear_memcpy_path_selected': False, 'table_LEA_VA': '0x19f8f',
                                'table_VA': hex(table), 'tiling_enum': enum, 'descriptor_VA': hex(descriptor),
                                'descriptor_masks': [hex(v) for v in masks], 'descriptor_name': names[0],
                                'source_pitch': pitch, 'linear_destination_pitch': ROW, 'resource_flags_0x1c': raw['resource_0x1c'],
                                'lock_resolve_trigger': 'resource+0x1c bit0=1; m_Info+0x1ad bit2=0',
                                'unobserved': ['m_Info+0x110 height', 'mip/slice offset table contents',
                                               'actual locked backing allocation bytes', 'kernel AUX/dirty/CCS state']},
              'independent_native_CPU_tests': tests, 'alternative_layout_checks': candidates,
              'observed_CPU_channel_invariant_violations': channel_invariants,
              'recovered_backing_under_zero_origin_model': {'bytes': len(recovered), 'min_address': min(recovered),
                                                            'max_address': max(recovered), 'first_16_bytes_hex': first.hex(),
                                                            'limits': 'Conditional inverse map only; not a capture of all raw backing.'},
              'interpretation': ['Simple spatial permutation of valid RGBA texels cannot create nonzero G/B or lose constant alpha.',
                                 'Every tested zero-origin uncompressed layout has mismatches in defined overlapping bytes.',
                                 'Compressed/unresolved main-surface representation is consistent with data, but not uniquely proven.',
                                 'Wrong backing, unobserved subresource offsets and padding remain alternatives; no candidate fix is validated.'],
              'evidence': [file_record(p) for p in [args.driver, donor, args.intel_source,
                            ROOT / 'ga412/tools/swizzle-reference.c', Path(__file__),
                            args.capture / 'result.json', args.capture / 'probe.stderr',
                            *[args.capture / (name + '.bin') for name in data], args.output / 'build.json']]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'selected_descriptor': names[0], 'source_pitch': pitch,
                      'native_offsets_checked': sum(t['offsets_checked'] for t in tests),
                      'alternative_layouts_checked': len(candidates), 'channel_violations': channel_invariants}))


if __name__ == '__main__':
    main()
