"""Regression tests for concrete independent review findings and PRM discrepancies."""
import copy
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'translator'))
sys.path.insert(0,str(ROOT/'tools'))
import offline_translate as T
import batch_decode as B

class ReviewTests(unittest.TestCase):
    def test_timeout_structured(self):
        with mock.patch.object(T.subprocess,'run',side_effect=subprocess.TimeoutExpired('iga',30)):
            with self.assertRaises(T.Rejected) as cm:T.invoke([])
        self.assertEqual(cm.exception.code,'TOOL_TIMEOUT')

    def test_missing_tool_structured(self):
        with mock.patch.object(T.subprocess,'run',side_effect=FileNotFoundError('iga absent')):
            with self.assertRaises(T.Rejected) as cm:T.invoke([])
        self.assertEqual(cm.exception.code,'TOOL_UNAVAILABLE')

    def test_invalid_json_structured(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as p:
            with mock.patch.object(T,'invoke',return_value=(0,b'not-json',b'')):
                with self.assertRaises(T.Rejected) as cm:T.decode(bytes(16),'11',Path(p))
        self.assertEqual(cm.exception.code,'DECODER_FAILURE')

    def test_invalid_json_schema_structured(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as p:
            with mock.patch.object(T,'invoke',return_value=(0,b'{"elems":[{"kind":"I"}]}',b'')):
                with self.assertRaises(T.Rejected) as cm:T.decode(bytes(16),'11',Path(p))
        self.assertEqual(cm.exception.code,'DECODER_FAILURE')

    def test_missing_source_text_structured(self):
        source=(ROOT/'analysis/vs-bounded.bin').read_bytes()[8:16]
        real=T.decode
        def missing(*args,**kw):
            r=real(*args,**kw);r['lines'].clear();return r
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as p:
            with mock.patch.object(T,'decode',side_effect=missing):
                with self.assertRaises(T.Rejected) as cm:T.translate(source,Path(p))
        self.assertEqual(cm.exception.code,'SOURCE_ASSEMBLY_MISSING')

    def test_unexpected_main_swsb_rejected(self):
        source=(ROOT/'analysis/vs-bounded.bin').read_bytes()[8:16]
        real=T.decode
        def corrupt(data,platform,directory):
            r=real(data,platform,directory)
            if platform=='12p1':r['instructions'][0]['regDist']='@7'
            return r
        with tempfile.TemporaryDirectory(dir=ROOT/'tests') as p:
            with mock.patch.object(T,'decode',side_effect=corrupt):r=T.translate(source,Path(p))
        self.assertEqual(r['instructions'][0]['code'],'UNEXPECTED_MAIN_SWSB')

    def test_additional_control_flow_rejected(self):
        for op in ['join','do']:
            with self.subTest(op=op):
                with self.assertRaises(T.Rejected) as cm:T.eligibility({'op':op,'pc':0})
                self.assertEqual(cm.exception.code,'BRANCH_RELOCATION_UNSUPPORTED')

    def test_packed_group_advances_bit_not_dword(self):
        f=B.FieldDef('bit',0,0,'bool',None,{})
        g=B.GroupDef(32,3,1,[f]);d=SimpleNamespace(groups=[g])
        groups=B._decode_groups(d,struct.pack('<II',0,5),0,2)
        self.assertEqual([e[0]['value'] for e in groups[0]['entries']],[True,False,True])

    def test_target_stencil_has_incompatible_length(self):
        gen=B.GenModel('gen12',ROOT/'tools/mesa-eu/source/src/intel/genxml')
        batch=(ROOT/'analysis/batch-8pages.bin').read_bytes()
        r=B.decode_instruction(gen,batch,0x6ab0)
        self.assertEqual(r['status'],'no_valid_instruction')
        self.assertTrue(any(c.get('declared_shorter_than_xml') for c in r['candidates']))
        self.assertEqual(gen.find('3DSTATE_STENCIL_BUFFER').xml_length,8)

    def test_draw_extension_not_silently_validated(self):
        gen=B.GenModel('gen11',ROOT/'tools/mesa-eu/source/src/intel/genxml')
        batch=(ROOT/'analysis/batch-8pages.bin').read_bytes()
        r=B.decode_instruction(gen,batch,0x6df8)
        self.assertEqual(r['declared_length'],10)
        self.assertFalse(r['raw_dwords'][0]&(1<<11))
        self.assertFalse(r['length_semantics_validated'])
        self.assertEqual(r['validation_level'],'bounded_length_walk_only')

    def test_additional_enabled_ps_entry_bounds_and_translation(self):
        import json
        programs=json.loads((ROOT/'analysis/ps-variants.json').read_text())['programs']
        for name,length,units in [('ps-kp1',440,8),('ps-kp2',216,4)]:
            with self.subTest(name=name):
                p=next(x for x in programs if x['name']==name)
                self.assertEqual(p['length'],length)
                self.assertFalse(p['boundary']['branches'])
                self.assertFalse(p['boundary']['eot'].get('pred'))
                with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
                    result=T.translate((ROOT/f'analysis/{name}-bounded.bin').read_bytes(),Path(d))
                self.assertEqual(result['validated_units'],units)
                self.assertEqual(result['status'],'UNSUPPORTED')
                self.assertFalse(result['full_shader_emitted'])

if __name__=='__main__':unittest.main()
