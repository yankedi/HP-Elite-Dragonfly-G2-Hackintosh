# GA416 上游崩溃与 RTC/CMOS 研究

**Exa追加调查及Perplexity结果：** 见[追加核查](GA416-EXA-PERPLEXITY-FOLLOWUP.md)：补充HP具体005/CMOS偏移修复记录、RTCMemoryFixup的25G83 ABI待核验点、本机RTC长度8→2字节匹配，以及Arrow Lake案例的BIOS混杂变量；重新核实下文Metal POSH泄漏复测。Perplexity验证码认证成功但MCP/独立CLI搜索仍403，未取得搜索答案。

**后续补充（第五份panic之后）：** 主代理新增找到网络上同pmap签名、通过调整OpenCore内存图Quirks改善的Arrow Lake平台报告，并用UUID匹配25G83 KDK实际反汇编确认该panic也可由非managed页面触发。见 [pmap/OpenCore候选核查](GA416-PMAP-OPENCORE-CANDIDATE.md)。这是待HP实测的配置层候选，不改变下文“NG上游未找到同签名修复commit”的结论。

**RTC照片补充：** 用户已提供明确的HP“实时时钟电源丢失（005）”照片，详见[005证据](GA416-HP-RTC-005.md)。不能把该照片当作502校验和错误，也不能仅凭提示判定电池已坏或DisableRtcChecksum就是修复。

2026-10-25。范围：只读研究、公开上游源码/issue/commit 检索、项目内既有证据复核。**本轮没有连接 HP，没有修改 EFI/NVRAM/驱动，没有向任何仓库发 issue/评论，也没有 git commit。**

本文回答三件事：

1. 这些新 panic 在 NootedGreen/JulioNectar 上游有没有同签名修复，TGL 与 RPL 应如何区分；
2. HP 类机器上 macOS 后 BIOS 时间丢失、`DisableRtcChecksum`/`AppleRTC`/`RTCMemoryFixup` 的已知行为与边界；
3. macOS 26.6.2 / 25G83 的 KDK、`kernelcore` 是否有直接可用资料。

先给结论：**没有找到能把当前这些 panic 直接归因于某一个 NootedGreen 上游 commit 的证据。** 上游确实有 IOSurface 拷贝、对象生命周期、GPU 复位和用户态 Metal 泄漏方面的修复，但它们针对的是不同签名或不同代际；把“同一条内核释放路径”当成“同一个根因”会重复本轮要避免的错误。

---

## 1. 原始证据的边界

### 1.1 这些新 panic 不是同一条失败链

表中前四行是 2020 时间戳的 panic 文件（pmap、kalloc、最新 pmap、WindowServer 120 s）；最后一行是 2026-10-25 17:05 的 98 s watchdog（不同启动）。放在一起只是为了区分调用面。

| panic 首行 | uptime | 直接触发点 | 当时调用面 | 不能推出 |
|---|---:|---|---|---|
| `pmap_recycle_page: page ... is referenced @pmap.c:1511` | 1192.0438 s | `vm_page_free_list` → `pmap_recycle_page` | `IOSurfaceRootUserClient::get_value` → `OSSerialize::free` → `kmem_free` → VM 映射拆除 | 不能推出 TrackpadExtension 有 bug；不能推出 IOSurface 对象一定损坏；不能推出 GA416 kext 造成 |
| `... not in the expected zone early.kalloc.48[87], but found in [0] @zalloc.c:786` | 2371.0886 s | `OSObject::operator delete` → zalloc 错误 zone 检查 | `IOMachPort::free` ← `ipc_mqueue_copyin`；进程为 VTDecoderXPCService | 不能推出视频解码器有 bug；不能与上一行合并成“IOSurface UAF” |
| `pmap_recycle_page: page ... is referenced @pmap.c:1511` | 1218.7566 s | 缺页路径进入页面释放/一致性检查 | 进程为 `log`；KDK 重符号化后是 `user_trap → vm_fault_internal → vm_fault_page` | 不能推出日志工具写坏内存；也不能证明实时流/历史查询是触发者 |
| `userspace watchdog timeout: no successful checkins from WindowServer ... 120 seconds` | 69977.2580 s | watchdog 发现 WindowServer 120 s 未报到 | watchdog 用户态 panic 路径；主代理将其作为历史事件单独保留，不计入四份新 panic | 只能证明 WindowServer 未按期 check-in；不能证明 GPU hang，也不能证明是哪个线程阻塞 |
| `watchdog timeout: no checkins from watchdogd in 98 seconds` | 791.5097 s | watchdog 发现 watchdogd 98 s 未报到 | AppleSMC/IOWatchdog 定时器线程 | 回溯是“发现超时”的线程，不是阻塞线程；不能据此归责 SMC 或某个驱动 |

这些事件的触发进程/回溯分别落在 IOSurface 属性序列化、Mach port 释放、缺页处理、WindowServer 用户态 watchdog、watchdogd 内核 watchdog 五条不同路径。**它们最多共享“内核在释放/回收资源时发现状态不一致”这一层，不能共享一个未经证明的根因。**

项目最新采集又确认了第四份新 panic（`log` 进程，pmap 同一断言；详见 `GA416-FOURTH-PANIC.md` 与 `GA416-CRASH-SERIES-AND-LOGGING.md`）。这进一步说明：**同一 pmap 断言可以落在完全不同的调用者**，把 `TrackpadExtension` 或 `log` 当成根因是不成立的。

### 1.2 `pmap.c:1511` 到底在检查什么

Apple 公开 XNU 源码中，`pmap_recycle_page()` 的语义是：VM 把物理页交回空闲队列前，要求该页没有被任何 pmap 映射；若 `pmap_verify_free(pn)` 为假，就直接 panic：

```c
inline void
pmap_recycle_page(ppnum_t pn)
{
    const bool is_freed = pmap_verify_free(pn);
    if (__improbable(!is_freed)) {
        panic("%s: page 0x%llx is referenced", __func__, ...);
    }
}
```

