# 06 管线状态解码（SBA / 3DSTATE_VS / 3DSTATE_PS）

本文件覆盖 Task 9 的管线状态字段：对 GA3.2b record 1 batch 窗口内三个锚点指令
（`STATE_BASE_ADDRESS` @0x69F8、`3DSTATE_PS` @0x6B6C、`3DSTATE_VS` @0x6C00）
按 pinned Mesa 23.3.6 `gen11.xml` / `gen12.xml` **逐字段**解码。
数据源 `analysis/batch-decoded.json`，由 `tools/batch_decode.py` 生成（只读）。

- 三个指令都完整落在窗口内，`declared_length == xml_length`，无字段为"缺失"；
- 若某字段超出声明长度或在窗口之外，`present=false` 且显式标 `unknown`（本次未发生）；
- 组（group）字段不属于本三指令，无动态/结构体组。

## 1. 位域与对齐语义（独立核对）

| 字段 | XML start:end | 类型 | 对齐 `start % 32` | 解码含义 |
|---|---|---|---|---|
| `STATE_BASE_ADDRESS.Instruction Base Address` | 332:383 | address | 12 | `byte_addr = raw << 12` |
| `3DSTATE_VS.Kernel Start Pointer` | 38:95 | offset | 6 | `byte_off = raw << 6`；绝对 = Instruction Base + byte_off |
| `3DSTATE_PS.Kernel Start Pointer 0` | 38:95 | offset | 6 | 同上 |

`gen11` 与 `gen12` 解析后的字段签名（name/start/end/type/default）**完全一致**：
`xml_verification.anchor_field_differences` 三者均 `identical=true`，长度分别 22/9/12。
（gen12 有 151 条指令 vs gen11 142 条；但对本三指令无覆写，因此位域相同。）

### 派生的 kernel 指针

| 指令 | 字段 | raw | 字节偏移 | 绝对 VA（= Instruction Base + 偏移） |
|---|---|---|---|---|
| 3DSTATE_VS | Kernel Start Pointer | 0xF | 0x3C0 | 0x4271D3C0 |
| 3DSTATE_PS | Kernel Start Pointer 0 | 0x1 | 0x40 | 0x4271D040 |
| 3DSTATE_PS | Kernel Start Pointer 1 | 0x8 | 0x200 | 0x4271D200 |
| 3DSTATE_PS | Kernel Start Pointer 2 | 0x4 | 0x100 | 0x4271D100 |

`Instruction Base Address = 0x4271D000`（SBA 字段 332:383）。指针的绝对化只是按 XML 的
`offset` 语义推导；**不是**执行证据，也不独立证明这些 shader 被 dispatch。

## 2. STATE_BASE_ADDRESS @0x69F8（总长 22 dword）

| field | start:end | type | raw | decoded |
|---|---|---|---|---|
| DWord Length | 0:7 | uint | 0x14 | 20 |
| 3D Command Sub Opcode | 16:23 | uint | 0x1 | 1 |
| 3D Command Opcode | 24:26 | uint | 0x1 | 1 |
| Command SubType | 27:28 | uint | 0x0 | 0 |
| Command Type | 29:31 | uint | 0x3 | 3 |
| General State Base Address Modify Enable | 32:32 | bool | 0x1 | True |
| General State MOCS | 36:42 | uint | 0x70 | 112 |
| General State Base Address | 44:95 | address | 0x4271d | 0x4271D000 |
| Stateless Data Port Access MOCS | 112:118 | uint | 0x6e | 110 |
| Surface State Base Address Modify Enable | 128:128 | bool | 0x1 | True |
| Surface State MOCS | 132:138 | uint | 0x70 | 112 |
| Surface State Base Address | 140:191 | address | 0x4289d | 0x4289D000 |
| Dynamic State Base Address Modify Enable | 192:192 | bool | 0x1 | True |
| Dynamic State MOCS | 196:202 | uint | 0x70 | 112 |
| Dynamic State Base Address | 204:255 | address | 0x4291d | 0x4291D000 |
| Indirect Object Base Address Modify Enable | 256:256 | bool | 0x0 | False |
| Indirect Object MOCS | 260:266 | uint | 0x0 | 0 |
| Indirect Object Base Address | 268:319 | address | 0x0 | 0x0 |
| Instruction Base Address Modify Enable | 320:320 | bool | 0x1 | True |
| Instruction MOCS | 324:330 | uint | 0x46 | 70 |
| Instruction Base Address | 332:383 | address | 0x4271d | 0x4271D000 |
| General State Buffer Size Modify Enable | 384:384 | bool | 0x1 | True |
| General State Buffer Size | 396:415 | uint | 0x180 | 384 |
| Dynamic State Buffer Size Modify Enable | 416:416 | bool | 0x1 | True |
| Dynamic State Buffer Size | 428:447 | uint | 0x50 | 80 |
| Indirect Object Buffer Size Modify Enable | 448:448 | bool | 0x1 | True |
| Indirect Object Buffer Size | 460:479 | uint | 0xfffff | 1048575 |
| Instruction Buffer size Modify Enable | 480:480 | bool | 0x1 | True |
| Instruction Buffer Size | 492:511 | uint | 0x180 | 384 |
| Bindless Surface State Base Address Modify Enable | 512:512 | bool | 0x1 | True |
| Bindless Surface State MOCS | 516:522 | uint | 0x48 | 72 |
| Bindless Surface State Base Address | 524:575 | address | 0x4296d | 0x4296D000 |
| Bindless Surface State Size | 588:607 | uint | 0x7ff | 2047 |
| Bindless Sampler State Base Address Modify Enable | 608:608 | bool | 0x0 | False |
| Bindless Sampler State MOCS | 612:618 | uint | 0x0 | 0 |
| Bindless Sampler State Base Address | 620:671 | address | 0x0 | 0x0 |
| Bindless Sampler State Buffer Size | 684:703 | uint | 0x0 | 0 |

