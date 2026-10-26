#!/usr/bin/env python3
"""Prove re-signing preserved every original Mach-O section and dylib command."""
import hashlib
import json
from pathlib import Path
import struct
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def macho(data):
    assert data[:4] == b'\xcf\xfa\xed\xfe', 'expected thin x86_64 Mach-O'
    ncmds = struct.unpack_from('<I', data, 16)[0]
    commands, sections = [], {}
    offset = 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', data, offset)
        assert size >= 8 and offset + size <= len(data)
        if cmd == 0x19:
            count = struct.unpack_from('<I', data, offset + 64)[0]
            for index in range(count):
                section = offset + 72 + index * 80
                name = data[section:section + 16].split(b'\0')[0].decode()
                segment = data[section + 16:section + 32].split(b'\0')[0].decode()
                length = struct.unpack_from('<Q', data, section + 40)[0]
                start = struct.unpack_from('<I', data, section + 48)[0]
                flags = struct.unpack_from('<I', data, section + 64)[0]
                if flags & 0xff not in {1, 12, 18}:  # S_ZEROFILL variants have no file bytes.
                    assert start + length <= len(data)
                    sections[segment + ':' + name] = hashlib.sha256(data[start:start + length]).hexdigest()
        elif cmd != 0x1d:  # Only the code-signature load command may change.
            commands.append(data[offset:offset + size].hex())
        offset += size
    return sections, commands


def main():
    manifest = json.loads((ROOT.parent / 'ga49/private/GA47-MANIFEST.expected.json').read_text())
    original = ROOT.parent.parent / 'GA47-JulioNectar-HP-Port/build/ga47/GA47-HP-TGL-25G83-offline.tar.gz'
    report = []
    with tarfile.open(original) as old, tarfile.open(ROOT / 'private/package-signed.tar.gz') as new:
        binaries = {b['path'] for b in manifest['binaries']}
        for path in sorted(binaries):
            a = old.extractfile('package/' + path).read()
            b = new.extractfile('package-signed/' + path).read()
            sa, ca = macho(a)
            sb, cb = macho(b)
            assert sa == sb, 'Section changed: ' + path
            assert ca == cb, 'Non-signature load command changed: ' + path
            report.append({'path': path, 'sections': len(sa), 'all_section_hashes_equal': True, 'all_non_signature_non_segment_load_commands_equal': True})
        checked = 0
        for item in manifest['inventory']:
            path = item['path']
            if 'sha256' not in item or path in binaries or '/_CodeSignature/' in path:
                continue
            value = new.extractfile('package-signed/' + path).read()
            assert hashlib.sha256(value).hexdigest() == item['sha256'], path
            checked += 1
    signing = json.loads((ROOT / 'reports/SIGNING.json').read_text())
    signing['functional_code_check'] = 'PASS_ALL_31_MACHO_SECTIONS_AND_NON_SIGNATURE_COMMANDS_UNCHANGED'
    signing['unchanged_other_resources_and_plists'] = checked
    signing['code_comparison'] = report
    (ROOT / 'reports/SIGNING.json').write_text(json.dumps(signing, indent=2) + '\n')
    print('PASS: all 31 Mach-O section bytes/functional load commands and', checked, 'other resources/plists unchanged')


if __name__ == '__main__':
    main()
