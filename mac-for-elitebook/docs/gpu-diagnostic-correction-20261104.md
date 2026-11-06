# R18–R26 诊断更正与后续（2026-11-04）

此前将映射错误、UAF 排除、in-flight 覆盖和根因当成确定结论，证据不足，现予撤回；原始记录和日志保留。目标 `ACTHD=0x0a000140` / `IPEHR=0x61040001` 多次出现，但不证明地址归属或原因。R26 物理写后出现不同 hang，时间关联不证明因果，也不能证明旧页在执行。R25/R26 都不再用于启动；未重新武装或修改目标启动配置。

## 本地代码核查

- `repair24-submitpost/source/src/NootedGreen/kern_gen11.cpp` 的 `hpBtCmpBatch` 对 `e.addr` 非页对齐时，读取物理页后从 `page[0]` 比，而非页内偏移；匹配 descriptor 时没有应用 `e.addr - d->gpu`，也没有证明对象的生命周期。数值保留，不能解释为对应字节差异或排除复用。
- R23/R24 的提交检查也从 GPU 物理页首读字，而非 `addr` 的页内偏移；`hdr` 与 GPU VA、页表根及地址空间是否关联未经独立验证。PRE/POST 早期样本无法证明原函数不复制或重映射目标对象。
- GPU bit 7/page-size 处理、实际地址空间、候选命中和采样时序仍须独立核实。R19 的 `0x4bd727ec` 起始的 4072 字节副本不包含 `BB=0x4bd76788`。
- 固定上游参考 [Linux v6.12 i915 intel_gtt.h](https://github.com/torvalds/linux/blob/v6.12/drivers/gpu/drm/i915/gt/intel_gtt.h)：`GEN12_PPGTT_PTE_PAT2=BIT_ULL(7)`，而 `GEN12_PTE_PS64=BIT(8)`；`GEN8_PDE_IPS_64K=BIT(11)`、`GEN8_PDE_PS_2M=BIT(7)`。因此现有 walker 在叶 PTE 上将 `0x80` 注释为 `GEN12_PTE_PS64` 与该上游定义直接冲突，不能再依靠其 64K 结果。上游定义并不单独证明 macOS 的具体页表模式；仍需验证具体模式、页目录和地址空间。
- R25/R26 的 4 KiB 物理页写入没有证明所有权、长度或偏移；存在破坏无关数据的风险。R26 的 `0x03800000` hang 是观察，因果未证明。`resolve_hiz_g` panic 与目标 hang 的关系也未确定。
- 回程 watchdog 在整个 dmesg 中独立查找 `HP-BBTRACE: HANG` 和 `HP-PPGTT`，后者可能来自初始化；并不保证目标 hang 的完整输出已保存。控制进程可在 observer 的 identity mismatch 时退出，daemon watchdog 也可能随之终止。不能据此承诺必然回程或证据完整。

## R26 返回采集

NixOS 经 Tailscale SSH 验证 boot ID `f227a79e-eb2f-42bb-b362-f4e3bb1ebe62`。只读完整采集、APFS 数据卷核验和目录比较均 exit 0：`.local/driver-repair-20261103/repair26-batchcopy2/trial-r26/post-nixos-f227/`。

- `efivars-full.tar`: SHA256 `c576a640aba848ab55621351ac8228b718e4bab0b8a9d3539e33610d3b329fe8`
- `DiagnosticReports-full.tar`: SHA256 `26f7adcd48081f63c5ab252b7aeedc40a68b680d17da01bfd081ece906bca55c`
- 归档含 `Kernel-2026-11-04-150019.panic`，内容为 shutdown 期间 watchdog timeout；仅凭文件名和存在不能断定它属于 R26 或与 R26 写入有因果关系。R26 的 reboot 请求记录在 07:01:31Z，须进一步核对报告时间和 boot identity。

## 下一步

首先校验地址空间、页大小、实际相同 allocation、逐页偏移/边界及对象生命周期；不满足条件时报告未知。离线测试 `.local/gpu-diagnostic-audit-20261104/test_offsets.py` 四项通过，只验证数学范围处理，不验证 GPU walker。进一步核查上游与固定版本源码，修复和测试 watchdog 完整性；在这些前置条件完成前不交付或启动新候选，不进行物理内存写入或修改 PTE。

## 离线复核后续：R20–R26 CMP 条目与回程门控

参考 [Linux v6.12 gen8_ppgtt.c](https://github.com/torvalds/linux/blob/v6.12/drivers/gpu/drm/i915/gt/gen8_ppgtt.c)：其 `gen8_ppgtt_insert` 对图形 IP 版本低于 12.55 使用 `gen8_ppgtt_insert_huge`，该路径对 64K 使用 PDE 的 `GEN8_PDE_IPS_64K`；另一条 XeHP 路径有 PS64 TLB hint 和 compact 表。此为上游实现证据，不能替代对本机 macOS 地址空间模式的验证，也不能简单把两种布局混为一谈。

离线脚本 `.local/gpu-diagnostic-audit-20261104/replay_walks.py` 对 R20 retry1 至 R26 七条 CMP 日志记录，在目录项 IPS64/compact/large 标志未置位的情况下，按**假设普通 4K 布局**重算叶项。七条假设结果均与旧 walker 输出不同。例如 R22：VA `0x48e527ec`，PDE `0x3e63ea003`，PTE `0x39a60d08b`；旧输出 `0x39a6027ec`，普通 4K 假设为 `0x39a60d7ec`。这只是对日志条目的数学重放，不证明这些条目是 GPU 当时使用的映射，更不证明 CPU/GPU 归属关系。完整结果 `.local/gpu-diagnostic-audit-20261104/replayed-cmp-walks.ndjson`。

此外增加纯离线 watchdog 门控原型和反例测试：必须同一 hang 编号、目标寄存器、明确完整结束标志，早期安装标志或另一 hang 均不能触发。它不是实际 watchdog；现有 kext 尚未产生该协议结束标志，真实 OS/boot 校验、原始证据落盘、进程存活和回程尚未实现或测试。全部 11 项离线测试通过；未生成或启动新 IMG。

## R27 本地构建与回程组件（未交付）

R27 从 R20 源码派生，将 hang-time dump 缩为原始 MMIO 寄存器快照，去掉该 dump 中存疑的 PPGTT 遍历、已保存指针解引用和物理页读取，并输出 `HP-DIAG-END: hang=N status=complete scope=mmio-only`。此标志只表示声明的 MMIO 快照输出结束，不表示整个 GPU 状态完整；其他继承 hook 尚未全部审计。`r20-r27.diff`、源码、编译日志和收据均在 `.local/driver-repair-20261103/repair27-snapshot/`，NG SHA256 `cd06af37e17be3fd69442dd548e73c59c1d8b41d66d5530d26e363f6f9c0f12a`；本地构建成功，未生成或交付 IMG，不是修复。

`.local/gpu-diagnostic-audit-20261104/` 新增回程核心、SSH 命令构造和独立控制循环，模拟测试包含同一 hang/完整标记、旧 boot/错误 OS 拒绝、先完整保存并 fsync 再请求重启、超时保存、失联不凭旧数据重启。23 项离线测试通过。实现尚未与部署/observer 进程接线，未在真实 macOS 测试，也不能保证机器失联时返回；下一步先测试持久进程及重启后 collector 的完整生命周期和继承 hook，再决定是否生成 IMG。

后续审计发现 R27 仍安装了 submit 路由，会读取 `hdr` 所在页和 descriptor，其安全性未由 MMIO-only dump 变更解决。因此另建 R28：`hpBtInstall` 只安装 `doHangAnalysis` 路由，不安装两个 submit 路由、不解析 `pmap_valid_page`；其他非 BBTRACE 的原有补丁仍保留。`.local/driver-repair-20261103/repair28-mmio-only/build-receipt.json` 记录本地编译的 NG SHA256 `229e9b3859413979d253015d5680adfa7d758103759041d88856f8aca396d62b`，UUID `4C4C44DE-5555-3144-A102-6BC9BDB60AB9`。24 项离线测试通过；未构建 IMG、未交付或启动，observer 的旧路由安装门控也必须调整。两个版本均不是 GPU 修复。

## R28 实机结果与回程修正

R28 镜像 `b0c315d45029f8fcff0e9558731860d9321c1f997c653bebb6862514d9b5b71d` 实际启动 macOS `E439D465-83D0-416F-AAC1-E24FCFFA7E1C`；独立 worker 验证该 boot 与 NG UUID。捕获的完整原始 dmesg SHA256 `bae506aa3ed442535db664591adfdc2ad2919972cccaff626d1fe6f25a94039e` 包含：

- `121.554694s`：`HANG #1 ACTHD=40006ba8 IPEHR=7a000004`，其 MMIO-only 结束标记齐全。
- `176.547532s`：`HANG #2 ACTHD=0a000140 BB=4b90a8f8 IPEHR=61040001`，其 MMIO-only 结束标记齐全。

worker 保存 dmesg 后于 10:03:59Z 请求受 boot ID 守卫的重启，SSH 返回 255，不能仅凭它认定重启成功；10:04:57Z 独立 observer 实际观测到 NixOS `c24f81d0-9c25-4e73-922c-ac52cb000709`，10:05:21Z 完整 EFI/DiagnosticReports 采集 exit 0。首次 reset 快照的三项采集均 exit 0。详情及哈希见 `.local/driver-repair-20261103/repair28-mmio-only/r28-evidence-receipt.json`。本轮没有完成 Geekbench Metal，也没有修复：目标寄存器组合再次出现。

本轮 worker 只认目标 hang，在第 1 个非目标 hang 的结束标记之后又等待约 55 秒，偏离用户希望先回程的要求。现已将回程策略在本地改为：同一 hang 的 MMIO-only 结束标志齐全后，无论是否目标 hang 都先持久化再请求正常重启；若结束标志缺失，最多等待 20 秒后保存当时原始 dmesg 并请求重启；无 hang 仍为 600 秒。28 项模拟测试通过，**新策略尚未实机验证**。若 SSH 无法连接仍不能保证自动回程。

## 本地 TGL 提交函数静态分析

本地 `AppleIntelTGLGraphics` 原始二进制 SHA256 `1b2f5aa3131f9b909fe984877e41d5ebcdb2837572b45e1e901a72a6271515a2`。`llvm-objdump` 全量反汇编私有保存于 `.local/gpu-diagnostic-audit-20261104/tgl-submitBatchBuffer.disasm.txt`，SHA256 `d2faf15d6d549202643161f0c8595ffd75c166805182376c8ef3afdde4be7de9`；工具的地址选项对 Mach-O 未截断输出，因此文件是全量而非单函数。

`IGHardwareRingBuffer::submitBatchBuffer` 的 `0x42f7a–0x4306a` 直接可见：将 `rsi` 的 64 位地址及 `rcx` 指针分别记入 ring 历史槽，随后依据 context 字段构造 `0x18800001` 家族的 MI_BATCH_BUFFER_START，把 `rsi & ~3` 的低位及高位编码到命令，调用 `writeBuffer` 写三个 dword；`rcx` 在本函数内用于保存而未作为拷贝来源读取。这比 R23/R24 的错误对比更可靠地说明**该函数直接构造 ring 命令**；并不证明调用者没有预先映射/复制，也不证明 `rcx` 对应的就是 GPU 地址指向的同一个分配。需要继续分析调用方以及实际 context 地址空间选择，不能由此直接修改 PTE 或做物理页复制。

同一反汇编 `IGAccelFIFOChannel::submitBuffer` 的 `0x4c710–0x4c738` 检查 descriptor `+0x20` 指针与 `+0x30` 计数，并在特定条件下用它们写 batch 结束标记。`0x4c828–0x4c851` 将 descriptor `+0x18` 装入 RSI、`+0x20` 装入 RCX、`+0x30` 装入 R8D，再经 ring vtable `+0x118` 间接调用；这支持它们在提交路径中被共同传递，但调用目标及 GPU 虚拟地址空间/映射仍需独立确认，不足以证明物理页身份或生命周期。

对同一固定二进制的 Mach-O `__DATA` 段地址/文件偏移以及 `llvm-nm` 符号进行静态核对：基类 vtable `0xd5640 + 0x10 + 0x118 = 0xd5768` 和 Main ring vtable `0xdf4e0 + 0x10 + 0x118 = 0xdf608` 的文件指针都为 `0x42f7a`，即上述 `submitBatchBuffer` 符号地址。根据 Itanium C++ ABI address-point 假设，这支持该间接槽在所查两个类中指向该函数；尚未证明现场实例类型、动态覆盖和 GPU 地址空间。descriptor 中的地址、CPU 指针和计数被配对传入，比单纯数值邻近强，但仍不等于已证实页表映射、GPU 执行状态或对象在 hang 时存活。
