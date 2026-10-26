#!/usr/bin/env python3
"""Archive public research inputs with byte hashes; never uses credentials."""
import datetime
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
import urllib.parse

root = Path(__file__).resolve().parents[1] / 'private' / 'sources'
root.mkdir(parents=True, exist_ok=True)
for name, url in json.load(sys.stdin).items():
    if '/' in name or name.startswith('.'):
        raise ValueError(name)
    target = root / name
    if target.exists() or target.with_suffix(target.suffix + '.receipt.json').exists():
        raise FileExistsError(target)
    row = {'url': url, 'captured_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'HP-peripheral-research/1.0'})
        with urllib.request.urlopen(req, timeout=45) as response:
            data = response.read(12 * 1024 * 1024 + 1)
            if len(data) > 12 * 1024 * 1024:
                raise ValueError('Source exceeds 12MiB bound')
            # Keep provenance, not temporary signed asset download credentials.
            final = urllib.parse.urlsplit(response.url)
            row.update(status=response.status, final_url=urllib.parse.urlunsplit(
                (final.scheme, final.netloc, final.path, '', '')),
                final_url_query_omitted=bool(final.query))
        target.write_bytes(data)
        row.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), file=name)
    except Exception as exc:
        row.update(error=str(exc))
    target.with_suffix(target.suffix + '.receipt.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(row))
