# R8 批次/ring 深层取证（2026-11-04）

> **2026-11-04 离线复核修正（重要）：** 本文 R8h/R9/R10 中基于 GGTT-PTE aperture
> 的 `0xc01dbead` poison/PTE-alias 结论已被撤回/降级。`MI_BBS 0x18b00101` 的
> AddressSpaceIndicator=1，ACTHD/target 是 **PPGTT** 地址；GGTT aperture 读的不是
> 当前 context 的 PPGTT 页表。正确读法是 RCS `PDP0` 作为 PML4 做四级 walk。
> 详见 `docs/offline-ppgtt-review-20261104.md`。R9/R10 的 large-pool 与 alignment
> 负结果仍然成立，但不再作为 poison/越界机制的证明。

## 背景

R7 的 Geekbench Metal 压测已确认会触发 context 5 RCS hang，并最终导致 WindowServer
userspace watchdog panic。已有证据只能给出 `ACTHD/BB_ADDR/IPEHR`，无法说明 GPU 当时执行
的具体 batch。R7 dmesg 的 ring dump 显示一个 `MI_BATCH_BUFFER_START` 目标
`0x4bda9000`，而 `BB_ADDR=0x4bdaabf8`，正好是 `+0x1bf8`；第二次 replay 目标
`0x48e99000`、`BB_ADDR=0x48e9abf8`，仍是 `+0x1bf8`。这提供了强线索，但没有 batch 字节。

参考 NP550XDA 的真实 TGL 诊断实现（`xe/bbtrace`、`xe/bbcopy`、`xe/hangdiag`、
`V204` ring preamble、`poolguard`），在 R7 新基底上构建了两个只读诊断候选。

## R8b：submit-time batch trace

- 镜像 `HP-UPSTREAM-6F03560-REPAIR8B-BATCH-TRACE.img`
  SHA256 `ab9f79ade24d2888de544ade735a51325e7ebcc8d05703969ca5296f7fcf4198`
- NG `06f72898e82964a1f84e2d226a8eb973a2926b7188c0a2319d523e44f8bb7f86`
- UUID `4C4C449E-5555-3144-A184-4F59F31B90E1`
- 在 `IGHardwareRingBuffer::submitBatchBuffer`、`IGAccelFIFOChannel::submitBuffer`、
  `doHangAnalysis` 上安装只读 RouteRequestPlus；记录 128 个提交/128 个 descriptor，
  对 RCS 复制最多 1024 dwords（不跨 4 KiB 页）。
- 实机 boot `546D9524-2C16-4FFF-B1E4-CAA51B4491F2`，所有 R7 安装门控和
  `HP-BBTRACE: ready submitBb=1 submitBuffer=1 hang=1` 均通过。

### R8b 首次 hang

- 时间约 `2026-11-04 01:48:08 +0800`，uptime `154.991190s`。
- GPU 报告 context **19**，RCS `RING_START=0x404b8000`、HEAD=`0x190`、TAIL=`0x1f8`。
- `ACTHD=0x40008004`、`BB=0x40008005`（valid=1）、`BB_STATE=0x20`（PPGTT）、
  `IPEHR=0x40178001`、EIR/ESR=1/1。
- `HP-BBTRACE` 记录 6935 次提交；最近的候选是
  `gpu=0x40006e40`、seq=81、stamp=9、pid=439（SecurityAgent），`delta=4548`；
  同地址 descriptor 声明长度为 `0x224` 字节。`ACTHD` 比 batch 起点晚 `0x11c4`，
  已超过 descriptor 声明长度。
- ring AubList 中可见跳转目标 `0x40006000`、`0x40006c00`、`0x40006e40`。
- R8b 的 submit-time copy 只覆盖 batch 前 448 字节，未覆盖 `0x11c4` 处的实际
  ACTHD，所以没有直接得到故障指令。
- 首个 hang 的 context/进程是 SecurityAgent（登录/安全 UI），不是 Geekbench；
  Geekbench 当时仍在运行。这与 R7 的 context 5 Geekbench Horizon hang 不同，
  但都属于 TGL RCS batch 问题。

## R8c：精确 ACTHD 读取

- 镜像 `HP-UPSTREAM-6F03560-REPAIR8C-BATCH-TRACE.img`
  SHA256 `6a15f0ec9adf4b70aa6e1730692a072cc44c81fb4abfa2a3ccbc957af936167c`
