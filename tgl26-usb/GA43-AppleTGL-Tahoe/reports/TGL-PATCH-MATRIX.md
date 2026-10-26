# Tiger Lake / Raptor Lake 补丁分类矩阵（任务 B）

本表以固定 commit `54d514f079bad088eb2002eb931686216f141fc5` 的
`julio-xps13/src/NootedGreen` 为源码基准，并用 upstream
`95f81898be65cb9f7b3d370ca78054be4cc8a62d` 做差异核对。行号是 fork 源码行号。
`CATALOG.md` 是作者自己的清单，本表在关键处回到源码和 16.0.32 二进制复核，
不把 CATALOG 的“always”直接当成真 TGL 上会执行。

## 分类与 25G83 证据等级

| 标记 | 含义 |
|---|---|
| **A** | 只适用于 Raptor Lake / Alder Lake（或 display 13 / RPL 调度器/拓扑），原生 TGL 不需要 |
| **B** | 真正的 Tahoe/25G83 兼容修复，原生 TGL 也可能需要，应移植并单测 |
| **C** | 通用稳定性/生命周期修复，有真实证据但需在 TGL 上重新验证 |
| **D** | 未知、实验性、危险或证据不足；默认关闭，不能因为“别人能用”就启用 |
| `[1]` | 源码可确认与 OS 构建号无关 |
| `[2]` | 有充分源码证据可兼容 25G83（仍不等于本机运行证据） |
| `[3]` | 依赖具体 Apple 二进制版本/偏移，必须拿 25G83 文件比对 |
| `[4]` | 当前无法确认 |

**重要结论先说：**

1. `isRealTGL` 只按 CPUID model `0x8C/0x8D` 判定，9A49 会走“真 TGL”分支。
   `kern_green.cpp:251-266`。`VERIFIED_SOURCE`。
2. **`XE-FMT` 和 `XE-PLANES2` 被放在 `if (!NGreen::callback->isRealTGL)`
   块内**（`kern_gen11.cpp:2228` 起）。它们修的是 Tahoe 的 IOSurface 布局，
   不是 RPL 硬件特性；真 TGL 反而不会执行。这是 B 类补丁被错误地当成 A 类。
3. **`-ngreenxefix` 不是一个“TGL 兼容开关”**。它会把 display 13 寄存器
   过滤、BLR、FBDPMS、命令池、NOORPHAN 和整套 RPL CSB/ELSQ hook 一起打开，
   其中多项没有 `isRealTGL` 保护。真 TGL 上不能直接使用这个 master switch。
4. `XE-VALD`、`V40`、`V221`、`XE-RESFREE`、`XE-GTFREQ`、`XE-IDLEBOUND`、
   `forceWake` 替换和 `HANGCHECK` 是**无条件**安装/执行的；它们没有
   `isRealTGL` 保护。前几项可能是 Tahoe 兼容修复，后几项在真 TGL 上风险较高。
5. 参考项目在 RPL 25G241 上的成功不能证明这些补丁在 9A49/25G83 上安全。
   每一行都给出“是否需要”和“25G83 是否兼容”两个独立判断。

## 逐补丁矩阵

