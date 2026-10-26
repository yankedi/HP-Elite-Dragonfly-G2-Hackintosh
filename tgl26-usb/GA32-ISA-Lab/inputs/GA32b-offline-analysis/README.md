# GA3.2b 原始 THAG v2 离线分析（独立复核）

输入文件：`tgl-hang-GA32b-crash-20261018.bin`

- SHA-256：`1622ecc2aecdcc85ae45dcf86e4219338f6e41e0243b27d5e7128a9999f13333`
- 文件长度：99,648 bytes = 2 × 49,824 bytes (`0xC2A0`)
- 记录 0：`result=12` (`UnsafePhysicalRange`), 页表项读 4 次 / 数据页读 0 次，Batch/VS/PS 均没有捕获。
- 记录 1：`result=0` (`Ok`), 页表项读 48 次 / 数据页读 12 次；总读取 49,536 bytes；Batch 32,768B，VS 8,192B，PS 8,192B。`resolveDiag=0xF`。
- **记录 1 两份 VS/PS 窗口逐字节相同**，均为从 GPU 虚拟地址 `0x4271D000` 开始的 8 KiB 区域；不代表两段 Shader 相同。

## 已确认的 GPU VA 及指针关系

- RCS PDP0/PML4 候选根：`0x3F23E6000`
- Batch 起点：`0x426F7000`
- BB_ADDR：`0x426FE104` = Batch 起点 + `0x7104`
- `STATE_BASE_ADDRESS` 指令位于 Batch + `0x69F8`；头 `0x61010014`，长度编码为 22 dword。
- `3DSTATE_PS` 在 +`0x6B6C`；头 `0x7820000A`，12 dword。
- `3DSTATE_VS` 在 +`0x6C00`；头 `0x78100007`，9 dword。
- SBA 的 Instruction Base：`0x4271D000`。
- PS Kernel Start Pointer `+0x40` → GPU VA `0x4271D040`。
- VS Kernel Start Pointer `+0x3C0` → GPU VA `0x4271D3C0`。
- VS、PS 两个地址均映射到物理页 `0x3E9026000`，页内相差 `0x380`。
- Batch 中非零字节从捕获窗口 `+0x6000` 开始，到 `+0x7103` 结束（**不能因此推定所有零填充都是实际执行流或完整命令边界**）。

## 原始 EU 字节（从入口开始的 16 bytes）

- PS `0x4271D040`: `5b 00 60 00 1c c0 00 20 01 46 20 07 04 04 00 01`
- VS `0x4271D3C0`: `41 2b 02 20 e0 20 02 04 41 4b 16 20 e0 76 02 04`

首个 PS dword `0x0060005B` 的 bit29 未设置；首个 VS dword `0x20022B41` 的 bit29 已设置，符合 Intel EU 指令可能有非紧凑/紧凑混合编码的特征，**这不是完整的语义反汇编，也不独立证明它们有效或 ISA 不兼容**。

## 提取的文件

- `batch-8pages.bin`: GPU Batch 的 32 KiB 捕获窗口，不代表完整命令流。
- `shared-eu-window-2pages.bin`: 8 KiB 原始 EU 窗口，包含两入口。**VS 和 PS 的原始捕获区域与此文件相同**。
- `ps-from-entry-to-next-entry-candidate.bin`: `[0x40, 0x3C0)`，只是下一已知入口之前的候选片段（896B），不是已证实 PS 程序长度。
- `vs-from-entry-to-last-nonzero-candidate.bin`: `[0x3C0, 0x4E0)`，只是末尾非零 16-byte 对齐的候选片段（288B），不是已证实 VS 程序长度。
- `extraction.json`: 原始文件哈希、地址、命令、切片 SHA-256。
- `extract_ga32b.py`: 可重复执行的严格 v2 提取脚本；不会写源文件。

## 推荐的下一步（只离线）

1. 优先使用 **Intel IGA 或 Mesa Intel EU disassembler**，分别将候选入口字节以 Ice Lake (ICL/Gen11) 与 Tiger Lake (TGL/Gen12) 模式反汇编。每个版本记录工具提交、平台、输出、无效指令数和成功到达 EOT 的证据。
2. 解码混合 8/16-byte compact / noncompact 指令，**不可按固定 16 字节切割**，不要以非零 byte 数判断指令长度。
3. 按 Batch 起始 VA 验证 `STATE_BASE_ADDRESS`、`3DSTATE_PS`、`3DSTATE_VS` 的参数布局和 kernel pointer，结合前后命令状态，验证是否是驱动实际执行的着色器。
4. 将真实指令对照 Gen11→Gen12 编码差异，不要仅凭 `0x5B/0x41` 等头字节断言具体操作码错误；建立具体的 `offset, ICL mnemonic, TGL mnemonic, reason` 对照表。
5. 目前不建议先做 GA3.3b 实机实验：Record 1 已提供一个成功捕获，Record 0 的安全拒绝来源仍未知，但不足以阻塞已有数据的离线研究。

## 数据安全

这些二进制来源于 GPU 映射物理内存，可能包含用户或进程私有数据。请只在授权的私有工作环境中分析；不要提交到公开仓库或用于公开问题单附件。
