import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'track-a'))
import command_stream as C

END=0x05000000
def bbs(target,second=True,extra=0):
    return [0x18800101|(int(second)<<22)|extra,target&0xffffffff,target>>32]

class Commands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.src=C.Model('gen11');cls.dst=C.Model('gen12')
    def reject(self,code,fn,*args,**kw):
        with self.assertRaises(C.Rejected) as e:fn(*args,**kw)
        self.assertEqual(e.exception.code,code)
    def test_actual166_boundaries_match_historical_raw(self):
        raw=(ROOT/'inputs/batch.bin').read_bytes()[0x6000:0x7104]
        trace=C.Parser(self.src,{0x426fd000:raw},context=5).parse(0x426fd000)
        old=json.loads((ROOT/'inputs/batch-decoded.json').read_text())['per_gen']['gen11']['chains'][0]['instructions']
        self.assertEqual(len(trace),166)
        for a,b in zip(trace,old):
            self.assertEqual(a['source_va']-0x426f7000,b['offset'])
            self.assertEqual(a['raw'],b['raw_dwords'])
    def test_stencil_old_rejects_target_length(self):
        p=self.src.decode(C.binary([0x78060003,0,0,0,0]))
        r=C.validate_target(p,self.dst)
        self.assertEqual(r['classification'],'EXPLICITLY_NONCONFORMING')
    def test_draw_old_nonconforming(self):
        p=self.src.decode(C.binary([0x7b000008]+[0]*9))
        self.assertIn('TARGET_LENGTH_MISMATCH',C.validate_target(p,self.dst)['issues'])
    def test_draw_candidates_have_expected_lengths(self):
        for dw,n in [(0x7b000808,10),(0x7b000005,7)]:
            p=self.dst.decode(C.binary([dw]+[0]*(n-1)))
            self.assertEqual(p['length'],n*4)
    def test_source_short_command_refused(self):self.reject('INVALID_PACKET_LENGTH',self.src.decode,C.binary([0x78100000,0]))
    def test_unknown_packet(self):self.reject('UNKNOWN_PACKET',self.src.decode,C.binary([0xdeadbeef]))
    def test_truncated(self):self.reject('TRUNCATED_PACKET',self.src.decode,C.binary([0x78100007]))
    def test_bad_boundary(self):self.reject('BAD_BOUNDARY',self.src.decode,bytes(16),1)
    def test_oversize(self):self.reject('INVALID_LENGTH',C.words,bytes(C.MAX_BYTES+4))
    def test_dword_overflow(self):self.reject('DWORD_OVERFLOW',C.binary,[1<<32])
    def test_address_overflow(self):self.reject('INTEGER_OVERFLOW',C.checked_add,C.MAX_VA,1)
    def test_zero_modify_inherits_unknown(self):
        raw=C.binary([0x61010014]+[0]*21+[END]);p=C.Parser(self.src,{0x1000:raw});t=p.parse(0x1000)
        self.assertEqual(t[0]['state_after']['InstructionBase']['status'],'UNKNOWN')
        self.assertIn('UNRESOLVED_INHERITED_STATE',[e['code'] for e in t[0]['state_events']])
    def test_zero_modify_preserves_known(self):
        d=[0x61010014]+[0]*21;f=next(f for f in self.src.schema('STATE_BASE_ADDRESS')['fields'] if f['name']=='Instruction Base Address')
        d=C.setbits(d,f['start'],f['end'],0x123)
        mf=next(f for f in self.src.schema('STATE_BASE_ADDRESS')['fields'] if f['name']=='Instruction Base Address Modify Enable')
        d=C.setbits(d,mf['start'],mf['end'],1)
        p=C.Parser(self.src,{0x1000:C.binary(d+[0x61010014]+[0]*21+[END])});t=p.parse(0x1000)
        self.assertEqual(t[1]['state_after']['InstructionBase']['value'],0x123000)
    def test_pipeline_mask_zero_does_not_replace_unknown(self):
        p=C.Parser(self.src,{0x1000:C.binary([0x69040000,END])});t=p.parse(0x1000)
        self.assertEqual(t[0]['state_after']['PipelineSelect']['status'],'UNKNOWN')
    def test_uncaptured_heap_explicit(self):
        raw=(ROOT/'inputs/batch.bin').read_bytes()[0x6000:0x7104]
        t=C.Parser(self.src,{0x426fd000:raw}).parse(0x426fd000)
        draws=[p for p in t if p['name']=='3DPRIMITIVE']
        self.assertEqual(len(draws),4)
        self.assertTrue(all(any(e['code']=='RESOURCE_DATA_MISSING' for e in p['state_events']) for p in draws))
        self.assertTrue(all(p['state_after']['RenderTarget']['status']=='UNKNOWN' for p in draws))
    def test_nested_returns(self):
        seg={0x1000:C.binary(bbs(0x2000)+[END]),0x2000:C.binary([0,END])}
        t=C.Parser(self.src,seg).parse(0x1000)
        self.assertEqual([p['source_va'] for p in t],[0x1000,0x2000,0x2004,0x100c])
    def test_first_level_tail_call(self):
        seg={0x1000:C.binary(bbs(0x2000,False)+[0xdeadbeef]),0x2000:C.binary([END])}
        t=C.Parser(self.src,seg).parse(0x1000)
        self.assertEqual(len(t),2)
    def test_loop(self):self.reject('BATCH_LOOP',C.Parser(self.src,{0x1000:C.binary(bbs(0x1000,False))}).parse,0x1000)
    def test_depth_bound(self):
        p=C.Parser(self.dst,{0x1000:C.binary(bbs(0x2000)+[END]),0x2000:C.binary(bbs(0x3000)+[END]),0x3000:C.binary([END])},max_depth=2,nesting_mode='nested')
        self.reject('BATCH_DEPTH_LIMIT',p.parse,0x1000)
    def test_predicated_bbs_refused(self):self.reject('INDIRECT_CONTROL_FLOW',C.Parser(self.src,{0x1000:C.binary(bbs(0x1000,extra=1<<15))}).parse,0x1000)
    def test_offset_bbs_refused(self):self.reject('INDIRECT_CONTROL_FLOW',C.Parser(self.src,{0x1000:C.binary(bbs(0x1000,extra=1<<16))}).parse,0x1000)
    def test_missing_nested_segment(self):self.reject('RESOURCE_DATA_MISSING',C.Parser(self.src,{0x1000:C.binary(bbs(0x2000)+[END])}).parse,0x1000)
    def test_mid_packet_target(self):
        p=C.Parser(self.src,{0x1000:C.binary(bbs(0x2004)+[END]),0x2000:C.binary([0x11000001,0,0,END])})
        self.reject('MID_PACKET_TARGET',p.parse,0x1000)
    def test_alias_segment_refused(self):self.reject('SEGMENT_ALIAS',C.Parser,self.src,{0x1000:C.binary([0,END]),0x1004:C.binary([END])})
    def test_packet_bound(self):self.reject('PACKET_LIMIT',C.Parser(self.src,{0x1000:C.binary([0,END])},max_packets=1).parse,0x1000)
    def test_variable_growth_and_explicit_relocation(self):
        seg={0x1000:C.binary([0]+bbs(0x2000)+[END]),0x2000:C.binary([0,END])}
        before=copy.deepcopy(seg)
        r=C.strict_shadow(seg,0x1000,{0x1000:0x100000,0x2000:0x200000},{'MI_NOOP':lambda p:C.binary([0,0])},target_nesting_mode='legacy')
        self.assertEqual(seg,before)
        self.assertEqual(r['mapping'][0x1004],0x100008)
        self.assertEqual(r['relocations'][0]['new_target'],0x200000)
        self.assertEqual(r['layout'][0]['target_length'],8)
        self.assertEqual(r['decoded_packets'],7)
    def test_cross_page_growth(self):
        seg={0x1000:C.binary([0]*1023+[END])}
        r=C.strict_shadow(seg,0x1000,{0x1000:0x100000},{'MI_NOOP':lambda p:C.binary([0,0])})
        self.assertGreater(len(r['segments'][0x100000]),4096)
    def test_target_alias_refused(self):
        seg={0x1000:C.binary(bbs(0x2000)+[END]),0x2000:C.binary([END])}
        self.reject('TARGET_SEGMENT_ALIAS',C.strict_shadow,seg,0x1000,{0x1000:0x100000,0x2000:0x100000})
    def test_unknown_resource_reference_no_partial_output(self):
        seg={0x1000:C.binary([0x61010014]+[0]*21+[END])}
        self.reject('UNKNOWN_ADDRESS_REFERENCE',C.strict_shadow,seg,0x1000,{0x1000:0x100000},{'STATE_BASE_ADDRESS':lambda p:C.binary(p['raw'])})
    def test_unverified_packet_no_output(self):
        seg={0x1000:C.binary([0x69040000,END])}
        self.reject('TARGET_FORMAT_UNVERIFIED',C.strict_shadow,seg,0x1000,{0x1000:0x100000})
    def test_schema_validation_detects_corruption(self):
        d={'schema':1,'mesa_commit':C.PIN,'commands':[{'name':'A','gen11':self.src.schema('MI_NOOP'),'gen12':None}]}
        self.assertTrue(C.validate_spec_document(d));d['commands'][0]['gen11']['fields'][0]['start']=-1
        self.reject('INVALID_SCHEMA_FIELD',C.validate_spec_document,d)

if __name__=='__main__':unittest.main()
