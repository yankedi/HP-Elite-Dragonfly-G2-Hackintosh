#!/usr/bin/env python3
"""Decode XNU's packed 7-bit ASCII NVRAM panic bytes without changing NVRAM."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib


def unpack_ascii(data):
    accumulator = bits = 0
    result = bytearray()
    for byte in data:
        accumulator |= byte << bits
        bits += 8
        while bits >= 7:
            result.append(accumulator & 0x7f)
            accumulator >>= 7
            bits -= 7
    # Verify the packed bytes exactly, including the last padding bits.
    repacked = bytearray()
    accumulator2 = bits2 = 0
    for byte in result:
        accumulator2 |= byte << bits2
        bits2 += 7
        while bits2 >= 8:
            repacked.append(accumulator2 & 0xff)
            accumulator2 >>= 8
            bits2 -= 8
    if bits2:
        repacked.append((accumulator2 | (accumulator << bits2)) & 0xff)
    assert bytes(repacked) == data, 'Packed panic round trip failed'
    text = result.rstrip(b'\0').decode('ascii')
    assert text.startswith('panic(cpu ') and 'Boot args:' in text and 'Kernel UUID:' in text
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('nvram_plist')
    parser.add_argument('output_text')
    args = parser.parse_args()
    data = plistlib.loads(Path(args.nvram_plist).read_bytes())['aapl,panic-info']
    text = unpack_ascii(data)
    Path(args.output_text).write_text(text)
    print(json.dumps({'packed_bytes': len(data), 'decoded_bytes': len(text.encode()),
                      'packed_sha256': hashlib.sha256(data).hexdigest(),
                      'decoded_sha256': hashlib.sha256(text.encode()).hexdigest(),
                      'exact_pack_roundtrip': True, 'panic': text.splitlines()[0]}, indent=2))


if __name__ == '__main__':
    main()
