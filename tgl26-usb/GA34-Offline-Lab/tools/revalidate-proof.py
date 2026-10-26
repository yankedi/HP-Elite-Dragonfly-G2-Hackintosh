#!/usr/bin/env python3
"""Bounded independent evidence check. Writes only GA34 reference/track-a.

No main normalizer imports, hardware operations, or historical source writes.
Re-fetches official public reference material only; never uploads captures.
"""
import concurrent.futures
import datetime
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import urllib.request

REF = Path(__file__).resolve().parent
LAB = REF.parent.parent
OLD = LAB.parent / 'GA32-ISA-Lab'
MESA = OLD / 'tools/mesa-eu/source'
COMMIT = '863338275d915e867319c3690ffd3272b06303c3'
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TZ='UTC')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(p):
    data = p.read_bytes()
    return {'path': str(p.relative_to(LAB)), 'bytes': len(data), 'sha256': sha(data)}


def run(argv):
    p = subprocess.run(argv, capture_output=True, text=True, env=ENV)
    return {'argv': list(map(str, argv)), 'returncode': p.returncode,
            'stdout': p.stdout, 'stderr': p.stderr}


def fetch(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=45) as response:
            data = response.read()
            return {'url': url, 'final_url': response.url,
                    'status': response.status, 'bytes': len(data),
                    'sha256': sha(data), 'pdf_signature': data.startswith(b'%PDF-'),
                    'content_type': response.headers.get('Content-Type')}, data
    except Exception as e:
        return {'url': url, 'error': str(e)}, None


