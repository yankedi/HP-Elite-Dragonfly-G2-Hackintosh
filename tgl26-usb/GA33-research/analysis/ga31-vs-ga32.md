# GA3.1b vs GA3.2b THAG 对比

| | GA3.1b | GA3.2b |
|---|---|---|
| 文件 | `tgl-hang-GA31b-20261018.bin` | `tgl-hang-GA32b-crash-20261018.bin` |
| SHA-256 | `5ed3283a76178eee…` | `1622ecc2aecdcc85…` |
| 记录数 | 2 | 2 |

## 记录 0

| 字段 | GA3.1b | GA3.2b |
|---|---|---|
| 记录模式 | GA3.1 | GA3.2 |
| ms | 58653 | 51278 |
| wakeDomain | 0 | 7 |
| resolveDiag/pad | 0x0 | 0xF |
| result | MemoryMapUnverified | UnsafePhysicalRange |
| classifierReady | 0 | 1 |
| exclusionsVerified | 0 | 1 |
| bbAddr | 0x0 | 0x40B75ED8 |
| pml4 | 0x0 | 0x3F23E6000 |
| batchPages | 0 | 0 |
| tableReads | 0 | 4 |
| pageReads | 0 | 0 |
| readBytes | 0 | 32 |
| Batch 非零 | 0 | 0 |
| VS 非零 | 0 | 0 |
| PS 非零 | 0 | 0 |
| 首次失败 | 0a-classifier | 1..3-first-page |

关键寄存器对比：

| 寄存器 | GA3.1b | GA3.2b |
|---|---|---|
| GFXREG_BATCHBUFF_BB_ADDR | 0x40B75ED8 | 0x40B75ED8 |
| GFXREG_BB_ADDR_UDW | 0x00000000 | 0x00000000 |
| GFXREG_RCS_PDP0_DESCRIPTOR_LO | 0xEEE08000 | 0xF23E6000 |
| GFXREG_RCS_PDP0_DESCRIPTOR_HI | 0x00000003 | 0x00000003 |
| GFXREG_RENDERDEBUG_ACTHD | 0x000000D4 | 0x000000D4 |
| GFXREG_RENDERDEBUG_IPEHR | 0x7A000004 | 0x7A000004 |
| GFXREG_RING_BUFFER_PRB0_HEAD | 0x000000D4 | 0x000000D4 |
| GFXREG_RING_BUFFER_PRB0_TAIL | 0x000000F0 | 0x000000F0 |
| GFXREG_RING_BUFFER_PRB0_START | 0x402DA000 | 0x402DA000 |
| GFXREG_RENDERDEBUG_INSTDONE_1 | 0xFFDFFFFB | 0xFFDFFFFB |
| GFXREG_RCS_GFX_MODE | 0x00000000 | 0x00000000 |
| (no GA2 report name) | 0x80000182 | 0x80000182 |
| GFXREG_RING_BUFFER_CCID | 0x00000080 | 0x00000080 |
| GFXREG_RCS_EXECLIST_STATUS | 0x00002098 | 0x00002098 |
| GFXREG_COMMON_SLICE_INSTDONE_REG | 0xFFFFFFFE | 0xFFFFFFFE |
| GFXREG_CONDITION_EIR | 0x00000004 | 0x00000004 |

## 记录 1

| 字段 | GA3.1b | GA3.2b |
|---|---|---|
| 记录模式 | GA3.1 | GA3.2 |
| ms | 69777 | 62291 |
| wakeDomain | 0 | 7 |
| resolveDiag/pad | 0x0 | 0xF |
| result | MemoryMapUnverified | Ok |
| classifierReady | 0 | 1 |
| exclusionsVerified | 0 | 1 |
| bbAddr | 0x0 | 0x426FE104 |
| pml4 | 0x0 | 0x3F23E6000 |
| batchPages | 0 | 8 |
| tableReads | 0 | 48 |
| pageReads | 0 | 12 |
| readBytes | 0 | 49536 |
| Batch 非零 | 0 | 706 |
| VS 非零 | 0 | 791 |
| PS 非零 | 0 | 791 |
| 首次失败 | 0a-classifier | complete |

关键寄存器对比：

| 寄存器 | GA3.1b | GA3.2b |
|---|---|---|
| GFXREG_BATCHBUFF_BB_ADDR | 0x426FE104 | 0x426FE104 |
| GFXREG_BB_ADDR_UDW | 0x00000000 | 0x00000000 |
| GFXREG_RCS_PDP0_DESCRIPTOR_LO | 0xEEE08000 | 0xF23E6000 |
| GFXREG_RCS_PDP0_DESCRIPTOR_HI | 0x00000003 | 0x00000003 |
| GFXREG_RENDERDEBUG_ACTHD | 0x0000014C | 0x0000014C |
| GFXREG_RENDERDEBUG_IPEHR | 0x7A000004 | 0x7A000004 |
| GFXREG_RING_BUFFER_PRB0_HEAD | 0x0000014C | 0x0000014C |
| GFXREG_RING_BUFFER_PRB0_TAIL | 0x00000168 | 0x00000168 |
| GFXREG_RING_BUFFER_PRB0_START | 0x402BE000 | 0x402BE000 |
| GFXREG_RENDERDEBUG_INSTDONE_1 | 0xFFDFFFFB | 0xFFDFFFFB |
| GFXREG_RCS_GFX_MODE | 0x00000000 | 0x00000000 |
| (no GA2 report name) | 0x80000182 | 0x80000182 |
| GFXREG_RING_BUFFER_CCID | 0x00000080 | 0x00000080 |
| GFXREG_RCS_EXECLIST_STATUS | 0x00014198 | 0x00014198 |
| GFXREG_COMMON_SLICE_INSTDONE_REG | 0xFFFFFFFE | 0xFFFFFFFE |
| GFXREG_CONDITION_EIR | 0x00000000 | 0x00000000 |

## 差异结论

- GA3.1b 两条记录均为 `MemoryMapUnverified`（分类器未解析），零读取。
- GA3.2b 记录 0 为 `UnsafePhysicalRange`（门禁通过后第一个数据页被拒绝）；记录 1 **完整成功**（result=Ok，Batch/VS/PS 均读取）。
- resolveDiag 0x0 → 0xF：_max_mem/_pmap_valid_page/探针/_uio_free 全部就绪（位定义见 THAG-FORMAT.md）。
- BB_ADDR 与 GA3.1b 相同（0x40B75ED8 / 0x426FE104），说明 GPU VA 分配确定；PDP0 物理页不同（0xEEE08000 → 0x3F23E6000 组合 PML4）。
