"""Real correlate() calls: exact archived failures plus isolated strengthened fixtures."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'track-c'))
from correlate import MAX_VA,PML4_LIMIT,VA_LIMIT,correlate,synthetic_cases


def audit_fixture():
    # Byte-for-byte JSON values from logs/audit-parser/results.json, not upgraded evidence.
    h={'hang_sequence':1,'context_id':5,'pml4':0x1000,'timestamp':1,'clock_id':'mock','reset_epoch':1}
    f={'capture_status':'OK','valid':True,'page_va':0x2000,'hang_sequence':1,'context_id':5,'pml4':0x1000,
       'sample_before':2,'sample_after':3,'clock_id':'mock','reset_epoch':1,'pre_reset_epoch_verified':True,
       'address_space':'PPGTT','allocation_id':'alloc1','mapping_generation':9}
    a={'kind':'Batch','base':0x2000,'size':64,'address_space':'PPGTT','pml4':0x1000,'allocation_id':'alloc1',
       'mapping_generation':9,'identity_evidence':'synthetic','valid_from':0,'valid_to':4}
    return h,f,a


def identity_fixture():
    h,f,a=audit_fixture()
    a.update(clock_id='mock',reset_epoch=1,identity_verified=True)
    return h,f,a


class CorrelationFixes(unittest.TestCase):
    def assert_no_identity(self,result):
        self.assertFalse(result['same_allocation_proved'])
        self.assertFalse(result['hang_allocation_proved'])
        self.assertFalse(result['sample_allocation_proved'])
        self.assertEqual(result['identity_scope'],'NONE')
        self.assertFalse(result['hang_causality_proved'])

    def assert_hang_identity(self,result):
        self.assertEqual(result['level'],'ALLOCATION_IDENTITY_MATCH')
        self.assertTrue(result['same_allocation_proved'])
        self.assertTrue(result['hang_allocation_proved'])
        self.assertTrue(result['sample_allocation_proved'])
        self.assertEqual(result['identity_scope'],'HANG_THROUGH_SAMPLE')
        self.assertFalse(result['hang_causality_proved'])
        self.assertFalse(result['exact_access_address_proved'])

    def test_c01_exact_missing_epochs_and_false_string(self):
        for case in ['reset-epoch-both-missing','verification-string-false']:
            with self.subTest(case=case):
                h,f,a=audit_fixture()
                if case=='reset-epoch-both-missing':
                    del h['reset_epoch'];del f['reset_epoch']
                else:f['pre_reset_epoch_verified']='false'
                r=correlate(h,f,[a])
                self.assert_no_identity(r)
                self.assertEqual(r['level'],'TEMPORAL_UNPROVEN')
                self.assertIn('RESET_TIMING_UNPROVEN',r['limitations'])

    def test_c01_gate_isolated_with_all_other_evidence_present(self):
        for value in [None,True,False,'1',-1,1.0,[],{}]:
            with self.subTest(epoch=value):
                h,f,a=identity_fixture()
                h['reset_epoch']=f['reset_epoch']=a['reset_epoch']=value
                self.assert_no_identity(correlate(h,f,[a]))
        for value in [False,'false','true',1,0,None,[],{}]:
            with self.subTest(flag=value):
                h,f,a=identity_fixture();f['pre_reset_epoch_verified']=value
                self.assert_no_identity(correlate(h,f,[a]))

    def test_c01_zero_epoch_is_known_and_missing_one_side_is_unknown(self):
        h,f,a=identity_fixture()
        h['reset_epoch']=f['reset_epoch']=a['reset_epoch']=0
        self.assert_hang_identity(correlate(h,f,[a]))
        for side in ['hang','fault']:
            with self.subTest(side=side):
                h,f,a=identity_fixture()
                del (h if side=='hang' else f)['reset_epoch']
                self.assert_no_identity(correlate(h,f,[a]))

    def test_c02_exact_invalid_matching_pml4(self):
        for value in [-1,0x1001]:
            with self.subTest(pml4=value):
                h,f,a=audit_fixture();h['pml4']=f['pml4']=a['pml4']=value
                r=correlate(h,f,[a])
                self.assert_no_identity(r)
                self.assertEqual(len(r['candidates']),1)
                self.assertEqual(r['candidates'][0]['level'],'ADDRESS_RANGE_CANDIDATE')
                self.assertIn('CONTEXT_ADDRESS_SPACE_UNPROVEN',r['limitations'])

    def test_c02_root_bounds_and_types_isolated(self):
        for value in [-4096,0,0x1001,PML4_LIMIT,PML4_LIMIT+4096,True,False,4096.0,'4096',None,[]]:
            with self.subTest(pml4=value):
                h,f,a=identity_fixture();h['pml4']=f['pml4']=a['pml4']=value
                self.assert_no_identity(correlate(h,f,[a]))
        for value in [4096,PML4_LIMIT-4096]:
            with self.subTest(valid_pml4=value):
                h,f,a=identity_fixture();h['pml4']=f['pml4']=a['pml4']=value
                self.assert_hang_identity(correlate(h,f,[a]))

    def test_c02_allocation_root_must_also_match(self):
        for value in [0x3000,-1,0x1001,PML4_LIMIT,True,None]:
            with self.subTest(allocation_pml4=value):
                h,f,a=identity_fixture();a['pml4']=value
                r=correlate(h,f,[a]);self.assert_no_identity(r)
                self.assertEqual(r['candidates'][0]['level'],'ADDRESS_RANGE_CANDIDATE')

    def test_c03_exact_foreign_allocation_clock_or_epoch(self):
        for key,value,code in [('clock_id','different-clock','ALLOCATION_CLOCK_DOMAIN_UNPROVEN'),
                               ('reset_epoch',99,'ALLOCATION_RESET_EPOCH_UNPROVEN')]:
            with self.subTest(key=key):
                h,f,a=audit_fixture();a[key]=value
                r=correlate(h,f,[a]);self.assert_no_identity(r)
                self.assertIn(code,r['limitations'])
                self.assertEqual(len(r['candidates']),1)

    def test_c03_allocation_domain_is_mandatory_isolated(self):
        for key,values in [('clock_id',[None,'','  ','different-clock',1,True,[]]),
                           ('reset_epoch',[None,-1,True,'1',1.0,99,[]])]:
            for value in values:
                with self.subTest(key=key,value=value):
                    h,f,a=identity_fixture();a[key]=value
                    r=correlate(h,f,[a]);self.assert_no_identity(r)
                    self.assertTrue(r['candidates'][0]['range_overlap_only'])
        for key in ['clock_id','reset_epoch']:
            with self.subTest(missing=key):
                h,f,a=identity_fixture();del a[key]
                self.assert_no_identity(correlate(h,f,[a]))

    def test_c04_exact_replacement_after_hang(self):
        h,f,a=audit_fixture()
        h.update(allocation_id='old-allocation',mapping_generation=8);a['valid_from']=2
        r=correlate(h,f,[a]);self.assert_no_identity(r)
        self.assertIn('HANG_ALLOCATION_IDENTITY_UNPROVEN',r['limitations'])

    def test_c04_replacement_has_only_sample_identity_with_complete_evidence(self):
        h,f,a=identity_fixture()
        h.update(allocation_id='old-allocation',mapping_generation=8);a['valid_from']=2
        r=correlate(h,f,[a])
        self.assertEqual(r['level'],'SAMPLE_ALLOCATION_IDENTITY_MATCH')
        self.assertEqual(r['identity_scope'],'SAMPLE_ONLY')
        self.assertTrue(r['sample_allocation_proved'])
        self.assertFalse(r['same_allocation_proved']);self.assertFalse(r['hang_allocation_proved'])
        self.assertIn('HANG_ALLOCATION_LIFETIME_UNPROVEN',r['limitations'])
        self.assertIn('HANG_ALLOCATION_IDENTITY_UNPROVEN',r['limitations'])
        self.assertFalse(r['hang_causality_proved'])

    def test_c04_lifetime_must_cover_hang_even_without_hang_identity_fields(self):
        h,f,a=identity_fixture();a['valid_from']=2
        r=correlate(h,f,[a])
        self.assertTrue(r['sample_allocation_proved']);self.assertFalse(r['same_allocation_proved'])
        self.assertIn('HANG_ALLOCATION_LIFETIME_UNPROVEN',r['limitations'])
        a['valid_from']=1;a['valid_to']=3
        self.assert_hang_identity(correlate(h,f,[a]))

    def test_c04_supplied_hang_identity_and_generation_each_bind(self):
        for fields in [dict(allocation_id='old'),dict(mapping_generation=8),dict(allocation_id=None),
                       dict(mapping_generation=None),dict(mapping_generation=True),dict(allocation_id=True)]:
            with self.subTest(fields=fields):
                h,f,a=identity_fixture();h.update(fields)
                r=correlate(h,f,[a])
                self.assertTrue(r['sample_allocation_proved']);self.assertFalse(r['same_allocation_proved'])
                self.assertIn('HANG_ALLOCATION_IDENTITY_UNPROVEN',r['limitations'])
        for fields in [dict(allocation_id='alloc1'),dict(mapping_generation=9),
                       dict(allocation_id='alloc1',mapping_generation=9)]:
            with self.subTest(matching_fields=fields):
                h,f,a=identity_fixture();h.update(fields)
                self.assert_hang_identity(correlate(h,f,[a]))

    def test_c05_exact_string_interval_is_structured(self):
        h,f,a=audit_fixture();a['valid_from']='0'
        r=correlate(h,f,[a]);self.assert_no_identity(r)
        self.assertEqual(len(r['candidates']),1)
        self.assertIn('INVALID_ALLOCATION_INTERVAL',r['limitations'])
        self.assertIn('INVALID_ALLOCATION_INTERVAL',r['candidates'][0]['limitations'])
        json.dumps(r)

    def test_c05_malformed_candidate_does_not_abort_next_valid_identity(self):
        for bad in [None,[],42,'allocation',{'base':True,'size':64},
                    {'base':VA_LIMIT,'size':1}]:
            with self.subTest(bad=bad):
                h,f,a=identity_fixture();r=correlate(h,f,[bad,a])
                self.assert_hang_identity(r)
                self.assertEqual(r['rejected_candidates'][0]['index'],0)
        for value in ['0',False,True,-1,0.0,[],{},float('nan')]:
            with self.subTest(valid_from=value):
                h,f,a=identity_fixture();bad=dict(a,valid_from=value)
                r=correlate(h,f,[bad,a]);self.assert_hang_identity(r)
                self.assertEqual(len(r['candidates']),2)
                self.assertFalse(r['candidates'][0]['sample_identity_match'])
                self.assertIn('INVALID_ALLOCATION_INTERVAL',r['candidates'][0]['limitations'])

    def test_c05_reversed_missing_or_sample_expired_intervals(self):
        for fields,code in [(dict(valid_from=4,valid_to=0),'INVALID_ALLOCATION_INTERVAL'),
                            (dict(valid_from=None),'ALLOCATION_LIFETIME_UNPROVEN'),
                            (dict(valid_to=None),'ALLOCATION_LIFETIME_UNPROVEN'),
                            (dict(valid_to=2),'SAMPLE_ALLOCATION_LIFETIME_UNPROVEN'),
                            (dict(valid_from=3),'SAMPLE_ALLOCATION_LIFETIME_UNPROVEN')]:
            with self.subTest(fields=fields):
                h,f,a=identity_fixture();a.update(fields)
                r=correlate(h,f,[a]);self.assert_no_identity(r)
                self.assertIn(code,r['limitations'])

    def test_x01_exact_last_va_byte_is_a_candidate(self):
        h,f,a=audit_fixture();f['page_va']=VA_LIMIT-4096;a.update(base=MAX_VA,size=1)
        r=correlate(h,f,[a]);self.assert_no_identity(r)
        self.assertEqual(len(r['candidates']),1)
        self.assertEqual(r['candidates'][0]['base'],MAX_VA)
        self.assertNotIn('INVALID_ALLOCATION_RANGE',r['limitations'])

    def test_x01_valid_half_open_ends_and_adjacent_nonoverlap(self):
        for base,size in [(MAX_VA,1),(VA_LIMIT-4096,4096),(VA_LIMIT-4,4)]:
            with self.subTest(base=base,size=size):
                h,f,a=identity_fixture();f['page_va']=VA_LIMIT-4096;a.update(base=base,size=size)
                self.assert_hang_identity(correlate(h,f,[a]))
        for base,size in [(MAX_VA,2),(VA_LIMIT,1),(0,VA_LIMIT+1),(0,0),(-1,1),(True,1),(0,True)]:
            with self.subTest(invalid_base=base,size=size):
                h,f,a=identity_fixture();a.update(base=base,size=size)
                r=correlate(h,f,[a]);self.assert_no_identity(r)
                self.assertIn('INVALID_ALLOCATION_RANGE',r['limitations'])
        for base,size in [(0x1000,4096),(0x3000,1)]:
            with self.subTest(adjacent_base=base):
                h,f,a=identity_fixture();a.update(base=base,size=size)
                self.assertEqual(correlate(h,f,[a])['candidates'],[])

    def test_identity_receipt_requires_true_boolean_and_nonempty_label(self):
        for flag in [None,False,1,'true','false',[],{}]:
            with self.subTest(flag=flag):
                h,f,a=identity_fixture();a['identity_verified']=flag
                r=correlate(h,f,[a]);self.assert_no_identity(r)
                self.assertIn('IDENTITY_RECEIPT_UNVERIFIED',r['limitations'])
        for receipt in [None,True,1,'','  ',[],{}]:
            with self.subTest(receipt=receipt):
                h,f,a=identity_fixture();a['identity_evidence']=receipt
                self.assert_no_identity(correlate(h,f,[a]))
        h,f,a=identity_fixture();self.assert_hang_identity(correlate(h,f,[a]))

    def test_weak_page_candidates_do_not_become_identity(self):
        h,f,a=identity_fixture()
        allocations=[dict(a,base=0x2010,size=8),dict(a,base=0x2080,size=8)]
        for a in allocations:
            for key in ['identity_verified','identity_evidence','allocation_id','mapping_generation']:del a[key]
        r=correlate(h,f,allocations);self.assert_no_identity(r)
        self.assertEqual(len(r['candidates']),2)
        self.assertTrue(all(a['range_overlap_only'] for a in r['candidates']))
        self.assertEqual(r['level'],'ADDRESS_SPACE_MATCH')
        self.assertFalse(r['exact_access_address_proved'])

    def test_identity_and_generation_are_typed_nonempty_and_matching(self):
        for key,values in [('allocation_id',[None,True,'','  ',[],{}]),
                           ('mapping_generation',[None,True,-1,'9',9.0,[],{}])]:
            for value in values:
                with self.subTest(key=key,value=value):
                    h,f,a=identity_fixture();a[key]=f[key]=value
                    self.assert_no_identity(correlate(h,f,[a]))
        h,f,a=identity_fixture();a['allocation_id']='1';f['allocation_id']=1
        self.assert_no_identity(correlate(h,f,[a]))
        h,f,a=identity_fixture();a['mapping_generation']=f['mapping_generation']=0
        self.assert_hang_identity(correlate(h,f,[a]))

    def test_alias_ambiguity_blocks_both_sample_and_hang_proof(self):
        h,f,a=identity_fixture()
        for allocations in [[a,dict(a)],[a,dict(a,valid_from=2)]]:
            with self.subTest(starts=[x['valid_from'] for x in allocations]):
                r=correlate(h,f,allocations);self.assert_no_identity(r)
                self.assertIn('AMBIGUOUS_ALLOCATION_ALIAS',r['limitations'])

    def test_ggtt_does_not_require_or_fabricate_a_pml4(self):
        h,f,a=identity_fixture();h.pop('pml4');f.pop('pml4');a.pop('pml4')
        f['address_space']=a['address_space']='GGTT'
        self.assert_hang_identity(correlate(h,f,[a]))
        f['context_id']=6
        r=correlate(h,f,[a]);self.assert_no_identity(r)
        self.assertEqual(len(r['candidates']),1)

    def test_other_typed_temporal_fields_and_invalid_containers(self):
        for field in ['hang_sequence','context_id','timestamp']:
            with self.subTest(hang_field=field):
                h,f,a=identity_fixture();h[field]=True
                self.assert_no_identity(correlate(h,f,[a]))
        for field in ['hang_sequence','context_id','sample_before','sample_after']:
            with self.subTest(fault_field=field):
                h,f,a=identity_fixture();f[field]=True
                self.assert_no_identity(correlate(h,f,[a]))
        h,f,a=identity_fixture()
        for bad_h,bad_f,bad_a,code in [(None,f,[a],'INVALID_HANG_RECORD'),(h,[],[a],'INVALID_FAULT_RECORD'),
                                       (h,f,None,'INVALID_ALLOCATION_LIST')]:
            with self.subTest(code=code):
                r=correlate(bad_h,bad_f,bad_a);self.assert_no_identity(r)
                self.assertIn(code,r['limitations'])

    def test_inputs_preserved_and_result_deterministic(self):
        h,f,a=identity_fixture();inputs=copy.deepcopy((h,f,[a]))
        first=correlate(h,f,[a]);self.assert_hang_identity(first)
        self.assertEqual((h,f,[a]),inputs)
        self.assertEqual(first,correlate(h,f,[a]))

    def test_updated_synthetic_samples_include_real_positive_and_negatives(self):
        cases={c['name']:c for c in synthetic_cases()}
        self.assertEqual(len(cases),18)
        self.assert_hang_identity(cases['identity-positive']['result'])
        self.assert_hang_identity(cases['last-va-byte']['result'])
        for name in ['allocation-sample-only','allocation-replaced']:
            with self.subTest(name=name):
                self.assertTrue(cases[name]['result']['sample_allocation_proved'])
                self.assertFalse(cases[name]['result']['same_allocation_proved'])
        for name in ['Batch','Shader','Surface','PostSync','epoch-unknown','proof-string-false',
                     'pml4-negative','pml4-unaligned','allocation-foreign-clock','allocation-foreign-epoch',
                     'allocation-malformed-time']:
            with self.subTest(name=name):self.assert_no_identity(cases[name]['result'])


if __name__=='__main__':unittest.main()
