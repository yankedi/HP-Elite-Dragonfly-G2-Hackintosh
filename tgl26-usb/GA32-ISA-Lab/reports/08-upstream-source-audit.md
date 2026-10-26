# 08 · 上游源码与来源审计（Gen11→Gen12 EU 翻译器参考）

- 日期：2026-10-18；离线、只读。**未**构建、未跑 VM、未连目标机、未改 `/tmp/opencode/ga33`、未动 HP/介质/EFI。
- 审核对象：参考项目 `holdmysocks/latitude-7320-detachable-hackintosh` 的 `LAYER4.md`、`0004-tgl-accelerator.patch`、`tgl-xlate/`，以及本项目 `/tmp/opencode/ga33` 的 `tools/tgl-xlate` 与 `research/*`。
- 归档：[`../reference/`](../reference/README.md)（`PROVENANCE.json` + 上游快照 + 本项目分析快照）。

> 术语：本报告中的 **GA4–GA11** 指参考项目 `LAYER4.md` 记录的 2026-10-08 实机运行（kext 0004a–0004f）；与本项目的 `WhateverGreen-GA3.1/3.2/3.3`（hang 采集诊断）是两条不同实验线，勿混淆。

---

## 1. 来源固定（可复核）

| 依赖 | 固定点 | 校验方式 | 置信度 |
| --- | --- | --- | --- |
| 参考项目 | `1010490d3421628c9d6fd0bd518b6c4b6f8ee33c`（main HEAD） | `git ls-remote`；**归档每个文件的 git blob SHA-1 均等于上游 tree 同路径 blob** | 已核实 |
| Mesa（翻译器依赖） | tag `mesa-23.3.6` → `863338275d915e867319c3690ffd3272b06303c3` | `git ls-remote`；本地 sparse checkout HEAD 相同 | 已核实 |
| Intel IGA | `c36a504a4e6c68030c3302646aa396b8b59b22cb`（当时 IGC master HEAD） | `git ls-remote` == 本地 `tools/iga/source` HEAD | 本次已固定 commit；master 分支日后可变化，并非 tag |

关键文件 SHA-256（完整清单见 `reference/PROVENANCE.json`）：

- `LAYER4.md` `34f1a3809c5ca2d4589a894ddf9d6145a686143ae83615126e8658b5e01a279f`
- `0004-tgl-accelerator.patch` `42c5ac94dddbb13b0338c9ff9b2e80d8cbb50464bbe7dee7ff01a6e896c02a1c`
- `tgl_xlate.c` `a50c3da141857695b7f487e0377644c2b120de11ba999da30feedc1412d101f7`
- `xlate-GA11.txt` `9e17c2bf4a04de225c0c3af543d91c8f3f13cb9cade77b896c0366f1cd6dcb5f`

