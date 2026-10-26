"""Independent-audit counterexamples, plus explicit nesting-mode positives."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import command_stream as C
END=0x05000000
def bbs(t):return [0x18c00101,t&0xffffffff,t>>32]

class AuditRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.src=C.Model('gen11');cls.dst=C.Model('gen12')
    def rejects(self,code,fn,*a,**kw):
        with self.assertRaises(C.Rejected) as e:fn(*a,**kw)
        self.assertEqual(e.exception.code,code)
    def chain(self):
        return {0x1000:C.binary(bbs(0x2000)+[END]),0x2000:C.binary(bbs(0x3000)+[0,END]),0x3000:C.binary([END])}
    def test_A01_gen11_second_level_chains(self):
        t=C.Parser(self.src,self.chain()).parse(0x1000)
        self.assertEqual([p['source_va'] for p in t],[0x1000,0x2000,0x3000,0x100c])
    def test_A01_legacy_cycle_not_depth_growth(self):
        seg={0x1000:C.binary(bbs(0x2000)+[END]),0x2000:C.binary(bbs(0x2000)+[END])}
        self.rejects('BATCH_LOOP',C.Parser(self.src,seg,max_depth=3).parse,0x1000)
    def test_A01_tgl_mode_unknown_refused(self):
        self.rejects('BATCH_MODE_UNRESOLVED',C.strict_shadow,self.chain(),0x1000,{k:k*256 for k in self.chain()})
    def test_A01_known_nested_mode_three_levels(self):
        t=C.Parser(self.dst,self.chain(),nesting_mode='nested').parse(0x1000)
        self.assertEqual([p['source_va'] for p in t],[0x1000,0x2000,0x3000,0x200c,0x2010,0x100c])
    def test_A01_target_mode_semantics_mismatch(self):
        # Source second-level chains never emit the dead middle segment's return path.
        self.rejects('RESOURCE_DATA_MISSING',C.strict_shadow,self.chain(),0x1000,{k:k*256 for k in self.chain()},target_nesting_mode='nested')
    def test_A01_nonfirst_entry_requires_external_return_context(self):
        self.rejects('INITIAL_BATCH_LEVEL_UNRESOLVED',C.Parser,self.src,{0x1000:C.binary([END])},initial_level=2)
    def test_A02_wrong_fallthrough_destination_refused(self):
        seg={0x1000:C.binary(bbs(0x3000)+[0]*1021),0x2000:C.binary([END]),0x3000:C.binary([END])}
        self.rejects('CONTROL_FLOW_MAPPING_MISMATCH',C.strict_shadow,seg,0x1000,{0x1000:0x100000,0x2000:0x200000,0x3000:0x101000},target_nesting_mode='legacy')
    def test_A02_preserved_crosssegment_fallthrough(self):
        seg={0x1000:C.binary(bbs(0x3000)+[0]*1021),0x2000:C.binary([END]),0x3000:C.binary([END])}
        r=C.strict_shadow(seg,0x1000,{0x1000:0x100000,0x2000:0x101000,0x3000:0x200000},target_nesting_mode='legacy')
        self.assertTrue(r['control_flow_occurrences_verified'])
    def test_A03_payload_entry_rejected_in_parser_and_shadow(self):
        seg={0x1000:C.binary([0x11000001,0,END])}
        self.rejects('MID_PACKET_TARGET',C.Parser(self.src,seg).parse,0x1008)
        self.rejects('MID_PACKET_TARGET',C.strict_shadow,seg,0x1008,{0x1000:0x100000})
    def test_A04_conditional_termination_unresolved(self):
        seg={0x1000:C.binary([0x1b200002,0,0x3000,0,0x69040300,END])}
        parser=C.Parser(self.src,seg)
        self.rejects('CONDITIONAL_CONTROL_FLOW_UNRESOLVED',parser.parse,0x1000)
        self.assertEqual(parser.state['PipelineSelect']['status'],'UNKNOWN')
    def pipeline(self,dw):
        t=C.Parser(self.src,{0x1000:C.binary(dw+[END])}).parse(0x1000)
        return t[-2]['state_after']['PipelineSelect']['fields']
    def test_A05_mask_preserves_ancillary_fields(self):
        f=self.pipeline([0x69043330,0x69040300])
        for name in ('Media Sampler DOP Clock Gate Enable','Force Media Awake'):self.assertEqual(f[name]['value'],1)
    def test_A05_ancillary_updates_without_selector_update(self):
        f=self.pipeline([0x69041310,0x69041000])
        self.assertEqual(f['Media Sampler DOP Clock Gate Enable']['value'],0)
        self.assertEqual(f['Pipeline Selection']['source_va'],0x1000)
    def test_A05_illegal_mask_and_initial_unknowns(self):
        p=self.src.decode(C.binary([0x69040101]));v=C.validate_target(p,self.dst)
        self.assertIn('ILLEGAL_PIPELINE_SELECTOR_MASK',v['issues']);self.assertFalse(v['format_checked'])
        f=self.pipeline([0x69040300]);self.assertEqual(f['Force Media Awake']['status'],'UNKNOWN')
        f=self.pipeline([0x69040300,0x69040101]);self.assertEqual(f['Pipeline Selection']['status'],'UNKNOWN')
    def test_A05_tgl_force_media_bit_reserved_despite_XML(self):
        p=self.src.decode(C.binary([0x69042320]))
        self.assertIn('RESERVED_MBZ_CONFLICT',C.validate_target(p,self.dst)['issues'])
    def test_A06_END_MBZ_rejected(self):
        self.rejects('UNPROVEN_END_ENCODING',C.strict_shadow,{0x1000:C.binary([END|2])},0x1000,{0x1000:0x100000})
    def test_A06_BBS_address_padding_rejected(self):
        seg={0x1000:C.binary(bbs(0x2001)+[END]),0x2000:C.binary([END])}
        self.rejects('BBS_ADDRESS_MBZ',C.strict_shadow,seg,0x1000,{0x1000:0x100000,0x2000:0x200000})
    def test_A07_half_group_nonconforming(self):
        p=self.src.decode(C.binary([0x11000002,0,0,0]));v=C.validate_target(p,self.dst)
        self.assertIn('TRUNCATED_GROUP_ENTRY',v['issues']);self.assertFalse(v['format_checked'])
    def test_A08_boundary_scan_work_is_bounded(self):
        seg={0x1000:C.binary(bbs(0x3000)+[END]),0x2000:C.binary([0]*1024+[END])}
        p=C.Parser(self.src,seg,max_packets=3)
        self.rejects('DECODE_WORK_LIMIT',p.parse,0x1000);self.assertEqual(p.decode_work,6)
    def test_X01_last_valid_dword_accepted(self):
        b=C.VA_END-4;t=C.Parser(self.src,{b:C.binary([END])}).parse(b)
        self.assertEqual(t[0]['source_va'],b)
        self.rejects('INTEGER_OVERFLOW',C.Parser,self.src,{b:C.binary([0,END])})
    def test_input_total_and_segment_work_limits(self):
        self.rejects('INPUT_LIMIT',C.Parser,self.src,{i*4096:C.binary([END]) for i in range(257)})

if __name__=='__main__':unittest.main()
