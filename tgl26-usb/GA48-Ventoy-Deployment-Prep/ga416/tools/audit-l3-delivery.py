#!/usr/bin/env python3
"""Final local audit of actual build/deployment receipts; no remote or GPU work."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'ga416/private/l3-six'
REPORTS=ROOT/'ga416/reports'
SPEC=importlib.util.spec_from_file_location('c',ROOT/'ga414/tools/common.py')
c=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(c)


def load(name):return json.loads((REPORTS/name).read_text())


def main():
    src=load('L3-6-SOURCE.json');build=load('L3-6-BUILD.json');image=load('L3-6-IMAGE.json')
    signature=load('L3-6-SIGNATURE.json');delivery=load('L3-6-DELIVERY.json')
    assert src['source_commit']==build['source_commit']==delivery['source_commit']
    assert build['MachO']['uuid']==image['NG_UUID']==delivery['NG_UUID']
    assert build['binary']['sha256']==image['NG_binary_sha256']
    assert delivery['sha256']==image['image']['sha256']
    assert c.sha(ROOT/image['image']['path'])==delivery['sha256']
    assert c.inventory(WORK/'image-readback')==image['full_image_inventory']
    assert signature['status']=='OFFLINE_ADHOC_INTEGRITY_PASS'
    assert all(d['pages_verified']==110 and d['special_slots_verified']==[1,2,3] for d in signature['directories'])
    assert len(signature['corruption_controls_rejected'])==3
    assert build['new_undefined_symbols']==[]
    for record in [build['binary'],build['recipe'],build['archive'],build['compile_log'],build['signature_tool'],src['diff'],src['static_fuse_evidence'],image['baseline_PLANES2'],image['FAT_check']]:
        path=ROOT/record['path'];assert path.stat().st_size==record['bytes'] and c.sha(path)==record['sha256'],path
    baseline=json.loads((ROOT/'ga415/reports/PLANES2-IMAGE.json').read_text())
    diff=[n for n in image['full_image_inventory'] if image['full_image_inventory'][n]!=baseline['full_image_inventory'][n]]
    assert diff==['EFI/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen']
    assert image['full_image_inventory'].keys()==baseline['full_image_inventory'].keys()
    assert delivery['states']=={'SOURCE_PATCHED':True,'KEXT_BUILT':True,'IMG_BUILT':True,'IMG_DEPLOYED':True,
                                'NEW_DRIVER_BOOTED':'NOT_TESTED','L3_6_RUNTIME_CONFIRMED':'NOT_TESTED',
                                'DESKTOP_ARTIFACTS_RESOLVED':'NOT_TESTED','DESKTOP_ARTIFACTS_REMAIN':'NOT_TESTED'}
    for name,digest in delivery['commands'].items():assert c.sha(ROOT/name)==digest
    before=json.loads(json.loads((WORK/'usb-protected-before.json').read_text())['stdout'])
    after=json.loads(json.loads((WORK/'usb-protected-after.json').read_text())['stdout'])
    for key in ['protected_images','boot_ESP_readonly_hash_snapshot','boot_id','USB_partition']:assert before[key]==after[key]
    mount=json.loads(json.loads((WORK/'usb-readonly-mounted-readback.json').read_text())['stdout'])
    assert mount['full_image_inventory']==image['full_image_inventory']
    assert mount['unmounted'] and mount['loop_detached'] and mount['mount_readonly']
    assert mount['image_sha256_after_mount']==delivery['sha256']
    old_manifest=load('EVIDENCE-MANIFEST.json')['files']
    for name,record in old_manifest.items():assert c.sha(ROOT/name)==record['sha256'],name
    assert c.inventory(Path(src['source_worktree'])/'src/NootedGreen')==src['source_inventory']
    assert c.run(['git','-C',src['source_worktree'],'status','--porcelain'])==''
    original=ROOT.parent/'GA414-Native-NOAUX-Source'
    assert c.run(['git','-C',original,'status','--porcelain'])==''
    assert c.run(['git','-C',original,'rev-parse','HEAD']).strip()==src['baseline_commit']
    assert c.inventory(original/'src/NootedGreen')==c.inventory(ROOT/'ga414/private/source/src/NootedGreen')
    for p in (ROOT/'ga416/tools').glob('*.py'):compile(p.read_text(),str(p),'exec')
    subprocess.run(['bash','-n',str(ROOT/'ga416/tools/check-l3-six-macos.sh')],check=True)
    report_path=ROOT/'ga416/GA416-L3-6-DELIVERY.md'
    for link in re.findall(r'\]\(([^)]+)\)',report_path.read_text()):
        if '://' not in link:assert (report_path.parent/link).is_file(),link
    evidence_files=[p for p in WORK.rglob('*') if p.is_file()]
    evidence_files.extend(p for p in REPORTS.glob('L3-6-*.json') if p.name!='L3-6-FINAL-AUDIT.json')
    evidence_files.extend([REPORTS/'GA416-L3-6.patch',REPORTS/'HP-Tahoe-GA416-L3-6.img.sha256',report_path])
    evidence_files.extend((ROOT/'ga416/tools').glob('*l3*'))
    files={str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':c.sha(p)} for p in sorted(set(evidence_files)) if p.is_file()}
    result={'status':'GA416_L3_6_DELIVERY_AUDIT_PASS','source_commit':src['source_commit'],
            'NG_UUID':delivery['NG_UUID'],'image_sha256':delivery['sha256'],'USB_image':delivery['USB_image'],
            'image_files':len(mount['full_image_inventory']),'changed_image_files':diff,
            'protected_USB_images_unchanged':len(before['protected_images']),
            'internal_boot_ESP_files_unchanged':len(before['boot_ESP_readonly_hash_snapshot']),
            'prior_GA416_evidence_files_unchanged':len(old_manifest),'independent_source_worktree_clean':True,
            'original_GA414_source_worktree_unchanged_and_clean':True,
            'signature_offline':'PASS','native_codesign_strict':'NOT_RUN_MACOS_UNAVAILABLE',
            'manual_boot_and_desktop':'NOT_TESTED','evidence':files}
    (REPORTS/'L3-6-FINAL-AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='evidence'},ensure_ascii=False))


if __name__=='__main__':main()
