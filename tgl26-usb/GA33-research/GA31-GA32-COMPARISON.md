# GA3.1b → GA3.2b 对比（含三代 gpuRestart 对照）

## THAG 对比

| 字段 | GA3.1b 记录0 | GA3.1b 记录1 | GA3.2b 记录0 | GA3.2b 记录1 |
|---|---|---|---|---|
| result | MemoryMapUnverified | MemoryMapUnverified | UnsafePhysicalRange | **Ok** |
| resolveDiag/pad | 0x0 | 0x0 | 0xF | 0xF |
| classifierReady | 0 | 0 | 1 | 1 |
| exclusionsVerified | 0 | 0 | 1 | 1 |
| tableReads/pageReads | 0/0 | 0/0 | 4/0 | 48/12 |
| readBytes | 0 | 0 | 32 | 49,536 |
| batch 非零字节 | 0 | 0 | 0 | 706 |
| VS/PS 非零字节 | 0/0 | 0/0 | 0/0 | 791/791 |
| wakeDomain | 0（未写） | 0 | 7 | 7 |

**修复验证**：GA3.2 的初始化顺序修复生效（resolveDiag=0xF），分类器与 fences 全部就绪；
GA3.2b 记录 1 证明整条采集链路（页表遍历、Batch、SBA/VS/PS 扫描、kernel 页读取）工作正常。

## 三代 gpuRestart 寄存器签名

| 会话 | 第 1 起 | 第 2 起 | 第 3 起 | 第 4 起 | PDP0（每启动） |
|---|---|---|---|---|---|
| GA2b (10-17 23:03) | ctx6 BB=0x40b75ed8 | ctx5 0x426fe104 | ctx6 0x435b7520 | ctx5 0x42ace74c | 0x3FDC12000 |
| GA3.1b (10-18 01:53) | ctx6 0x40b75ed8 | ctx5 0x426fe104 | ctx6 0x435b7520 | ctx5 0x42ace74c | 0x3EEE08000 |
| GA3.2b (10-18 04:03) | ctx6 0x40b75ed8 | ctx5 0x426fe104 | ctx6 0x435b8520 | ctx5 0x42ace74c | 0x3F23E6000 |

全部 12 份报告：ACTHD==HEAD（0xD4/0x14C/0x244/0x16C），TAIL 超前 0x1C/0x15C，
START=0x402DA000（ctx6）/0x402BE000（ctx5），**IPEHR=0x7A000004（PIPE_CONTROL）**，
INSTDONE=0xFFDFFFFB（VS、CS 未完成），EIR=4（ctx6 第一起）或 0。
→ 三代 hang 是**同一个执行模式**；GA3.2 没有引入新的挂死形态。

## 捕获覆盖差异

GA3.2b 共 4 起 hang，但 THAG 只有 2 条记录：第一条（ctx6）记录拒绝，第二条（ctx5）成功
→ `hangCaptured=1` 置位后（kern_igfx.cpp:1470）不再采集后续 hang（设计上限行为）。
