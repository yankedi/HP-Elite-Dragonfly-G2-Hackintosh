# 驱动修复实测：REPAIR1 与 REPAIR2-FFDOP

**验收口径澄清（用户于2026-11-03指出）：FF_DOP workaround遗漏已修补，实机补丁应用检查通过；整体GPU功能仍失败。** 实机`ffdop_installed_verified=true`与精确UUID证明这一候选已加载并完成补丁应用检查；目前未采集`0x20ec`直接MMIO读回。后文“未通过/未修好”涉及303、RCS和整体功能验收，不能据此说FF_DOP补丁没有应用成功。此前对用户笼统回答“没有修复成功”混淆了这两项结论，现明确纠正；保留原始实测与回执。

**最新结论：REPAIR2-FFDOP 也未通过，完整现场和终态证据已收回。** 303及初始context5 RCS故障仍在；压测停住时macOS SSH仍可用。保存完整现场后，代理停止本轮压测并请求正常重启，随后发生新的 **重启过程中的shutdown watchdog panic**；现已回NixOS。详情见文末，REPAIR1原结果保持。

## 结果

**REPAIR1 已完成一次无人值守实测，仍未通过。** 新 IOSurface 兼容修正及命令批次钩子实际执行；Metal 出现 workload 303 校验错误，随后发生 RCS hang，最终为 WindowServer watchdog panic。目标随后回到 NixOS，完整终态证据已收回并完成比对。故障后已按用户指令转入本地分析，没有再次启动镜像。

本轮正常重启后，代理未再发重启、关机、挂起或固件修改指令；开发机保持运行。

用户随后明确纠正：“这不是卡死啊是正常panic后重启，卡死是卡在macos啊”。因此本轮恢复归类为 **watchdog panic 后正常重启回 NixOS**，不是 macOS 卡死未恢复。此用户说明与已取得的新鲜 EFI panic 和新 NixOS boot 相符；SSH 断线本身不作为 panic 或卡死依据。用户要求“继续修复后测试”仍有效，下一份 FF_DOP 独立试验的准备另存，不改写上述已完成实测或离线构建当时的回执。

## 修复内容与身份

相对原 KPOOL，仅替换 NootedGreen 二进制，98 个 EFI 文件中的其余文件及 OpenCore 配置保持逐字节一致。

- 对真实 TGL/Tahoe，IOSurface plane-count 从旧 `+0xb0` 改为实际 `+0x98`，像素格式从旧 `+0xa4` 改为实际 `+0x80`。
- 从当前 IOSurface 解析原生 getter，资源创建前验证布局和共享纹理 override，拒绝会导致零除的无效布局。
- rect-list 分组预留上限改为 `0xc00` 字节；在分配器决定是否换槽之前计入页对齐空间，换槽后重算 padding，并保持 CPU/GPU 地址偏移一致。
- 保留既有 R3 scratch、CCS 提交绕过、REC 及 KPOOL。特别注意：CCS 提交绕过仍不是完整 CCS resolve 实现。

| 资产 | SHA-256 / UUID |
| --- | --- |
| 原 KPOOL IMG | `4285f20880b9b3847034771b4d66b632919871ad18d6e01cdb411d45809adcc2` |
| REPAIR1 IMG | `95364c416701a4aeecbad30b15dd9c59dd8c028b4fbc1dbc2a5452069974cec3` |
| REPAIR1 NootedGreen | `2174deebc4575445df213f414e77b3d53adac40e28c68439aab55fad0e2e33a2` |
| NootedGreen UUID | `4C4C447C-5555-3144-A17B-FC2B50598B1D` |
| 不变的 config | `7df7f1f674e485195bfb5e8c94779047976131e5da7b2b573e4043d181ac71fd` |

实际 macOS 为 25G83，boot `FB143E8C-ECE2-47DF-9FC5-C0B672A9DA03`；250 项安装内容、运行 UUID、R3/R4/REC/KPOOL、新 ABI 及 rect 安装检查均通过。70.341694 秒首次 IOSurface 验证命中；74.031330 秒首次页对齐批次命中，`ndw=0x130 / request=0x2b0 / pad=0x600`。

## 时间线

下表为 UTC；原始 macOS 日志使用 UTC+8。

