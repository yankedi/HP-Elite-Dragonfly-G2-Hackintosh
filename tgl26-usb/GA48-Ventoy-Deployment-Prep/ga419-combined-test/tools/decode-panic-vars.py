#!/usr/bin/env python3
"""Locally decode XNU x86 packA numeric panic chunks preserved from Linux efivarfs."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('capture', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
assert not args.output.exists()
outer = json.loads(args.capture.read_text())
assert outer['returncode'] == 0
capture = json.loads(outer['stdout'])
assert capture['os'] == 'Linux'
saved = capture['firmware_saved']
assert saved['returncode'] == 0
variables = json.loads(saved['stdout'])['panic_vars']
args.output.mkdir(mode=0o700)
chunks = {}
originals = []
for row in variables:
    name = row['name']
    assert Path(name).name == name
    raw = base64.b64decode(row['base64'], validate=True)
    assert len(raw) >= 4
    (args.output / name).write_bytes(raw)
    m = re.fullmatch(r'AAPL,PanicInfo([0-9A-Fa-f]{4})-7c436110-ab2a-4bbb-a880-fe41995c9f82', name)
    # The 000K variable is retained raw; it is not part of the numeric text stream.
    if m:
        index = int(m[1], 16)
        assert index not in chunks
        assert int.from_bytes(raw[:4], 'little') == 7
        chunks[index] = raw[4:]
    originals.append({'name': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
assert chunks and sorted(chunks) == list(range(max(chunks) + 1))
# Firmware chunk boundaries are not packA boundaries (768 % 7 != 0).
packed = b''.join(chunks[i] for i in sorted(chunks))
assert len(packed) % 7 == 0
decoded = bytearray()
for offset in range(0, len(packed), 7):
    word = int.from_bytes(packed[offset:offset + 7], 'little')
    decoded.extend((word >> (7 * j)) & 127 for j in range(8))
repacked = bytearray()
for offset in range(0, len(decoded), 8):
    word = sum(decoded[offset + j] << (7 * j) for j in range(8))
    repacked.extend(word.to_bytes(7, 'little'))
assert repacked == packed
raw_text = bytes(decoded)
text = raw_text.rstrip(b'\0').decode('ascii')
assert text.startswith('panic(cpu ') and 'Kernel UUID:' in text and 'System uptime in nanoseconds:' in text
(args.output / 'numeric-chunks.packed').write_bytes(packed)
(args.output / 'panic.unpacked-with-padding.bin').write_bytes(raw_text)
(args.output / 'panic.txt').write_text(text)
report = {'status': 'NUMERIC_EFIVARS_DECODED_PACKA_ROUNDTRIP_PASS', 'source': str(args.capture),
    'source_sha256': hashlib.sha256(args.capture.read_bytes()).hexdigest(), 'linux_boot': capture['boot'],
    'chunks': sorted(chunks), 'all_original_variables': originals, 'packed_bytes': len(packed),
    'packed_sha256': hashlib.sha256(packed).hexdigest(), 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
    'signature': text.splitlines()[0], 'uptime_ns': int(re.search(r'System uptime in nanoseconds: (\d+)', text)[1]),
    'method': 'Strip 4byte Linux efivar attributes, concatenate numeric chunks, unpack LE seven-bit groups; pack back to exact original bytes.',
    'source_reference': 'Apple xnu osfmk/kern/debug.c struct pasc and packA/unpackA; retrieved source reference archived separately. Reference is not claimed exact target kernel source.',
    'scope': 'Text recovered locally from read-only firmware capture; no macOS incident JSON header or invented incident UUID.'}
(args.output / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