- NG `0483ecb569c0bb527b3d3a20804f2b71c9f82e6a7282777b300a26800b4837c8`
- UUID `4C4C4406-5555-3144-A1F2-944B2223BFCB`
- 相对 R8b 只改诊断：
  1. 候选 batch 按 `ACTHD - batch.start` 选择，不再要求落在 submit-time copy 内；
  2. descriptor 能覆盖时先用 descriptor CPU 指针 + `ndw` 读取 64 dwords；
  3. 若 descriptor 不覆盖，则从 submit-time CPU 指针 + delta 直接读取 64 dwords，
     上限 64 KiB，并记录 `HP-BBTRACE: DIRECT`。
- 实机 boot `D07AE9F1-0DED-4986-ACA0-D1EE57D1FA65`，所有门控和
  `HP-BBTRACE: ready` 通过。
- 前两次完整 Geekbench Metal run（Background Blur→…→Particle Physics）均完成，
  `workload 303 validation failed` 仍出现，但没有新的 gpuRestart/hang；说明该
  SecurityAgent 登录/UI hang 不是每次必现，或者需要更长时间/特定桌面状态。
- 已启动最多 4 次额外 Geekbench 循环，观察是否再次命中 SecurityAgent 或
  Geekbench context 5 hang；结果待定。

## 已知的闭环保留

- R8b 首次 hang 后 Geekbench 被停止，随后正常重启请求；macOS 在关机阶段又出现一次
  **watchdog timeout: no checkins from watchdogd in 185 seconds, shutdown in progress**
  panic（`Kernel-2026-11-04-020321.panic`）。这是关机 watchdog，不是 GPU hang panic；
  不能混入 GPU 根因结论。
- 观察器在 `bb05d7eb-38cf-4ead-8816-bc10d74da8b9` 上完成 EFI/所有 DiagnosticReports
  采集；R8c boot 使用 `D07AE9F1`。
- R8b/R8c 均为只读诊断，不改变 R7 的 NOAUX+NOCCS3+L3=6、ROW/rect/ABI/topology 行为。

## 证据

- R8b: `repair8b-batch-trace/result-r8b.json`、`trial/run/run2/`、`live-r8b-dmesg.txt`
- R8c: `repair8c-batch-trace/trial/run/run/`、`live-r8c-dmesg.txt`
- 原始 `gpuRestart`/panic 报告保留在观察器的 first-reset/post-nixos 归档中。

## 当前结论与边界

- 已证实的深层事实：SecurityAgent context 19 的首个 hang 在一个 `submitBatchBuffer`
  batch `0x40006e40` 之后 `0x11c4` 处，descriptor 只声明 `0x224` 字节；ring 的
  last jump 与 batch 地址一致。该 batch 是登录/安全 UI 提交，不是 Geekbench。
- 这支持“batch 尾部/长度、第二级 batch 或 pool 边界”类问题，但不证明唯一根因。
- R8c 的精确读取尚未在 hang 路径上执行；目前两次 Geekbench 完整 run 没有复现。
- 下一步：继续循环直到再次命中，若命中则读取 `DIRECT`/`EXACT` 的 64 dwords；
  若长时间不复现，按 NP550 的 poolguard/STAMPFIX 方向做最小行为候选并对照测试。


## R8c 后续：目标 hang 已复现，锁定 WindowServer BB 目标

R8c 前两次完整 Geekbench run 没有 hang；第三次循环 run（uptime 约607–610秒）
复现了 R7 的目标签名：

- `607.070671s` GPURestartSignaled stamp1/25。
- `610.359767s` HANG：`ACTHD=0x0a000140`、`BB=0x4b95783c`、`IPEHR=0x61040001`、
  `stamp=1`、type=0。该 `ACTHD/IPEHR` 与 R7 的 context5 目标一致。
- 最近的 outer batch 是 `0x4b9537ec`，seq45661，pid204 **WindowServer**，
  descriptor `+0x1520`，submit-time copy 3300 bytes；`BB 0x4b95783c` 在它之后
  **0x4050** 字节处，超过 descriptor 和 copy 范围。`ACTHD 0x0a000140` 不在这些
  outer batch 内，说明它是另一个/嵌套地址空间。
- 后续 `021311/021409/021510` gpuRestart 报告均为 context5 WindowServer、RCS idle、
  IPEHR=`0x03800000`（MI_REPORT_HEAD），是 reset/recovery 报告，不是初始
  `0x61040001` inline hang。

结论：目标 GPU hang 的顶层提交进程是 **WindowServer**，不是 Geekbench 本身；
Geekbench Metal 压测只是触发条件。`BB=0x4b95783c` 位于 outer batch
`0x4b9537ec + 0x4050`，这是 R8c 没有读取到的关键 inner/next-level batch。

## R8d：BB 目标优先读取

