#!/usr/bin/env python3
"""Export explicitly supplied local configs as public examples; never edit inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib


def export(source, destination):
    raw = source.read_bytes()
    config = plistlib.loads(raw)
    generic = config['PlatformInfo']['Generic']
    for key in ('SystemSerialNumber', 'MLB', 'SystemUUID'):
        generic[key] = ''
    generic['ROM'] = bytes(6)
    security = config['Misc']['Security']
    for key in ('PasswordHash', 'PasswordSalt'):
        security[key] = b''
    security['ApECID'] = 0
    removed = []
    for guid, values in config['NVRAM']['Add'].items():
        for key in list(values):
            if key.lower().startswith('bluetooth'):
                del values[key]
                removed.append(f'NVRAM/Add/{guid}/{key}')
    public = plistlib.dumps(config, sort_keys=False)
    destination.write_bytes(public)
    return {
        'source_config_sha256': hashlib.sha256(raw).hexdigest(),
        'public_config': destination.name,
        'public_config_sha256': hashlib.sha256(public).hexdigest(),
        'identity_fields_cleared': ['SystemSerialNumber', 'MLB', 'SystemUUID', 'ROM'],
        'security_fields_cleared': ['PasswordHash', 'PasswordSalt', 'ApECID'],
        'removed_cached_fields': removed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accelerated', type=Path, required=True)
    parser.add_argument('--software', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records = [export(args.accelerated, args.output / 'config-accelerated.example.plist'),
               export(args.software, args.output / 'config-software-display.example.plist')]
    (args.output / 'export-manifest.json').write_text(json.dumps({
        'schema_version': 1, 'opencore_version': '1.0.8',
        'scope': 'Sanitized configuration examples; not a newly boot-tested binary EFI.',
        'configurations': records,
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
