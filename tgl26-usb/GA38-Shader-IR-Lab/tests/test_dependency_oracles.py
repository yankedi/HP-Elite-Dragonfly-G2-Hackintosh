"""Hand-enumerated footprints and graph edges, independent of region arithmetic.

Synthetic access-level units deliberately bypass decode. Literal coordinates
exercise the graph, not EU encoding or numeric semantics.
"""
from pathlib import Path
import os
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
for sub in ['tools', 'dependency']:
    sys.path.insert(0, str(ROOT / sub))
from common import load, analysis_run
from dependency_graph import build_graph

RUN = analysis_run()


def access(mode, start=None, end=None, *, state='KNOWN', file='GRF', role='UNIT', lane=0):
    return {'mode': mode, 'file': file, 'state': state, 'role': role,
            'elements': None if start is None else [{'byte_start': start, 'byte_end': end, 'lane': lane}],
            'condition': 'synthetic mask/predicate' if state != 'KNOWN' else 'all channels execute',
            'symbolic_set': 'symbolic test footprint' if start is None else None,
            'evidence': ['INDEPENDENT-LITERAL-FOOTPRINT']}


def graph(*instructions):
    nodes = [{'byte_range': [16*i, 16*(i+1)], 'raw_hex': '00'*16, 'opcode': 'synthetic',
              'register_access': {'accesses': accesses}, 'message_effects': {'is_send': send}}
             for i, (accesses, send) in enumerate(instructions)]
    return build_graph({'shader_id': 'ACCESS_MODEL', 'platform': '12p1',
                        'program_sha256': '0'*64, 'nodes': nodes})


class DependencyOracles(unittest.TestCase):
    def test_literal_partial_raw_war_waw_and_disjoint(self):
        g = graph(([access('WRITE', 32, 36)], False), ([access('READ', 34, 36)], False),
                  ([access('WRITE', 34, 38)], False), ([access('READ', 40, 44)], False))
        self.assertEqual({(e['producer_offset'], e['consumer_offset'], e['kind']) for e in g['edges']},
                         {(0, 16, 'RAW'), (0, 32, 'WAW'), (16, 32, 'WAR')})
        self.assertTrue(all(e['relation'] == 'MUST_DEPEND' for e in g['edges']))
        self.assertEqual(g['pairs'][-1]['relation'], 'INDEPENDENT_PROVEN')

    def test_masked_predicated_and_cross_lane_overlap_is_may(self):
        g = graph(([access('WRITE', 64, 68, state='CONDITIONAL', lane=0)], False),
                  ([access('READ', 64, 68, state='CONDITIONAL', lane=16)], False))
        e, = g['edges']
        self.assertEqual(e['relation'], 'MAY_DEPEND')
        self.assertEqual(e['overlap_bytes'], [{'byte_start': 64, 'byte_end': 68, 'producer_lane': 0, 'consumer_lane': 16}])

    def test_symbolic_acc_and_flag_edges_are_not_disjoint(self):
        for file in ['ACC', 'FLAG']:
            g = graph(([access('WRITE', file=file, state='UNKNOWN')], False),
                      ([access('READ', file=file, state='UNKNOWN')], False))
            self.assertEqual(g['edges'][0]['relation'], 'UNKNOWN')
            self.assertIsNone(g['edges'][0]['overlap_bytes'])

    def test_unknown_file_aliases_any_register(self):
        g = graph(([access('WRITE', file='ANY', state='UNKNOWN')], False),
                  ([access('READ', 4088, 4096)], False))
        self.assertEqual(g['edges'][0]['relation'], 'UNKNOWN')

    def test_send_consumption_response_and_payload_producer_constraints(self):
        g = graph(([access('WRITE', 0, 32)], False),
                  ([access('READ', 0, 32, role='SEND_PAYLOAD0'), access('WRITE', 160, 288, role='SEND_RESPONSE')], True),
                  ([access('WRITE', 0, 32), access('READ', 160, 164)], False))
        self.assertEqual({(e['producer_offset'], e['consumer_offset'], e['constraint']) for e in g['edges']},
                         {(0, 16, 'PAYLOAD_PRODUCER_COMPLETE_BEFORE_SEND'), (0, 32, 'REGISTER_WAW_ORDER'),
                          (16, 32, 'SEND_PAYLOAD_CONSUMED_BEFORE_OVERWRITE'), (16, 32, 'SEND_RESPONSE_COMPLETE_BEFORE_CONSUMER')})
        self.assertEqual(len(g['necessary_wait_edge_indices']), 2)
        completion, = g['message_completion']
        self.assertEqual(completion['events'], ['SUBMITTED', 'PAYLOAD_CONSUMED', 'RESPONSE_WRITTEN', 'SIDE_EFFECT_COMPLETE', 'TOKEN_RELEASED'])
        self.assertEqual(completion['eot_requirement'], 'UNKNOWN_MESSAGE_SPECIFIC_EOT_COMPLETION')

    def test_intervening_write_does_not_prove_old_reaching_value(self):
        g = graph(([access('WRITE', 0, 4)], False), ([access('WRITE', 0, 4)], False),
                  ([access('READ', 0, 4)], False))
        old = next(e for e in g['edges'] if e['producer_offset'] == 0 and e['consumer_offset'] == 32)
        latest = next(e for e in g['edges'] if e['producer_offset'] == 16 and e['consumer_offset'] == 32)
        self.assertEqual(old['relation'], 'MAY_DEPEND')
        self.assertIn('intervening write', old['reason'])
        self.assertEqual(latest['relation'], 'MUST_DEPEND')

    def test_actual_all_pairs_and_message_completion_coverage(self):
        for shader, count, messages in [('PS0', 11, 2), ('PS-KP1', 29, 4), ('PS-KP2', 15, 2), ('VS', 24, 2)]:
            for side in ['source', 'candidate']:
                g = load(RUN / f'dependency/graphs/{shader}-{side}.json')
                self.assertEqual(len(g['nodes']), count)
                self.assertEqual(len(g['pairs']), count*(count-1)//2)
                self.assertEqual(len(g['message_completion']), messages)
                for e in g['edges']:
                    self.assertTrue(e['evidence'])
                    self.assertIn(e['relation'], {'MUST_DEPEND', 'MAY_DEPEND', 'UNKNOWN'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
