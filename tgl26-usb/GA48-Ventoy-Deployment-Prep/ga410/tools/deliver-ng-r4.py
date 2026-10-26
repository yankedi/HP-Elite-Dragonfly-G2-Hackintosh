#!/usr/bin/env python3
"""Native-sign and publish the isolated R4 upstream CCS compatibility experiment."""
import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('native_delivery', Path(__file__).with_name('deliver-ng-r2.py'))
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)

if __name__ == '__main__':
    delivery.main(version=4)
