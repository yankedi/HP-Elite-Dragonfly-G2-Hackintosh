#!/usr/bin/env python3
"""Make a new private configuration copy; never alter an existing image or EFI."""
import copy
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    original = ROOT.parent / 'out/stage/EFI/OC/config.plist'
    config = plistlib.loads(original.read_bytes())
    candidate = copy.deepcopy(config)
    guid = '7C436110-AB2A-4BBB-A880-FE41995C9F82'
    assert config['NVRAM']['Add'][guid]['csr-active-config'] == bytes(4)
    assert 'csr-active-config' not in config['NVRAM']['Delete'][guid]
    # Explicitly leave the Recovery-managed persistent CSR as the only source.
    del candidate['NVRAM']['Add'][guid]['csr-active-config']
    dest = ROOT / 'private/config-GA410-preserve-Recovery-CSR.plist'
    with dest.open('xb') as stream:
        plistlib.dump(candidate, stream, sort_keys=False)
    r = subprocess.run([str(ROOT.parent / 'out/ocvalidate'), str(dest)], capture_output=True, text=True)
    (ROOT / 'private/ocvalidate.txt').write_text(r.stdout + r.stderr)
    assert r.returncode == 0
    report = {'new_config': str(dest.relative_to(ROOT)), 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest(), 'only_change': 'Remove default Add csr-active-config=0; retain persistent Recovery CSR; no AMFI arg added', 'ocvalidate_rc': r.returncode, 'applied_to_any_EFI_or_image': False, 'existing_GA48_behavior': 'Add only supplies a value if missing; csr-active-config is not in Delete, so an existing Recovery-persisted CSR is not overwritten. Validate actual state after VESA maintenance boot.', 'NVRAM_Delete': config['NVRAM']['Delete'][guid], 'WriteFlash': config['NVRAM']['WriteFlash'], 'source_documentation': 'https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/Configuration.tex'}
    (ROOT / 'reports/CONFIG.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: new private configuration copy validated; existing GA48/VESA/internal EFI untouched')


if __name__ == '__main__':
    main()