| 补丁 | 原始功能 | 原生 TGL 是否需要 | 25G83 是否兼容 | 证据 | 建议 |
|---|---|---|---|---|---|
| **kern_start Tahoe** `[B]` | 把 Lilu 插件最大内核版本从 `Sequoia` 改为 `Tahoe`，否则 macOS 26 不加载 | **需要** | `[2]` 只依赖 `KernelVersion` 枚举，与 build 号无关 | `kern_start.cpp:24`；upstream 同位置为 `Sequoia`；`Lilu.kext/.../kern_util.hpp` 有 `Tahoe=25` | 保留 |
| **isRealTGL CPUID** `[B]` | family 6 + model `0x8C`（TGL-U）/`0x8D`（TGL-H）判定真 TGL | **需要**；i5-1135G7 应为 `0x8C` | `[1]` CPUID 与 OS build 无关 | `kern_green.cpp:251-266` | 保留；日志确认 `isRealTGL=1` |
| **`-ngreentglwithgfx`** `[B]` | 同时加载 TGL framebuffer 和 HW accelerator personality | **需要**；FB-only 会缺 DBUF 编程 | `[3]` 依赖目标 kext 的 bundle ID/personality | NootedGreen README；`kern_gen11.cpp:81-95`；`kern_green.cpp` kext 选择 | 使用；但必须用目标 25G83 kext 重新核对 personality |
| **`-disablegfxfirmware`** `[A]` | 禁止 GuC/HuC 固件，强制 RPL host scheduler | **不需要**；真 TGL 可认证/加载 GuC | `[3]` 25G83 固件/GuC 二进制未验证 | `kern_gen11.cpp` loadGuCBinary 分支；CATALOG V52 | **禁止**；会破坏原生电源/频率模型 |
| **`ngreenSched=4/5`** `[A]` | 选 IGScheduler4/5；源码真 TGL 默认 3（GuC） | **不需要** | `[4]` 目标 scheduler 行为未验证 | `kern_gen11.cpp:5247` 附近 | **禁止**；让真 TGL 用默认 scheduler 3 |
| **`ngreen-dmc=adlp`** `[A]` | 载入 ADL-P DMC v2.16 payload | **不需要**；TGL-U 不是 ADL-P | `[3]` DMC 固件与目标平台必须匹配 | `FirmwareADLP.cpp`；CATALOG 1.1 | **禁止**；用 TGL 原生 DMC 路径或不覆盖 |
| **`-ngreenxefix` master** `[A/D]` | 打开 display 13 修复、PSMI、forcewake refcount、V99/V193 关闭、BLITSCRATCH、POOL、NOORPHAN、全部 scheduler hook | **不能整体使用**；应拆成独立 B/C 项 | `[4]` 组合行为未在 TGL/25G83 验证 | `kern_gen11.cpp:3616-3618`；CATALOG 1.0 | **禁止整体启用**；建立 TGL 专用 profile |
| **xeFixFilterWrite display 13** `[A]` | `CHICKEN_MISC_2` bit30（关 DPT）、`DBUF_CTL_S1` bit31、`GAMMA_MODE_A=0` | **不需要**；这些针对 display 13（ADL-P/RPL-P），TGL 是 display 12 | `[3]` 寄存器在 TGL 上语义不同，不能假设兼容 | `kern_gen11.cpp:3777-3838`；CATALOG 1.1 明确写 display 13 | **默认关闭**；如果 xefix 被打开，必须在 TGL 上先做寄存器差异审计 |
| **XE-BLR** `[A/D]` | 保持 PWM 周期、重缩放 duty，修 RPL 亮度只到 50% | **未知/大概率不需要**；TGL 原生背光路径不同 | `[4]` 25G83 PWM 寄存器/面板未验证 | `kern_gen11.cpp:3782-3810`；CATALOG 1.1 | **默认关闭**；只有实测亮度异常才单独移植 |
| **XE-FBDPMS** `[A/D]` | 伪造 panel power state，只开关背光，不拆 pipe/link | **不需要**；真 TGL 应由 Apple 原生 DPMS 处理 | `[4]` 目标 FB 对象 offset `+0x1dc/+0x4284` 未验证 | `kern_gen11.cpp:6813-6848` | **默认关闭**；伪 DPMS 会阻止真正睡眠/唤醒 |
| **XE-BOOTHOLD** `[D]` | 首帧前保持 plane/backlight 关闭，等 WindowServer ring 回绕 | **未知**；属于显示时序/外观优化 | `[4]` 依赖 plane/backlight 寄存器 | `kern_gen11.cpp:3652-3760` | **默认关闭**；若要解决启动花屏，单独做 TGL 版本 |
| **V99R/V99G** `[A]` | 把非 aperture SURF 重定向到固定 GGTT 槽并复制 PTE | **不需要**；这是 RPL/ADL 的 scanout 变通 | `[3]` 固定 4000 页槽位与 TGL GGTT 布局不匹配 | `kern_gen11.cpp:4190-4225`；CATALOG 1.1 | **禁止**；默认关闭 |
| **V193** `[A]` | 阻止 routeSel=3 的 3D blit | **不需要**；RPL EU shader hang 的对策 | `[3]` 依赖 submitBlit 布局 | `kern_gen11.cpp:7937-7955` | **禁止**；会让 TGL 丢失正常 blit |
| **V52 拓扑硬编码** `[A]` | L3Bank=8、MaxEU/SS=8、NumSubSlices=12，BCS readiness bypass | **不需要**；真 TGL 从 fuse 读拓扑 | `[3]` 硬编码值会破坏 9A49 的 96EU/6 DSS 拓扑 | `kern_gen11.cpp:2123-2150`；CATALOG V52 | **禁止**；真 TGL 保留 Apple 探测 |
| **V46 deviceStart bypass** `[A]` | NOP BCS 失败门，强制 IGAccelDevice::deviceStart 成功 | **不需要**；TGL BCS 正常 | `[3]` 依赖 16.0.32 deviceStart 字节 | `kern_gen11.cpp` V46 pattern；CATALOG 2.A | **禁止** |
| **V54/V65/V507** `[A]` | 预开 GFX master IRQ、tier-1 interrupt、RING_MODE GFX_RUN_LIST_ENABLE | **不需要**；RPL IRQ/execlist 不工作 | `[3]` 依赖 RPL 寄存器行为 | `kern_gen11.cpp:5136-5255`；CATALOG V54/V65/V507 | **禁止** |
| **V57/V71** `[A]` | 清 ERROR_GEN6、mask RING_EMR，RPL GPU 错误风暴 | **不需要** | `[3]` 会掩盖 TGL 真实错误 | `kern_gen11.cpp:5799-5866`；CATALOG V57/V71 | **禁止** |
| **V111 deviceStart force success** `[A]` | 强制 IGAccelDevice::deviceStart 返回 true | **不需要** | `[3]` 依赖 IGAccelDevice 符号 | `kern_gen11.cpp:5877-5892` | **禁止**；失败应保留真实错误 |
| **V132/V148/V165 Blit3D** `[A]` | RPL 下 Blit3D context 缺失时的 fallback/自定义初始化 | **不需要**；真 TGL 用 Apple 原始初始化 | `[3]` 依赖 context 偏移 `+0xb8/+0xd8` | `kern_gen11.cpp:6287-6628`; `6860-7060` | **禁止**；真 TGL 走 original |
| **V212 scheduler idle** `[A]` | 当 INSTDONE 忽略 bit0 为 `0xFFFFFFFE` 时报告 idle | **不需要**；RPL bit0 stuck | `[3]` 只匹配 RPL 的 INSTDONE 模式 | `kern_gen11.cpp:10975-11001` | **禁止** |
| **V509 LRCA repair** `[A]` | 修 RPL context image 的 LRCA page1 | **不需要**；TGL restore 正常 | `[3]` 依赖 context 偏移/GGTT slot | `kern_gen11.cpp` V509；CATALOG 2.C | **禁止** |
| **RCS PSMI Wa_1607297627** `[D]` | 对 `RING_PSMI_CTL` 写 `0x10801080` | **未知**；Linux 对 TGL/ADL-P 有此 WA，Apple 原生 TGL 可能已做 | `[3]` 目标 RCS 寄存器/驱动路径未验证 | `kern_gen11.cpp` applyPreStart；CATALOG 1.2 | **默认关闭**；若真 TGL stamp timeout，再单独验证 |
| **XE-FMT** `[B]` | `performTransaction` 读 `IOSurface+0xa4` 得到 0，改为 `'BGRA'` | **很可能需要**；这是 Tahoe IOSurface 布局，不是 RPL 硬件 | `[3]` 25G83 项目源码确认 `+0xa4` 仍为 stale zero，但目标字节/偏移需比对 | `kern_gen11.cpp:2249-2255`（在 `!isRealTGL` 块内）；`intel_framebuffer.cpp:606-613`（25G83） | **必须移植出 `!isRealTGL` 块**，作为 TGL B 项单独测试 |
| **XE-PLANES2** `[B]` | `calculateIOSurfaceDeviceCacheVRAMBytes` 从 `+0xb0` 改读 `+0x98` | **很可能需要**；Tahoe plane count 布局变化 | `[3]` `+0x98` 是 25G241 证据，25G83 未证明；25G83 项目优先用导出 getter | `kern_gen11.cpp:2320-2335`（在 `!isRealTGL` 块内）；CATALOG 1.1 | **移植出 `!isRealTGL` 块**；25G83 先验证 `+0x98` 或改用 getter |
| **XE-VALD** `[B]` | 清 `ValidateTransaction` 的 `0x500` option 位；把 `IOSurface+0xa4` 读取 NOP 掉，保留 `'BGRA'` | **很可能需要**；Tahoe IOAF2 option 语义和 stale offset | `[2]` 25G83 项目源码也指出 `+0xa4` stale 和 transaction option 差异；`[3]` 具体字节 | `kern_gen11.cpp:1638-1668`；**当前无条件应用**；25G83 `intel_framebuffer.cpp` | **保留但加目标校验**；这是少数已经对真 TGL 生效的 B 类补丁 |
| **XE-NOCCS3** `[D]` | 让 `submitCCSResolve` 直接返回，绕过 Tahoe 命令池 | **未知/不需要**；真 TGL 应保留压缩和 resolve | `[4]` 依赖 IOAF2 pool 行为和 TGL AUX 所有权 | `kern_gen11.cpp:2245-2269`（`!isRealTGL` 块内） | **默认关闭**；不要用 RPL 的 resolve 绕过掩盖 TGL 问题 |
| **XE-NODEPTH** `[D]` | 让 `submitDepthResolve` 直接返回 | **未知/不需要** | `[4]` 同上 | `kern_gen11.cpp:2271-2283`（`!isRealTGL` 块内） | **默认关闭** |
| **XE-NOAUX** `[A]` | 强制 `fillSurfaceStateAuxInfo` 的 AUX=NONE | **不需要**；TGL 有 AUX-TT/压缩 | `[4]` 会关闭 TGL 正常压缩 | `kern_gen11.cpp:2285-2293`（`!isRealTGL` 块内） | **禁止** |
| **XE-NOTCF/NOTCF2/BLIT16** `[A]` | 去掉 flip/stamp 的 Tile Cache Flush；强制 Blit3D SIMD16 | **不需要**；RPL EU/flush hang 的对策 | `[3]` 依赖 blit/pipe 命令字节 | `kern_gen11.cpp:2293-2320`; CATALOG 1.4 | **禁止** |
| **XE-BLITALIGN** `[D]` | 把 64B 对齐检查放宽到 16B，并把大 copy 改走 2D | **未知**；可能是 Tahoe/16.0.32 通用问题，也可能依赖 RPL BCS | `[4]` 25G83 未验证 | `kern_gen11.cpp:2337-2360`（`!isRealTGL` 块内） | **默认关闭**；先测 TGL 的 CoreVideo/IOSurface 对齐 |
| **XE-POOL / POOLALIGN** `[B/C]` | 放大命令池、把 blit 命令对齐到 64B | **可能**；Tahoe pool 的 `getBufferPtrNoInc` 行为和 16.0.32 blit 对齐不是 RPL 专属 | `[4]` 依赖 pool 偏移 `+0x1842/+0x1850/+0x1858`，25G83 未验证 | `kern_green.cpp:357-410`；`kern_gen11.cpp` POOLALIGN；**仅在 xefix 下启用** | **从 xefix 拆出**，作为独立 TGL 候选；先做目标池布局检查 |
| **XE-BLITSCRATCH2** `[A/D]` | 为 Blit3D scratch 提供 CPU 映射临时缓冲 | **不需要**；它只服务 `!isRealTGL` 的自定义 V148 初始化 | `[3]` 依赖 IGSharedMappedBuffer/IOAF2 | `kern_gen11.cpp:6860-7060`；仅 xefix | **禁止**；真 TGL 走 Apple 原始 init |
| **XE-NOORPHAN** `[C/D]` | `IOAccelOrphanedMemoryPool::getMemory` 永远返回 nullptr，禁用 orphan 复用 | **未知**；如果 25G83 IOAF2 orphan 池本身正常，禁用会泄漏/掩盖 | `[3]` 依赖 IOAF2 符号/行为 | `kern_green.cpp:591-599`；仅 xefix | **默认关闭**；先确认 TGL 上是否真出现 orphan 链表损坏 |
| **XE-RESFREE** `[C/D]` | `IGAccelResource::free` 前清理无效 plane 表指针 | **可能**；Tahoe 资源表 ABI 变化可能影响 TGL | `[3]` 偏移 `+0x250/+0x258/+0xac..0xae` 需目标复核 | `kern_gen11.cpp:6848-6873`；**无条件路由** | **默认关闭**；作为 C 类候选，目标二进制确认后再开 |
| **XE-GTFREQ** `[A]` | 把频率下限抬到 1500 MHz，修 RPL 无 GuC 时 100 MHz | **不需要**；真 TGL 有 GuC/SLPC | `[3]` TGL RP0 与 RPL 不同；会强制高功耗 | `kern_gen11.cpp:6760-6780`；**无条件路由** | **禁止**；真 TGL 保留原生频率管理 |
| **XE-IDLEBOUND** `[A/C]` | 一次 waitForGpuIdle ≥2s 后，30s 内跳过等待 | **不需要**；RPL stamp 不返回 | `[3]` 会掩盖 TGL 真实 hang | `kern_gen11.cpp:6785-6805`；**无条件路由** | **禁止** |
| **XE-PAGESYNC** `[C]` | pageon/pageoff 后等待 copy event | **可能**；Tahoe copy engine 同步问题不一定是 RPL 专属 | `[4]` 依赖 IOAF2 event 布局 | `kern_gen11.cpp:623-634`；ringDiag/xefix | **默认关闭**；单独验证 TGL pageon/pageoff |
| **XE-CSBGUARD/CSBRESYNC** `[A/C]` | 丢弃/重同步 RPL CSB active→idle 事件 | **不需要**；RPL execlist 异常 | `[3]` 依赖 CSB 结构/事件顺序 | `kern_gen11.cpp:713-760`；仅 xefix | **禁止** |
| **XE-SAMETAIL/ELSQ waits/POSH** `[A]` | 同 tail lite restore、等 ELSQ idle、清 POSH | **不需要**；RPL execlist/POSH 差异 | `[3]` 依赖 RPL 寄存器/上下文 | `kern_gen11.cpp:453-916`；仅 xefix | **禁止** |
| **forceWake 替换** `[D]` | 用 i915 移植的 `SafeForceWakeMultithreaded` 替换 Apple 实现 | **不需要**；真 TGL 应保留 Apple 原生 forcewake | `[3]` 依赖 TGL forcewake 寄存器/锁行为 | 路由 `kern_gen11.cpp:2010`；body `10082+` | **禁止**；不要 route，除非有实测缺陷 |
| **HANGCHECK（默认 on）** `[D]` | 第 15 次 forceWake 时 dump GPU 状态，临时 remap GGTT[0]/LRCA | **不需要**；诊断代码 | `[3]` 临时 GGTT 写入在 TGL 上可能触发 MCE/竞态 | `kern_gen11.cpp:10082-10358`；`-ngreenxefix` 只顺带静音 | **必须在 TGL profile 中显式关闭**；建议新增独立 boot-arg/源码 guard |
| **V204 ccont/display hooks** `[D/B]` | 给 plane/scaler 补 `ccont`/`fWriteAccessor`，修显示对象 | **未知**；真 TGL 可能原生正确 | `[4]` 依赖 FB 对象 offset | `kern_green.cpp` V204；CATALOG 2.C | **默认关闭**；只有显示异常且目标 offset 验证后再开 |
| **V40 IOAF2 capability bypass** `[B/D]` | NOP IOAF2 capability 检查，避免 boot hang | **未知**；可能是 16.0.32 vs Tahoe IOAF2 通用问题 | `[3]` 模式 `41 54 53 50 F7 C2 ...` 需目标二进制检查 | `kern_green.cpp:508-521`；**无条件应用** | **需要 TGL 专用 gate**；不能直接删除，也不能假设 RPL 证据 |
| **V221 waitForStamp** `[B/D]` | GFX start 前 stamp 超时假成功，避免 CoreDisplay 死锁 | **未知**；TGL IRQ 安装顺序可能不同 | `[3]` 依赖 IOAF2 符号/时序 | `kern_green.cpp:350-577`；**无条件应用** | **需要 TGL 专用 gate**；先测原生 stamp 是否正常 |
| **DYLDPatches（V50/V60/V187/V189 等）** `[A/D]` | CoreDisplay/sandbox/GVA 的 DYLD 字节 patch | **基本不需要**；多数是 spoofed RPL 路径 | `[3]` 硬编码 Sonoma/Tahoe 字节，命中不确定 | `DYLDPatches.cpp`；CATALOG 2.C | **默认关闭**；不要用 RPL 的 CoreDisplay 补丁掩盖 TGL 问题 |
| **MTL header + libxedrv 注入** `[B]` | 在 MTL driver Mach-O header 增加 `LC_LOAD_DYLIB` | **需要**；没有 adapter 旧驱动无法接 Tahoe Metal | `[3]` header `ncmds/sizeofcmds` 和 padding offset 是二进制特定 | `macos/mtl17-patches.json` offsets 16/4224；donor 已匹配 | **需要目标 25G83 文件先通过 `check-tgl-compat.py`**；不能直接套 25G241 偏移 |
| **MTL compiler plugin path** `[B]` | 把旧 driver 的插件路径改到 `xe.bundle` | **需要** | `[3]` 路径字符串和 sandbox 规则是 25G241 证据；25G83 未验证 | `mtl17-patches.json` offset 0x0a2e7b；`docs/METAL.md` | 目标文件验证后再选 |
| **MTL13/14 fast clear** `[A/D]` | NOP `setne`，关闭 fast clear/dual-SIMD8 clear | **不需要/未知**；RPL AUX 表问题 | `[3]` 依赖 16.0.32 代码字节 | `mtl17-patches.json` 0x1c7c0/0x1c7cf/0x49cfe | **默认关闭**；TGL 支持 fast clear |
| **MTL15 compression flag** `[A]` | `mov ecx,[rax+0x18]` → `xor ecx,ecx`，忽略 IOSurface 压缩标志 | **不需要/未知**；RPL AUX 问题 | `[3]` 依赖 16.0.32 代码字节 | `mtl17-patches.json` 0x18c28 | **默认关闭** |
| **MTL16/17 clear VS** `[D]` | `je`→NOP、`jne`→`jmp`，修 clear 后 VS 状态 | **未知**；RPL 观察 | `[3]` 依赖 16.0.32 代码字节 | `mtl17-patches.json` 0x67c27/0x67c5c | **默认关闭**；TGL 先测原始 clear |
| **MTL18 L3 alloc** `[A]` | `0x88`→`0xd0`（RPL-P L3 reset） | **不需要** | `[3]` TGL-U 的 L3 值不同 | `mtl17-patches.json` 0x65f12 | **禁止** |
| **Info.plist PoshDisable=1** `[A]` | 关闭 POSH | **不需要**；TGL 有 POSH | `[3]` 目标 driver 行为未验证 | `patch-mtl17.py`；`docs/METAL.md` | **禁止**；只有 RPL 无 POSH |
| **libxedrv descriptor 转换** `[B]` | Tahoe descriptor → 16.0.32 旧布局 | **需要** | `[2]` 25G83 独立项目的 size/offset/bit 位置与 `libxedrv` 同形；仍需运行时探针 | `libxedrv.m:44-123`；`pipeline_descriptor_compat.m:74-92` | **保留**；补 class size `0x338`、`_private@0x30` 检查 |
| **libxedrv 新 selector/拒绝能力** `[B]` | 补 `resourceIndex`/buffer descriptor，拒绝 dynamic libs/archive/mesh | **需要**；否则 Tahoe Metal 会调不存在的 selector | `[2]` 25G83 项目也做同类拒绝；具体 selector 需目标运行验证 | `libxedrv.m:127-221`；25G83 `metal_entries.m` | **保留**；按 TGL 能力调整拒绝列表 |
| **libxedrv 无压缩** `[A/D]` | 所有纹理 `allowGPUOptimizedContents=NO` | **不需要**；TGL 支持压缩 | `[4]` 会降低 TGL 性能/改变行为 | `libxedrv.m:296-395`；`XE_COMPRESSAO=1` 可关 | **TGL 应改为默认保留压缩**；不要无条件禁用 |
| **libxedrv v15 no-copy** `[C/B]` | 非 256B 对齐的 zero-copy 纹理改为复制 | **未知**；可能是旧 driver/Gen12 通用 | `[4]` 25G83 CA/IOSurface 路径未测 | `libxedrv.m:435-480` | **保留但单独测试**；不是 RPL 专属 |
| **libxedrv v16 blit 排序** `[C/B]` | 把 fill/aligned copy 全走 3D，避免同 command buffer 2D/3D 竞争 | **未知**；可能是 Tahoe 内核 fence 通用问题 | `[4]` 25G83 未测 | `libxedrv.m:482-580` | **保留但单独测试**；若 TGL BCS fence 正常可关 |
| **libxedrv v17 stencil 64KB** `[C]` | 把未对齐 64KB 的 stencil 重建到独立 heap | **未知**；driver 16.0.32 通用 | `[4]` 25G83 未测 | `libxedrv.m:332-395` | **保留但单独测试** |
| **compiler adapter/bridge** `[B]` | 新 LLVM 32023 → 旧 LLVM 3902/IGC | **需要** | `[3]` `getSerializedModule` 签名和 GPUCompiler 32023 路径依赖目标系统 | `compiler-adapter.cpp`；`llvm-bridge.cpp`；`docs/METAL.md` | **保留**；25G83 先取 `MTLCompiler`/`GPUCompiler` 符号 |
| **`amfi_get_out_of_my_way=1`** `[加载]` | 允许 ad-hoc 签名代码进入 WindowServer/MTLCompilerService | **方案 A 的参考实现需要，但本任务禁止** | `[3]` 目标 AMFI/签名策略未验证 | 参考 `docs/METAL.md`、`docs/HISTORY.md`；任务安全边界 | **禁止**；没有合法签名/加载方案前不得部署 |

