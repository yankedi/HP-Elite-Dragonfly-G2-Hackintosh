#!/usr/bin/env python3
"""Execute source-to-register-spec checks against archived immutable sources."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]

def main():
    base=ROOT/'reference/track-b';spec=json.loads((ROOT/'track-b/register-spec.json').read_text())
    outputs=[]
    for version,header in [('v5.15','i915_reg.h'),('v6.18','gt/intel_gt_regs.h')]:
        prefix=base/version/'drivers/gpu/drm/i915'
        h=(prefix/header).read_text();uncore=(prefix/'intel_uncore.c').read_text()
        table=uncore.split('static const struct intel_forcewake_range __gen12_fw_ranges[] = {',1)[1].split('};',1)[0]
        ranges=[(int(a,16),int(b,16),d) for a,b,d in re.findall(r'GEN_FW_RANGE\((0x[0-9a-f]+), (0x[0-9a-f]+), ([A-Z0-9_]+)\)',table)]
        matched=[]
        for key,symbol in [('fault','GEN12_RING_FAULT_REG'),('data0','GEN12_FAULT_TLB_DATA0'),('data1','GEN12_FAULT_TLB_DATA1')]:
            m=re.search(r'^#define\s+'+symbol+r'\s+_MMIO\((0x[0-9a-f]+)\)',h,re.M)
            assert m,symbol
            offset=int(m[1],16);assert offset==spec['registers'][key]['offset']
            domains=[d for a,b,d in ranges if a<=offset<=b];assert domains==['FORCEWAKE_GT'],domains
            matched.append({'symbol':symbol,'offset':offset,'domain':domains[0]})
        gt=(prefix/'gt/intel_gt.c').read_text()
        assert re.search(r'fault_data1\s*&\s*FAULT_VA_HIGH_BITS\)\s*<<\s*44',gt)
        assert re.search(r'fault_data0\s*<<\s*12',gt)
        assert 'RING_FAULT_VALID' in gt and 'intel_gt_clear_error_registers' in gt
        assert re.search(r'0x4000\s*\+\s*\(i\)\s*\*\s*4',h)
        outputs.append({'version':version,'register_checks':matched,'va_formula_verified':True,
                        'explicit_clear_present':True,'global_mocs_index37_overlap':0x4000+37*4==0x4094})
    provenance=json.loads((base/'provenance.json').read_text())
    for s in provenance['sources']:
        if 'sha256' in s:assert hashlib.sha256((ROOT/s['path']).read_bytes()).hexdigest()==s['sha256']
    for s in json.loads((base/'official-provenance.json').read_text()):
        assert hashlib.sha256((ROOT/s['path']).read_bytes()).hexdigest()==s['sha256']
    prm=(base/'tgl-registers-a-l.txt').read_text()
    section=prm[prm.index('Register Space:',prm.index('FAULT_TLB_RD_DATA1 -')):]
    assert '0CEBCh' in section[:500] and '31:9' in section[:600] and '8:7' in section[:1000]
    assert 'TLB Entry Present' in section[:1800] and 'TLB Entry Valid' in section[:1800]
    assert 'Cycle GTT SEL (1-GGTT Cycle, 0-PPGTT Cycle)' in section[:2500]
    out={'checks':outputs,'official_DATA1_fields_checked':True,'source_hashes_checked':True,
         'hardware_reads':0,'scope':'source text/definition checks, no Apple-hook safety proof'}
    (ROOT/'track-b/source-audit.json').write_text(json.dumps(out,indent=2)+'\n')
    print('Both pinned versions: registers/domain/VA/clear/MOCS checked; official DATA1 and source hashes checked')
if __name__=='__main__':main()
