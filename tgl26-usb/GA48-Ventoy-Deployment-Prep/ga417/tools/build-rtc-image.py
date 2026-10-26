#!/usr/bin/env python3
"""Clone sealed GA416 image; change only Kernel/Quirks/DisableRtcChecksum."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ga417/private/rtc'
spec = importlib.util.spec_from_file_location('common', ROOT / 'ga414/tools/common.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
NAME = 'HP-Tahoe-GA417-RTC-CHECKSUM-ONLY.img'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-existing', action='store_true',
                        help='Finish verification of an existing image without rewriting it')
    options = parser.parse_args()
    os.umask(0o077)
    WORK.mkdir(parents=True, exist_ok=True)
    baseline = json.loads((ROOT/'ga416/reports/L3-6-IMAGE.json').read_text())
    source = ROOT/baseline['image']['path']
    assert c.sha(source) == baseline['image']['sha256']
    original = ROOT/'ga416/private/l3-six/image-readback/EFI/OC/config.plist'
    assert c.sha(original) == baseline['full_image_inventory']['EFI/OC/config.plist']
    raw = original.read_bytes()
    find = b'<key>DisableRtcChecksum</key>\n\t\t\t<false/>'
    replace = b'<key>DisableRtcChecksum</key>\n\t\t\t<true/>'
    assert raw.count(find) == 1
    changed = raw.replace(find, replace, 1)
    before, after = plistlib.loads(raw), plistlib.loads(changed)
    assert before['Kernel']['Quirks']['DisableRtcChecksum'] is False
    assert after['Kernel']['Quirks']['DisableRtcChecksum'] is True
    after['Kernel']['Quirks']['DisableRtcChecksum'] = False
    assert after == before
    config = WORK/'config-RTC-CHECKSUM-ONLY.plist'
    if options.verify_existing:
        assert config.read_bytes() == changed
    else:
        with config.open('xb') as f:
            f.write(changed)
    # Keep an explicit exact config rollback, in addition to the original IMG.
    rollback = WORK/'config-GA416-ROLLBACK.plist'
    if options.verify_existing:
        assert rollback.read_bytes() == raw
    else:
        with rollback.open('xb') as f:
            f.write(raw)
    validation = c.run([ROOT/'out/ocvalidate', config])
    assert 'No issues found' in validation
    image = WORK/NAME
    if not options.verify_existing:
        with source.open('rb') as src, image.open('xb') as dst:
            shutil.copyfileobj(src,dst)
            dst.flush()
            os.fsync(dst.fileno())
    assert image.stat().st_size == source.stat().st_size
    image_hash_before = c.sha(image)
    disk = str(image)+'@@1048576'
    if not options.verify_existing:
        c.run(['mcopy','-o','-i',disk,config,'::/EFI/OC/config.plist'])
        image_hash_before = c.sha(image)
    readback = WORK/('readback-verified' if options.verify_existing else 'readback')
    readback.mkdir()
    c.run(['mcopy','-s','-i',disk,'::/*',readback])
    wanted = dict(baseline['full_image_inventory'])
    wanted['EFI/OC/config.plist'] = c.sha(config)
    assert c.inventory(readback) == wanted
    assert c.inventory(readback)['EFI/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen'] == baseline['NG_binary_sha256']
    # Switching back recovers the complete original file inventory.
    restored = dict(wanted)
    restored['EFI/OC/config.plist'] = c.sha(rollback)
    assert restored == baseline['full_image_inventory']
    assert (readback/'EFI/OC/config.plist').read_bytes() == changed
    with source.open('rb') as src, image.open('rb') as dst:
        assert src.read(1048576) == dst.read(1048576)
    fd, temporary = tempfile.mkstemp(prefix='ga417-rtc-',suffix='.fat',dir='/tmp/opencode')
    try:
        with os.fdopen(fd,'wb') as dst, image.open('rb') as src:
            src.seek(1048576)
            shutil.copyfileobj(src,dst)
        fat = c.run(['fsck.fat','-n','-v',temporary])
        # Exercise rollback on a disposable FAT copy, then extract all files.
        # Neither the delivered candidate nor the original IMG is changed.
        c.run(['mcopy','-o','-i',temporary,rollback,'::/EFI/OC/config.plist'])
        with tempfile.TemporaryDirectory(prefix='ga417-rtc-rollback-',dir='/tmp/opencode') as dest:
            c.run(['mcopy','-s','-i',temporary,'::/*',dest])
            assert c.inventory(Path(dest)) == baseline['full_image_inventory']
        rollback_fat = c.run(['fsck.fat','-n','-v',temporary])
    finally:
        Path(temporary).unlink()
    assert c.sha(source) == baseline['image']['sha256']
    assert c.sha(image) == image_hash_before
    report = {'status':'RTC_CHECKSUM_SINGLE_FACTOR_IMAGE_BUILT_NOT_BOOTED',
        'image':c.record(image),'baseline':baseline['image'],
        'only_semantic_change':{'path':'Kernel/Quirks/DisableRtcChecksum','before':False,'after':True},
        'config':c.record(config),'rollback_config':c.record(rollback),
        'changed_files':['EFI/OC/config.plist'],'added_files':[],'removed_files':[],
        'file_inventory':wanted,'all_kexts_and_GA416_graphics_stack_unchanged':True,
        'NG_UUID':baseline['NG_UUID'],'NG_binary_sha256':baseline['NG_binary_sha256'],
        'ocvalidate':validation,'FAT_check':fat,'MBR_unchanged':True,
        'readback':'ALL_FILES_MATCH_EXPECTED','rollback_inventory':'EXACT_GA416_BASELINE',
        'rollback_applied_to_disposable_FAT_and_all_files_reextracted':True,
        'rollback_FAT_check':rollback_fat,'resumed_existing_verification':options.verify_existing,
        'prior_attempt_limit':'First build stopped during temporary FAT copy with ENOSPC; source image and candidate retained. Resumed verification is independent.',
        'baseline_IMG_preserved':True,'Metal_bundle_in_image':False,
        'RTCMemoryFixup_or_IO_length_or_other_memory_Quirk_changes':False,
        'internal_EFI_modified':False,'booted':False,'RTC005_fix_confirmed':False}
    c.save(ROOT/'ga417/reports/RTC-IMAGE.json',report)
    (WORK/(NAME+'.sha256')).write_text(c.sha(image)+'  '+NAME+'\n')
    print(json.dumps({k:report[k] for k in ['status','image','only_semantic_change','changed_files']},indent=2))


if __name__ == '__main__':
    main()
