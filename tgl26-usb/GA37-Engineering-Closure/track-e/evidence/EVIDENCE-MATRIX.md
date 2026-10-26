# GA37 Track E · 证据矩阵（中文 · rev2）

> **rev2 修正说明**：本文件为对 rev1 的主代理评审修正。rev1 的原始回执（`INPUTS.json` SHA-256
> `11b2402b6d45fe41ce09c3c201727b20c628cc120658bfde1498643f3b592b61`、EVIDENCE-MATRIX.md SHA-256
> `98ede6ee3af005564c127b1493834e5aab60eecbbc356a812eff347ea63be354`）保存在 `CORRECTION-NOTE.md`。
> 修正内容见 `CORRECTION-NOTE.md` 第 1–4 条：①GA35/GA36 的 exact 25G83 KC 锚与阶段区分；②THAG 整文件哈希标注；
> ③H-A..H-F 与 USER A–F 两套矩阵；④去掉“4 shader 静态数据即可完全闭合/URB-RT payload ABI 由静态数据证明”的过度声明。

> 范围：只读索引。全部新工件仅写入 `GA37-Engineering-Closure/track-e/evidence/`。
> 未 SSH、未接触硬件、未部署、未改 IMG/EFI/固件、未执行上游代码、未写 GPU 命令/shader、未做公开检索。
> 无 Python import、无 pycache；仅 `sha256sum`/`stat`/`jq` 只读。`SOURCE_IMG = null`，`RESULT_IMG = null`，`real_mmio_backend = NONE`。
> 机器可读清单见同目录 `INPUTS.json`（rev2，163 项；含精确路径/SHA-256/字节数/schema/证据锚）。
> 本文件只转述既有固定报告与数据字段，不新增全 shader 解码、不重新扫描捕获、不重跑历史实验。

---

## 1. 四个真实 shader 内核（4 kernels）

来源：`GA32-ISA-Lab/reports/03-shader-boundaries.md`、`04-gen11-gen12-diff.md`、
`08-upstream-translator-evaluation.md`、`analysis/isa-diff.json`、`analysis/ps-variants.json`。

| 入口 | IBA 偏移 | 边界 | 字节 | ICL 指令 | compact/native | SEND | 分支 | EOT | TGL 未报 illegal | TGL illegal | 上游 Gen12 往返 |
|---|---|---:|---:|---:|---|---:|---:|---|---:|---:|---|
| PS0 | `+0x40` | `[0x40,0xD8)` | **152** | **11** | 3/8 | 2 | 0 | sendsc RT write `+0x88` | 5 | 6 | 11→11 逐字节相同 |
| PS KP1 | `+0x200` | `[0x200,0x3B8)` | **440** | **29** | 3/26 | 4 | 0 | SEND EOT `+0x1A8` | 17 | 12 | 29→29 逐字节相同 |
| PS KP2 | `+0x100` | `[0x100,0x1D8)` | **216** | **15** | 3/12 | 2 | 0 | SEND EOT `+0xC8` | 9 | 6 | 15→15 逐字节相同 |
| VS | `+0x3C0` | `[0x3C0,0x4E0)` | **288** | **24** | 12/12 | 2 | 0 | sends URB write `+0x110` | 13 | 11 | 24→24 逐字节相同 |

- 四入口共 79 条 ICL 指令、1096 B；三个 PS 共 808 B/55 条；旧 896 B 切片含 88 B 间隙/填充，**不是单一 shader**。
- **分支总数为 0**：四个真实程序均无分支。因此 GA38 的 **branch relocation 对当前实际语料并非必需**，
  应作为未来显式项单独处理，不在本轮推进（`reports/09`、`analysis/isa-diff.json` `branches=0`）。
- 这些“完整”仅指**指定入口到无条件 EOT**，不证明 hang 的 draw 执行到了它们，也不证明硬件合法。

---

## 2. 31 个隔离单位 vs whole-shader（SEND / NF / SWSB）

来源：`GA32-ISA-Lab/reports/09-translator-design.md`、`translator/offline_translate.py`、`reports/11-independent-audit.md`。

| 入口 | 隔离单位 | 该入口 ICL 指令 |
|---|---:|---:|
| PS0 | 4 | 11 |
| VS | 15 | 24 |
| PS KP1 | 8 | 29 |
| PS KP2 | 4 | 15 |
| **合计** | **31** | 79 |