| 时间 | 实际事件 |
| --- | --- |
| 01:45:44 | 镜像完整哈希读回、单次 env 武装后正常重启 |
| 01:47:20 | 严格 SSH 确认新 macOS boot |
| 01:47:32 | 身份与全部补丁检查通过后立即启动 Metal，空闲等待为 0 |
| 01:48:14 | workload 303 failed validation |
| 01:48:43 | 首次 GPU reset；随后收回完整 dmesg、IORegistry、系统及所有用户 DiagnosticReports |
| 01:48:46—01:48:56 | 后续 context46、context46、context5 hang 摘要 |
| 01:51:34—01:51:35 | 负载与日志 SSH 超时退出；当时不以失联认定 panic |
| 01:51:46 | 严格确认新 NixOS boot `8d3b6832-9e4d-4272-b40d-9276527efd2a` |
| 01:52:04 | 完整 EFI、所有 DiagnosticReports 及远端比对均退出 0 |

负载输出推进至 Background Blur、Face Detection、Horizon Detection，未取得有效分数。像素正确性探针未在此轮运行。

## 终态与首个 hang

六个新鲜数字 EFI panic 块全部相对试前变化；3941 packed bytes 解码后逐字节重编码往返一致。此次 panic 在 **278.950405105 秒**发生：WindowServer 120 秒没有成功 check-in，1 次 induced crash。解码文本 SHA-256：

`562d5ad199cdf86bb5e8a211f5f89ed7db8fc5bc7c890e75f91f1e395a20ffcc`

这次终态是 watchdog。测试比此前 860 秒的除零终态更早结束，因此不能把本轮未出现除零视作长期验收。

首次完整 dmesg 保留：

- context5，RCS busy-in-ring；HEAD `0x03203468`、TAIL `0x3558`。
- ACTHD `0x0a000140`、IPEHR `0x61040001`、EIR/ESR 均为 0。
- ring 中两条 PPGTT batch 指向 `0x4bda9000`、`0x4bdb27ec`。
- 146.085341 秒，REC 确实执行 `restore=1 / replay=1`，后续仍发生 hang。
- 首 reset 快照抓得早，新增磁盘 gpuRestart 文件尚未写出；终态目录增量为两份 WindowServer watchdog spin。原始完整 dmesg/IORegistry 提供首故障寄存器，不能拿历史 gpuRestart 文件充当新样本。

上述是与 KPOOL 相同的初始 context5 故障形态。303 在首个记录的 reset 前约 29 秒已失败，依然应单独处理正确性问题。

### 命令解码勘误

HEAD 前一 DWORD `0x03800000` 是 **MI_REPORT_HEAD**，不是此前标注的 MI_ARB_CHECK。官方 Linux 定义为：

- `MI_REPORT_HEAD = 0x07 << 23 = 0x03800000`
- `MI_ARB_CHECK = 0x05 << 23 = 0x02800000`

实际 TGL 的 `submitToRing`（VM `0x4335d`）和 `resubmitStampToRing`（VM `0x432bd`）都会写入 `0x03800000`。因此不应以先前错误标签为依据移除“仲裁检查”。本轮 HEAD 所在 DWORD 实际为 0，前一 DWORD 才是该 report 命令；IPEHR 的旧 CSR 编码也不能代替实际 head 命令。

## 故障后的离线进展

已进一步对照实际 TGL 与官方 Linux TGL workarounds：

1. **发现明确的 FF_DOP 时钟门控 workaround 覆盖缺口，并已实现下一份本地补丁。** 实际 `startGraphicsEngine` 的 VM `0x25166` 窗口只向 `CS_DEBUG_MODE1 (0x20ec)` 写 `0x00010001`，没有设置 Linux `Wa_1606700617` 对 TGL 要求的 bit1。现有移植代码位于 return 后或 `!isRealTGL` 分支。
2. 下一份补丁仅在真实 TGL/Tahoe，将这一窗口改为写 `0x00030003`，随后恢复 EDX=`0x00010001`，保持后续 `CS_CHICKEN1` 的原有抢占设置。这样避免“把 FF_DOP 位顺带写入抢占寄存器”的副作用。
3. 该本地 kext 已构建、签名。原/新实际机器码在开发机普通内存上执行通过，对全部 65536 种初始低 16 位验证了掩码写语义和 EDX 保持。**尚未生成第二份 IMG、交付或启动。** 这是修复已定位的硬件 workaround 缺口，不等于新一轮 GPU 通过。
4. 首故障的 `PSMI=0x1090` 已包含所需 `0x1080` 位；`FF_SLICE_CS_CHICKEN1=0x4000` 符合 Linux per-context 抢占策略。后续不应直接启用整组 RPL 修正、清除此位或笼统启用 `-ngreenxefix`。
5. `ROW_CHICKEN2` 的 TGL 读相关 workaround 仍是后续审查点：需连同 MCR 广播、forcewake 和上下文保存一起审查；当前不把缺少该寄存器快照说成已观测到错误值。

