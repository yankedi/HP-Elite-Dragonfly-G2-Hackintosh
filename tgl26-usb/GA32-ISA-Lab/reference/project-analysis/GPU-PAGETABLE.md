# GPU 页表与地址翻译审计（任务 D）

## 输入寄存器与组合

- `regs[2]/regs[3]` = RCS PDP0 低/高（0x2270/0x2274）。GA3.2b：低=0xF23E6000，高=0x00000003。
- `capture()`（kern_tglhang.hpp:486-487）组合：`pml4 = (pdHi << 32) | (pdLo & 0xFFFFF000)`
  = **0x3F23E6000**（与用户给出的候选值一致；先由源码重建，未做假设）。
- `BB_ADDR = (bbHi & 0xFFFF) << 32 | bbLo` → 0x40B75ED8（记录 0）/ 0x426FE104（记录 1）。
- PDP0 低 dword 的低 12 位为描述符标志，代码只取 [31:12] — 与 Gen 系 PDP 描述符格式一致。

## 四级遍历（translate()，kern_tglhang.hpp:317-361）

- 掩码 `AddrMask = 0x000FFFFFFFFFF000`（52 位物理地址）；
- 每级读 8 字节 PTE（entry），present 位 = bit0；
- 大页：level 1（2MiB）/level 2（1GiB）当 bit7 (PS) 置位，掩码后拼页内偏移；
- 叶子页在读取前先经 `allowed()`（分类器 + fences），**页表页与数据页同样过门禁**；
- 溢出：`fetch()` 检查 `physical + length < physical`；`toPpnum()` 保证 32 位页号与 16TiB 上界。

## GA3.2b 实测证据（强）

- 记录 1：12 次翻译全部成功；batchPhys[] 8 页与 kernelPhys[2]=0x3E9026000 都是
  **15.6–15.8 GiB 的正常 RAM**，全部通过 `pmap_valid_page` 与 fences；
- 说明 PDP0→PML4 解释、52 位掩码、4KiB 遍历、present 位判断在本机 25G83 上全部正确；
- 记录 1 的 SBA/VS/PS 指针与 kernel 偏移（0x3C0/0x40）自洽，翻译结果被后续读取验证。

## 记录 0 的拒绝（细节未知）

- 4 次入口读取成功（32B）后，**叶子页** `allowed()` 失败；
- 失败点在 `translate()` 末尾（4KiB 分支 kern_tglhang.hpp:342-346）或大页分支（:334-337）；
- 现有记录无法给出被拒页地址与门名 → GA3.3 诊断（见 THAG-FORMAT.md v3 字段）。

## 未决问题

- 被拒页是否确为 stolen/不可用区（假设：占位页/已释放映射）——GA3.3 一次运行即可回答；
- GPU 页表页是否可能位于非 pmap 管理区（如 stolen）——记录 1 未出现；若出现，
  安全逻辑会拒绝（正确），GA3.3 同样会标明来源。
