"""Bounded, deterministic offline IO. Nothing here opens devices or networks."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT.parent / 'GA32-ISA-Lab'
MAX_PROGRAM_BYTES = 1 << 20
MAX_INSTRUCTIONS = 256  # bounded straight-line corpus/expansion model, per program


class Rejected(ValueError):
    def __init__(self, code: str, detail: str, offset: int | None = None):
        super().__init__(detail)
        self.code, self.detail, self.offset = code, detail, offset

    def as_dict(self):
        return {'code': self.code, 'detail': self.detail, 'offset': self.offset}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path):
    return json.loads(path.read_text())


def analysis_run() -> Path:
    """Tests follow the persisted current run unless the official runner overrides it."""
    explicit = os.environ.get('GA38_RUN')
    if explicit:
        return output_root(Path(explicit))
    state = load(ROOT / 'state.json')
    return output_root(ROOT / state['latest_integrated_run'])


def dump(path: Path, obj):
    path = output_root(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def write_bytes(path: Path, data: bytes):
    path = output_root(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def output_root(path: Path) -> Path:
    """Resolve before any write; historical directories are never output roots."""
    result = path.resolve()
    if result != ROOT and ROOT not in result.parents:
        raise Rejected('OUTPUT_SCOPE', str(result))
    return result


def frames(data: bytes) -> list[tuple[int, int]]:
    if not 0 < len(data) <= MAX_PROGRAM_BYTES:
        raise Rejected('PROGRAM_LENGTH', 'Expected 1..1MiB')
    result = []
    pc = 0
    while pc < len(data):
        if len(data) - pc < 8:
            raise Rejected('TRUNCATED_COMPACT', 'Fewer than eight bytes remain', pc)
        size = 8 if int.from_bytes(data[pc:pc + 4], 'little') & (1 << 29) else 16
        if size > len(data) - pc:
            raise Rejected('TRUNCATED_NATIVE', 'Fewer than sixteen bytes remain', pc)
        result.append((pc, size))
        if len(result) > MAX_INSTRUCTIONS:
            raise Rejected('INSTRUCTION_RESOURCE_BOUND', f'At most {MAX_INSTRUCTIONS} instructions per bounded program', pc)
        pc += size
    return result
