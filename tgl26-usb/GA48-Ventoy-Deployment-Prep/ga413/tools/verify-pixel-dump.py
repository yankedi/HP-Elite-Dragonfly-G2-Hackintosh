#!/usr/bin/env python3
"""Three-boundary gates, delegating full pixel/hash/expected audit to GA4.12."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ga412_pixel_verifier', ROOT / 'ga412/tools/verify-pixel-dump.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
legacy_validate = base.validate_metadata
require = base.require
STAGES = ('render', 'synchronize', 'copy')


def validate_metadata(result):
    require(result['schema'] == 'ga413-managed-rt-v1' and result['mode'] == 'staged-boundary', 'wrong boundary schema/mode')
    require(result['operation_counts'] == {'render': 1, 'synchronize': 1, 'copy': 1}, 'wrong GPU operation counts')
    commands = result['commands']
    require(len(commands) == 3, 'exactly three CBs required')
    require(len({c['id'] for c in commands}) == 3, 'duplicate CB identities')
    previous = 0
    for ordinal, (command, stage) in enumerate(zip(commands, STAGES), 1):
        require(command['stage'] == stage and command['ordinal'] == ordinal, 'CB ordinal/stage mismatch')
        require(command['created_ns'] >= previous, 'next CB created before previous wait completed')
        for key in ('source', 'target'):
            require(command['resources'][key] == result[key], 'resource changed between boundaries')
        buffer = command['resources']['readback_buffer']
        require(buffer['storage'] == 0 and buffer['length'] == 332800, 'readback allocation changed')
        # Reuse every GA4.12 geometry/command/callback/snapshot/tracer gate.
        view = dict(result, schema='ga412-managed-rt-v1', mode='legacy',
                    commands=[dict(command, stage='legacy_render_sync_copy')])
        legacy_validate(view)
        previous = command['completion_observed_ns']


base.validate_metadata = validate_metadata


def audit(directory):
    result, code = base.audit(directory)
    metadata = json.loads((directory / 'result.json').read_bytes())
    for ordinal, command in enumerate(metadata['commands'], 1):
        require(json.loads((directory / f'command-{ordinal}.json').read_bytes()) == command,
                'individual command receipt mismatch')
    result['mode'] = 'staged-boundary'
    result['commands'] = metadata['commands']
    return result, code


def main():
    if len(sys.argv) != 2:
        print('usage: verify-pixel-dump.py DIRECTORY', file=sys.stderr); return 2
    try:
        result, code = audit(Path(sys.argv[1]))
    except (ValueError, KeyError, TypeError, OSError, IndexError) as error:
        result, code = {'status': 'INVALID', 'error': str(error)}, 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
