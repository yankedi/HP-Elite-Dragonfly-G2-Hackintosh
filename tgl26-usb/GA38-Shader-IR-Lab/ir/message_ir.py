"""Symbolic contracts for the sampler/RT/URB messages actually in this corpus.

The EU carrier, message fields, symbolic resource identity and completion are
separate contracts. Equal DWORDs are never a complete cross-generation proof.
"""
from __future__ import annotations

from common import Rejected

SFIDS = {'smpl': 2, 'rc': 5, 'urb': 6}


def fact(value=None, state='KNOWN', rule='SEND-DESCRIPTOR', condition=None):
    return {'state': state, 'value': value, 'evidence': [rule], 'condition': condition}


def bits(value, high, low):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF or not 0 <= low <= high <= 31:
        raise Rejected('DESCRIPTOR_INTEGER_RANGE', repr((value, high, low)))
    return (value >> low) & ((1 << (high - low + 1)) - 1)


def immediate(operand):
    if operand.get('kind') != 'IM':
        return fact(None, 'UNKNOWN', 'DYNAMIC-DESCRIPTOR', 'value in address register at execution')
    try:
        value = int(operand['value'], 0)
    except (ValueError, TypeError, KeyError):
        return fact(None, 'UNKNOWN', 'OPAQUE-DESCRIPTOR')
    if not 0 <= value <= 0xFFFFFFFF:
        raise Rejected('DESCRIPTOR_INTEGER_RANGE', str(value))
    return fact(value)


def field(desc, high, low, rule):
    if desc['state'] != 'KNOWN':
        return fact(None, 'UNKNOWN', rule, 'descriptor value must be known')
    return {**fact(bits(desc['value'], high, low), rule=rule), 'descriptor_bits': [high, low]}


