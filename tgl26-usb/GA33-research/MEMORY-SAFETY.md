# 物理内存安全审计（任务 D/E/F）

## 1. Host Bridge（任务 E）

`readHostBridge()`（kern_igfx.cpp:1313）匹配 `vendor-id=0x8086, device-id=0x9A14`（TGL host bridge），
读 config 0xBC/0xB8/0xB0/0xB4 → TOLUD/TSEGMB/BDSM/BGSM。GA3.2b 实测：

| 寄存器 | 原始值 | 掩码后（bits31:20） | 含义 |
|---|---|---|---|
| TOLUD | 0x50800001 | 0x50800000 (1288MB) | 低端 DRAM 顶端 |
| TSEGMB | 0x44000001 | 0x44000000 (1088MB) | TSEG/SMRAM 基址 |
| BDSM | 0x48800001 | 0x48800000 (1160MB) | data stolen 基址 |
| BGSM | 0x48000001 | 0x48000000 (1152MB) | GTT stolen 基址 |

一致性核对：DSMBASE（MMIO 0x1080C0/C4）= 0x48800001 → 与 BDSM 相同；
GGC=0x4C1 → GMS=4 → 128MB（与 BIOS DVMT 128MB 一致）；stolen=[0x48800000,0x50800000)
与 TOLUD 对齐。**寄存器解读自洽**，`fencesAllow()` 的掩码/单位与 Intel 语义一致。

`deriveFences`（kern_tglhang.hpp:255-317）：firmware floor = min(BDSM,BGSM,TSEGMB) = TSEGMB
→ 实际拒绝 **[1088MB, 1288MB)**（含 TSEG/SMRAM/stolen 全部）；另有 maxMem 上界与 4G 交界检查。
Host Bridge 只用于**额外拒绝**，从不用于批准（与任务要求一致）。

## 2. pmap_valid_page（任务 F）

- 签名：`boolean_t pmap_valid_page(ppnum_t)`；`ppnum_t = uint32_t`（本机 MacKernelSDK
  `mach/vm_types.h:68`），机器码在 25G83 KC 上逐指令验证过（GA3.1 审计，T 0xffffff80004c8650）。
- `pmap_memory_regions[]` 由 `i386_vm_init` 从 EFI memory map 构建，仅收录非 runtime 的
  conventional/loader/boot-services 区；**page 0 被显式移除**（xnu i386_vm_init.c:470-478）
  → 探针 `pmap_valid_page(0)==false` 成立（GA3.2b resolveDiag bit2=1 实测）。
- GA3.2b 记录 1 的全部 GPU 页面（15.6–15.8 GiB 物理）通过分类器 → 分类器对真实 IOKit
  物理分配工作正常。GPU 页表页与数据页都走同一门禁（`Reader::fetch` 对入口读取同样调用
  `allow()`，kern_tglhang.hpp:187-215）。
- 未证明安全的页面一律拒绝（fail closed）；**禁止**用禁用分类器的方式解决拒绝问题。

## 3. GA3.2b 拒绝归因（记录 0）

被拒页物理地址未记录；可能来源：pmap 分类失败（页不在 usable RAM 区，例如被释放后指向
stolen 里的占位页——参考项目 GA10 曾因读 GPU 占位页触发 machine check）或 fences 命中
（[1088,1288)MB 或 maxMem/4G 边界）。两者都是**正确拒绝**；GA3.3 记录
`failPhys/failGpuVA/failLevel/pmapRejected/fenceRejected` 后即可区分。

## 4. 安全不变量（GA3.3 保持）

- 分类器缺失/探针失败 → `MemoryMapUnverified`，零读取；
- stolen/TOLUD/TSEG/firmware floor/maxMem/16TiB 检查原样保留；
- 逐页检查、超时上限（采集 3 次、96KB、128 页表读）、失败即停；
- hook 内无文件 I/O；写出在 thread call；
- 不新增任何物理访问路径，不绕过任何门禁。
