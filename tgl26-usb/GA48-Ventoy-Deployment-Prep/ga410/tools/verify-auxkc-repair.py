#!/usr/bin/env python3
"""Verify the real linked AuxKC, its five Mach-Os, and preserved baseline kexts."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import uuid


def commands(data, offset=0):
    magic, cpu, _, kind, count, total, _, _ = struct.unpack_from('<8I', data, offset)
    assert magic == 0xFEEDFACF and cpu == 0x01000007, 'Not x86_64 Mach-O'
    cursor = offset + 32
    end = cursor + total
    assert end <= len(data)
    result = []
    for _ in range(count):
        command, size = struct.unpack_from('<II', data, cursor)
        assert size >= 8 and cursor + size <= end
        result.append((command, cursor, size))
        cursor += size
    assert cursor == end
    return kind, result


def decode(path):
    data = Path(path).read_bytes()
    kind, cmds = commands(data)
    assert kind == 12, 'Not MH_FILESET'
    filesets, prelink, collection_uuid = {}, None, None
    for command, cursor, size in cmds:
        if command == 0x1B:
            collection_uuid = str(uuid.UUID(bytes=data[cursor + 8:cursor + 24])).upper()
        elif command == 0x80000035:
            address, offset, name_offset, _ = struct.unpack_from('<QQII', data, cursor + 8)
            name = data[cursor + name_offset:cursor + size].split(b'\0', 1)[0].decode()
            _, inner = commands(data, offset)
            uuids = [str(uuid.UUID(bytes=data[p + 8:p + 24])).upper()
                     for cmd, p, _ in inner if cmd == 0x1B]
            assert len(uuids) == 1 and name not in filesets
            filesets[name] = {'address': address, 'file_offset': offset, 'uuid': uuids[0]}
        elif command == 0x19:
            for section in range(struct.unpack_from('<I', data, cursor + 64)[0]):
                p = cursor + 72 + section * 80
                name = data[p:p + 16].rstrip(b'\0')
                segment = data[p + 16:p + 32].rstrip(b'\0')
                if (segment, name) == (b'__PRELINK_INFO', b'__info'):
                    _, length, offset = struct.unpack_from('<QQI', data, p + 32)
                    prelink = plistlib.loads(data[offset:offset + length].rstrip(b'\0'))
    assert prelink and collection_uuid
    assert str(uuid.UUID(bytes=prelink['_PrelinkKCID'])).upper() == collection_uuid
    members = {}
    for item in prelink['_PrelinkInfoDictionary']:
        name = item['CFBundleIdentifier']
        assert name not in members
        path = item['_PrelinkBundlePath']
        assert path.startswith('/Library/') and '/Volumes/' not in path
        record = {'version': item['CFBundleVersion'], 'path': path}
        if 'CFBundleExecutable' in item:
            assert name in filesets and item['_PrelinkExecutableSize'] > 0
            assert item['_PrelinkExecutableLoadAddr'] == filesets[name]['address']
            record.update(filesets[name])
        members[name] = record
    assert set(filesets) == {e['CFBundleIdentifier'] for e in prelink['_PrelinkInfoDictionary']
                             if 'CFBundleExecutable' in e}
    return {
        'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
        'uuid': collection_uuid,
        'boot_uuid': str(uuid.UUID(bytes=prelink['_BootKCID'])).upper(),
        'system_uuid': str(uuid.UUID(bytes=prelink['_PageableKCID'])).upper(),
        'members': members, 'executable_count': len(filesets),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate')
    parser.add_argument('baseline')
    args = parser.parse_args()
    candidate, baseline = decode(args.candidate), decode(args.baseline)
    assert baseline['sha256'] == '5d6170588133eae3fe1d4f0024f67960f0ce6aeb6d2f3266e9865d96ddfa8fcd'
    assert candidate['boot_uuid'] == baseline['boot_uuid']
    assert candidate['system_uuid'] == baseline['system_uuid']
    expected = {
        'org.smichaud.HookCase': '4C4C4459-5555-3144-A1DA-AC5685822B59',
        'com.xxxxx.driver.AppleIntelTGLGraphics': 'BA3AA1C0-FE6B-33B3-9D85-73F848394E3D',
        'com.xxxxx.driver.AppleIntelTGLGraphicsFramebuffer': 'B96A8448-9D17-3F78-B76D-15A0B359A9A0',
    }
    assert set(candidate['members']) == set(baseline['members']) | set(expected)
    for name, old in baseline['members'].items():
        new = candidate['members'][name]
        assert old['version'] == new['version'], name
        if 'uuid' in old:
            assert old['uuid'] == new['uuid'], name
    for name, expected_uuid in expected.items():
        assert candidate['members'][name]['uuid'] == expected_uuid, name
    assert candidate['executable_count'] == 5 and len(candidate['members']) == 6
    print(json.dumps({'verification': 'PASS', 'candidate': candidate, 'baseline': baseline,
                      'trusted_runtime_loading_proven': False}, indent=2))


if __name__ == '__main__':
    main()
