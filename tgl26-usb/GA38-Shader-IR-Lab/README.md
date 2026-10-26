# GA3.8 — 全程序 EU 语义与 Gen12 候选校验器

这是四个真实 Gen11 Shader 的**纯离线分析工程**。保留源/候选全部机器码与精确偏移，建立类型化 IR、实际 SEND 合同、保守依赖图和 Gen12 调度子集检查，逐指令独立评价十二层。数值精度、资源 ABI 或硬件完成规则不足时保留 UNKNOWN。

最终结论见 [FINAL-REPORT.md](FINAL-REPORT.md)，实际逐程序报告与 [GA3.9 修复清单](reports/TRANSLATOR-FIX-BACKLOG.md) 位于 `reports/`。`state.json` 是当前状态，`history.json` 为追加证据，`continuation.md` 为续接入口。

## 最短复现入口

在本目录运行。`reproduce-*` 必须是不存在的新目录；已封存交付目录不原地重跑。

```bash
export PYTHONDONTWRITEBYTECODE=1
python3 -B tools/seal.py verify
python3 -B tools/run_checks.py --output runs/reproduce-checks
python3 -B tools/run_mutants.py --run runs/reproduce-checks/clean-a --output runs/reproduce-mutants
python3 -B tools/render_reports.py --run runs/reproduce-checks/clean-a --output runs/reproduce-reports
python3 -B tests/check_expansion_cli.py runs/reproduce-expansion
```

复现会新增工件，故原 seal 的“完整文件集合未变”校验应在新增运行前做；每次复现保留在独立新目录，不改旧回执。`tools/analyze.py --output <本Lab内新目录>` 单独运行八份真实程序流程；`tools/validate_candidate.py --help` 是显式一对多映射候选接口。

```bash
python3 -B tools/validate_candidate.py --shader PS0 \
  --candidate corpus/candidate/PS0.bin --output runs/reproduce-one-candidate
```

显式 `--mapping` 接受 `entries` 对象或数组，条目形如 `{"source_offset":0,"target_byte_range":[0,32]}`；给出的范围必须是完整目标指令范围、无重叠、覆盖所有源与目标。对象若带源/目标 SHA，须匹配实际输入。见 `runs/expansion-015/mapping.json` 的真实 11→12 条指令例；没有可靠对应时输出 UNKNOWN 和全部未映射目标偏移。

## 环境与固定依赖

- Python 3.13 实测；主要分析为标准库。JSON Schema 校验依赖 `reference/python-requirements.txt` 的五个精确版本，交付包含 `reference/python-deps/`。分析不把 Python 当 native ASan/UBSan 被测程序。
- IGA 完整 pin：`c36a504a4e6c68030c3302646aa396b8b59b22cb`，历史目录 `../GA32-ISA-Lab/tools/iga/source` 和 `build/IGAExe/iga64`；每次解码前核 HEAD、可执行文件和共享库 SHA。历史 manifest 不包含的共享库有本轮独立采集回执，身份范围明确区分。
- Mesa：`863338275d915e867319c3690ffd3272b06303c3`；Translator：`1010490d3421628c9d6fd0bd518b6c4b6f8ee33c`。后者按固定归档 13 blob 核验，不谎称本地有该仓 worktree。
- 来源与规范：`reference/inventory/PROVENANCE.json`、`reference/rules/RULES.json`、`validator/rules/evidence-map.json`；编码 SubRegNum 字节单位和 IGA JSON `sr` 元素单位有独立更正记录。
- 所有工具构建/代码只在 CPU 执行，最多 256 条指令/程序、100000 hazard 边；不支持分支则明确拒绝。

## 重要工件

|路径|用途|
|---|---|
|`corpus/provenance.json`|Record1 重提取与四源/四候选原路径、SHA、framing|
|`ir/outputs/`、`ir/messages/`|全部节点原 bytes、显式/隐式访问、消息/资源/完成合同|
|`dependency/graphs/`|保守 RAW/WAR/WAW、partial/lane/mask 与 SEND 完成约束|
|`validator/outputs/`|逐程序 SWSB 事件、每边约束、十二层比较与映射|
|`tests/oracles/`、`tests/mutants/`|独立期望、14 类覆盖、原期望与有来源 errata|
|`tests/historical-regression/`|原 31 隔离单位、640 次调用及独立两 Debug build 扩展|
|`review/initial/`、`review/final/`|DeepSeek 初审、原反例、修复后独立复审|
|`runs/`、`checkpoints/`|原失败、实际重放、双新目录确定性与修前源快照|
|`reports/REQUIREMENTS-MAP.md`|用户要求逐项到代码/验证证据映射|
|`manifest.json`、`manifest.sha256`|私有全量工件及外部来源 seal；symlink 只哈希链接文本|

## Native 矩阵与历史单位

`tests/historical-regression/replay.py --out <本Lab内新目录>` 重放归档 Clang Release、GCC Release、Clang Debug ASan+UBSan 三种构建。`tests/historical-regression/debug-extension/replay-extension.py` 在其 `debug-extension/` 内新目录复制固定源码并真实构建独立 Clang/GCC Debug，详细参数见各自 README。旧 640-run 结果和回执保持原样。

31 个严格单位的已知字段/往返成功只保留其隔离单位范围。错误平台/损坏输入下 Debug 断言 abort 与 Release 错误退出被独立记录，未将断言当 sanitizer 漏洞或有效输入成功。复现不应为“补绿”忽略这些差异。

## 边界和迁移

`hardware_validated=false`，`READY_FOR_HARDWARE_APPROVAL=NO`。本轮没有新 GPU Hang、MMIO、SSH 改机、kext、EFI/IMG、固件、启动变量或门禁修改。GA32–GA37 输入和 seal 只读；未修真实 Translator 运行路径。

整个 Lab 含私有捕获派生数据与构建证据，不进入 Git、不公开上传。迁移须私下转移 Lab、manifest 中的外部历史来源及原捕获，并核对 SHA；仅项目代码仓不足以复现。固定绝对路径/工具路径不同需明确记录迁移适配，不能篡改旧来源回执。
