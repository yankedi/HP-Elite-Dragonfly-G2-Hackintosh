#!/usr/bin/env python3
"""Verify Apple XAR TOC signature, certificate chain and every package member.

Does not install, execute package scripts, or certify a bootable installer.
The Apple Root CA is pinned independently of the embedded XAR certificates.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zlib

from fetch_install_assistant import EXPECTED_BYTES, ROOT

ROOT_CERT_SHA256 = "b0b1730ecbc7ff4505142c49f1295e6eda6bcaed7e2c68c5be91b5a11001f024"
NS = "{http://www.w3.org/2000/09/xmldsig#}"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(package, apple_root, openssl, output):
    if package.stat().st_size != EXPECTED_BYTES:
        raise ValueError("Full selected package size differs")
    if sha(apple_root) != ROOT_CERT_SHA256:
        raise ValueError("Independent Apple Root CA pin differs")
    receipts = []

    def run(label, arguments, accept_failure=False):
        result = subprocess.run([str(openssl), *arguments], capture_output=True, timeout=30)
        (output / (label + ".stdout")).write_bytes(result.stdout)
        (output / (label + ".stderr")).write_bytes(result.stderr)
        receipts.append({"label": label, "command": [str(openssl), *arguments], "exit_code": result.returncode})
        if result.returncode and not accept_failure:
            raise ValueError("OpenSSL failed: " + label)
        return result.returncode

    with package.open("rb") as stream:
        magic, header, version, packed, unpacked, algorithm = struct.unpack(">4sHHQQI", stream.read(28))
        if magic != b"xar!" or version != 1 or algorithm != 1 or header != 28 or packed > 2**20 or unpacked > 8*2**20:
            raise ValueError("Unexpected selected Apple XAR header")
        stream.seek(header)
        compressed = stream.read(packed)
        toc = zlib.decompress(compressed)
        if len(toc) != unpacked:
            raise ValueError("TOC size differs")
        root = ET.fromstring(toc)
        (output / "xar-toc.xml").write_bytes(toc)
        heap = header + packed
        checksum = root.find("./toc/checksum")
        if checksum is None or checksum.attrib.get("style") != "sha1":
            raise ValueError("Unexpected XAR checksum")
        digest = hashlib.sha1(compressed).digest()
        stream.seek(heap + int(checksum.findtext("offset")))
        if stream.read(int(checksum.findtext("size"))) != digest:
            raise ValueError("XAR TOC checksum differs")
        signatures = root.findall("./toc/signature")
        if len(signatures) != 1 or signatures[0].attrib.get("style") != "RSA":
            raise ValueError("Expected one RSA signature")
        signature = signatures[0]
        stream.seek(heap + int(signature.findtext("offset")))
        signed = stream.read(int(signature.findtext("size")))
        (output / "signature.bin").write_bytes(signed)
        (output / "digest.bin").write_bytes(digest)
        certs = root.findall(".//" + NS + "X509Certificate")
        if len(certs) != 3:
            raise ValueError("Unexpected Apple update chain")
        for index, cert in enumerate(certs):
            der = output / f"cert-{index}.der"
            der.write_bytes(base64.b64decode(cert.text))
            run(f"cert-{index}", ["x509", "-inform", "DER", "-in", str(der), "-out", str(der.with_suffix(".pem"))])
        run("anchor", ["x509", "-inform", "DER", "-in", str(apple_root), "-out", str(output / "anchor.pem")])
        (output / "intermediates.pem").write_bytes(b"".join((output / f"cert-{index}.pem").read_bytes() for index in (1, 2)))
        run("chain", ["verify", "-CAfile", str(output / "anchor.pem"), "-untrusted", str(output / "intermediates.pem"), str(output / "cert-0.pem")])
        run("leaf", ["x509", "-in", str(output / "cert-0.pem"), "-pubkey", "-noout", "-out", str(output / "leaf.pub")])
        common = ["pkeyutl", "-verify", "-pubin", "-inkey", str(output / "leaf.pub"),
                  "-in", str(output / "digest.bin"), "-pkeyopt", "digest:sha1"]
        run("signature", [*common, "-sigfile", str(output / "signature.bin")])
        tampered = bytearray(signed)
        tampered[0] ^= 1
        (output / "tampered-signature.bin").write_bytes(tampered)
        if run("tampered-signature", [*common, "-sigfile", str(output / "tampered-signature.bin")], True) == 0:
            raise ValueError("Tampered RSA signature accepted")
        members = []
        for item in root.findall("./toc/file"):
            name = item.findtext("name")
            data = item.find("data")
            if data is None or item.findtext("type") != "file":
                raise ValueError("Unexpected selected package entry")
            length, size = int(data.findtext("length")), int(data.findtext("size"))
            offset = heap + int(data.findtext("offset"))
            if offset < heap or offset + length > package.stat().st_size:
                raise ValueError("XAR member bounds invalid")
            archived, extracted = data.find("archived-checksum"), data.find("extracted-checksum")
            for check in (archived, extracted):
                if check is None or check.attrib.get("style") not in ("sha1", "sha256"):
                    raise ValueError("Unsupported signed member digest")
            ah = hashlib.new(archived.attrib["style"])
            eh = hashlib.new(extracted.attrib["style"])
            encoding = data.find("encoding").attrib["style"]
            if encoding not in ("application/octet-stream", "application/x-gzip"):
                raise ValueError("Unexpected selected package compression")
            decoder = zlib.decompressobj(47) if encoding == "application/x-gzip" else None
            stream.seek(offset)
            remaining, expanded = length, 0
            while remaining:
                chunk = stream.read(min(2**20, remaining))
                if not chunk:
                    raise ValueError("Truncated member: " + name)
                ah.update(chunk)
                plain = decoder.decompress(chunk) if decoder else chunk
                eh.update(plain)
                expanded += len(plain)
                remaining -= len(chunk)
            if decoder:
                tail = decoder.flush()
                eh.update(tail)
                expanded += len(tail)
                if not decoder.eof:
                    raise ValueError("Incomplete compressed member")
            if expanded != size or ah.hexdigest() != archived.text or eh.hexdigest() != extracted.text:
                raise ValueError("Signed member checksum differs: " + name)
            members.append({"name": name, "bytes": size, "archived_bytes": length,
                            "archived_checksum": ah.hexdigest(), "extracted_checksum": eh.hexdigest(), "verified": True})
    return {"schema_version": 1, "package_sha256": sha(package), "bytes": package.stat().st_size,
            "toc_rsa_signature_verified": True, "apple_root_sha256": ROOT_CERT_SHA256,
            "certificate_chain_verified_at_current_time": True, "tampered_signature_rejected": True,
            "members": members, "openssl_sha256": sha(openssl), "commands": receipts,
            "internal_os_build_verified": False, "bootable_media_created": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default=".local/install-prep/full-installer/InstallAssistant.pkg")
    parser.add_argument("--apple-root", required=True, help="AppleIncRootCertificate.cer, DER, independently pinned")
    parser.add_argument("--openssl", required=True)
    args = parser.parse_args()
    package, anchor = [(ROOT / value).resolve(strict=True) for value in (args.package, args.apple_root)]
    if any(not p.is_relative_to(ROOT / ".local") or not p.is_file() for p in (package, anchor)):
        raise ValueError("Package and anchor must be private regular files")
    openssl = Path(args.openssl).resolve(strict=True)
    output = Path(tempfile.mkdtemp(prefix="verification-", dir=package.parent))
    report = verify(package, anchor, openssl, output)
    report["runner_sha256"] = sha(Path(__file__))
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str((output / "report.json").relative_to(ROOT)), **report}, indent=2))


if __name__ == "__main__":
    main()