def main():
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    provenance = {
        'schema': 1, 'started_utc': started,
        'scope': 'A2/A3 independent static evidence; no GPU execution',
        'original_retrieval_logs': 'ABSENT; inherited PDF/text/source files existed on entry. No original retrieval date, redirect chain, or headers are claimed.',
        'url_method': 'Reconstructed from current official Intel platform index, metadata titles and printed document refs. Later direct PDF revalidation is distinguished from original retrieval.',
        'pdfinfo_binary': glob.glob('/nix/store/*poppler*/bin/pdfinfo')[0],
        'text_line_convention': '1-based LF lines; embedded form-feed is not a line separator',
        'mesa_commit': COMMIT,
        'official_index_tool_evidence': record(REF/'official-index-links-revalidation.json'),
        'indexes': [], 'pdfs': [], 'mesa_files': [], 'checks': [],
    }

    # Archive actual current official indexes under new names; never alter PDFs.
    for platform in ['tiger-lake', 'ice-lake']:
        url = ('https://www.intel.com/content/www/us/en/docs/graphics-for-linux/'
               'developer-reference/1-0/' + platform + '.html')
        result, data = fetch(url)
        if data:
            path = REF / (platform + '-index-revalidation.html')
            path.write_bytes(data)
            result['archive'] = record(path)
            result['attachment_ids_found'] = sorted(set(re.findall(
                rb'getcontent/(\d+)', data, re.I)))
            result['attachment_ids_found'] = [x.decode() for x in result['attachment_ids_found']]
        provenance['indexes'].append(result)

    docs = [
        ('tgl-vol2a-command-instructions', '703042', 'IHD-OS-TGL-Vol 2a-12.21'),
        ('tgl-vol2d-command-structures', '703050', 'IHD-OS-TGL-Vol 2d-12.21'),
        ('tgl-vol9-render-engine', '703063', 'IHD-OS-TGL-Vol 9-12.21'),
        ('icl-vol2a-command-instructions', '684420', 'IHD-OS-ICLLP-Vol 2a-1.20'),
        ('icl-vol2d-command-structures', '684425', 'IHD-OS-ICLLP-Vol 2d-1.20'),
        ('icl-vol9-render-engine', '684504', 'IHD-OS-ICLLP-Vol 9-1.20'),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        fetched = list(pool.map(fetch, ['https://cdrdv2.intel.com/v1/dl/getcontent/' + d[1] for d in docs]))
    for (stem, content_id, docref), (receipt, data) in zip(docs, fetched):
        p = REF / (stem + '.pdf')
        txt = REF / (stem + '.txt')
        metadata = run([provenance['pdfinfo_binary'], str(p)])
        item = dict(record(p), text=record(txt), document_ref=docref,
                    official_content_id=content_id,
                    pdf_metadata=metadata, later_official_revalidation=receipt)
        item['later_official_bytes_match_present_file'] = (data == p.read_bytes()) if data else None
        item['printed_docref_found_in_text'] = docref in txt.read_text()
        assert item['printed_docref_found_in_text'], stem
        provenance['pdfs'].append(item)

    # git show reads object database only, including paths excluded by sparse checkout.
    for p in sorted((REF / 'mesa-8633382').rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(REF / 'mesa-8633382').as_posix()
        r = subprocess.run(['git', '-C', str(MESA), 'show', COMMIT + ':' + rel], capture_output=True)
        item = dict(record(p), source_path=rel,
                    source_url='https://gitlab.freedesktop.org/mesa/mesa/-/blob/' + COMMIT + '/' + rel,
                    git_show_returncode=r.returncode,
                    git_object_bytes_match=r.returncode == 0 and r.stdout == p.read_bytes())
        assert item['git_object_bytes_match'], rel
        provenance['mesa_files'].append(item)

    # Verify immutable historical input and each relevant raw packet against batch bytes.
    frozen = LAB / 'inputs/batch-decoded.json'
    historical = OLD / 'analysis/batch-decoded.json'
    assert frozen.read_bytes() == historical.read_bytes()
    assert sha(frozen.read_bytes()) == 'ba9f3c4c3424423670250a6e14e8f61a582dc6e975875f1f5dc12af0dc503215'
    batch = (LAB / 'inputs/batch.bin').read_bytes()
    decoded = json.loads(frozen.read_text())
    chain = next(c for c in decoded['per_gen']['gen11']['chains'] if c['start'] == 0x6000)
    packets = chain['instructions']
    names = {'3DSTATE_DEPTH_BUFFER', '3DSTATE_STENCIL_BUFFER', '3DSTATE_HIER_DEPTH_BUFFER',
             '3DSTATE_WM_DEPTH_STENCIL', '3DSTATE_WM_HZ_OP', '3DSTATE_VF_SGVS',
             '3DSTATE_VF_SGVS_2', '3DPRIMITIVE'}
    checked = []
    for p in packets:
        if p.get('name') not in names:
            continue
        dw = p['raw_dwords']
        assert struct.unpack_from('<' + 'I'*len(dw), batch, p['offset']) == tuple(dw)
        checked.append({'name': p['name'], 'offset': p['offset_hex'],
                        'dwords_hex': [f'{x:08x}' for x in dw]})
    for p in packets:
        if 0x6df8 <= p['offset'] <= 0x6ffc:
            assert p.get('name') not in names - {'3DPRIMITIVE'}
    stencil = json.loads((LAB / 'track-a/stencil-proof.json').read_text())
    draw = json.loads((LAB / 'track-a/draw-proof.json').read_text())
    for words, hexbytes in [
        (stencil['target']['concrete_local_example_dwords_hex'], stencil['target']['concrete_local_example_bytes_le_hex']),
        (draw['candidate_A']['dwords_hex'], draw['candidate_A']['bytes_le_hex']),
        (draw['candidate_B']['dwords_hex'], draw['candidate_B']['bytes_le_hex']),
    ]:
        assert struct.pack('<'+'I'*len(words), *(int(x,16) for x in words)).hex() == hexbytes
    for p in checked:
        if p['name'] == '3DPRIMITIVE':
            assert p['dwords_hex'] == draw['input']['all_four_source_dwords_hex']
    provenance['checks'].append({'name': 'historical/frozen/raw-byte-and-numeric-proof-consistency',
                                 'status': 'PASS', 'historical_path': str(historical),
                                 'input': record(frozen), 'batch': record(LAB/'inputs/batch.bin'),
                                 'checked_packets': checked})

    clean = run(['git', '-C', str(MESA), 'diff', '--exit-code', COMMIT, '--',
                 'src/intel/genxml', 'src/util', 'include'])
    assert clean['returncode'] == 0, clean
    provenance['checks'].append(dict(name='generator-and-pack-header-dependencies-match-commit', **clean))

    # Actual Mesa-generated pack, compiling only a tiny independent CPU check.
    generator = MESA / 'src/intel/genxml/gen_pack_header.py'
    xml = MESA / 'src/intel/genxml/gen12.xml'
    g = run(['python', str(generator), str(xml)])
    assert g['returncode'] == 0, g['stderr']
    header = REF / 'gen12-pack-proof.h'
    header.write_text(g.pop('stdout'))
    g['output'] = record(header)
    provenance['checks'].append(dict(name='upstream-pack-header-generation', **g))
    compile_argv = ['cc', '-std=c11', '-DUTIL_ARCH_LITTLE_ENDIAN=1', '-DUTIL_ARCH_BIG_ENDIAN=0',
                    '-I'+str(MESA/'src'), '-I'+str(MESA/'include'), str(REF/'pack-proof.c'),
                    '-lm', '-o', str(REF/'pack-proof')]
    c = run(compile_argv)
    provenance['checks'].append(dict(name='pack-proof-compile', **c))
    assert c['returncode'] == 0, c['stderr']
    r = run([str(REF/'pack-proof')])
    (REF / 'pack-proof.log').write_text(r['stdout'] + r['stderr'])
    provenance['checks'].append(dict(name='pack-proof-execution', **r))
    assert r['returncode'] == 0, r
    provenance['earlier_bounded_attempt'] = 'Initial compile without endian configuration failed at util/u_endian.h. Corrected by setting host little-endian compile definitions. No GPU or normalizer run.'
    provenance['proof_artifacts'] = [record(p) for p in [
        LAB/'track-a/stencil-proof.json', LAB/'track-a/draw-proof.json',
        LAB/'track-a/reports/stencil-and-draw-semantics.md',
        LAB/'reports/stencil-and-draw-semantics.md',
        REF/'pack-proof.c', REF/'pack-proof', REF/'pack-proof.log', REF/'revalidate-proof.py']]
    provenance['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (REF/'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps({'checks': 'PASS', 'pdf_revalidation': [
        {'path': x['path'], 'match': x['later_official_bytes_match_present_file'],
         'status': x['later_official_revalidation'].get('status'),
         'error': x['later_official_revalidation'].get('error')}
        for x in provenance['pdfs']], 'mesa_exact_files': len(provenance['mesa_files']),
        'output': str(REF/'provenance.json')}, indent=2))


if __name__ == '__main__':
    main()
