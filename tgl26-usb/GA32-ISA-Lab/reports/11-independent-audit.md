# 11 · 独立只读审计（GA32-ISA-Lab）

> 主代理整合回执（保留以下原始审计不改写为事先通过）：M2边界标签/谓词检查、M3 opts/subop差分、M4主SWSB检查与措辞、M5工具/JSON/text/IO结构化拒绝均已修正；zip数量/退出核查与join/do也已补。`test_review_fixes.py`新增11项具体回归，最终完整79项通过；额外PS入口和命令格式新证据见报告12。M1清单以最终archive创建/验证回执为准。两份08报告分别为源码审查与实测评估，引用使用完整文件名。

- 审计员：`opencode-go/deepseek-v4.1-flash`（被主代理委派的独立子代理）。
- 日期：2026-10-18。**只读**：无网络、无实机、无 GPU、无 raw 上传、无对既有文件的修改；唯一新增文件为本报告。
- 审计对象（固定版本，均已复核 mtime 未在审计期间变化）：
  `translator/offline_translate.py`、`tools/isa_analyze.py`、`tools/evaluate_upstream.py`、
  `reports/03`、`04`、`07`、`08`（两份）、`09`、`FINAL-REPORT.md`、`tests/test_translator.py`。
- 未审计（按要求回避并发批次工作）：`reports/05-batch-command-stream.md`、`reports/06-pipeline-state.md`、
  `tests/test_batch.py`、`tools/` 下批次相关解码器。审计期间 05/06 由并发代理生成，本报告不评价。
- 并发说明：审计期间并发代理还改写了 `reports/07-rcs-hang-root-cause.md`（11:37，+3 代表）与新增根目录
  `FINAL-REPORT.md`；本报告对 report07 的引用基于**当前**版本，并在四.6 复核了其新增内容。
- 复核基线：捕获 `1622ecc2…`、ZIP `9af68646…`、PS/VS 切片、`reference/PROVENANCE.json` 内每个文件的
  SHA-256 与 git blob SHA-1、`tgl-command-stream-official.pdf` 与镜像逐字节一致、本地
  `tools/iga/source` HEAD `c36a504a…` 与 `tools/mesa-eu/source` HEAD `86333827…`。

## 结论摘要

核心**可执行行为**可由我独立复现，未发现会让原型“静默产出错误/部分 shader”的缺陷：只读重跑
`ps-icl.bin`/`vs-icl.bin` 得到 4/11 与 15/24 且 `full_shader_emitted=false`；branch/SEND/非有限立即数
被拒；predicate/`(sat)`/`(W)` 参与往返比对。主要问题是**证据生成器的标签/字段完备性**与**交付清单缺失**，
属于“结论方向正确、但证据措辞超出代码实际检查范围”。共列出 5 项必须修复、4 项应修复，另有缺失项与
“已核验正确”的正面清单。

---

## 一、必须修复（MUST-FIX）

### M1 — 交付清单不存在，但多处文档声称存在
- `README.md:17`、`README.md:19`、`README.md:38` 把 `manifest.json` / `manifest.sha256` 描述为已有文件，
  并给出复核命令 `sha256sum -c manifest.sha256`。实际根目录**没有**这两个文件（`ls` 已确认）。
- 根目录 `FINAL-REPORT.md`（并发代理新写）“完整SHA-256清单为 `manifest.json` / `manifest.sha256`”。
- 影响：README 的复核路径与“完整私有交付清单”承诺无法执行；迁移时缺少机器可读清单。
- 修复：运行 `python3 tools/archive_lab.py --create` 生成清单，或把三处引用改为“待生成（pending）”。

### M2 — `isa_analyze` 自动生成的 `boundary.claim` 断言“unpredicated”，代码从不检查谓词
- `tools/isa_analyze.py:109`：`'claim': 'straight-line unpredicated EOT-bounded entry; …'` 是**常量字符串**。
- 代码只统计 opcode 级控制流（`:56-57` 的 `branches`、`:99` 的 `control_flow`），**从不检查
  `pred` / `freg` / `wren`**（对比 `:88` 的差分字段表里才包含这三个字段）。