来源：<https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/osfmk/x86_64/pmap.c#L1498-L1513>。该 tag 中 panic 恰好在第 1511 行，与 25G83 的 `pmap.c:1511` 对得上；25G83 的实际 xnu 是 `12377.161.14`，Apple 尚未发布这个精确 tag，所以只能把它当作“同代码路径”的最接近公开源，而不是逐字节同一构建。

调用侧在 `vm_page_free_list()`：当 `prepare_object == false` 时，它无条件调用 `pmap_recycle_page()`；另有 `vm_page_grab_finalize()` 在 `vm_check_refs_on_alloc` 为真时调用。见 <https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/osfmk/vm/vm_resident.c#L6011-L6070>。

因此这条 panic 的可靠含义只有：**一个即将被回收的物理页仍然被某个 pmap 认为有映射/引用。** 它可能是页表引用计数错误、映射拆除顺序错误、驱动保留了过期映射，或更下层的内存破坏。它不告诉你“谁写坏了”，也不等于 `IOSurface` 对象本身一定损坏。`IOSurfaceRootUserClient::get_value` 只是在当时释放 `OSSerialize` 缓冲区，恰好走到这条 VM 路径。

### 1.3 `early.kalloc.48` 错误 zone 的含义

XNU 的 `zone_page_metadata_index_confusion_panic()` 在释放对象时检查该对象所在页的 zone metadata：

```c
zidx = meta->zm_index;
...
panic("%p not in the expected zone %s%s[%d], but found in %s%s[%d]", ...);
```

来源：<https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/osfmk/kern/zalloc.c#L730-L765>（该 tag 在第 762 行；25G83 panic 报 786 行，说明 25G83 的 zalloc.c 有约 24 行版本差，不能把行号当成逐字节一致）。

panic 文本中的 `expected zone early.kalloc.48[87]` 是传入释放函数的期望 zone；`found in [0]` 表示该地址所在页的 metadata 指向了 zone index 0（文本中 zone 名为空），不是 `early.kalloc.48`。这通常意味着以下之一：

- 同一对象被释放两次，第一次释放后页已被回收/重分配；
- 传入的地址已经不是原来的对象；
- 页 metadata 或对象头被覆盖。

panic 没有区分这三种。`IOMachPort::free` 是当时正在释放的对象，`VTDecoderXPCService` 是调用进程；**两者都不是根因证据**。项目主代理用匹配 KDK 重符号化后，路径进一步落到 `ipc_right_dealloc → ipc_notify_no_senders_kobject → IOMachPort::free → OSObject_typed_operator_delete → zfree_ext`；这仍然是“释放/回收时发现对象不属于期望 zone”的路径，不是“VTDecoder 解码错误”的证据。这条与 pmap 那条的对象、调用者、失败检查都不同，不能合并叙述。

### 1.4 2020-01-01 时间戳不能当时间线

四份 2020 时间戳的 panic 文件时间分别是（含项目最新确认的第四份）：

- `2020-01-01 08:00:53 +0800` = `2020-01-01 00:00:53 UTC`（第四份 pmap，`log` 进程）
- `2020-01-01 08:00:57 +0800` = `2020-01-01 00:00:57 UTC`（pmap，TrackpadExtension）
- `2020-01-01 08:01:08 +0800` = `2020-01-01 00:01:08 UTC`（kalloc 错误 zone）
- `2020-01-01 08:18:48 +0800` = `2020-01-01 00:18:48 UTC`（WindowServer 120 s）

它们都紧贴 `2020-01-01 00:00 UTC` 这个典型默认值。文件 mtime 与 panic 文本时间只差几秒，说明这份时间更像是 **panic 报告写出时的墙钟**，而不是“崩溃瞬间”的可靠时间。截至最新采集，四份新 panic 的时间戳都落在 2020-01-01 附近；不是只有两份。

更关键的是不自洽：watchdog 那一份的 uptime 是 69977.2580 s（约 19 小时 26 分），如果启动时 RTC 是 `2020-01-01 00:00Z`，panic 应落在约 19:26Z，而不是 00:18Z。因此至少有一个前提不成立：报告可能是在后一次启动、RTC 尚未被 NTP 校正时生成的；或者时间字段来自另一套时钟。**不能把这三个日期当成真实崩溃日期，也不能用它们给 panic 排序。** 它们能支持的结论只有“当时墙钟曾处于 2020-01-01 附近，且与 RTC/CMOS 异常方向一致”。

`+0800` 只是本地时区渲染；`2020-01-01 08:00 +0800` 本身就是 `2020-01-01 00:00 UTC`。**UTC 偏移不是 RTC 无效的证据。**

### 1.5 一个历史反证：同一 pmap 签名在加速栈未启用时也出现过

项目内更早的 `GA1/panic/Kernel-2020-01-01-080254.panic`（文件 mtime 2026-10-17，macOS 25G83）也是：

```text
pmap_recycle_page: page ... is referenced @pmap.c:1511
Panicked task ...: iconservicesagent
```

该启动的 boot-args 含 `-igfxvesa`，说明 GPU 加速栈未启用；同一目录另一份 panic（`Kernel-2020-01-01-080100.panic`）的回溯确实在 `AppleIntelICLGraphics`，但这份 pmap panic 本身只显示 VM/pmap 路径。它不能证明“所有 pmap panic 都与 NootedGreen 无关”（该启动仍可能有其他 kext/配置），但它是一个明确的反证：**这个 pmap 签名在 GA416 的 L3/NOAUX/PLANES2 组合之前就出现过，不能仅凭当前安装的 kext 就认定它是新引入的。**

来源：本地历史文件 `GA1/panic/`。这是历史证据，不是当前 boot 的日志；主代理仍应以当前采集为准。

---

## 2. 上游 issue / commit 检索

### 2.1 JulioNectar 仓库：issue #3

<https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/3>

主题是 80 EU 机器的桌面伪影，不是 panic。结论是 RPL/ADL 80 EU 需要 `ngreen-eu=80 ngreen-l3=6`；拓扑单独不够，L3 bank 数才是缺失项。相关 commit `c4ea440`（XE-TOPO）和 `6b5f049`（文档确认）。

对 GA416 的适用性仅限“80 EU / 6 L3”这一事实：用户在 issue 评论中报告 i5-1135G7、8086:9A49、`0x9118=0x88`、5 DSS / 80 EU / 6 L3；本地把 native TGL 的 L3 fallback 从 8 改为 6。**这不是 pmap/zone/watchdog 的修复。**

