from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'track-c'))
from correlate import correlate

class Correlation(unittest.TestCase):
    def setUp(self):
        self.h={'hang_sequence':1,'context_id':5,'pml4':0x1000,'timestamp':1,'clock_id':'mock','reset_epoch':1}
        self.f={'capture_status':'OK','valid':True,'page_va':0x2000,'hang_sequence':1,'context_id':5,'pml4':0x1000,
                'sample_before':2,'sample_after':3,'clock_id':'mock','reset_epoch':1,'pre_reset_epoch_verified':True,'address_space':'PPGTT'}
        self.a={'kind':'Batch','base':0x2000,'size':64,'address_space':'PPGTT','pml4':0x1000}
    def test_range_never_identity(self):
        r=correlate(self.h,self.f,[self.a]);self.assertEqual(r['level'],'ADDRESS_SPACE_MATCH');self.assertFalse(r['same_allocation_proved'])
    def test_all_kinds(self):
        for k in ['Batch','Shader','Surface','PostSync']:
            with self.subTest(kind=k):self.assertEqual(correlate(self.h,self.f,[dict(self.a,kind=k)])['candidates'][0]['kind'],k)
    def test_fault_invalid(self):self.assertEqual(correlate(self.h,dict(self.f,valid=False),[self.a])['level'],'UNAVAILABLE')
    def test_fault_unavailable(self):self.assertEqual(correlate(self.h,dict(self.f,capture_status='MMIO_FAILED'),[self.a])['level'],'UNAVAILABLE')
    def test_sequence_missing(self):self.assertEqual(correlate(self.h,dict(self.f,hang_sequence=2),[self.a])['level'],'TEMPORAL_UNPROVEN')
    def test_epoch_mismatch(self):self.assertEqual(correlate(self.h,dict(self.f,reset_epoch=2),[self.a])['level'],'TEMPORAL_UNPROVEN')
    def test_time_backwards(self):self.assertIn('TIMESTAMP_INCONSISTENT',correlate(self.h,dict(self.f,sample_after=0),[self.a])['limitations'])
    def test_clock_mismatch(self):self.assertEqual(correlate(self.h,dict(self.f,clock_id='wall'),[self.a])['level'],'TEMPORAL_UNPROVEN')
    def test_context_mismatch(self):self.assertFalse(correlate(self.h,dict(self.f,context_id=6),[self.a])['same_allocation_proved'])
    def test_pml4_mismatch(self):self.assertEqual(correlate(self.h,dict(self.f,pml4=0x3000),[self.a])['level'],'ADDRESS_RANGE_CANDIDATE')
    def test_identity_requires_generation_interval_and_evidence(self):
        a=dict(self.a,allocation_id='alloc1',mapping_generation=9,identity_evidence='synthetic-mapping-receipt',
               identity_verified=True,clock_id='mock',reset_epoch=1,valid_from=0,valid_to=4)
        f=dict(self.f,allocation_id='alloc1',mapping_generation=9)
        r=correlate(self.h,f,[a]);self.assertTrue(r['same_allocation_proved']);self.assertFalse(r['hang_causality_proved'])
        self.assertFalse(correlate(self.h,dict(f,mapping_generation=10),[a])['same_allocation_proved'])
    def test_alias_is_ambiguous(self):
        a=dict(self.a,allocation_id='alloc1',mapping_generation=9,identity_evidence='synthetic',
               identity_verified=True,clock_id='mock',reset_epoch=1,valid_from=0,valid_to=4)
        r=correlate(self.h,dict(self.f,allocation_id='alloc1',mapping_generation=9),[a,a]);self.assertFalse(r['same_allocation_proved'])
    def test_no_range(self):self.assertEqual(correlate(self.h,dict(self.f,page_va=0x4000),[self.a])['candidates'],[])
    def test_overflow(self):self.assertIn('INVALID_ALLOCATION_RANGE',correlate(self.h,self.f,[dict(self.a,base=1<<48)])['limitations'])
    def test_high_invalid_fault_va(self):self.assertEqual(correlate(self.h,dict(self.f,page_va=1<<48),[self.a])['level'],'UNAVAILABLE')
if __name__=='__main__':unittest.main()
