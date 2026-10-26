# GA37 · Track E 证据/路线图 独立审查 AUDIT

- 审查对象：`track-e/ACCELERATION-OPTIONS.md`、`track-e/GA38-TECHNICAL-PLAN.md`、`track-e/RESEARCH-PRIORITIES.md`、`track-e/evidence/*`。
- 审查范围：只读核对本目录三份主文档 + `evidence/` 索引的事实、路径、哈希、维度、计数与边界声明；不重跑历史解码、不做公开检索、不执行上游代码。
- 约束遵守：未 SSH、未接触硬件、未部署、未改 IMG/EFI/固件/NVRAM、未写 GPU 命令或 shader。全部只读命令为 `sha256sum`/`stat`/`jq`/`git log -1`/`grep`；未使用 Python，未产生 `__pycache__`。仅新增本文件 `track-d/roadmap-review/AUDIT.md`；**未修改** primary 文档、`state.json`、`history.json`、`continuation.md`。
- 结论：**13 项必查点全部 PASS，未发现阻断性事实错误或过度声明。** 3 项为标签/计数措辞与记录完整性观察（无阻断，见第 3 节）。

---

## 1. 逐项核对

| # | 必查点 | 判定 | 证据（路径:行 / 命令实测） |
|---|---|---|---|
| 1 | 唯一 GA38 方向 | PASS | `track-e/ACCELERATION-OPTIONS.md:3`「唯一推荐」；`GA38-TECHNICAL-PLAN.md:3` `GA38_DIRECTION = FOUR_SHADER_MESSAGE_DEPENDENCY_IR_AND_GEN12_CANDIDATE_VALIDATOR`；`RESEARCH-PRIORITIES.md:1`；`state.json`(`ga38_direction`)；`tools/delivery_audit.py:27` expected 同值。全文无第二条并列主线。 |
| 2 | 用户 A–F × 8 维度 | PASS | `ACCELERATION-OPTIONS.md:15-24`，表头 `:17` 为「候选 + 距离当前代码/可离线证明/额外数据/是否依赖新Fault/难度/内存安全风险/对真正加速的贡献/较小中间成果」= 8 维；`evidence/INPUTS.json` `user_task_matrix_A_F.dimensions` = `code_distance, offline_proof, extra_data, fault_dependency, difficulty, memory_safety, acceleration_benefit, small_intermediate`（一一对应）。`A–F` 六候选齐全。 |
| 3 | 8 项技术计划 | PASS（措辞见 §3.1） | `GA38-TECHNICAL-PLAN.md` 有 8 个编号小节 `## 1.`–`## 8.`（实测 `grep '^## '`=8），且 `:39-48`（§4）实测 8 条验收标准 `* `。计划清单本身存在且唯一。 |
| 4 | 输入路径在文中存在 | PASS | `GA38-TECHNICAL-PLAN.md:17` THAG → `GA32/capture/tgl-hang-GA32b-crash-20261018.bin` 存在；`:18` `GA32-ISA-Lab/analysis/ps-variants.json`、`isa-diff.json`、`reports/03-shader-boundaries.md` 存在；`:19` `analysis/{ps,ps-kp1,ps-kp2,vs}-icl.asm` 4 份存在；`:20` `analysis/upstream-{ps,ps-kp1,ps-kp2,vs}-gen12.bin` + `upstream-semantic-review.json` 存在；`:21` `analysis/translated-{ps,vs,ps-kp1,ps-kp2}/{report.json,unit-*.bin}` 存在；`:23` GA34 `state-ir.json`/`stencil-proof.json`/`draw-proof.json` 存在。 |
| 5 | 哈希 64-hex 且与实物一致 | PASS | `evidence/INPUTS.json` `files[]` 共 **163** 条，逐条 `sha256` 全部匹配 `^[0-9a-f]{64}$`、路径唯一、磁盘全部存在（实测 loop，无缺失/无重复）。文中完整哈希抽验：THAG 整文件 `1622ecc2aecdcc85ae45dcf86e4219338f6e41e0243b27d5e7128a9999f13333`(=99648B, `GA32/capture/...` 与 `GA34-Offline-Lab/inputs/THAG.bin` 双方一致)；SystemKC `fbab2d48…`、BootKC `c80161fa…`、AuxKC `5d617058…` 三份 `sha256sum` 实测一致；PS0 上游 `146d5896…` 实测一致。 |
| 6 | 历史 A–F 未被混淆 | PASS | `evidence/EVIDENCE-MATRIX.md:118` §5A 显式标注「历史根因竞争假设 H-A..H-F（非用户 A–F）」；`:133` §5B「用户请求的工程方向 USER A–F」；`ACCELERATION-OPTIONS.md:13`「以下使用用户本轮 A–F 定义」；`evidence/CORRECTION-NOTE.md` 修正 3 记录两套矩阵拆分。全文未把历史假设写成无前缀 A–F。 |
| 7 | 当前 KC 可用、payload 缺失 | PASS | `INPUTS.json` `available_apple_binary`（SystemKC 361922560B/C80161FA 等）与 `resource_raw_capture.not_available`（原始 PTE、Surface/Binding/Sampler/heap、RT/aux/CCS、vertex/constant/thread payload、CSB、Gen12 fault 三寄存器、MOCS、运行态认证/KASLR slide）并存；`EVIDENCE-MATRIX.md:99-102` 明确 GA34「未取得 binary」为历史状态，当前 binary 可用、缺的是 raw heap/MOCS/运行态。 |
| 8 | 31 单位 ≠ whole 79 程序 | PASS | `INPUTS.json` `strict_units.total=31`、`whole_shader=UNSUPPORTED`；`GA32-ISA-Lab/reports/09-translator-design.md:9-10`；四份 `report.json` 实测 `validated_units` = 4/8/4/15、`status=UNSUPPORTED`、`full_shader_emitted=false`、`hardware_execution_validated=false`。文档均称 31 单位「不拼成 shader」，79 条为**源 ICL 指令**，非已译程序。 |
| 9 | 无分支语料，不虚设 branch 要求 | PASS | `INPUTS.json` `shader_totals.branches_total=0` + `branch_note`；`isa-diff.json` ps/vs `branches=0`，`ps-variants.json` KP1/KP2 `boundary.branches=[]`；`EVIDENCE-MATRIX.md:30-31`；`GA38-TECHNICAL-PLAN.md:11`「无branch…输入出现branch必须拒绝」、`:46`「不要求本轮实现 generalCFG/branchreloc」。 |
| 10 | F/NF 未知，不冒充设备信心 | PASS | `GA38-TECHNICAL-PLAN.md:45` NF 精度不明不得以随机 float 宣告等义、否则保持 UNKNOWN；`:34` 不设 `hardware_validated=true`；`ACCELERATION-OPTIONS.md:24`（F）「不证明系统二进制兼容」、`:30` READY≠部署批准；`RESEARCH-PRIORITIES.md:4` E/F 不选作核心。离线/模拟未升格为设备级结论。 |
| 11 | 无 GA38 代码 | PASS | 树内 `find` 无 `corpus.py`/`semantic_ir.py`/`message_ir.py`/`dependency_graph.py`/`gen12_schedule_check.py`/`compare_program.py`；唯一 `*GA38*` 命中为计划本身 `track-e/GA38-TECHNICAL-PLAN.md`；`GA38-TECHNICAL-PLAN.md:5`「GA37 只交付本计划，无 GA38 新实现」；`history.json` ga37-005 `limitations`「Roadmap only; noGA38code」。 |
| 12 | 无硬件批准 | PASS | `state.json:7` `"hardware_approval": "NO"`；`ACCELERATION-OPTIONS.md:30` `READY_FOR_HARDWARE_APPROVAL=NO`；`GA38-TECHNICAL-PLAN.md:58`「## 7. 后续硬件准入（本计划不批准）」、`:60`「不得将 GA38_OFFLINE_ENTRY READY 解释为 hardwareREADY」。 |
| 13 | 文中 PS 偏移 vs ps-variants/reports 一致 | PASS | 实测：`isa-diff.json` ps `entry=64(0x40)`/len152、vs `entry=960(0x3C0)`/len288；`ps-variants.json` ps-kp1 `entry=512(0x200)`/len440、ps-kp2 `entry=256(0x100)`/len216；`reports/03-shader-boundaries.md:7-10` 同值，指令数 11/24/29/15。与 `EVIDENCE-MATRIX.md:24-27`、`GA38-TECHNICAL-PLAN.md:18`、`ACCELERATION-OPTIONS.md:7`（152/440/216/288 与 11/29/15/24）逐项一致；三者共 808B/55 条、合计 1096B/79 条亦自洽。 |
| 14 | 固定工具 pin，含 IGA c36a504a | PASS | `GA38-TECHNICAL-PLAN.md:22` 与 `INPUTS.json` `frozen_baselines.pinned_sources` 一致：IGA `c36a504a4e6c68030c3302646aa396b8b59b22cb`（实测 `tools/iga/source` HEAD 同值）、Mesa `863338275d915e867319c3690ffd3272b06303c3`（实测 HEAD `VERSION: bump for 23.3.6`）、上游 translator `1010490d3421628c9d6fd0bd518b6c4b6f8ee33c`（实测见 `reference/PROVENANCE.json:11`）。均为 40-hex commit，另 `146d5896…` 等 SHA-256 为 64-hex。 |

