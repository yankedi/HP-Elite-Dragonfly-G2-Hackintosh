# GA3.9 native：补丁归档（`translator/patches/native/`）

本目录是 GA39 source-copy / native-build 子任务的第二个（且唯一另一个）写入范围。

## `mesa-brw_eu_emit-acc1.patch`

- 来源：认证上游 `holdmysocks/latitude-7320-detachable-hackintosh` @
  `1010490d3421628c9d6fd0bd518b6c4b6f8ee33c` 的
  `WhateverGreen-patches/tgl-xlate/` 构建引导所需补丁（`setup.sh` 应用）。
- SHA-256：`b87de68be436a853237e08f7883d8c1c2439b8e9cf1c4db1dc1cdcfd79e0168f`
- 作用：在 `src/intel/compiler/brw_eu_emit.c` 中把三源目的寄存器断言从
  `dest.nr == BRW_ARF_ACCUMULATOR` 放宽为 `(dest.nr & 0xF0) == BRW_ARF_ACCUMULATOR`
  （Apple 编译器会用 `acc1` 作目的寄存器），并在 `brw_inst_set_3src_a1_dst_reg_file`
  路径前补一段取累加器寄存器文件的处理。
- **这是适配补丁，不是上游 Mesa 行为。**
- 本机独立构建**不重新应用**此补丁：`translator/source/native/adapter/eu/brw_eu_emit.c`
  已是打过补丁的字节（SHA-256 `9dd0b7cd6733719371b135dca1a4bd5bd02a4f4801d76bccd0a464145debb035`），
  直接编译以保证与历史构造字节一致。

## `patch-application-receipt.txt`

对固定 pristine Mesa 源树（`GA32-ISA-Lab/tools/mesa-eu/source`，
`863338275d915e867319c3690ffd3272b06303c3`）以 `patch -p1 --dry-run` 复算：
可干净应用，退出 0，且**未写目标树**（只读目标）。

## 边界

- 未修改 GA31–GA38 任何文件；未改 `translator/strict-policy/`；
- 无硬件/GPU/MMIO/SSH/IMG/EFI/固件/NVRAM/启动项访问；
- 本目录内容仅研究用途（`NOT_FOR_HARDWARE`）。