- 等级：31 单位全部 `ROUNDTRIP_VALIDATED`（IR 字段比对 + 目标 exact binary 往返），**各自独立、不拼成 shader**。
- **whole-shader = UNSUPPORTED**：整 program 非零退出、`full_shader_emitted=false`，每项带 source offset。
- 31→whole 的缺口（事实）：
  - **SEND/SENDC/SENDS/SENDSC/EOT**：全拒（不猜 payload/descriptor/SFID）。
  - **MAD/MAC 与 NF**：全拒（accumulator/中间精度/舍入及隐含依赖未证）。
  - **acc/debug/其他 ARF**：全拒。
  - **Branch/JMPI/IF/ELSE/ENDIF/HALT**：支持范围外，但**当前语料无分支**，不作为 GA38 必需项（显式延后）。
  - mixed-type MOV、integer ADD/MUL、未知/invalid opcode：全拒。
- **SWSB**：单位级只校验自动 drain 形状，主指令自身 `regDist/sbid` 未比较。

**修正后的边界声明**：**不能**由 4 个 shader 的静态数据声称 URB/RT 消息 payload ABI 等价已经证明。
可做到的是：解析/建模 **raw 消息 descriptor** 并给出**参数化契约**，同时把 **payload 内容标为 UNKNOWN**；
这不构成具体的可执行语义（不证明消息在硬件上被正确解释）。

---

## 3. 命令类与资源原始捕获可用性（56 / 5 / 105）

来源：`GA34-Offline-Lab/track-a/packet-audit.json`、`state-ir.json`、`spec-diff.json`、
`prm-constraints.json`、`GA32-ISA-Lab/reports/05`、`12`。

冻结 batch 窗口 `0x426F7000`，ring 关联入口 `+0x6000`，END `+0x7100`；166 packet / 1089 DWORD。

| 分类 | 数量 | 含义 |
|---|---:|---|
| VALID_TGL_PACKET_SUBSET | **56** | 55 个全零 `MI_NOOP` + 1 个 canonical `MI_END`；仅包级语义 |
| EXPLICITLY_NONCONFORMING | **5** | 1 个旧 `STENCIL_BUFFER` 5DW（TGL 要求 8DW）+ 4 个 draw `extended=0` 却 10DW（PRM 要求 7） |
| UNKNOWN | **105** | 资源/继承/字段/编程限制等证据缺口 |
| （格式层通过） | 161 | 仅通过格式层，**不是 161 条已证合法 TGL 命令** |
| 需 heap 引用 | 33 | 资源依赖，离线无法闭合 |
| 需继承未知 | 2 | 继承前态未知 |

**资源/二进制可用性（修正：区分 binary 与 raw resource）**：

| 项 | 可用? | 说明 |
|---|---|---|
| batch 8 页 32768 B | ✅ | 记录 1 派生 `+0x2A0..0x829F` |
| shared EU window 8192 B | ✅ | 记录 1 派生 `+0x82A0..0xA29F` |
| THAG 整文件 99648 B（2 条 v2 记录） | ✅ | 冻结副本与原始一致 |
| 12 份 gpuRestart | ✅ | GA2/GA31/GA32 私有归档 |
| 官方 TGL PRM、Linux 寄存器头 | ✅ | 已固定 hash |
| **exact Apple 25G83 KC（SystemKC/BootKC/AuxKC）** | ✅ **可用** | GA35 原件（SystemKC `fbab2d48…`、BootKC `c80161fa…`、AuxKC `5d617058…`）+ 身份/符号/线性反汇编；GA36 以同一 SystemKC 完成 24 函数字节校验 PASS |
| **原始 PTE 字节** | ❌ | 只有记录值 `kernelPhys=0x3E9026000`；“共享物理页”未独立证 |
| **Surface/Binding/Sampler/Dynamic heap 内容** | ❌ | 资源缺席清单缺 |
| **RT 布局/view/aux/CCS/compression** | ❌ | 未捕获 |
| **vertex/constant 数据、thread payload** | ❌ | 未捕获 |
| **CSB/execlist 时间序列** | ❌ | 无有界事件流 |
| **Gen12 fault 0xCEC4/0xCEB8/0xCEBC** | ❌ | 旧 `0x4094` valid=0 |
| **Apple MOCS 寄存器编程值 / stepping / workaround** | ❌ | 与 binary 无关，仍缺 |
| **运行态指令/接收者认证、独立 KASLR slide** | ❌ | KC 原件已有，但不含运行态字节 |

- **阶段区分（修正 1）**：GA34 报告“exact AppleIntelICLGraphics 25G83 binary/disassembly not located”
  是 **GA34 当时的历史状态**；**当前阶段** GA35 已取得 exact 25G83 KC 原件并完成身份/线性反汇编，
  GA36 复用同一 SystemKC raw bytes。**缺失的是 raw heap/MOCS 编程/运行态认证，而非 25G83 binary 本身。**
