# TrackB 有界预算与验证记录

- 目标：GA36 TrackB bounded target-path analysis；只写 `GA36/track-b/`。
- 输入：GA35 sealed accurate25G83 indices、`analysis/expanded/*.all.json.gz`、`analysis/cache-fixups.json`、rawKC；未修改 GA35。
- 函数预算：`24/24`，达到上限；只按已有 symbol entry 提取，未重 disassemble、未全量生成新 corpus。
- bounded-xref：`1` 次，仅过滤操作数 `+0x11c0/+0x11c1/+0x11c2/+0x11c3/+0xdf8/+0x1468`；记录 `423` 条跨五映像命中（ICL 330、Framebuffer 3、IOAccelerator 88、IOGPU 2、IOGraphics 0）。同数值偏移不自动归因。
- 选定 24 函数：SafeForceWake 三变体、populateAccelConfig、start/stop/free/setPowerState/systemWillSleep、df8 init/clean、三 PowerWell、两 IOGraphics PM、hardwareErrorEvent、resetGraphicsEngine/doSchedulerReset/doHangAnalysis、begin/endReset、processGPUReset、FIFO restart。
- 每个函数保留：entry/end、KC fileoff、VA、image UUID、source SHA、raw bytes/raw SHA、basic-block starts、有限 callers、field/lock fragments。
- 独立检查：`analysis/verify_track_b.py` 只读 GA35 rawKC，验证整文件 SHA、24 个 selected slice bytes/SHA、fragment instruction bytes、source UUID/SHA；失败即退出非零。
- 安全限制：无 SSH、硬件、MMIO、deploy、images、EFI、hook；没有证明 actual-hardware-safe point，最终为 `BLOCKED`。
- 最小剩余缺口：live instruction/receiver 认证；flags bit11/12/df8/1468 的运行时对象来源；PM active-power token；ACK 后置条件；reset/clear 全局排他与 fault epoch/latch；CEC4/CEB8/CEBC 真实语义和采样授权。
