#!/usr/bin/env python3
"""CPU-only independent R8 input/expected generator; never loads Metal."""
import argparse
from pathlib import Path

WIDTH, HEIGHT, INPUT_ROW, OUTPUT_ROW = 257, 65, 512, 1280


def generate():
    source = bytearray(INPUT_ROW * HEIGHT)
    expected = bytearray(OUTPUT_ROW * HEIGHT)
    for row in range(HEIGHT):
        for column in range(WIDTH):
            value = (13 * column + 29 * row) % 256
            source[row * INPUT_ROW + column] = value
            offset = row * OUTPUT_ROW + column * 4
            expected[offset:offset + 4] = bytes((value, 0, 0, 255))
    return bytes(source), bytes(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=False, exist_ok=False)
    for name, data in zip(('input', 'expected'), generate()):
        with (args.directory / f'{name}.bin').open('xb') as stream:
            stream.write(data)


if __name__ == '__main__':
    main()