说明：`Buffer Size` 字段单位未在 XML 中给出 scale，本表仅保留原始整数值，不做单位换算。
`Indirect Object Base Address` 与 `Bindless Sampler State Base Address` 的命令位域为 present-and-zero，
但Modify Enable=0，**实际GPU base继承此前状态，当前捕获内未知**，不能把命令字段0写作已生效零base。

## 3. 3DSTATE_VS @0x6C00（总长 9 dword）

| field | start:end | type | raw | decoded |
|---|---|---|---|---|
| DWord Length | 0:7 | uint | 0x7 | 7 |
| 3D Command Sub Opcode | 16:23 | uint | 0x10 | 16 |
| 3D Command Opcode | 24:26 | uint | 0x0 | 0 |
| Command SubType | 27:28 | uint | 0x3 | 3 |
| Command Type | 29:31 | uint | 0x3 | 3 |
| Kernel Start Pointer | 38:95 | offset | 0xf | 0x3C0 → VA 0x4271D3C0 |
| Software Exception Enable | 103:103 | bool | 0x0 | False |
| Accesses UAV | 108:108 | bool | 0x0 | False |
| Illegal Opcode Exception Enable | 109:109 | bool | 0x0 | False |
| Floating Point Mode | 112:112 | uint | 0x0 | 0 |
| Thread Dispatch Priority | 113:113 | uint | 0x0 | 0 |
| Binding Table Entry Count | 114:121 | uint | 0x0 | 0 |
| Sampler Count | 123:125 | uint | 0x0 | 0 |
| Vector Mask Enable | 126:126 | bool | 0x0 | False |
| Per-Thread Scratch Space | 128:131 | uint | 0x0 | 0 |
| Scratch Space Base Pointer | 138:191 | address | 0x0 | 0x0 |
| Vertex URB Entry Read Offset | 196:201 | uint | 0x0 | 0 |
| Vertex URB Entry Read Length | 203:208 | uint | 0x1 | 1 |
| Dispatch GRF Start Register For URB Data | 212:216 | uint | 0x2 | 2 |
| Enable | 224:224 | bool | 0x1 | True |
| Vertex Cache Disable | 225:225 | bool | 0x0 | False |
| SIMD8 Dispatch Enable | 226:226 | bool | 0x1 | True |
| SIMD8 Single Instance Dispatch Enable | 233:233 | bool | 0x0 | False |
| Statistics Enable | 234:234 | bool | 0x1 | True |
| Maximum Number of Threads | 246:255 | uint | 0x16b | 363 |
| User Clip Distance Cull Test Enable Bitmask | 256:263 | uint | 0x0 | 0 |
| User Clip Distance Clip Test Enable Bitmask | 264:271 | uint | 0x0 | 0 |
| Vertex URB Entry Output Length | 272:276 | uint | 0x1 | 1 |
| Vertex URB Entry Output Read Offset | 277:282 | uint | 0x1 | 1 |

关键位：`Enable=1`、`SIMD8 Dispatch Enable=1`、`Statistics Enable=1`、
`Binding Table Entry Count=0`、`Sampler Count=0`。这些是命令字段值，不代表硬件状态已生效。

## 4. 3DSTATE_PS @0x6B6C（总长 12 dword）