- `state-ir.json.unknown_heap = RESOURCE_DATA_MISSING` 指的是 heap/资源数据缺失。

---

## 4. THAG 有效性（修正 2：整文件哈希）

- **`1622ecc2aecdcc85ae45dcf86e4219338f6e41e0243b27d5e7128a9999f13333` 是 THAG 整文件
  （99648 B、两条 v2 记录）的 SHA-256，不是记录 1 的 SHA-256。**
- 记录 1 派生的字节（batch 8 页、VS/PS 窗口）可用，但必须与整文件哈希**分开标注**，不得把整文件哈希写成
  “记录 1 哈希”。
- 副本：`GA34-Offline-Lab/inputs/THAG.bin` 与 `GA32/capture/tgl-hang-GA32b-crash-20261018.bin` 同整文件 hash；
  `GA32-ISA-Lab` 559 文件清单、`GA34-Offline-Lab` 408 文件清单、`GA35` 471、`GA36` 233 在本机核验全匹配。
- **本索引对 THAG 的效果为 NONE**：不重解释、不重判、不失效（**don't invalidate valid THAG**）。

---

## 5A. 历史根因竞争假设 H-A..H-F（显式标注，非用户 A–F）

来源：`GA32-ISA-Lab/reports/07-rcs-hang-root-cause.md`（竞争假设矩阵）。**这是历史 hang 根因假设，不是用户请求的工程方向。**

| 标签 | 假设 | 已确认事实 | 缺失 | 证据锚 |
|---|---|---|---|---|
| **H-A** | EU ISA 不等义 | 编码层 CONFIRMED；VS+0 compact MUL SIMD8→16 反例 | 逐线程执行轨迹 | `reports/04`、`analysis/isa-diff.json` |
| **H-B** | Kernel/Batch 地址 | 指针位布局/边界可验；ring BBS 入口 | 原始 PTE/alias/时序 | `reports/07`、`analysis/rcs-evidence.json` |
| **H-C** | Surface/内存状态 | 命令字段可解析 | surface/tiling/binding/sampler/payload | `reports/06`、`analysis/pipeline-snapshots.json` |
| **H-D** | Cache/CCS/Resolve | 代际差异可审 | aux/CCS/fastclear、PC 目的地 PTE、flush、0xCEC4 | `reports/07` |
| **H-E** | CSB/Execlist | ctx 切换与 hang 可记 | CSB 事件流 | `reports/07` |
| **H-F** | 其他跨代状态/命令 | stencil 5DW vs 8DW；draw extended=0 却 10DW | 硬件处置、首个故障、URB/payload/WA | `reports/12`、`GA34 track-a/stencil-proof.json`、`draw-proof.json` |

---

## 5B. 用户请求的工程方向 USER A–F × 8 维度（修正 3）

USER A–F：**A 整 4-shader 翻译**、**B 命令状态变换**、**C resource ABI**、**D 上游翻译器修复**、
**E 已知简单原生 TGL pipeline**、**F 完整原生 TGL 驱动/编译器**。

8 维度（主代理指定）：**code-distance / offline-proof / extra-data / Fault dependency / difficulty / memory-safety / acceleration-benefit / small-intermediate**。

| 方向 | code-distance | offline-proof | extra-data | Fault 依赖 | difficulty | memory-safety | 加速收益 | small-intermediate |
|---|---|---|---|---|---|---|---|---|
| **A 整 4-shader 翻译** | 中（31单位→whole；无分支故无需重定位） | 中-高（ISA 可静态证；URB/RT 消息 payload ABI 不可由 4 静态程序单独证） | 低（ISA）；消息 payload 内容缺 → 参数化契约 + UNKNOWN payload | 否（静态） | 高（NF/acc/SEND/SWSB + 消息契约） | 分析期无；日后写回改 GPU 输入需独立授权 | 中（仅当消息 ABI 也正确） | 有（逐指令静态语义矩阵 + 参数化消息契约，含 UNKNOWN payload） |
| **B 命令状态变换** | 中（parser/state-IR/normalizer 已有） | 中（格式层可证；33 需 heap 包不可离线闭合） | 高（surface/binding/sampler/constant heap） | 判定是否首个故障需真实 fault | 中 | 中（改 GPU 命令，风险高于只读） | 中 | 有（5 缺陷规范闭合 + 格式分类表） |
| **C resource ABI** | 大（无 resource ABI 模型） | 低（资源原始捕获缺） | 极高（PTE/heap/surface/sampler/payload） | 是 | 很高 | 高（资源访问越界） | 高（若为根因） | 弱 |
| **D 上游翻译器修复** | 小（上游 tgl-xlate 固定源已在本地） | 中（可对 4 shader 测，whole 语义仍缺） | 低-中 | 否 | 中 | 高（上游 stolen/半翻译 machine-check 风险，GA10） | 中（上游未达稳定桌面，覆盖不全） | 有（修复特定拒绝类） |
| **E 已知简单原生 TGL pipeline** | 很大（无现有原生 pipeline） | 低-中 | 极高 | 是 | 极高 | 极高 | 高 | 无 |
| **F 完整原生 TGL 驱动/编译器** | 极大 | 极低 | 极大 | 是 | 极高 | 极高 | 极高 | 无 |

