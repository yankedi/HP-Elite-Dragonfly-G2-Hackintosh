# 有状态命令兼容层：当前可执行范围

`python3 track-a/command_stream.py` 从本Lab冻结输入重建 `spec-diff.json`、`state-ir.json`、`packet-audit.json` 及严格Shadow拒绝回执。

## 机器可读规范

固定Mesa23.3.6 `863338275d915e867319c3690ffd3272b06303c3`，通过其原生GenXml importer解析继承关系；不修改源码，不生成旧目录bytecode。每种实际命令及surface/sampler/binding辅助struct保存两代：opcode header字段、默认值、逐bit范围、enum、group（含原XML）、length/bias、地址/offset、动态依赖及逐字段差异。

范围明确：**XML字段覆盖完整，不是PRM全部编程限制已形式化**。XML没声明的保留位和条件限制标UNKNOWN，不能把XML缺省值当所有场景必须等于该值，也不能以“位域宽度相同”证明跨代语义相同。Null/Draw的额外PRM规则由独立证明工件集成。

`validate_spec_document`对schema版本、commit、非空/不重复命令名与字段bit边界做实际检查；packet验证另行检查固定/动态长度、明确mbz/mbo、动态组残片、非法selector mask、目标字段截断/布局改变、资源与状态依赖。原166包与THAG逐字节对应通过测试。78定义含74实际种命令+4辅助模型，另有5个传递struct；每bit覆盖/未声明unknown范围均有机器记录。

`prm-constraints.json`收录80种命令/结构的官方段落定位：ICL80、TGL77（3个历史命令未在TGL exactheading定位）；2194/2328个literal限制上下文。它是完整段落来源索引，不是从自然语言自动推得硬件证明；仅12条列明规则被单独建模，其余明确UNKNOWN。TGL pipeline bit5在固定XML仍名ForceMediaAwake，官方PRM实际MBZ，验证优先PRM。XMLnonzero MOCS断言作为pack层提示；SBA未modify/NULLDepth/disabledHiZ的MOCS0不无条件升级硬件不符合，effective-state仍未证。

## 分类计数（当前严格证据口径）

|分类|数量|范围|
|---|---:|---|
|VALID_TGL_PACKET_SUBSET|56|55个全零MI_NOOP及1个精确MI_END，仅包级语义，不等于整批可执行|
|EXPLICITLY_NONCONFORMING|5|旧stencil长度与四draw扩展长度规则|
|UNKNOWN|105|尚有资源、继承、字段/编程限制等证据缺口|

161包可通过当前**格式层**检查；这个数字不是161条完整语义已证TGL命令。准确逐包结果、需heap和继承状态计数在 `packet-audit.json`，后续集成新规则以实际输出为准。

## 有状态IR

维护Pipeline/Context、SBA多个base、VS/PS/dispatch、URB、Depth/Stencil/HiZ、binding/sampler、vertex、RT、cache与batch栈。每个packet保留raw、source VA/offset、schema、groups、state_after和结构化事件。

* SBA ModifyEnable=0保留上态；上态未知仍UNKNOWN；已知前次包值保留并明确未证硬件生效。
* PIPELINE_SELECT逐字段mask合并与knownness；未更新ancillary字段保留上态，selector的一bit掩码显式非法，不凭零填未知。
* 未捕获heap、完整RT、shader语义、payload保持RESOURCE_DATA_MISSING；动态组按真实包长有界解析，struct内容无法由简单字段模型恢复时不编造。
* context=5是已有报告关联元数据，非同一次原子硬件执行轨迹。

## 调用栈与Shadow

Parser支持显式捕获segment表、PPGTT MI_BBS第一级→第二级及END return、**第二级内部legacy BBS为chain，不继续push栈**；first-level tailcall。Gen12必须明确提供MI_MODE nesting模式，不能从header猜；nested最多3层，第三级未证编程限制拒绝。当前entry支持显式first-level契约，不支持没有returncontext的二级入口。初始entry和BBS目标均验证packet边界。条件结束、间接/谓词/offset/resource-streamer/未建模控制位、BBS低地址MBZ、非canonicalEND、缺segment/alias/循环/截断均拒绝。总decode工作预算包含边界发现且按segment缓存；半开VA区间可达2^48端点，最后一个有效DWORD不被误拒。

`strict_shadow`两遍：唯一路径packet布局→typed MI_BBS地址位域重定位→Gen12再解析，并将**每次动态执行occurrence**与源→目标映射比较，不能只比较包数；跨segment fallthrough/return改变目的地即拒绝。完整source/target VA、offset、length映射及relocation表，目标buffer增长/跨页由新buffer承载；只允许经过证明的纯零NOOP扩展，不信任任意converter回调。没有未知地址扫描。任何失败只抛结构化拒绝，不返回半成品bytes。目标解析仍用同一XML引擎，因此独立PRM/C pack和安全复审是不同证据，不把第二次相同算法运行冒称独立实现证明。

目前严格Shadow支持纯NOOP/END/BBS控制流子集。真实Batch在尚未证明的PIPE_CONTROL等包处明确拒绝完整转换。`normalizer.py`已产A/B两份4368B格式研究样本（源4356B，stencil扩12B），连续decode166/178包、保留真实四draw参数/next边界；MOCS4及资源absence/stepping作为明确未验证假设列入receipt。opaque包和typed资源引用保留，不作未知引用重定位，**不能作为strict converter成功或GPU提交buffer**。严格Null helper对未知/存在资源、活跃/缺失状态、未知MOCS/stepping拒绝。

## 测试

`python3 -B -m unittest discover -s track-a/tests -v`，最终64项；早期31项绿灯仍漏掉独立审查反例，原审查证据保留在`logs/audit-parser`。修复后新增20初审回归+13normalizer/复审测试，最终Lab日志见`logs/lab-check.txt`。第二轮条件XP/checker envelope/study VA/冻结输入来源问题已修复，经独立35项confirmation和13原反例确认关闭，见`r01-r04-closure.md`；两个candidate B七DWdraw不再误标XP截断。八个nativeClang/GCC Debug/Release/plain/sanitizer pack构建匹配独立上游pack输出，见`logs/pack-*-results.json`。未将离线测试当作MMIO或GPU安全证明。
