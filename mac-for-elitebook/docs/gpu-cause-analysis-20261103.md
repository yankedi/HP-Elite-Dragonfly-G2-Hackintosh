# GPU 故障原因分析：2026-11-03

**后续实测与勘误：** 用户随后已授权检查后直接实测，结果见 [REPAIR1实测与离线修复](driver-repair-trial-20261103.md)。本报告原先把 ring 中 `0x03800000` 标为 `MI_ARB_CHECK`，现按 Linux 命令定义更正为 `MI_REPORT_HEAD`；`MI_ARB_CHECK` 是 `0x02800000`。更正前原文已私下归档，SHA-256 `4164d13161954fde658aeb933825326c8d002fda4b06b92d8cc95ea6fdfe7e3d`；既有原始日志和旧分析产物保持原状，勘误证据见新试验 `panic-analysis.json`。

## 当前结论与范围

用户要求无人值守分析，并明确此后**不再测试新镜像**。本轮工作为恢复后只读取证、本地实际二进制反汇编、带指令地址的手工伪代码还原和跨试验比较，没有新镜像实测。

目前有三个不同层次的结论：

1. **本轮最终 panic 的直接机制已定位：TGL 驱动计算 IOSurface 资源布局时除以零。** 同时确认旧驱动与当前 Tahoe 的 IOSurface 私有字段布局不一致，现有修正被真实 TGL 的机型门控跳过。这是明确的兼容性缺口，也是解释本次除零的高可信方向。
2. **初始 GPU hang 仍不能唯一归因。** 它早于最终除零，且在不同试验出现不同命令流/复位状态；不能用终态 panic 替代初始故障解释。
3. **“扩大少量小命令池即可修好”的解释不成立。** 补丁实际命中后，303 校验失败、RCS hang、原有 context19 特征仍出现；反汇编也不支持用一次大预留请求直接证明越界写。

本轮分析材料在私有目录 `.local/gpu-cause-analysis-20261103/`；完整原件仍在各试验目录，未以筛选结果替代原件。

## 1. 证据和实际二进制归属

用户恢复 NixOS 后，严格 SSH 核实操作系统和新 boot ID；原有观察器已完成完整 EFI、系统及所有用户 DiagnosticReports 采集及远端 tar 比较，均退出 0。最新 KPOOL 试验的 98 个 EFI 文件与交付候选完全一致，一次引导环境指向正确目标且已 consumed。

最新完整采集：

- EFI tar SHA-256：`3ad72535a5869774d38c89f92be9cea4a4764d94c35a46fe16a7ca3b1741bd94`。
- DiagnosticReports tar SHA-256：`b7f9d8dbbc0c07bb169b877df76b84bef4d102e749e1e2c6217457dd0ea4735c`。
- 9 个新鲜数字 PanicInfo 块，合计 6279 个压缩字节，解码/重编码逐字节一致；最后一块非满块。
- 解码文本 SHA-256：`919741ed09514c4866e70eaa8815aaaf5879b3dfbf5113620ea205e8604d0355`。
- 完整实时流 337607 行、可获得的历史回填 17613974 行，gzip 完整性通过，均无非 JSON 行。历史回填结束于采集启动附近，不能当成后续实时记录。
- 首次 reset 时完整 dmesg、IORegistry 和所有 DiagnosticReports 快照均已收回。终态报告相对上轮新增 8 份 gpuRestart；磁盘未新增本轮 panic，当前终态来自新鲜 EFI。

实际驱动身份与 panic 中的 UUID 相符：

| 组件 | 核实身份 |
| --- | --- |
| 系统 | macOS `25G83`；上游安装目标为 `25G241`，现场保留 `XE_FORCE=1` 差异 |
| TGL | UUID `BA3AA1C0-FE6B-33B3-9D85-73F848394E3D`；SHA-256 `1b2f5aa3131f9b909fe984877e41d5ebcdb2837572b45e1e901a72a6271515a2` |
| IOSurface | UUID `8E1FFEDA-8C53-336F-B59B-776024E3B66D`，从现有实际 BootKC 提取分析 |
| IOAcceleratorFamily2 | UUID `B77A42EC-6B0C-3A8D-89A2-B8F4CDBAC8C9`，从现有实际 SystemKC 提取分析 |
| 固定上游源码 | `6f03560ef9694f9826caae15624d4a6cb1bf9ffc`，各单变量差异另有源码回执 |

