# GPU hang：现有证据离线复核（2026-11-04）

## 状态

用户说明 EliteBook 暂时不能测试，USB 已插在开发机；本轮仅做本地分析，没有连接目标、写 USB、请求重启或修改固件。**GPU hang 尚未修复**，不将可能机制当成已证实根因。

## 已观察到的现象

1. R28 和 R28 retry1 的原始 dmesg 均出现 `ACTHD=0x0a000140` / `IPEHR=0x61040001`。两份日志中相邻的 Apple GPU hang summary 分别报告 context ID **7** 和 **94**；同一寄存器组合不能一概称为固定的 context 5，也不能仅凭数值一致断定是同一原因。R28 retry1 的 summary 显示 RCS busy、`BB_ADDR` valid=0、`IPEIR/EIR/ESR=0`；这些只反映采样时报告状态，不证明实际读取的 batch 地址、非法命令或不存在故障。
2. R28 retry1 在首次 hang 的 MMIO-only 结束标记后保存了 1,479,351 字节 dmesg 并请求重启，随后观察到 NixOS `a08af76a-46ad-4b34-9e3f-8381906b53df`，post-NixOS EFI 和 DiagnosticReports 收集 exit 0。请求时 SSH exit 255 不单独证明重启成功。并发首次 reset 的 dmesg/ioreg/DiagnosticReports 请求均 exit 255、空文件；不能当成完整采集。本轮没有 Geekbench Metal 完整通过。原件与哈希在 `.local/driver-repair-20261103/repair28-mmio-only/r28-retry1-evidence-receipt.json`。
3. R11 poolguard 实际命中其小 buffer 边界案例后仍出现目标寄存器组合；R12 STAMPFIX 核心路由安装后仍出现该组合。它们不能作为目标 hang 已消除的证据，也不能排除不同 hang 有共同因素。R9/R10 的池大小/对齐对照已阴性，不重复。

## 六轮候选范围核查

对 R20 retry1 和 R21–R25 的六个保存日志，按日志中的候选编号及 GPU 起始地址配对其打印出来的 descriptor，再用其显式长度核算：六次的 `BB` 都**不在**保存的候选副本内，也都不在配对的日志 descriptor 范围内。四次差值 `0x3f9c`，两次 `0x2d4c`；这些差值由“在 64 KiB 内选附近项”的算法影响，不能当作硬件重复越界的证明。

例：R20 retry1 的候选 `0x4bd727ec`，副本 3480 字节，配对 descriptor 长 `0x1520`、结束 `0x4bd73d0c`，而 `BB=0x4bd76788`。原日志标签 `target inside batch` 不可靠。对这份候选的 CPU/GPU 内容、页和生命周期作出的旧结论不能用于修复。范围核查原始输入哈希和逐轮结果：`.local/gpu-diagnostic-audit-20261104/candidate-range-audit.ndjson`；脚本只做日志数值核算，不证明日志条目是同一活跃对象。

## 提交路径的静态证据

固定 TGL 二进制 SHA256 `1b2f5aa3131f9b909fe984877e41d5ebcdb2837572b45e1e901a72a6271515a2`。`IGAccelFIFOChannel::submitBuffer` 依次加载 descriptor `+0x18/+0x20/+0x30` 到 RSI/RCX/R8D，并调用 ring vtable `+0x118`。基类与 Main ring vtable 在静态文件的对应槽都指向 `submitBatchBuffer` 的 `0x42f7a`；该函数记录 RSI/RCX，并用 RSI 产生 batch-start ring 命令。证据 `.local/gpu-diagnostic-audit-20261104/submit-link-audit.json` 和完整反汇编 `.local/gpu-diagnostic-audit-20261104/tgl-submitBatchBuffer.disasm.txt`。

这支持这两个 descriptor 字段在该静态提交路径成对传递，**不证明现场 ring 动态类型、CPU 指针和 GPU 页表指向的物理页相同、hang 时对象还存活、或正在执行同一段命令**。需要真正归属和时序证据；不能回到 R25/R26 的物理页覆盖方案。

### Tahoe IOAcceleratorFamily2 的具体构造路径

从之前留存的 SystemKernelExtensions.kc（SHA256 `fbab2d48bf1470fb0ec15dd62a6bb90c39d8bb45ed68240d3c73f1e43e770dee`）离线提取实际 `IOAcceleratorFamily2`，UUID `B77A42EC-6B0C-3A8D-89A2-B8F4CDBAC8C9`。在 `IOAccelCommandBufferPool2::submitBuffer` 的 `0x145883ca–0x1458854f` 静态指令中可见，某一提交路径按下式构造 descriptor：

```text
descriptor[+0x20] = pool[+0x1848]                     // CPU 指针值
descriptor[+0x18] = map_virtual_slot_0x128() + pool[+0x1848] - current_slot_cpu_base
descriptor[+0x30] = (pool[+0x1858] - pool[+0x1848]) >> 2
```

同一系统二进制的 `getGPUVirtualAddress(ptr)` 采用相同虚调用和 `ptr - current_slot_cpu_base` 算术。这比“两个值数值接近”更强：**该路径设计上用同一个槽内偏移关联 CPU 指针和 GPU 虚拟地址**。但虚表槽的最终运行时目标、该提交是否为现场目标、页表内容、IOMMU/地址空间及采样时刻仍未验证，仍不能推断实际物理页或挂起原因。

同一 `submitBuffer` 的轮换路径直接调用 `IOAccelMemoryMap::testEvent`；条件不满足时可以调用 `allocMoreCommandBuffers`，再走 `IOAccelMemoryMap::finishEvent` 分支。分配路径直接调用 `IOAccelSysMemory::withOptions` 和 `lockForCPUAccess`。这表明该**静态路径存在事件检查、扩容和等待/完成相关调用**，推翻此前“驱动必然没有生命周期处理”的推断；尚不能断定现场分支是否执行、事件是否正确或有无提前复用。

六段函数原始字节/反汇编和 SHA256 收据保存在 `.local/gpu-diagnostic-audit-20261104/pool-function-extract/`；`.local/gpu-diagnostic-audit-20261104/pool-mapping-audit.json` 是逐指令字节和相对调用目标的离线复核。提取结果和已保存系统 KC 均未修改。

### 事件路径进一步复核

同一保存的 SystemKC 中，`IOAccelMemoryMap::testEvent` 和 `finishEvent` 分别把 `map+0x38` 传给事件机虚表 `+0x190` 和 `+0x188`。`update_pte` 的静态代码先调用事件机 `+0x188`，再调用 map 虚表 `+0x180`；这不证明任何具体映射在运行时执行了该路径。Fast2 静态虚表相应槽原始值的低 30 位分别匹配命名的 `testEvent` 和 `finishEvent`，但尚未解码 chained pointer，也未验证实际动态类型。