| field | start:end | type | raw | decoded |
|---|---|---|---|---|
| DWord Length | 0:7 | uint | 0xa | 10 |
| 3D Command Sub Opcode | 16:23 | uint | 0x20 | 32 |
| 3D Command Opcode | 24:26 | uint | 0x0 | 0 |
| Command SubType | 27:28 | uint | 0x3 | 3 |
| Command Type | 29:31 | uint | 0x3 | 3 |
| Kernel Start Pointer 0 | 38:95 | offset | 0x1 | 0x40 → VA 0x4271D040 |
| Software Exception Enable | 103:103 | bool | 0x0 | False |
| Mask Stack Exception Enable | 107:107 | bool | 0x0 | False |
| Illegal Opcode Exception Enable | 109:109 | bool | 0x0 | False |
| Rounding Mode | 110:111 | uint | 0x0 | 0 (RTNE) |
| Floating Point Mode | 112:112 | uint | 0x0 | 0 (IEEE-754) |
| Thread Dispatch Priority | 113:113 | uint | 0x0 | 0 |
| Binding Table Entry Count | 114:121 | uint | 0x0 | 0 |
| Single Precision Denormal Mode | 122:122 | uint | 0x0 | 0 (Flushed to Zero) |
| Sampler Count | 123:125 | uint | 0x0 | 0 (No Samplers) |
| Vector Mask Enable | 126:126 | bool | 0x0 | False |
| Single Program Flow | 127:127 | bool | 0x0 | False |
| Per Thread Scratch Space | 128:131 | uint | 0x0 | 0 |
| Scratch Space Base Pointer | 138:191 | address | 0x0 | 0x0 |
| 8 Pixel Dispatch Enable | 192:192 | bool | 0x1 | True |
| 16 Pixel Dispatch Enable | 193:193 | bool | 0x1 | True |
| 32 Pixel Dispatch Enable | 194:194 | bool | 0x1 | True |
| Position XY Offset Select | 195:196 | uint | 0x0 | 0 (POSOFFSET_NONE) |
| Render Target Resolve Type | 198:199 | uint | 0x0 | 0 (RESOLVE_DISABLED) |
| Render Target Fast Clear Enable | 200:200 | bool | 0x0 | False |
| Push Constant Enable | 203:203 | bool | 0x0 | False |
| Maximum Number of Threads Per PSD | 215:223 | uint | 0x3f | 63 |
| Dispatch GRF Start Register For Constant/Setup Data 2 | 224:230 | uint | 0x6 | 6 |
| Dispatch GRF Start Register For Constant/Setup Data 1 | 232:238 | uint | 0xb | 11 |
| Dispatch GRF Start Register For Constant/Setup Data 0 | 240:246 | uint | 0x4 | 4 |
| Kernel Start Pointer 1 | 262:319 | offset | 0x8 | 0x200 → VA 0x4271D200 |
| Kernel Start Pointer 2 | 326:383 | offset | 0x4 | 0x100 → VA 0x4271D100 |

关键位：三个 `Pixel Dispatch Enable` 全为 1，`Maximum Number of Threads Per PSD=63`，
`Maximum Number of Threads`（VS）=363。`Kernel Start Pointer 1/2` 存在且非零，
这两个非零入口已在整合时补充真实解码：KP1 440B/29条，KP2 216B/15条，均至EOT，见 `analysis/ps-variants.json`。

## 5. 缺失与未知

- 本次三指令均在窗口内且长度自洽，**没有**字段 `present=false`；不存在"缺失但被省略"的情况。
- 若将来锚点落在窗口外或声明的 DWordLength 小于 XML 固定长度，解码器会显式给出
  `status=no_valid_instruction` / `missing`，而不是补零或猜测。
- 组字段：本三指令无 group；链上其它指令的动态组已在报告 05 说明。

## 6. 与其它证据的边界

- 物理映射 `0x3E9026000`（record 1 的 `kernelPhys`）来自采集元数据；本分析**没有**独立 PTE log，
  因此不当作已验证映射，也未用于本文件的任何推导。
- 本文件字段值只说明"捕获窗口里这条命令的位域是什么"；
  不证明该命令生效、不证明 shader 运行、不证明 GPU 状态。
- 复现：`python3 tools/batch_decode.py --json analysis/batch-decoded.json`（默认读取 raw THAG、record 1）。

## 7. 四个draw的最小状态快照与跨代格式约束

`python3 tools/pipeline_reconstruct.py`生成 `analysis/pipeline-snapshots.json` / `pipeline-summary.md`：
覆盖四个draw与22类必要状态（全部可解简单字段、未支持组及raw均保留）。PIPELINE_SELECT=3D，PS_EXTRA Pixel Shader Valid=1，
VS Enable/SIMD8=1；SF/CLIP/WM、URB、push/constants、binding/sampler指针有记录。
实际surface/sampler/constant heap内容没有捕获；动态/struct组未知，不伪造。Gen12 stencil长度及draw扩展flag不一致见报告12，
因此“同一Gen11声明长度链”不等于已验证正确的TGL pipeline。