### 2.2 JulioNectar 仓库：issue #7（原生 TGL 的 NOAUX/NOCCS3）

<https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/7>

这是与本机最接近的原生 TGL 证据：HP Elite Dragonfly G2、i5-1135G7、9A49、25G83。核心结论是：CPU `getBytes` 在 `resolveCCS` 返回成功后仍然读到压缩/未解析内容；把 NOAUX 也应用到 native TGL 后，CPU/GPU 读回都变为 0 坏点。

仓库所有者对 NOCCS3 的原文非常关键：

> “In this repo **XE-NOCCS3 is only safe together with XE-NOAUX**. NOAUX patches ... so there is nothing left for `submitCCSResolve` to resolve, and stubbing it (NOCCS3) is harmless.”

同一评论还有适用性警告：

> “Caveat: this stack has only been built and tested on 26.7.1 (25G241); your 25G83 offsets may differ, so check every patch's bytes as you did.”

这支持**保留 NOAUX + NOCCS3 这一对**，而不是单独删掉其中一个；但它没有涉及 pmap/zone。它也不能证明 25G83 上所有补丁字节都与 25G241 相同。

### 2.3 JulioNectar 仓库：issue #12（POSH 96 KB 泄漏）

<https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/12>

这是目前最明确的“对象生命周期”类上游修复，但它在**用户态 Metal 驱动**，不在内核：

- `MTLIGAccelCommandBuffer` 的 `_pPoshUsedAsTarget` 每个 command buffer 泄漏 96 KB；
- WindowServer 可增长到 10+ GB；
- 修复 commit `06986480e4d9c1383e57ad4e8e89213b5f124bc9`：在 `-[MTLIGAccelCommandBuffer dealloc]` 中把 `0x7ed87` 的 `jne` 改成 `nop nop`；
- 报告者在打了补丁的 bundle 上复测：1500 个 command buffer 后 96 KB 块从 1500 降到 0，WindowServer 内存不再增长；
- 修复前提是 `MTLIGAccelCommandQueue.m_pPoshUsedAsTarget` 始终为 NULL；这是该构建的 disassembly 结论。

来源：issue #12 的 owner 评论（2026-10-25）与报告者复测评论；commit <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/commit/06986480e4d9c1383e57ad4e8e89213b5f124bc9>。

**适用性**：这是 `AppleIntelTGLGraphicsMTLDriver.bundle` 16.0.32 的二进制补丁，不是 NootedGreen kext。它可能降低 WindowServer 的内存增长，但没有证据表明它能修 pmap_recycle_page 或 zalloc 错误 zone。若要在 25G83 上使用，必须先确认 bundle 版本、`0x7ed87` 处仍是 `75 0d`，并重新签名；不要仅凭版本号套用。

另有一个容易与“内核对象生命周期”混淆的上游用户态项：libxedrv v18 的 `0c08285c1cdfdaebf31837907afc2e3e696a042d` 把宽度 ≥32768 B/row 的 IOSurface 直接 alias 成 no-copy MTLBuffer（用于登录壁纸）。它改变的是用户态 IOSurface 映射方式，不是内核 pmap/zone 修复；当前机器已加载 libxedrv，但它不在 pmap/zone panic 的调用链里。它能作为一个“映射层变量”保留在清单中，不能被当作根因。

### 2.4 JulioNectar 仓库：issue #13 / #8 / #2（RPL/ADL 初始化与 hang）

- #13 A7A8 64 EU RPL-P：`IOAccelTask::release` page fault ← `IGAccelTask::withOptions`；owner 明确说 fault 在 Apple 自己的 `withOptions`，不是 NootedGreen 代码；根因是 task init 返回 false 后错误路径释放半初始化对象。
  <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/13>
- #8 A7A8 48 EU 桌面 HDMI：`AppleIntelPort::probePortState()+0x207` 纯虚调用；owner 说 slot 0x190 是纯虚，问题是桌面 RPL + HDMI 端口类型，不是拓扑。
  <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/8>
- #2 Latitude 7430 RPL：打开 Photo Booth / 显示 / 触控板时 RCS hang（context 5，WAIT_ON_SCANLINE），可导致 WindowServer watchdog；这是 GPU hang 路径。
  <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/2>

它们与本次 pmap/zone 不是同签名。#2 只与“watchdog”这一表层症状相同；#13 只与“对象释放”这一层相同。把它们当成本次根因会跨越证据层级。

### 2.5 更早的 sgiammori/NootedGreen：TGL 初始化期 panic

上游基础仓库的 TGL 报告也值得作为“对象生命周期但不同签名”的对照：

- #12（sgiammori）Lenovo i5-1135G7 / 9A49 / Ventura 13.6：`-allow3d` 时 `IOAccelTask::releaseEv` NULL deref（CR2=0xc78），100% 复现；owner 最后说库已开放、请自行 fork，没有给出修复。
  <https://github.com/sgiammori/NootedGreen/issues/12>
- #16 TGL-H 9A60：`-allow3d` 时 IntelAccelerator 初始化期 panic；作者已禁用 `getGPUInfo` override、`IGAccelTask::withOptions` hook 等仍复现。
  <https://github.com/sgiammori/NootedGreen/issues/16>
- #20/#21：真实 TGL 的 scanout/display pipe 仍未打通，作者报告 native-init 的 gap 并非“real TGL 自动正确”。
  <https://github.com/sgiammori/NootedGreen/issues/20>、<https://github.com/sgiammori/NootedGreen/issues/21>

这些是 **TGL 初始化期**的 NULL/初始化失败，不是运行 20 分钟后的 pmap/zone 断言；但它们说明“原生 TGL 路径一定成熟”这个假设本身需要证据。它们也没有提供本次 panic 的修复。

### 2.6 没有找到同签名修复

检索范围：JulioNectar 仓库公开 issue（16 个）及其评论、主要 commit；sgiammori/NootedGreen 公开 issue（20 个）及主要评论；NootedGreen 源内 `XE-*` 补丁说明。**在已检索的公开材料中**：