- 实测该数据里 PS0 有 **5** 条、VS 有 **2** 条 `wren=True`（`analysis/isa-diff.json`：PS `0x00/0x10/0x20/0x30/0x40`、VS `0xc8/0xf0`），
  即存在条件写使能；把它们概括成“unpredicated / straight-line”至少不精确，而且**若未来输入含真正 predicate，
  该 JSON 仍会输出 “unpredicated”**。
- 修复：由观测到的 `pred/freg/wren` 推导该短语，或删除“unpredicated”字样。

### M3 — `isa_analyze` 逐条差分遗漏 `opts`（及其它选项），却声称“全部数据/字段”
- `tools/isa_analyze.py:88` 只比较 `['es','eo','pred','wren','fm','freg','dst','srcs']`，外加 `op`；
  **不比较 `opts`**（也不含 `subop`）。`opts` 承载 `Saturate`/`EOT`/`Compacted` 等。
- 后果：若某条 ICL/TGL 的**唯一**差异在 `opts`，该行不会被标出任何差异；而 report04 的表（`04-gen11-gen12-diff.md:5-17`）
  被表述为完整统计。当前样本中所有“双端可解码”行本就因 `dst/srcs` 被判差异，故结论数字未被改变；但字段集不完备是
  证据完备性缺陷。
- 修复：把 `opts` 纳入差分字段（或明确声明字段集为“部分字段”）。

### M4 — `normalized()` 文档字符串与实现矛盾：依赖键并未“单独比较”
- `translator/offline_translate.py:57` 注释：“No architectural execution/operand keys ignored. **Dependency keys compared separately.**”
- 实现 `:58-60` 明确把 `regDist`、`sbid` 排除；`:104-108` **只**校验合成 drain 的 `regDist/srcs`，
  **主目标指令自身的 `regDist`/`sbid` 既不比较也不报告**（`report.json` 里 `swsb.regDist/sbid` 恒为 `null`）。
- 后果：report09 的“逐字段比对”与离线 `report.json` 的 `swsb` 字段容易被读成“依赖字段已核对”，实际未核对。
  在“孤立指令”语境下不比较 SWSB 是合理限制，但**代码注释与报告措辞必须与行为一致**。
- 修复：改写注释/报告为“调度字段未比较，仅校验自动 drain”，或显式比较/输出主指令的 `regDist/sbid`。

### M5 — 非结构化失败路径：与“每个不支持项都有结构化 code+offset”的承诺不符
- `translator/offline_translate.py:132-134` 的 per-unit 循环只 `except Rejected`；而 `:134` 在**调用前**就要
  求 `src['lines'][offset]` 存在，`:41` 的 `invoke` 可能抛 `subprocess.TimeoutExpired`/`OSError`，`:48-49`
  只捕获 `json.JSONDecodeError`。任一异常都会让整个进程以 traceback 终止，而非输出 per-unit `UNSUPPORTED`。
- 这仍是 **fail-closed**（不会产出 shader，退出非零），但违反了 report09:21 与 FINAL-REPORT 所述
  “每个不支持项包含 source offset、结构化错误代码与原因”。
- 备注：我已确认 IGA `-Xprint-pc` 对 `illegal` 也输出 `/* [pc] */` 行，故 `KeyError` 在当前工具下**不易触发**；
  此条按“证据完整性/边界鲁棒性”计，概率低但应补 catch-all 包装。

---

## 二、应修复（SHOULD-FIX）

