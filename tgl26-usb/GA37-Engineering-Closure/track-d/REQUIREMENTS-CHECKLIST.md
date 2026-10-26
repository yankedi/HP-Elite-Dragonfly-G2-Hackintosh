# 用户要求 → 实际交付与证据索引

|要求|代码/文档|运行证据与范围|
|---|---|---|
|先查实际历史/主要报告/manifest，不覆盖历史|reference/inventory、reference/ga36-source-freeze.json、tools/seal.py|1713历史清单文件+53external原SHA；最终seal verify再次重算|
|A1真实CAS修复保留、成败/独占/终态/再次hang|track-a/legacy-regression/、WRITER-FIXES.md|原样函数提取8矩阵，baseline确定失败行为/candidate单owner；source-level非kext|
|A2匹配ThreadCall可得性与契约限制|THREADCALL-LIFECYCLE.md、reference/bounded-research|5问题有限研究；目标tag未找到，121.6明确reference|
|A2 submit/cancel/queue/active/shutdown/teardown|track-a/source/owned_executor.hpp、EXECUTOR-OWNERSHIP.md|Control+Client+move-onlyTicket，publishing/queue/active栅栏；timeout拒绝强制free，真实XNU条件仍阻塞|
|A3实际GA36代码而非示意算法|track-a/source/kern_capture36.hpp原bytes、tests/ga36_pipeline.cpp原bytes|原stress有限lease拒绝失败日志保留；只适配host期望，不改历史核心|
|1/2/16/64竞争、同时submit/close|track-a/tests/executor.cpp contention/shutdownRace|Clang/GCC Debug/Release/ASanUBSan +各TSan，results.json|
|queued销毁/active关闭/再次提交/重入/再次hang|queuedOwnership/activeCloseTimeout/reentrantPublicationDuringWrite/normalAndRepeat|真实CPU测试、active关闭timeout不free；ASan rawcallback旧反例UAF|
|writer失败/buffer释放/序号回绕/中断/Resetmock|captureReentryAndWriterFailure/exhaustionAndReset/closeInsidePolicy|失败终态、固定slots/持有backend、UINT64_MAX拒绝、Interrupt明确拒绝、新generation模拟，不模拟真实MMIOreset|
|B1全量prefix语义/重试/去重|track-b/FILE-COMMIT-SEMANTICS.md、track-a/WRITER-FIXES.md|相同prefix幂等；全量revision中旧record可重复，不声称exactly-once事件日志|
|B2真实文件/shortwrite/crash/fsync/close/commit/dirsync|track-b/src/snapshot_writer.cpp、FILE-FAILURE-MATRIX.md|修复后73案例/8build，stage注入/fork退出，prefix symlink/post-publish OOM/资源边界负例，旧evidence保留；不是断电/APFS验证|
|B3 THAG2/3、Fault108v1、Pipeline兼容|track-b/src/recordwire.cpp、integration/pipeline_writer.cpp|6build实际接GA36core+Session+准确nominal callbackbridge，最终snapshot原THAGSHA不变|
|C1两层独立门、所有硬件安全前提|track-c/source/fault_record_v2.hpp、READ-SAFETY-GATE.md、FAULT-COHERENCE.md|12安全条件/10可信维度；unknown不放行，raw不冒有效VA|
|C2 v1不改/v2独立端序长度optional/rawderived|track-c/source/legacy、fault_record_v2.hpp、dispatch.hpp、schema.md|108B与384B；旧decoder保留、显式字节codec、严格版本/保留位/长度/未知字段|
|C2兼容/坏数据/版本/跨build字节|track-c/tests、results.json|8build sample exactbytes；原始审计错误与修复checkpoint留档|
|D1有限研究五问题|reference/bounded-research/RESEARCH-BUDGET.md、EVIDENCE-GAPS.md|每问最多2来源，不再全量scan/无新目标读取|
|D2独立审查/修复/默认关闭|track-d/{executor-review,writer-review,codec-review}/|初审AUDIT保留、FINAL-CLOSURE提供独立复核；硬件UNKNOWN不被mock升格|
|E1六候选八维|track-e/ACCELERATION-OPTIONS.md|用户A–F与历史H-A..H-F严格区分，当前KC可得、资源实内容缺口明确|
|E2唯一方向与8项具体计划|track-e/GA38-TECHNICAL-PLAN.md、RESEARCH-PRIORITIES.md|真实4shader消息/依赖IR与候选checker；只计划不提前实现GA38|
|真实命令/exit/SHA、失败保留、determinism|各results.json/时间logs、reference来源、最终manifest|测试结果有scope，独立audit不能用测试数量代替设备证明|
|所有禁止操作、中文报告、持久记录|FINAL-REPORT.md、state.json/history.json/continuation.md|realbackendNONE、硬件approvalNO、source/resultIMGnull；无实机步骤|

审计交付以最终`FINAL-SAFETY-AUDIT.md`、各独立FINAL-CLOSURE与`logs/delivery-audit.json`为准；本索引不把尚未关闭的审计发现标成已经解决。
