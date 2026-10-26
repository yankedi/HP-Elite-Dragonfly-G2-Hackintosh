#!/usr/bin/env python3
"""Configurable SSH wrapper for archived, explicitly authorized workflows."""
import argparse
import remote


def configure():
    remote.configure()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name')
    parser.add_argument('command')
    parser.add_argument('--timeout', type=int, default=60)
    parser.add_argument('--allow-error', action='store_true')
    args = parser.parse_args()
    configure()
    remote.run(args.name, args.command, timeout=args.timeout, check=not args.allow_error)
