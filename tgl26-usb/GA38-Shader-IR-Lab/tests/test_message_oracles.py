"""Literal message-field oracles from independent RULES M1-M5 / actual table."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from common import load, analysis_run

RUN = analysis_run()
# shader, PC, descriptor, extended descriptor, SFID, mlen, emlen, rlen, header
ROWS = [
    ('PS0', 0x50, 0x02420001, 0x42, 2, 1, 1, 4, 0),
    ('PS0', 0x88, 0x08031400, 0x25, 5, 4, 0, 0, 0),
    ('PS-KP1', 0xE0, 0x04840001, 0x82, 2, 2, 2, 8, 0),
    ('PS-KP1', 0x120, 0x04840001, 0x82, 2, 2, 2, 8, 0),
    ('PS-KP1', 0x168, 0x10031000, 0x05, 5, 8, 0, 0, 0),
    ('PS-KP1', 0x1A8, 0x10031800, 0x25, 5, 8, 0, 0, 0),
    ('PS-KP2', 0x90, 0x04840001, 0x82, 2, 2, 2, 8, 0),
    ('PS-KP2', 0xC8, 0x10031000, 0x25, 5, 8, 0, 0, 0),
    ('VS', 0x100, 0x02080007, 0x206, 6, 1, 8, 0, 1),
    ('VS', 0x110, 0x02080027, 0x226, 6, 1, 8, 0, 1),
]


class ActualMessageOracles(unittest.TestCase):
    def test_all_twenty_carriers_against_literal_table(self):
        for shader, pc, desc, exdesc, sfid, mlen, emlen, rlen, hdr in ROWS:
            for side in ['source', 'candidate']:
                with self.subTest(shader=shader, pc=pc, side=side):
                    messages = load(RUN / f'ir/messages/{shader}-{side}.json')['messages']
                    m = next(m for m in messages if m['instruction_offset'] == pc)
                    self.assertEqual(m['sfid']['state'], 'KNOWN')
                    self.assertEqual(m['sfid']['value'], sfid)
                    self.assertEqual(m['descriptor']['value'], desc)
                    self.assertEqual(m['extended_descriptor']['value'], exdesc if side == 'source' else exdesc & ~0x3F)
                    self.assertEqual([m['lengths'][k]['value'] for k in ['payload0_grf', 'payload1_grf', 'response_grf']],
                                     [mlen, emlen, rlen])
                    self.assertEqual(m['header_present']['value'], hdr)
                    self.assertEqual(m['issues'], [])
                    self.assertTrue(all(r['state'] == 'UNKNOWN' and r['identity'] is None for r in m['resource_dependencies']))

    def test_message_specific_fields_against_known_contracts(self):
        for shader in ['PS0', 'PS-KP1', 'PS-KP2', 'VS']:
            for side in ['source', 'candidate']:
                for m in load(RUN / f'ir/messages/{shader}-{side}.json')['messages']:
                    f = m['descriptor_fields']
                    if m['family'] == 'SAMPLER':
                        self.assertEqual(f['binding_table_index']['value'], 1)
                        self.assertEqual(f['sampler_index']['value'], 0)
                        self.assertEqual(f['message_type']['value'], 0)
                        self.assertEqual(f['simd_mode']['value'], 1 if shader == 'PS0' else 2)
                        self.assertEqual(f['return_format']['value'], 0)
                    elif m['family'] == 'RENDER_TARGET':
                        self.assertEqual(f['binding_table_index']['value'], 0)
                        self.assertEqual(f['message_type']['value'], 12)
                        self.assertEqual(f['last_render_target']['value'], 1)
                        self.assertEqual(f['subtype_simd_control']['value'], 4 if shader == 'PS0' else 0)
                        self.assertEqual(f['slot_group']['value'], 1 if shader == 'PS-KP1' and m['instruction_offset'] == 0x1A8 else 0)
                    elif m['family'] == 'URB':
                        self.assertEqual(f['message_type']['value'], 7)
                        self.assertEqual(f['global_offset_encoded']['value'], 0 if m['instruction_offset'] == 0x100 else 2)
                        self.assertEqual(f['per_slot_offset']['value'], 0)
                        self.assertEqual(f['channel_mask_present']['value'], 0)
                    else:
                        self.fail('Real corpus message family omitted')


if __name__ == '__main__':
    unittest.main(verbosity=2)
