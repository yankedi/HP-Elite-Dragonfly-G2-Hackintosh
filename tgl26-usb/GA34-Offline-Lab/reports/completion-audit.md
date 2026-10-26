# Prompt → 工件 → 实证完成审计

审计目标是交付GA3.4离线命令兼容/诊断**基础工程**、正负样本、可运行验证、来源与独立安全闭环、中文15问十状态及私有封存；不将本轮定义为已修复GPU、完整跨代执行等价或真实Hook已安全。以下把离线交付与仍未知的研究结论分别列明。

|要求|实际工件/实证|完成范围与未达到项|
|---|---|---|
|基线实查/历史不变|`inputs/provenance.json`7冻结输入；`reference/ga33-source-provenance.json`4副本；`logs/historical-preservation.json`559+2/两cleanpin/四副本末次hash复核|离线基线已交付；IMG无新source/result、无写入，不冒称重新逐byte哈希全部磁盘镜像|
|新Lab范围/权限持久化|`state.json`、`continuation.md`、append-only `experiment-history.json`|本Lab唯一研发写入位置；未连接HP/部署/改IMG/EFI/固件/物理保护/GPU输入|
|A1机器schema/bitdiff|`track-a/spec-diff.json`、`command_stream.py`、`reports/command-compatibility.md`|74实际种命令+4辅助模型/5传递struct，双代opcode/length/fields/default/enum/group/addresses/unknown ranges；XML覆盖完成，完整PRM执行语义**PARTIAL**|
|A1官方条件来源|`track-a/prm-constraints.json`、`tools/catalog_prm_constraints.py`、`reference/track-a/provenance.json`|80种定位ICL80/TGL77，2194/2328literal片段、12明确规则；其余未形式化标UNKNOWN，不把文字提取当validator证明|
|A2 NullStencil|`stencil-proof.json`、独立PRM/ISL报告及`reference/track-a/pack-proof.c`、`normalizer.null_stencil`|8DW/SurfaceType7/Depth copy/条件MOCS4与MBZ独立pack验证；未知或存在资源、状态/MOCS/stepping不明拒绝。Apple资源inventory/MOCS/workaround尚未取得，不无条件转真实流|
|A3四draw A/B|`draw-proof.json`、`normalizer.py`、`shadow-batches/format-candidate-{A,B}.{bin,json}`|原7b000008在双代畸形；四draw参数/40Bextent/next边界保留；A/B零XP定义字段条件等价；未宣称畸形源执行等价|
|A3完整位置/引用检查|两candidate receipt source_target_map/typed_resource_inventory/target_validation；R03/R04回归|两4368B输出，166/178连续decode；exact frozen输入/typedVA界绑定，无BBS，未猜重定位opaque资源。未知heap/base-relative语义仍阻塞GPU执行|
|A4有状态IR|`track-a/state-ir.json`与parser/tests|Pipeline逐fieldmask、SBA ModifyEnable、VS/PS/dispatch/URB/Depth/Stencil/HiZ/binding/sampler/vertex/RT/cache/contextmetadata；未知继承/heap不补零，不冒称真实原子状态|
|A4控制流|`test_audit_regressions.py`、独立A两轮closure|Gen11legacy二级chain、Gen12显式mode/nested3层、entry/BBS边界、conditional/indirect/predicate拒绝、loop/alias/packet+scan budget；entry支持已知first-level契约|
|A5严格Shadow/重定位|`strict_shadow`、`strict-noop-growth.{bin,json}`、typedBBS/跨页测试|两遍位置表、typed地址、逐dynamicoccurrence核对，fallthrough变化拒绝，不回传partial；纯NOOP/END/BBS子集验证，完整真实批仍明确拒绝|
|A6全166分类/统计|`packet-audit.json`与`logs/results-summary.json`|56包级subset/5明确不符/105未知，161格式检查/56静态可转/33显式资源/2继承未知；不是161条完整有效命令|
|B1寄存器/历史适用|`register-spec.json`、`fault-registers.md`、`source-audit.json`及固定Linux两commit/官方703046|CEC4/CEB8/CEBC、9A49/TGL12.0、全GTengine、valid/type/source/engine双mask、VA/GTT/clear/0x4094MOCS重叠已核；公开完整CEC4/CEB8表/枚举仍缺，**PARTIAL**|
|B2 Forcewake/power/ACK|`forcewake-audit.md`及两版`intel_uncore.c`|LinuxB400–CFFF明确GT；Apple7/ACK/power/锁序未证，**真实接入保持BLOCKED**，无provider|
|B3当前Apple/Reset前路径|`reset-timeline.md`、`diagnostic-design.md`、GA33源码行号|wrapper先原void再domain7；Linuxcapture→clear→reset实证；25G83exactMachO/完整反汇编本地未找到，不造CSB/contextdestroy/clear时序|
|B4 record/codec/上限|`kern_tglfault34.hpp`、`fault-record-format.md`|108B LE/version/size/validity/raw与derived分离；固定8append/首条保留/sequenceoverflow/fail-stop。context/PML4/phase等实际未得者不编造；Complete仅协议完整非同次硬件快照|
|B5独立源码与开关|`diagnostic-src/ga33-base`、405行header-onlypatch、`kern_tglfault34_boottext.hpp`|baselinehash相同、patchcheck与payload复原；Request默认关、bounded exact boot-textscanner24cases。无实际bootarg routing/hook/backend；wholekext**NOT_BUILT**，无已验证本地Xcode/SDK环境|
|B6全部fault负样本|8corebuild的28groups及`test_tglfault34.cpp`|valid0/1、PPGTT/GGTT、engine/source/type、DATA1合法高低位、VA界、三readfail、42guard注入、reset/ACK/power、时间/身份、多hang/full/seqwrap、trunc/version/codec、alias冻结回归；未试验实际MMIO或panic|
|实际wire样本|`track-b/samples/{initial,post-alias-fix}`及独立faultclosure regenerated-samples|五108B wire+JSON跨三来源byte-identical；实走Collector/encode/落盘回读/decode/encode/derive；严格synthetic、context/PML4unknown|
|C1身份/时间/空间关联|`correlate.py`、40suite、18synthetic、`correlation-model.md`|Batch/Shader/Surface/PostSync/未知/valid0/时序不明，typedepoch/root/clock/ID/gen/lifetime/alias、sample-vs-hangcontinuity分层；identity非因果，真实THAG缺新字段不由合成补全|
|C2四实验排序|`next-experiment-ranking.md`|关闭未知/成熟度/硬件风险/command行为/恢复/失败证据/额外前提已比；优先Fault-only信息，但当前**不具备硬件审批条件**|
|D1工具链真实矩阵|`logs/diagnostic-core/*-results.json`、`logs/pack-*-results.json`、samplelogs|Clang21.1.8/GCC16.2.0 Debug/Release plain+ASanUBSan；8core×28=224、8pack、4freestanding及sample实跑；Python64+40=104，C++sanitizer未被冒称覆盖Python|
|D1确定性/来源hash|`logs/determinism.json`、`logs/results-summary.json`|13分析工件双再生成同hash；16nativebinary与testedsourcehash核对/两个跨8build stdout组一致；sourcepins与PDFsha保留|
|D2独立初审/修复|初审14findings/22反例；`correlation-fix-receipt.md`；A `repaired-command-review.md`与`r01-r04-closure.md`|原A13/原C9及第二轮A4全部确认关闭；原失败证据/snapshot保留，未改写历史成功|
|D2 fault闭环|`independent-fault-review.md`、`fault-alias-closure.md`及closure-receipt|两API alias已入口descriptor冻结修复；63descriptor+3request变体在Debug/Release sanitizer通过，191protected不改。累计20distinct问题已修复；并发/ABA/contextlifetime仍明确caller/live契约，非thread-safe证明|
|最终报告/十状态|`FINAL-REPORT.md`、README、test-coverage与safety-integration|逐答15问，10状态有证据范围，科学结果PARTIAL/硬件NO未被抹去|
|最终checks/封存|Lab `make check`、仓库根`make check`、`verify_delivery.py`、`archive.py`、manifest checksum|最终实际audit/manifest验证日志是验收证据；本表不代替执行。manifest封存后停止，不自动重启任何试验|

## 审计判断

本轮允许的离线框架、条件候选、诊断mock、测试/来源/安全闭环与报告交付有实际工件；缺失的runtime数据及Apple安全证明按原任务允许的分支保留PARTIAL/BLOCKED接入。未达到的**完整PRM语义、完整可执行Shadow、实际fault与同次因果、whole-kext可加载、硬件审批**不计为已达成。后续需要新资料/独立授权，不能通过测试绿灯或manifest存在将其升级。