本地重新读取并核对各镜像与 NG 二进制哈希，未只沿用文件名：

| 版本 | IMG SHA-256 |
| --- | --- |
| 修正重启参数的干净基底 | `4f5159f98b229f6e1cd142c5b583afbad0a215116a624e60cefb62516b976b76` |
| R3 | `cb44495996b8e483044ebd7007ddb8ae63b690ab14c41bb5bd857d6ee387bca6` |
| R3+CCS | `24b5d16d5a77d387451bc468ab547ec523dae5817d4cce7490dc615786ceb437` |
| R3+CCS+REC | `13e4b7804d4edac72c69f8f816160847e3b5af29ec1babf51026e0c44ec7062c` |
| R3+CCS+REC+KPOOL | `4285f20880b9b3847034771b4d66b632919871ad18d6e01cdb411d45809adcc2` |

机器可读完整映射为 `configuration-map.json`。

直接从上述五个 IMG 读取的 `config.plist` 均为 SHA-256 `7df7f1f674e485195bfb5e8c94779047976131e5da7b2b573e4043d181ac71fd`。NG 本体的镜像内读取也与各构建二进制逐哈希吻合；并非仅检查构建目录。

## 2. 最终除零：指令已经定位，存在明确的 IOSurface 布局错配

本轮 KPOOL 新鲜 EFI 报告：

- uptime：`860.583301957` 秒。
- 当前线程进程：`VTDecoderXPCService`。
- 故障：`divide error`，不是 WindowServer watchdog。
- 符号：`IGAccelResource::calculateIOSurfaceDeviceCacheVRAMBytes + 0x399`。
- 对应 TGL 文件 VM：`0x72bcd`，机器码 `41 f7 f7`，即 **`divl %r15d`**。
- 保存的 `R15=0`、`RAX=0`、`RDX=0`，直接证实除数为零。

实际二进制的关键路径：

```text
TGL 0x7287d: 读取 IOSurface + 0xb0，作为旧的 plane-count
TGL 0x72890: 非零时用该值决定 plane 表/循环数量
TGL 0x72bb6: 根据最初的旧字段是否非零选择分支
TGL 0x72bcd: bytesPerRow / bytesPerElement，未保护零除数

当前 IOSurface::getPlaneCount():      读取 this + 0x98
当前 IOSurface::getPixelFormat():     读取 this + 0x80
```

当前系统的 `getPlaneBytesPerElement(plane)` 会检查真实 plane-count：有有效 plane 表且索引合法才取表项；无对应 plane 时，仅 plane0 可使用整面字段，其余返回 0。这与旧驱动从错误字段得到循环数量、访问不存在的 plane 后除零的机制吻合。保存的 `RSI=2` 也与非法 plane 索引的回退路径相容。

还保留两条界限：

- 函数有另一个 override-dictionary 分支，会显式把除数寄存器置零；单凭保存寄存器不能完全排除该分支。
- 没有本次 IOSurface 对象的完整内存，不能声称已读到该对象 `+0xb0` 的具体值，或已严格证明真实 plane-count。

因此，**已证实的是终态除零、字段布局不匹配和缺失的运行时修正；“错误 plane-count 导致本次非法 plane”是有直接静态支持的高可信因果解释，尚缺对象级运行证据。**

### 为什么已有 PLANES2 没有覆盖本机

固定源码的 `kern_gen11.cpp` 已有 `XE-PLANES2`，把该唯一匹配的旧 `+0xb0` 读取改为 `+0x98`；但它放在整个 `if (!isRealTGL)` 分组中。实际 dmesg 明确 `isRealTGL=1`，随后跳过该组。当前 R3/R4/REC/KPOOL 的有限移植均未包含 PLANES2。

这里的问题是把**操作系统私有 ABI 兼容性**和**CPU/GPU 拓扑适配**放在同一个机型门控中。真实 TGL 不需要伪造拓扑，不代表移植来的旧驱动可以使用 Tahoe 旧布局。

同组 `XE-FMT` 还针对另一个旧偏移 `+0xa4`，但实际 `25G83` getter 是 `+0x80`。现有上游处理是强制 BGRA，并不是通用格式转换。后续静态修正设计应优先采用真实 getter/经版本核实的布局，保留多平面 YUV，不能为了消除 panic 就把所有表面强行改成单 plane 或 BGRA。

## 3. 干净基底和 R3-only 的 CPU 写故障

### 3.1 Blit3D scratch

