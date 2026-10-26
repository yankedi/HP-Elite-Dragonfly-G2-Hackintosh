# THAG 记录格式（v2 = GA3.1/GA3.2，v3 = GA3.3）

## 记录头（两版本相同）

| 偏移 | 字段 | 类型 | 说明 |
|---|---|---|---|
| 0x00 | magic | u32 | 0x47414854 "THAG" |
| 0x04 | index | u32 | 记录序号 |
| 0x08 | ms | u32 | 采集时 uptime（毫秒） |
| 0x0C | attempts | u32 | 本记录内的尝试次数 |
| 0x10 | wakeDomain | u32 | GA3.2 起写入：产生窗口的 forcewake 域（7=渲染） |
| 0x14 | attemptReasons[8] | u32×8 | 每次尝试的结果码 |
| 0x34 | regs[16] | u32×16 | 引擎寄存器快照（顺序见下） |
| 0x74 | ggc | u32 | GGC（GMS 位 15:8） |
| 0x78 | dsmLo / 0x7C dsmHi | u32 | DSMBASE |
| 0x80 | pad（v2 恒 0）/ resolveDiag（GA3.2+） | u32 | 见下 |
| 0x88 | maxMem | u64 | `_max_mem`（上界，仅参考） |
| 0x90 | out | CaptureOutput | 49,680 B |

`sizeof(HangRecord)`：v2 = 49,824 = 0xC2A0；v3 = 49,912 = 0xC2F8（追加 88B 诊断）。
两版本均经 clang `-fdump-record-layouts-complete` 对真实头文件验证
（`layout_dump_ga32.txt`、GA31-hang/analysis/layout_dump.txt）。

## resolveDiag（GA3.2 起）

位掩码（`TglHang::packResolveDiag`）：bit0 `_max_mem`、bit1 `_pmap_valid_page`、
bit2 探针通过（`pmap_valid_page(0)==false`）、bit3 `_uio_free`；bits16-23 最后一次
KernelPatcher 错误码。GA3.2b 两条记录均为 0xF。

## CaptureOutput 关键偏移（相对记录 0x90）

result +0x00；fences +0x08（96B：haveStolen/stolenBase/stolenSize、haveLowTop/lowTop、
haveTseg/tsegBase、haveFirmwareFloor/firmwareFloor、haveMaxMem/maxMem）；
ramTop +0x60；bbAddr +0x68；pml4 +0x70；batchStart +0x78；batchPhys[8] +0x80；
batchValid +0xC0；batchPages +0xC4；tableReads +0xC8；pageReads +0xCC；readBytes +0xD0；
classifierReady +0xD8；classifierProbeOk +0xDC；classifierProbe1 +0xE0；bridgeValid +0xE4；
exclusionStolen/LowTop/Tseg +0xE8/0xEC/0xF0；exclusionsVerified +0xF4；bridgeRegs[4] +0xF8
（TOLUD, TSEGMB, BDSM, BGSM）；scan +0x108（foundSba/Vs/Ps +0x108/109/10A、sbaAt +0x110、
instructionBase +0x118、kernelOffset +0x120、kernelAt +0x130、sbaCmd +0x140、kernelCmd +0x198）；
kernelPhys +0x1F8；kernelPages +0x208；**batch 载荷 +0x210（8×4096）**、
**kernel 载荷 +0x8210（2×2×4096）**（记录内 0x2A0 / 0x82A0 / 0xA2A0）。

## v3 诊断块（记录内 0xC2A0 起，88B）

| 偏移 | 字段 | 说明 |
|---|---|---|
| +0x00 | version | =3 |
| +0x04 | size | sizeof(HangRecord) |
| +0x08 | stage | 最后进入的阶段（1=分类器 2=排除 3=寄存器 4=batch 5=扫描 6=kernel 7=完成） |
| +0x0C | failReason | 首次拒绝的 Reason |
| +0x10 | failLevel | 首次拒绝所在页表级（3..0，0xFF=无） |
| +0x14/18/1C | pmapChecked/Accepted/Rejected | `pmap_valid_page` 调用统计 |
| +0x20 | fenceRejected | 被额外 fences 拒绝的次数 |
| +0x24/28 | readAttempts/readSuccesses | 真实物理读取尝试/成功 |
| +0x2C/30/34 | batchBytes/vsBytes/psBytes | 捕获有效载荷字节 |
| +0x38 | bridgeDiag | bit0 bridge 读取成功、bit1..3 各 fence 已验证、bit4 bridgeValid、bits8-15 bridgeState |
| +0x40/48/50 | failGpuVA/failPhys/failTable | 首次拒绝的 GPU VA / 物理地址 / 所在页表 |

## 记录检测与解析

`analysis/parse_thag.py`（v4）按文件大小与每记录起点魔数自动识别 v2/v3（1..3 条记录），
v3 额外校验 diagnostic version/size 并输出诊断；异常文件（截断、坏魔数、非法条数）明确报错。
GA3.3 之前无版本字段，因此 v2/v3 的判别依靠尺寸；GA3.3 起记录自带版本。
