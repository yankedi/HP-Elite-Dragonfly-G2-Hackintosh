#!/usr/bin/env python3
"""Verify a completed live gzip capture and retain bounded shutdown evidence."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    args.receipt = args.receipt.resolve()
    receipt = json.loads(args.receipt.read_text())
    source = ROOT/receipt['stdout']
    raw_hash = hashlib.sha256()
    count, events, invalid = 0, 0, 0
    first, last = None, None
    levels, processes = collections.Counter(), collections.Counter()
    matches, tail = collections.deque(maxlen=300), collections.deque(maxlen=40)
    pattern = re.compile(r'shut.?down|power.?off|system.?halt|halted|logout|log.?out|reboot',re.I)
    with source.open('rb') as f:
        compressed_hash = hashlib.file_digest(f,'sha256').hexdigest()
    assert compressed_hash == receipt['compressed_sha256']
    assert source.stat().st_size == receipt['compressed_bytes']
    with gzip.open(source,'rb') as f:
        for line in f:
            raw_hash.update(line)
            count += len(line)
            if not line.startswith(b'{'):
                continue
            try:
                event = json.loads(line)
            except (ValueError,UnicodeDecodeError):
                invalid += 1
                continue
            if 'eventMessage' not in event:
                continue
            events += 1
            process = Path(event.get('processImagePath','')).name
            levels[event.get('messageType','unknown')] += 1
            processes[process] += 1
            row = {key:event.get(key) for key in ['timestamp','machTimestamp','processID','processImagePath','subsystem','category','eventMessage']}
            first = first or row
            last = row
            tail.append(row)
            if pattern.search(event.get('eventMessage','')):
                matches.append(row)
    assert count == receipt['uncompressed_bytes']
    assert raw_hash.hexdigest() == receipt['uncompressed_sha256']
    private = args.receipt.with_name(args.receipt.name.replace('.result.json','.shutdown-candidates.json'))
    candidates = {'method':'Keyword candidates only, not shutdown completion proof','matches_last_300':list(matches),'tail_last_40':list(tail)}
    if private.exists():
        assert json.loads(private.read_text()) == candidates
    else:
        with private.open('x') as f:
            json.dump(candidates,f,indent=2)
            f.write('\n')
    report = {'status':'CAPTURE_ENDED_GZIP_INTEGRITY_AND_BOTH_HASHES_PASS',
        'boot':receipt['boot'],'started_utc':receipt['started_utc'],'finished_utc':receipt['finished_utc'],
        'ssh_returncode':receipt['returncode'],'collector_error':receipt['error'],
        'compressed_bytes':source.stat().st_size,'compressed_sha256':compressed_hash,
        'uncompressed_bytes':count,'uncompressed_sha256':raw_hash.hexdigest(),
        'events':events,'invalid_JSON_lines':invalid,'message_types':dict(levels),
        'top_processes':processes.most_common(10),
        'first_event_timestamp':first['timestamp'] if first else None,
        'last_event_timestamp':last['timestamp'] if last else None,
        'first_event_machTimestamp':first['machTimestamp'] if first else None,
        'last_event_machTimestamp':last['machTimestamp'] if last else None,
        'shutdown_candidates':str(private.relative_to(ROOT)),
        'source':str(source.relative_to(ROOT)),'result_receipt':str(args.receipt.resolve().relative_to(ROOT)),
        'limit':'User intended normal shutdown; SSH255/EOF alone is neither complete orderly shutdown proof nor a new Panic. Next POST005/direct Linux RTC outcome pending.'}
    out = ROOT/'ga417/reports/RTC-LIVE-LOGGING-END.json'
    with out.open('x') as f:
        json.dump(report,f,indent=2)
        f.write('\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
