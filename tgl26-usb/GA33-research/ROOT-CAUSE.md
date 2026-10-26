# GA3.2b 根因报告（任务 B/C）

## 记录 0：第一个数据页被安全门禁拒绝（预期行为）

| 字段 | 值 |
|---|---|
| result | `UnsafePhysicalRange`（枚举 12，kern_tglhang.hpp:84） |
| attempts / wakeDomain | 1 / 7（渲染 forcewake 窗口，GA3.2 起记录） |
| resolveDiag | 0xF（maxMem/pmap/probe/uio_free 全部成功；GA3.3 前无 lastError） |
| classifierReady / probeOk | 1 / 1 |
| exclusionsVerified | 1（stolen=1, lowTop=1, tseg=1） |
| bridgeRegs | TOLUD=0x50800001, TSEGMB=0x44000001, BDSM=0x48800001, BGSM=0x48000001 |
| bbAddr / pml4 / batchStart | 0x40B75ED8 / 0x3F23E6000 / 0x40B6E000 |
| tableReads / pageReads / readBytes | 4 / 0 / 32 |
| payload | 0 / 0 / 0 |

**执行路径**（源码行号针对 GA3.2 树）：

1. `wrapDoHangAnalysis`（kern_igfx.cpp:1422）进入分析，`wrapSafeForceWake`（:1457）在 `domain==7` 的
   forcewake 窗口内调用 `hangCapture`（:1363）。
2. `hangCapture` 填 `in.classifierReady = pmapValidPage != nullptr`（:1404）等输入，调用
   `TglHang::capture()`。
3. `capture()` 第 0 级门禁全部通过：`kern_tglhang.hpp:463-477`。
4. 第 1 级寄存器通过：`bbAddr=0x40B75ED8`，`pml4=0x3F23E6000`（`kern_tglhang.hpp:480-491`）。
5. 第 3 级 batch 循环：`translate()`（kern_tglhang.hpp:317）对 `batchStart=0x40B6E000` 走 PML4→PDP→PD→PT
   四级页表：**4 次入口读取全部成功**（readBytes=32）。
6. 叶子页 `allowed(page, PageSize)`（kern_tglhang.hpp:342-346）返回值 `false`
   → `reader.reason = UnsafePhysicalRange`，capture 以该原因返回。
   `allowed()` → kext `hangPageAllowed()`（kern_igfx.cpp:1297）：先 `fencesAllow()`（:1305），
   再逐页 `toPpnum()` + `pmap_valid_page()`（:1311-1313）。

**结论**：拒绝由 `hangPageAllowed` 的两个门之一触发：**额外 fences** 或 **pmap_valid_page**。
现有 THAG 数据无法区分是哪一个（缺少被拒物理页与门名），也无法判断该页是否真的是不可读区域。
两种情形下拒绝本身都符合设计（fail closed）。

## 记录 1：完整成功

| 字段 | 值 |
|---|---|
| result | `Ok` |
| bbAddr / pml4 / batchStart | 0x426FE104 / 0x3F23E6000 / 0x426F7000 |
| batchPhys[8] | 0x3E8431000, 0x3E8430000, 0x3E786F000, 0x3E786E000, 0x3E786D000, 0x3E786C000, 0x3F1356000, 0x3F2CC8000 |
| tableReads/pageReads/readBytes | 48 / 12 / 49,536（12 翻译 × 4 入口 + 12 数据页） |
| scan | SBA @0x426FD9F8；instructionBase=0x4271D000；VS @+0x3C0；PS @+0x40 |
| kernelPhys / kernelPages | 0x3E9026000 / [2,2] |
| payload | Batch 32,768/706 非零；VS 8,192/791；PS 8,192/791 |

所有 batch 物理页（15.6–15.8 GiB）都通过了分类器与 fences —— 说明分类器对真实 GPU 缓冲区工作正常。

## 任务 C 统计（GA3.2b）

| 指标 | 记录 0 | 记录 1 |
|---|---|---|
| Batch 有效/非零字节 | 0 / 0 | 32,768 / 706 |
| VS 有效/非零字节 | 0 / 0 | 8,192 / 791 |
| PS 有效/非零字节 | 0 / 0 | 8,192 / 791 |
| 页表翻译成功（入口读取/4） | 1（4 次） | 12（48 次） |
| 页表翻译失败 | 1（首次数据页前中止） | 0 |
| 物理读取失败 | 0（从未尝试） | 0（12 次全部成功） |
| Batch 命令头 | 无数据 | STATE_BASE_ADDRESS、3DSTATE_VS、3DSTATE_PS |

> 注：`tableReads` 只统计**成功**的入口读取；失败在第一次即中止，未计数（GA3.3 增加
> `readAttempts/readSuccesses` 与 `pmapChecked/Accepted/Rejected`、`fenceRejected`）。

## 待 GA3.3 回答的最小数据集合

- `failPhys`（被拒物理页）、`failGpuVA`、`failLevel`、`failTable`；
- `pmapRejected` vs `fenceRejected`（拒绝来源）；
- `readAttempts/readSuccesses`（真实 IOMemoryDescriptor 读尝试数）；
- `recordVersion/recordSize`（解析器可辨识版本）。
