import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'track-a'))
import command_stream as C
import normalizer as N

class Normalization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=C.Model('gen11');cls.dst=C.Model('gen12')
        cls.blob=(ROOT/'inputs/batch.bin').read_bytes()[0x6000:0x7104]
        cls.packets=C.Parser(cls.src,{0x426fd000:cls.blob}).parse(0x426fd000)
    def null(self,**kw):
        args=dict(resource_absent=True,disabled_state=dict.fromkeys(('stencil_test','stencil_write','depth_test','depth_write','hiz','hz_operation'),True),depth_encoded=0,mocs=4,mocs_evidence='synthetic explicit',stepping_resolved=True)
        args.update(kw);return N.null_stencil(C.binary([0x78060003,0,0,0,0]),**args)
    def rejects(self,code,fn,*a,**kw):
        with self.assertRaises(C.Rejected) as e:fn(*a,**kw)
        self.assertEqual(e.exception.code,code)
    def test_null_matches_independent_upstream_pack(self):
        proof=json.loads((ROOT/'track-a/stencil-proof.json').read_text())
        b=self.null();self.assertEqual(b.hex(),proof['target']['concrete_local_example_bytes_le_hex'])
        p=self.dst.decode(b);v=C.values(p)
        self.assertEqual(p['length'],32);self.assertEqual(v['Surface Type'],7)
        self.assertEqual(v['MOCS'],4)
    def test_depth_value_copied_instead_of_assumed_zero(self):
        b=self.null(depth_encoded=17);self.assertEqual(C.values(self.dst.decode(b))['Depth'],17)
    def test_unknown_and_present_resources_refused(self):
        for v in (None,False,'true'):
            self.rejects('UNKNOWN_RESOURCE',self.null,resource_absent=v)
    def test_active_or_missing_state_refused(self):
        self.rejects('ACTIVE_OR_UNRESOLVED_DEPTH_STENCIL_STATE',self.null,disabled_state={})
    def test_present_surface_syntax_not_promoted_to_resource_proof(self):
        # Defined non-null SurfaceType2D code and nonzero MOCS fit the target
        # encoding. There is no captured layout/view/allocation proof for it.
        d=C.words(self.null());d[1]=1<<29
        p=self.dst.decode(C.binary(d));v=C.validate_target(p,self.dst)
        self.assertTrue(v['format_checked']);self.assertEqual(v['classification'],'UNKNOWN')
        self.assertIn('RESOURCE_DATA_MISSING',v['issues'])
        src=C.binary([0x78060003,1<<31,0,0,0])
        self.rejects('PRESENT_OR_UNKNOWN_STENCIL_NEEDS_RESOURCE_TRANSLATION',N.null_stencil,src,
                     resource_absent=True,disabled_state={},depth_encoded=0,mocs=4,mocs_evidence='synthetic',stepping_resolved=True)
    def test_unknown_mocs_stepping_depth_refused(self):
        self.rejects('UNVERIFIED_TARGET_MOCS',self.null,mocs=0)
        self.rejects('UNVERIFIED_TARGET_MOCS',self.null,mocs_evidence='')
        self.rejects('UNRESOLVED_DEPTH_STATE',self.null,depth_encoded=None)
        self.rejects('UNRESOLVED_STEPPING_WORKAROUND',self.null,stepping_resolved=False)
    def test_all_four_draw_candidates_and_next_boundaries(self):
        draw=[p for p in self.packets if p['name']=='3DPRIMITIVE'];self.assertEqual(len(draw),4)
        for p in draw:
            for mode,header in [('A',0x7b000808),('B',0x7b000005)]:
                out=N.draw_candidate(C.binary(p['raw']),mode);N.check_draw(out,mode,self.dst)
                self.assertEqual(C.words(out)[0],header);self.assertEqual(C.words(out)[1:],p['raw'][1:])
                self.assertEqual(len(out),p['length'])
    def test_nonzero_xp_and_indirect_not_generalized(self):
        d=[0x7b000008]+[0]*8+[1]
        self.rejects('NONZERO_INLINE_XP',N.draw_candidate,C.binary(d),'A')
        d=[0x7b000408]+[0]*9
        self.rejects('UNSUPPORTED_SOURCE_DRAW',N.draw_candidate,C.binary(d),'A')
    def test_whole_studies_lengths_mapping_and_unverified_status(self):
        original=hashlib.sha256(self.blob).hexdigest()
        for mode,count in [('A',166),('B',178)]:
            b,r=N.study_candidate(mode,self.packets)
            self.assertEqual(len(b),len(self.blob)+12);self.assertEqual(r['target_packets_contiguously_decoded'],count)
            self.assertFalse(r['gpu_executable_proven']);self.assertFalse(r['strict_shadow'])
            mapping={x['source_va']:x['target_va'] for x in r['source_target_map']}
            for p in self.packets:
                shift=12 if p['source_va']>0x426fdab0 else 0
                self.assertEqual(mapping[p['source_va']],0x50000000+p['source_va']-0x426fd000+shift)
            self.assertEqual(len(r['draws']),4)
        self.assertEqual(hashlib.sha256(self.blob).hexdigest(),original)
    def test_R01_ordinary_draw_absent_XP_is_valid_conditional_extent(self):
        p=self.dst.decode(C.binary([0x7b000005]+[0]*6));v=C.validate_target(p,self.dst)
        self.assertTrue(v['format_checked']);self.assertNotIn('TRUNCATED_TARGET_FIELD',v['issues'])
        xp=[f for f in p['fields'] if f['start']>=224]
        self.assertEqual(len(xp),3)
        self.assertTrue(all(f['status']=='ABSENT_CONDITIONAL_DEFAULT_ZERO' and f['value']==0 for f in xp))
        b,r=N.study_candidate('B',self.packets)
        draw=[p for p in r['target_validation'] if p['name']=='3DPRIMITIVE']
        self.assertEqual(len(draw),4);self.assertTrue(all(p['validation']['format_checked'] for p in draw))
    def test_R02_check_draw_rejects_wrong_opcode_mode_and_envelope(self):
        for dw,mode,code in [([0x11000005]+[0]*9,'B','INVALID_DRAW_OPCODE_OR_MODE'),
                             ([0x11000008]+[0]*9,'A','INVALID_DRAW_OPCODE_OR_MODE'),
                             ([0x11000005]+[0]*6,'bogus','UNKNOWN_DRAW_CANDIDATE'),
                             ([0x7b000808]+[0]*9+[0xdeadbeef],'A','INVALID_DRAW_ENVELOPE'),
                             ([0x7b000005]+[0]*9+[0xdeadbeef],'B','INVALID_DRAW_ENVELOPE')]:
            self.rejects(code,N.check_draw,C.binary(dw),mode,self.dst)
    def test_R03_study_base_bounds_alignment_and_overflow(self):
        for base in (-1,C.VA_END,1<<80,True):self.rejects('INVALID_STUDY_BASE',N.study_candidate,'A',self.packets,base)
        self.rejects('TARGET_ALIGNMENT',N.study_candidate,'A',self.packets,C.VA_END-4)
        self.rejects('INTEGER_OVERFLOW',N.study_candidate,'A',self.packets,C.VA_END-4096)
    def test_R04_provenance_forbids_forged_and_contradictory_input(self):
        forged=copy.deepcopy(self.packets);forged[0]['name']='MI_NOOP';forged[0]['fields']=[]
        self.rejects('STUDY_INPUT_PROVENANCE_MISMATCH',N.study_candidate,'A',forged)
        changed=bytearray(self.blob)
        p=next(p for p in self.packets if p['name']=='3DSTATE_WM_DEPTH_STENCIL')
        f=next(f for f in p['fields'] if f['name']=='Stencil Test Enable')
        raw=C.binary(C.setbits(p['raw'],f['start'],f['end'],1));off=p['source_va']-0x426fd000
        changed[off:off+len(raw)]=raw
        parsed=C.Parser(self.src,{0x426fd000:bytes(changed)}).parse(0x426fd000)
        self.rejects('STUDY_INPUT_PROVENANCE_MISMATCH',N.study_candidate,'B',parsed)

if __name__=='__main__':unittest.main()