Fast2 的 `testEventUnlocked` 最多检查八个条目，可提前返回，比较缓存及重新读取的 stamp；`finishEventUnlocked` 包含对 `0xe00002d6` 的比较及指向 `signalHardwareError` 的直接调用。**这只能描述静态控制流，不能说明现场事件超时、提前复用或 PTE 错误。** 字节核对结果 `.local/gpu-diagnostic-audit-20261104/event-path-audit.json`；函数字节、反汇编及各自哈希收据在 `map-function-extract/` 和 `event-function-extract/`。

## 指令和拓扑线索

- 固定 Mesa genxml 提交 `863338275d915e867319c3690ffd3272b06303c3` 中，`0x61040001` 匹配 Gen8 的 `GPGPU_CSR_BASE_ADDRESS`，Gen11 显式排除此定义，Gen12 继承集合中没有与该固定头匹配的定义。机器可读复核 `.local/gpu-diagnostic-audit-20261104/genxml-header-recheck.json`。Mesa 数据库缺定义**不是** Intel 硬件非法命令的证明；IPEHR 是采样值，可能非当前故障指令或跨状态。尚未得到同一地址空间中的完整实际命令流，不应修改或跳过该命令。
- R28 retry1 的启动 dmesg 显示 native 1 slice、10 subslices、80 EU，旧 TGL 驱动打印该 SKU 拓扑不匹配及 `L3BankCount: 0`；随后 `HP-NATIVE4` 按已有本机 NixOS 测量把 L3 0→6，镜像维持 1/10。静态分支 `0x28781–0x28822` 支持该驱动的特定 SKU 路径对 10 subslices 打印错误；但日志和 fallback **没有证明**拓扑是 hang 根因，不能仅凭此更改 EU 数、L3 参数或关闭工作线程。应继续本地追踪该分支返回后的使用者与已知对照试验。
- R20–R26 旧 walker 把 Gen12 PTE bit 7 当 64 KiB PS；固定 Linux v6.12 定义 bit 7 为 PAT2、PS64 为 bit 8，另有 PDE IPS/compact 的不同模式。旧比较还忽略页内偏移与 descriptor 偏移。旧页内容和 `samePhys` 不足以证明别名、TLB、cache 或 UAF。

## 本地准备及下一步

R29 已从 R28 另行构建本地诊断 kext：在 FIFO `submitBuffer` 同步时记录有界的 descriptor 地址、计数、ring、PID 和序号；hang 时只打印与同 ring、数值范围匹配的记录，**不读取 descriptor 的 CPU buffer，也不读写 PTE/物理内存**。NG SHA256 `707b508936f8c430024cebbcaf648d5b3f69aa4880b6b4d1fb3a16d9dfc6fdae`，构建收据 `.local/driver-repair-20261103/repair29-submit-snapshot/build-receipt.json`。静态/离线测试覆盖记录范围与不同结束标记；该 hook 仍有并发、对象有效性、日志关联和扰动风险，未经实机测试，且只是一条诊断，不是修复。

### R29 hook 审核：现有构建不应部署

对照源文件 SHA256 `780143a72a8ebb397abf9f8cae7492b8072ea567341903dc7305ca62bc3eca18` 和原 TGL 二进制 `1b2f5aa3131f9b909fe984877e41d5ebcdb2837572b45e1e901a72a6271515a2`，发现具体边界，原 R29 继续标为 **未部署、不得直接实测**：

1. hook 在调用原 `submitBuffer` **之前**读取 descriptor 和 channel 字段；`hpBtKernelPtr` 只检查数值形态，不证明地址可访问、对象存活或布局匹配。原函数 `0x4c6d7–0x4c6e2` 有可能在读取 descriptor 前因状态位直接退出；hook 增加了原路径不一定发生的解引用。记录只是进入 hook 时的尝试，不证明原调用提交成功。
2. 同一原子 try-lock 保护写入和读取，取得锁时可避免该数组的并发读写；忙时提交记录被静默跳过，hang 采集报 `status=unavailable`。锁一直持有到多次 `IOLog` 结束，可能延长关键路径或导致更多丢样；这是静态风险，并无现场死锁或实测延迟证据。`HP-DIAG-END status=complete` 在 unavailable 或高位 BB 跳过之后仍可能输出，只表示诊断路径走完，不表示元数据完整。
3. 匹配是同 ring 指针加数值半开区间，最多报告八条，并非 context/地址空间、对象身份或执行证明；漏记、环形覆盖和指针复用可造成漏报或误关联。BB 低两位被清除，高 32 位非零时跳过匹配。
4. 32 位 `gHpR29Next` 回绕到零时 `count` 变为零，随后渐增至 256，暂时忽略仍留在数组内的历史；需约 2^32 次成功记录才触发，实际是否达到未知。命中上限时日志的 `scanned=count` 是计划扫描数而非实际已扫描数；前八项均命中时只检查八项却报告 256。`.local/gpu-diagnostic-audit-20261104/test_r29_review.py` 固定源哈希并复现这两个边界；这是用户空间模型，不是内核并发测试。

下一候选应先重新设计同步与对象访问边界、正确报告丢样/截断和序号回绕，再做离线验证与安全审查；不要把现有 R29 构建当成安全诊断镜像。继续离线追踪 context 和映射；在用户恢复设备且允许现场测试前，不启动 EliteBook 或写入 USB。未来首个 hang 优先保存可得证据并尽快请求回程，SSH 不可达时无法保证无人值守自动回程。修复仍须完整 Metal 工作负载和稳定性检验。

### 无额外对象解引用的诊断设计草案（仅模型）

固定 TGL 二进制在 `0x4c828` 起为 ring 虚调用准备 ring 指针、GPU 地址、CPU 指针和 dword 数值，`0x4c851` 调用 `+0x118`；固定的基类 ring `submitBatchBuffer` 入口将这些参数存入 ring 内记录。字节与文件哈希由 `.local/gpu-diagnostic-audit-20261104/test_ring_metadata_model.py` 检查。**构想**仅在此 ring 方法入口记录传入的标量：ring 值、GPU 值、CPU 是否非空及 dword 数，不读取 ring、descriptor、CPU buffer 或 PTE；尽量保持原函数 ABI、参数、返回值及调用次数。不同 ring 动态类型、符号路由覆盖范围和 ABI 仍须核实；入口记录不保证实际执行或成功提交，也无法绑定 GPU context，数值匹配仍只是假设线索。

