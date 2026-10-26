#!/usr/bin/env python3
"""Generate GA33-research/analysis/ga32b-fields.md and ga31-vs-ga32.md from decoded JSONs."""
import json

def load(p): return json.load(open(p))

ga31 = load('ga31b.json')
ga32 = load('ga32b.json')

def fmt(v):
    if isinstance(v, int) and v > 0xFFFF:
        return hex(v)
    return str(v)

# ---------------- ga32b-fields.md ----------------
lines = []
A = lines.append
A("# GA3.2b THAG 字段解码（编译器验证布局）\n")
A(f"- 文件：`{ga32['file']}`")
A(f"- SHA-256：`{ga32['sha256']}`，{ga32['size']} bytes，{ga32['records_in_file']} × 0x{ga32['record_size']:X}")
A("- 布局：clang `-fdump-record-layouts-complete` 对 GA3.2 头文件验证（analysis/layout_dump_ga32.txt）；")
A("  `sizeof(HangRecord)=0xC2A0`，`0x80=resolveDiag`（GA3.1 为 pad），`out` 起始 0x90，")
A("  batch 区 0x2A0、VS 区 0x82A0、PS 区 0xA2A0（均相对记录起点）。\n")
for r in ga32['records']:
    o = r['out']
    A(f"## 记录 {r['index']}（ms={r['ms']}，attempts={r['attempts']}，wakeDomain={r['wakeDomain']}，模式 {r['mode']}）\n")
    A(f"- `result` = {o['result']}（raw {o['result_raw']}）")
    A(f"- `resolveDiag` = 0x{r['resolveDiag']['raw']:X}：" +
      "，".join(f"{k}={int(v)}" for k, v in r['resolveDiag']['bits'].items()) +
      f"；bits16-23 lastSolveSymbolError={r['resolveDiag']['lastSolveSymbolError']}")
    A(f"- `attemptReasons[0..{r['attempts']-1}]` = {r['attemptReasonNamesUsed']}")
    A(f"- `classifierReady={o['classifierReady']}`，`classifierProbeOk={o['classifierProbeOk']}`，`classifierProbe1={o['classifierProbe1']}`")
    A(f"- `exclusionsVerified={o['exclusionsVerified']}`（stolen={o['exclusionStolen']}，lowTop={o['exclusionLowTop']}，tseg={o['exclusionTseg']}）")
    A(f"- `bridgeValid={o['bridgeValid']}`；bridgeRegs=" + ", ".join(f"{k}=0x{v:08X}" for k, v in o['bridgeRegs'].items()))
    A(f"- `bbAddr=0x{o['bbAddr']:X}`，`pml4=0x{o['pml4']:X}`，`batchStart=0x{o['batchStart']:X}`")
    A(f"- `batchValid=0x{o['batchValid']:02X}`（{o['batchValidPages']} 页），`batchPages={o['batchPages']}`")
    A(f"- `tableReads={o['tableReads']}`，`pageReads={o['pageReads']}`，`readBytes={o['readBytes']}`")
    A(f"- `scan`：foundSba={o['scan']['foundSba']} foundVs={o['scan']['foundVs']} foundPs={o['scan']['foundPs']}，"
      f"sbaAt=0x{o['scan']['sbaAt']:X}，instructionBase=0x{o['scan']['instructionBase']:X}，"
      f"kernelAt={[hex(x) for x in o['scan']['kernelAt']]}，kernelOffset={[hex(x) for x in o['scan']['kernelOffset']]}")
    A(f"- `kernelPhys={[hex(x) for x in o['kernelPhys']]}`，`kernelPages={o['kernelPages']}`")
    A(f"- 载荷：batch 有效 {o['payload']['batch_region']['valid_bytes']} B / 非零 {o['payload']['batch_region']['nonzero_bytes']} B；"
      f"VS {o['payload']['kernel_vs_region']['valid_bytes']} / {o['payload']['kernel_vs_region']['nonzero_bytes']}；"
      f"PS {o['payload']['kernel_ps_region']['valid_bytes']} / {o['payload']['kernel_ps_region']['nonzero_bytes']}")
    if o['batch_command_headers']:
        A(f"- Batch 命令头：{o['batch_command_headers']}")
    A(f"- 首次失败推断：**{r['first_failure']['stage']}** — {r['first_failure']['explanation']}")
    for u in r['first_failure']['unknown']:
        A(f"  - 未证实：{u}")
    A("\n寄存器（驱动 GA2 报告命名）：\n")
    A("| # | 寄存器 | 名称 | 值 |")
    A("|---|---|---|---|")
    for e in r['registers']:
        A(f"| {e['index']} | 0x{e['address'][2:].upper()} | {e['name']} | 0x{e['value']:08X} |")
    A("")
