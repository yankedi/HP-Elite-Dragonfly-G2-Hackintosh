#!/usr/bin/env python3
"""Check the public tree's core evidence, configuration and artifact boundaries."""
import ast
import hashlib
import json
from pathlib import Path
import plistlib
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors = []
    counts = {'files': 0, 'json': 0, 'python': 0, 'plist': 0}
    forbidden_suffixes = {'.img', '.dmg', '.raw', '.qcow2', '.iso', '.pkg', '.cpio',
                          '.zip', '.key', '.pem', '.p12', '.pfx', '.o', '.a', '.so', '.dylib', '.exe'}
    private_key = re.compile(rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----')
    private_paths = [b'/home/' + b'yan/', b'/Users/' + b'yan/']
    personal_endpoints = re.compile(rb'(?:192\.168\.1\.86|100\.86\.149\.94|' +
                                    b'|'.join(re.escape(p) for p in private_paths) + b')')
    magic = (b'\x7fELF', b'MZ', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe')
    for path in ROOT.rglob('*'):
        rel = path.relative_to(ROOT)
        if '.git' in rel.parts or '__pycache__' in rel.parts:
            if '.git' in rel.parts and rel.parts[0] != '.git':
                errors.append(f'Nested Git metadata in publication: {rel}')
            continue
        if path.is_symlink():
            errors.append(f'Symlink requires explicit review: {rel}')
            continue
        if not path.is_file():
            continue
        counts['files'] += 1
        if any(p in ('.local', '.cache', 'private') for p in rel.parts):
            errors.append(f'Private directory in public tree: {rel}')
        if path.suffix.lower() in forbidden_suffixes:
            errors.append(f'Binary/private artifact in public tree: {rel}')
        if path.stat().st_size > 50 * 1024 * 1024:
            errors.append(f'Large file requires review: {rel}')
            continue
        raw = path.read_bytes()
        if raw.startswith(magic):
            errors.append(f'Executable binary in public tree: {rel}')
        if private_key.search(raw):
            errors.append(f'Private key material in {rel}')
        if personal_endpoints.search(raw):
            errors.append(f'Original personal endpoint/path in {rel}')
        if path.suffix == '.json':
            counts['json'] += 1
            try:
                json.loads(raw)
            except (ValueError, UnicodeError) as exc:
                errors.append(f'{rel}: {exc}')
        if path.suffix == '.py':
            counts['python'] += 1
            try:
                ast.parse(raw, filename=str(rel))
            except (SyntaxError, UnicodeError) as exc:
                errors.append(f'{rel}: {exc}')
        if path.suffix == '.plist':
            counts['plist'] += 1
            try:
                plistlib.loads(raw)
            except (ValueError, plistlib.InvalidFileException) as exc:
                errors.append(f'{rel}: {exc}')

    required = ['README.md', 'graphics/README.md', 'mac-for-elitebook/README.md',
                'tgl26-usb/README.md', 'EFI/components.json', 'docs/ISSUE-DRAFT.md',
                'evidence/software-control-summary.json', 'evidence/panics-manifest.json']
    for name in required:
        if not (ROOT / name).is_file():
            errors.append(f'Missing publication entry: {name}')
    for path in (ROOT / 'EFI').glob('*.example.plist'):
        data = plistlib.loads(path.read_bytes())
        generic = data['PlatformInfo']['Generic']
        if any(generic[k] for k in ('SystemSerialNumber', 'MLB', 'SystemUUID')) or any(generic['ROM']):
            errors.append(f'Nonblank machine identity: {path.name}')
        for values in data['NVRAM']['Add'].values():
            if any(k.lower().startswith('bluetooth') for k in values):
                errors.append(f'Cached Bluetooth identity: {path.name}')
    for path in [ROOT / 'README.md', *(ROOT / 'docs').glob('*.md'), ROOT / 'EFI/README.md', ROOT / 'evidence/README.md']:
        for link in re.findall(r'\]\(([^)\s]+)\)', path.read_text()):
            if re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', link) or link.startswith('#'):
                continue
            target = link.split('#', 1)[0]
            if target and not (path.parent / target).exists():
                errors.append(f'Broken current documentation link: {path.relative_to(ROOT)} -> {target}')
    manifest = ROOT / 'evidence/panics-manifest.json'
    if manifest.is_file():
        for record in json.loads(manifest.read_text())['records']:
            path = ROOT / 'evidence' / record['public_file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != record['public_text_sha256']:
                errors.append(f'Panic text hash mismatch: {record["public_file"]}')
    inventories = ROOT / 'evidence/loaded-kexts-manifest.json'
    if inventories.is_file():
        for record in json.loads(inventories.read_text())['records']:
            path = ROOT / 'evidence' / record['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
                errors.append(f'Loaded-kext inventory hash mismatch: {record["file"]}')
        experimental = ('com.StezzaPilot.NootedGreen', 'AppleIntelTGLGraphicsFramebuffer',
                        'AppleIntelTGLGraphics', 'org.smichaud.HookCase')
        accelerated = (ROOT / 'evidence/accelerated-loaded-kexts.txt').read_text()
        control = (ROOT / 'evidence/software-display-loaded-kexts.txt').read_text()
        if not all(name in accelerated for name in experimental) or any(name in control for name in experimental):
            errors.append('Published loaded-kext inventories contradict the reported control')
    graphics_sums = ROOT / 'graphics/provenance/SHA256SUMS'
    if graphics_sums.is_file():
        for line in graphics_sums.read_text().splitlines():
            expected, name = line.split('  ', 1)
            path = (ROOT / 'graphics' / name).resolve()
            if not path.is_relative_to(ROOT / 'graphics') or not path.is_file():
                errors.append(f'Invalid graphics checksum path: {name}')
            elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                errors.append(f'Graphics publication hash mismatch: {name}')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        raise SystemExit(1)
    print('Public tree checks passed:', ', '.join(f'{v} {k}' for k, v in counts.items()))
    print('Scope: static publication checks; no boot, hardware stability or new rebuild claim.')


if __name__ == '__main__':
    main()