R8d 在 R8c 基础上只改诊断选择：
- 优先用 `BB_ADDR & ~1` 作为 target；只有 BB 不可用时才用 ACTHD；
- 选择包含 target 的最近 outer batch，delta = target - batch.start；
- 先走 descriptor-bounded exact read，再走最多 64 KiB 的直接读取；
- 记录 `TARGET/SRC=BB|ACTHD` 和 `DIRECT/EXACT` dwords。

R8d 本地产物 SHA256 `6d7644ba8f2590322a6ec056e74d528f3e1e37033891ed63bb77463b25ebaf98`，
NG `c05acf4d2faad8445ef1e998e4c4f2fce96607404973ddfd8b3daf1f842b1856`，
UUID `4C4C44D0-5555-3144-A1E5-57ADA4872D04`。已进入独立实测，目标是读取
`0x4b9537ec + 0x4050` 处的 inner batch。

R8c 目标 hang 证据：`repair8c-batch-trace/result-r8c.json`、`live-r8c-dmesg-2.txt`、
`r8c-hang-reports/`、`trial/run/run/first-reset-*`。


## R8d/R8f：WindowServer 多级 batch 链

R8d（BB 目标优先）在 boot `6B9804AA` 的第一次压测中再次命中目标：

- `ACTHD=0x0a000140`、`BB=0x48ea5538`、`IPEHR=0x61040001`；选中 outer
  `0x48ea27ec`（WindowServer/pid204）后，`BB` 偏移 11596；直接读取的 64 dwords
  是 `00000000 20000000` 重复和 `78490001` 序列，属于 state-like 数据，不是
  ACTHD 指令。
- 同 boot 后续一个 BB 目标 `0x4bdb344c` 的直接读取出现
  `18b00101 4319829c`，即 **MI_BATCH_BUFFER_START → 0x4319829c**，直接证明存在
  nested/second-level batch 链。

R8f 增加 ACTHD descriptor 查找和完整 submit-copy 扫描，在 boot `45BF0863` 再次命中：

- `ACTHD=0x0a000140`、`BB=0x4bdb5538`、`BB_STATE=0`、`SBB=0`、
  `IPEHR=0x61040001`、stamp1。
- `HP-BBTRACE: ACTHD_DESC none for 0a000140`：128 个最近 submitBuffer descriptor
  中没有任何一个包含 ACTHD。
- 选中 outer `0x4bdb27ec`（WindowServer/pid204，seq5390），copy 3480B，
  delta 11596；`SCAN ndw=870 MI_BATCH_START=1 MI_BATCH_END=0`。
- full copy 第一个 DWORD 是 `18b00101`，target **`0x40d7f308`**，即 outer batch
  一开头就是第二个 `MI_BATCH_BUFFER_START`。复制的前 870 dwords 中没有
  `MI_BATCH_BUFFER_END`（但 copy 受页/长度限制，不能仅据此断言整个 batch 无 end）。
- `BB` 目标的直接读取仍是 `78490001` state-like 序列，不是 ACTHD 指令。

当前最合理的定位：目标 hang 发生在 **WindowServer 的 nested/second-level batch
链**中；ring 外层先跳到 `0x40d7f308`，真正的 ACTHD `0x0a000140` 不在已记录的
descriptor 里，可能是更深层的 PPGTT/第二次级 batch。还缺第二级 target 的 CPU
映射/PPGTT 翻译，以及 batch end/生命周期；不能把“无 end”单独当成已证实根因。

已保存 `repair8d-bb-target/result-r8d.json`、`repair8f-acthd-desc/result-r8f.json`
及两 boot 的 dmesg/reports。下一步：沿 `0x40d7f308` 继续追踪目标链，或对
`0x0a000140` 做 PPGTT/描述符解析；然后才考虑 batch-end/pool boundary 的行为修复。


## R8h：ACTHD 命中 poison scratch 页，修正候选 R9

R8h 在 boot `5820FCBF` 的真实压测中再次命中目标，并用 GGTT-PTE page-0 aperture
读取了 **ACTHD 0x0a000140**：

- `page=0xa000`，`PTE=0x00000003:fb091001`，present=1；+0x140 开始的 32 个 dword
  全部是 **`0xc01dbead`**，+0x200 之后为 0。这不是有效命令；`IPEHR=0x61040001`
  只是硬件报告的指令字，ACTHD 所指的页面本身是 scratch/poison。
- 外层 batch `0x48ea27ec`（WindowServer）copy 3480B，`SCAN ndw=870
  MI_BATCH_START=1 MI_BATCH_END=0`；第一个 `MI_BBS=0x18b00101 -> 0x413e9308`。
  chain target 的 aperture 读取也是 0。BB 目标 `0x48ea5538` 的直接读取却是
  有效命令区（`78490001...`、`78550003...`），说明 BB 本身没有坏，坏的是
  ACTHD/更深层地址。