丢样方案草案：容量固定 256，尝试锁不成功则不等待并用适当的原子饱和计数器记丢样；另有饱和有效条目数，64 位序号回绕不重置条目数。锁内只复制有界快照到专用存储；释放锁后匹配、输出，报告实际扫描数、可用数、截断、busy、丢样采样值及饱和状态。丢样计数与快照非同一原子时刻，输出须明确是近似采样；快照缓存重入保护、原子实现的中断上下文安全、锁内拷贝耗时、日志本身和 hook 扰动仍需单独证明。不要在锁内 IOLog，也不要把可选元数据成功作为首次 hang 后回程的必要条件。

上述为用户空间参考模型 `.local/gpu-diagnostic-audit-20261104/ring_metadata_model.py`，不是 kext 实现、构建或部署授权；Python 锁尤其不能证明内核内存序、原子或中断安全。模型测试覆盖 64 位回绕、固定容量覆盖、busy/丢样、范围边界及命中上限的真实扫描数；缓冲区要求 2 的幂以保证序号回绕后的槽位映射。没有任何实机可靠性或修复结论，R29 仍不得直接部署。

### 2026-11-05：R30 scalar ring 诊断本地构建

用户告知 EliteBook 已重启 NixOS 且 USB 已插入后，通过 Tailscale 严格主机密钥只读查询，实际确认 `Linux / ID=nixos`，boot ID `5e7486a9-41fd-4921-b38d-0c36d3f7db17`。只读 `lsblk` 证实 USB 的 exFAT `4868-2795` 当前未挂载；原始查询 `.local/gpu-resume-20261105/lsblk-verified.json`。本轮没有修改 USB、内置 EFI、NVRAM 或请求重启。

基于 R28 源码（不是危险的 R25/R26 或 R29），另建 `.local/driver-repair-20261103/repair30-ring-metadata/` 并在开发机交叉构建。R30 额外路由 `IGHardwareRingBuffer::submitBatchBuffer`：只记录函数传入的 ring 指针值、GPU 地址、stamp 和第 5 个标量参数（对已审计 FIFO 调用点是 dword 数），**submit hook 不解引用 ring、descriptor 或 CPU batch**；相同 ring 加地址区间匹配仅作线索，不代表 context、物理页、实际执行或 BB 有效性。记录采用非阻塞 try-lock、固定 256 槽、单独饱和数量及 64 位回绕序号，输出丢样模 2^64；hang 时最多复制 8 条到小快照，释放该锁后再输出 `available/scanned/hits/truncated`。`HP-DIAG-END` 表示诊断代码走完，不保证元数据完整；原 hang 路由仍先调用原始分析，若其阻塞则不保证能看到首 hang 标记。

R30 NG SHA256 `ce5a74928089fe7d383fbd1baf7b7f8f976f288e9359f98056f1c333d8dc5d60`，UUID `4C4C4471-5555-3144-A101-9E0946CC7018`；构建收据 `.local/driver-repair-20261103/repair30-ring-metadata/build-receipt.json`。与 R28 源树比较仅 `kern_gen11.cpp` 不同。离线测试 `.local/gpu-diagnostic-audit-20261104/test_r30_ring_host.py` 从构建源码直接抽取 hook 用 host stub 编译并测试无效 CPU 指针不被解引用、原函数参数/返回、半开边界、64 位回绕、8 条上限、锁忙丢样及 4 线程 4 万次调用；这不是 macOS 内核中断/路由/真实对象生命周期验证。

**仅本地诊断构建，不是 GPU 修复，尚未打包 IMG、交付、启动或 Metal 测试，不得部署**。还须审查锁/路由实际 ABI、丢样及回程监督，结合未过滤的完整日志和硬件实测；此候选不能补出完整 batch 或 GPU 页表。

#### R30 首次试验准备（2026-11-05；尚无实机结果）

**后续实测结果（覆盖本节“尚无实机结果”的时效状态）：** R30 进入 macOS 并出现 GPU hang，Metal 测试中断；首 hang dmesg 在回程请求前保存，之后观察到 NixOS。试后新增的五块 PanicInfo 精确往返解码为 shutdown 期间 watchdog panic，uptime 364.730 秒、VFS shutdown 尚未开始；与本次启动参数和时间线一致，但文本不含 boot UUID，无法仅凭此证明 shutdown 阻塞原因或 GPU 因果。证据及哈希见 `docs/continuation.md` 最新条目。R30 的 `truncated=0` 仅表示当次扫描未提前停止，不表示历史未覆盖：256 槽是**所有 ring 共享**的滚动窗口；源码实际使用 `(BB_HI << 32) | (BB & ~3)` 作目标，同 ring 和按参数解释的区间同时满足才计命中。零命中不能证明 batch 不曾提交，也不能断言映射正确或错误。下一步离线追踪不同动态 ring 提交路径，并设计同时统计筛选阶段、覆盖程度的有界标量诊断；禁止从此推导物理页写入。

用户再次明确要求继续测试。已从 R28 镜像 `b0c315d45029f8fcff0e9558731860d9321c1f997c653bebb6862514d9b5b71d` 在开发机生成 R30 本地镜像 `0e97df741abe09dc107d5e3d7ab3372fddc5954d116a882e9c248047b023eac0`；98 个 EFI 文件只有 NG 可执行文件不同，OpenCore 版本匹配的 `ocvalidate`、FAT 检查和 ad-hoc 签名静态检查通过，不等于已启动。证据 `.local/driver-repair-20261103/repair30-ring-metadata/image-receipt.json`。

设备当前 `Linux/NixOS` boot `5e7486a9-41fd-4921-b38d-0c36d3f7db17`。同 boot 守卫只读备份 USB 的整个 `ventoy/`（`.local/gpu-resume-20261105/ventoy-before.tar` SHA256 `4beaece0354004c8bf8a277e3daf0e6e303b2246b45b3d92a98a45c39597604d`），env 为 consumed 且保留已被用户删除的 R28 镜像旧目标；原 recovery IMG 不在 USB，不能声称恢复介质可用。只读完成 EFI 全量 `5bda2b988927151ed2d1d0c941bd56df6f894e636d0589e47de02b9841f0343c` 与 DiagnosticReports `0bad4387b6b4eefb00a049416c8072f71ea1ee4d8d7239d06edf33d98772f9c3`；collector 各阶段、源比对和结束同 boot 检查均 exit0；与 R28 retry1 归档比较 258 文件、无新增/变化/缺失。