### S1 — `evaluate_upstream.py` 位置对齐无计数保护
- `tools/evaluate_upstream.py:28`：`for i,j in zip(s['instructions'],t['instructions'])` 位置对齐，
  无 `len(source)==len(target)` 断言；若上游插入/删除一条指令，`zip` 会静默截断并给出错位的
  `source_offset→target_offset` 映射，而脚本仍报成功。当前数据 11/11、24/24 不触发。
- 另：`:23` 先 `decode(target,…)` 但未在构造映射前检查 `t['exit']`；目标解码失败会产生空映射而非显式错误
  （`full_shader_semantics_validated` 仍为 `False`，故不是假成功，但诊断信息缺失）。

### S2 — `BRANCHES` 集合漏 `join`/`do`（仍 fail-closed，但错误码误导）
- `translator/offline_translate.py:18` 未含 `join`、`do`（上游明确把 `goto/join` 视作流控）。它们会落到
  `:68-69` 的 `OPCODE_UNSUPPORTED`（“Supported opcodes: mov/add/mul only”），而不是 `BRANCH_RELOCATION_UNSUPPORTED`。
  行为仍拒绝，仅分类不准。

### S3 — “双端有效解码”措辞
- `reports/04-gen11-gen12-diff.md:8/17` 用“TGL 可解码”“双端有效解码子集”。这些 TGL 结果为 **IGA 未报错**，
  而字节是 Gen11 编译器产物，其 TGL 解码是巧合重解释，并非“有效的 Gen12 程序”。report04:3 已作提醒，
  但“有效”二字仍可能被读成“合法 Gen12 编码”。建议统一为“IGA 未报错的重解释”。

### S4 — 报告编号重复 / 前向引用
- `reports/` 存在**两份 08**（`08-upstream-source-audit.md`、`08-upstream-translator-evaluation.md`），
  且 `reports/FINAL-REPORT.md:37/49/66` 前向引用 `report05`/`report10`（05/06 由并发代理补齐、10 已存在），
  编号不唯一会使 FINAL 的交叉引用有歧义。

---

## 三、缺失/未完成项

- **`manifest.json` / `manifest.sha256`**（见 M1）。
- `reports/05`、`06`：审计开始时缺失，审计期间由并发代理生成；不在本审计范围。
- `reports/10-test-report.md`：存在；其“38 个 unittest 方法”与我在 `tests/test_translator.py` 数得的
  **38** 个 `def test_` 一致，`logs/test-translator.txt` 亦为 `Ran 38 tests … OK`。
- `reference/tgl-command-stream-source.json` 的机器可读来源只记录第三方镜像 URL（kiwitree.net），
  官方 `cdrdv2.intel.com/…/703062` 仅出现在 `official-prm-verification.md` 的散文里；建议把官方 URL 写入该 JSON。

---

## 四、六个焦点逐项结论

### 1) EOT 边界 / CFG / predication
- **边界可复现**：`window = 捕获记录1[0x82A0:+8192]`；`ps = window[0x40:0xD8]`（152B）、`vs = window[0x3C0:0x4E0]`（288B），
  与 `analysis/ps-bounded.bin`/`vs-bounded.bin`、`extraction.json` 的 slice 哈希全部一致（我逐一重算）。
- **边界规则**：取“从入口线性解码中遇到的**第一条 EOT**”（`isa_analyze.py:44-59`）。对这两个入口成立；
  但该规则**不证明**入口之前没有更早 EOT、也不证明程序不会被非直线方式进入——属合理假设，report03:10 已限定范围。
- **CFG**：`:107` 只是“每条→下一条”的线性后继链；因 `control_flow=0` 该链即实际控制流，但称之为 CFG 偏高，
  且其正确性依赖“无分支”这一已检查事实。
- **predication**：见 **M2** —— 标签未经验证，且数据里存在 7 条写使能指令。

