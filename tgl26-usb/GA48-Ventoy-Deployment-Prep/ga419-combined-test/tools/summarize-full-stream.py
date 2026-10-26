#!/usr/bin/env python3
"""Verify a completed raw stream and derive a local-only failure summary."""
import argparse
import collections
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--stem', required=True)
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--directory', type=Path, default=ROOT / 'private/macos-live', help='Directory containing the preserved stream and end receipt')
args = parser.parse_args()
assert Path(args.stem).name == args.stem
assert not args.output.exists()
work = args.directory
receipt = json.loads((work / (args.stem + '.result.json')).read_text())
target = work / (args.stem + '.ndjson.gz')
counts = collections.Counter()
levels = collections.Counter()
tail = collections.deque(maxlen=60)
kernel_tail = collections.deque(maxlen=60)
patterns = {
    'kernel_panic': re.compile(r'panic\(cpu|corrupt list around element|pmap_recycle_page: page', re.I),
    'gpu_hang': re.compile(r'GPU (?:panic|restart|hang)|hang detected|IOGPU.*(?:timeout|fault)', re.I),
    'input_error': re.compile(r'(?:Voodoo|I2C|GPIO).*(?:fail|error|timeout|storm)', re.I),
    'code_signature': re.compile(r'unsupported code signature page shift|validated cs_blob', re.I),
    'video_transition': re.compile(r'HTMLVideoElement|acceleratedRenderingStateChanged|PlaybackSessionInterfaceMac::rateChanged'),
    'shutdown_transition': re.compile(r'SHUTDOWN_TIME|shutdown|shutting down|poweroff|power off|logout|ShutdownDialog', re.I),
}
selected = {key: collections.deque(maxlen=40 if key == 'shutdown_transition' else 8) for key in patterns}
selected_count = collections.Counter()
digest = hashlib.sha256()
byte_count = 0
events = 0
invalid = 0
partial = 0
first = None
last = None
latest = None
latest_mach = -1
with gzip.open(target, 'rb') as f:
    for line in f:
        digest.update(line)
        byte_count += len(line)
        if not line.endswith(b'\n'):
            partial += len(line)
        if not line.startswith(b'{'):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            invalid += 1
            continue
        events += 1
        proc = event.get('processImagePath', '')
        message = event.get('eventMessage', '')
        stamp = event.get('timestamp')
        mach = event.get('machTimestamp', -1)
        counts[proc] += 1
        levels[event.get('messageType', '')] += 1
        row = {'timestamp': stamp, 'machTimestamp': mach, 'process': proc, 'message': message}
        if first is None:
            first = row
        last = row
        if isinstance(mach, int) and mach > latest_mach:
            latest_mach = mach
            latest = row
        tail.append(row)
        if proc == '/kernel':
            kernel_tail.append(row)
        for key, regex in patterns.items():
            if regex.search(message):
                selected_count[key] += 1
                selected[key].append(row)
assert byte_count == receipt['uncompressed_bytes']
assert digest.hexdigest() == receipt['uncompressed_sha256']
with target.open('rb') as f:
    assert hashlib.file_digest(f, 'sha256').hexdigest() == receipt['compressed_sha256']
result = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'boot': receipt['boot'],
    'original': str(target), 'source_receipt': str(work / (args.stem + '.result.json')),
    'gzip_and_both_hashes_verified': True, 'uncompressed_bytes': byte_count,
    'events': events, 'invalid_JSON_lines': invalid, 'partial_bytes': partial,
    'first_event': first, 'last_received_event': last, 'latest_mach_event': latest,
    'top_processes': counts.most_common(20), 'levels': levels,
    'kernel_tail': list(kernel_tail), 'tail': list(tail),
    'selected': {key: {'count': selected_count[key], 'tail': list(rows)} for key, rows in selected.items()},
    'scope': 'Derived local summary; original unfiltered bytes retained; patterns do not exclude other causes.'}
with args.output.open('x') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({key: result[key] for key in ['boot', 'gzip_and_both_hashes_verified', 'uncompressed_bytes',
    'events', 'invalid_JSON_lines', 'partial_bytes', 'latest_mach_event', 'selected']}, ensure_ascii=False, indent=2))
