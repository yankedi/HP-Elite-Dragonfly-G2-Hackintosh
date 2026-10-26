#!/usr/bin/env python3
"""Render Chinese reports directly from actual raw-anchored machine results."""
from __future__ import annotations

import argparse
from pathlib import Path

from common import ROOT, load, output_root


def write(root, name, text):
    path = output_root(root / name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + '\n')


def hexs(values):
    return ', '.join(f'+0x{x:X}' for x in values)


def render(run, destination):
    run, destination = output_root(run), output_root(destination)
    summary = load(run / 'summary.json')
    provenance = load(run / 'corpus/provenance.json')
    allmessages, allschedules, allfindings = [], [], []
    backlog = ['# GA3.9：Translator 修复与证明任务列表', '',
        '本表区分实际候选反例、离线可验证的字段/调度修复与当前缺失的证明。变异负例只验证校验器，不被计作原候选错误。所有偏移均为各程序内字节偏移，EU 窗口绝对范围另列。', '',
        '## P0：实际候选确定反例', '']
    actual_counters = []
    for prog in summary['programs']:
        ident = prog['shader_id']
        review = load(run / f'validator/outputs/{ident}-comparison.json')
        source = load(run / f'ir/outputs/{ident}-source.json')
        target = load(run / f'ir/outputs/{ident}-candidate.json')
        schedule = load(run / f'validator/outputs/{ident}-schedule.json')
        sc = load(run / f'ir/messages/{ident}-source.json')
        tc = load(run / f'ir/messages/{ident}-candidate.json')
        allmessages.extend([sc, tc])
        allschedules.append(schedule)
        allfindings.extend(review['findings'])
        actual_counters.extend((ident, f) for f in review['findings'] if f['status'] == 'COUNTEREXAMPLE')
        srcfact = next(p for p in provenance['programs'] if p['shader_id'] == ident)
        lines = [f'# {ident}：真实源与 Gen12 候选逐程序审查', '',
            f"源：{srcfact['source']['bytes']}B／{len(source['nodes'])} 条，EU 窗口 `+0x{srcfact['eu_window_offset']:X}`。",
            f"源 SHA256 `{source['program_sha256']}`；候选 SHA256 `{target['program_sha256']}`。", '',
            '## 结论和边界', '',
            f"十二层逐项结果：`{review['counts']}`。目标调度约束：`{schedule['counts']}`。",
            'STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS 仅限该字段/约束及所列假设，不代表完整指令等价。UNKNOWN 保留来源与影响。硬件认证始终为 false。', '',
            '## 指令对应与十二层状态', '',
            '映射来自被冻结候选及历史布局见证，并用真实 framing 验证全覆盖。它是对应假设，等价性由各层独立检查。额外 SYNC/一对多范围可表达；多 ALU 组合缺证明时返回 UNKNOWN。', '',
            '|源偏移|EU窗口|源编码|候选范围|opcode|结果 C / X / U|', '|---|---|---|---|---|---|']
        for n in source['nodes']:
            pc = n['byte_range'][0]
            fs = [f for f in review['findings'] if f['source_offset'] == pc]
            ts = fs[0]['target_offsets']
            c, x, u = [sum(f['status'] == s for f in fs) for s in
                       ['STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS', 'COUNTEREXAMPLE', 'UNKNOWN']]
            lines.append(f"|+0x{pc:X}|+0x{n['eu_window_range'][0]:X}|`{n['raw_hex']}`|{hexs(ts)}|{n['opcode']}|{c} / {x} / {u}|")
        lines.extend(['', '## 逐层状态与最小修复入口', '', '|源偏移|层|状态|规则|结论/约束|', '|---|---|---|---|---|'])
        for f in review['findings']:
            lines.append(f"|+0x{f['source_offset']:X}|{f['layer']}|{f['status']}|{f['rule']}|{f['detail'].replace('|','／')}|")
        lines.extend(['', '## 可复核机器工件', '',
            f'- `{run.relative_to(ROOT)}/ir/outputs/{ident}-source.json` 与 candidate：原 bytes、访问集合、未知、工具身份。',
            f'- `{run.relative_to(ROOT)}/ir/messages/{ident}-{{source,candidate}}.json`：所有 SEND 合同。',
            f'- `{run.relative_to(ROOT)}/dependency/graphs/{ident}-{{source,candidate}}.json`：完整保守 hazard 图。',
            f'- `{run.relative_to(ROOT)}/validator/outputs/{ident}-comparison.json`：每层源/目标原码、偏移、规则、必要前提、修复与来源。',
            f'- `{run.relative_to(ROOT)}/validator/outputs/{ident}-schedule.json`：每条等待约束及状态。'])
        write(destination, f'{ident}.md', '\n'.join(lines))
    for ident, f in actual_counters:
        backlog.append(f"- {ident} 源 +0x{f['source_offset']:X} → {hexs(f['target_offsets'])}，{f['layer']}：{f['detail']}。修复：{f['minimal_repair']}。")
    if not actual_counters:
        backlog.append('当前已建模字段没有原候选的确定 COUNTEREXAMPLE。现有候选的不可信点是下面可精确定位、尚未完成的语义/ABI/调度证明；不得把测试 mutant 或 UNKNOWN 改写成已证实候选错误。')
    backlog.extend(['', '## P1：CPU 离线可推进的精确证明/修复', '',
        '|程序|实际源偏移|任务|独立验收|', '|---|---|---|---|'])
    for prog in summary['programs']:
        ident = prog['shader_id']
        source = load(run / f'ir/outputs/{ident}-source.json')
        nfs = [n['byte_range'][0] for n in source['nodes'] if n['numeric_semantics']['nf']]
        accs = [n['byte_range'][0] for n in source['nodes'] if n['numeric_semantics']['accumulator']]
        dbg = [n['byte_range'][0] for n in source['nodes'] if n['control_effects']['debug_switch']]
        if nfs:
            backlog.append(f'|{ident}|{hexs(nfs)}|NF→GRF 替换：补精度、舍入、掩码与临时 GRF 活跃区间证明；必要时拒绝该转换|固定规范规则＋独立数值等义 oracle；随机 float 仅辅助|')
        elif accs:
            backlog.append(f'|{ident}|{hexs(accs)}|ACC 显式/隐式读写：定义内部区域与 MUL/MAC 融合/精度合同|独立 ACC 依赖 oracle 与精度规则；不能按 GRF 物理大小猜测|')
        if dbg:
            backlog.append(f'|{ident}|{hexs(dbg)}|Debug/Switch→null MOV：明确删改 ARF 写入/线程切换提示的可观察性前提|按准确代际规范作消除许可或保持 UNKNOWN；无证据不称语义等价|')
    backlog.extend(['', '## P2：SEND Descriptor 与 payload ABI', '',
                    '|程序|源/目标偏移|消息|最小后续任务|', '|---|---|---|---|'])
    for packet in allmessages:
        if packet['platform'] != '11':
            continue
        for m in packet['messages']:
            backlog.append(f"|{packet['shader_id']}|+0x{m['instruction_offset']:X}|{m['family']}|建立 Gen11/Gen12 每字段转换定理；核 payload/response GRF 长度与 header/SIMD；符号资源与真实 heap 分开|" )
    backlog.extend(['', '## P3：调度、EOT 与未来独立证据', '',
        '对每份 `*-schedule.json` 中 UNKNOWN_SCHEDULING_SEMANTICS 的实际 producer/consumer offset，先补精确单流水线、token source/destination wait、无 response SEND 与 EOT 规则，再决定是否需要插入等待。保守 hazard 图含传递边，不能把每条旧写覆盖边都当真实 reaching-value 依赖。', '',
        '真实 Surface/Binding Table/Sampler/URB/RT/dispatch payload 身份和运行态资源有效性属于后续独立证据缺口。本轮不会通过假设 heap 一定有效消除 UNKNOWN。', '',
        '下一阶段优先 CPU 离线可校验修复与可拒绝证明缺口；不提前改上游真实运行路径或部署。Metal 加速仍需要完整命令状态、资源/映射同步、调度及用户态驱动集成。'])
    backlog.extend(['', '### 实际未决调度位置（逐规则去重）', '',
                    '|程序|producer→consumer（目标偏移）|规则|最小后续任务|', '|---|---|---|---|'])
    for schedule in allschedules:
        seen = set()
        for c in schedule['constraints']:
            if c['status'] != 'UNKNOWN':
                continue
            key = (c['producer_offset'], c['consumer_offset'], c['rule'])
            if key in seen:
                continue
            seen.add(key)
            coordinate = lambda x: '?' if x is None else f'+0x{x:X}'
            backlog.append(f"|{schedule['shader_id']}|{coordinate(key[0])} → {coordinate(key[1])}|{key[2]}|{c['detail'].replace('|','／')}|")
    write(destination, 'TRANSLATOR-FIX-BACKLOG.md', '\n'.join(backlog))
    msg = ['# 全部实际 SEND 合同', '',
        '四源与四候选各 10 条 SEND。消息族只有 SAMPLER、RENDER_TARGET、URB；原 bytes、descriptor、carrier 与资源/完成未知各自独立保存。', '',
        '|程序/平台|偏移|族/SFID|Descriptor|ExDescriptor|payload0+1 / response (GRF)|Header|EOT|', '|---|---|---|---|---|---|---|---|']
    for packet in allmessages:
        for m in packet['messages']:
            lengths = m['lengths']
            fmt = lambda f: '?' if f['value'] is None else hex(f['value'])
            msg.append(f"|{packet['shader_id']} / {packet['platform']}|+0x{m['instruction_offset']:X}|{m['family']} / {m['sfid']['value']}|{fmt(m['descriptor'])}|{fmt(m['extended_descriptor'])}|{lengths['payload0_grf']['value']}+{lengths['payload1_grf']['value']} / {lengths['response_grf']['value']}|{m['header_present']['value']}|{m['eot']}|")
    msg.extend(['', 'BTI/Sampler 数字是 descriptor 中的编码值，不能由它推断真实 Surface/RT 的身份或有效性。相同 descriptor DWORD 仅能说明编码位值相同；完整消息语义需按代际逐字段证明。', '',
                '规则与证据索引见 `reference/rules/`；机器合同逐字段有 bit 范围、rule、known/unknown 与资源依赖。'])
    write(destination, 'MESSAGE-CONTRACTS.md', '\n'.join(msg))
    sched = ['# SWSB、寄存器与消息完成依赖', '',
        '执行模型：Xe-LP 单一 in-order ALU 流水线距离等待与显式 SEND token 事件子集。未建模的 pipeline、ACC/NF、外部副作用可见性和 EOT 消息完成规则返回 UNKNOWN。', '',
        '|程序|checked|counterexample|unknown|', '|---|---|---|---|']
    for s in allschedules:
        sched.append(f"|{s['shader_id']}|{s['counts']['STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS']}|{s['counts']['COUNTEREXAMPLE']}|{s['counts']['UNKNOWN']}|")
    sched.extend(['', 'Payload 被消费、response 写回、副作用完成、token 可重用、EOT 安全为五个不同事件。源图的 symbolic 访问不会推定与别的指令独立。distance wait 统计 in-order 指令而不把异步 SEND 当已完成。', '',
                  '本表为程序内有限子集约束；完整事件与每条边的状态见各程序 `*-schedule.json`。独立 mutant 删除等待/提前复用 token 的预期来源与原候选分开保存。'])
    write(destination, 'SWSB-DEPENDENCIES.md', '\n'.join(sched))
    findings = ['# 四个候选的字段级发现汇总', '',
                f"真实源 79 条、候选 79 条；十二层共 {len(allfindings)} 项。",
                f"原候选分类总计：{ {s: sum(f['status']==s for f in allfindings) for s in ['STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS','COUNTEREXAMPLE','UNKNOWN']} }。", '',
                '每个具体偏移的原码、源/目标对应、规则、假设、违反约束、最小修复和证据在各程序机器 JSON 与 Markdown。原候选字段通过不消除 NF/ACC、Debug/Switch、跨代 SEND、资源 ABI 或 EOT 的证明缺口。', '',
                'GA3.9 优先顺序见 `TRANSLATOR-FIX-BACKLOG.md`；硬件批准为 NO。']
    write(destination, 'CANDIDATE-FINDINGS.md', '\n'.join(findings))
    scratch = ['# NF 临时 GRF、mask 与中间精度审计', '',
        '审计分开处理临时寄存器物理占用与数值等义。下表列实际 NF→GRF 替换、同一 GRF 在源和候选中的所有已知访问，便于复核覆盖风险。完整 byte/lane hazard 另见 dependency/graphs。', '',
        'NF 内部宽度、舍入、融合与中间精度没有精确规范证据，NUMERIC_SEMANTICS=UNKNOWN；不能以把 NF 当 32-bit float 的仿真补证明。execution mask、predicate 和执行大小逐字段比较，partial write 的未激活 lane 保留条件访问。', '',
        '|程序|NF源偏移→目标偏移|scratch GRF|源已知触及偏移|目标已知触及偏移|', '|---|---|---|---|---|']
    for prog in summary['programs']:
        ident = prog['shader_id']
        source = load(run / f'ir/outputs/{ident}-source.json')
        target = load(run / f'ir/outputs/{ident}-candidate.json')
        comparison = load(run / f'validator/outputs/{ident}-comparison.json')
        def touches(program, register):
            return [n['byte_range'][0] for n in program['nodes'] if any(
                a['file'] == 'GRF' and a['elements'] is not None and any(
                    e['byte_start'] < (register+1)*32 and register*32 < e['byte_end'] for e in a['elements'])
                for a in n['register_access']['accesses'])]
        for n in source['nodes']:
            if n['iga_fields'].get('dst', {}).get('type') != 'nf':
                continue
            entry = next(e for e in comparison['mapping_witness']['entries'] if e['source_offset'] == n['byte_range'][0])
            targets = [t for t in target['nodes'] if entry['target_byte_range'][0] <= t['byte_range'][0] < entry['target_byte_range'][1]]
            for t in targets:
                reg = t['iga_fields'].get('dst', {}).get('reg', {})
                if reg.get('rn') == 'r':
                    r = reg.get('r', 0)
                    scratch.append(f"|{ident}|+0x{n['byte_range'][0]:X} → +0x{t['byte_range'][0]:X}|r{r}|{hexs(touches(source,r)) or '无已知显式触及'}|{hexs(touches(target,r))}|")
    scratch.extend(['', '已知源 GRF 没有显式触及只证明该访问投影未冲突；不证明资源/thread payload 的 incoming live-in、ABI 允许占用或 NF 高精度可丢弃。目标每次改写/读取均进入完整依赖图，缺失 source→scratch 数值/活跃区间定理时仍 UNKNOWN。', '',
        'VS 的 MUL +0x0、MAC +0x20、MAD +0x28、读 ACC 的 ADD +0xD8 单独保留显式或隐式 ACC 访问，不能被 PS 的 NF scratch 规则覆盖。其实际掩码/控制/内部精度条件与 symbolic access 见 VS 原始 IR。'])
    write(destination, 'NF-ACC-SCRATCH-AUDIT.md', '\n'.join(scratch))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    render(args.run, args.output)