- 第二次 reset 的 ACTHD `0x01406198` aperture 读取全为 0；IPEHR=`0x03800000`，
  是恢复态，不是初始目标。
- 项目源码 `kern_green.cpp` 的既有注释明确描述过同一指纹：blit3d 批处理越过
  command pool 缓冲区，GPU 继续读下一页 scratch，内容正是 `0xc01dbead`。
- 实测 pool 初始化：count=8 的小池已是 0x1000→0x20000；count=256 的 64 KiB
  池不变；但 **count=256、size=0x1000 的大数量 4 KiB 池仍为 0x1000**，是
  最可能的越界来源。
- 既有 `-ngreenxefix` 会把 count>16 的 4 KiB 池提升到 16 KiB，但 R7/R8 的
  boot-args 没有这个开关；小池 HP-KPOOL 已独立修复，大池没有。

## R9：只启用 large-count 4 KiB → 16 KiB 的隔离修复

R9 在 R8h 只读诊断之上，在 `wrapPoolInit` 增加 `HP-POOLBOUND`：
- 仅对 real TGL + Tahoe、`count > 16`、`bufSize >= 0x1000 && < 0x4000` 的池
  设置为 0x4000；
- 不改 count=8 小池、不改 64 KiB 池、不启用完整 `-ngreenxefix` 的其它行为；
- `-ngreennopoolbound` 可关闭。

镜像 SHA256 `c613050019365439d5b0e116b4a85f6da772de8690ef22afc182991cb661680a`，
NG `859b97afb9ffbce9d1260c4ea2102ae47c6c0f5fbf2d8dfb8ba99b9efa19ce34`，
UUID `4C4C4454-5555-3144-A1C4-61F4F824CAA0`。R9 已进入独立实测；判据是
`HP-POOLBOUND` 出现在 count=256/0x1000 池上，并在相同 Geekbench 循环中不再
出现 `APERTURE ACTHD` 的 `0xc01dbead`/目标 hang。

R8h 证据：`repair8h-aperture/result-r8h.json`、`live-r8h-dmesg.txt`、
`repair8g-chain/result-r8g.json`。R9 证据：`repair9-poolbound/trial-r9/`。


## R9 实测：16 KiB 大池修复不足

R9 在 boot `A4FA739A` 实际应用了 `HP-POOLBOUND`：
`count=256 size=0x1000->0x4000`（pool 6/7/10/11），小池 128 KiB 与 64 KiB 池保持。
但测试结果为**否定**：

- 启动后、手动 Geekbench 前，88.79 秒出现一次独立 WindowServer/login hang：
  `ACTHD=0x40174ba8`、`BB_STATE=0x20`、`IPEHR=0x7a000004`、descriptor
  `0x40174000+0xbdc`，aperture 读取为全 0，direct 读取可见
  `7a000004...05000000`（PIPE_CONTROL + MI_BATCH_BUFFER_END）。这不是目标 poison 签名。
- 随后手动 Geekbench run1 完整通过；run2 在 uptime 512.18 秒再次命中目标：
  `ACTHD=0x0a000140`、`BB=0x4bd75538`、`IPEHR=0x61040001`，aperture 仍为
  32 个 `0xc01dbead`。外层 `0x4bd727ec`（WindowServer）仍是
  `MI_BBS 0x18b00101 -> 0x4b92a308`；`0x4b92a308` 的 aperture 也是全 0，
  且其 PTE `0xfcca4001` 与 ACTHD 页 `0xa000` 的 PTE 相同——**两个 GGTT 虚拟页
  指向同一个 physical poison/scratch 页**。
- 因此，目标不是简单的“4 KiB 池越界后被 16 KiB 修复”：(1) 外层 batch/BB 有有效命令；
  (2) MI_BBS target 本身直接指向 scratch 别名页。大池扩容不够。

## R10：仅启用大分配 64 字节对齐

历史 `xe/pool` 注释还指出：Tahoe 的 blit/state 偏移可能让大命令从非 64 字节
边界开始。R9 的外层 `0x4bd727ec` 和 target `0x4b92a308` 都不是 64 字节对齐
（`0x2c`、`0x08` mod 0x40）。R10 在 R9 上只增加 **HP-POOLALIGN**：
- real TGL/Tahoe，`ndw >= 0x400`，在原始 allocator 前把当前偏移补 MI_NOOP 到
  下一个 64 字节边界（仅当 `cur+pad+4*ndw <= lim`）；
