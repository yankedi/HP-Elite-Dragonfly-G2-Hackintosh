# GA415：静默像素错误捕获与定位

当前：已捕获真实静默错误、交付有界Blit观察镜像；花屏根因 `ROOT_CAUSE_UNVERIFIED`。
进度与未验收项见 [FINAL-REPORT.md](FINAL-REPORT.md)，手动启动步骤见 [BLIT-OBSERVER.md](BLIT-OBSERVER.md)。

## 五个指定工具

| 文件 | 实际能力 |
|---|---|
| `tools/iosurface-pixel-probe.m` | CPU-only或单次显式GPU Command Buffer；独立阶段dump、资源描述、hash、时间线、一次性claim |
| `tools/desktop-capture.m` | CG窗口/显示元数据，授权后ScreenCaptureKit全屏/独立窗口；明确标记未知路径 |
| `tools/pixel-diff.py` | 有效RGBA像素精确比较、错误图样/旧帧参考、PNG/ROI/通道/alpha/重复块候选 |
| `tools/expected-pattern.py` | 独立重建8种数学参考图，不从实际输出生成Expected |
| `tools/build-darwin.sh` | 目标Mac原生严格编译、ad-hoc签名与hash；不执行GPU |

Python工具需要Pillow；CPU和探针结果必须区分。真实构建日志在 `reports/native-build-v2/`。

## 可以离线复核的真实捕获

`captures/case-{A,B,C}/gpu-{A,B,C}/` 是真实GPU输出，不是fixture：
包含input、独立验证过的Expected、IOSurface前后、直接Copy proxy、GPU输出、CPU输出和manifest。
实际执行stdout/stderr/exit也一并保存。没有收录Apple专有driver/SDK/KDK。

在仓库根目录，例如：

```bash
python3 ga415/tools/verify-capture.py ga415/captures/case-A/gpu-A --output /tmp/opencode/ga415-A-review.json
python3 ga415/tools/audit-actual-cases.py --capture-root ga415/captures --output /tmp/opencode/ga415-independent-review
```

输出路径必须不存在。第一条A应退出0；同样复核B/C应得到 `PIXEL_FAIL` 并退出1，这是已记录的真实失败。
第二套auditor使用独立线性索引构建Expected，不导入主verifier/expected generator。
上述均为离线读取，不提交GPU工作。

## CPU fixtures

`fixtures/pixel-tools/` 明确标为 `SYNTHETIC_CPU_FIXTURE_NOT_GPU_RUNTIME`：
24项检查包含有效像素/边界、单byte、alpha-only、行偏移/顺序、重复块、premultiply、
8种pattern、已知矩形和legacy tile候选。候选不认证真实资源布局。
`fixtures/native-cpu-capture-B/` 是真实CPU-only IOSurface种子，供metadata adversarial测试使用。
`fixtures/verifier-adversarial-result.json` 记录13项拒绝/分类检查。

如需重新检查比较工具，可使用新输出目录：

```bash
python3 ga415/tools/test-pixel-tools.py --output /tmp/opencode/ga415-new-fixtures
python3 ga415/tools/test-capture-verifier.py --cpu-capture ga415/fixtures/native-cpu-capture-B --output /tmp/opencode/ga415-new-verifier-checks
```

这些是CPU测试，不是GPU复现。既有测试已通过，无需为了读取结果再次执行。

## Mac构建与CPU-only模式

```bash
bash ga415/tools/build-darwin.sh /private/tmp/ga415-new-build
/private/tmp/ga415-new-build/iosurface-pixel-probe --cpu-only --case B --bpr align16 --output /private/tmp/ga415-new-cpu-B
```

CPU-only模式不调用MTLCreateSystemDefaultDevice，不证明GPU正确。
GPU模式需要显式 `--execute-once`、新claim与新目录；进程超时不取消GPU工作。
只有新的现场单例授权及启动期健康核验后才能安排，不在此提供自动case循环。

桌面工具可只读元数据：

```bash
/private/tmp/ga415-new-build/desktop-capture --metadata-only --output /private/tmp/ga415-new-metadata
```

真正截图涉及执行进程的屏幕录制权限。当前成功窗口配对复用了图形Terminal的系统截图权限；
不把它记作自编ScreenCaptureKit截图已实测成功。

## 报告入口

- [桌面/图层证据](reports/DESKTOP-ARTIFACTS.md)
- [IOSurface结果](reports/IOSURFACE-RESULT.json)
- [截图比较](reports/CAPTURE-COMPARISON.json)
- [根因候选](reports/ROOT-CAUSE-CANDIDATES.md)
- [已验证PLANES2定向panic修复](reports/PLANES2-RUNTIME.md)
- [Blit观察镜像审计](reports/BLIT-OBSERVER-AUDIT.json)

完整桌面截图、健康采集、panic/NVRAM和原生回读保存在本地 `private/`，默认不提交。
所有状态以真实收据为准，命令返回0不等于像素正确。