## 证据与检查

全部私有材料：`.local/driver-repair-20261103/`。

- `trial/panic-analysis.json`：本轮终态及离线审计结论。
- `trial/posttrial-integrity.json`：完整原始流 120427 行、可用历史回填 5830246 行，gzip 检查通过，均 0 条坏 JSON；SSH255 意味历史回填未正常结束，不宣称保留了流启动前所有日志。
- `trial/run/post-nixos/`：完整 EFI、系统及所有用户 DiagnosticReports；采集与远端比对退出 0。
- `trial/posttrial-boot-verification.json`：用后 USB 的 98 个 EFI 文件仍与候选匹配，env 已消费正确 REPAIR1 目标。
- `source-receipt.json`、`image-receipt.json`：测试源码与镜像哈希/差异；测试源码保持不改。
- `offline-ffdop/receipt.json`：后续仅 FF_DOP 的本地源码单差异、签名二进制、实际指令回归及官方源文件哈希。
- `verification.json`：REPAIR1 旧/新指令重放、785664 个 4KB 游标/大小边界案例、128KB 槽内 padding 和矩形数守恒检查。

新镜像的 OC1.0.8 `ocvalidate`、只读 FAT 检查、完整 kext 读回及仓库检查均通过；这些静态检查与实际 GPU 失败分别记录。

## 继续测试：REPAIR2-FFDOP 准备

在用户要求“继续修复后测试”后，已将上述独立 FF_DOP kext 打包为新文件 `HP-UPSTREAM-6F03560-REPAIR2-FFDOP.img`，相对 REPAIR1 的 98 个 EFI 文件仅 NG 二进制不同；配置和先前修复保持。IMG SHA-256 为 `3047bd4377f41ba076ea418e177d91ac65064e26897a9119e92c534c6272e519`，NG SHA-256 为 `49fe4602565e6a65f3d9b4914336ee827b1eeb7eebb3a2186d95b8e85b31b30c`，UUID 为 `4C4C44D8-5555-3144-A164-F3EBD4ED5399`。

未向 kext 再加寄存器读回日志，使用已通过独立构建/签名和实际指令回放的候选。观察器增加 FF_DOP 安装日志门控，并要求 UUID、250 项内容及全部既有修复检查通过才即时启动 Metal；安装日志不冒充硬件寄存器实测值。OC1.0.8/FAT/完整读回与仓库检查通过。当前 NixOS boot `8d3b6832-9e4d-4272-b40d-9276527efd2a`，本轮试前完整 USB 启动资产已收回，98EFI 与 REPAIR1 匹配且 env 已消费正确旧目标。

准备使用新的 `offline-ffdop/trial-control.py`、`observer.py` 和独立 `trial/`，保留旧脚本与所有证据；交付/武装/一次正常重启/实际结果由新生命周期回执记录。此段为准备完成，不能视作新镜像已经启动或功能通过。

### REPAIR2 实际启动

随后新 trial 已完成交付与全图读回、独立 env 备份及单次武装，06:25:39UTC 正常重启。06:27:10UTC 严格确认新 macOS25G83 boot `62335E47-3E14-4A4D-BBD0-4253AA5DC62C`；250项内容、NG UUID、R3/R4/REC/KPOOL/REPAIR1 及 FF_DOP 安装门控均通过，实际 IOSurface 验证和 rect 钩子也已命中。06:27:44UTC idle0启动 Metal；此刻尚无结果。独立观察器 PID3093284，证据 `offline-ffdop/trial/run/`，完整 stream/history 和首reset全量快照保持，不重复部署或负载。安装门控通过与实际 GPU 正确性验收仍分别记录。

### REPAIR2 运行态失败及完整现场

06:28:25UTC 再次出现 workload303 failed validation，输出推进至 Horizon Detection 后没有继续，也无有效分数。06:28:53UTC首reset后，完整dmesg、IORegistry和所有DiagnosticReports均成功收回；首故障仍是context5，ACTHD`0x0a000140`、IPEHR`0x61040001`、EIR/ESR`0/0`，HEAD本轮为`0x04a036c0`。160.895845秒实际REC restore/replay各1。