干净基底两次在 `61.439744361`、`75.318373340` 秒触发 WindowServer 写页故障，目标为 scratch 起点 `+0xd000`，尚余 `0x44` 字节复制。

实际 `blit3d_initialize_scratch_space` 在文件 VM `0x319f6..0x31a09` 执行 `memcpy(base+0xd000, ..., 0x44)`，其后写入最高到 `+0xd20f`。这些写入**都在参数声明的 `0xd240` 逻辑长度以内**。

这纠正了一个容易混淆的说法：基底证据不是“初始化器必然超过声明长度”；它显示实际 CPU 可访问范围在页边界出现问题。R3 将申请对齐到 `0xe000` 后能跨过该故障，支持分配/映射粒度兼容性方向，但本轮尚未把具体截短位置唯一定位到某个分配器或映射函数。

### 3.2 `resolve_ccs+0xc7`

R3-only 新鲜 EFI 在 `68.426917103` 秒报告 SecurityAgent 的写页故障。当前实际 TGL 的反汇编和外部重定位明确：

```text
tail  = align_down(rectangleCount * 72 + 0x13f, 64)
cursor = pool->getBufferPtrNoInc(2)
state = cursor + 0x1000 - tail
first rectangle write = state + 0xb0
```

保存寄存器与 `rectangleCount=1`、`tail=0x180` 的计算逐项吻合，得出的写地址正好等于 panic 的 CR2。调用并不是按实际 tail 大小向 pool 预留足够空间，而只传入 2 DWORD；这一结构值得继续审计。

但没有该时刻 pool 的 base/end、实际分配长度及完整对象，不能把源码注释中“buffer2 不存在”直接提升为已证实事实。R4/NOCCS3 的入口直接返回，只绕开该路径，并未实现正确 CCS resolve，后续资源内容正确性仍然需要独立解释。

## 4. 小池容量：有 API 风险，不等于已证明越界

实际 IOAF `getBufferPtrNoInc` 会检查当前游标与剩余空间；切换到新固定容量 buffer 后直接返回，不再按请求长度检查新 buffer 是否足够。这个 API 使用约束确实存在。

然而，TGL `blit3d_init_ctx` 的反汇编显示：

- 预留请求：`0x3ffe` DWORD。
- 本函数实际构造的块：`0xa00` 字节。
- 最终 `setBufferPtr(start + 0xa00)`，返回 `0x280` DWORD。

**一次大的预留请求不是一次同等大小的写入。** 仅凭它和 4KB 小池，就断言此初始化器已写越界，证据不足。此前 KPOOL 候选的容量假说应据此降级，而不是继续扩大池子碰运气。

更直接的反证来自已结束的 KPOOL 试验：5 次启动期小池调整日志明确 count8、4KB→128KB；仍有 303 校验失败，终态 8 份新报告中还有：

- `00:57:30`，context19，RCS busy-in-batch。
- ring 中的 batch 跳转为 `0x40006e40`，并非上轮 `0x40007e40`。
- `ACTHD=0x40008004`、`IPEHR=0x401a8001`，`EIR=0`、`ESR=1`。

即相似旧模式仍存在，但不能把所有寄存器说成完全相同。现有日志未将该 PPGTT batch 归属到具体 pool/资源，扩大少量小池也不覆盖所有 count256 的池。

## 5. RCS hang：至少有三种观察，不宜混成一个错误

| 观察 | 证据 | 能推出什么 |
| --- | --- | --- |
| 首次 context5 ring 卡住 | KPOOL 首次完整 dmesg：HEAD `0x3e88`，IPEHR `0x61040001`，EIR/ESR 均 0 | HEAD 附近 `0x03800000` 为 `MI_REPORT_HEAD`（本次勘误）；IPEHR 不是该处 ring DWORD，不能据此认定非法命令 |
| 后续 context5 batch 卡住 | 7 份终态报告：PIPE_CONTROL header `0x7a000004`，不同 batch 地址 | 命令执行/同步问题持续存在，不是一次 reset 后就恢复正确运行 |
| context19 特征 | REC-DIAG 和 KPOOL 均出现 ACTHD `0x40008004`、IPEHR `0x401a8001` | 小池扩容和恢复代码都未消除此模式；缺失 batch 内容和资源映射，不能唯一定位生成者 |

