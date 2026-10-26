#!/usr/bin/env python3
"""CPU-only first GA416 boot audit and lossless before/after evidence sheets."""
import hashlib
import json
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[2]
GA=ROOT/'ga416';WORK=GA/'private/l3-six-runtime';REPORTS=GA/'reports'
IMAGES=GA/'images/l3-six-runtime'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def receipt(name):return load(GA/'private/commands'/('l3six-'+name+'.json'))
def body(name):return json.loads(receipt(name)['stdout'])


def sheet(left,right,dest,labels):
    a=Image.open(left).convert('RGB');b=Image.open(right).convert('RGB')
    width=max(a.width,b.width);height=max(a.height,b.height)
    out=Image.new('RGB',(width*2,height+35),'#dddddd');draw=ImageDraw.Draw(out)
    draw.text((10,10),labels[0],fill='black');draw.text((width+10,10),labels[1],fill='black')
    out.paste(a,(0,35));out.paste(b,(width,35));out.save(dest)


def main():
    initial=body('initial-runtime-health');dmesg=initial['dmesg']['stdout']
    session=initial['session']['stdout'].strip();uuid='REDACTED-SESSION-ID'
    assert session=='REDACTED-SESSION-ID'
    assert uuid in initial['loaded']['stdout'] and initial['build']['stdout'].strip()=='25G83'
    assert 'HP-GA416: L3 override 0 -> 6' in dmesg and 'HP-GA416: effective L3BankCount = 6' in dmesg
    assert 'HP-R5: native TGL topology slices=1 subslices=10 maxEU/SS=8 totalEU=80 L3Banks=6 nativeL3=0 mirrors=1/10 dispatchers=5' in dmesg
    assert 'GA414 NOAUX: gate=1 cpu=0x8c pci=8086:9a49 subsystem=103c:8716 build=25G83' in dmesg
    signature=receipt('native-signature');assert signature['returncode']==0
    ng_sha=load(REPORTS/'L3-6-BUILD.json')['binary']['sha256']
    assert uuid in signature['stdout'] and ng_sha in signature['stdout'] and 'Signature=adhoc' in signature['stderr']
    desktop=load(WORK/'desktop-reviewed.json');assert desktop['status']=='PREVIOUS_DESKTOP_ARTIFACTS_NOT_OBSERVED'
    capture=WORK/'captures/desktop';assert (capture/'exit').read_text().strip()=='0'
    for name,digest in desktop['screenshots'].items():assert sha(capture/name)==digest
    health=[];expected_diags={x['path']:x['sha256'] for x in initial['diagnostics']}
    for name in ['health-before-desktop','health-immediate-pre-desktop','health-after-desktop',
                 'r8-health-immediate-pre','r8-health-post','final-health',
                 'recovery-health-before-permission-fix','recovery-health-immediate-pre',
                 'recovery-health-post','recovery-final-health']:
        row=body(name);assert row['status']=='HEALTH_GATE_PASS' and row['session']==session
        assert {x['path']:x['sha256'] for x in row['diagnostics']}==expected_diags
        health.append({'name':name,**row})
    # The only R8 launcher attempt was rejected by exec permission before main ran.
    attempt=receipt('r8-execute-ONCE');assert attempt['returncode']==126
    assert (WORK/'captures/r8.exit').read_text().strip()=='126'
    stderr=(WORK/'captures/r8.stderr').read_text()
    assert 'Permission denied' in stderr and (WORK/'captures/r8.stdout').stat().st_size==0
    assert not (WORK/'captures/r8-capture').exists()
    assert (WORK/'STOP-GPU.json').is_file()
    assert '-rw-r--r--' in receipt('r8-failed-launch-readonly')['stdout']
    recovery=receipt('recovery-r8-execute-ONCE');assert recovery['returncode']==0
    assert (WORK/'captures/r8-recovery.exit').read_text().strip()=='0'
    fix=body('recovery-fix-executable-permission')
    assert fix['before_mode']=='0o644' and fix['after_mode']=='0o700'
    assert fix['binary_sha256_unchanged']=='b324901b7c4dd8b62f812fb08b0e98950eb303c160a2bc9764302178d930db37'
    primary=load(WORK/'R8-PIXEL-AUDIT.json');assert primary['status']=='PIXEL_PASS'
    cap=WORK/'captures/r8-recovery-capture'
    raw={n:(cap/(n+'.bin')).read_bytes() for n in ['input','expected','gpu','cpu']}
    # Independent Expected: direct packed index, no primary-auditor/generator imports.
    expected=bytes(c for k in range(257*65) for c in ((13*(k%257)+29*(k//257))%256,0,0,255))
    active={n:b''.join(raw[n][y*1280:y*1280+1028] for y in range(65)) for n in ['expected','gpu','cpu']}
    assert len(raw['input'])==512*65 and all(len(raw[n])==1280*65 for n in active)
    assert all(raw['input'][(k//257)*512+k%257]==expected[4*k] for k in range(257*65))
    assert active['expected']==expected
    comparisons={}
    for name,a,b in [('gpu_vs_expected',active['gpu'],expected),('cpu_vs_expected',active['cpu'],expected),
                     ('cpu_vs_gpu',active['cpu'],active['gpu'])]:
        stats={'bad_pixels':sum(a[i:i+4]!=b[i:i+4] for i in range(0,len(a),4)),
               'differing_bytes':sum(x!=y for x,y in zip(a,b)),'total_pixels':257*65}
        assert stats['bad_pixels']==primary['comparisons'][name]['bad_pixels']==0
        assert stats['differing_bytes']==primary['comparisons'][name]['differing_bytes']==0
        comparisons[name]=stats
    traces=[json.loads(l.split('CPU_TRACE_JSON ',1)[1]) for l in (WORK/'captures/r8-recovery.stderr').read_text().splitlines() if l.startswith('CPU_TRACE_JSON ')]
    assert len(traces)==10 and [r['sequence'] for r in traces]==list(range(1,11))
    stacks={}
    for event in traces:
        stack=stacks.setdefault(event['thread'],[])
        if event['phase']=='enter':stack.append(event['method'])
        else:assert event['phase']=='exit' and stack.pop()==event['method']
    assert all(not stack for stack in stacks.values())
    metadata=load(cap/'result.json');assert len(metadata['commands'])==1
    IMAGES.mkdir(parents=True,exist_ok=True)
    sheet(GA/'private/captures/desktop/settings-window.png',capture/'settings-window.png',
          IMAGES/'settings-before-after.png',('PLANES2 / L3=8 / earlier boot','GA416 / L3=6 / current boot'))
    sheet(GA/'private/captures/finder-scene/window.png',capture/'finder-window.png',
          IMAGES/'finder-before-after.png',('PLANES2 / L3=8 / earlier boot','GA416 / L3=6 / current boot'))
    old=Image.open(GA/'private/captures/desktop/settings.png');new=Image.open(capture/'settings.png')
    old.crop((100,990,1820,1080)).save(IMAGES/'dock-before.png')
    new.crop((100,990,1820,1080)).save(IMAGES/'dock-after.png')
    sheet(IMAGES/'dock-before.png',IMAGES/'dock-after.png',IMAGES/'dock-before-after.png',
          ('PLANES2 / L3=8 / earlier boot','GA416 / L3=6 / current boot'))
    oldboot=json.loads(load(GA/'private/commands/boot-health-20261025T062703Z.json')['stdout'])
    oldargs=oldboot['identity']['stdout'].split('kern.bootargs: ',1)[1].strip()
    assert initial['bootargs']['stdout'].strip()==oldargs
    previous=load(REPORTS/'EVIDENCE-MANIFEST.json')['files']
    for name,row in previous.items():assert sha(ROOT/name)==row['sha256'],name
    result={
        'status':'L3_6_RUNTIME_CONFIRMED_DESKTOP_ARTIFACTS_RESOLVED_IN_OBSERVED_SCENES',
        'states':{'SOURCE_PATCHED':True,'KEXT_BUILT':True,'IMG_BUILT':True,'IMG_DEPLOYED':True,
                  'NEW_DRIVER_BOOTED':True,'L3_6_RUNTIME_CONFIRMED':True,
                  'DESKTOP_ARTIFACTS_RESOLVED':True,'DESKTOP_ARTIFACTS_REMAIN':False,
                  'desktop_state_scope':'Only observed Settings/About,Finder,Dock scenes; wallpaper excluded'},
        'session':session,'NG_UUID':uuid,'NG_binary_sha256':ng_sha,
        'system':'macOS26.6.2/25G83','PCI':'8086:9A49','subsystem':'103C:8716',
        'topology':{'slices':1,'SS':10,'EU_per_SS':8,'EUs':80,'native_donor_L3':0,'effective_L3':6,
                    'mirrors':[1,10],'dispatchers':5},
        'hardware_L3_evidence':'Prior NixOS measurement 0x9118=0x88; runtime log is an explicit static reference, not a live Fuse read',
        'runtime_lines':[l for l in dmesg.splitlines() if any(k in l for k in ['HP-GA416:','HP-R5: native TGL','GA414 NOAUX:','XeNG NOAUX:','XE-NOCCS3:','XeNG PLANES2:'])],
        'NOAUX_install_verified':True,'NOCCS3_install_verified':True,'PLANES2_install_verified':True,
        'native_codesign_strict_deep':{'status':'PASS','receipt':'ga416/private/commands/l3six-native-signature.json',
                                      'object':'Exact cross-signed build artifact staged in temporary directory, never re-signed or installed; hash/UUID match build and loadedUUID'},
        'desktop':desktop,'settings_window':next(w for w in load(capture/'settings-metadata/windows.json') if w['kCGWindowNumber']==40),
        'finder_window':next(w for w in load(capture/'finder-metadata/windows.json') if w['kCGWindowNumber']==34),
        'image_capture':'GUI Terminal system screencapture; archived GA415 binary metadata only. No ScreenCaptureKit image claim.',
        'wallpaper':'OUT_OF_SCOPE_USER_REQUEST','same_frame_physical_camera_pair':'NOT_CAPTURED; user provided firsthand observation',
        'comparison':{'baseline_boot':'8B9C5493-4CAC-487E-8452-4E59B0096778','baseline_L3':8,'current_L3':6,
                      'bootargs_identical':True,'build_functional_diff':'Only native TGL L3 fallback 8->6; logging changed',
                      'interpretation':'Supports L3 mismatch as a cause of the previous desktop artifacts; observed Settings/Finder/Dock now correct.',
                      'limits':'Cross-boot qualitative scene comparison; live content/focus/layout can vary; not independent per-pixel Expected proof or long-term stability.'},
        'R8':{'status':'PIXEL_PASS','pixel_status':'PIXEL_PASS','GPU_executions':1,'explicit_command_buffers':1,
              'launcher_attempts_including_preexec_rejection':2,'automatic_retry':False,
              'permission_fix':fix,'recovery_authorization':load(WORK/'r8-permission-recovery-authorized.json'),
              'initial_preexec_failure':{'exit':126,'stderr':stderr,'GPU_submissions':0,'original_STOP_and_claim_preserved':True},
              'successful_execution_exit':0,'comparisons':comparisons,'second_independent_Expected_auditor_agrees':True,
              'active_sha256':{n:hashlib.sha256(data).hexdigest() for n,data in active.items()},
              'full_sha256':{n:hashlib.sha256(data).hexdigest() for n,data in raw.items()},
              'tracer_events':len(traces),'tracer_nesting_balanced':True,'metadata':metadata,
              'limits':'One managed RT case; no long-term stability or per-resource kernel CCS/NOAUX counter claim.'},
        'health':{'gates':health,'diagnostic_files':len(expected_diags),'new_or_changed_within_this_observation':[],
                  'boot_epoch':health[0]['boot_epoch'],'first_observation_epoch':initial['observed_epoch'],
                  'last_observation_UTC':health[-1]['utc'],'stability':'BOUNDED_HEALTHY_OBSERVATION_NOT_LONG_TERM'},
        'counter_query':receipt('ioreg-counters'),'counter_limit':'Empty query/exit1 is neither pass nor fail; use in-boot logs.',
        'source_commit':load(REPORTS/'L3-6-SOURCE.json')['source_commit'],
        'no_driver_source_or_image_edits_this_run':True,'automatic_reboot':False,
        'old_GA416_evidence_files_unchanged':len(previous)}
    (REPORTS/'L3-6-RUNTIME-RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'NG_UUID':uuid,'native_codesign_strict':'PASS',
                      'R8':result['R8']['status'],'health_gates':len(health),'diagnostics':len(expected_diags)}))


if __name__=='__main__':main()