另建 R30 试验控制与 observer，依赖先前 R28 retry1 已真实完成一次回程的独立 return worker；新增 `hang=1 submit=1` 安装门控，首次 hang 后优先保存原始 dmesg 并尝试重启，关闭与其竞争的首次 reset 并行 ioreg/reports 采集；未过滤的日志流、启动前 IORegistry 和返回后的完整 EFI/DiagnosticReports 保留。只有回程请求/SSH 可用时才能执行，**SSH 失联时没有可靠带外手段，不保证自动返回**。`test_r30_trial_gates.py` 和 R30 host tests 是静态/本地检查，不证明上机安全。首次启动结果、是否捕获、是否返回、GPU 修复和 Metal 都必须以真实日志记录。

### Ring 路由、ABI 和并发边界复核

固定 TGL 文件的六个已命名 ring vtable：基类、Main、Blit、Media、VEBox、Compute，按假定的 Itanium address point 读取 `+0x118`，文件中均指向 `0x42f7a`。FIFO 的 `0x4c851` 虚调用前的机器码载入：RDI=ring、RSI=descriptor `+0x18`、EDX=stamp 值、RCX=descriptor `+0x20`、R8D=descriptor `+0x30`、R9D=descriptor `+0x6a` 字节，另把 `+0x69` 字节压栈。所查的目标函数尾部设置 AL=1 并返回。逐字节结果 `.local/gpu-diagnostic-audit-20261104/ring-route-audit.json`。这些只对一个静态调用点和所列具名表成立，不能证明运行时类、其他调用方、路由安装、跳板或全部 ABI 正确；若实现 hook 必须完整保留包括栈上参数和返回值的原调用。

R29 的 `hpBtInstall` 实际只路由 FIFO submit 和 hang；源里旧 `hpBtSubmitBatchBuffer` 虽存在，却会解引用 ring 和 batch CPU 指针并复制 buffer，**不能当成新设计直接启用**。`RouteRequestPlus` 先调用 `routeMultiple`，可选 pattern 回退调用 `routeFunction`；仅从包装层不能证明任何目标机上的 hook 或跳板安装成功。

内核并发仍是实现前阻碍：必须核实各调用上下文是否允许拟用原子操作，明确中断/重入情形、内存序、丢样计数饱和策略和计数采样竞态；busy 时不得自旋等待。饱和计数若用无界 CAS 重试，也可能违反这个时间约束。不能把参考模型的 `threading.Lock`（其 drop 计数甚至可能等待）直接翻译成内核方案。快照应有预分配且防重入的专用存储，不能假设 256 条可安全置于内核栈；锁外日志仍可能耗时。上述均为设计约束而非已验证实现，优先保证首个 hang 采集后的回程不依赖该可选日志。

### 无人值守回程：离线故障注入发现的缺口

对现存 `return_watchdog.py` 和 `safe_return.py` 进行注入式用户空间检查；没有 SSH、重启或目标访问：

1. 完整非目标 hang #1 与完整目标 hang #2 已在同一快照时，`capture_and_request` 优先选择目标 #2 作为文件/元数据标签，而非第一个完整 hang。原始快照本身仍完整保存两条；这不是丢失整份原件，但不符合按首个 hang 标记的预期。
2. 若先获得不完整 hang 快照，接着身份不可用直至超时，当前 watchdog 仅把快照留在内存，返回 `identity-or-capture-lost-no-reboot`，该快照并未持久化；拒绝无身份重启是既定安全边界。此情况与 R28 retry1 已保存的完整原件不同，不能把模拟缺口当作实机发生。
3. 若本地证据文件创建/同步失败，当前流程抛异常而不会发出 reboot 请求。这保留“不先落证据就重启”的既有策略，但无人值守时可能滞留 macOS；不能假定永远能回程，也不应为消除这一风险而绕过 OS/boot 身份校验。

复现代码 `.local/gpu-diagnostic-audit-20261104/test_return_gap_review.py`；测试记录当前缺口，不是认可这些结果。下一版本应研究首条不完整快照及早持久化、首个 hang 的标签语义和采集/存储失败时可审计的有界回程策略，并保持严格 SSH 主机密钥、远端同次 Darwin/boot 检查；存储失败时的取舍需明示且不能声称已有实机验证。现有原始脚本和 R28 收据未改，首次 hang 后尽快回程仍受连接和目标响应限制。

#### 回程状态机离线模型（不连接设备）

新增 `.local/gpu-diagnostic-audit-20261104/return_policy_model.py`，仅输出决策，不执行文件写入、SSH 或重启：

1. 从收到的完整原始快照中按顺序选择第一条可识别 hang，第一次就请求持久化原始字节；首条不完整时如果之后收到其完整标记，再请求保存完整原始快照，不把后一个 hang 的标记当首条完成。
2. 首条完成且相应持久化报告成功后，或首条不完整超过模型的 20 秒宽限期后，提出重新核实身份并执行远端同次 boot/OS 守卫的回程请求。保存尝试报告失败或超时则优先提出受守卫回程；**此分支可能损失证据**，体现避免卡在 macOS 的权衡，不能把该分支描述为保存成功。
3. 身份不可用或不匹配时模型不提出重启；远端守卫不匹配时禁止重启请求。重启请求不等于 NixOS 已返回。模型没有自动 post-NixOS 采集，实际必须仍由独立监督流程验证 OS/boot 并保存 EFI 和 DiagnosticReports。

六项注入式模型测试覆盖上述顺序、丢连接、存储失败/超时、首条标记和守卫；全套离线测试 59 项通过。**模型不会真的保存或重启，也无法强制超时**：真实持久化、`fsync`、日志和进程可能阻塞，需独立监督及可证实的有界失败处理；断网、系统卡死、远端拒绝请求及监督进程退出时仍不能保证回程。尚无集成、目标验证或部署，原 watchdog 未修改。

#### 子进程持久化监督原型（仅本地测试）

`.local/gpu-diagnostic-audit-20261104/persistence_supervisor_prototype.py` 在子进程以 exclusive create 写入完整原始字节，对文件和目录分别 `fsync`，并向父进程返回长度/哈希；父进程等待期限后尝试终止子进程，返回 `timed-out`、文件状态 **unknown**，不把超时视为未写入。各次操作须使用不重复路径，避免迟到子进程覆盖或冒充其他尝试。本地临时目录测试覆盖完整写入、拒绝覆盖、模拟卡住、无回执及不匹配回执；超时结果传入前述状态机后仅产生受守卫回程**决策**，测试不发 SSH 或重启。

