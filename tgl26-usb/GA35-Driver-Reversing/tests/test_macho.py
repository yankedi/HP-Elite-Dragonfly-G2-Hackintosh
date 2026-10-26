import pathlib
import struct
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from macho import FormatError, Image, region
from disassemble import Decoder


def image(commands=b'',ncmd=0,tail=b''):
    return struct.pack('<8I',0xfeedfacf,0x1000007,3,2,ncmd,len(commands),0,0)+commands+tail


class Bounds(unittest.TestCase):
    def test_header(self):
        self.assertEqual(Image(image()).cpu,0x1000007)
        for data in (b'',image()[:31],b'\0'*32):
            with self.assertRaises(FormatError): Image(data)

    def test_load_command_bounds(self):
        for cmd,n in [(struct.pack('<II',1,0),1),(struct.pack('<II',1,9),1),
                      (struct.pack('<II',1,16),1),(struct.pack('<II',1,8),0)]:
            with self.assertRaises(FormatError): Image(image(cmd,n))

    def test_budget(self):
        data=bytearray(image());struct.pack_into('<I',data,16,65537)
        with self.assertRaises(FormatError): Image(data)

    def test_file_ranges(self):
        for a,b in [(-1,1),(0,-1),(3,1),(0,4),(2,2)]:
            with self.assertRaises(FormatError): region(b'abc',a,b)
        self.assertEqual(region(b'abc',3,0),b'')

    def test_segment_mapping_halfopen_and_zero_fill(self):
        cmd=struct.pack('<II16sQQQQiiII',0x19,72,b'__TEXT',0x1000,0x100,104,4,7,5,0,0)
        im=Image(image(cmd,1,b'abcd'))
        self.assertEqual(im.va_to_offset(0x1003),107)
        for va,size in [(0xfff,1),(0x1004,1),(0x1003,2),(0x1100,1)]:
            with self.assertRaises(FormatError): im.va_to_offset(va,size)

    def test_fileset_name_offset_and_termination(self):
        for so,raw in [(31,b'abc\0'),(36,b'abc\0'),(32,b'abcd')]:
            cmd=struct.pack('<IIQQII',0x80000035,40,0x1000,72,so,0)+raw.ljust(8,b'x')
            with self.assertRaises(FormatError): Image(image(cmd,1,b'\0'*32))

    def test_symtab_index(self):
        cmd=struct.pack('<6I',2,24,56,1,72,4)
        data=image(cmd,1,struct.pack('<IBBHQ',9,0xe,1,0,0x1000)+b'abc\0')
        with self.assertRaises(FormatError): Image(data).symbols()

    def test_symtab_terminator(self):
        cmd=struct.pack('<6I',2,24,56,1,72,4)
        data=image(cmd,1,struct.pack('<IBBHQ',0,0xe,1,0,0x1000)+b'abcd')
        with self.assertRaises(FormatError): Image(data).symbols()

    def test_uuid(self):
        cmd=struct.pack('<II',0x1b,24)+bytes(range(16))
        self.assertEqual(Image(image(cmd,1)).uuid,'00010203-0405-0607-0809-0A0B0C0D0E0F')

    def test_decoder_bytes_relative_call(self):
        d=Decoder()
        try:
            raw=bytes.fromhex('554889e5e801000000c3')
            ins=d.decode(raw,0x1000)
            self.assertEqual(b''.join(bytes.fromhex(x['bytes']) for x in ins),raw)
            self.assertEqual(ins[2]['operands'],'0x100a')
            self.assertEqual(ins[2]['va'],0x1004)
        finally: d.close()


if __name__=='__main__': unittest.main()
