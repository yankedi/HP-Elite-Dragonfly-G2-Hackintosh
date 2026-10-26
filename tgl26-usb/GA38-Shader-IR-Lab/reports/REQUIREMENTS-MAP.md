# GA3.8 要求—实现—证据映射

|要求|实现/表示|核验证据与限制|
|---|---|---|
|固定 Record1、四 EOT、原始 bytes/hash|`corpus/corpus.py`、`ir/iga_adapter.py`|`corpus/provenance.json`、8 native decode receipts；Record0/padding 未混入|
|完整工具版本与历史清单只读|`reference/inventory/verify.py`、`tools/seal.py`|full provenance 回执、GA37 972+171 原 seal、13 translator blobs；完整 pin 非短前缀|
|A1 全 79 源类型 IR、未知区分 NONE|`ir/semantic_ir.py` dataclass Fact/Access/Instruction、`ir/schema.json`|raw coverage、8 schema、序列化回读；UNKNOWN footprint 为 null+symbolic，不是空数组|
|A2 byte/lane/subreg/region/mask/implicit|`operand_access`、`ir/integrity.py`|literal byte/lane 测试、ACC/MAC/DW MUL 模型、M05/M05b/F01；JSON sr 为元素单位|
|NF 内部精度/融合/舍入/活跃区间|symbolic ACC/NF、每 operand 独立比较|`reports/NF-ACC-SCRATCH-AUDIT.md`、RULES A/N；精度和 incoming ABI 缺证 UNKNOWN|
|B1/B2 双代真实 SEND 全字段|`ir/message_ir.py`|10+10 合同；`runs/message-fields-018` 核独立 literal 表；实际仅 sampler/RT/URB|
|B3 符号资源与五完成事件|message/resource/completion 独立合同|缺 heap、Surface/BT/Sampler/URB/RT/thread ABI 身份 None/UNKNOWN；dynamic desc 负例|
|B4 代际证据与争议|`reference/rules/RULES.json`、`validator/rules/evidence-map.json`|PRM 版本/页/行、IGA/Mesa pin/blob；TS_EOT/RT 与 JSONsr 更正保留|
|C1 完整 RAW/WAR/WAW/partial/predicate/flag/acc|`dependency/dependency_graph.py`|`runs/dependency-oracles-019` 7 literal 图 oracle；每程序 n(n-1)/2 register-pair 分类|
|C2/C3 payload/response/token/EOT|SEND 边、completion 五事件、每边来源|调度按边判断；副作用可见性/EOT/复用隐式同步规范不足 UNKNOWN；无万能 EOT fence|
|D1/D2 Gen12 原码调度 subset|`validator/gen12_schedule_check.py`|raw 注解+固定 native IGA；in-order counter、token set/src/dst、SYNC、pipeline；未建模 UNKNOWN|
|D3 14 指定 mutant|`tests/oracles/generate.py` 独立期望、`tools/run_mutants.py`|21 fixture 含 14 类、M05b 真 NF 指令，SBID 预期 errata 有直接源证；原失败保留|
|E1 一对多/额外 SYNC/缺映射|`validator/mapping.py`、`validate_mapping`、`tools/validate_candidate.py`|`runs/expansion-015` 真 11→12 CLI；无见证全 UNKNOWN+列12目标；multi-ALU 无组合证明 UNKNOWN|
|E2/E3 十二层独立结果/精确偏移|`validator/compare_program.py`|79×12=948 项，双方 bytes/offset/rule/假设/修复/来源；NF 不掩盖已知 GRF 字段|
|F1/F2 完整表示与31单位回归|IR/graph integrity、native replay|31/31 已知隔离单位；旧成功不扩大为整 Shader 证明|
|F3 Clang/GCC Debug/Release、ASan/UBSan|`tests/historical-regression/` 及 `debug-extension/`|5 build 身份/命令/exits/input-output hashes，640 原调用保留+独立新 Debug；Debug asserts 独立记录|
|F3 独立 oracle、属性、损坏/版本/端序/边界|`tests/test_*.py`、独立 fixture|随机 interval 对称/单调、hash/version/overflow/illegalcompact/branch/unknownfamily/动态desc、两clean42工件确定性|
|F4 独立审查与原失败重放|`review/initial/`、`review/final/`|初审冻结9项/7mustfix；针对性回归及复审；已修/受限/未知/缺输入分开|
|G 范围与持久留痕|scope guard、只读历史、新 Lab only|`history.json`、`continuation.md`、原失败/checkpoint；规则子任务曾误写 tmp 的迁移/偏离回执单独保留|
|H/I/J 中文交付、13状态、修复清单|README/FINAL/state/reports、`tools/render_reports.py`|最终状态有作用域；逐条 shader/offset 的 GA3.9 backlog、独立审计、manifest+selfhash|
|K 完整实际执行/工程验收|`tools/run_checks.py`、`tools/seal.py`|两新目录实际运行、make check 回执、最终全量交付审计；硬件批准 NO|

工程 COMPLETE 表示要求的完整可追溯表示和评价已交付，允许显式 UNKNOWN；它不表示全部 ISA、完整资源 ABI、真实硬件调度或 Metal 已验证。
