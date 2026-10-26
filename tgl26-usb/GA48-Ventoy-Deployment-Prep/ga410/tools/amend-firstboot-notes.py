#!/usr/bin/env python3
"""Correct inherited VESA-only notes in our two new images, preserving receipts."""
import hashlib
import json
import shlex
import shutil
import subprocess
from pathlib import Path
import importlib.util

import recovery_ssh
import remote


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    root = remote.ROOT
    recovery_ssh.configure()
    spec = importlib.util.spec_from_file_location('firstboot_delivery', Path(__file__).with_name('deliver-firstboot-images.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = json.loads((root / 'reports/FINALPREP-IMAGES.json').read_text())
    delivery = json.loads((root / 'reports/FINALPREP-DELIVERY.json').read_text())
    for name in ['FINALPREP-IMAGES', 'FINALPREP-DELIVERY']:
        saved = root / ('private/' + name + '-before-note-fix.json')
        with saved.open('xb') as stream:
            stream.write((root / ('reports/' + name + '.json')).read_bytes())
    results = []
    for image, delivered in zip(report['images'], delivery['images']):
        local = root.parent / image['local_image']
        old_hash = image['sha256']
        assert sha(local) == old_hash
        note = root / ('reports/BOOT-IN-' + ('TGL' if image['kind'] == 'tgl' else 'RECOVERY') + '.txt')
        subprocess.run(['mcopy', '-o', '-i', str(local) + '@@1048576', str(note), '::/FIRST-BOOT.txt'], check=True)
        image['initial_delivered_sha256_before_note_correction'] = old_hash
        image['first_boot_note_sha256'] = sha(note)
        image['sha256'] = sha(local)
        dest = delivered['destination']
        temporary = dest + '.note-fix'
        remote.upload(local, temporary, timeout=360)
        command = ('set -eu; previous=$(' + module.HASHER + ' ' + shlex.quote(dest) + '); '
                   'replacement=$(' + module.HASHER + ' ' + shlex.quote(temporary) + '); '
                   '[ "${previous%% *}" = ' + old_hash + ' ]; '
                   '[ "${replacement%% *}" = ' + image['sha256'] + ' ]; '
                   '/bin/mv -f ' + shlex.quote(temporary) + ' ' + shlex.quote(dest) + '; /bin/sync')
        remote.run('recovery2222-finalprep-correct-embedded-note-' + image['kind'], command, timeout=180)
        inventory = module.mounted_inventory(image['kind'] + '-final-note', dest, kind=image['kind'])
        expected = dict(delivered['non_EFI_Recovery_payloads_unchanged_from_GA48'])
        expected['FIRST-BOOT.txt'] = image['first_boot_note_sha256']
        assert {k: v for k, v in inventory.items() if not k.startswith('EFI/')} == expected
        assert {k.removeprefix('EFI/'): v for k, v in inventory.items() if k.startswith('EFI/')} == image['efi_inventory']
        row = remote.run('recovery2222-finalprep-final-image-sha-' + image['kind'], module.HASHER + ' ' + shlex.quote(dest), timeout=150)
        assert row['stdout'].split('  ', 1)[0] == image['sha256']
        results.append({**{k: v for k, v in delivered.items() if k != 'non_EFI_Recovery_payloads_unchanged_from_GA48'},
                        'sha256': image['sha256'], 'non_EFI_payloads': expected,
                        'initial_sha256_before_note_correction': old_hash,
                        'intentional_non_EFI_change': 'Only FIRST-BOOT.txt: inherited VESA-only instruction corrected',
                        'BaseSystem_dmg_and_chunklist_unchanged': True})
    delivery['images'] = results
    delivery['inherited_notes_corrected_and_native_reverified'] = True
    (root / 'reports/FINALPREP-IMAGES.json').write_text(json.dumps(report, indent=2) + '\n')
    (root / 'reports/FINALPREP-DELIVERY.json').write_text(json.dumps(delivery, indent=2) + '\n')
    print(json.dumps([{k: item[k] for k in ['name', 'sha256']} for item in results], indent=2))


if __name__ == '__main__':
    main()