边界：该原型不是可部署 watchdog，进程创建本身、调度、终止、内核不可中断 I/O 和父进程本身都不保证有界；即便已发终止，超时子进程也可能之后完成写入。`saved` 只是子进程报告写入及同步成功并非防断电的绝对保证；回执与证据应避免落到同一个卡住的 I/O 路径并需明确失败审计。尚未处理生产所需的启动失败、并发尝试的资源上限、子进程迟到回执/清理、Supervisor 自身崩溃、真实 SSH 身份守卫、记录文件命名及返回后完整采集。因此不接入目标，不宣称无人值守可靠。63 项离线测试及仓库检查通过。

#### 回程守卫和 NixOS 采集衔接审查

离线检查 R28 的 `observer.py`（SHA256 `e00f4d1d98a2db42ed41d8fa0969769ca69a67bb44a2b5bea96ad53d85974bad`）与 `collect-nixos-evidence.py`（SHA256 `e3ffd032f31da14ba0ef20c66305333cf6f2327f4d391c5ab9c06bcc2ad31995`）：observer 使用 Tailscale 严格主机密钥连接、检查 Linux/NixOS 与旧 boot 字符串，再启动独立 collector；collector 再次查询系统和 boot，执行 EFI 全量采集，并校验 APFS 分区及只读数据卷后采集完整 DiagnosticReports 与 tar 比较。采集中的失败不意味着 panic。

需要解决的衔接缺口：observer 的 `nixos_return()` 在 collector 非零退出后仍返回 True，不能把这个返回值当作完整采集成功；observer 的旧 boot 检查是全文字符串匹配，而 collector 独立接受自身查询的 boot，并未由调用者强制绑定到 observer 刚验证的新 boot。两次查询之间若发生重启，不能仅凭退出码视为同一 boot。现有 `ssh_transport.privileged` 在异常处理块之前读取私有 sudo 文件；本地故障注入证实读取抛错时不会调用 SSH 且异常向上传播，回程请求可能中止。此为模拟结果，非声称 R28 发生过该错误。

新增纯模型 `.local/gpu-diagnostic-audit-20261104/post_return_gate_model.py`：要求精确 Linux/NixOS、有效且不同于先前 Linux 的 boot UUID；分别区分 collector 退出失败、boot 不匹配、事件缺失和仅事件显示成功。后者明确标作 `events-only-unverified-files`：事件或退出码不是原件存在、哈希和归档完整性的证明。模型及注入测试没有调用 SSH、collector 或 reboot；实际实现仍须对同一 boot 绑定每阶段、保留未过滤原件、验证文件/哈希并收集失败回执，且需要受控实测。R28 retry1 既有成功收据和原件不受此审查影响。

#### 同 boot 采集与回程失败：本地模型

`.local/gpu-diagnostic-audit-20261104/boot_bound_collection_model.py` 接收**模拟**的到达身份及每个阶段前后身份、退出码和未过滤原始字节；以到达时验证的新 NixOS boot 作为预期，分别记录 EFI 和 DiagnosticReports 阶段。即使采集失败或之后身份不匹配，本地测试仍逐字节保留已收到的原始内容并计算哈希；若有阶段缺失、失败或 boot 不一致，不报告完整采集。测试中的成功也只标为 `raw-received-archive-and-provenance-unverified`，不声称真实归档完整。exclusive create 测试确认既有文件不覆盖。

模型还注入凭据读取失败、远端守卫拒绝及返回码等情况，区分未请求与请求结果不明，不记录凭据或异常正文；回程请求成功不能证明 NixOS 到达。这些回调均为模拟，没有读取真实凭据或执行 SSH。

限制：阶段前后身份仅是测试输入，不是实际 SSH 身份认证或远端原子守卫；两个检查间发生变化不能单靠模型排除。模型写入本地临时测试文件，没有 `fsync`、有界监督、实际 tar/文件/来源完整性验证或真实 EFI/APFS 采集，也不处理所有磁盘故障。必须把预期 boot 传入真实 collector 并让各次远端读取受同一 boot 守卫，分别记录每阶段失败和原始证据，再经过完整本地验证及受控实测；模型不得部署。

#### 同 boot collector 本地候选（未接入）

从保存的 R28 使用的 collector 原文件（SHA256 `e3ffd032f31da14ba0ef20c66305333cf6f2327f4d391c5ab9c06bcc2ad31995`）保留原件，另复制为 `.local/clean-upstream-20261102/backup/collect-nixos-evidence-bound.py`（SHA256 `d856905f03abb185a23ac0990f3c51a2ddb99e51aedc942f77477cfacfad5186`）。候选要求外部提供有效且不同的旧 boot 和预期新 boot，初次 NixOS 查询与预期匹配才继续原有的完整 EFI/DiagnosticReports 只读采集；沿用原有 EFI、分区检查和只读块服务的 boot 检查，末尾再查询 Linux/NixOS/相同 boot，不匹配则失败并保留已收集文件。它仍需依赖外部 observer 安全验证并传入正确预期 boot，检查不构成跨网络的原子身份保证。

`.local/gpu-diagnostic-audit-20261104/test_bound_collector_offline.py` 将所有 subprocess 调用替换为假函数，验证旧/新 boot 相同在查询前拒绝、错误 boot 和伪造的 `OTHER_ID=nixos` 在采集前拒绝、身份原始输出保留、匹配时下一步仍生成带 boot 检查的 EFI 命令。**测试在 EFI 调用之前刻意停止**；FUSE、完整归档、结束身份检查、采集失败与 observer 调用均未经集成测试，更没有实机验证。候选未接到任何 observer、watchdog、USB 或设备，不能部署；现有 observer 对 collector 非零退出仍返回 True 的缺口尚未修改。返回 OS 验证、完整采集和实际文件/哈希验证仍须分别确认。

#### 候选 collector 后续控制流离线测试

新增 `.local/gpu-diagnostic-audit-20261104/test_bound_collector_lifecycle.py`，在临时目录对上述候选运行控制流，所有 SSH、FUSE、tar、挂载检查及 sentinel 哈希均替换成假实现。测试覆盖：结束查询 boot 变化时非零退出且保留模拟原始数据；相同 boot 到达末尾标记；EFI 和 DiagnosticReports 失败时保留已生成的模拟字节且报告失败。这些是控制流检查，**不验证真实挂载、远端守卫、归档内容、哈希或硬件**。

另建 `.local/gpu-diagnostic-audit-20261104/post_return_integration_prototype.py`，仅调用注入的模拟 collector：将 NixOS 到达与 collector 失败/异常分开报告；退出 0 也只称 `collector-exit-zero-files-unverified`，不称证据完整。它未替换旧 observer，也不执行任何 subprocess 或 SSH。现有 observer 的状态缺口、文件持久性/哈希核验、异常与超时监督、同 boot 的真实远端读取和无人值守回程都仍待集成验证；R29 和该候选仍不得部署。

