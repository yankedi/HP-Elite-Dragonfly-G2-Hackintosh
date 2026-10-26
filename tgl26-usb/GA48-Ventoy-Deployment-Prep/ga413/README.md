# GA4.13 — Managed RT staged-boundary

**已完成一次 R6 实机采集：有效 `PIXEL_FAIL`。** 三个 CB 全部正常完成，GPU 有效像素正确，CPU 仍有 16,705 / 16,705 错误像素。

完整结论、SHA256、时序、健康窗口和下一步建议见 [FINAL-REPORT.md](FINAL-REPORT.md)。

## 文件

- `tools/managed-rt-probe.m`：从 GA4.12 派生，render／sync／copy 各一次、三个完成等待。
- `tools/build-darwin.sh`：原生严格构建和 CPU-only 验证；不运行 GPU 探针。
- `tools/verify-pixel-dump.py`：严格三 CB 门槛，复用 GA4.12 expected／像素／hash 验证。
- `tools/compare-boundaries.py`：新旧完整错误位置、通道、行与周期比较。
- `tools/test-boundary-verifier.py`：有意义的正常／故障 fixture。
- `tools/audit-workload-scope.py`：相同工作负载区域与显式操作次数审计。
- `tools/health-remote.py`：只读设备、文件版本、服务、reset 目录检查，固定此次 session。
- `tools/summarize-evidence.py`：从已保存证据生成可分享摘要并重算核对。
- `reports/`：已封存的实际结果。
- `private/`、`out/`：忽略提交的原件／fixture。

## 离线复核

以下只读取既有采集，不提交新 GPU 工作。需要本机保留的私有 dump：

```bash
python3 ga413/tools/audit-workload-scope.py
python3 ga413/tools/verify-pixel-dump.py ga413/private/r8-staged-boundary-capture
python3 ga413/tools/compare-boundaries.py ga412/private/r8-legacy-capture ga413/private/r8-staged-boundary-capture
python3 ga413/tools/summarize-evidence.py
```

verifier 的退出码 1 在本次实测代表有效 **PIXEL_FAIL**，不是采集 INVALID（退出码 2）。比较器退出 0 代表对照有效，不代表 CPU 像素 PASS。生成器拒绝以不同内容覆盖封存报告。

纯 CPU fixture 可用新的输出／报告路径执行：

```bash
python3 ga413/tools/test-boundary-verifier.py --report ga413/out/new-fixture-report.json
```

本轮一次性 GPU 标记已消费，不能自动重跑；后续实际 backing 取证属于新的受控实验。
