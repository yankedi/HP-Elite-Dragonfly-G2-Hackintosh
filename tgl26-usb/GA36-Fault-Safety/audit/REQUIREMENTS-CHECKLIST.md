# GA36 prompt→工件→证据验收表

验收对象是用户允许的**离线修复、可审计路径与Mock-only/差距分支交付**。不能把以下文档存在当成PM/ACK/Reset等实际前提已证。

|需求|工件/实际证据|裁定|
|---|---|---|
|任务目标1，A1真实源码与状态机|track-a/baseline/{kern_igfx.cpp,kern_igfx.hpp,kern_tglhang.hpp}，CAS-ROOT-CAUSE、CAPTURE-PIPELINE；原CAS及原失败/发布顺序的实际提取函数测试|已确认原缺陷，不推广缺失GA33实物或运行GA32|
|A1全部关联变量/原子操作|baseline的hangWriting/WriteError/Count/InProgress/Attempts/Captured/Wakes/Call/WriteBuf；独立AUDIT F1/2/5/6逐字段指出volatile共享和无teardown|源级ownership分析完成，实际Hookproducer不获认证|
|A2独立修复，非机械取反|candidate成功owner、error-before-release、Failed2终态、uioFree-preopen、强制hangDump0；独立core immutable publication/pending/watermark/close；CAS-FIX.patch|已完成；wire unchanged；不假装接入旧GPU链|
|A3单/2/16线程与CAS成败|tests/legacy实际callback，tests/pipeline contenders及120×16、16producers；logs/legacy/tracka-results.json、logs/pipeline/results.json|通过；mockXNU与实际ThreadCall分开|
|A3提前退出/open失败/部分写/timeout|legacy9后端路径、missingcallback/missinguioFree/short/error/TimedOut-return测试|返回路径正确；不可返回IO不获证明|
|A3重入/两Hang/未完成snapshot/发布后修改|producerReentry、nested writer、normal连续prefix/complete=false、scratch改变后不可变snapshot|CPU契约下通过|
|A3取消/销毁/标志错误恢复|close+active lease+join、publication terminal races、Failed无reset、不重试；ThreadCall pinned CONTRACT|CPU测试/上游契约完成；真实queued-callback fence仍阻塞|
|A3重复/漏写/版本/截断/顺序|watermark/nestedPending；exact-native-v3→file→strict codec、原v2 roundtrip、10负例；旧parser22检查|通过；外部通知丢失不谎称已写；旧parser warning限制记明|
|目标2，B1不全扫|track-b/analysis/analysis-budget.md、24函数focused-fragments与一轮bounded-xref|固定预算；复用GA35，没有全量重新反汇编|
|B2完整出口及真实字节|FORCEWAKE-BRANCHES、branchmap、focused-fragments，原KC24函数72caller197fragment verifier|byte核验通过；zero/flag12/forward/local/no-transition/ACKpanic/release分开|
|B3五种条件|GT-POWER-LIFETIME、start/stop/config/callback/PM/PowerWell函数|静态推进；真实power/request/ACK/锁/reset排他未混用|
|B4 Hang/reset/clear/indirect|RESET-AND-CLEAR-TIMELINE、CALLGRAPH，旧4094在941C请求后，vtable候选及unresolvedreceiver|局部先后成立；Gen12clear/latch/全局排他UNKNOWN|
|B5 A/B/C完整比较|SAFE-SAMPLING-POINTS五条件+工程风险表|三者BLOCKED，未扩大原锁范围|
|目标3，C1兼容复用|track-c/source两GA34 byte-identical header，source_copies SHA证据，108B codec回归|通过，无不兼容格式|
|C2九条件4值默认拒绝|kern_tglfault34_gate.hpp、gate tests，4^9全部状态与malformed enum|仅allVERIFIED+enable；当前3CONDITIONAL6UNKNOWN拒绝|
|C3 tuple一致性|同一次三读A/B/A混合、CEC4前后相同仍ABA反例、mock reset/power/ACKtimeout|反例通过；实际tuple安全保持UNKNOWN，不追加真实读|
|C4证据不足只Mock-only|强制captureoff、独立Fault核心、无新增真实reader；source diff和默认禁用回归|MOCK_ONLY；无实机批准|
|D1 Writer独立审查|audit/writer-review/AUDIT、FINAL-CLOSURE；F6修复再验证，其他integration gate保留|完成审查，不把未解决项涂绿|
|D2 Hook独立审查|同上末节及track-c/HOOK-ABI-REVIEW、track-b五报告，stock/live/ABI/context/panic/MCE/sideeffect限制|静态PARTIAL、真实HookBLOCKED|
|D3真实CPU测试|Clang/GCC release、ASan+UBSan，故障/并发/parser/serializer/mockReset/ACKtimeout/PowerLost/mutation实际日志|通过；不是TSan、GPU执行或形式证明|
|阻塞后自主推进|已完成Writer、24函数PM/reset、tuple反例与安全gate，未在第一个UNKNOWN停止|离线边界可完成项交付；不无限重复扫描|
|指定目录/15问/11状态|根FINAL-REPORT，README，A四文件，B五文件，C三文件，audit/logs/NEXT-EXPERIMENT|delivery_audit.py检查真实文件与状态；15问对应题号|
|复现命令/回退/保存|A TEST-REPORT、C run_tests.sh、NEXT-EXPERIMENT、tools/seal.py|当前compiler/source pin记明；seal后只verify，重分析新私有副本|
|来源/专有数据/旧证据|reference/inventory；准确KC/UUID固定；raw Apple及派生仅本地私有；原GA32b有效|历史tracked inputs最终再逐SHA核对；无上传/提交|
|执行限制与持久记录|state/continuation/history；无SSH或HP变更；bytecode incident显式保留/修复|原始历史工件未改；不可隐瞒曾生成临时pycache的边界副作用|
|全部SHA/封存|manifest.json、manifest.sha256、logs/manifest-verification.txt|最终seal逐文件与外部来源核验，另有selfhash及只读verify|

## 不能算完成的真实设备子项

live代码/完整ABI、active power、actual GT selector/ref/ACK、reset/clear排他、MMIO mapping/lifetime、tuple latch、same-hang context/PML4、真实ThreadCall teardown与文件原子持久性**未完成**。本轮用户明确允许这些关键条件不足时以Mock-only及最后缺口交付，因此本轮研究交付完成不等于上述设备子项完成或审批通过。
