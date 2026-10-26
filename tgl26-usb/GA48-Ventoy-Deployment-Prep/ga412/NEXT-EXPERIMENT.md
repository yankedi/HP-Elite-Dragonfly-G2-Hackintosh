# 唯一下一步：只改变 Command Buffer 边界

## 已完成的基线

2026-10-24 07:58（目标机+0800）唯一R8 legacy已经执行，完整数据有效：GPU expected0错、CPU expected16705像素错。不要将它写成待执行，也不要清除本轮once-claim后重跑。

实际运行过的程序与参数如下，**这段是归档命令，不是要求现在再次执行**：

```sh
BASE=/private/tmp/ga412-r8-build-FEAA8C24
GA411_TRACE_DYLIB="$BASE/repro-build-v2/trace-managed-cpu.dylib" \
  "$BASE/repro-build-v2/managed-rt-probe" R8 legacy "$BASE/r8-legacy-capture"
```

实际执行还有本地`ga412/private/r8-once-started.json`和远端`once-execution-claim`双重一次性标记。程序只写用户态新产物目录，不改系统文件；它会创建Metal设备并提交一个显式GPU CB，CPU getBytes也会经过driver自然lock/resolve链。

## 下一次只改什么

固定R6软件、R8输入、257×65、RGBA8 Managed、shader、descriptor、source upload、shared输出分配、一个render/一次sync/一次copy、observer版本及快照步骤，只改变分组与等待：

```text
已采集legacy：
  CB1: render → synchronizeResource(target) → copy(target → shared buffer)
  wait CB1 → GPU深拷贝并落盘 → CPU getBytes → CPU落盘

建议候选（尚未实现/编译/运行）：
  CB1: render                           → wait CB1
  CB2: synchronizeResource(target)      → wait CB2
  CB3: copy(target → same shared buffer)→ wait CB3
  GPU深拷贝并落盘 → CPU getBytes → CPU落盘
```

这个因素包含分组及对应完成等待的改变；不把等待次数当成另一个未经说明的因素。

**不使用GA4.11旧staged作为纯边界对照：它还多了一次pre-sync GPU copy。** 当前交付的GA4.12可执行文件故意只接受R8 legacy，不能给它传一个未实现的staged参数并声称候选已就绪。

先在独立诊断源码中实现上述唯一候选、完整原生编译链接/CPU回归，再单独授权一次实机运行。此文是下一实验设计，不是已验证候选或立即执行指令。

## 能区分什么

- 三CB候选GPU继续正确且CPU由FAIL变PASS：支持错误对命令分组/完成等待边界敏感；不能单独证明某个kernel fence或NOCCS3就是根因。
- GPU正确、CPU仍错：这种边界改变不足以恢复CPU读回；后续关键缺口仍是同资源内核dirty/AUX/CCS与CPU backing/布局的关联。
- GPU也错或任一CB失败：保留原始数据与status/error，不把结果当修复；CB未完成时标INVALID。
- 不能根据本候选单独区分内核CCS提交被跳过、CPU布局转换错误和隐式copy转换。缺什么就继续标NOT_OBSERVED，而不叠加压缩补丁。

## 风险、时限和停止

- 后续11:10只读回执已发现同一R6的新reset家族，详见[离线分析](reports/OFFLINE-CAUSE-ANALYSIS.md)。07:58前置健康不能沿用为未来候选许可；当前不执行该候选，恢复实机实验前重新核实健康与恢复条件。
- 历史已有RCS hang/reset及WindowServer watchdog，最坏已知风险包括桌面/SSH失去响应，用户可能需物理重启或Recovery。保活和30秒alarm不能取消卡住的GPU或保证SSH可用。
- 候选仍应单进程、单用例、30秒进程alarm，SSH外层45秒时限；任一超时、失联、reset/watchdog立即停止，不自动重试或恢复。
- 建议记录每个CB完成callback、wait及error；三个CB全Completed、无error才接受像素结果。运行后做一次只读健康核对，不能把一次无hang写成长稳。
- 不需要为运行探针常规进入Recovery；回退介质必须事先可见。VESA只改变启动显示路径，不能撤销已安装11组件/AuxKC；不把它当完整系统恢复。
- 所有新数据保存全新目录，独立GPU/CPU/expected各83200字节，正常行pitch1280，padding排除。保留stdout/stderr/exit及失败部分产物。

## 当前即可复用的CPU-only流程

macOS上保留仓库`ga412/tools/`结构后，使用一个全新构建目录：

```sh
bash ga412/tools/build-darwin.sh /private/tmp/ga412-new-cpu-build
/private/tmp/ga412-new-cpu-build/inspect-texture-abi \
  /Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsMTLDriver \
  /private/tmp/ga412-new-cpu-build/trace-managed-cpu.dylib
```

以上只构建/CPU测试、读取并在自身进程验证ABI，不执行probe或GPU workload。路径已存在时换新的名字，保留旧证据。

NixOS本地可随时复核已有实机数据：

```sh
python3 ga412/tools/verify-pixel-dump.py ga412/private/r8-legacy-capture
# 本次真实数据预期退出1、PIXEL_FAIL，不是测试脚本故障。
python3 ga412/tools/test-pixel-verifier.py \
  --report ga412/out/repeated-cpu-regression.json
# fixture目录自动使用新名字，之前失败/成功日志都保留。
```

独立expected生成（需要全新输出目录）：

```sh
python3 ga412/tools/expected-pattern.py ga412/out/new-independent-pattern
```

本次实机数据及自产Mach-O均已保存到本地`ga412/private/`，未来实验不依赖原`/private/tmp`目录永久存在。不要把合成fixture的PASS当成真实GPU结果。
