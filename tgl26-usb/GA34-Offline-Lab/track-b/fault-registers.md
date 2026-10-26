# Gen12 Fault寄存器核验

## 固定来源与适用性

历史Linux v5.15 commit `8bb7eca972ad531c9b149c0a51ab43a417385813`，交叉v6.18 `7d0a66e4bb9081d75c82ec4957c50034cb0ea449`；源码、URL与SHA在 `reference/track-b/{provenance,device-provenance}.json`。v5.15 `i915_pciids.h:609`含0x9A49；`i915_pci.c:842–875`把TGL设为Gen12，故不是只借用未来master规则。

* v5.15 `i915_reg.h:2591–2596,2761–2764`：CEC4 fault，CEB8 DATA0，CEBC DATA1。
* `intel_gt.c:329–367,374`：Gen12使用这三寄存器；Gen8起只有**一个All Engine Fault Register**，不是给RCS基址加offset。
* valid bit0，type bits2:1，source10:3；历史engine14:12，v6.18扩为16:12。原始32bit必须保存；本机TGL decode与新通用mask分层，不把新增字段无条件反推历史意义。type/source这里只保留数值，不伪造未核实枚举。
* VA=`((uint64_t)(DATA1&0xF)<<44)|((uint64_t)DATA0<<12)`，48bit页地址；DATA1 bit4=1 GGTT，0 PPGTT。fault engine不能单独关联当前RCS context/PML4。
* `GEN12_GLOBAL_MOCS(37)=0x4000+37*4=0x4094`，两版header均证实表达式重叠。旧Apple报告0x4094=0不能当Gen12 fault=0。

## 官方规范独立补充

Intel官方附件703046（TGL Vol2c A–L），本地PDF/text和hash见 `reference/track-b/official-provenance.json`。**印刷p906 / text32038–32076**给出CEBC `FAULT_TLB_RD_DATA1`：RO，bits3:0是VA47:44，bit4是GTT选择；另有bit5 TLB valid、bit6 present、bits8:7 page-size（4K/64K/2M/1G），**31:9 MBZ**。因此不能把5–8位设为非法保留位。页尺寸是TLB条目属性，fault地址本身仍只精确到4KiB，不能据此反推完整allocation。

公开Vol2c中没有定位到CEC4完整描述及DATA0独立表，故寄存器审查标PARTIAL，不冒称所有硬件副作用/枚举已由官方完全证明。DATA1的 `_Custom_GTIReset: DEV` 注记不证明Apple具体reset会在何时清除哪几位。

## Clear / Reset

历史 `intel_gt_clear_error_registers:291–293`显式RMW清valid再posting read；`intel_gt_check_and_clear_faults:370–382`先读/检查再清。Linux `intel_reset.c:1326–1333`先RPM引用，再error-state capture，再clear，之后才尝试engine/full reset；说明**诊断可能在物理reset前已被软件clear**。仅说“reset前Hook”不足以保证fault有效。

新诊断只读，绝不执行Linux clear序列。DATA1 RO与Linux使用常规read支持无读清观察方案，但缺完整CEC4公开表及Apple25G83路径证明，不能因此批准实际MMIO。精确安全门禁见forcewake审查。