- 没有 issue 报告 `pmap_recycle_page ... is referenced`；
- 没有 issue 报告 `not in the expected zone early.kalloc.48`；
- 没有检索到 commit 声称修复这两个签名；
- 唯一带 “zone” 的是 #12 的用户态 `MallocHelperZone`/`MALLOC_MEDIUM`，与内核 zalloc 无关。

这是基于公开检索的**否定性证据**，不等于全世界没有修复；但它足以否定“上游已有一个可直接套用的同签名修复”这一说法。

### 2.7 源内已有的对象生命周期补丁

本地 GA416 源码树 `GA416-L3-6-Source`（HEAD `f93dc244`，基线 `c24ed0d`）包含：

| 补丁 | 作用 | 本地状态 | 与本次 panic 的关系 |
|---|---|---|---|
| `XE-RESFREE` | `IGAccelResource::free` 前清理 per-plane/mip 表中的无效指针 | 默认开启（`-ngreennoresfree` 关闭） | 减少 `kfree`/无效指针类 panic；**没有**证明能修 pmap/zone |
| `XE-NOORPHAN` | `IOAccelOrphanedMemoryPool::getMemory` 不返回可复用内存，避免 orphan 池“corrupt list” | 源码有，但只在 `-ngreenxefix` 下挂载；当前 boot-args **没有** `-ngreenxefix`，因此未启用 | 是 IOAF2 对象复用类问题；主要在 RPL 观察，TGL 未验证；**不是**当前 panic 的已证明原因 |
| `XE-PAGEONGUARD` | `pageon` 前用 `pmap_find_phys` 检查 plane 表/数组是否映射 | 默认开启（`-ngreennopageonguard` 关闭） | 防止 pageon 的 GP fault；不是 pmap_recycle_page 的修复 |
| `XE-PLANES2` | `calculateIOSurfaceDeviceCacheVRAMBytes` 从 `IOSurface+0x98` 读 plane count | 默认开启（`-ngreennoplanesfix` 关闭） | 这是当前最值得核对的 IOSurface ABI 点；见 §2.8 |
| `XE-FMT` | `performTransaction` 强制 `BGRA` | 默认开启（`-ngreentgltahoe` 下） | 显示格式，不是内存回收 |

`XE-NOORPHAN` 的源码注释明确说它是在 RPL 的 TGL 驱动事件/ABI 不匹配下观察到 orphan 池链表损坏；这类“RPL 上成立、TGL 上未必需要”的补丁不能因为“看起来像对象生命周期”就整体搬到 TGL。

### 2.8 `IOSurface+0x98` 是未闭环点，但不能据此判根因

本地 GA416 源码在 native TGL + `-ngreentgltahoe` 下应用 `XE-PLANES2`，把 driver 原来的 `IOSurface+0xb0` 改成 `+0x98`。源码注释自己写着：

> “+0x98 remains the upstream 25G241 value, pending 25G83 runtime validation.”

项目内更早的 GA4.4 证据报告也把它标为 `DONOR_VERIFIED + TARGET_ABI_UNVERIFIED`，并写明“目标 getter 优先”：

- `GA44-TGL-25G83-Evidence/reports/PATCH-REVALIDATION.md`
- `GA44-TGL-25G83-Evidence/reports/IOAF2-25G83.md`
- `GA44-TGL-25G83-Evidence/patches/nootedgreen-tgl-native.patch`（注释原文：`+0x98` is only a candidate for 25G83 until the target binary confirms it）

**正确的说法**：这是一个真实存在的 25G83 IOSurface ABI 未验证点；如果 `+0x98` 在该构建不是 plane count，`calculateIOSurfaceDeviceCacheVRAMBytes` 可能使用错误计数，进而影响 plane 表/VRAM 计算。**但不能反过来说它已经导致 pmap/zone panic**——当前桌面可用、此前已有一次 R8 PIXEL_PASS，且 panic 调用点并不在 `calculateIOSurfaceDeviceCacheVRAMBytes`。它是一个应验证的风险，不是已证明的根因。

### 2.9 `MEKOD/not-a-security-issue`：IOSurface 属性路径的已知 UAF 类

<https://github.com/MEKOD/not-a-security-issue>

该仓库展示了一个针对 `com.apple.iokit.IOSurface` 的确定性 UAF/teardown panic PoC，声称影响 macOS 15.x–26.x，需要约 386,000 次属性/锁操作和堆 grooming，Apple 将其归类为“非安全问题”。它说明 **IOSurface 的属性序列化/销毁路径在 26.x 确实是脆弱的**，但它不是修复，也不是本机随机崩溃的证据；正常使用不满足它的操作规模。

引用它的价值仅在于：`IOSurfaceRootUserClient::get_value` 出现在 pmap panic 的调用链里并不是不可能，但“出现”不等于“根因”。不能只凭关键词把本机 panic 归到 IOSurface UAF。

### 2.10 TGL / RPL 适用性矩阵