**缺口**：归档的上游 `tgl-xlate/` 是 `/tmp/opencode/ga33` 中存在的那一份子集；上游另有 `eu-stubs/`、`kshim/`、`kruntime.c`、`stub/`、`fzbuild.sh`、`a1_3src_helpers.h`（本地 Linux 适配副本在 `tools/tgl-xlate`）。`xlate-GA7..GA10`、hang/csb/panic 日志未归档。参考机型是 i5-1140G7/7320，本项目是 i5-1135G7/9a49/**25G83**，寄存器与偏移仅供参照，未经本机确认。

---

## 2. GA4–GA11：实现了什么、为什么没有稳定桌面

`LAYER4.md:191-208` 的运行表 + `:167-181` §6：

| 运行 | 新增 | 结果（上游报告） |
| --- | --- | --- |
| GA4/GA5 | 6 槽 CSB 读取 | 事件 65/90 次；GPU 每 ~10s 挂死，VS 忙（Gen11 ISA） |
| GA6 | `igfxtglhang=1` | 捕获 hung batch 与其 kernel：**Gen11 机器码** |
| GA7 | `igfxtglxl=1` | 翻译 15/拒 6；旧 hang 消失，被拒 PS 仍挂 |
| GA8 | sync 插入、分支、增长 | 翻译 18/拒 1 |
| GA9 | 精确寄存器跟踪 | **首次出画**；249 译/145 拒 |
| GA10 | jmpi、寄存器描述符、36KB | 1231 译；**读 stolen 触发 machine check** |
| GA11 | RAM-only、goto/join、间接、padding、100KB | 2049 译/52 拒；无 panic，残余 hang |

**没有稳定桌面的直接原因（§6）**：
1. **未被翻译的 340KB 像素着色器**（GA11 九份）——只读到 100KB，首条是无条件 `jmpi +335432`；0004g 提到 700KB（本仓库实现为 `XlatePages=176`≈704KB，patch `kern_igfx.hpp` 注 **L1072**）。
2. **驱动自身的 resolve 批次**（RECTLIST draw + `3DSTATE_PS` 带 RT fast-clear + 永不完成的 `PIPE_CONTROL`）——疑为 Gen11 CCS_D 在 TGL 变成 MCS、需要 aux-map，未证实；0004g 用 `igfxtglres` 跳过作实验（patch **L782-795**）。
3. **一份已翻译仍挂的 8 像素 kernel**，16/32 像素变体未捕获。
4. **从未覆盖**：compute/media kernel、驱动 blit kernel、message descriptor 与 thread payload 差异，以及"画出来是否正确"。

残余的挂死**签名**与本项目观测相似：RCS `IPEHR=0x7A000004`(PIPE_CONTROL)、`INSTDONE=0xFFDFFFFB`(VS/CS 未完成)。旧 `reference/project-analysis/RCS-HANG.md` 将“batch 已跑完、ISA 导致 hang、不是显存/CCS 问题”写为确定结论，**本轮不接受这些排他因果推断**；签名相似不能证明机制相同。GA10 machine check 与本机 fail-closed 叶子拒绝仅为保留内存访问风险的参照，也没有证据证明被拒页就是 stolen。以本轮 reports/07 的竞争假设矩阵为准。

---

## 3. 已实现的翻译规则（`tgl_xlate.c`）

- **通用 1→1 重编码** `:278-318`：dst/src 直接与 `g[a0.n+imm]` 间接、立即数、条件修饰符、MATH function。
- **SEND 家族** `:133-187`：`sends/sendsc`→`send/sendc` 双 payload；描述符可为立即数、`a0.0`、`a0.n`（`ex_const` 常量折叠 `:146-173`）。
- **三源** `:189-250`：仅 MAD/CSEL/BFE/BFI2；`LRP` 直接拒（`:242`）。
- **流控** `:253-269`：IF/ELSE/ENDIF/WHILE/BREAK/CONTINUE/HALT、JMPI（立即）。
- **原始 opcode** `:106-122`：`goto 0x2E`、`join 0x2F`（Mesa 表不含 join）。
- **thread-switch hint**：`mov ARF 0xF0,0` → `mov null,0` `:124-131`（保留为有序指令以维持 `@1` 语义）。
- **NF 累加器** `:199-214`：改用内核未命名的空闲 GRF（float），寄存器从 127 向下找（`:726-738`）。
- **软件 scoreboard（SWSB）** `:413-562`：默认 `@1`；每个 send 取 token；消费者用 `$n.dst`，否则插入 `sync.nop`；**分支前与跳转目标前等待全部未决 send**，保证各路径状态一致（`:520-526`）。

## 4. 未实现/被拒绝的规则（风险面）

| 位置 | 拒绝/缺口 | 影响 |
| --- | --- | --- |
| `:80-85` | unknown opcode / `align16` / exec size>32 / Gen12 无此 opcode | 整 kernel 拒 |
| `:141,176,178` | 间接寻址的 send、拆分 send 的间接、寄存器描述符 send | 未覆盖 |
| `:206,212` | 无空闲 GRF 替换 NF 累加器 | 整 kernel 拒 |
| `:242,246` | `lrp`、MAD/CSEL/BFE/BFI2 之外的三源 | 未覆盖 |
| `:266` | 经寄存器跳转的 jmpi | 未覆盖 |
| `:272` | `call/calla/ret/brd/brc` | **整 kernel 拒** |
| `:548` | 16 个 scoreboard token 用尽 | 拒（保守） |
| `:568` | 一条输入展开成 >1 条输出 | 拒 |
| `:628` | 布局与最终 compact 结果不一致 | 拒 |
| `:609,614,618` | 跳转目标不是指令边界 | 整 kernel 拒（kernel 内嵌数据/错位 padding 即命中） |
| `:673,696` | 跳转越过已读字节 / 未读到 EOT | `need_more`，要求读更多页 |
| `:749` | 增长放不下（无 Gen12 compact 形式 + 插入 sync） | 拒 |
| `:751` | 编码器断言 | 拒 |
| `:694` | NF 累加器 + 间接寻址 | 拒 |

结论：翻译器**不是"只改 MOV"**——SYNC/SWSB、send 重编码、compact、跳转布局均必需；覆盖范围是"逐条可 1→1 重编码"的指令子集，任何未知即整 kernel 拒绝。

## 5. 分支重定位与边界（`tgl_xlate.c`）

- **跳转类别** `xl_jump_kind` `:450-459`：goto→3、join→2、jmpi→1、其余按 jip/uip。
- **距离基准**：jmpi 从**下一条指令**算（`:608`，16B 固定宽度），jip/uip 从**自身**算（`:615,619`）。
- **目标解析**：对旧偏移二分查找 `xl_index_of` `:470-480`；找不到 → 拒 `:609/614/618`。跳到"n（末尾）"合法（`:610`）。
- **标签**：所有被跳转的指令标 `is_label` `:701-709`，并在其前插入等待，使各路径 scoreboard 状态一致。
- **增长/布局**：`limit = min((old_len+63)&~63, size)`，且 padding 内出现任何非零字节就退回 `old_len` `:740-743`；一次可编译则复用旧 compact 形态，放不下则**全压缩**重试 `:745-750`；仍放不下即拒。输出缓冲在 `total<old_len` 时补零 `:632`，返回值取 `max(total,old_len)` `:634`——所以写回总是 >= 原长度且不含残留 Gen11 代码。
- 上限：`XL_MAX_INSNS=48000`、静态缓冲 `:430-443`；越界/超量走 `:575` 或 `:696`。

## 6. SEND / compact / SWSB 的未证等价点

- **`mov ARF 0xF0`→`mov null,0`**：作者注为保留"有序指令"语义以让 `@1` 仍表示"上一条已完成"；thread-switch 语义被丢弃，属**设计性近似**，未经执行证实等价。
- **NF→普通 GRF**：选择"内核未命名"的寄存器，配合 `NF+indirect` 拒绝（`:694`）降低别名风险，但仍是语义替换。
- **compact**：布局与发射各调用一次 `brw_try_compact_instruction`，不一致则拒（`:628`），避免静默错编码。
- **SWSB 保守性**：任何间接寻址把读写集扩为"任意 GRF"（`resources` `:333-342,392-405`），偏向多等待而非少等待。

## 7. 缓存 / 跨页 / 物理门禁与 Machine Check 风险（`0004-tgl-accelerator.patch`）

- **物理读/写门禁** `tglPhysicalAllowed` **L379-387**：`tglStolenSize==0 || address<0x100000` → **拒**（fail-closed）；否则允许 `address+len ≤ stolenBase`，或 **`4GB ≤ address+len ≤ 16GB`**。
- **stolen 发现** `tglFindStolen` **L393-406**：由 MMIO 镜像 `0x1080C0`(DSMBASE)/`0x108040`(GGC) 取值；若 `base<0x40000000 || base>0x6C800000 || size==0` → 回退常量 `0x6C000000/0x8000000`。
- **页表遍历** `tglGpuToPhysical` **L422-436**：52 位掩码，1GiB/2MiB 大页由 bit7 判定，叶子页再走 `tglPhysicalAllowed`。
- **缓存** `xlateKernel` **L579-593**：键=`firstPhys+offset`；**只比较首 min(length,4096-offset) 字节的 hash**；拒绝也缓存（`0x80000000|64`，L626-629）。
- **跨页读** `readMore` **L557-566**：逐页按 GPU 页表读，首页带偏移；`XlatePages=176`（704KB）。**跨页写** **L605-613**：逐页回写。
- **batch 走查** `xlateBatch` **L649-780**：`MaxDwords=96*1024`（384KB，L692）；PDP0 靠寄存器对特征定位（L669-688），不匹配即 `badImage`/`notRender` 放弃。

**Machine Check 风险（按严重度）**：

1. **16GB 上界是硬编码**（L386）。本机 `hw.memsize=16GiB`，只是恰好落在硬编码窗口内；若内存图/保留区不同，4–16GB 内"看似 RAM"的叶子可能是 MMIO/保留区 → 读之即 machine check。参考项目的上界**不是**从固件表推导的。
2. **stolen 回退常量**（L400-403）绑定参考机（i5-1140G7）。本机 DSMBASE=0x48800000（`project-analysis/MEMORY-SAFETY.md`）在可信窗口内、不会触发回退；但若真 stolen 基址低于回退基址，`[真基址, 回退基址)` 会被**误放行**。
3. **本项目现有 kext 的门禁更严**：`pmap_valid_page` + TOLUD/TSEG/firmware-floor/4G/16TiB/maxMem（`MEMORY-SAFETY.md`、`GPU-PAGETABLE.md`），且**页表页与数据页同门禁**。未来若移植翻译器，应沿用本项目门禁，**不要**照搬参考项目的 RAM 常量窗口。
4. 低风险观察：`tglReadPhysical`/`tglWritePhysical` 用 `kIODirectionOut` 同时用于读与写（L411/L513），方向标志语义不严谨，但非主要风险。

## 8. Fail-open / fail-closed 行为

| 位置 | 行为 | 判定 |
| --- | --- | --- |
| `tglPhysicalAllowed`（L382-386） | stolen 未初始化 → 全拒 | **fail-closed** ✅ |
| `xlateKernel` 翻译失败（L605 之前） | 不写回，`rejected++`，**内核保持 Gen11** | **fail-visible**（不破坏，但 draw 仍挂） ✅ |
| `xlateKernel` 回写中途失败（L605-613） | 逐页写，某页失败即 `ok=false` **停止但已写页不回滚** → **半翻译 kernel** | ⚠️ **潜在 fail-open/损坏**（依赖"刚读到的页仍映射"） |
| `wrapSubmitCCSResolve`/`wrapSubmitDepthResolve`（L782-795） | 直接 `return 0`，**跳过 resolve**，调用方不看返回值 | ⚠️ **刻意 fail-open**（避免挂死，但渲染可能错） |
| 缓存首 4KB 比较（L582-592） | 物理页复用但内容同 → 命中旧翻译 | ⚠️ 陈旧命中（概率低） |
| `xlateBatch` `!ended`（L778-779） | 只计数，不视为错误 | 记录型 |
| `wrapSubmitBatchBuffer`（L797-808） | 无论翻译结果如何都调用原函数 | 正确 |

## 9. 源码声明 vs 已验证事实

| 声明 | 证据强度 | 说明 |
| --- | --- | --- |
| “捕获字节是有效 Gen11 指令流，不能在 TGL 以相同比特保持等义” | **强（静态编码）** | 本轮 Intel IGA 双平台直接复核（VS 24 / PS0 11 条），有相同 MUL bytes 的 SIMD/operand 改变与 MOV/SYNC 反例；不声称这已证明硬件执行故障的因果。 |
| "翻译后 Gen12 校验通过" | **仅结构** | `xlate` 重编码为 24/11 条 Gen12，Mesa Gen12 validator pass（`project-analysis/GEN11-GEN12-ISA.md`、`vs-xlate.txt`/`ps-xlate.txt`）。**这只证明编码/布局合法，不证明语义正确、更不证明 draw 完成。** 本报告**不**把"24 VS + 11 PS 已翻译"当作翻译正确或能出桌面的语义证据。 |
| 参考项目 GA9–GA11 出画、GA10 machine check | **上游实机声明** | 在 7320/i5-1140G7、2026-10-08 观测；本项目**未复现**，仅作为机制参照。 |
| GA11 判据（2049 译/52 拒、残余 hang） | **上游实机声明** | `xlate-GA11.txt` 归档；其拒绝列表"jump out of the kernel @+0xAF8"实为**读取截断**（`need_more`），非真跳转越界。 |
| 翻译器 fuzz/ktest/回归 | **本体未复跑** | 上游称 400k 随机/变异 kernel + sanitizer（`LAYER4.md:151-154`）；本项目只构建了 `g11to12` 离线工具，未跑 kext-flag 对象路径（`ktest`）与 `fuzz`。 |

## 10. 结论与风险清单

1. 参考目录**来源已固定**：上游 commit `1010490d…`（逐 blob 校验）、Mesa `86333827…`；可离线复核。
2. **GA4–GA11 无稳定桌面**是"翻译覆盖不完整 + 驱动自身 resolve + 未覆盖 compute/media/blit"的叠加，**不是**单一 MOV 问题；GA10 的 machine check 来自读 stolen 占位页。
3. 翻译器的正确性边界是"逐条 1→1 可重编码"；任何未知指令、align16、`call/ret/brd/brc`、间接 send、跳转非指令边界都会**整 kernel 拒绝**（fail-closed 于内存，fail-visible 于 draw）。
4. **最高风险**是物理门禁的**机器相关硬编码**（16GB 上界、stolen 回退常量）；移植时必须替换为本项目基于 `pmap_valid_page` + 固件表推导的门禁（`MEMORY-SAFETY.md`），并保留"页表页与数据页同门禁"。
5. **次高风险**是回写中途失败的**半翻译 kernel**（L605-613 无回滚）与 `igfxtglres` 的**静默跳过**（L782-795）。
6. **证据纪律**：本项目尚未启用任何翻译（GA3.3 无 `igfxtglxl`）；离线"24+11 条翻译通过 validator"仅是结构证据，**不得**表述为语义正确或可出桌面。

---

### 复核命令

```sh
# 来源固定
git ls-remote https://github.com/holdmysocks/latitude-7320-detachable-hackintosh HEAD
git ls-remote https://gitlab.freedesktop.org/mesa/mesa.git refs/tags/mesa-23.3.6 'refs/tags/mesa-23.3.6^{}'
# 归档一致性（git blob SHA-1 应等于上游 tree）
cd reference && jq -r '.files[]|"\(.git_blob_sha1)  \(.path)"' PROVENANCE.json | while read h p; do echo "$h $(git hash-object "$p")"; done
```