## 守卫审计：谁没有 `isRealTGL` 保护

### 1. `-ngreenxefix` 下、但没有 `isRealTGL` 保护

| 位置 | 行为 | 在真 TGL 上的风险 |
|---|---|---|
| `xeFixFilterWrite` / `xeFixEnsure`（`kern_gen11.cpp:3777-3838`） | 改 `0x44FE8`、`0x42084`、`0x4A480` | display 13 寄存器语义，TGL display 12 不应假设 |
| `XE-BLR`（同上） | 改 `0xC8254/0xC8258` | 可能打乱 TGL 背光 |
| `wrapSetFramebufferPowerState`（`6813-6848`） | 伪 DPMS | 可能让 TGL 无法真正睡眠/唤醒 |
| `wrapPoolInit` / `wrapPoolGetPtr`（`kern_green.cpp:357-410`） | 改命令池大小/对齐 | 可能是 TGL 也需要的 B 项，但当前被 xefix 绑定 |
| `wrapOrphanGet`（`kern_green.cpp:591-599`） | 禁用 orphan 复用 | 可能泄漏/掩盖 TGL 正常回收 |
| `ringDiag` / `flipDiag`（`kern_gen11.cpp:1919-1935`） | 安装 CSB/ELSQ/POSH 等 hook | 这些 hook 的 body 含 RPL 修复，真 TGL 上会改变调度行为 |
| `BLITSCRATCH2`（`kern_gen11.cpp:7003-7060`） | 临时 CPU 映射 | 只应服务 `!isRealTGL` 的 V148；真 TGL 不应走到 |
| `forceWake` refcount / `fwsubmit` / `elsqidle` | 替换/包裹 Apple forcewake 和提交 | 真 TGL 原生路径可能更正确 |