| 上游项 | 来源 | 主要目标 | GA416 本地状态 | 与本次 panic 同签名？ | 适用性判断 |
|---|---|---|---|---|---|
| 80 EU / L3=6 拓扑 | #3、`c4ea440`、`6b5f049` | RPL/ADL 80 EU；native TGL 的 L3 fallback | 本地 L3 8→6 | 否 | 伪影/拓扑修复；不是 panic 修复 |
| NOAUX | #7、GA414 | native TGL HP/25G83（也用于 RPL） | 已应用 | 否 | 与 NOCCS3 成对；owner 明确说 NOCCS3 单独不安全 |
| NOCCS3 | #7、GA414 | Tahoe + RPL，后扩展到 native TGL | native TGL 已应用 | 否 | 需与 NOAUX 配对；25G83 字节需核对 |
| NODEPTH | #7、GA414 | RPL 的 depth resolve 路径 | 源码在 `!isRealTGL` 分支；native TGL 未应用 | 否 | 不要把 RPL 的 depth resolve 绕过当作 TGL 修复 |
| XE-PLANES2 / XE-FMT | HP/25G83 补丁 | Tahoe IOSurface ABI，TGL/ADL/RPL 都可遇到 | 已应用（`+0x98`） | 否 | **25G83 ABI 未验证**；验证优先，不能判根因 |
| XE-RESFREE | 本地源码 20/10 | RPL 首次观察，通用释放路径 | 默认开 | 否 | 可能减少 `kfree` 类；不是 pmap/zone 的已验证修复 |
| XE-NOORPHAN | 本地源码 20/10 | RPL 观察到的 orphan 池损坏 | 源码有，当前未挂载（缺 `-ngreenxefix`） | 否 | TGL 未验证；不要为“像”而启用 |
| XE-PAGEONGUARD | 本地源码 19-20/10 | RPL 首次观察 | 默认开 | 否 | 防 GP fault；不是 pmap |
| XE-GPUREC v1/v2 | `813d2e6`、`df7ab78`、`1c792c4` | RPL 共享 render reset | **不在安装的 kext 中**（strings/git 均无） | 否 | 修 GPU hang→watchdog 类；不修 pmap/zone；不要盲目搬到 TGL |
| XE-BLITFIX | `df7ab78` | IOSurface 拷贝路由，TGL/RPL | **不在安装的 kext 中** | 否 | 修内容为零/绿黑图；不修内存回收 |
| XE-BLITALIGN | `282acba` 等 | IOSurface 线性拷贝 | strings 有；源码在 `!isRealTGL` 分支，native TGL 未走 | 否 | 内容正确性；不是 TGL 的 panic 修复 |
| Metal POSH 96 KB 泄漏 | #12、`0698648` | 用户态 Metal bundle | 未见已安装证据 | 否 | 降 WindowServer 内存增长；不是内核 pmap/zone 修复 |
| TGL `IOAccelTask::releaseEv` | sgiammori #12/#16 | TGL 初始化 | 不同签名 | 否 | 说明 TGL init 仍有历史问题；没有可用修复 |

**“安装的 kext 中没有 GPUREC/BLITFIX”是事实，不是价值判断。** 我在镜像回读的 `NootedGreen` 二进制中检索字符串：`GPUREC`、`BLITFIX`、`xe-rec-*`、`xe-blitfix` 均为 0；`BLITALIGN`、`BLITSCRATCH`、`PAGEONGUARD`、`PLANES2`、`NOORPHAN`、`IDLEBOUND`、`NOCCS3`、`NOAUX` 均存在。源码分支的最后主提交在 2026-10-21，确实早于 10-22/10-23 的 GPUREC/BLITFIX 提交；GA416 的 L3 分支是在此基础上做的，不应被描述成“已包含全部上游修复”。

---

## 3. RTC / CMOS

### 3.1 OpenCore 的两个不同层级

OpenCore 当前文档对 `DisableRtcChecksum` 的原文：

> **DisableRtcChecksum** — Type: plist boolean; Failsafe: false; Requirement: 10.4; Description: **Disables primary checksum (`0x58`–`0x59`) writing in AppleRTC.**
>
> Note 1: This option will not protect other areas from being overwritten, see RTCMemoryFixup kernel extension if this is desired.
>
> Note 2: This option will not protect areas from being overwritten at firmware stage (e.g. macOS bootloader), see `AppleRtcRam` protocol description if this is desired.

来源：<https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/Configuration.tex>（搜索 `DisableRtcChecksum`；当前 master 的 `Configuration.pdf` 同文）。

`AppleRtcRam` 是 UEFI 协议替换：

> Replaces the Apple RTC RAM protocol with a builtin version. Builtin version ... may filter out I/O attempts to certain RTC memory addresses. The list ... can be specified in `4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102:rtc-blacklist` variable as a data array.

来源：同一 `Configuration.tex`，`UEFI → ProtocolOverrides → AppleRtcRam`。

`RTCMemoryFixup` 是内核 kext，用 `rtcfx_exclude=offset1,offset2,start-end` 模拟/屏蔽 CMOS 偏移；它自己说明：

> “An open source kernel extension providing a way to emulate some offsets in CMOS (RTC) memory. It can help you to avoid some conflicts between macOS AppleRTC and firmware/BIOS of your PC.”
>
> Offsets `00`–`FF`; `0x80`–`0xAB` may hold hibernation info; excluding them breaks hibernation.

来源：<https://github.com/acidanthera/RTCMemoryFixup>（README；最新 release 1.0.7，2020-10-05；OpenCore `Docs/Kexts.md` 仍把它列为 26 可用，但没有 2026 年的新 release，属于“老工具、需实测”）。

**边界**：

- `DisableRtcChecksum` 只挡 AppleRTC 内核态对 `0x58–0x59` 的写入；BIOS 校验和不在这些偏移、或写入发生在 boot.efi/固件阶段时，它无效。
- `RTCMemoryFixup` 在内核态拦截 RTC I/O，不能保护 boot.efi/固件阶段。
- `AppleRtcRam` + `rtc-blacklist` 在 UEFI 协议层过滤，能覆盖 boot.efi 阶段；但它需要正确填写 Data 字节，不是字符串。
- `WriteFlash` 管 NVRAM 写入策略，不等同于 RTC/CMOS 保护；不要把它当成 RTC 修复。

### 3.2 HP 机器的已知行为

最接近的 HP 案例是 acidanthera bugtracker #1305（EliteBook 840 G2）：

> “After I restart, my time get reseted every time. I have DisableRTCChecksum quirk enabled but seems to not work ... I tried excluding the entire region with `rtcfx_exclude=00-FF` but my time is still reset. The battery holds the charge well.”

vit9696 的回复：

> “Could be EfiBoot doing this. I would suggest using rtc-blacklist instead.”

来源：<https://github.com/acidanthera/bugtracker/issues/1305>。这条证据非常重要：**它直接否定了“打开 DisableRtcChecksum 就一定解决 HP 时间丢失”的假设**，也说明需要把内核态和固件态分开查。

**#1322** 中另一个 HP（Elite X2）机器，维护者给出的完整坏区字节串是：

```text
58597F80818283B0B1B2B3DEDF
```