def contract(node):
    d = node['iga_fields']
    platform = node['platform']
    if not node['message_effects']['is_send']:
        return None
    src = d.get('srcs', [])
    if len(src) < 4:
        # Retain a contract rather than silently skip a future unsupported form.
        src = [*src, *({} for _ in range(4 - len(src)))]
    exdesc, desc = immediate(src[-2]), immediate(src[-1])
    if platform == '11':
        sfid = field(exdesc, 3, 0, 'SEND-SFID-GEN11')
    elif node['length'] == 16:
        # Native Gen12 SFID is a carrier field, independent of whether we
        # understand that functional unit's complete message semantics.
        sfid = {**fact((int.from_bytes(bytes.fromhex(node['raw_hex']), 'little') >> 92) & 15,
                       rule='SEND-SFID-GEN12'), 'instruction_bits': [95, 92]}
    else:
        sfid = fact(None, 'UNKNOWN', 'SEND-SFID-GEN12', 'compact SEND SFID extraction unmodeled')
    header = field(desc, 19, 19, 'SEND-COMMON-HEADER')
    lengths = {'payload0_grf': field(desc, 28, 25, 'SEND-COMMON-MLEN'),
               'payload1_grf': field(exdesc, 9, 6, 'SEND-EX-MLEN'),
               'response_grf': field(desc, 24, 20, 'SEND-COMMON-RLEN')}
    ranges = [{'role': a['role'], 'file': a['file'], 'state': a['state'],
               'elements': a['elements'], 'symbolic_set': a['symbolic_set']}
              for a in node['register_access']['accesses']
              if a['role'] in {'SEND_PAYLOAD0', 'SEND_PAYLOAD1', 'SEND_RESPONSE'}]
    # Access state may be conditional on the mask, but the encoded carrier range
    # itself is a decoded static shape. Preserve that distinction in comparisons.
    for a in ranges:
        if a['elements'] is not None and a['state'] == 'CONDITIONAL':
            a['state'] = 'KNOWN'
    unresolved = [{'code': 'MISSING_THREAD_PAYLOAD_ABI', 'impact': 'Payload values/dispatch ABI unproved',
                   'evidence': ['CAPTURE-DOES-NOT-CONTAIN-ABI']},
                  {'code': 'MESSAGE_COMPLETION_UNRESOLVED', 'impact': 'Token readiness is not proof of externally visible completion',
                   'evidence': ['SEND-COMPLETION']}]
    parsed = {'header_present': header}
    resources = []
    sf = sfid['value']
    if sf == 2:
        family = 'SAMPLER'
        parsed.update({'binding_table_index': field(desc, 7, 0, 'SAMPLER-BTI'),
                       'sampler_index': field(desc, 11, 8, 'SAMPLER-INDEX'),
                       'message_type': field(desc, 16, 12, 'SAMPLER-MESSAGE-TYPE'),
                       'simd_mode_low': field(desc, 18, 17, 'SAMPLER-SIMD'),
                       'simd_mode_high': field(desc, 29, 29, 'SAMPLER-SIMD'),
                       'return_format': field(desc, 30, 30, 'SAMPLER-RETURN-FORMAT')})
        parsed['simd_mode'] = fact((parsed['simd_mode_low']['value'] | (parsed['simd_mode_high']['value'] << 2))
                                   if desc['state'] == 'KNOWN' else None,
                                   'KNOWN' if desc['state'] == 'KNOWN' else 'UNKNOWN', 'SAMPLER-SIMD')
        resources = ['BINDING_TABLE', 'SURFACE_STATE', 'SAMPLER_STATE', 'SAMPLER_HEAP']
        side_effect = fact('resource read; exact footprint/visibility unknown', 'CONDITIONAL', 'SAMPLER-MESSAGE-TYPE')
    elif sf == 5:
        family = 'RENDER_TARGET'
        parsed.update({'binding_table_index': field(desc, 7, 0, 'RT-BTI'),
                       'message_control': field(desc, 13, 8, 'RT-MESSAGE-CONTROL'),
                       'message_type': field(desc, 17, 14, 'RT-MESSAGE-TYPE'),
                       'per_sample': field(desc, 13, 13, 'RT-PER-SAMPLE'),
                       'last_render_target': field(desc, 12, 12, 'RT-LAST-TARGET'),
                       'slot_group': field(desc, 11, 11, 'RT-SLOT-GROUP'),
                       'subtype_simd_control': field(desc, 10, 8, 'RT-SUBTYPE')})
        resources = ['BINDING_TABLE', 'RENDER_TARGET_SURFACE', 'RT_PAYLOAD_ABI', 'BLEND_AND_DEPTH_STATE']
        side_effect = fact('potential render-target write', 'CONDITIONAL', 'RT-MESSAGE-TYPE')
    elif sf == 6:
        family = 'URB'
        parsed.update({'message_type': field(desc, 3, 0, 'URB-OPCODE'),
                       'global_offset_encoded': field(desc, 14, 4, 'URB-GLOBAL-OFFSET'),
                       'per_slot_offset': field(desc, 17, 17, 'URB-PER-SLOT'),
                       'channel_mask_present': field(desc, 15, 15, 'URB-CHANNEL-MASK')})
        resources = ['URB_ALLOCATION', 'URB_HANDLE_IN_PAYLOAD', 'URB_ENTRY_LAYOUT', 'THREAD_PAYLOAD_ABI']
        side_effect = fact('potential URB write', 'CONDITIONAL', 'URB-OPCODE')
    else:
        family = 'UNKNOWN_MESSAGE'
        parsed['message_type'] = fact(None, 'UNKNOWN', 'UNMODELED-MESSAGE-FAMILY')
        resources = ['UNKNOWN_MESSAGE_RESOURCES']
        side_effect = fact(None, 'UNKNOWN', 'UNMODELED-MESSAGE-FAMILY')
        unresolved.append({'code': 'UNKNOWN_MESSAGE_TYPE', 'impact': 'Descriptor/SFID-specific resource and completion semantics unknown',
                           'evidence': ['UNMODELED-MESSAGE-FAMILY']})
    if desc['state'] != 'KNOWN' or exdesc['state'] != 'KNOWN':
        unresolved.append({'code': 'DYNAMIC_DESCRIPTOR', 'impact': 'Length/type/heap references may be dynamic',
                           'evidence': ['DYNAMIC-DESCRIPTOR']})
    unresolved.extend({'code': 'MISSING_' + resource, 'impact': resource + ' actual identity and contents unavailable',
                       'evidence': ['MISSING-LIVE-RESOURCE-STATE']} for resource in resources)
    issues = []
    parsed['extended_function_control'] = field(exdesc, 31, 12, 'SEND-EX-FUNCTION-CONTROL')
    if platform == '11':
        parsed['eot_in_extended_descriptor'] = field(exdesc, 5, 5, 'SEND-EOT-GEN11')
        if exdesc['state'] == 'KNOWN' and bool(bits(exdesc['value'], 5, 5)) != node['control_effects']['eot']:
            issues.append({'code': 'EOT_CARRIER_CONFLICT', 'scope': 'IGA carrier fields'})
    else:
        parsed['legacy_sfid_bits'] = field(exdesc, 3, 0, 'SEND-EX-LOW-BITS-GEN12')
        parsed['legacy_eot_bit'] = field(exdesc, 5, 5, 'SEND-EOT-GEN12')
        unresolved.append({'code': 'GEN12_EXDESC_SPEC_CONFLICT',
                           'impact': 'IGA requires legacy SFID/EOT bits clear; pinned PRM TS_EOT/RC structures contain incompatible descriptions',
                           'evidence': ['SEND-GENERATION-CONTRACT', 'EOT-MESSAGE-SPECIFIC-COMPLETION']})
    if lengths['response_grf']['state'] == 'KNOWN' and lengths['response_grf']['value'] > 16:
        issues.append({'code': 'RESPONSE_LENGTH_INVALID', 'value': lengths['response_grf']['value'], 'rule': 'SEND-COMMON-RLEN'})
    if d.get('dst', {}).get('reg', {}).get('rn') == 'null' and lengths['response_grf']['state'] == 'KNOWN' and lengths['response_grf']['value']:
        issues.append({'code': 'NULL_DEST_NONZERO_RESPONSE', 'rule': 'SEND-COMMON-RLEN'})
    for key, operand, key_in_operand in [('payload0_grf', src[0], 'alen'), ('payload1_grf', src[1], 'len'),
                                         ('response_grf', d.get('dst', {}), 'len')]:
        decoded_length = operand.get(key_in_operand)
        if lengths[key]['state'] == 'KNOWN' and decoded_length is not None and lengths[key]['value'] != decoded_length:
            issues.append({'code': 'MESSAGE_LENGTH_CARRIER_MISMATCH', 'field': key,
                           'descriptor_length': lengths[key]['value'], 'carrier_length': decoded_length})
    return {'schema_version': 1, 'shader_id': node['shader_id'], 'platform': platform,
            'instruction_offset': node['byte_range'][0], 'raw_hex': node['raw_hex'],
            'opcode_form': d['op'], 'sfid': sfid, 'family': family,
            'descriptor': desc, 'extended_descriptor': exdesc,
            'descriptor_fields': parsed, 'lengths': lengths,
            'carrier_register_ranges': ranges, 'payload_sources': src[:2], 'response_destination': d.get('dst'),
            'execution_size': d['es'], 'channel_offset': d.get('eo', 0),
            'header_present': header, 'eot': node['control_effects']['eot'],
            'message_type': parsed['message_type'],
            'potential_external_side_effect': side_effect,
            'thread_payload_dependencies': fact('symbolic dispatch/header/payload contract', 'UNKNOWN', 'MISSING_THREAD_PAYLOAD_ABI'),
            'resource_dependencies': [dict(resource=x, state='UNKNOWN', identity=None) for x in resources],
            'completion_semantics': {k: fact(None, 'UNKNOWN', 'SEND-COMPLETION') for k in
                ['payload_consumed', 'response_written', 'side_effect_visible', 'token_released']},
            'eot_semantics': fact(None, 'UNKNOWN', 'EOT-MESSAGE-SPECIFIC-COMPLETION'),
            'swsb': {'regDist': d.get('regDist'), 'sbid': d.get('sbid')},
            'carrier_encoding': 'IGA_DECODED_LEGAL',
            'message_content_semantics': 'UNKNOWN', 'issues': issues, 'unresolved_fields': unresolved,
            'evidence': ['IGA-JSON', 'SEND-GENERATION-CONTRACT'], 'hardware_validated': False}


def build_messages(program):
    return {'schema_version': 1, 'shader_id': program['shader_id'], 'platform': program['platform'],
            'program_sha256': program['program_sha256'],
            'messages': [c for n in program['nodes'] if (c := contract(n)) is not None],
            'hardware_validated': False}
