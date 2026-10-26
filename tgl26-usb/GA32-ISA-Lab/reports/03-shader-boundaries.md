# 03 · Shader 边界（实际 IGA 输出）

依据固定 IGA `c36a504a4e6c68030c3302646aa396b8b59b22cb`，命令与 stdout/stderr 在 `logs/`；运行 `python3 tools/isa_analyze.py` 可重建。

| 入口 | ICL 完整直线程序 | 指令 | compact/native | EOT 指令相对位置 | 结束 GPU VA（exclusive） |
|---|---:|---:|---:|---:|---|
| PS0 `0x4271D040` | **152 B / 0x98** | 11 | 3 / 8 | `+0x88` sendsc render-target write | `0x4271D0D8` |
| VS `0x4271D3C0` | **288 B / 0x120** | 24 | 12 / 12 | `+0x110` sends URB write | `0x4271D4E0` |
| PS KP1 `0x4271D200` | **440 B / 0x1B8** | 29 | 3 / 26 | `+0x1A8` SEND EOT | `0x4271D3B8` |
| PS KP2 `0x4271D100` | **216 B / 0xD8** | 15 | 3 / 12 | `+0xC8` SEND EOT | `0x4271D1D8` |

四个程序在 ICL 下边界内全解码、无分支，末条 SEND 无 predicate 且 EOT。`isa-diff.json` 与 `ps-variants.json` 保存CFG；生成器显式拒绝branch/带predicate EOT，分别记录 `predicated_instruction_offsets` 与 `write_enabled_instruction_offsets`（W写使能不是predicate）。这里的“完整”只指**这些命令中指定入口至EOT**，不证明 hung draw 已执行到它们或覆盖完整提交历史。

PS 的旧 896 B 切片并非一个程序：第一个 EOT 后存在零填充，继续线性解码造成错位，再后面有其他非零程序。不能把 padding 的 illegal 当作 PS0 内部非法，也不能以 VS 的下一入口或末尾非零认定 PS0 长度。旧 VS 288 B 候选恰与 EOT 结束重合，本次由解码确认而非沿用猜测。

PS 第一条：native 16B、`(W) mad (8|M0) acc0.0<1>:nf r4.3<0;0>:f r2.0<8;1>:f r4.0<0>:f`，无 predicate / flag modifier / SEND / EOT；Gen11 没有 Gen12 SWSB 字段。VS 第一条：compact 8B、`mul (8|M0) acc0.0<1>:f r2.0<0;1,0>:f r4.0<8;8,1>:f`，无 predicate/flag modifier/EOT。详细 operand 类型、region、execution、SEND descriptor、option 位均保存在逐指令 JSON（不是只打印 mnemonic）。

**整合补充**：捕获PS包的8/16/32 dispatch enable均为1、PS_EXTRA Pixel Shader Valid=1，故已补充KP1/KP2。三个PS共808B/55条；原896B候选包含三入口程序及88B间隙。相应额外四份ASM在 `analysis/ps-kp{1,2}-{icl,tgl}.asm`。

**仍未知**：command state是否在hang时真实生效；未捕获thread payload、完整state heap或执行轨迹。Gen12命令长度也有不一致，见report12。没有真实硬件执行验证。