它对应 0x58–0x59、0x7F–0x83、0xB0–0xB3、0xDE–0xDF 等多段；报告还提到 macOS 更新/安装器、深度睡眠会写不同区域，所以需要多场景测试。这里的字节串是 `rtc-blacklist`/`rtcfx_exclude` 的**数据**，不是可直接照抄到另一台 HP 的结论。
来源：<https://github.com/acidanthera/bugtracker/issues/1322>。

HP 官方支持文档对 CMOS 校验和错误的解释则是硬件/固件两条线：

> “There are two main reasons a BIOS test fails: The battery on the system board has lost its ability to supply power. The BIOS was updated incorrectly.”

并建议恢复默认、必要时更换 CMOS 电池。
来源：<https://support.hp.com/us-en/document/ish_9432008-9432063-16>。

HP 社区还有一类机器（不是 Dragonfly G2）明确说“没有独立 CMOS/RTC 电池，主电池承担 RTC 供电”，拔主电池就会每次丢失 BIOS 设置和时间：
<https://h30434.www3.hp.com/t5/Notebook-Operating-System-and-Recovery/Does-removing-the-laptop-battery-over-time-erase-the-BIOS/td-p/8900277>。

**没有检索到 HP Elite Dragonfly G2 的 macOS RTC 专项报告。** 因此不能把任何论坛上的 HP 偏移表直接当作本机结论；Dragonfly G2 需要自己测。

### 3.3 `AppleRTC active` 与 `RTC memory address 112 length 8` 的含义

当前 IORegistry 里：

```text
RTC (PNP0B00), _STA=15
IODeviceMemory = (({address=112, length=8}))
AppleRTC active, IONameMatch=PNP0B00, IOMatchedAtBoot=Yes
```

112 = `0x70`，length 8 = `0x70–0x77`。这是 ACPI `PNP0B00` 常见的 RTC index/data 寄存器窗口（`0x70` 索引、`0x71` 数据，其余为 NMI/扩展），**不是 256 字节的 CMOS RAM 内容本身**，也不是“AppleRTC 正在写坏 0x58/0x59”的证据。`AppleRTC active` 只说明驱动匹配并启动了；它不证明 RTC 读写正确，也不证明时间丢失是它造成。

同理，`RTC memory address 112 length 8` 不能拿来反推 CMOS 电池、校验和区域或 RTCMemoryFixup 的偏移。要判断 RTC 是否真的在走，应该比较 BIOS 时间、`kern.boottime`、单调 uptime 和 NTP 校正记录，而不是看这个 IORegistry 窗口。

### 3.4 当前项目快照的交界证据

项目内的交付镜像回读（`ga416/private/l3-six/image-readback/EFI/OC/config.plist`）与主代理 2026-10-25 的当前核对（`GA416-CRASH-SERIES-AND-LOGGING.md`）一致：

- `Kernel → Quirks → DisableRtcChecksum = false`
- 无 AppleRTC Kernel.Patch
- `UEFI → ProtocolOverrides → AppleRtcRam = false`
- 没有 `RTCMemoryFixup.kext`
- 没有 `rtc-blacklist`

这些是当前部署基线的事实，不是本轮改动。若当前仍是这个状态，那么“时间丢失没有被任何 RTC 保护覆盖”是合理的待验证点，但**不能直接跳到“打开某个选项就会好”**——HP #1305 已经说明单开 `DisableRtcChecksum` 可能无效。RTC 修复应与崩溃诊断分开验收，一次只动一个变量。

### 3.5 建议的区分实验（只做研究设计，不执行）

1. **先证明是 RTC 还是 NTP/时区**：在 BIOS 里记录日期时间；完全关机（不是重启），等待 10 分钟以上；再进 BIOS 看时间。若关机期间也丢，优先怀疑 RTC 电池/主板供电；若只在 macOS 关机后丢，优先怀疑 AppleRTC/EfiBoot 写入。
2. **对比 OS**：同一台机器用 Linux/Windows 正常关机，再进 BIOS 看是否丢。若只有 macOS 丢，才把范围收窄到 macOS/OpenCore。
3. **区分“只丢时间”还是“设置也回默认”**：只丢时钟更像电池/晶振；出现 CMOS checksum/设置回默认更像校验和/固件写入。
4. **一次只动一个变量**：先只开 `DisableRtcChecksum` 观察；无效再考虑 `AppleRtcRam` + `rtc-blacklist`，或 `RTCMemoryFixup` 的 `rtcfx_exclude` 二分（`00-FF` → `00-7F`/`80-FF` → …）。不要同时开多个机制，否则无法归因。
5. **记录 NTP**：联网后时间恢复只证明网络时间可用，不证明 RTC 正常；要记录 boot 时墙钟与 NTP 校正的时间差。

**RTC 与 panic 的关系**：目前没有证据表明 RTC 复位会导致 pmap/zone/watchdog panic。RTC 解释的是 2020 时间戳和 BIOS 时间丢失；panic 需要独立的内存/调度证据。不要把两件事合并成一个根因。

---

## 4. macOS 26.6.2 / 25G83 的 KDK 与 `kernelcore`

### 4.1 KDK 25G83 是存在的

Dortania 的 KDK 镜像仓库有精确的 25G83 资产：

- Release：<https://github.com/dortania/KdkSupportPkg/releases/tag/25G83>
- 资产：`Kernel_Debug_Kit_26.6.2_build_25G83.dmg`
- 大小：1,179,774,396 bytes
- SHA-256：`577cdc8b2c09eaebfb16b0372ab6d6dc128ad4a08eaae09428d84a6c8a1e53c3`
- 发布时间：2026-09-08（该镜像由 CI 上传）

Apple 官方入口仍是 <https://developer.apple.com/download/more/>（需要开发者登录）。Apple 文档说明 KDK 用于两机内核调试和 core dump 分析，安装后位于 `/Library/Developer/KDKs/`，可用：

```sh
lldb /Library/Developer/KDKs/KDK_26.6.2_25G83.kdk/System/Library/Kernels/kernel
```

来源：<https://developer.apple.com/documentation/apple-silicon/debugging-a-custom-kernel-extension>。