#### 首 hang 到返回后采集：隔离组合测试

新增 `.local/gpu-diagnostic-audit-20261104/return_flow_fixture.py`，把既有回程状态模型、可注入的持久化与守卫回调、返回后状态模型连在一起；不是运行用 watchdog。测试使用临时目录和子进程持久化原型，其他远端身份、守卫、重启和 collector 均是假回调：

- 模拟完整首 hang 先保存原始字节，再请求守卫回程；随后 NixOS 身份到达但 collector 退出 7，明确分别报告到达和采集失败。
- 模拟持久化超时后仅在重新提供匹配 Darwin boot 身份时才调用假守卫；守卫拒绝不表示发出了重启，也不把旧 NixOS boot 当作新到达。
- 模拟本地保存或传输异常，分别报告失败，不把重启请求当作返回成功，也不重复发请求。

对应测试 `.local/gpu-diagnostic-audit-20261104/test_return_flow_fixture.py`。这只是离线模拟的流程组合，没有轮询/独立守护、真实身份认证或远端守卫，没有可用来确认 EFI/DiagnosticReports 文件的完整验证，也不证明生产集成或自动回程；原 observer、watchdog、collector 和 R29 保持各自原状态。

#### 返回后 supervisor 本地集成候选

`.local/gpu-diagnostic-audit-20261104/post_return_supervisor_candidate.py` 是尚未接入旧 observer 的实验代码，不是纯状态模型：显式运行时会通过既有 Tailscale 地址和严格主机密钥检查查询 Linux/NixOS/boot，保存未过滤的身份输出；校验新 boot 后以该值和旧 boot 调用独立的 `collect-nixos-evidence-bound.py`。collector 原始 stdout/stderr 单独保留，不设置采集时长或大小限制；状态将 arrival 与 collector 返回码分开，0 也只报告 `collector-exit-zero-files-unverified`。它本身**不监控 macOS、不重启、不等待 NixOS 到达**，不能单独实现无人值守回程。

四项测试把所有 subprocess 调用替换为假函数，检查实际传给 collector 的旧/新 boot、host-key 参数、身份失败不启动 collector、非零退出与启动异常，以及保存假身份和输出原文。`.local/gpu-diagnostic-audit-20261104/test_post_return_supervisor_candidate.py` 不访问设备。候选仍无实机验证、独立监督接入、文件哈希/归档校验和完整失败持久性保证；采集可能无限期卡住，目录创建或回执写入失败也可能无法留下状态。不能部署或把 exit 0 当作成功采集。

#### 首 hang 回程 core 本地候选

新增未接入 worker 的 `.local/gpu-diagnostic-audit-20261104/return_watchdog_candidate.py`：首次识别 hang 即通过注入的有界持久化接口尝试保存原始快照；该 hang 后续完成时另存完整快照，不把后续 hang 误当首条完成。存储失败/超时或未完成超过宽限期后，重新核对 Darwin/预期 boot，再调用**必须自行在同次远端操作中守卫身份**的 reboot 回调。若先前不完整快照已保存、后续 dmesg 读取失败但身份仍匹配，宽限期届满仍尝试守卫回程；身份不可用或变化则不重启。持久化失败时可能丢失原始证据，该权衡不能描述为取证成功。

七项离线测试覆盖首条保存顺序、之后完整快照、保存超时/异常、身份变化、后续读取丢失和后续 hang；其中一项使用实际本地子进程保存到临时目录，所有身份、采集和重启均为假回调。`reboot-requested` 仅表示调用了回调，SSH 返回 255 或异常不证明请求已送达，更不证明 NixOS 到达。

**这不是完整无人值守实现**：回调有界/远端身份守卫仅为调用契约，不能由 core 自行保证；采集或进程启动可能阻塞，事件当前只在返回结果内存中，独立监督、持久化失败回执、重启后的等待/collector 对接均未完成。原 `return_worker.py` 和已保存证据未修改；新 core 没有 CLI、未部署，未经实机测试。

#### 回程 worker 本地候选（未部署）

新增 `.local/gpu-diagnostic-audit-20261104/return_worker_candidate.py`，将上述 core 与现有严格主机密钥的 macOS transport、独占名称的本地子进程保存候选相连；验新 Darwin boot 与指定 kext UUID 后，首 hang 读取原始 dmesg，尝试保存并按 core 判断回程。对于 reboot，transport 在同一次远端 shell 调用中检查 Darwin 和 boot；启动或读取凭据仍可能失败。worker 在回程尝试**之后**才落最终结果与保存回执，避免将回执落盘作为重启前的强制等待。结果丢失、存储超时后子进程迟到、SSH 不可达或机器失去响应时仍可能失败；回调或 SSH 的退出状态不证明 NixOS 已到达。

三项离线测试使用真实本地临时快照写入，但身份、kext 和所有 macOS transport 操作均由假对象替代：保存先于模拟重启、读取凭据的异常不泄露内容、重启前 boot 改变则拒绝调用。候选未接入独立 supervisor、NixOS 等待或 post-return collector；现有 `return_worker.py` 未改。进程启动/文件同步仍可能阻塞，进程崩溃或最终回执失败可能无记录；不运行、不部署，等待后续完整安全审查和设备许可。

#### 独立协调器本地候选（不得部署）

新增 `.local/gpu-diagnostic-audit-20261104/return_coordinator_candidate.py`：设计上作为单独进程启动候选 worker，在 worker 运行期间通过严格主机密钥的 Tailscale SSH 查询 NixOS，保留查询原始输出；只有核实新 Linux/NixOS boot 不等于提供的旧 boot，才把该确切 boot 作为 `--expected-boot` 传给同 boot collector。worker 退出、SSH 断线及重启请求都不等于 NixOS 到达；collector 返回 0 也只标记文件尚未核验，不声称完整采集。实际完整 collector 输出没有人为时长或大小限制。

四项隔离测试把 worker、SSH 与 collector **全部打桩**，验证旧 NixOS boot/worker exit 0 不触发采集、查询超时后可继续、确切 boot 参数传递、collector 非零失败及 worker 启动失败。未发起真实 SSH 或重启。候选尚不能当作可靠独立监督：worker 存活与退出只在到达/等待结束时采样，启动失败或协调器/机器崩溃不会自动修复；等待到期后未终止仍在运行的 worker，外部必须继续监督；I/O 或进程启动可能阻塞，状态/回执也可能写入失败。给定的旧 boot 必须预先真实核实；可能的陈旧身份、网络丢失、时序竞态及真实 collector/文件完整性仍需审查。**尚未集成进现有试验流程、未授权实机运行。**

