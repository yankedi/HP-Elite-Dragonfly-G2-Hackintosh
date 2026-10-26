#!/usr/bin/env python3
"""CPU-only Gen11/12 schema, state IR, validation and fail-closed shadow layout.

XML is an encoding model, NOT a complete programming-restriction specification.
Every output distinguishes format checking from resource/execution semantics.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
MESA=ROOT.parent/'GA32-ISA-Lab/tools/mesa-eu/source'
GENXML=MESA/'src/intel/genxml'
PIN='863338275d915e867319c3690ffd3272b06303c3'
MAX_BYTES=1<<20
MAX_VA=(1<<48)-1
VA_END=1<<48
HEADERS={'Command Type','Command SubType','3D Command Opcode','3D Command Sub Opcode',
         'MI Command Opcode','Media Command Opcode','SubOpcode','Pipeline'}
UNKNOWN={'status':'UNKNOWN','reason':'UNRESOLVED_INHERITED_STATE'}

class Rejected(ValueError):
    def __init__(self,code,detail='',offset=None):
        super().__init__(detail);self.code=code;self.detail=detail;self.offset=offset
    def json(self):return {'status':'REJECTED','code':self.code,'detail':self.detail,'offset':self.offset}

def checked_add(a,b,maximum=MAX_VA):
    if not isinstance(a,int) or not isinstance(b,int) or a<0 or b<0 or a>maximum-b:
        raise Rejected('INTEGER_OVERFLOW',f'{a}+{b}')
    return a+b

def words(blob):
    if not blob or len(blob)>MAX_BYTES or len(blob)%4:raise Rejected('INVALID_LENGTH',str(len(blob)))
    return list(struct.unpack('<'+'I'*(len(blob)//4),blob))

def binary(dw):
    if any(not isinstance(x,int) or not 0<=x<=0xffffffff for x in dw):raise Rejected('DWORD_OVERFLOW')
    return struct.pack('<'+'I'*len(dw),*dw)

def bits(dw,start,end):
    if start<0 or end<start or end>=len(dw)*32:raise Rejected('TRUNCATED_FIELD',f'{start}:{end}')
    return (int.from_bytes(binary(dw),'little')>>start)&((1<<(end-start+1))-1)

def setbits(dw,start,end,value):
    if not 0<=value<1<<(end-start+1):raise Rejected('FIELD_OVERFLOW')
    total=int.from_bytes(binary(dw),'little');mask=((1<<(end-start+1))-1)<<start
    out=(total&~mask)|(value<<start)
    return words(out.to_bytes(len(dw)*4,'little'))

def field_schema(f):
    a=dict(f.attrib);a['start']=int(a['start']);a['end']=int(a['end'])
    if 'default' in a:a['default']=int(a['default'],0)
    a['values']=[dict(v.attrib) for v in f.findall('value')]
    return a

def dependencies(name):
    result=[]
    if name.startswith('3DSTATE_') or name=='3DPRIMITIVE':result.append('PipelineSelect')
    if name.startswith('3DSTATE_'):
        if any(x in name for x in ('POINTER','CONSTANT','VERTEX_BUFFER','VERTEX_ELEMENT')):result+=['heap_or_buffer_data']
        if any(x in name for x in ('VS','PS','GS','HS','DS')):result+=['InstructionBase','kernel_or_dispatch_payload']
    if name in {'3DPRIMITIVE','3DPRIMITIVE_EXTENDED'}:
        result+=['SBA','VS','PS','URB','DepthStencilHiZ','RenderTarget','binding_sampler_heaps','vertex_state']
    if name in {'3DSTATE_STENCIL_BUFFER','3DSTATE_DEPTH_BUFFER','3DSTATE_HIER_DEPTH_BUFFER'}:
        result+=['DepthStencilHiZ','surface_dimensions_view_aux']
    if name=='PIPE_CONTROL':result+=['cache_flush_order','post_sync_allocation']
    if name.startswith('MI_LOAD_REGISTER'):result+=['MMIO_register_semantics']
    return result

def encoding_coverage(fields,groups,length):
    """Unspecified XML bits remain unknown, never implicitly MBZ."""
    extent=(length or 1)*32;covered=set()
    for f in fields:covered.update(range(f['start'],f['end']+1))
    for g in groups:
        a=g['attributes'];start,count,size=int(a['start']),int(a['count']),int(a['size'])
        for i in range(count):
            for f in g['fields']:covered.update(range(start+i*size+f['start'],start+i*size+f['end']+1))
    def spans(seq):
        out=[]
        for i in sorted(seq):
            if out and out[-1][1]+1==i:out[-1][1]=i
            else:out.append([i,i])
        return out
    return {'extent_bits':extent,'xml_described_ranges':spans(covered),
            'xml_undeclared_ranges_unknown':spans(set(range(extent))-covered),
            'dynamic_group_extent':'packet-length-dependent' if any(g['attributes']['count']=='0' for g in groups) else None}

class Model:
    def __init__(self,gen):
        if gen not in {'gen11','gen12'}:raise Rejected('UNSUPPORTED_PLATFORM')
        sys.path.insert(0,str(GENXML));import intel_genxml
        xml=intel_genxml.GenXml(str(GENXML/(gen+'.xml')));xml.merge_imported();xml.filter_engines({'render'})
        self.gen=gen;self.elements={e.attrib['name']:e for e in xml.et.getroot() if 'name' in e.attrib}
        self.instructions={n:e for n,e in self.elements.items() if e.tag=='instruction'}
    def schema(self,name):
        e=self.elements.get(name)
        if e is None:return None
        fields=[field_schema(f) for f in e.findall('field')]
        if name in {'3DPRIMITIVE','3DPRIMITIVE_EXTENDED'}:
            for f in fields:
                if f['start']>=224:f['presence_condition']='header.bit11==1; absent XP defaults to zero per PRM'
        groups=[{'attributes':dict(g.attrib),'fields':[field_schema(f) for f in g.findall('field')],
                 'children_xml':__import__('xml.etree.ElementTree',fromlist=['tostring']).tostring(g,encoding='unicode')}
                for g in e.findall('group')]
        length=int(e.attrib['length']) if 'length' in e.attrib else None
        return {'name':name,'kind':e.tag,'length':length,
                'bias':int(e.attrib.get('bias',1)),'fields':fields,'groups':groups,
                'dependencies':dependencies(name),'encoding_coverage':encoding_coverage(fields,groups,length),
                'address_references':[{'name':f['name'],'start':f['start'],'end':f['end'],'kind':f['type'],
                                       'interpretation':'absolute_or_base_relative_requires_state_and_resource_proof'} for f in fields if f['type'] in {'address','offset'}],
                'programming_constraints':'PARTIAL_XML_PLUS_EXPLICIT_RULES',
                'unmodelled_reserved_and_conditional_fields':'UNKNOWN_UNLESS_EXPLICIT_IN_XML_OR_PRM_RULE'}
    def identify(self,header):
        matches=[]
        for name,e in self.instructions.items():
            fixed=0;ok=True
            for f in e.findall('field'):
                start,end=int(f.attrib['start']),int(f.attrib['end']);n=f.attrib.get('name')
                if start>=32 or n not in HEADERS or 'default' not in f.attrib:continue
                mask=(1<<(end-start+1))-1;fixed+=end-start+1
                if (header>>start)&mask != int(f.attrib['default'],0):ok=False;break
            if ok and fixed>=9:
                # Gen11 extended draw has same opcode; bit11 selects its explicit model.
                if name=='3DPRIMITIVE_EXTENDED' and not header&(1<<11):continue
                if name=='3DPRIMITIVE' and header&(1<<11) and '3DPRIMITIVE_EXTENDED' in self.instructions:continue
                matches.append((fixed,name))
        if not matches:raise Rejected('UNKNOWN_PACKET',hex(header))
        matches.sort(reverse=True);best=[n for s,n in matches if s==matches[0][0]]
        if len(best)!=1:raise Rejected('AMBIGUOUS_PACKET',repr(best))
        return self.schema(best[0])
    def decode(self,blob,offset=0):
        if offset<0 or offset%4 or offset+4>len(blob):raise Rejected('BAD_BOUNDARY',offset=offset)
        header=int.from_bytes(blob[offset:offset+4],'little');s=self.identify(header)
        length=next((f for f in s['fields'] if f['name']=='DWord Length'),None)
        n=((header>>length['start'])&((1<<(length['end']-length['start']+1))-1))+s['bias'] if length else s['length'] or s['bias']
        if n<1 or n>512:raise Rejected('INVALID_PACKET_LENGTH',str(n),offset)
        if offset+n*4>len(blob):raise Rejected('TRUNCATED_PACKET',s['name'],offset)
        if s['length'] and n<s['length']:raise Rejected('INVALID_PACKET_LENGTH',s['name'],offset)
        dw=words(blob[offset:offset+n*4]);fields=[]
        for f in s['fields']:
            x=dict(f)
            if s['name'] in {'3DPRIMITIVE','3DPRIMITIVE_EXTENDED'} and not header&(1<<11) and n==7 and f['start']>=224:
                x.update(status='ABSENT_CONDITIONAL_DEFAULT_ZERO',value=0,raw=None);fields.append(x);continue
            try:
                x['raw']=bits(dw,f['start'],f['end']);x['value']=x['raw']
                if f['type'] in {'address','offset'}:x['value']<<=f['start']%32
                x['status']='PRESENT'
            except Rejected:x.update(status='TRUNCATED_FIELD',value=None,raw=None)
            fields.append(x)
        # Preserve groups; resolve bounded dynamic element count using packet extent.
        groups=[]
        for g in s['groups']:
            a=g['attributes'];start,count,size=int(a['start']),int(a['count']),int(a['size'])
            if not size or start>n*32:groups.append({'status':'UNKNOWN_GROUP','schema':g});continue
            dynamic=count==0;count=(n*32-start)//size if dynamic else count
            if count>512:raise Rejected('GROUP_LIMIT')
            entries=[]
            for i in range(count):
                entry=[]
                for f in g['fields']:
                    x=dict(f);x['start']+=start+i*size;x['end']+=start+i*size
                    try:
                        x['raw']=bits(dw,x['start'],x['end']);x['value']=x['raw']
                        if x['type'] in {'address','offset'}:x['value']<<=x['start']%32
                        x['status']='PRESENT'
                    except Rejected:x.update(status='TRUNCATED_FIELD',value=None,raw=None)
                    if x['type'] in self.elements and self.elements[x['type']].tag=='struct':x['status']='RESOURCE_DATA_MISSING_STRUCT'
                    entry.append(x)
                entries.append(entry)
            groups.append({'status':'DECODED_BOUNDED_GROUP','count':count,'dynamic':dynamic,
                           'remainder_bits':(n*32-start)%size if dynamic else 0,'entries':entries,'schema':g})
        return {'name':s['name'],'source_offset':offset,'length':n*4,'raw':dw,'fields':fields,'groups':groups,'schema':s}

def values(packet):return {f['name']:f.get('value') for f in packet['fields']}

def all_fields(packet):
    return packet['fields']+[f for g in packet['groups'] for e in g.get('entries',[]) for f in e]

def validate_target(packet,target):
    """Not a full hardware validator; unknown constraints never silently pass."""
    name=packet['name'];s=target.schema(name);issues=[]
    if s is None:return {'classification':'UNKNOWN','issues':['TARGET_FORMAT_UNVERIFIED'],'format_checked':False}
    dw=packet['raw'];expected=s['length']
    if name in {'3DPRIMITIVE','3DPRIMITIVE_EXTENDED'}:expected=10 if dw[0]&(1<<11) else 7
    dynamic=any(int(g['attributes']['count'])==0 for g in s['groups'])
    if expected and len(dw)!=expected and not dynamic:issues.append('TARGET_LENGTH_MISMATCH')
    for f in s['fields']:
        if name in {'3DPRIMITIVE','3DPRIMITIVE_EXTENDED'} and not dw[0]&(1<<11) and len(dw)==7 and f['start']>=224:continue
        if f['end']>=len(dw)*32:issues.append('TRUNCATED_TARGET_FIELD');continue
        raw=bits(dw,f['start'],f['end'])
        if f['type']=='mbz' and raw:issues.append('RESERVED_MBZ_CONFLICT')
        if f['type']=='mbo' and raw!=(1<<(f['end']-f['start']+1))-1:issues.append('RESERVED_MBO_CONFLICT')
        if f.get('nonzero')=='true' and raw==0:
            # Pack-generator assertion is not proof of an effective hardware
            # constraint for inherited/disabled/null state. Preserve as unknown.
            issues.append('XML_NONZERO_EFFECTIVE_STATE_UNPROVEN:'+f['name'])
        if f['values'] and str(raw) not in {v['value'] for v in f['values']}:
            # Sparse enums may omit valid encodings; absence is unknown, not nonconformance.
            issues.append('ENUM_VALUE_UNVERIFIED:'+f['name'])
    try:t=target.decode(binary(dw))
    except Rejected:t=None;issues.append('TARGET_FORMAT_UNVERIFIED')
    source_signature=[(f['name'],f['start'],f['end'],f['type']) for f in packet['schema']['fields']]
    target_signature=[(f['name'],f['start'],f['end'],f['type']) for f in s['fields']]
    if source_signature!=target_signature:issues.append('FIELD_LAYOUT_OR_SEMANTICS_CHANGED')
    if any(f['type'] in {'address','offset'} for f in all_fields(packet)):issues.append('RESOURCE_DATA_MISSING')
    if s['dependencies']:issues.append('STATE_OR_PROGRAMMING_RESTRICTIONS_UNPROVEN')
    if any(g.get('remainder_bits',0) or any(f.get('status')=='TRUNCATED_FIELD' for e in g.get('entries',[]) for f in e) for g in packet['groups']):
        issues.append('TRUNCATED_GROUP_ENTRY')
    if t is not None and any(g.get('remainder_bits',0) or any(f.get('status')=='TRUNCATED_FIELD' for e in g.get('entries',[]) for f in e) for g in t['groups']):
        issues.append('TRUNCATED_GROUP_ENTRY')
    if name=='PIPELINE_SELECT':
        if (dw[0]>>8)&3 in (1,2):issues.append('ILLEGAL_PIPELINE_SELECTOR_MASK')
        if target.gen=='gen12' and dw[0]&0xa0:issues.append('RESERVED_MBZ_CONFLICT')
    if name=='MI_BATCH_BUFFER_END' and dw[0]&~0x05000001:issues.append('RESERVED_MBZ_CONFLICT')
    if name=='MI_BATCH_BUFFER_START' and (len(dw)!=3 or dw[1]&3):issues.append('RESERVED_MBZ_CONFLICT')
    if name=='3DSTATE_STENCIL_BUFFER' and target.gen=='gen12' and len(dw)>=2:
        if (dw[1]>>29)&7 not in (1,3,7):issues.append('PRM_RESERVED_STENCIL_SURFACE_TYPE')
    if any(g.get('status')!='DECODED_BOUNDED_GROUP' or any(f.get('status')!='PRESENT' for e in g.get('entries',[]) for f in e) for g in packet['groups']):
        issues.append('GROUP_SEMANTICS_UNVERIFIED')
    definite=any(i in issues for i in ['TARGET_LENGTH_MISMATCH','RESERVED_MBZ_CONFLICT','RESERVED_MBO_CONFLICT','TRUNCATED_TARGET_FIELD','TRUNCATED_GROUP_ENTRY','ILLEGAL_PIPELINE_SELECTOR_MASK','PRM_RESERVED_STENCIL_SURFACE_TYPE'])
    # Only fully defined side-effect-free no-op/end form earns this narrow label.
    simple=(name=='MI_NOOP' and dw==[0]) or (name=='MI_BATCH_BUFFER_END' and dw==[0x05000000])
    cls='EXPLICITLY_NONCONFORMING' if definite else 'VALID_TGL_PACKET_SUBSET' if simple and not issues else 'UNKNOWN'
    return {'classification':cls,'format_checked':not definite and t is not None,
            'issues':sorted(set(issues)),
            'statically_convertible':simple and not issues,
            'execution_semantics_validated':simple and not issues,
            'resource_semantics_validated':simple and not issues}

STATE_NAMES=['PipelineSelect','ContextID','InstructionBase','DynamicStateBase','SurfaceStateBase','GeneralStateBase',
             'IndirectObjectBase','BindingTableBase','SamplerState','VS','PS','DispatchEnable','URB',
             'Depth','Stencil','HiZ','RenderTarget','CacheFlush','VertexState']
BASE_FIELDS={'Instruction Base Address':'InstructionBase','Dynamic State Base Address':'DynamicStateBase',
             'Surface State Base Address':'SurfaceStateBase','General State Base Address':'GeneralStateBase',
             'Indirect Object Base Address':'IndirectObjectBase'}

class Parser:
    def __init__(self,model,segments,context=None,max_packets=4096,max_depth=3,
                 nesting_mode=None,initial_level=1,max_decode_work=None):
        self.model=model;self.segments=dict(segments);self.max_packets=max_packets;self.max_depth=max_depth
        if initial_level!=1:raise Rejected('INITIAL_BATCH_LEVEL_UNRESOLVED','only explicit first-level entry supported')
        if nesting_mode not in (None,'legacy','nested'):raise Rejected('INVALID_BATCH_MODE')
        if model.gen=='gen11' and nesting_mode=='nested':raise Rejected('UNSUPPORTED_BATCH_MODE')
        self.nesting_mode='legacy' if model.gen=='gen11' else nesting_mode
        self.max_decode_work=max_decode_work if max_decode_work is not None else max_packets*2
        self.decode_work=0;self.scan_offsets={};self.scan_boundaries={}
        if len(self.segments)>256 or sum(len(b) for b in self.segments.values())>16*MAX_BYTES:raise Rejected('INPUT_LIMIT')
        self.state={k:copy.deepcopy(UNKNOWN) for k in STATE_NAMES}
        if context is not None:self.state['ContextID']={'status':'KNOWN','value':context,'evidence':'caller_metadata_not_hardware_proof'}
        self.trace=[];self.boundaries=set();self.stack=[]
        ranges=[]
        for base,blob in self.segments.items():
            words(blob);end=checked_add(base,len(blob),VA_END)
            if base%4:raise Rejected('UNALIGNED_SEGMENT')
            if any(base<e and b<end for b,e in ranges):raise Rejected('SEGMENT_ALIAS')
            ranges.append((base,end))
    def locate(self,va):
        if va%4 or va<0 or va>MAX_VA:raise Rejected('BAD_TARGET_ADDRESS',hex(va))
        for base,blob in self.segments.items():
            if base<=va<base+len(blob):return base,blob,va-base
        raise Rejected('RESOURCE_DATA_MISSING',hex(va))
    def decode(self,blob,off):
        if self.decode_work>=self.max_decode_work:raise Rejected('DECODE_WORK_LIMIT')
        self.decode_work+=1
        return self.model.decode(blob,off)
    def check_boundary(self,va):
        base,blob,off=self.locate(va)
        boundaries=self.scan_boundaries.setdefault(base,{0});o=self.scan_offsets.get(base,0)
        while o<off:
            o+=self.decode(blob,o)['length'];boundaries.add(o)
        self.scan_offsets[base]=max(o,self.scan_offsets.get(base,0))
        if off not in boundaries:raise Rejected('MID_PACKET_TARGET',hex(va))
        return base,blob,off
    def update(self,p):
        v=values(p);name=p['name'];at=p['source_va'];events=[]
        known=lambda value:{'status':'KNOWN_PACKET_VALUE','value':value,'source_va':at,'effective_hardware_state':'UNPROVEN'}
        if name=='PIPELINE_SELECT':
            mask=v.get('Mask Bits',0);fields=self.state['PipelineSelect'].setdefault('fields',{})
            controls={'Pipeline Selection':(0,1),'Render Slice common Power Gate Enable':(2,2),
                      'Render Sampler Power Gate Enable':(3,3),'Media Sampler DOP Clock Gate Enable':(4,4),
                      'Media Sampler Power Clock Gate Disable':(6,6)}
            if self.model.gen=='gen11':controls['Force Media Awake']=(5,5)
            for field,(start,end) in controls.items():
                fieldmask=((1<<(end-start+1))-1)<<start
                if mask&fieldmask==fieldmask:fields[field]=known((p['raw'][0]&fieldmask)>>start)
                else:
                    fields.setdefault(field,copy.deepcopy(UNKNOWN))
                    events.append({'code':'UNRESOLVED_INHERITED_STATE' if fields[field]['status']=='UNKNOWN' else 'INHERITED_KNOWN_PACKET_VALUE','state':'PipelineSelect.'+field})
            if mask&3 in (1,2):
                fields['Pipeline Selection']=dict(UNKNOWN,reason='ILLEGAL_PIPELINE_SELECTOR_MASK')
                events.append({'code':'ILLEGAL_PIPELINE_SELECTOR_MASK','state':'PipelineSelect'})
            self.state['PipelineSelect']['status']='PARTIAL_PACKET_STATE' if any(f['status']!='UNKNOWN' for f in fields.values()) else 'UNKNOWN'
        if name=='STATE_BASE_ADDRESS':
            for field,key in BASE_FIELDS.items():
                modify=field+' Modify Enable'
                if v.get(modify)==1:self.state[key]=known(v[field])
                else:events.append({'code':'UNRESOLVED_INHERITED_STATE' if self.state[key]['status']=='UNKNOWN' else 'INHERITED_KNOWN_PACKET_VALUE','state':key})
        mapping={'3DSTATE_VS':'VS','3DSTATE_PS':'PS','3DSTATE_PS_EXTRA':'DispatchEnable',
                 '3DSTATE_DEPTH_BUFFER':'Depth','3DSTATE_STENCIL_BUFFER':'Stencil','3DSTATE_HIER_DEPTH_BUFFER':'HiZ',
                 'PIPE_CONTROL':'CacheFlush'}
        if name in mapping:self.state[mapping[name]]=known(v)
        if 'BINDING_TABLE' in name:self.state['BindingTableBase']=known(v);events.append({'code':'RESOURCE_DATA_MISSING','state':'binding_heap'})
        if 'SAMPLER_STATE' in name:self.state['SamplerState']=known(v);events.append({'code':'RESOURCE_DATA_MISSING','state':'sampler_heap'})
        if name.startswith('3DSTATE_URB_'):self.state['URB'].setdefault('packets',{})[name]=known(v)
        if name in {'3DSTATE_VERTEX_BUFFERS','3DSTATE_VERTEX_ELEMENTS'}:self.state['VertexState']=known({'groups':p['groups']})
        if name.startswith('3DPRIMITIVE'):
            events+=[{'code':'RESOURCE_DATA_MISSING','state':s} for s in ['RenderTarget','surface_heap','shader_semantics','thread_payload']]
        return events
    def parse(self,entry):
        va=entry;visited=set();self.check_boundary(entry)
        while True:
            if len(self.trace)>=self.max_packets:raise Rejected('PACKET_LIMIT')
            if (va,tuple(self.stack)) in visited:raise Rejected('BATCH_LOOP',hex(va))
            visited.add((va,tuple(self.stack)))
            base,blob,off=self.locate(va);p=self.decode(blob,off);p['source_va']=va;p['segment_base']=base
            p['batch_level']=1+len(self.stack);p['nesting_mode']=self.nesting_mode or 'UNKNOWN'
            if p['name']=='MI_CONDITIONAL_BATCH_BUFFER_END':raise Rejected('CONDITIONAL_CONTROL_FLOW_UNRESOLVED',offset=va)
            if len(self.stack)==2 and p['name'] not in {'MI_NOOP','MI_BATCH_BUFFER_END','MI_BATCH_BUFFER_START'}:
                raise Rejected('THIRD_LEVEL_PROGRAMMING_RESTRICTIONS_UNPROVEN',offset=va)
            self.boundaries.add(va);self.trace.append(p);p['state_events']=self.update(p)
            p['state_after']=copy.deepcopy(self.state)
            nextva=checked_add(va,p['length'],VA_END);v=values(p)
            if p['name']=='MI_BATCH_BUFFER_END':
                if p['raw']!=[0x05000000]:raise Rejected('UNPROVEN_END_ENCODING',offset=va)
                if not self.stack:break
                va=self.stack.pop();continue
            if p['name']=='MI_BATCH_BUFFER_START':
                described=0
                for f in p['schema']['fields']:
                    if f['end']<32:described|=((1<<(f['end']-f['start']+1))-1)<<f['start']
                if p['raw'][0]&~described:raise Rejected('INDIRECT_CONTROL_FLOW','unmodelled BBS control bits',va)
                if p['raw'][1]&3:raise Rejected('BBS_ADDRESS_MBZ',offset=va)
                if v.get('Predication Enable',0):raise Rejected('INDIRECT_CONTROL_FLOW','predicated BBS',va)
                if v.get('Add Offset Enable',0) or v.get('Resource Streamer Enable',0):
                    raise Rejected('INDIRECT_CONTROL_FLOW','offset/resource-streamer BBS',va)
                if v.get('Address Space Indicator')!=1:raise Rejected('ADDRESS_SPACE_UNRESOLVED','GGTT requires separate map',va)
                target=v.get('Batch Buffer Start Address')
                if target is None:raise Rejected('UNKNOWN_ADDRESS_REFERENCE',offset=va)
                # Decode target boundaries sequentially from segment start; no scan or payload jump.
                self.check_boundary(target)
                if self.nesting_mode is None:raise Rejected('BATCH_MODE_UNRESOLVED','target MI_MODE.NestedBatchBufferEnable not supplied',va)
                if v.get('Second Level Batch Buffer'):
                    if self.nesting_mode=='nested' or not self.stack:
                        if len(self.stack)+1>=min(self.max_depth,3):raise Rejected('BATCH_DEPTH_LIMIT')
                        self.stack.append(nextva)
                    # Legacy second-level BBS chains without replacing first-level return.
                elif self.stack and self.nesting_mode=='legacy':
                    raise Rejected('FIRST_LEVEL_FROM_SECOND_UNVERIFIED',offset=va)
                va=target
            else:va=nextva
        return self.trace

def strict_shadow(segments,entry,target_bases,converters=None,*,target_nesting_mode=None):
    """Two passes, recognized references only. Never publish partial bytes on failure."""
    parser=Parser(Model('gen11'),segments);trace=parser.parse(entry);converters=converters or {}
    # Unique packet nodes, not duplicate dynamic execution copies.
    unique={p['source_va']:p for p in trace};outputs={};mapping={};relocations=[];pending=[];layout=[]
    occupied=[]
    for base in sorted(segments):
        if base not in target_bases:raise Rejected('TARGET_BASE_MISSING')
        target=target_bases[base];data=bytearray()
        for va,p in sorted(unique.items()):
            if p['segment_base']!=base:continue
            if p['name'] in converters:out=converters[p['name']](copy.deepcopy(p))
            elif p['name'] in {'MI_NOOP','MI_BATCH_BUFFER_END','MI_BATCH_BUFFER_START'}:out=binary(p['raw'])
            else:raise Rejected('TARGET_FORMAT_UNVERIFIED',p['name'],va)
            words(out);newva=checked_add(target,len(data));mapping[va]=newva
            layout.append({'source_va':va,'source_segment':base,'source_offset':va-base,'source_length':p['length'],
                           'target_va':newva,'target_offset':len(data),'target_length':len(out)})
            # All other references require explicit resource identity/translation rule.
            refs=[f for f in all_fields(p) if f['type'] in {'address','offset'}]
            if p['name']!='MI_BATCH_BUFFER_START' and refs:raise Rejected('UNKNOWN_ADDRESS_REFERENCE',p['name'],va)
            if p['name'] not in {'MI_NOOP','MI_BATCH_BUFFER_END','MI_BATCH_BUFFER_START'}:
                raise Rejected('UNPROVEN_CONVERTER',p['name'],va)
            if p['name']=='MI_NOOP' and (p['raw']!=[0] or any(words(out))):
                raise Rejected('UNPROVEN_CONVERTER','only pure-zero NOOP may expand',va)
            if p['name'] in {'MI_BATCH_BUFFER_END','MI_BATCH_BUFFER_START'} and out!=binary(p['raw']):
                raise Rejected('UNPROVEN_CONVERTER','control flow may only change via typed relocation',va)
            if p['name']=='MI_BATCH_BUFFER_START':pending.append((base,len(data),p))
            data.extend(out)
            if len(data)>MAX_BYTES:raise Rejected('OUTPUT_LIMIT')
        if not data:continue
        end=checked_add(target,len(data),VA_END)
        if target%4096:raise Rejected('TARGET_ALIGNMENT')
        if any(target<e and b<end for b,e in occupied):raise Rejected('TARGET_SEGMENT_ALIAS')
        occupied.append((target,end));outputs[base]=data
    for base,offset,p in pending:
        f=next(f for f in p['fields'] if f['name']=='Batch Buffer Start Address');old=f['value']
        if old not in mapping:raise Rejected('UNRESOLVED_RELOCATION',hex(old))
        dest=mapping[old]
        if dest&((1<<(f['start']%32))-1):raise Rejected('RELOCATION_ALIGNMENT')
        d=words(bytes(outputs[base][offset:offset+p['length']]))
        d=setbits(d,f['start'],f['end'],dest>>(f['start']%32));outputs[base][offset:offset+p['length']]=binary(d)
        relocations.append({'kind':'MI_BBS_EXPLICIT_FIELD','source_va':p['source_va'],'field_start':f['start'],
                            'field_end':f['end'],'old_target':old,'new_target':dest,'target_packet_va':target_bases[base]+offset})
    target_segments={target_bases[b]:bytes(v) for b,v in outputs.items()}
    decoded=Parser(Model('gen12'),target_segments,nesting_mode=target_nesting_mode).parse(mapping[entry])
    for p in decoded:
        s=p['schema'];n=len(p['raw']);expected=s['length']
        if p['name'].startswith('3DPRIMITIVE'):expected=10 if p['raw'][0]&(1<<11) else 7
        if expected and n!=expected:raise Rejected('TARGET_LENGTH_MISMATCH')
    by_source={r['source_va']:r for r in layout};expected_trace=[]
    for p in trace:
        row=by_source[p['source_va']]
        # Only zero NOOP expansion may insert multiple packets; control packets are exact.
        expected_trace.extend(range(row['target_va'],row['target_va']+row['target_length'],4)
                              if p['name']=='MI_NOOP' else [row['target_va']])
    if [p['source_va'] for p in decoded]!=expected_trace:
        raise Rejected('CONTROL_FLOW_MAPPING_MISMATCH','mapped execution occurrences differ from target trace')
    return {'status':'VALIDATED_SUBSET','scope':'layout/control-flow only, no GPU execution',
            'target_nesting_mode':target_nesting_mode or 'UNKNOWN_NO_BBS_EXECUTED','control_flow_occurrences_verified':True,
            'mapping':mapping,'layout':layout,'relocations':relocations,'segments':target_segments,'decoded_packets':len(decoded)}

def validate_spec_document(doc):
    if not isinstance(doc,dict) or doc.get('schema')!=1 or doc.get('mesa_commit')!=PIN:
        raise Rejected('INVALID_SCHEMA_VERSION')
    names=set()
    for command in doc.get('commands',[]):
        if command['name'] in names:raise Rejected('DUPLICATE_SCHEMA_COMMAND')
        names.add(command['name'])
        for gen in ['gen11','gen12']:
            s=command[gen]
            if s is None:continue
            for f in s['fields']:
                if not isinstance(f['start'],int) or f['start']<0 or f['end']<f['start'] or f['end']>MAX_BYTES*8:
                    raise Rejected('INVALID_SCHEMA_FIELD',f['name'])
    if not names:raise Rejected('EMPTY_SCHEMA')
    return True

def main():
    old=json.loads((ROOT/'inputs/batch-decoded.json').read_text())
    names=sorted({p['name'] for p in old['per_gen']['gen11']['chains'][0]['instructions']})
    src=Model('gen11');dst=Model('gen12')
    extra=['RENDER_SURFACE_STATE','SAMPLER_STATE','BINDING_TABLE_STATE','3DPRIMITIVE_EXTENDED']
    diffs=[]
    for name in names+extra:
        a,b=src.schema(name),dst.schema(name)
        fields11={f['name']:f for f in a['fields']} if a else {}
        fields12={f['name']:f for f in b['fields']} if b else {}
        diffs.append({'name':name,'actually_in_chain':name in names,'gen11':a,'gen12':b,
                      'field_differences':[{'name':k,'gen11':fields11.get(k),'gen12':fields12.get(k)}
                                           for k in sorted(fields11.keys()|fields12.keys()) if fields11.get(k)!=fields12.get(k)]})
    referenced=set();queue=[f['type'] for d in diffs for gen in ('gen11','gen12') if d[gen]
                          for f in d[gen]['fields']+[x for g in d[gen]['groups'] for x in g['fields']]]
    structs=[]
    while queue:
        name=queue.pop()
        if name in referenced:continue
        referenced.add(name)
        a,b=src.schema(name),dst.schema(name)
        if not any(s and s['kind']=='struct' for s in (a,b)):continue
        structs.append({'name':name,'gen11':a,'gen12':b})
        queue.extend(f['type'] for s in (a,b) if s for f in s['fields']+[x for g in s['groups'] for x in g['fields']])
    document={'schema':1,'mesa_commit':PIN,'scope':'complete resolved XML fields and transitive struct schemas; PARTIAL official programming restrictions',
              'prm_constraints_file':'track-a/prm-constraints.json','commands':diffs,'referenced_structs':sorted(structs,key=lambda x:x['name']),
              'known_xml_prm_disagreement':[{'name':'PIPELINE_SELECT','gen12_bit':5,'XML':'Force Media Awake','PRM':'Reserved MBZ; validator uses PRM'}]}
    validate_spec_document(document)
    (ROOT/'track-a/spec-diff.json').write_text(json.dumps(document,indent=2)+'\n')
    blob=(ROOT/'inputs/batch.bin').read_bytes()[0x6000:0x7104]
    parser=Parser(src,{0x426fd000:blob},context=5);trace=parser.parse(0x426fd000)
    rows=[]
    for p in trace:rows.append({'offset':p['source_va']-0x426f7000,'source_va':p['source_va'],
                               'name':p['name'],'validation':validate_target(p,dst)})
    from collections import Counter
    stats=dict(Counter(r['validation']['classification'] for r in rows))
    report={'packet_count':len(rows),'classifications':stats,'packets':rows,
            'format_checked_count':sum(r['validation']['format_checked'] for r in rows),
            'static_convertible_count':sum(r['validation']['statically_convertible'] for r in rows),
            'requires_heap_count':sum('RESOURCE_DATA_MISSING' in r['validation']['issues'] for r in rows),
            'needs_inheritance_count':sum(any(x['code']=='UNRESOLVED_INHERITED_STATE' for x in p['state_events']) for p in trace),
            'complete_gpu_semantics_validated':False}
    (ROOT/'track-a/packet-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    (ROOT/'track-a/state-ir.json').write_text(json.dumps({'entry':0x426fd000,'packets':trace,
       'unknown_heap':'RESOURCE_DATA_MISSING','snapshot_atomicity':'UNPROVEN'},indent=2)+'\n')
    try:strict_shadow({0x426fd000:blob},0x426fd000,{0x426fd000:0x50000000})
    except Rejected as e:
        (ROOT/'track-a/strict-shadow-result.json').write_text(json.dumps(e.json(),indent=2)+'\n')
    print('packets',len(rows),'classifications',stats,'format_checked',report['format_checked_count'])
if __name__=='__main__':main()
