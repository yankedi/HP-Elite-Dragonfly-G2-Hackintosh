# GA417 Metal动态验证边界与顺序

当前HP在NixOS。已完成hash对应的封存二进制静态同缺陷审计及独立离线签名包；未宣称在HP实际测得泄漏量或修复后的残留块数。

## 已有观测

`ga415/reports/INITIAL-HEALTH.json`在2026-10-24T08:32:01Z记录WindowServer PID197、RSS3842004 KiB，约3.66GiB；字段来自`ps pid,state,rss,%cpu,comm`，不是footprint。单个样本不能证明持续增长，更不能把全部RSS归为POSH。已封存的crash-series目录未发现专门的heap/vmmap输出文件。本轮未重采海量日志。

## 下一次用户手动回macOS：先只读

1. 使用原GA416引导，`DisableRtcChecksum=false`，保持原Metal，先确认桌面响应、25G83、新boot UUID、GA416 NG UUID及L3=6/80EU/10SS。
2. `tools/collect-metal-snapshot.py`是单次采集器：核对指定boot，封存实际完整bundle、所有hash、原生codesign、ps/RSS、vm_stat、已加载kext、现有dmesg及诊断目录元数据。它不循环、不提交GPU工作；只有显式`--vmmap`才执行一次vmmap摘要。每次输出必须新目录。
3. 正常使用时由用户选择几个时间点采样；记录相同boot/PID/主二进制hash和使用场景。新boot/WindowServer重启要另开序列，RSS不与footprint或heap块数混作一条曲线。
4. 先在独立目录对候选执行原生`codesign --verify --deep --strict --verbose=4`，再核对主二进制SHA和其他bundle文件。封存基线不等于最新现场全bundle；当前实装主文件若不再是`e3242693…`，停止套用旧包并重新审计。

## 需要限量复现时

仅用户在场、系统健康且同意该次执行后，执行一次8–16个空command buffer的有限最小复现，逐个等待完成并释放autoreleasepool；不自动重试、不运行上千次、不自动升级压力。前后在同一测试进程统计heap中归属`MTLIGAccelCommandBuffer._pPoshUsedAsTarget`的块；96KiB尺寸桶本身可能有其他分配，不能只按尺寸认领。限量样本没有清晰分配栈时记为未判定，不扩大负载。

## 修复后的验证

保留本机当前原bundle备份、包内restore以及原GA416引导。候选尚未部署。用户决定单因素切换后，仍使用原GA416引导；用户手动重启WindowServer所在系统，不同时切RTC。

先重复相同的低负载采样/有限复现，记录修复前后残留块及正常使用内存趋势；再验证Metal基础功能和既有单次R8流程。R8原脚本绑定旧boot、旧路径，不能直接重放，须重新绑定当前boot并保持一次性claim。GPU reset、新gpuRestart、WindowServer更换PID或无响应要单独记录并停止后续GPU测试。

当前状态：候选离线签名/差分/恢复包PASS；HP动态残留块对照、原生codesign、Metal/R8回归、修复后的长期观察均NOT_TESTED。POSH用户态泄漏不解释为pmap/wrong-zone已确认根因。
