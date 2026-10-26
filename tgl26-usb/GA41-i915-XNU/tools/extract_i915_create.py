#!/usr/bin/env python3
"""Extract two MIT Intel functions verbatim, with source hashes and license.

This is a deliberately narrow port seam, not a whole-i915 build. The caller
supplies a real backing provider. Generated bodies must remain byte-identical.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources/linux/drivers/gpu/drm/i915/gem/i915_gem_create.c"
text = SRC.read_text()
parts = []
records = []
for start in ("static int i915_gem_publish(", "int\ni915_gem_create_ioctl("):
    a = text.index(start)
    opening = text.index("{", a)
    depth = 1
    b = opening + 1
    while depth:
        depth += (text[b] == "{") - (text[b] == "}")
        b += 1
    body = text[a:b] + "\n"
    parts.append(body)
    records.append({"function": start.split("(")[0].split()[-1],
                    "source": str(SRC.relative_to(ROOT)),
                    "first_line": text.count("\n", 0, a) + 1,
                    "sha256": hashlib.sha256(body.encode()).hexdigest(),
                    "modifications": "none; OS adapters/types supplied outside extracted bodies"})
out = ROOT / "i915-xnu/gem/upstream_create.inc"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("// SPDX-License-Identifier: MIT\n/* Copyright © 2020 Intel Corporation.\n"
               " * Verbatim function bodies from Linux v6.18, commit\n"
               " * 7d0a66e4bb9081d75c82ec4957c50034cb0ea449.\n */\n" + "\n".join(parts))
(ROOT / "sources/i915-function-reuse.json").write_text(json.dumps(records, indent=2) + "\n")
print(json.dumps(records, indent=2))