#### 协调器故障与既有归档的离线核查

`.local/gpu-diagnostic-audit-20261104/test_coordinator_failure_review.py` 使用假 worker/SSH 重现两个限制：本地 arrival 输出落盘报错时，即使收到有效新 boot 也被统一当作查询失败并最终不启动 collector；到达超时时若 worker 仍在运行，协调器只记录 `worker_exit_at_arrival_or_timeout=null`，没有负责其后续生命周期。这是当前候选行为，不是已有实机故障；磁盘挂起或独立监督进程故障仍未解决。

新增只读 `.local/gpu-diagnostic-audit-20261104/archive_integrity_offline.py`，完整计算归档 SHA256、遍历并读取所有普通文件成员，不解包或改写原件，可核对先前收据哈希。对已保存 R28 retry1 数据重新检查：

| 原始归档 | 与既有收据 SHA256 | 成员 / 普通文件 | 结果 |
|---|---|---:|---|
| `run/post-nixos/efivars-full.tar` | `6b05f0141e7b0bc5176dcbb7830a79803b50bac19b6b669ad1e9d6d68097b233` 一致 | 374 / 373 | 可读取 |
| `run/post-nixos/DiagnosticReports-full.tar` | `0bad4387b6b4eefb00a049416c8072f71ea1ee4d8d7239d06edf33d98772f9c3` 一致 | 263 / 258 | 可读取 |

机器结果保存在 `.local/gpu-diagnostic-audit-20261104/r28-efivars-archive-recheck.json` 与 `r28-reports-archive-recheck.json`。这证明当前本地文件与先前收据哈希一致，及归档中普通文件可读；**不单独证明源端完整、采集时同 boot、GPU 修复或 Metal 通过**。归档器的另一轮测试使用伪造小归档，验证已知哈希不符及成员截断会失败。R28 原始归档与收据未修改。

#### 协调器 V2 本地候选：故障处理变化

为保留历史证据，旧协调器未改；另建 `.local/gpu-diagnostic-audit-20261104/return_coordinator_v2_candidate.py`。该候选对已收到的 NixOS 身份先解析、再尝试以子进程保存原始查询输出；保存失败时计数并明确标记，不再把有效 boot 静默当作 SSH 查询失败。若日志子进程仍存活或启动/监督异常，停止启动更多日志子进程并记录遗漏；**这意味着身份查询日志可能丢失，不可报告为完整证据**。确认新 boot 后仍把该 boot 原样传给同 boot collector，collector 完整原始采集不设人为时长/大小上限。

生命周期上，等待超时后若 worker 仍活跃，候选继续查询和轮询，不立即退出；collector 启动后也同时轮询 worker 和 collector，异常路径尝试等两者退出，不强行终止采集。五项离线故障测试中所有远程身份、worker、collector、日志子进程均为假对象，覆盖日志失败、超时后存活、日志写入子进程卡住、collector 启动失败和启动后异常。模拟显示上述状态被区分，但**不能证明进程在真实系统中安全或可靠**。

V2 若 worker、collector 或内核 I/O 永久卡住，也可能永久等待；协调器崩溃、外部杀死或宿主机故障仍可遗留子进程。`Popen`、磁盘访问、退出回执可能阻塞或失败，远端 OS/boot 守卫、证据哈希、kext 与完整 Metal 运行均未实测。必须外部独立监督、明确失败报警和继续设计异常处理；此候选未接入试验流程、**不得部署**。

#### 崩溃实测与无快照超时回程候选

`.local/gpu-diagnostic-audit-20261104/test_coordinator_crash_local.py` 在本地启动实际协调器进程，其 worker 用本机无害 `sleep` 进程替身，SSH、collector、日志写入均为假操作。测试向其**自行创建的精确协调器进程**发出 SIGKILL 后，通过 pidfd 观察替身 worker 仍存活，再仅使用 pidfd 清理该测试进程。这是本地进程实验，说明 V2 协调器崩溃不能自动确保其子进程退出；不是目标机故障或真实 SSH/重启实验。仍需外部进程级监督与报警，不能把 V2 当作完整无人值守方案。

另审查发现上一版回程 core 在总等待超时而 dmesg 始终不可读时，即使仍能验证预期 Darwin boot，也只返回 `identity-or-capture-unavailable-no-reboot`，可能继续停留 macOS。为保留旧实现和证据，复制另建 `.local/gpu-diagnostic-audit-20261104/return_watchdog_v2_candidate.py`：在该超时分支，**若当前和紧接着的复核身份均匹配**，提出带远端同次 OS/boot 守卫的回程请求，并标明 `timeout-no-current-snapshot`；如果先前保存过部分快照则注明，否则明确可能没有现场证据。这个回程选择体现优先避免长期卡死的权衡，并不声称成功取证或已回到 NixOS。身份丢失/变化仍拒绝请求，远端守卫仍由调用方实现。

四项测试使用假身份、dmesg、持久化与重启回调，覆盖无快照、先前部分、复核 boot 变化和身份不可用；默认总超时仍为 600 秒，且阻塞调用可延长实际等待。V2 core **尚未接入 worker、协调器或实机**；运行它仍不能保证远端守卫、最终回执或回程可靠。不能把该候选当成已部署修复。

#### V2 core 与独立 worker 的本地接线

原 worker 保持不变，另建 `.local/gpu-diagnostic-audit-20261104/return_worker_v2_candidate.py`，仅将它的 core 调用切换到上述 V2。三项离线测试替换全部 macOS 身份、kext 和 SSH transport：dmesg 一直不可用时在测试时钟超时后调用假守卫接口并记录未保存快照；复核 boot 改变时不调用重启；有完整首 hang 时仍先写本机临时快照再调用假重启。测试中的退出 0 或 SSH 255 仅代表 worker/回调结果，不证明重启送达或返回 NixOS。

此 worker 候选尚未被协调器选择或连接返回后采集，不能自动认为其受到监督；无快照分支有明确证据丢失风险，600 秒默认超时及阻塞调用也不能保证尽快回程。所有设备操作均未执行。候选未经完整集成/实机验证，**不得部署**；外部独立监督、协调器崩溃后的生命周期和告警仍未解决。

#### V3 协调器本地接线与组合检查

保留先前协调器，另建 `.local/gpu-diagnostic-audit-20261104/return_coordinator_v3_candidate.py`：在 V2 协调器基础上明确选择 `return_worker_v2_candidate.py`，可传递 worker 总超时（默认仍 600 秒），并沿用返回后确切 boot 传入 collector 的路径。传入的总超时只影响 worker 策略，不对完整 EFI/DiagnosticReports 采集施加时长或大小限制；任何阻塞仍可能延长回程。