**建议：** 不要用 `-ngreenxefix` 作为 TGL 开关；新增 `-ngreentgltahoe`
或逐项 boot-arg，把 B/C 项从 A/D 项中拆出来。

### 2. 被 `!isRealTGL` 挡住、但其实是 Tahoe 布局修复

| 位置 | 为什么是 B 而不是 A |
|---|---|
| `XE-FMT`（`kern_gen11.cpp:2249`） | 读 `IOSurface+0xa4` 是 16.0.32 的固定代码，Tahoe 布局变化与 CPU 型号无关；25G83 项目也记录同一 stale 读取 |
| `XE-PLANES2`（`kern_gen11.cpp:2320`） | `calculateIOSurfaceDeviceCacheVRAMBytes` 的 plane count 读取是 16.0.32 的固定代码；TGL 也会遇到同样的 IOSurface 对象 |
| `XE-NOCCS3` / `XE-NODEPTH` | 其中“Tahoe 命令池与 16.0.32 resolve 不匹配”部分是 OS ABI，不只是 RPL 硬件；但 TGL 的 AUX/压缩所有权不同，不能直接照搬。归 D，需单独验证 |
| `XE-BLITALIGN` | 2D/3D blit 路由和 64B 对齐可能是 16.0.32 + Tahoe 的通用问题，也可能是 RPL BCS 特性；归 D |

