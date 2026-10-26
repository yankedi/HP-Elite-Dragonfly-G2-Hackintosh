# GA33-research — GA3.2b 取证与 GA3.3 诊断版（离线）

生成：2026-10-18，全离线（无实机实验、无介质/固件/EFI 修改）。测试机当前停留在 GA32a（未重启）。

## 关键发现（一句话版）

1. **GA3.2b 捕获实际成功了一半**：记录 1（ctx5，BB_ADDR 0x426FE104）是**完整成功的采集**——Batch 32,768B、VS 8,192B、PS 8,192B 有效载荷，扫描定位到 STATE_BASE_ADDRESS / 3DSTATE_VS / 3DSTATE_PS。记录 0（ctx6，BB_ADDR 0x40B75ED8）在**第一个数据页**被安全检查拒绝（`UnsafePhysicalRange`），表格读取成功 4 次（32B）、零物理数据读取。
2. `resolveDiag = 0xF`：`_max_mem`、`_pmap_valid_page`（含探针）、`_uio_free` 全部解析成功——GA3.1b 的顺序缺陷已修复生效。
3. 拒绝发生在**页表遍历成功之后、第一个数据页被分类器/fences 拒绝之时**；现有记录未区分 "pmap 拒绝" 与 "fence 拒绝"，也无法给出被拒物理页——这正是 GA3.3 诊断版要回答的问题。
4. 捕获的 shader kernel 是 **Gen11 机器码**（Mesa Gen11 反汇编器完整解码；Gen12 解码器无法解析），离线翻译（参考项目 g11to12 + Mesa 23.3.6）通过 Gen12 校验——与参考项目 "Apple ICL 驱动发出 Gen11 EU 代码" 的结论一致。
5. RCS Hang 签名三代一致（IPEHR=0x7A000004 PIPE_CONTROL、INSTDONE=0xFFDFFFFB、VS/CS 未完成）；WindowServer 主线程阻塞于 IOAccelerator/IOAcceleratorFamily2 被看门狗终止；displaypolicyd 每次启动 ~50-70s 后 SIGABRT（历史一致性行为，非 GA3.2 回归）。

## 结论

- `GA32_ROOT_CAUSE: CONFIRMED`（记录 0 的拒绝是安全门禁按设计工作；归因细化需 GA3.3 诊断字段）
- `GA33_OFFLINE_READY: YES`
- `NEXT_REAL_MACHINE_TEST: READY_FOR_USER_APPROVAL`

## 文件

见 manifest.json。分析工具：`analysis/parse_thag.py`（v4，兼容 GA3.1/GA3.2/GA3.3）、`analysis/compare.py`。
