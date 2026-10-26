#!/usr/bin/env python3
"""Capstone5 linear function fragments with bytes, KC offset, VA, direct edges.

Function extent is the next distinct __text symbol or section end (an upper
bound, not a recovered CFG). Indirect calls are explicitly unresolved. No
invented runtime addresses, signatures, relocations or physical memory reads.
"""
import bisect
import ctypes as C
import hashlib
import json
import mmap
import pathlib
import re
import subprocess
import weakref
from macho import Image, FormatError, safe_name, confined, branch_kind, direct_target

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIB = pathlib.Path('/nix/store/w0h86x0g5kkprjdk2c2jrdr5lmngw8il-capstone-5.0.9/lib/libcapstone.so.5.0.9')
PATTERN = re.compile(r'ForceWake|Forcewake|ForceWak|Hang|hang|Restart|restart|Reset|reset|Fault|fault|Execlist|Execlists|CSB|Watchdog|watchdog|SafeReadRegister|SafeWriteRegister|PowerState|powerState|RuntimePower')


class Insn(C.Structure):
    _fields_ = [('id',C.c_uint),('address',C.c_uint64),('size',C.c_uint16),
                ('bytes',C.c_uint8*24),('mnemonic',C.c_char*32),
                ('op_str',C.c_char*160),('detail',C.c_void_p)]


class Decoder:
    def __init__(self):
        self.lib = C.CDLL(str(LIB))
        self.lib.cs_open.argtypes = [C.c_int,C.c_int,C.POINTER(C.c_size_t)]
        self.lib.cs_disasm.argtypes = [C.c_size_t,C.c_char_p,C.c_size_t,C.c_uint64,C.c_size_t,C.POINTER(C.POINTER(Insn))]
        self.lib.cs_disasm.restype = C.c_size_t
        self.lib.cs_free.argtypes = [C.POINTER(Insn),C.c_size_t]
        self.lib.cs_close.argtypes = [C.POINTER(C.c_size_t)]
        self.handle = C.c_size_t()
        if self.lib.cs_open(3,8,C.byref(self.handle)) != 0:
            raise RuntimeError('cs_open x86_64 failed')
        self._finalizer=weakref.finalize(self,self.lib.cs_close,C.byref(self.handle))

    def decode(self,data,va):
        ptr = C.POINTER(Insn)()
        count = self.lib.cs_disasm(self.handle,data,len(data),va,0,C.byref(ptr))
        try:
            return [{'va':ptr[i].address,'size':ptr[i].size,
                     'bytes':bytes(ptr[i].bytes[:ptr[i].size]).hex(),
                     'mnemonic':ptr[i].mnemonic.decode(), 'operands':ptr[i].op_str.decode()} for i in range(count)]
        finally:
            self.lib.cs_free(ptr,count)

    def close(self):
        self._finalizer()


