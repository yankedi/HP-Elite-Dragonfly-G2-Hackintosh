# R32：Tiger Lake GPGPU 抢占候选（仅本地，未验证）

R31 首 hang 的 BB 地址 valid=0、Apple summary 为 RCS busy in ring；不能把该 BB 的邻近值当作正在执行的 batch。采集器记录 RCS `0x20e0=0x4000`，但它位于恢复/诊断序列中，不可认作发生 hang 的精确瞬时值。

上游 Linux 固定提交 [9b11bbf0c4008fa0b715ed68db0d5669175413c5](https://github.com/torvalds/linux/commit/9b11bbf0c4008fa0b715ed68db0d5669175413c5) 为 Tiger Lake 增加 `WaDisableGPGPUMidThreadPreemption`：启用 per-context 控制并选择 thread-group 默认粒度。对应固定版本 `i915_reg.h` 定义 `0x20e0[14]` 为 per-context 控制、`0x2580[2:1]` 中 `01` 为 thread-group、`00` 为 mid-thread；这是 Linux 针对 TGL 的 workaround，不证明本次 macOS hang 由抢占造成。上游另有[对 per-context 策略及用户态覆盖的解释](https://lists.freedesktop.org/archives/intel-gfx/2022-September/305478.html)。两份固定源码原件在 `.local/driver-repair-20261103/repair32-preemption-investigation/`。

固定 Apple TGL 二进制 SHA `1b2f5aa3131f9b909fe984877e41d5ebcdb2837572b45e1e901a72a6271515a2` 的 `startGraphicsEngine`：`0x25160` 计算带掩码的值，`0x25189` 设置 `0x20e0[14]`，`0x25199` 将 EDX 并入 ECX，`0x2519b` 写 `0x2580`。R31 的 FF_DOP 补丁保留 EDX=`0x10001`，且 Apple 当前根据 feature 分支可能已经写入 thread-group；尚无该字段的实时读取证据。既有 `-ngreenobjpoff` 是另一个 3D bit 的方案，与本候选不同，而且它搜索的原始字节会先被 FF_DOP 补丁替换，不能假设该选项在此基底生效。

R32 仅在本地 R31 源的现有 FF_DOP 替换字节中将后续 EDX `0x10001` 改为 `0x10003`，请求 `0x2580[2:1]=01`，FF_DOP 与其他 masked 位保持不变。两条 feature 分支、全部 65536 个低位旧值的宿主模型验证候选只可能改变 bit1；固定 donor 唯一原始指令窗口也已检查。证据测试 `.local/driver-repair-20261103/repair32-preemption-investigation/test_candidate.py`。内核交叉构建成功，NG SHA `8d26a099e410a3b764290ec999666928e94a67bcbb29ba4b5f29f8a554fca3d2`，UUID `4C4C44F1-5555-3144-A131-0012485F37DF`。

**未部署、不是已证实修复。** 此写只请求 engine 初始化时的设置，context 初始化、切换或用户态命令可能覆盖；如果原 feature 分支已经选 thread-group，它可能完全无效果。还需审查写入时机及安全 forcewake 下的真实 `0x2580` 读回，核实目标 context，而不能仅凭补丁 ready 或未复现一次宣布有效。一个可证伪对照：同一 R31 工作负载及其余配置，只改变此请求；先验证安装和尽可能可靠的读回，若字段本来已为 01 或运行中未保持，结果不能作为该假设的有效检验；若字段明确改变仍出现 hang，则该单独干预未解决问题。成功也须完整 Metal 和重复稳定性验证。实机安全门控完成前不将本地 kext交付；以后首次 hang 优先持久化原始 dmesg 并尽快请求身份守卫回程，SSH 不可用时回程无法保证。

## 静态读回路径复核

固定 donor 的 `startGraphicsEngine` 在 `0x25125` 请求 forcewake，`0x2519b` 写 `0x2580`，`0x25cea` 调用 `populateResetRegisterList`，然后 `0x25cf9` 请求释放 forcewake。被调函数在 `0x29a66` 已经读取 `0x2580` 并将结果加入带 `GFXREG_CS_CHICKEN1` 名称的 reset-register 列表；因此潜在方案是记录这个**已有读取的标量**，不额外读 MMIO。`.local/driver-repair-20261103/repair32-preemption-investigation/audit_readback.py` 对固定二进制哈希、原始读取字节和反汇编中的六个位置做静态断言；唯一直接调用点是上述 engine-start 调用。R31 已有 dmesg 和采集的日志流中没有该标签，不能把静态代码当实测读回。

这条静态路径并不证明实际 forcewake ACK、列表加入成功、列表条目的生命周期或锁保护，也不证明采样属于 hang 时的活动 context。不要直接解引用猜测的列表或只因符号存在就部署 hook；下一步应验证列表布局和分配失败/并发边界，并审查如何在不改变原函数 ABI、寄存器、异常和回程门控的情况下取得该已有标量。只有初始化读回还不够证明 context 切换后保持。

### 已有读取后的栈局部值原型（未接入 kext）

固定 donor 在 `0x29a66` 将 MMIO 读入 EAX，`0x29a6c` 存到栈 `rbp-0x3c`；`strncpy` 返回后 `0x29a85` 的前 14 字节是两条不使用 RIP 相对寻址的指令。局部宿主原型从该栈位置复制标量到专用存储，不增加 MMIO、也不遍历可能失效的列表；可执行机器码测试覆盖标量、RAX/RDX 和 carry 保留。证据 `.local/driver-repair-20261103/repair32-preemption-investigation/test_readback_prefix.py`。字节检查发现这 14 字节在整个 donor 出现 **19 次**，不能使用全局唯一模式匹配；须基于经验证的函数符号和偏移以及更大范围字节守卫定位。

此仅是用户态原型，尚未集成、签名或实机使用：原型的值和有效位是两个独立写入，存在并发/发布时序问题；线程栈、Lilu trampoline 指令长度和控制流、内核执行安全均未在内核验证。初始化值不代表所有 context 或运行中值，也没有 wake ACK 证据。不要把宿主成功作为实机门控通过。

### 原子发布与跳板静态审查

另存的用户态原型 `test_readback_atomic.py` 将有效位和 32 位值编码在单个 8 字节对齐的 64 位存储中，使用 `pushfq/popfq` 保持标志；4 个宿主线程合计 40,000 次写入的检查未观察到撕裂值。它只能提供“某次调用的最近发布值”，不能关联具体引擎启动调用或保证记录先后顺序，亦不能替代 C++ 侧的原子加载和对齐保证；宿主测试不证明内核内存模型或中断安全。

已读本地 Lilu 1.7.2 实现 `repair4-rect-topology/lilu-1.7.2-kern_patcher.cpp` SHA `6d8c6af91d22b31afafaf2d62bf6e1ca18a4b965547604f28978bba5ca6ba8dd`：`routeBlock(..., true)` 调 `createTrampoline(from, LongJump, ...)`，使用反汇编长度后**原样复制**原指令，再跳回；实现假设被复制部分 PIC，不会自动修复 RIP 相对地址。候选位置的前两条指令总长恰为 14 字节、均为基址寄存器寻址；下一条是条件分支，因此必须在目标 Lilu 版本核实 `LongJump` 和实际反汇编长度确为 14，不能复制第三条相对跳转。也需验证符号解析和完整字节守卫、调用并发及失败时不能让压力测试继续；尚未实际安装跳板或执行内核测试。

**长度离线复核：** 从 R31 本地 IMG 提取的实际 Lilu `Info.plist` 报 1.7.2，二进制 SHA `e2a1a6352dfd7143e5edcdd4a60627ad8ea715ce84a048af3370f7aecd014634`，与早期对照字节一致；同 kext 的头文件定义 `LongJump = 6 + sizeof(uintptr_t)`，x86_64 为 14。取上游固定 tag commit `e4748cc081bf060302c7d3c44a643ce1d11b7e1d` 的 HDE 源码作宿主构建，其 `hde64.h` 与 IMG 中头文件 SHA 均为 `109319ff7ab6b135708fb4ff7d20a7cef4eb30cd4c2048cf8090caaadb53bb1a`；运行原 HDE 解码候选字节结果 `7 + 7 = 14`，下一相对分支为2字节，不需复制。原件、测试程序及收据位于 `.local/driver-repair-20261103/repair32-preemption-investigation/hde/` 和 `hde_test.c`。这验证对应源码与候选字节的离线行为；不能仅凭版本和头文件完全证明发布的 Lilu 二进制必然由该源码构建，也不证明运行时跳板安装安全。内核对齐发布、context 覆盖、异常及回程门控仍待验证。

### 同诊断的本地候选与对照

另建 `.local/driver-repair-20261103/repair32-readback/`：在 R32 上添加函数符号加固定偏移、原读取字节及14字节站点核验的跳板，复制原本已经读出的栈标量，单个对齐64位存储发布；engine-start wrapper 以原子加载报告 `startup-last-writer`，不声明当前 context。实际 kext 的机器码发射器由 `test_emitter.py` 与先前执行的宿主并发原型逐字节比较通过，新增 undefined imports 为零。本地构建 NG SHA `8b3df79767e832c1e042b0915fe2e97fb94d37250d9bc656a68e67f4af990da3`。

另建 `.local/driver-repair-20261103/repair32-readback-control/`，保持同样的诊断但将 preemption 写恢复为 R31 基线；本地 NG SHA `19af6161b4dfe916a5f166a3199cbe69244dfb0fd09a8988e12e97a81a687b22`。`test_pair.py` 检查源差异仅为目标 EDX 值及明确标识的日志/注释，其余 NootedGreen 文件逐字节相同；不代表两份二进制仅有一个字节不同，也不证明实机 context 覆盖。

**两者都未部署。** 静态字节守卫、宿主执行和交叉构建不能证明内核跳板安装、并发、异常、实际 forcewake 或每个 context 的持续设置安全。控制器目前沿用 R31 检查，尚未为新 `HP-R32-WA` 和 `HP-R32-READBACK` 路由及有效值增加专用压力测试门控；不得以现成 R31 observer 直接启动本候选。下一步先构建及测试适用于两份配置的 observer 门控（失败则不运行 Metal，保留独立身份守卫回程），然后审查证据收集和安全策略后才考虑实机对照。

**后续本地 observer 门控（未接入部署控制器）：** `.local/driver-repair-20261103/repair32-trial-automation/` 新建候选/对照专用 observer 与纯判定函数，必须提供模式并要求原组合安装门控；首次 smoke 前检查对应 WA ready、读回 route ready、无失败/矛盾标记、最后一条 startup 样本有效且不是 `ffffffff`，候选还要求 `0x2580[2:1]=01`。失败不运行 Metal；第二个 Metal 入口也复核。该值仍是 last-writer 启动样本，不能证明 hang 时 context。5 项宿主测试覆盖缺失、失败、矛盾、无效/格式错误、候选字段及两个入口的静态控制流；未验证真实 SSH 或 macOS 执行，尚未接入交付脚本。

**回程策略审查发现真实缺口：** 当前 R31 实测用的 `return_watchdog.py` 对不完整 hang 最多等 20 秒，期间若身份或采集丢失，现有模拟测试显示既不保存已经取得的不完整原始快照，也不请求重启；`safe_return.capture_and_request` 的持久化异常会中止重启。另一个模拟测试显示在同次 dmesg 同时存在两个完整 hang 时文件名可能偏向后一个目标 hang，虽然整个原始快照仍被保存。45 项 `test_return*.py` 混合生产和未部署的候选/模型测试，全部通过不代表这些缺口已经修复。必须先审查立即持久化首个不完整快照、失败状态的身份守卫回程以及现有行为兼容性；SSH 不可用仍无法保证回程。切勿为了赶进度声称 observer 测试或候选 watchdog 模型已通过实机。

**随后新建的本地回程候选（尚未接入现场控制器）：** 用户明确指出只需先把证据保存到开发机，本机回 NixOS 后可借助工具读取 macOS 分区。`.local/driver-repair-20261103/repair32-trial-automation/prompt_return_core.py` 和 `prompt_return_worker.py` 采用首个已识别 hang（即使缺少完整结束标志）先把**未过滤原始快照写到开发机**，立即重新核验 boot 并尝试在远端同一调用内守卫重启，不等完整 ioreg/DiagnosticReports；本地写入失败或超时不冒称已保存，也不阻止仍通过身份守卫的回程尝试。之后在 NixOS 使用现有只读 APFS 采集器收集完整可获得的 DiagnosticReports/EFI；不能保证故障瞬间所有记录已写入 macOS 数据卷或仍可恢复。若 SSH 不可用，无法保证回程。

本地核心 5 项 mock 测试覆盖不完整/完整 hang、错误/超时、身份变化、超时无快照；2 项 worker 测试使用模拟 SSH，其中一项使用真实本地子进程写入与 fsync，检查原始字节在重启回调前落盘。二者未调用真实目标；写入子进程的 5 秒期限不保证进程启动、调度或 D 状态可终止。该 worker 还未完成与 R32 控制器及 observer 的端到端集成，不能把测试等同于实测回程。

**本地集成及单次对照准备：** 候选 IMG SHA `a9c19bf2fe29ceeb45b3a0eac12aac8d3b18077a4aa72fc1166bd19de1310a30`，对照 IMG SHA `2138e88117feff26be5e165cc34bcbf0233b1117d4a9c208b958481c41194219`，两者从 R31 IMG 构建，98 个 EFI 文件均只有各自 NG 二进制变化，签名、OC1.0.8、FAT 静态检查通过。`repair32-trial-automation/trial-control.py` 已连接专用 observer、独立 v2 回程 worker、同 boot 守卫的只读 EFI/APFS 采集器，强制 return 与等待最终 collector；mock 集成测试覆盖门控、旧/非法 boot、采集失败及两个 Metal 入口，但未证明内核 hook 安全或现场返回。

审查时发现首次启动若预期 NG UUID 未加载，原候选 worker 会等 arrival timeout 后直接退出而不请求回程；v2 对观测到的新 Darwin boot 给予 90 秒加载窗口，仍未核验 NG 时保存可获得的未过滤 dmesg 并以该新 boot 独立守卫尝试回程，结果明确标记 NG 未验证；boot 变化则不重启。mock 测试覆盖该失败路径及已验证 boot 的首个不完整 hang。若 SSH 不可达、新 boot 无法确认、本地进程/存储卡死或固件无带外恢复，仍不能保证回程。

当前设备只读验证 NixOS boot `f068c113-f425-45d1-b03c-300f4dc438d6`、USB `4868-2795` 已连接，ventoy 全量只读备份于 `repair32-trial-automation/ventoy-before-control.tar`，env 为 consumed 且指向 R31；USB 空闲约75 GB。试前 EFI/DiagnosticReports 为 R31 回程后完整归档；尚未交付 R32 或请求重启。对照先用于确定基线启动读回，不是修复；后续实际结果必须独立记录。
