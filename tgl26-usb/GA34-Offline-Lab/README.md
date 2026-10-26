# GA3.4 Offline Engineering

仅CPU离线命令兼容与Gen12 fault诊断工程。**完整真实Shadow拒绝、真实MMIO接入未连接、READY_FOR_HARDWARE_APPROVAL=NO**。结论与15问/十状态见[FINAL-REPORT.md](FINAL-REPORT.md)。

历史输入保持只读，GA32-ISA-Lab manifest `6527515adfde14011a604c2caea7aa0abb6aedb53e9269a7951c194559b656fe`已在本轮开工时复验通过。

## 核心交付

|目录/文件|内容与范围|
|---|---|
|`track-a/command_stream.py`|逐bit XML schema、UNKNOWN继承、显式batch模式/有界解析、严格typed relocation与执行occurrence核对|
|`track-a/spec-diff.json`, `prm-constraints.json`|78定义/5传递struct、官方段落/限制索引；官方语义形式化仍PARTIAL|
|`track-a/packet-audit.json`, `state-ir.json`|166真实包逐项；56包级有效/5明确不符/105未知，非整批语义证明|
|`track-a/normalizer.py`, `stencil-proof.json`, `draw-proof.json`|条件Null例、四draw A/B定义字段与独立官方PRM/Mesa依据|
|`track-a/shadow-batches/`|A/B各4368B格式研究及receipt；严格跨页NOOP示例另列，等级不混用|
|`track-b/diagnostic-src/`|默认关闭freestanding mock core、108B LE codec、相邻GA3.3原样副本、离线boottext scanner/sample|
|`track-b/ga33-add-unattached-tglfault34.patch`|仅新增独立header；未接入原hook，无真实MMIO backend|
|`track-b/samples/initial/`|5个108B合成wire与derived JSON，实际encode/decode回读验证，非硬件捕获|
|`track-b/*audit.md`, `fault-registers.md`, `reset-timeline.md`|固定历史i915/v6.18/官方PRM、GT域、Apple exactbinary/锁时序缺口|
|`track-c/correlate.py`, `reports/`|18合成场景、sample identity/整段hang continuity分离、防页范围冒allocation|
|`track-*/reports/`, `logs/`|独立审查、原失败反例、修复回归、编译/确定性和保留审计|
|`manifest.json`, `manifest.sha256`|最终私有完整性封存；重新生成任何工件后须重封清单|

## 在开发主机复现

在本目录执行。Python3标准库；XML importer从只读依赖`../GA32-ISA-Lab/tools/mesa-eu/source`读取，固定commit `863338275d915e867319c3690ffd3272b06303c3`。没有独立GPU/VM/目标机前置条件。

```sh
make check
make sources
make analyze
python3 -B tools/check_determinism.py
```

`make check`为Lab的Python suites、AST/JSON、固定输入/clean source检查；仓库根`make check`另外验证项目基础记录，其日志为`logs/repository-check.txt`，不是本Lab测试替代品。

需要重建native时：

```sh
bash track-b/diagnostic-src/build_core.sh
python3 -B tools/pack_matrix.py --label clang
python3 -B tools/pack_matrix.py --label gcc
python3 -B track-b/diagnostic-src/deliver_core.py
```

core脚本实际选择Clang/GCC，Debug/Release×plain/ASan+UBSan，保存旧日志再生成新receipt；pack脚本使用其编译器收据重建独立上游pack检查。core每build28组、共8个executable/224组调用；pack另外8个，4个freestanding object另列。Python64+40=104项。编译器精确路径/flags/version/SHA在`logs/diagnostic-core`与`logs/pack-*-results.json`。仅CPU代码受这些sanitizer覆盖，Python parser不因此获得C++ sanitizer证明。

生成一套新的sample（run-name不能覆盖已有证据）：

```sh
python3 -B track-b/diagnostic-src/build_samples.py --run-name local-reproduce-1
```

检查历史与最终封存：

```sh
python3 -B tools/verify_history.py
python3 -B tools/verify_delivery.py
python3 -B tools/archive.py
sha256sum -c manifest.sha256
```

`archive.py --create`会**重新封存**当前文件，只在完成检查与持久记录后使用；普通验证不得用重封掩盖修改。新实验输出请另建目录并追加记录，不覆写原失败证据。旧`logs/audit-parser/reproduce.py`是在旧hash上证明缺陷存在的历史脚本，不是当前应通过的回归suite。

## 当前范围

三fault寄存器CEC4/CEB8/CEBC需要LinuxGT域；Apple domain7/ACK/power/reset locks未知，exact25G83 binary未找到。Null示例含MOCS4只是条件Mesa示例，不是Appleruntime证明。两个完整格式研究保留opaque资源，不能提交；严格Shadow真实批拒绝。whole-kext未构建，Metal/GUI/硬件执行未验证。

本目录含私有捕获派生数据，不公开上传。阶段状态见 `state.json` 和 `continuation.md`。

迁移须私下携带整个Lab、manifest以及外部固定Mesa源树/历史输入；仓库本身不含这些private artifacts。未生成新SMBIOS或密钥，也未上传捕获。SOURCE_IMG/RESULT_IMG均无；实机后续由用户另行决定。