**修正后的推荐（事实 + 建议，最终唯一选择归主代理）**：

- 在缺失资源捕获的现实下，**USER-A** 的静态 ISA 部分主要由 **4 个真实 shader 静态数据**支撑，
  但这**不等于由 4 静态数据即可完全闭合**：URB/RT 消息 payload ABI 等价需要运行时 payload，
  只能建模 **raw 消息 descriptor + 参数化契约**并显式保留 **UNKNOWN payload**，不构成具体可执行语义。
- **USER-B** 的 5 缺陷格式层是**更小的中间可交付**，但其 33 个需 heap 的包离线不可闭合。
- **USER-C/D/E/F** 分别受资源捕获缺失、上游覆盖不全与机器检查风险、以及范围过大所限；
  E/F 直接依赖真实 fault 与完整原生实现，离线不可独立闭合。
- 当前语料**无分支**，故 **branch relocation 不是 GA38 必需项**，显式延后为未来项。
- **FINAL unique GA38 方向选择由主代理决定**；本文件只给事实、维度与锚点，不代主代理决策。

---

## 6. exact Apple 25G83 二进制锚（修正 1）

| 项 | 值 | 来源 |
|---|---|---|
| 版本 | 26.6.2 / **25G83** / x86_64 / XNU 12377.161.14~5 | `GA35-Driver-Reversing/25G83-BINARY-IDENTITY.md` |
| SystemKC | 361922560 B `fbab2d48bf1470fb0ec15dd62a6bb90c39d8bb45ed68240d3c73f1e43e770dee` | `GA35-.../inputs/macos-readonly/System/Library/KernelCollections/SystemKernelExtensions.kc` |
| BootKC | 67584000 B `c80161fa3065883753fc285339281361a8469cbb6fb27653c88e2a22eb4807a4` | 同上 |
| AuxKC | 917504 B `5d6170588133eae3fe1d4f0024f67960f0ce6aeb6d2f3266e9865d96ddfa8fcd` | 同上 |
| AppleIntelICLGraphics | 24.0.5, UUID `B7DF3049-D3A9-3070-9843-6E5AE47673D7`, KC offset `0x13e9f000`, 5440 符号 | `analysis/binary-identity.json`、`analysis/kc/*.symbols.json` |
| 运行 VA 规则 | `runtime VA = KC-coordinate VA + 0xffffff7f80ce5000`（load bias，**非**独立 KASLR slide） | `25G83-BINARY-IDENTITY.md` |
| GA36 复用 | 24 函数 raw KC 字节检查 PASS（SystemKC SHA + 24 切片 + UUID-SHA） | `GA36-Fault-Safety/logs/track-b-main-verification.txt` |

---

## 7. 证据锚索引（顶层）

- GA32：`reports/{03,04,05,06,07,08-*,09,10,11,12,FINAL-REPORT}.md`；`analysis/{isa-diff.json,ps-variants.json,translated-*/unit-*.bin,*.asm,upstream-*-gen12.bin}`
- GA34：`track-a/{state-ir.json,packet-audit.json,spec-diff.json,stencil-proof.json,draw-proof.json}`；`track-a/shadow-batches/*`；`track-c/next-experiment-ranking.md`
- GA35：`25G83-BINARY-IDENTITY.md`；`inputs/macos-readonly/**/KernelCollections/*.kc`；`analysis/{binary-identity.json,hook-abi.json,kc/*.json,disassembly/*.txt}`
- GA36：`state.json`；`manifest.json`；`track-b/analysis/{focused-fragments.json,bounded-xref.json,verify_track_b.py}`；`logs/track-b-main-verification.txt`
- 原始：`GA32/capture/tgl-hang-GA32b-crash-20261018.bin`（整文件 `1622ecc2…`，2 记录）

逐项精确路径 / SHA-256 / 字节数 / schema / 已证-未知见 `INPUTS.json`（rev2，163 项）。
