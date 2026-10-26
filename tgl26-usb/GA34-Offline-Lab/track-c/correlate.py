#!/usr/bin/env python3
"""Offline evidence matching. Range overlap is never allocation identity or causality."""
import json
from pathlib import Path

MAX_VA=(1<<48)-1
VA_LIMIT=MAX_VA+1
# Evidence accepts normalized physical root addresses, not CR3/PCID bitfields.
# This is a bounded 48-bit input model, not proof of mapped physical memory.
PML4_LIMIT=1<<48

def known_counter(value):
    return type(value) is int and value>=0

def known_label(value):
    return type(value) is str and bool(value.strip())

def known_identity(value):
    return known_counter(value) or known_label(value)

def valid_pml4(value):
    return type(value) is int and 0<value<PML4_LIMIT and value%4096==0

def add_limitation(record,code):
    if code not in record['limitations']:record['limitations'].append(code)

def correlate(hang,fault,allocations):
    result={'level':'UNAVAILABLE','candidates':[],'same_allocation_proved':False,
            'sample_allocation_proved':False,'hang_allocation_proved':False,
            'identity_scope':'NONE','exact_access_address_proved':False,
            'hang_causality_proved':False,'limitations':[],'rejected_candidates':[]}
    if not isinstance(hang,dict):
        add_limitation(result,'INVALID_HANG_RECORD');return result
    if not isinstance(fault,dict):
        add_limitation(result,'INVALID_FAULT_RECORD');return result
    if fault.get('capture_status')!='OK':
        add_limitation(result,'FAULT_CAPTURE_UNAVAILABLE');return result
    if fault.get('valid') is not True:
        add_limitation(result,'FAULT_VALID_CLEAR');return result
    va=fault.get('page_va')
    if not known_counter(va) or va>MAX_VA or va%4096:
        add_limitation(result,'INVALID_FAULT_VA');return result
    result['level']='TEMPORAL_UNPROVEN'
    sequence=hang.get('hang_sequence')
    if not known_counter(sequence) or not known_counter(fault.get('hang_sequence')) or sequence!=fault['hang_sequence']:
        add_limitation(result,'SEQUENCE_UNPROVEN');return result
    before,after=fault.get('sample_before'),fault.get('sample_after')
    stamp=hang.get('timestamp')
    if any(not known_counter(x) for x in [before,after,stamp]) or not stamp<=before<=after:
        add_limitation(result,'TIMESTAMP_INCONSISTENT');return result
    epoch=hang.get('reset_epoch')
    if (fault.get('pre_reset_epoch_verified') is not True or not known_counter(epoch)
        or not known_counter(fault.get('reset_epoch')) or fault['reset_epoch']!=epoch):
        add_limitation(result,'RESET_TIMING_UNPROVEN');return result
    clock=hang.get('clock_id')
    if not known_label(clock) or not known_label(fault.get('clock_id')) or fault['clock_id']!=clock:
        add_limitation(result,'CLOCK_DOMAIN_UNPROVEN');return result
    if fault.get('address_space') not in ('PPGTT','GGTT'):
        add_limitation(result,'ADDRESS_SPACE_UNKNOWN');return result
    result['level']='ADDRESS_RANGE_CANDIDATE'
    space=fault['address_space'];pml4=hang.get('pml4')
    context_proven=(known_counter(hang.get('context_id')) and known_counter(fault.get('context_id'))
                    and fault['context_id']==hang['context_id'])
    ppgtt_proven=(space=='GGTT' or (valid_pml4(pml4) and valid_pml4(fault.get('pml4')) and pml4==fault['pml4']))
    if not context_proven or not ppgtt_proven:add_limitation(result,'CONTEXT_ADDRESS_SPACE_UNPROVEN')
    else:result['level']='ADDRESS_SPACE_MATCH'
    if not isinstance(allocations,(list,tuple)):
        add_limitation(result,'INVALID_ALLOCATION_LIST');return result
    for index,a in enumerate(allocations):
        if not isinstance(a,dict):
            add_limitation(result,'INVALID_ALLOCATION_RECORD')
            result['rejected_candidates'].append({'index':index,'code':'INVALID_ALLOCATION_RECORD'});continue
        base,size=a.get('base'),a.get('size')
        if not known_counter(base) or not known_counter(size) or size==0 or base>=VA_LIMIT or size>VA_LIMIT-base:
            add_limitation(result,'INVALID_ALLOCATION_RANGE')
            result['rejected_candidates'].append({'index':index,'code':'INVALID_ALLOCATION_RANGE'});continue
        # Fault register represents a page. Match overlapping bytes, never infer exact access address.
        if not (base<va+4096 and va<base+size):continue
        if a.get('address_space')!=space:continue
        item={'index':index,'kind':a.get('kind','UNKNOWN'),'allocation_id':a.get('allocation_id'),
              'mapping_generation':a.get('mapping_generation'),'range_overlap_only':True,'base':base,'size':size,
              'level':'ADDRESS_RANGE_CANDIDATE','sample_identity_match':False,'hang_identity_match':False,
              'limitations':[]}
        address_match=(context_proven and ppgtt_proven
                       and (space=='GGTT' or (valid_pml4(a.get('pml4')) and a['pml4']==pml4)))
        if address_match:item['level']='ADDRESS_SPACE_MATCH'
        else:add_limitation(item,'ALLOCATION_ADDRESS_SPACE_UNPROVEN')
        clock_match=known_label(a.get('clock_id')) and a['clock_id']==clock
        epoch_match=known_counter(a.get('reset_epoch')) and a['reset_epoch']==epoch
        if not clock_match:add_limitation(item,'ALLOCATION_CLOCK_DOMAIN_UNPROVEN')
        if not epoch_match:add_limitation(item,'ALLOCATION_RESET_EPOCH_UNPROVEN')
        start,end=a.get('valid_from'),a.get('valid_to')
        interval_valid=known_counter(start) and known_counter(end) and start<=end
        if start is None or end is None:add_limitation(item,'ALLOCATION_LIFETIME_UNPROVEN')
        elif not interval_valid:add_limitation(item,'INVALID_ALLOCATION_INTERVAL')
        sample_live=interval_valid and start<=before<=after<=end
        if interval_valid and not sample_live:add_limitation(item,'SAMPLE_ALLOCATION_LIFETIME_UNPROVEN')
        identity_match=(known_identity(a.get('allocation_id')) and known_identity(fault.get('allocation_id'))
                        and type(a['allocation_id']) is type(fault['allocation_id'])
                        and a['allocation_id']==fault['allocation_id']
                        and known_counter(a.get('mapping_generation')) and known_counter(fault.get('mapping_generation'))
                        and a['mapping_generation']==fault['mapping_generation'])
        if not identity_match:add_limitation(item,'ALLOCATION_IDENTITY_UNPROVEN')
        receipt_verified=a.get('identity_verified') is True and known_label(a.get('identity_evidence'))
        if not receipt_verified:add_limitation(item,'IDENTITY_RECEIPT_UNVERIFIED')
        sample_match=address_match and clock_match and epoch_match and sample_live and identity_match and receipt_verified
        hang_identity=True
        for key,check in [('allocation_id',known_identity),('mapping_generation',known_counter)]:
            if key in hang and (not check(hang[key]) or not check(a.get(key))
                                or type(hang[key]) is not type(a[key]) or hang[key]!=a[key]):
                hang_identity=False;add_limitation(item,'HANG_ALLOCATION_IDENTITY_UNPROVEN')
        hang_live=interval_valid and start<=stamp<=before<=after<=end
        if sample_match:
            item['sample_identity_match']=True;item['range_overlap_only']=False
            item['level']='SAMPLE_ALLOCATION_IDENTITY_MATCH'
            if not hang_live:add_limitation(item,'HANG_ALLOCATION_LIFETIME_UNPROVEN')
            if hang_live and hang_identity:
                item['hang_identity_match']=True;item['level']='ALLOCATION_IDENTITY_MATCH'
        for code in item['limitations']:add_limitation(result,code)
        result['candidates'].append(item)
    identities=[a for a in result['candidates'] if a['sample_identity_match']]
    if len(identities)>1:add_limitation(result,'AMBIGUOUS_ALLOCATION_ALIAS')
    elif len(identities)==1:
        result['sample_allocation_proved']=True;result['identity_scope']='SAMPLE_ONLY'
        result['level']='SAMPLE_ALLOCATION_IDENTITY_MATCH'
        if identities[0]['hang_identity_match']:
            result['same_allocation_proved']=True;result['hang_allocation_proved']=True
            result['identity_scope']='HANG_THROUGH_SAMPLE';result['level']='ALLOCATION_IDENTITY_MATCH'
    if not result['candidates']:add_limitation(result,'FAULT_PAGE_UNATTRIBUTED')
    add_limitation(result,'ADDRESS_IDENTITY_IS_NOT_HANG_CAUSALITY')
    return result

