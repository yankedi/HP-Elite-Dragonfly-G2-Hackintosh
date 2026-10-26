# GA35 执行过的检查与复现

测试只覆盖离线解析、字节绑定、隔离状态机与codec；没有GPU执行、真实MMIO、kext部署或完整kext构建。

## 已执行结果

|检查|实际结果|证据|
|---|---|---|
|GA34只读manifest/交付引用|408项/36引用全部匹配，历史未改|`audit/ga34-review/logs/final-review-verification.json`|
|GA34 track A/C独立复制回归|64+40 Python测试通过|同目录报告及logs|
|诊断core编译/运行|Clang21.1.8、GCC16.2.0；Debug/Release×plain/ASan+UBSan，8build×28组=224组通过|`audit/ga34-review/native-build/`|
|freestanding/别名反例|4个freestanding仅mem函数允许未定义；4个alias sanitizer构建通过|同目录；GCC harness警告降为非fatal单独保留|
|wire/scanner|5个108B样本、10文件与三份sealed源集匹配；scanner24 cases|`audit/ga34-review/sample-output/`及report|
|本地Mach-O/decoder初始回归|10测试通过，修复后重跑通过|`logs/parser-tests.txt`、`parser-tests-post-review.txt`|
|精确KC输入|完整Boot/System/Aux及4份plist均远端前/本地/远端后SHA一致|`logs/fetch*-receipt.json`|
|真实库存及重生成|五目标映像解析；修复后重新生成成功|`logs/kc-inventory-post-review.txt`、`disassembly-post-review.txt`、`trace-graph-post-review.txt`|
|全部expanded片段逐byte/坐标|11416个符号上界片段、469052条解码指令重新与KC匹配|`logs/fragment-verification.json`|
|仓库检查|`make check` exit0|`logs/repository-check.txt`|
|旧writer CAS语义|精确XNU `_OSCompareAndSwap`确为`lock cmpxchg; sete al`，成功返回1，与旧源码成功即return相反|`analysis/atomic-semantics.json`、`logs/atomic-semantics.txt`；静态缺陷，未执行旧writer|
|GA35独立隔离安全审查|core/原基线/tested副本逐byte一致；已有3个CPU mock binary各28组通过；真实Hook仍BLOCKED|`audit/safety-review/SAFETY-REVIEW.md`、`evidence.json`|
|工具F1–F8独立closure|8类原发现全部以新断言关闭；完整SystemKC172映像/1354映射采样无问题；expanded11416/469052独立重核通过|`audit/tool-review/closure/REPORT.md`及logs|
|额外R1–R3修复后|独立原48项断言取消expectedFailure标记后**48/48全通过**，最终cache1673stub/119vtable slots再核PASS|`audit/main-fixes/FINAL-CLOSURE.md`、`final-closure-v2.txt`、`final-cache-real-v2.txt`|

独立解析工具初审找到8项正确性/证据绑定问题（10个合成反例），不是硬件漏洞。原始fail/expectedFailure日志保持原样，主代理修复前的55份工具/分析文件在`audit/main-fixes/before/`及其manifest；后续闭环报告单列，不能把旧expected failures描述成通过。

初轮独立closure为45pass+3expected failures（R1–R3），最终主代理修复后才得到48真实通过。通用工具的其他低级观察/预算与事务边界仍在`audit/main-fixes/FINAL-CLOSURE.md`明确列出，不宣称通用工具零问题。Forcewake独立初稿的flag11极性错误已修订，原稿在`audit/forcewake-binary/first-pass/`，修订verifierALL CHECKS PASSED。

## 复现

在本目录执行，不从GA34原地构建：

```sh
python3 -B -m unittest discover -s tests -v
python3 -B tools/kc_inventory.py
python3 -B tools/disassemble.py
python3 -B tools/trace_graph.py
python3 -B tools/verify_fragments.py
python3 -B tools/verify_identity.py
python3 -B tools/cache_fixups.py
python3 -B tools/hook_abi.py
python3 -B tools/evidence_graph.py
python3 -B tools/atomic_semantics.py
python3 -B audit/main-fixes/run_final_closure.py
```

这些本地分析命令会重生成本目录对应派生文件；封存后的核验应先复制研究目录，或者仅运行最终manifest只读verify。SSH采集脚本有固定allowlist和拒绝覆盖保护，不作为离线测试依赖；已交付原件不需要重新SSH取得。

完整native矩阵入口是`audit/ga34-review/run_native_matrix.sh`。它为保留证据拒绝覆盖已有sample-output，原目录直接重跑将故意拒绝；要复现，请复制该审查目录到新的GA35本地子目录并移除**新副本**的native-build/sample-output内容，保持`repro/`相对布局，随后运行新副本脚本。基线原件和已有审查结果不得删改。

## 解释边界

- ASan/UBSan与freestanding通过不验证MMIO异常、内核中断约束、实时锁序或设备电源。
- 字节/坐标一致不等于反汇编CFG可达、动态receiver一致或live trampoline认证。
- epoch/held/ack的mock输入可以构造；测试通过不证明Apple真的提供这些条件。
- 部分片段有undecoded tail，原bytes保留；JSON明确`decode_complete`，不得宣称全部函数CFG完整恢复。
- 全部真实采样、Metal与GPU hang排他因果未测试；没有把它们计入通过项。
