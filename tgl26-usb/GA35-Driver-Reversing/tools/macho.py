"""Read-only, bounded little-endian Mach-O64/KC fileset inventory.

KC segment/section/symtab file offsets are collection-absolute. This reader does
not rebase, fix up, extract executable Mach-O files, or interpret runtime memory.
"""
import hashlib
import pathlib
import re
import struct
import uuid


class FormatError(ValueError):
    pass


def safe_name(name):
    if not isinstance(name,str) or not name or len(name.encode())>200:
        raise FormatError('invalid output identifier')
    out=name if re.fullmatch(r'[A-Za-z0-9_.-]+',name) and name not in ('.','..') else 'encoded-'+name.encode().hex()
    return out if len(out.encode())<=200 else 'encoded-sha256-'+hashlib.sha256(name.encode()).hexdigest()


def confined(root,relative):
    root=pathlib.Path(root).resolve()
    path=(root/relative).resolve()
    if not path.is_relative_to(root):raise FormatError('path outside research root')
    return path


def branch_kind(mnemonic):
    return mnemonic.split()[-1]


def direct_target(operand):
    return int(operand,0) if re.fullmatch(r'0x[0-9a-fA-F]+|0|[1-9][0-9]*',operand) else None


def region(data, offset, size):
    if offset < 0 or size < 0 or offset > len(data) or size > len(data)-offset:
        raise FormatError('file range out of bounds')
    return data[offset:offset+size]


def unpack(data, fmt, offset):
    return struct.unpack(fmt, region(data, offset, struct.calcsize(fmt)))


def text(data):
    return bytes(data).split(b'\0', 1)[0].decode('utf-8', 'replace')


class Image:
    def __init__(self, data, offset=0, name='collection'):
        self.data, self.offset, self.name = data, offset, name
        h = unpack(data, '<8I', offset)
        if h[0] != 0xfeedfacf or h[1] != 0x1000007:
            raise FormatError('expected little-endian x86_64 Mach-O')
        _, self.cpu, self.subcpu, self.filetype, ncmds, size, self.flags, _ = h
        if ncmds > 65536 or size > 16*1024*1024:
            raise FormatError('command budget exceeded')
        end = offset+32+size
        region(data, offset+32, size)
        self.segments, self.sections, self.entries = [], [], []
        self.uuid, self.symtab = None, None
        cursor = offset+32
        for _ in range(ncmds):
            cmd, cs = unpack(data, '<II', cursor)
            if cs < 8 or cs % 8 or cursor+cs > end:
                raise FormatError('bad load command')
            if cmd == 0x19:
                if cs < 72:
                    raise FormatError('short segment')
                v = unpack(data, '<16sQQQQiiII', cursor+8)
                seg = dict(zip(['name','vmaddr','vmsize','fileoff','filesize','maxprot','initprot','nsects','flags'], v))
                seg['name'] = text(seg['name'])
                if seg['nsects'] > 4096 or 72+seg['nsects']*80 > cs:
                    raise FormatError('bad section count')
                if seg['filesize']>seg['vmsize'] or seg['vmaddr']+seg['vmsize']>1<<64:
                    raise FormatError('segment VM/file bounds')
                region(data, seg['fileoff'], seg['filesize'])
                self.segments.append(seg)
                for i in range(seg['nsects']):
                    s = unpack(data, '<16s16sQQIIIIIIII', cursor+72+80*i)
                    sec = dict(zip(['name','segment','addr','size','offset','align','reloff','nreloc','flags','reserved1','reserved2','reserved3'], s))
                    sec['name'], sec['segment'] = text(sec['name']), text(sec['segment'])
                    delta=sec['addr']-seg['vmaddr']
                    if sec['segment']!=seg['name'] or delta<0 or delta>seg['vmsize'] or sec['size']>seg['vmsize']-delta:
                        raise FormatError('section VM/segment bounds')
                    if sec['size'] and sec['flags']&0xff not in (1,0xc,0x12):
                        if sec['offset']!=seg['fileoff']+delta or delta>seg['filesize'] or sec['size']>seg['filesize']-delta:
                            raise FormatError('section file/segment mismatch')
                        region(data,sec['offset'],sec['size'])
                    region(data,sec['reloff'],sec['nreloc']*8)
                    self.sections.append(sec)
            elif cmd == 0x1b:
                if cs < 24:
                    raise FormatError('short UUID')
                if self.uuid is not None:raise FormatError('duplicate UUID command')
                self.uuid = str(uuid.UUID(bytes=bytes(region(data,cursor+8,16)))).upper()
            elif cmd == 2:
                if cs < 24:
                    raise FormatError('short symtab')
                if self.symtab is not None:raise FormatError('duplicate symtab command')
                self.symtab = unpack(data, '<IIII', cursor+8)
            elif cmd == 0x80000035:
                if cs < 32:
                    raise FormatError('short fileset entry')
                va, fo, so, reserved = unpack(data, '<QQII', cursor+8)
                if so < 32 or so >= cs:
                    raise FormatError('bad entry name')
                raw = bytes(region(data,cursor+so,cs-so))
                if b'\0' not in raw:
                    raise FormatError('unterminated entry name')
                region(data, fo, 32)
                self.entries.append({'name':text(raw),'vmaddr':va,'fileoff':fo,'reserved':reserved})
            cursor += cs
        if cursor != end:
            raise FormatError('load-command size mismatch')

    def va_to_offset(self, va, size=1):
        if va<0 or size<=0 or va+size>1<<64:raise FormatError('invalid VA range')
        matches = [s for s in self.segments if s['vmsize'] and va<s['vmaddr']+s['vmsize'] and s['vmaddr']<va+size]
        if len(matches) != 1:
            raise FormatError('VA unmapped or ambiguous')
        s = matches[0]
        delta=va-s['vmaddr']
        if delta<0 or delta>=s['vmsize'] or size>s['vmsize']-delta or delta>=s['filesize'] or size>s['filesize']-delta:
            raise FormatError('VA not fully file-backed')
        off = s['fileoff']+va-s['vmaddr']
        region(self.data,off,size)
        return off

    def symbols(self):
        if self.symtab is None:
            return []
        off, count, stroff, strsize = self.symtab
        if count > 2_000_000 or strsize > 256*1024*1024:
            raise FormatError('symbol budget exceeded')
        region(self.data,off,count*16)
        region(self.data,stroff,strsize)
        out = []
        for i in range(count):
            idx, kind, sect, desc, value = unpack(self.data,'<IBBHQ',off+i*16)
            if idx >= strsize:
                raise FormatError('bad string index')
            start = stroff+idx
            nul = self.data.find(b'\0',start,stroff+strsize)
            if nul < 0:
                raise FormatError('unterminated symbol')
            out.append({'name':bytes(self.data[start:nul]).decode('utf8','replace'),'type':kind,
                        'section':sect,'desc':desc,'value':value})
        return out

    def code_symbols(self):
        out=[]
        for s in self.symbols():
            if s['type']&0xe!=0xe or s['type']&0xe0 or not 1<=s['section']<=len(self.sections):continue
            sec=self.sections[s['section']-1]
            if sec['name']=='__text' and sec['addr']<=s['value']<sec['addr']+sec['size']:
                out.append(s)
        return out

    def inventory(self):
        return {'name':self.name, 'header_fileoff':self.offset, 'cpu':'x86_64',
                'uuid':self.uuid,'filetype':self.filetype,'segments':self.segments,
                'sections':self.sections,'symtab':self.symtab,'entries':self.entries}