def synthetic_cases():
    hang={'hang_sequence':1,'context_id':5,'pml4':0x1000,'timestamp':100,'clock_id':'mock','reset_epoch':2}
    fault={'capture_status':'OK','valid':True,'page_va':0x426fd000,'hang_sequence':1,'context_id':5,'pml4':0x1000,
           'sample_before':101,'sample_after':102,'clock_id':'mock','reset_epoch':2,'pre_reset_epoch_verified':True,'address_space':'PPGTT'}
    allocs=[{'kind':kind,'base':base,'size':size,'address_space':'PPGTT','pml4':0x1000,'clock_id':'mock','reset_epoch':2}
             for kind,base,size in [('Batch',0x426fd000,0x1104),('Shader',0x4271d000,8192),
                                    ('Surface',0x43000000,8192),('PostSync',0x40001040,8)]]
    cases=[]
    def add(name,h,f,aa):
        cases.append({'name':name,'hang':h,'fault':f,'allocations':aa,'result':correlate(h,f,aa)})
    for a in allocs:
        add(a['kind'],hang,dict(fault,page_va=a['base']&~4095),allocs)
    for name,f in [('unknown',dict(fault,page_va=0x70000000)),('invalid',dict(fault,valid=False)),
                   ('timing',dict(fault,pre_reset_epoch_verified=False))]:
        add(name,hang,f,allocs)
    identity=dict(allocs[0],allocation_id='alloc1',mapping_generation=9,identity_verified=True,
                  identity_evidence='synthetic-mapping-receipt',valid_from=99,valid_to=103)
    identified=dict(fault,allocation_id='alloc1',mapping_generation=9)
    add('identity-positive',hang,identified,[identity])
    add('epoch-unknown',dict(hang,reset_epoch=None),dict(identified,reset_epoch=None),[identity])
    add('proof-string-false',hang,dict(identified,pre_reset_epoch_verified='false'),[identity])
    for name,root_address in [('negative',-1),('unaligned',0x1001)]:
        add('pml4-'+name,dict(hang,pml4=root_address),dict(identified,pml4=root_address),[dict(identity,pml4=root_address)])
    add('allocation-foreign-clock',hang,identified,[dict(identity,clock_id='foreign')])
    add('allocation-foreign-epoch',hang,identified,[dict(identity,reset_epoch=99)])
    add('allocation-sample-only',hang,identified,[dict(identity,valid_from=101)])
    add('allocation-replaced',dict(hang,allocation_id='old',mapping_generation=8),identified,[dict(identity,valid_from=101)])
    add('allocation-malformed-time',hang,identified,[dict(identity,valid_from='99')])
    add('last-va-byte',hang,dict(identified,page_va=VA_LIMIT-4096),[dict(identity,base=MAX_VA,size=1)])
    return cases

def main():
    root=Path(__file__).resolve().parents[1]
    cases=synthetic_cases()
    output=root/'track-c/reports/synthetic-correlation-fixed.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'schema':2,'input_class':'SYNTHETIC_MOCK_NOT_HARDWARE','cases':cases},indent=2)+'\n')
    print(len(cases),'synthetic attribution cases;',output.relative_to(root))
if __name__=='__main__':main()