open('ga32b-fields.md', 'w').write("\n".join(lines) + "\n")
print('wrote ga32b-fields.md')

# ---------------- ga31-vs-ga32.md ----------------
def rec_map(j):
    return {r['index']: r for r in j['records']}

m31, m32 = rec_map(ga31), rec_map(ga32)
L = []
B = L.append
B("# GA3.1b vs GA3.2b THAG 对比\n")
B(f"| | GA3.1b | GA3.2b |")
B("|---|---|---|")
B(f"| 文件 | `{ga31['file'].split('/')[-1]}` | `{ga32['file'].split('/')[-1]}` |")
B(f"| SHA-256 | `{ga31['sha256'][:16]}…` | `{ga32['sha256'][:16]}…` |")
B(f"| 记录数 | {ga31['records_in_file']} | {ga32['records_in_file']} |")
B("")
for i in (0, 1):
    a, b = m31[i], m32[i]
    B(f"## 记录 {i}")
    B("")
    B("| 字段 | GA3.1b | GA3.2b |")
    B("|---|---|---|")
    B(f"| 记录模式 | {a['mode']} | {b['mode']} |")
    B(f"| ms | {a['ms']} | {b['ms']} |")
    B(f"| wakeDomain | {a['wakeDomain']} | {b['wakeDomain']} |")
    B(f"| resolveDiag/pad | 0x{a['resolveDiag']['raw']:X} | 0x{b['resolveDiag']['raw']:X} |")
    B(f"| result | {a['out']['result']} | {b['out']['result']} |")
    B(f"| classifierReady | {a['out']['classifierReady']} | {b['out']['classifierReady']} |")
    B(f"| exclusionsVerified | {a['out']['exclusionsVerified']} | {b['out']['exclusionsVerified']} |")
    B(f"| bbAddr | 0x{a['out']['bbAddr']:X} | 0x{b['out']['bbAddr']:X} |")
    B(f"| pml4 | 0x{a['out']['pml4']:X} | 0x{b['out']['pml4']:X} |")
    B(f"| batchPages | {a['out']['batchPages']} | {b['out']['batchPages']} |")
    B(f"| tableReads | {a['out']['tableReads']} | {b['out']['tableReads']} |")
    B(f"| pageReads | {a['out']['pageReads']} | {b['out']['pageReads']} |")
    B(f"| readBytes | {a['out']['readBytes']} | {b['out']['readBytes']} |")
    B(f"| Batch 非零 | {a['out']['payload']['batch_region']['nonzero_bytes']} | {b['out']['payload']['batch_region']['nonzero_bytes']} |")
    B(f"| VS 非零 | {a['out']['payload']['kernel_vs_region']['nonzero_bytes']} | {b['out']['payload']['kernel_vs_region']['nonzero_bytes']} |")
    B(f"| PS 非零 | {a['out']['payload']['kernel_ps_region']['nonzero_bytes']} | {b['out']['payload']['kernel_ps_region']['nonzero_bytes']} |")
    B(f"| 首次失败 | {a['first_failure']['stage']} | {b['first_failure']['stage']} |")
    B("")
    B("关键寄存器对比：")
    B("")
    B("| 寄存器 | GA3.1b | GA3.2b |")
    B("|---|---|---|")
    for ea, eb in zip(a['registers'], b['registers']):
        B(f"| {ea['name']} | 0x{ea['value']:08X} | 0x{eb['value']:08X} |")
    B("")
B("## 差异结论\n")
B("- GA3.1b 两条记录均为 `MemoryMapUnverified`（分类器未解析），零读取。")
B("- GA3.2b 记录 0 为 `UnsafePhysicalRange`（门禁通过后第一个数据页被拒绝）；记录 1 **完整成功**（result=Ok，Batch/VS/PS 均读取）。")
B("- resolveDiag 0x0 → 0xF：_max_mem/_pmap_valid_page/探针/_uio_free 全部就绪（位定义见 THAG-FORMAT.md）。")
B("- BB_ADDR 与 GA3.1b 相同（0x40B75ED8 / 0x426FE104），说明 GPU VA 分配确定；PDP0 物理页不同（0xEEE08000 → 0x3F23E6000 组合 PML4）。")
open('ga31-vs-ga32.md', 'w').write("\n".join(L) + "\n")
print('wrote ga31-vs-ga32.md')
