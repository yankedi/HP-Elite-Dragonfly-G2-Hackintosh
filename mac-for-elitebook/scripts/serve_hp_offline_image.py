#!/usr/bin/env python3
"""Serve one verified installer data image read-only, with HTTP byte ranges.

No directory listing or upload endpoint. Intended for a same-LAN Recovery
read-only hdiutil attach; does not select a disk or run an installer.
"""

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import sys
import threading

SIZE = 19922944000
SHA256 = "75f6cab00020ad6c2124579bc4641ca0f9029ad0ff23cf3d8112d01211523c92"


def byte_range(header, size):
    """Return inclusive bounds; reject unsupported/malformed/unsatisfiable ranges."""
    if header is None:
        return 0, size - 1
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
    if not match or not any(match.groups()):
        raise ValueError("Expected one byte range")
    first, last = match.groups()
    if not first:
        suffix = int(last)
        if suffix == 0:
            raise ValueError("Empty suffix")
        return max(0, size - suffix), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start > end or start >= size:
        raise ValueError("Unsatisfiable range")
    return start, end


def make_handler(image, route, size):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_HEAD(self):
            self.respond(False)

        def do_GET(self):
            self.respond(True)

        def respond(self, body):
            if self.path != route:
                self.send_error(404)
                return
            try:
                start, end = byte_range(self.headers.get("Range"), size)
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            partial = self.headers.get("Range") is not None
            self.send_response(206 if partial else 200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("ETag", '"' + SHA256 + '"')
            if partial:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            sent = 0
            if body:
                try:
                    with image.open("rb") as source:
                        source.seek(start)
                        remaining = end - start + 1
                        while remaining:
                            chunk = source.read(min(1024 * 1024, remaining))
                            if not chunk:
                                raise OSError("Source image truncated")
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                            sent += len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            print(json.dumps({"client": self.client_address[0], "method": self.command,
                              "start": start, "end": end, "bytes_sent": sent}), flush=True)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--bind", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--duration", type=int, default=3600)
    args = parser.parse_args()
    image = args.image.resolve(strict=True)
    root = Path(__file__).resolve().parents[1]
    if not image.is_relative_to(root / ".local") or not image.is_file() or image.stat().st_size != SIZE:
        parser.error("Expected verified private installer data image")
    with image.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != SHA256 or args.duration <= 0:
        parser.error("Source image digest or duration invalid")
    route = "/" + secrets.token_urlsafe(24) + "/Tahoe-26.6.2-Offline-App.hfs"
    server = ThreadingHTTPServer((args.bind, args.port), make_handler(image, route, SIZE))
    timer = threading.Timer(args.duration, server.shutdown)
    timer.daemon = True
    timer.start()
    print(json.dumps({"url": f"http://{args.bind}:{server.server_port}{route}",
                      "image": str(image.relative_to(root)), "sha256": digest,
                      "bytes": SIZE, "duration_seconds": args.duration}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        timer.cancel()
        server.server_close()


if __name__ == "__main__":
    main()
