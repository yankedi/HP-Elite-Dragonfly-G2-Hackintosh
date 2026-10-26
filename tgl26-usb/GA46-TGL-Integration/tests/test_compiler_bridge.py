#!/usr/bin/env python3
"""Exercise real adapter failure semantics; no mocked compiler or LLVM symbols."""
from pathlib import Path
import subprocess
import sys
r=Path(__file__).resolve().parents[1]
out=Path(sys.argv[1]);out.mkdir()
subprocess.run(['c++','-std=c++17','-g','-fsanitize=address,undefined',
                str(r/'src/compiler-adapter.cpp'),str(r/'tests/test_adapter_boundary.cpp'),
                '-o',str(out/'adapter-boundary')],check=True)
subprocess.run([str(out/'adapter-boundary')],check=True)
print('Actual adapter: null creation / three fail-stop foreign ABI entries / no SIGSEGV handler mutation PASS')