## 2. 关键交叉核验（原文断言 → 实测）

- `ACCELERATION-OPTIONS.md:8`「上游四份…将 `acc0:nf` 换 `r122:f`、debug ARF `{Switch}` 换 `mov null,0`」：与 `GA32-ISA-Lab/reports/08-upstream-translator-evaluation.md`「仍不能称为等义完整 Shader」一致（真实字节/映射见 `analysis/upstream-semantic-review.json`）。
- `ACCELERATION-OPTIONS.md:9`「完整 Shadow 在 PIPE_CONTROL 就拒绝」：实测 `GA34-Offline-Lab/track-a/strict-shadow-result.json` = `{"status":"REJECTED","code":"TARGET_FORMAT_UNVERIFIED","detail":"PIPE_CONTROL"}`；`track-a/reports/command-compatibility.md:40` 同义。
- 命令分类 56/5/105/161/33/2：与 `INPUTS.json` `command_classes` 及 `EVIDENCE-MATRIX.md:71-78` 一致。
- 25G83 身份：`EVIDENCE-MATRIX.md:165-172` 的版本 26.6.2/25G83/XNU12377.161.14~5、三 KC 字节数（361922560/67584000/917504）、`runtime VA = KC-coordinate VA + 0xffffff7f80ce5000` 与 `GA35-Driver-Reversing/25G83-BINARY-IDENTITY.md` 一致。
- rev1 回执链：`evidence/CORRECTION-NOTE.md` 所列 rev1 `INPUTS.json=11b2402b…`、`EVIDENCE-MATRIX.md=98ede6ee…`、`build-inputs.sh=c1b03a87…`、`assemble.jq=7b8d3e09…` 与 rev2 `INPUTS.json` 的 `revisions[]` 自洽；当前文件实测哈希已等于 rev2（`INPUTS.json=ad20876a…` 等），说明 rev2 覆盖且历史回执保留。