与REPAIR1的279秒终态不同，本轮06:40:35UTC仍可严格SSH确认同macOS boot，Geekbench508/509仍在；不能将它说成已panic重启，亦不能仅凭GPU工作停住就说整机无响应。06:40:31—06:43:56UTC额外完成完整无筛选dmesg、IORegistry、系统及所有用户DiagnosticReports和完整进程表采集，全部exit0。IORegistry的reset、sibrestore、sibreplay、exfix均57，实际恢复循环没有让负载继续。原始记录及SHA见`offline-ffdop/trial/stalled-live-snapshot/receipt.json`。

该单变量FF_DOP修正不足以解决303与初始RCS故障；这一轮较长保持SSH可用只是一轮观察，不能宣称系统稳定或panic已修好。现场已完整保存后，计划只停止身份与boot核实的本轮压测进程，正常重启回NixOS并由现有观察器先取全EFI/所有reports；这种回退必须记作代理正常重启，不冒充panic自动恢复。

### REPAIR2 最终取证与恢复方式

后续按上述计划执行，但终态证据表明正常重启流程中另有watchdog故障：

| UTC | 事件 |
| --- | --- |
| 06:46:25 | 重启前完整 `nvram -xp` 收回；只有非数字000K，没有数字panic块 |
| 06:46:27 | 同boot、uid、父子关系和完整命令行核实后，仅对本轮508/509发SIGTERM |
| 06:46:38 | 观察器记录应用SSH退出255；这是主动终止后的负载结束，不是正确性通过或失联证据 |
| 06:46:42 | 确认两进程已消失后请求正常 `/sbin/reboot`，SSH随重启关闭 |
| 06:50:29 | 严格确认NixOS boot `2033d9ca-5474-43ca-8066-22972d5cef32` |
| 06:50:46 | 全EFI、系统及所有用户DiagnosticReports、远端比对全部exit0 |

新EFI五个数字块全部新鲜，3234 packed bytes逐字节往返一致，decoded SHA `86dd9cf85719b772b595c3fe501d794e16e056a1fd351e45b2b072826842a028`。终态在 **1414.756169812秒**：`no checkins from watchdogd in 185 seconds`、`shutdown in progress, vfs shutdown not yet started`、`System shutdown begun: YES`，当前线程为kernel_task。因此正确归类为 **代理正常重启请求后，在重启过程中发生shutdown watchdog panic，随后返回NixOS**；不是测试中自发panic回退，也不是干净完成正常重启，更不把本轮此前仍能SSH的状态称为整机卡死。

完整stream共376305行，gzip及JSON全部通过；共有68个hang摘要，context5×66、19×1、77×1。后期IOReg57次reset/restore/replay/exfix与较早全dmesg中的56个摘要是不同时间点采集，不作强行一一配对。可取得history共1244491行，gzip有效、最后1条JSON因主动重启截断，原件保留且截断记录单独存档；不称完整历史回填。

本轮11份14xx时间戳的gpuRestart内容均为context5；另15份字节有变的旧时间GPU报告不归为本轮新事件。磁盘`Kernel-2026-11-03-142644.panic`是 **REPAIR1的278.950405105秒panic回填**，不混为新终态。首次派生JSON中笼统`new_gpu_reports`标签已纠正为字节变化集合与本轮时间匹配集合，旧派生JSON另存，原始tar保持不改。

用后USB完整启动资产已收回，98EFI与REPAIR2一致，env消费正确REPAIR2目标。终态分析 `offline-ffdop/trial/analysis.json`、完整性 `trial/posttrial-integrity.json`、USB检查 `trial/posttrial-boot-assets/verification.json`、首次与后期全量现场均保留。当前无运行负载；后续需审查ROW_CHICKEN2的MCR/forcewake/上下文保存覆盖及303实际输出/dispatch，尚无第三候选。

最终`make check`（46Python/42JSON/36Markdown）、`git diff --check`、本地脚本语法及29份测试源码/基底IMG/结果IMG/NG重新读回均通过。`offline-ffdop/final-verification.json`和`artifact-manifest.json`保存核验与224项可读资产哈希，唯一无权限项为临时FUSE辅助文件`trial/run/post-nixos/helper/fusermount`，全部原始证据可读且已哈希；不为该辅助文件改变权限或扩大目标机操作。私有材料保持Git忽略，未提交或推送。