三项离线组合测试中，一项在同一测试进程实际调用 V2 worker 代码并使用临时目录保存首 hang 原始字节，但其 macOS 身份、dmesg、重启回调及 NixOS 查询、collector 都是替身；测试确认快照先于假重启、SSH 255 未被当作 NixOS 返回证明、新 boot 参数传给假 collector，以及 collector 非零与到达分开。其他测试覆盖非法超时和沿用 V2 的写入卡住/worker 仍活跃逻辑。**这不是实际多进程或真实设备端到端测试。**

V3 与 V2 一样无法在协调器被杀或永久阻塞时保证独立外部监督；现有真实本地 SIGKILL 实验已证明 V2 情形下 worker 可继续存活，V3 未解决该问题。没有真实 OS/boot 守卫、后续归档哈希或完整 Metal 结果验证，worker 超时无快照回程还可能丢失证据。V3 未接入用户试验、未部署，仍不具备无人值守安全保证。

#### worker 快照收据离线检查

新增 `.local/gpu-diagnostic-audit-20261104/verify_worker_snapshots_offline.py`，可只读检查候选 V2 worker 的快照收据：按记录的长度和 SHA256 读取完整本地快照，拒绝非约定名称、重复名称和符号链接，并明确区分超时、缺失、篡改和无快照。该检查只是**本地文件与同机收据的一致性**，不能证明源端真实性、首次 hang 完整性或已返回 NixOS；尚未接入任何 worker 或协调器。四项伪造临时文件测试通过。

另外重新计算既有 R28 retry1 worker 首 hang 原始 dmesg，SHA256 `b49a2cac6a21cec1d22b6e9dc4a38fafbface915ec5755b07561d475efeeaa2d` 与此前独立保存的该次回执一致；这是原件的只读核查，不是新的实机采集或修复证据。

## 用户要求：逐项处理实际报错，并尽量取得完整证据

用户明确表示即使报错未证明直接导致 GPU hang，也希望处理真实错误而不是只围绕一个猜测。按此要求，以已完整保存的 R28 retry1 worker dmesg 为输入，建立首个 `HP-BBTRACE: HANG` **之前**的 IGFB/IGPU ERROR 原始行索引 `.local/gpu-diagnostic-audit-20261104/r28-driver-error-index.json`，脚本与测试 `audit_driver_errors.py` / `test_driver_errors.py`。这不是全系统错误清单，也不改变或筛掉原始 dmesg。时间顺序上：MEI 错误 50.204 s、拓扑错误 50.469 s、显示链路带宽报错 59.209 s 起 5 次，目标 hang 标记 177.719 s；先后不证明因果。还有 power-well 驱动标称自覆盖、Unsupported DDI 20 次、VBL 提示等，应分别排查，而不是统一抹掉 ERROR 日志。

### MEI 设备名称不匹配：可复现的单变量修复候选

- **实际证据**：R28 retry1 macOS 早期完整 IORegistry 中，`HECI@16` 是活动的 IOPCIDevice、PCI ID `8086:a0e0`，compatible 中含 `HECI`，但日志提示 `ME PCI ACPI device not found` 并关闭 PAVP。Linux 既有 PCI 清单也记录 `00:16.0` HECI；这证明设备存在和当次名为 HECI，**不证明 macOS MEI 驱动能安全成功连接该设备**。
- **固定二进制静态证据**：framebuffer SHA256 `285ee7a9c3d6c9a9647013f44fb40f312b1cb42879974ef0542544cf049442b5` 中 `createMEIDriver` 的 `0x5ff77` 加载 `IMEI`，调用 `findMEDevice`；`findMEDevice` 调用 `IOService::nameMatching` 和 `waitForMatchingService`。这为名称不匹配提供了可证伪解释，实际 name-matching 结果仍需运行时验证。完整反汇编 `.local/gpu-diagnostic-audit-20261104/framebuffer-create-mei.disasm.txt`，IORegistry 原件 `trial-r28-retry1/run/ioreg.txt` SHA256 `f1e505a5d318bb95a984aed60fc7cb2bec8327841a85e3603aba96453be1de6a`。
- **仅本地 byte-level 候选**：`.local/gpu-diagnostic-audit-20261104/build_mei_name_candidate.py` 固定二进制哈希、核对调用与唯一字符串后，将一份本地副本的 `IMEI` 字面量改为 `HECI`，仅 3 个字节不同；候选 SHA256 `2de4746e10362b1b9affa490a2222f8db5545f82d6dedf9151eb7317f515354c`。此副本**未签名、未打包、未安装、不能启动、不得部署**，替换破坏原签名；它是供后续设计受控补丁的实验，不是声称修好 MEI。还须检查其他交叉引用、MEI 固件/电源兼容、签名与安装方案，以及明确单变量实机回归。MEI 通路可能执行设备操作，不能把它当作完全只读，也不能认定会修复 hang。
- **拓扑时序**：固定 R28 源码在原 `getGPUInfo()` 返回后才写 L3 0→6；原驱动在返回之前调用 `initHardwareCaps`。静态反汇编的该函数没有直接读取 `+0x1164`，不能据此声称早期 L3=0 已造成某个硬件故障或需要直接改 branch；仍需分析具体消费者。显示带宽报错另作为真实问题追查，不能单凭日志就伪造链路速率/时序。

### 完整证据的现实边界与下一次流程

目前已有完整保存的首 hang worker dmesg、部分先于故障的 IORegistry、返回后的完整 EFI 变量及 DiagnosticReports 归档；但 R28 retry1 首次 reset 的并行 dmesg/ioreg/reports 请求均 exit 255 且为空，原始 GPU batch、准确地址空间及页表根未被可靠保存，这些缺失无法从其他报告反推补齐。实时流和历史回填均有退出 255，不能称本轮全量日志完整。

设备恢复后，开始工作负载前先保存准确 boot/kext 身份、完整 IORegistry、完整日志流与可获得的历史回填；首次 hang 尽可能先保存未过滤 dmesg/状态，然后立即尝试受 OS/boot 守卫的回程，返回后保存完整 EFI 变量、系统及各用户 DiagnosticReports，并按哈希核对。若要得到可证明归属的 batch、context 和映射，还必须先安全审查能在对应提交/地址空间取证的方案，不能再使用 R25/R26 写物理页或未经验证的 R29。SSH 已失联、环形缓冲已覆盖或 GPU 本身不再响应时，完整性无法保证；必须把缺失明确标注，而不是为追求更多数据放任系统卡死。