本地 Mesa 源码提交 `863338275d915e867319c3690ffd3272b06303c3` 的 genxml 继承检查识别 `0x61040001` 对应旧 Gen8 `GPGPU_CSR_BASE_ADDRESS` 编码，该命令在 Gen11 被显式排除，不在有效 Gen12 定义中。这是值得追踪的兼容性线索，**不是已经证明 TGL 在执行一条不支持的故障命令**：只有 last-header 寄存器，缺完整 batch 和上下文归属，也未在本地 TGL kext 中找到这个完整 DWORD 字面量。

ring 中 `MI_BATCH_BUFFER_START` 的 ASI bit8 为 1，即 **PPGTT**。因此不能把低地址数值和某个 GGTT `HWS_PGA` 相等，当成已经跳进硬件状态页的证明。

## 6. 恢复代码能做什么、实际做了什么

实际 TGL 反汇编已核实 RCS/CCS 共用 render reset mask `0x2`，但原路径只恢复自身寄存器列表并重放自身引擎。REC 对该共享域次生丢状态问题有针对性。

REC-DIAG 与 KPOOL 首次 reset 的完整 dmesg 均明确：

```text
reset RCS ret=1 kick=0
sibling HWS 0x40005000 -> 0
restore=1 ownfix=0 replay=1
```

IORegistry 计数也核实寄存器恢复/重放确实发生。它证实恢复处理已运行；不是仅凭 `route=1` 推断。

但代码先调用原 `resetGraphicsEngine`，再恢复 sibling；它没有重写最初导致 hang 的 batch，也不修正 IOSurface 布局、303 数值输出或 CCS resolve 的正确性。一次 restore/replay 计数不证明随后 stamp 正常返回。

完整实时流中 `no channel associated` 的条数：CCS idle360 为114、CCS idle0 为68、REC首轮为0、REC-DIAG为0、KPOOL为116。各轮运行时长和终态不同，这些不是可直接比较的故障率；KPOOL 的116条至少否定“装了REC就必然消除通道问题”。

## 7. 跨试验因果顺序

| 配置/试验 | 早期实际结果 | 终态 |
| --- | --- | --- |
| 干净基底，两次 | 启动期 Blit3D CPU 写页故障，未开始 Metal | 同一初始化写故障 |
| R3-only | 跨过前项后到达 CCS resolve 写故障 | SecurityAgent 内核页故障 |
| R3+CCS，idle360 | 首次 RCS hang 早于 Metal 约260秒 | WindowServer watchdog，1132.591秒 |
| R3+CCS，idle0 | 303校验失败后出现reset | watchdog，573.046秒 |
| REC首轮 | 303校验失败后出现reset | watchdog，292.872秒 |
| REC-DIAG，同二进制 | 8项名称均打印，303仍失败；上传被隔离网络拒绝；之后发生一次hang | 代理正常重启回NixOS，无本轮新鲜panic证据 |
| KPOOL | 303失败，首次及反复RCS hang | VTDecoder资源布局除零，860.583秒 |

303 错误在 idle0/REC/KPOOL 多轮均早于首个记录到的 GPU restart 请求；它不只是“重启之后内容变坏”。但“早于记录到的 restart”不等于此前没有任何 GPU 错误，也不能证明它与 reset 是同一个根因。现有数据没有 303 的参考/实际输出差异，不能把 kernel-panic 修正当作数值正确性修正。

## 8. 后续原因定位方向

在本次禁测新镜像的范围内，合理顺序为：

1. 将 OS ABI 修正与硬件拓扑门控拆开进行设计审查；优先核实 plane-count、pixel-format 等真实 getter，保留格式和多平面语义。此次已定位到具体缺口，但未声称修正已实机验证。
2. 继续围绕 CCS 的准确预留量、buffer 游标/边界和 CPU/GPU 地址换算审计，而不是把入口跳过或任意扩容当成完整实现。
3. 对 RCS 初始故障保留独立问题：当前材料没有对应 batch 全文、PPGTT 页表/资源生命周期映射和 GPU-host 输出差异，无法从摘要唯一恢复其原因。静态扫描没有替代这部分运行时数据。
4. 任何将来扩展采集/实测范围都须另有用户授权；当前不自动启动新镜像或新 GPU 负载。

复现材料包括 `audit-binaries.py`、`analyze-evidence.py`、实际函数 `.bin/.asm`、`tgl-relocations.txt`、`reconstructed-paths.c`、配置映射、跨轮时间线及终态报告选择。`reconstructed-paths.c` 明确为人工还原的非构建伪代码，不是可交付驱动修复。
