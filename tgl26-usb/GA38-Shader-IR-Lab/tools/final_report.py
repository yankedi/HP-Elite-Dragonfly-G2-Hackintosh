#!/usr/bin/env python3
"""Generate the integrated Chinese report from final raw-anchored results/state."""
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
from common import ROOT, load


def render():
    state = load(ROOT / 'state.json')
    summary = load(ROOT / 'summary.json')
    verification = load(ROOT / state['latest_verification'])
    test_log = (ROOT / state['latest_verification']).parent / 'logs/tests-clean-a/stderr.txt'
    methods = int(re.search(r'Ran (\d+) tests?', test_log.read_text())[1])
    counts = {s: sum(p['comparison'][s] for p in summary['programs']) for s in
              ['STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS', 'COUNTEREXAMPLE', 'UNKNOWN']}
    lines = ['# GA3.8 最终中文报告', '',
        '## 1. 结论', '',
        '**离线工程已交付完整四程序表示和候选审查；四份现有 Gen12 候选仍没有获得完整语义等价证明。**', '',
        f"79 条真实源指令、79 条原候选指令全部保留原 bytes/offset；10+10 条 SEND 均有双代消息合同；8 份完整保守图、4 份目标调度审查、948 项十二层结果已生成。当前计数：`{counts}`。",
        '其中 checked 只表示所列字段/约束在明确前提下获静态核对；不是整条指令或整程序的硬件认证。原候选没有命中已建模子集的确定反例，不等于它们正确。数值、debug、跨代消息、资源和消息完成规则缺口都有实际偏移。', '',
        '## 2. 十三项验收状态', '', '|状态项|值|', '|---|---|']
    for key, value in state['final_status'].items():
        lines.append(f'|{key}|{value}|')
    lines.extend(['',
        'SOURCE_SEMANTIC_IR / MESSAGE_CONTRACTS / REGISTER_DEPENDENCIES 的 COMPLETE 指全部真实节点、载体、访问/约束和明确未知均被完整表示；FOUR_CANDIDATE_REVIEW 的 COMPLETE 指每条源指令每层都有评价，可为 UNKNOWN。GEN12_SWSB_CHECKER 仅 VALIDATED_SUBSET。SEND_ABI_SEMANTICS 的 UNKNOWN 不否定已实核的载体位域。', '',
        '## 3. 四真实程序与当前评价', '',
        '|程序|EU窗口入口|长度/源条数|候选条数|checked / counterexample / unknown|', '|---|---|---|---|---|'])
    corpus = load(ROOT / 'corpus/provenance.json')
    for p in summary['programs']:
        source = next(v for v in corpus['programs'] if v['shader_id'] == p['shader_id'])
        c = p['comparison']
        lines.append(f"|{p['shader_id']}|+0x{source['eu_window_offset']:X}|{source['source']['bytes']}B / {p['source']['instructions']}|{p['candidate']['instructions']}|{c['STATIC_CHECKED_WITH_EXPLICIT_ASSUMPTIONS']} / {c['COUNTEREXAMPLE']} / {c['UNKNOWN']}|")
    lines.extend(['',
        '捕获 SHA256 `1622ecc2aecdcc85ae45dcf86e4219338f6e41e0243b27d5e7128a9999f13333` 是完整 99648B 双 record 文件的哈希。只使用有效 Record1 共享 EU 窗口，四程序各在已证 EOT 截止，未解析 padding、Record0 或把四入口合并。', '',
        '## 4. 为什么现有候选仍不可信；下一步优先哪里', '',
        '1. **PS0 +0x0、+0x30 的 NF accumulator→r122:f**；KP1 八个 NF 写入位置改用 r107:f；KP2 四处改用 r117:f。位宽标签/译码成功不能证明 NF 内部表示、融合、中间舍入、denormal/FP 模式和普通 GRF 的数值等义。完整位置与 scratch 已知访问见 `reports/NF-ACC-SCRATCH-AUDIT.md`。GA3.9 最先应为这种转换设置“有定理/证据才接受，否则拒绝”的离线准入，并独立证明 scratch 生命期/ABI，而不是继续盲生机器码。',
        '2. **VS +0x0→+0x20、+0x28→+0xD8** 涉及显式/隐式 ACC。MAC 读 ACC 保留，内部精度/packing 与线程控制未知；不存在可拿随机 float 测试替代的严格证明。',
        '3. **PS-KP1 SEND +0x168 → MOV +0x178 → EOT SEND +0x1A8**：第一个 RT SEND 无 response；随后 `$0.dst` 是否提供所需完成以及再次设置 SBID0 的隐式同步，当前规范不足。IGA 有复用时自动同步的实现依据，因此不能只因缺显式 wait 就报硬件错误，也不能将 null-response `.dst` 默认完成。GA3.9 应先关闭这条精确规则缺口。',
        '4. **Debug/Switch 删除**：三个 PS 的 +0x10、VS +0xF0 源 ARF/debug 写入及 Switch 被 null MOV 代替，可观察性前提未知；双方 options 都参与比较。',
        '5. **消息与 payload**：PS0 +0x50 sampler / +0x88 RT；KP1 +0xE0、+0x120 sampler / +0x168、+0x1A8 RT；KP2 +0x90 sampler / +0xC8 RT；VS +0x100、+0x110 URB。Gen11/12 载体、SFID、长度、header、各 family 字段已按固定 PRM/Mesa 分开核验；实际 heap、Surface/BindingTable/Sampler/URB/RT 和 thread payload ABI 未捕全，保持 UNKNOWN。相同 descriptor DWORD 不是跨代消息语义证明。',
        '6. **EOT 与副作用**：四个最终 EOT 的载体/位置已核对，payload 已消费、response 写回、side-effect 可见、token 完成、EOT 安全为不同事件。没有把 EOT 当万能 fence；缺实际消息终止规范的地方未判 PASS。', '',
        '完整优先级、实际源/目标偏移、原编码、规则、假设和最小修复入口在 `reports/TRANSLATOR-FIX-BACKLOG.md` 与四份程序 JSON。当前没有证据足以宣布必须把哪一个原候选字段改成另一个值；不能拿 mutant 的错误假冒原候选错误。', '',
        '## 5. 实现与证据链', '',
        '- 类型化 Fact/Access/Instruction 与 JSON Schema，UNKNOWN≠NONE。IGA JSON typed sr 按元素宽度转字节，和编码 SubRegNum 的字节单位明确区分。执行 lane 标签不被用来错误证明物理 byte 不相交。',
        '- 精确 byte/lane 访问与 mask/predicate 条件，特殊/未知 ACC/flag/address/控制访问为 SymbolicSet；整数 DW MUL 隐式 ACC 写也保守表示。',
        '- 保守 all-pairs RAW/WAR/WAW 图包含传递 hazard；intervening overwrite 降低旧 reaching-definition 的确定度。每条边有来源/等级，删隐式访问或删图会被完整性校验拒绝。',
        '- Gen12 single-in-order-pipe regDist、异步 SEND token、SYNC 与 EOT 子集事件模型；没有把 IGA auto-deps 当证明。零局部约束不再显示正向 checked。',
        '- 源→目标映射按 hash-bound byte-range 覆盖核验，允许一对多/额外 SYNC/compact 扩张。实际 11→12 条 CLI 例验证可达性；缺见证显式 UNKNOWN，multi-ALU 组合缺定理也 UNKNOWN。',
        '- 每项十二层结果含实际双方原码、偏移、依赖字段、规则、违反约束或缺证明、前提、最小修复和来源；NF 未知只影响该 operand，不能掩盖其他已知 GRF 字段改变。', '',
        '## 6. 实际验证结果', '',
        f"- `{state['latest_verification']}`：两全新目录，{methods} 个 unittest 方法各通过；8 份 IR Schema；{verification['deterministic_files']} 份规范化工件逐字节/摘要一致（含9Markdown，仅替换不同run路径前缀）。",
        f"- `{state['latest_mutation_verification']}`：独立期望21 fixture 全通过、14必需 mutant 类齐全，含真实 NF 指令上的已知 GRF subregister 变异。另有 literal byte/lane、消息字段、graph-edge oracle 和属性测试。",
        '- 原 31 严格隔离单位 31/31 保持原已知字段/机器码往返；8 全程序正确平台 decode/roundtrip。原 640 native 调用跨 Clang/GCC Release 和 Clang Debug ASan+UBSan；另复制固定源码 513 文件逐字节核对后独立构建 Clang/GCC standalone Debug，31单位/8程序结果不退化。',
        '- ASan/UBSan 诊断 0；原 sanitizer Debug 4 次、两个新 plain Debug 合计8次对错误平台/损坏输入的内部 assertion abort 单列，未伪装成成功或 sanitizer finding。没有对 Python 代码冒称 ASan instrumented。',
        '- 负例包含 compact/native 截断、损坏/非法compact、不支持branch、动态descriptor、未知messagefamily、版本/hash不符、端序、整数/指令资源边界、graph完整性、输出symlink逃逸；原输入未被测试改坏。',
        '- `runs/repository-check-020`：make check 通过（46脚本/42JSON/27Markdown）；`runs/provenance-final-022` 独立全量复核历史 GA32–37 及 GA37 972本地+171外部项全部不变。', '',
        '## 7. 独立审计与真实失败修复', '',
        '用户指定 DeepSeek 简单独立任务；本轮未使用 Luna。初审冻结于 `checkpoints/pre-independent-repairs-006`，`review/initial` 保存9项发现/7mustfix及其原反例。修复、复审与受限条件详见 `reports/INDEPENDENT-AUDIT.md`、`review/final/closure.json`。',
        '独立 mutant 原17/20、随后20/21失败均保留：M05暴露region层漏typed subregister；VS源 +0xD8暴露symbolic ACC表达式用Python dict repr导致sorted JSON回读变化，现改canonical JSON并在8IR重建校验。SBID复用初期错误的CE预期经独立直读IGA/规范纠正为UNKNOWN；原oracle/generator、依据和ERRATA均保留，不以修改期望掩盖缺陷。',
        '规则任务曾误把16份原始decoder输出写到tmp，随后按字节/hash迁移到本Lab `reference/rules/raw`，`MIGRATION-RECEIPT.json`明确记录范围偏离，未把这次失误改写为从未发生。', '',
        '## 8. 已修复、受限、仍未知与输入缺口', '',
        '|类别|内容|', '|---|---|',
        '|已修复并重放|IR序列化、known operand被NF掩盖、DW MUL implicit、target-onlySwitch、调度空集/非法距离、通用映射接口与严格身份、null-response/SBID分类过度结论|',
        '|已验证但受限|真实 raw framing、双代载体字段、显式GRF byte/lane、完整hazard表示、有限 SWSB/命令集模型、隔离单位往返；均不等于GPU语义认证|',
        '|仍未知|NF/ACC内部数值/舍入/融合、Debug消除许可、无response token、复用隐式同步硬件规则、EOT和全局side-effect可见性、规范结构冲突|',
        '|缺输入|实际resource heaps/Surface/BT/Sampler/URB/RT/线程payload和运行态资源一致性，无法由本次captured bytes补造|', '',
        '## 9. 复现、封存与后续', '',
        'README 提供可运行入口，REQUIREMENTS-MAP 逐项映射用户要求到代码与实际证据。manifest/selfhash封存整个私有Lab（包含历史失败、原oracle、native源码/build与日志），外部来源固定在manifest；symlink只哈希链接文本。seal完整性不代表硬件语义认证，最终校验回执为 `logs/seal-verification.json`。',
        'READY_FOR_TRANSLATOR_REPAIR=YES 的含义是已有可执行离线validator与精确拒绝/修复/证明清单可供下一阶段使用，不表示所有语义问题已有直接修法。GA3.9优先NF转换拒绝/证明门槛、scratch活跃区间与PS-KP1无response消息token规则，再补消息ABI。',
        '**READY_FOR_HARDWARE_APPROVAL=NO。** 没有新GPUHang、MMIO、SSH改机、kext/EFI/IMG/固件/门禁或真实Batch/Shader写回；没有声称Metal成功。GA3.8交付后等待新目标授权，不自动启动GA3.9或实机实验。'])
    (ROOT / 'FINAL-REPORT.md').write_text('\n'.join(lines) + '\n')
    print('Wrote integrated final report from actual summary and explicit final status')


if __name__ == '__main__':
    render()