- `-ngreennopoolalign` 可关闭；
- 不启用完整 `-ngreenxefix`，保留 R9 大池 16 KiB、R7 NOAUX+NOCCS3+L3=6 与所有
  只读诊断。

R10 镜像 SHA256 `a4c7c504127f66a20c29ab8ce02a9e98b8d3414d383e391b4f9442f49d774dbc`，
NG `6a3185a85462f4c1cadaa62d2aaf80995eaaa7a19e423012577abea12691053a`，
UUID `4C4C44D7-5555-3144-A156-E70219D6524F`。若 R10 的 `HP-POOLALIGN` 命中且目标
不再出现，则对齐是有效修复维度；否则继续按 MI_BBS target/页别名与 batch 生命周期
缩小范围。R9 证据：`repair9-poolbound/result-r9.json`、`live-r9-run2-dmesg.txt`。


## R10 实测：对齐也 negative；目标在第一次对齐前已发生

R10 在 boot `AC56EB48` 应用了 R9 大池 16 KiB 与隔离的 64 字节对齐（`HP-POOLALIGN`）。
门控全部通过，压测开始后 **170.99 秒**再次命中目标：

- `ACTHD=0x0a000140`、`BB=0x4b6a7788`、`IPEHR=0x61040001`，aperture 仍为
  32 个 `0xc01dbead`。
- 外层 `0x4b6a37ec`（WindowServer）copy 3300B，`SCAN ndw=825
  MI_BATCH_START=1 MI_BATCH_END=0`，`CHAIN0 -> 0x4319d308`，chain 页仍不在
  table 中。
- `HP-POOLALIGN` 的第一次日志在 **187.337710 秒**（`ndw=0xd8e off=0x9b8 pad=0x8`），
  在目标 hang 之后。也就是说目标至少有一次没有走这条对齐路径，或坏 target 在
  对齐前已经写入/被复用。
- 因此 R10 也是 **negative**：大池 16 KiB 与 64 字节对齐都不能阻止目标。

## 最终定位（可复现，仍有未证明部分）

R10 在目标 hang 后自动返回 NixOS `f4d351fc-1c36-4063-ae8d-b47782adfb31`；观察器完成 first-reset dmesg/ioreg/DiagnosticReports 和 post-NixOS EFI/reports 采集。

已实测、可复现的链条：

1. Geekbench Metal（或启动后 WindowServer 负载）触发 WindowServer RCS hang；
2. 首个目标签名固定为 `ACTHD=0x0a000140`、`IPEHR=0x61040001`、`BB_ADDR` 指向
   一个 WindowServer outer batch 之后约 `0x2d4c/0x3f9c/0x4050` 的地址；
3. ACTHD 的 GGTT 页 present，但内容是已知 scratch poison **`0xc01dbead`**；
4. outer batch 开头是 `MI_BATCH_BUFFER_START`，目标地址的页有时与 ACTHD 页
   指向同一个 physical page（PTE 相同），且目标页为 poison/zeros；
5. outer batch 自身和 BB 目标的部分命令区是有效的；问题不是“整个 ring 为空”，
   而是第二级 target/页生命周期错误。

未证明：具体 allocator/relocation/页表更新路径为何把 MI_BBS target 指向 scratch；
完整 PPGTT/第二级 batch 的 CPU 映射；是否应在 submitBatchBuffer 阶段校验并修复
MI_BBS target，或修复 pool/页回收生命周期。**没有已验证的修复**；R9/R10 两个
最小候选均为 negative。可验证的下一步是给 MI_BBS target 增加只读校验/安全替换
（guard）或继续追踪 target 的提交者和页表生命周期。

## 离线复核后的修正（2026-11-04）

R8h/R9/R10 的 `APERTURE` 读取使用 GGTT PTE，把 PPGTT 的 ACTHD/target 当成 GGTT
地址，导致 `0xc01dbead` 和 PTE alias 的解释不成立。`MI_BBS 0x18b00101` 的
ASI=1 (PPGTT)；RCS `PDP0` 是 PML4 base（不是 1 GiB PDP）。真实 target/ACTHD 需要
用 PML4 四级 walk 读取页表和 batch，当前 dmesg 只有 PML4 base，没有页表页内容。
因此：
- **撤回** poison/同物理页/坏 MI_BBS target 的强断言；
- **保留** R9（大池 16 KiB）和 R10（64 字节对齐）均为实际 negative；
- 真正缺口是 **PPGTT 页表页/batch 内容**，以及 outer/inner batch 控制流。
详细证据和后续纯离线方案见 `docs/offline-ppgtt-review-20261104.md`。