### 2) IGA 输出 vs shader 语义声明
- 我逐条比对 `analysis/{ps,vs}-{icl,tgl}.asm`、`isa-diff.md/json` 与原始窗口字节，**反例精确复现**：
  VS`+0x00` 同 8 字节 compact，ICL `mul (8|M0) acc0.0 r2.0 r4.0` ↔ TGL `mul (16|M0) r2.3 -r32.3 r4.0 {$11.dst}`；
  PS`+0x10`/VS`+0xf0` ICL `mov dbg0.0 0:w {Switch}` ↔ TGL 可解码 `sync.nop null`；PS/VS 的 SEND 在 TGL 报 GED 解码错误。
- **范围诚实**：report04 末尾与 FINAL-REPORT 都明确“这证明编码不等义，不是已证唯一 hang 因果/更未证明硬件执行”；
  `GPU_HANG_ROOT_CAUSE = PARTIAL` 的降级是对旧结论的正确纠正。
- 唯一措辞问题见 **S3**。`ISA_INCOMPATIBILITY=CONFIRMED` 本身对任何两代 ISA 都是“同比特解码不同”的同义反复，
  报告已把它限定在编码层，故不构成过度声明。

### 3) flags / roundtrip 源语义比对
- 我独立运行原型：`(f0.0) add …` 与无谓词版本字节不同、`normalized` 不等（谓词计入 `freg`）；`(sat)` add 往返通过；
  `(W)`/`wren` 被保留并比较；branch→`BRANCH_RELOCATION_UNSUPPORTED`，`sendsc … {EOT}`→`SEND_EOT_SEMANTICS_UNPROVEN`。
- **缺口**见 **M4**：主指令的 `regDist/sbid` 被排除且未另报。
- 次要：`report.json` 的 `unit['target_length']` 含自动 drain（16B/条），故“单位目标长度”不是纯指令长度；
  report09 已说明 drain 的存在，但读者需注意该数值含义。

### 4) 孤立单位 vs 完整 shader
- **处理干净**：任何单位被拒 → 顶层 `status=UNSUPPORTED`、退出码 1（`offline_translate.py:139,153`）；
  `full_shader_emitted` 恒 `false`；`scope='isolated instruction subset, not executable shader'`；
  每单位单独写 `unit-XXXX.bin`（`:136-137`）。我确认 `analysis/translated-ps/` 恰有 4 个、`translated-vs/` 恰有 15 个
  `unit-*.bin`，代码中**不存在**拼接为 shader 的路径。此项无过度声明。
- 细节：`:116-121` 的 `target_offset` 恒为 0（每个单位自成一段），report09 的“源偏移→目标 offset 映射”实为平凡映射，属表述冗余而非错误。

### 5) 不支持 / 溢出 / 分支 / SEND 的 fail-closed
- **已核验的强约束**：`:27-38` 显式 8/16B framing（<8B 或截断即 `TRUNCATED`）；1MiB 上限（`:28-29`，CLI 侧 `:151` 有界读）；
  `:127-130` 用“IGA 指令数/PC 与 framing 不一致”拒绝 `SOURCE_INVALID`；`:96-97` `ENCODER_REJECTED`；
  `:99-100` `TARGET_DECODE_FAILED`；`:104-108` drain 形状；`:109-110` 语义往返；`:113-115` 二进制往返。
- 拒绝路径我均独立复现：`unknown_invalid_opcode`（16 字节全零 → IGA 解为 `illegal`）被 `OPCODE_UNSUPPORTED` 拒绝；
  越界 `jmpi` 触发 IGA 非零退出 → 顶层 `SOURCE_INVALID`。
- 缺口见 **M5**（异常未结构化）与 **S2**（`join/do` 分类）。