项目主代理已经在目标机安装 `KDK_26.6.2_25G83.kdk`，并实测其 x86_64 release kernel 与 `kernel.dSYM` 的 Mach-O UUID 都等于 panic 的 `39CC2C26-3F72-3565-89C4-94DFE36DFDF2`；因此用 `atos` 按 slide 重符号化是有效的。**这也说明 KDK 对本次问题不是“有没有”的问题，而是“怎么用、能用到哪一层”的问题。**

### 4.2 `kernelcore` 是什么

`kernelcore` 不是 Intel 专用的内核文件，也不是一个可以单独下载的“Tahoe Intel core”。在 XNU 的 LLDB 宏里，`tools/lldbmacros/core/kernelcore.py` 是被 `xnu.py` 导入的 Python 模块，提供内核对象/地址/队列等 LLDB 辅助，代码里同时处理 `x86_64` 和 `arm64`：

- <https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/tools/lldbmacros/core/kernelcore.py>
- `xnu.py` 的导入：<https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/tools/lldbmacros/xnu.py>

KDK 里的 `System/Library/Kernels/kernel` + `kernel.dSYM` 才是带符号的内核；`kernel.development` 是开发内核，另有 `kernel.kasan`。KDK 不是“Intel Tahoe 专属”，而是按 macOS build 提供，包含 x86_64 slice。主代理已在本机用 `file`/Mach-O header 确认这三个 x86_64 文件存在；它们尚未安装到启动 KC，当前仍为 release。

**本机的 `/System/Volumes/VM/kernelcore` 不是有效转储**：主代理实测为 1 MiB，256 个 4 KiB 块，每块 4095 字节零加换行，没有有效转储头；双端 SHA-256 相同，只是占位内容。它不能用于内核内存分析。`kern.coredump=1` 是用户进程 core 控制，不等于内核转储已启用；`/cores` 为空也不能证明有内核 core。

### 4.3 对当前问题的实际价值

- 当前 panic 已经带 `keepsyms=1`，但原始符号不是完整私有符号链；KDK 重符号化能进一步落到 `vm_fault`/`OSSerialize::free`/`ipc_right_dealloc` 等路径，主代理已实际使用。
- KDK 的价值在于：需要离线检查内核结构、`vm_page_t`/`pmap`/`zone` 状态，或用 `kdp-remote` 做两机调试时，提供匹配 25G83 的内核符号/类型。
- **必须匹配 build**：25G83 的 KDK 不能拿去符号化 26.7/25G220 的内核；反过来也一样。第三方 kext（NootedGreen）的符号还需要它自己的 dSYM，KDK 不会自动提供。
- 安装 KDK 本身通常不替换正在运行的内核；不要为了调试把 `kernel.development` 复制进系统卷或改 NVRAM，除非有明确回滚方案。本任务不执行这些操作。
- 目前没有可用的内核内存转储：`/System/Volumes/VM/kernelcore` 是 1 MiB 占位；要获得更深的“谁先写坏”证据，需要未来现场的全线程栈或单独授权的 development/KASAN/转储方案。

---

## 5. 研究结论与下一步

### 5.1 可以下的结论

1. **这些 panic 至少分属不同失败面**：pmap 页仍被引用、zalloc 错误 zone、watchdog 未 check-in；触发进程不是根因。
2. **没有上游同签名修复**。issue #12 的 POSH 泄漏、#13/#8 的 RPL 初始化、sgiammori #12/#16 的 TGL 初始化，都不能直接解释或修复本次 pmap/zone。
3. **最接近的上游对象生命周期项**是 `XE-RESFREE`、`XE-NOORPHAN`、`XE-PAGEONGUARD` 和用户态 POSH 修复；其中 `NOORPHAN` 当前未挂载，`GPUREC/BLITFIX` 不在安装的 kext 中。它们是“未包含/未启用”的事实，不是“已证明能修本次 panic”。
4. **TGL/RPL 必须分开**：80 EU 拓扑、GPUREC、NOORPHAN、HDMI/port init 的多数证据来自 RPL/ADL；native TGL 的 NOAUX/NOCCS3/PLANES2 是另一条经过 HP 实测的路径。不能整体合上游。
5. **RTC 是独立问题**：2020 时间戳与 BIOS 时间丢失方向一致，但 `+0800`、112/8 的 IORegistry 窗口、`AppleRTC active` 本身都不证明 RTC 无效；panic 时间戳与 uptime 不自洽，不能当时间线。
6. **KDK 25G83 可用且目标机已安装并验证 dSYM UUID**，但它是调试工具，不是修复；`kernelcore.py` 是 LLDB 宏模块，不是 Intel 专用文件；本机 `/System/Volumes/VM/kernelcore` 是 1 MiB 占位，不是有效转储。

### 5.2 建议的验证顺序（不改 EFI/NVRAM）

1. **先保留现场**：后续若再发生，优先完整保存 panic + stackshot；现有 panic 的 stackshot 字段为 `no on disk or sleep/wake failure panic stackshot found`，还缺全线程等待链。
2. **验证 `IOSurface+0x98`**：用 25G83 目标上的 `IOSurface::getPlaneCount` getter/KDK 反汇编核对，而不是继续把 25G241 的裸偏移当已证事实。若无法确认，任何基于 PLANES2 的因果推断都应降级。
3. **验证 Metal bundle 版本**：若考虑 #12 的 POSH 修复，先确认 25G83 的 `AppleIntelTGLGraphicsMTLDriver` 版本与 `0x7ed87: 75 0d`；这是用户态 bundle，需重新签名，不能与内核 panic 混为一谈。
4. **RTC 单变量实验**：按 §3.5 先区分电池/固件/OS 写入；一次只开一个保护机制。不要同时启用 `DisableRtcChecksum`、`AppleRtcRam`、`RTCMemoryFixup`。
5. **内存/内存映射反证**：社区有 `pmap_recycle_page` 在 macOS 26 上被 OpenCore 内存映射 quirk 改变后消失的个案（如 <https://www.hackintosh-forum.de/forum/thread/60523-macos-26-tahoe-auf-den-hackintosh/?pageNo=21> 的 Z890 案例），但平台不同、属于轶事，不能直接套到 HP TGL。若要查，先做 RAM 测试和当前 OC 内存 quirk 审计，不要盲改。
6. **GPUREC/BLITFIX 的取舍**：只有在出现同签名 GPU hang/blit 问题时才评估；GPUREC 是 RPL 共享 render reset 的修复，不应为了“上游更新”整体移植到 native TGL。若移植，必须保留 real-TGL 门和逐字节 preflight。