## 3. 观察与措辞更正（均无阻断；本次未改动被审文档）

### 3.1 「8 项具体计划」的计数指代（信息性）
`track-d/REQUIREMENTS-CHECKLIST.md:22` 与 `continuation.md:23` 用「8项具体计划」指代该计划。`GA38-TECHNICAL-PLAN.md` 实际含 **8 个编号小节**（§1–§8）与 **8 条 §4 验收标准**，但 **§3 代码模块清单实测为 7 项**（`corpus.py / semantic_ir.py / message_ir.py / dependency_graph.py / gen12_schedule_check.py / compare_program.py / tests/+emit_report.py`）。
- 建议：若以「8 项」为准，应把它绑定到 §1–§8 小节或 §4 的 8 条验收；若以 §3 实现模块为准则为 7 项。二者不一致只是命名问题，不影响方向与内容。**本文不改 primary 文档，仅记录。**

### 3.2 输入 row 的单/多文件覆盖面（信息性）
`GA38-TECHNICAL-PLAN.md:18` 用一行同时引用 `ps-variants.json` 与 `isa-diff.json` 作为「4 入口边界/原bytes」。实测：`ps-variants.json` 只含 `ps-kp1`/`ps-kp2` 两程序，`isa-diff.json` 只含 `ps`/`vs` 两程序；**两文件合起来**才覆盖 4 入口。该行已同时列出两文件，故表述成立；若被单独解读为「任一文件覆盖 4 入口」则该理解不成立。

### 3.3 记录完整性（流程观察，非文档错误）
`history.json` 最新事件为 `ga37-005-integration-and-audit-fixes`，其中以证据路径提及 `track-e/GA38-TECHNICAL-PLAN.md`，但 Track E 的 **rev1→rev2 修正（含 A–F 重映射、163 输入、THAG 整文件哈希作用域、25G83 KC 阶段）** 目前只在 `continuation.md:23` 与 `evidence/CORRECTION-NOTE.md` 留痕，尚未作为独立 history 事件追加。按 AGENTS「每次有意义修订应追加历史事件」的口径，这是一个**待补记录项**；本次审查按指令不写 `history.json`，故仅记录，供主代理最终整合时决定。

## 4. 未验证 / 不在本次范围

- 未重算 `files[]` 中每个 64-hex 与物件的实际字节（只校验格式、路径存在性与关键锚点哈希）；全量重算属交付 seal 职责。
- 未验证「79 条源指令 ↔ 上游候选」逐字节语义等价（计划本身也只主张编码级 `ROUNDTRIP_VALIDATED`，未主张整 shader 等义）——与文档一致，非缺口。
- 未评估 Track E 之外的 Track A–D 交付；本 AUDIT 只覆盖 roadmap/Track E。
- 未做任何公开检索或新硬件/新解码；所有结论来自既有 `GA32/GA34/GA35/GA36` 工件与 `track-e/` 文档，每事实不超过一个既有来源。

## 5. 判定

Track E 三份主文档与 `evidence/` 索引在方向唯一性、用户 A–F × 8 维、8 项计划、输入路径/哈希、历史 A–F 与用户 A–F 分离、当前 KC 可得 vs payload 缺失、31 单位 vs whole、无分支语料、F/NF 未知定位、无 GA38 代码、无硬件批准、PS 偏移与工具 pin 上**全部自洽且与既有真实工件一致**。仅有 2 处标签/计数措辞可细化（§3.1、§3.2）与 1 处历史事件待补（§3.3），**均不构成事实错误、过度声明或硬件放行**。`READ_SAFE=BLOCKED / FAULT_DATA_COHERENT=UNKNOWN / REAL_MMIO_BACKEND=NONE / READY_FOR_HARDWARE_APPROVAL=NO` 维持不变。