### 6) 旧“排除 memory/CCS”错误 与 hash/provenance
- **旧结论纠正正确且可核验**：`reference/linux-v6.18-intel_gt_regs.h`（sha `2d131eb5…`）确实定义
  `GEN8_RING_FAULT_REG=0x4094`、`GEN12_RING_FAULT_REG=0xcec4`、`GEN12_FAULT_TLB_DATA0/1=0xceb8/0xcebc`；
  report07 §“一个关键证据缺口…”（审计期间该节由并发代理从 19–23 行重排到 27–31 行）与 FINAL-REPORT:8 的纠正与之一致，
  且 `analysis/rcs-evidence.json` 中 `actual_gen12_fault_register_captured=false`。旧“已排除显存/CCS”确被正确撤回。
  （并发修订新增的三代表我还原核对：context 顺序 6/5/6/5、HEAD `D4/14C/244/16C`、head PC 后写值 `4/5/9/10`，
  与 `analysis/rcs-evidence.json` 完全一致。）
- **report07 具体引用逐条核对无误**：`gpuRestart`（sha `42391262698c…`，ctx5）第 333–335 行
  `0xC4=18800101 426FD000 00000000`（MI_BATCH_BUFFER_START→`0x426FD000`）；第 367–372 行 head PC 六 DWORD
  `7A000004 00104598 40001040 0 5 0`；`0x134` 前一 PC 的 Gen12 `Tile Cache Flush Enable=1`；`+0x148` 是
  “Adjusted to previous instruction”标记而非真 RING_HEAD——全部与原始文件/JSON 相符。12 份 gpuRestart 计数相符。
- **hash/provenance 全部匹配**：捕获、ZIP、PS/VS 切片、`PROVENANCE.json` 中 13 个上游文件 + 9 个项目笔记的
  SHA-256 与 git blob SHA-1（我用 `git hash-object` 重算）、官方/镜像 PDF `8f69aa40…` 逐字节相同、
  本地 IGA HEAD `c36a504a…`、Mesa HEAD `86333827…`。
- **无法离线复验**：`PROVENANCE.json` 的“blob == 上游 tree”结论依赖联网 `git ls-remote`/GitHub tree，
  本轮禁网，只能确认“本地 blob 自洽”（必要非充分）。报告已标注该固定点为“本次快照”。
- 次要：见第三节关于官方 PRM URL 未写入机器可读来源。

---

## 五、已核验为正确（正面清单，供整合方引用）

1. 全部关键哈希（捕获/ZIP/切片/参考文件/PDF/IGA/Mesa commit）在本机重算一致。
2. PS0=152B/11 条、VS=288B/24 条；“旧 PS 896B 不是单一 shader”的判断被字节与首 EOT 位置支持。
3. TGL 重解码的具体反例（VS+0 的 SIMD8→16、MOV→SYNC、SEND GED 错误）逐条与真实 asm 相符。
4. 原型独立重跑得 PS 4/11、VS 15/24、`full_shader_emitted=false`、退出 1；predicate/`(sat)`/`(W)` 被保留与比较；
   branch/SEND/非有限浮点立即数/整型 ALU/类型转换/间接寻址按声明的 code 拒绝。
5. `evaluate_upstream` 的上游输出 152/152、288/288，IGA 目标解码 exit 0、二进制往返逐字节相同（我重算目标 sha 一致）；
   其“`OPERAND_FIELDS_MATCH_ONLY` / `UNPROVEN`”用词本身是保守的。
6. 旧 fault 排除结论的纠正与 07 的 ring 证据链准确；FINAL-REPORT 的 22 问答未发现数字性错误。

## 六、审计员无法覆盖

- 实机/硬件执行、Metal/加速、任何 GPU 运行正确性（本就超出本阶段声明）。
- 需要联网的上游 commit/blob 等价性（见四.6）。
- `reports/05`、`06`、`tests/test_batch.py` 及批次解码器（并发代理范围，按要求回避）。
- 本审计为抽样+定向复核，不等同于对全部 `logs/` 与 `analysis/` 的逐字节回归。

**总体判定**：离线证据的核心事实与失败闭合行为**成立且可复现**；但按 M1–M5 修复前，不应把
“证据完备 / 结构化拒绝 / 交付清单完整”作为该实验室的最终状态对外陈述。