### 5.3 主要不确定性

- 25G83 的精确 xnu 源（`12377.161.14`）未在 apple-oss-distributions 发布；本文用最接近的 `12377.121.6` 解释语义，pmap 行号吻合，zalloc 行号有版本差。
- “没有上游同签名修复”是公开检索的否定性结论，不是对所有私有 fork/未公开修复的证明。
- `pmap_recycle_page` 的具体持锁者/残留映射没有在当前 panic 中给出；需要 stackshot 或 KDP。
- `early.kalloc.48` 的 `[0]` 只说明 metadata zone 不匹配，不能单独区分 double free、页重用和对象头覆盖。
- 项目内 OC 配置值有镜像回读与主代理当前核对两个来源；本报告只引用后者已明确的事实，未做独立的当前 ESP 审计。
- 用户态 libxedrv/Metal bundle 的 IOSurface aliasing 和内存增长是独立变量；它们不在当前 pmap/zone 调用链里，不能因为“同为 IOSurface”就归因，但也不能在未核对版本/偏移前宣称无关。
- RTC 的 HP 偏移表来自其他型号，Dragonfly G2 未检索到专项报告；必须实测。
- 2020 时间戳与 uptime 的不自洽说明时间字段不能作为事件排序依据。

---

## 6. 参考链接

**本报告引用的项目内证据**

- `ga416/GA416-FOURTH-PANIC.md` — 第四份 pmap（`log` 进程，20:18.7566 s）
- `ga416/GA416-CRASH-SERIES-AND-LOGGING.md` — 四份新 panic、KDK 符号化、当前 RTC/OC 基线、`kernelcore` 占位
- `ga416/reports/L3-6-CRASH-SERIES.json` — 四事件统计
- `GA44-TGL-25G83-Evidence/reports/PATCH-REVALIDATION.md`、`IOAF2-25G83.md`、`patches/nootedgreen-tgl-native.patch` — `IOSurface+0x98` 的 `TARGET_ABI_UNVERIFIED`
- `GA1/panic/` — 更早的 `-igfxvesa`/ICL 历史 pmap 对照（非当前 boot）

**上游 issue / commit**

- <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/3> — 80 EU 拓扑/伪影，`ngreen-eu=80 ngreen-l3=6`
- <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/7> — native TGL NOAUX/NOCCS3，25G83 字节核对警告
- <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/12> — POSH 96 KB 泄漏，`0698648`
- <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/13> — RPL `IOAccelTask::release` page fault
- <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/8> — RPL `probePortState` 纯虚
- <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/2> — RPL RCS hang / WindowServer watchdog
- <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/commit/06986480e4d9c1383e57ad4e8e89213b5f124bc9> — Metal bundle v18 POSH 修复
- <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/commit/813d2e6adca277dd349ebe9674233953cce66342> — XE-GPUREC v1 / RC6FW
- <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/commit/df7ab78f79d08a8a792292982b46d2bcf110f052> — XE-BLITFIX / GPUREC v2
- <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/commit/c4ea44075d7d3dc6997afc5f3462ffd54199439b> — XE-TOPO
- <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/commit/0c08285c1cdfdaebf31837907afc2e3e696a042d> — libxedrv v18 宽 IOSurface no-copy alias（用户态映射，不是 pmap 修复）
- <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/main/docs/KERNEL-PATCHES.md> — XE-RESFREE / NOORPHAN / PAGEONGUARD / GPUREC 等说明
- <https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/blob/main/docs/CATALOG.md> — 完整补丁目录与 boot-args
- <https://github.com/sgiammori/NootedGreen> — 上游基础仓库
- <https://github.com/sgiammori/NootedGreen/issues/12> — real TGL `IOAccelTask::releaseEv` NULL deref（不同签名）
- <https://github.com/sgiammori/NootedGreen/issues/16> — TGL-H 初始化 panic（不同签名）
- <https://github.com/sgiammori/NootedGreen/issues/20>、<https://github.com/sgiammori/NootedGreen/issues/21> — real TGL scanout/display pipe 进展

**XNU / IOSurface 类**

- <https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/osfmk/x86_64/pmap.c#L1498-L1513> — `pmap_recycle_page` 断言
- <https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/osfmk/vm/vm_resident.c#L6011-L6070> — `vm_page_free_list` 调用点
- <https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/osfmk/kern/zalloc.c#L730-L765> — 错误 zone 检查
- <https://github.com/MEKOD/not-a-security-issue> — IOSurface 属性路径 UAF PoC（不是修复）

**RTC / CMOS**

- <https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/Configuration.tex> — `DisableRtcChecksum` / `AppleRtcRam` / `rtc-blacklist`
- <https://github.com/acidanthera/RTCMemoryFixup> — `rtcfx_exclude` 语义与偏移注意
- <https://dortania.github.io/OpenCore-Post-Install/misc/rtc.html> — RTC 写入问题与二分方法
- <https://github.com/acidanthera/bugtracker/issues/1305> — HP EliteBook 840 G2：`DisableRtcChecksum`/`00-FF` 仍失败，EfiBoot 写入
- <https://github.com/acidanthera/bugtracker/issues/1322> — HP Elite X2 多坏区与 `rtc-blacklist`
- <https://support.hp.com/us-en/document/ish_9432008-9432063-16> — HP 官方 CMOS 校验和/电池说明
- <https://h30434.www3.hp.com/t5/Notebook-Operating-System-and-Recovery/Does-removing-the-laptop-battery-over-time-erase-the-BIOS/td-p/8900277> — 部分 HP 机器无独立 CMOS 电池

**KDK**

- <https://github.com/dortania/KdkSupportPkg/releases/tag/25G83> — KDK 25G83 镜像与 SHA-256
- <https://developer.apple.com/documentation/apple-silicon/debugging-a-custom-kernel-extension> — Apple KDK / lldb / `kdp-remote` 官方说明
- <https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/tools/lldbmacros/core/kernelcore.py> — `kernelcore` LLDB 模块
