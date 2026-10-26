# GA416 运行验收证据

结果入口：[GA416-DESKTOP-FIX-RESULT.md](GA416-DESKTOP-FIX-RESULT.md)。

2026-10-25 实际身份是旧 GA415-PLANES2（80EU/10SS，L3 回退 8），不是已证明的 Fuse-L3 修正版。桌面残缺保留；一次既有 R8 回归由两套独立 Expected 审计通过。新 L3 因果 A/B 尚未验收。

- `reports/`：运行拓扑、桌面对照、R8、健康/旧故障、文件完整性索引。
- `images/`：真实图像的对照排版与无损 ROI，均不是合成正确参考。
- `private/`：原始 SSH 回执、诊断归档、NVRAM、截图/元数据、R8 dump 和二进制上传记录；Git 忽略。
- `tools/health.py`：固定当前 boot 的只读健康采集。
- `tools/capture-*.command`：图形 Terminal 单次场景采集脚本。
- `tools/run-r8-once.py`：本次一次性 launcher，授权已使用，现有 claim 保留。
- `tools/summarize-evidence.py`：本地 CPU-only 复核与报告生成，可复现分析，不连接 HP。

原有 GA414/GA415 文件与旧 claim 保留；本轮未修改驱动源码或镜像。