def main():
    dest = ROOT/'analysis'/'disassembly'
    dest.mkdir(parents=True,exist_ok=True)
    decoder = Decoder()
    totals = []
    for invpath in sorted((ROOT/'analysis'/'kc').glob('*.kc.json')):
        inv = json.loads(invpath.read_text())
        source = confined(ROOT,inv['source'])
        with source.open('rb') as f, mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
            actual_digest=hashlib.sha256(data).hexdigest()
            if actual_digest!=inv['sha256']:raise FormatError('source SHA differs from inventory; refuse stale attribution')
            for item in inv['images']:
                if item['name'] == 'com.apple.kernel':
                    continue
                image = Image(data,item['header_fileoff'],item['name'])
                syms = image.symbols()
                byva = {}
                for s in image.code_symbols():
                    byva.setdefault(s['value'],[]).append(s['name'])
                textsecs = [s for s in image.sections if s['name'] == '__text']
                entries = sorted(v for v in byva if any(s['addr'] <= v < s['addr']+s['size'] for s in textsecs))
                names = [s['name'] for s in syms]
                dem = subprocess.run(['c++filt'],input='\n'.join(n[1:] if n.startswith('__Z') else n for n in names),text=True,capture_output=True,check=True).stdout.splitlines()
                demap = dict(zip(names,dem))
                functions,edges = [],[]
                for va in entries:
                    labels = byva[va]
                    if not any(PATTERN.search(n) for n in labels):
                        continue
                    section = next(s for s in textsecs if s['addr'] <= va < s['addr']+s['size'])
                    idx = bisect.bisect_right(entries,va)
                    end = min(entries[idx] if idx < len(entries) else section['addr']+section['size'],section['addr']+section['size'])
                    if end-va > 256*1024:
                        raise RuntimeError('function extent budget exceeded')
                    off = image.va_to_offset(va,end-va)
                    raw = bytes(data[off:off+end-va])
                    insns = decoder.decode(raw,va)
                    for ins in insns:
                        ins['kc_fileoff'] = off+ins['va']-va
                        ins['function_entry'] = va
                        kind=branch_kind(ins['mnemonic'])
                        if kind in ('call','jmp') or kind.startswith('j'):
                            operand = ins['operands']
                            target=direct_target(operand)
                            if target is not None:
                                ins['target_va'] = target
                                ins['target_symbols'] = byva.get(target,[])
                                edges.append({'from_function':va,'from_labels':labels,'instruction_va':ins['va'],
                                              'kind':kind,'printed_mnemonic':ins['mnemonic'],'target_va':target,'target_symbols':byva.get(target,[]),
                                              'reachability':'unproven_linear_decode'})
                            elif kind in ('call','jmp'):
                                edges.append({'from_function':va,'from_labels':labels,'instruction_va':ins['va'],
                                              'kind':kind,'printed_mnemonic':ins['mnemonic'],'unresolved_indirect':operand,
                                              'reachability':'unproven_linear_decode'})
                    record = {'symbols':labels,'demangled':[demap.get(n,n) for n in labels],
                              'entry_va':va,'extent_end_va':end,'kc_fileoff':off,
                              'source':inv['source'],'source_sha256':inv['sha256'],'image_uuid':image.uuid,
                              'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_bytes':raw.hex(),
                              'decoded_bytes':sum(i['size'] for i in insns), 'instructions':insns,
                              'decode_complete':sum(i['size'] for i in insns)==len(raw),
                              'reachability':'unproven_linear_decode','extent_kind':'symbol_bounded_fragment',
                              'extent_basis':'next distinct text symbol/section end; upper bound, not CFG proof'}
                    functions.append(record)
                prefix = confined(dest,safe_name(item['name']))
                prefix.with_suffix(prefix.suffix+'.json').write_text(json.dumps(functions,indent=2)+'\n')
                prefix.with_suffix(prefix.suffix+'.edges.json').write_text(json.dumps(edges,indent=2)+'\n')
                lines = [f"Source {inv['source']} SHA256 {inv['sha256']} UUID {image.uuid}",
                         'VA and file offsets are unslid KC coordinates. Extents are symbol upper bounds.']
                for fun in functions:
                    lines += ['', ' / '.join(fun['demangled']), f"ENTRY {fun['entry_va']:#x} FILE {fun['kc_fileoff']:#x} SHA256 {fun['raw_sha256']}"]
                    for ins in fun['instructions']:
                        target = ' ; '+','.join(ins['target_symbols']) if ins.get('target_symbols') else ''
                        lines.append(f"{ins['va']:016x} @{ins['kc_fileoff']:08x} {ins['bytes']:<32} {ins['mnemonic']:<8} {ins['operands']}{target}")
                    if fun['decoded_bytes'] != len(bytes.fromhex(fun['raw_bytes'])):
                        lines.append('WARNING: linear decoding stopped before upper bound; raw tail retained')
                prefix.with_suffix(prefix.suffix+'.txt').write_text('\n'.join(lines)+'\n')
                totals.append({'image':item['name'],'functions':len(functions),'edges':len(edges)})
            if hashlib.sha256(data).hexdigest()!=actual_digest:raise FormatError('source changed during disassembly')
    decoder.close()
    (dest/'decoder-provenance.json').write_text(json.dumps({'library':str(LIB),'sha256':hashlib.file_digest(LIB.open('rb'),'sha256').hexdigest(),
                                                          'ctypes_insn_size':C.sizeof(Insn),'totals':totals},indent=2)+'\n')
    print(json.dumps(totals,indent=2))


if __name__ == '__main__':
    main()