### 3. 完全无条件应用的关键项

| 位置 | 行为 | 建议 |
|---|---|---|
| `XE-VALD`（`kern_gen11.cpp:1638`） | FB `ValidateTransaction` 三个字节 patch | **保留但加目标校验**；真 TGL 很可能需要 |
| `V40`（`kern_green.cpp:508`） | IOAF2 capability 检查 NOP | 需要 TGL gate；不能盲信 RPL |
| `V221`（`kern_green.cpp:350`） | stamp 超时假成功 | 需要 TGL gate；先测原生 stamp |
| `XE-RESFREE`（`kern_gen11.cpp:6848`） | 资源表指针清理 | 默认关闭；目标 offset 确认后再开 |
| `XE-GTFREQ`（`6760`） | 频率下限 1500 MHz | **禁止**；真 TGL 有 GuC |
| `XE-IDLEBOUND`（`6785`） | 跳过 waitForGpuIdle | **禁止**；会掩盖 hang |
| `forceWake` 替换（`2010`/`10082`） | i915 forcewake | **禁止**；保留 Apple 实现 |
| `HANGCHECK`（`10082`） | 第 15 次 forceWake dump/remap | **必须显式关闭**；当前只有 xefix 顺带静音 |

## 结论

- **可以直接使用的代码：** `kern_start` 的 Tahoe 版本、`isRealTGL` 检测、
  `-ngreentglwithgfx` 加载策略（需目标 personality 核对）、Apple 16.0.32
  驱动本体、`libxedrv` 的 descriptor/selector 适配骨架、compiler adapter/bridge
  骨架。
- **需要移植的 B 类：** `XE-FMT`、`XE-PLANES2`（先从 `!isRealTGL` 块移出）；
  `XE-VALD`（已无条件，但需目标校验）；`XE-POOLALIGN`（从 xefix 拆出，
  先验证）；`libxedrv` 的 descriptor 预检补强；compiler bridge 的 25G83
  目标验证。
- **必须默认关闭/禁止的 A/D 类：** `-ngreenxefix`、`-disablegfxfirmware`、
  `ngreenSched=4/5`、`ngreen-dmc=adlp`、display 13 寄存器过滤、BLR、FBDPMS、
  V99/V193/V52/V46/V54/V65/V57/V111/V132/V148/V165/V212/V509、
  MTL13–18、PoshDisable、forceWake 替换、HANGCHECK、GTFREQ、IDLEBOUND。
- **必须从真实系统取证的：** 25G83 的 TGL kext/MTL driver/Info.plist/
  IOAF2/MTLCompiler 二进制、符号、header 布局；以及合法签名/AMFI 路径。
