#!/usr/bin/env python3
"""Independent, CPU-only RGBA8Unorm expected bytes. No sRGB conversion."""
import argparse
import hashlib
import json
from pathlib import Path

PATTERNS = ('affine', 'red', 'green', 'blue', 'checker', 'rows', 'blocks64', 'alpha')
CASES = {'A': (640, 100), 'B': (642, 32), 'C': (642, 100)}


def pixel(x, y, pattern='affine'):
    if pattern in ('red', 'green', 'blue'):
        return (255 if pattern == 'red' else 0, 255 if pattern == 'green' else 0,
                255 if pattern == 'blue' else 0, 255)
    if pattern == 'checker':
        c = 255 * (((x // 8) ^ (y // 8)) & 1)
        return c, 255 - c, c, 255
    if pattern == 'rows':
        return y & 255, (y >> 8) & 255, (y * 37) & 255, 255
    if pattern == 'blocks64':
        k = x // 16
        return k & 255, y & 255, (k * 41 + y * 17) & 255, 255
    a = (x * 19 + y * 23) & 255 if pattern == 'alpha' else 255
    if pattern not in ('affine', 'alpha'):
        raise ValueError('Unknown pattern')
    return (13 * x + 29 * y) & 255, (7 * x + 11 * y) & 255, (3 * x + 17 * y) & 255, a


def generate(width, height, pattern='affine', bpr=None, padding=0):
    bpr = width * 4 if bpr is None else bpr
    if not (0 < width <= 32768 and 0 < height <= 32768 and bpr >= width * 4 and bpr * height <= 128 * 1024**2):
        raise ValueError('Invalid or oversized geometry')
    data = bytearray([padding]) * (bpr * height)
    for y in range(height):
        for x in range(width):
            i = y * bpr + x * 4
            data[i:i + 4] = bytes(pixel(x, y, pattern))
    return bytes(data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=CASES, required=True)
    p.add_argument('--pattern', choices=PATTERNS, default='affine')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    w, h = CASES[a.case]
    data = generate(w, h, a.pattern)
    with a.output.open('xb') as f:
        f.write(data)
    print(json.dumps(dict(width=w, height=h, bpr=w * 4, pattern=a.pattern,
                          format='RGBA8Unorm; RGBA byte order; linear; straight alpha; no blending',
                          sha256=hashlib.sha256(data).hexdigest())))


if __name__ == '__main__':
    main()
