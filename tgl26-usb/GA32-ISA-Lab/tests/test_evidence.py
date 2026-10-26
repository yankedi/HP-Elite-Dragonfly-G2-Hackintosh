import hashlib
import json
from pathlib import Path
import struct
import unittest

ROOT=Path(__file__).resolve().parents[1]

class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capture=(ROOT.parent/'GA32/capture/tgl-hang-GA32b-crash-20261018.bin').read_bytes()
        cls.diff=json.loads((ROOT/'analysis/isa-diff.json').read_text())['programs']

    def test_original_receipt(self):
        self.assertEqual(len(self.capture),99648)
        self.assertEqual(hashlib.sha256(self.capture).hexdigest(),'1622ecc2aecdcc85ae45dcf86e4219338f6e41e0243b27d5e7128a9999f13333')
        for o in [0,0xc2a0]:self.assertEqual(self.capture[o:o+4],b'THAG')

    def test_extraction_byte_provenance(self):
        for n,o,size in [('batch-8pages.bin',0x2a0,32768),('shared-eu-window-2pages.bin',0x82a0,8192)]:
            self.assertEqual((ROOT/'analysis'/n).read_bytes(),self.capture[0xc2a0+o:0xc2a0+o+size])

    def test_shared_window_is_same_bytes_not_independent_pte(self):
        self.assertEqual(self.capture[0xc2a0+0x82a0:0xc2a0+0xa2a0],self.capture[0xc2a0+0xa2a0:0xc2a0+0xc2a0])

    def test_eot_bounds_not_candidate_slice(self):
        window=(ROOT/'analysis/shared-eu-window-2pages.bin').read_bytes()
        for p,e,n in [('ps',0x40,152),('vs',0x3c0,288)]:
            self.assertEqual((ROOT/f'analysis/{p}-bounded.bin').read_bytes(),window[e:e+n])
        self.assertEqual(window[0x40+152:0x100],bytes(0x100-0x40-152))

    def test_instruction_bytes_cover_proven_program(self):
        for p in self.diff:
            code=b''.join(bytes.fromhex(x['raw_hex']) for x in p['instructions'])
            self.assertEqual(code,(ROOT/f'analysis/{p["name"]}-bounded.bin').read_bytes())
            self.assertIn('EOT',p['instructions'][-1]['icl']['opts'])
            self.assertEqual(p['boundary']['branches'],[])

    def test_real_compact_semantic_counterexample(self):
        vs=next(p for p in self.diff if p['name']=='vs')['instructions'][0]
        self.assertEqual(vs['length'],8)
        self.assertEqual(vs['raw_hex'],'412b0220e0200204')
        self.assertEqual(vs['icl']['op'],vs['tgl']['op'])
        self.assertEqual((vs['icl']['es'],vs['tgl']['es']),(8,16))
        self.assertNotEqual(vs['icl']['dst'],vs['tgl']['dst'])

    def test_recorded_batch_known_headers(self):
        batch=(ROOT/'analysis/batch-8pages.bin').read_bytes()
        for o,w in [(0x69f8,0x61010014),(0x6b6c,0x7820000a),(0x6c00,0x78100007),(0x7100,0x05000000)]:
            self.assertEqual(struct.unpack_from('<I',batch,o)[0],w)

    def test_actual_ring_pc_and_missing_gen12_fault(self):
        a=json.loads((ROOT/'analysis/rcs-evidence.json').read_text())
        self.assertEqual(len(a),12)
        r=next(x for x in a if Path(x['path']).name=='Kernel_2026-10-18-040341_host.gpuRestart')
        self.assertEqual(r['head_pipe_control']['raw_dwords'],[0x7a000004,0x00104598,0x40001040,0,5,0])
        self.assertFalse(r['actual_gen12_fault_register_captured'])
        self.assertTrue(any(b['fields']['Batch Buffer Start Address']==0x426fd000 for b in r['ring_batch_starts']))

if __name__=='__main__':unittest.main()
