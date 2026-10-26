#!/usr/bin/env python3
"""PLANES2 plus only the GA416 NG bundle; new image, never an installed EFI."""
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'ga416/private/l3-six'
REPORTS=ROOT/'ga416/reports'
NAME='HP-Tahoe-GA416-L3-6.img'
SPEC=importlib.util.spec_from_file_location('c',ROOT/'ga414/tools/common.py')
c=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(c)


def main():
    os.umask(0o077)
    baseline=json.loads((ROOT/'ga415/reports/PLANES2-IMAGE.json').read_text())
    build=json.loads((REPORTS/'L3-6-BUILD.json').read_text())
    signature=json.loads((REPORTS/'L3-6-SIGNATURE.json').read_text())
    assert signature['status']=='OFFLINE_ADHOC_INTEGRITY_PASS'
    source=ROOT/baseline['image']['path'];assert c.sha(source)==baseline['image']['sha256']
    bundle=WORK/'build/product/NootedGreen.kext'
    assert c.inventory(bundle)==build['bundle_inventory']==signature['bundle_sha256']
    image=WORK/NAME
    with source.open('rb') as src,image.open('xb') as dest:
        shutil.copyfileobj(src,dest);dest.flush();os.fsync(dest.fileno())
    for path in sorted(bundle.rglob('*')):
        if path.is_file():
            c.run(['mcopy','-o','-i',str(image)+'@@1048576',path,
                   '::/EFI/OC/Kexts/NootedGreen.kext/'+str(path.relative_to(bundle))])
    readback=WORK/'image-readback';readback.mkdir()
    c.run(['mcopy','-s','-i',str(image)+'@@1048576','::/*',readback])
    actual=c.inventory(readback);wanted=dict(baseline['full_image_inventory'])
    for name,digest in build['bundle_inventory'].items():wanted['EFI/OC/Kexts/NootedGreen.kext/'+name]=digest
    assert actual==wanted
    changes=sorted(n for n in actual if actual[n]!=baseline['full_image_inventory'][n])
    assert changes==['EFI/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen']
    config=(readback/'EFI/OC/config.plist').read_bytes()
    assert config==(ROOT/'ga415/private/planesfix/PLANES2-config.plist').read_bytes()
    args=plistlib.loads(config)['NVRAM']['Add']['REDACTED-MACHINE-ID']['boot-args']
    assert args==baseline['boot_args_after']
    for option in ['-ngreennoplanesfix','-ngreenplanesxor','-ngreenxefix','-ngreenccs','ngreen-l3','ngreen-eu','-ngreen415obs']:
        assert option not in args
    validation=c.run([ROOT/'out/ocvalidate',readback/'EFI/OC/config.plist'])
    assert 'No issues found' in validation
    with image.open('rb') as a,source.open('rb') as b:assert a.read(1048576)==b.read(1048576)
    table=json.loads(c.run(['sfdisk','--json',image]));parts=table['partitiontable']['partitions']
    assert len(parts)==1 and parts[0]['start']==2048 and parts[0]['size']==2621440 and parts[0]['type']=='ef' and parts[0]['bootable']
    partition=WORK/'l3-six-partition.fat'
    with image.open('rb') as src,partition.open('xb') as dest:
        src.seek(1048576);shutil.copyfileobj(src,dest)
    (WORK/'fsck.txt').write_text(c.run(['fsck.fat','-n','-v',partition]))
    assert c.sha(source)==baseline['image']['sha256']
    data=(readback/'EFI/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen').read_bytes()
    assert c.macho(data)==build['MachO']
    report={'status':'IMG_BUILT_CROSS_SIGNED_BOOT_NOT_TESTED','image':c.record(image),
            'baseline_PLANES2':c.record(source),'NG_UUID':build['MachO']['uuid'],
            'NG_binary_sha256':build['binary']['sha256'],'source_commit':build['source_commit'],
            'changed_files_vs_PLANES2':changes,'added_files':[],'removed_files':[],
            'full_image_inventory':actual,'config_byte_identical':True,'boot_args':args,
            'ocvalidate_output':validation,'FAT_check':c.record(WORK/'fsck.txt'),
            'partition_table':table,'MBR_unchanged':True,'reopened_mtools_readback_all_files_match':True,
            'signature_offline':'OFFLINE_ADHOC_INTEGRITY_PASS','native_codesign_strict':'NOT_RUN_MACOS_UNAVAILABLE',
            'readonly_kernel_mount':'PENDING','runtime':'NOT_TESTED','IMG_DEPLOYED':False}
    c.save(REPORTS/'L3-6-IMAGE.json',report)
    (REPORTS/(NAME+'.sha256')).write_text(c.sha(image)+'  '+NAME+'\n')
    print(json.dumps({k:report[k] for k in ['status','image','NG_UUID','changed_files_vs_PLANES2']}))


if __name__=='__main__':main()
