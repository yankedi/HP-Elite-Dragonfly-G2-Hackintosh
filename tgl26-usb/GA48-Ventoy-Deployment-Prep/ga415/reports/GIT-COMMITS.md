# GA415 本地提交索引

分支：`ga415/silent-pixel-capture`。均为本地提交，本轮未push。

| 完整SHA | 单元 | 实际验证 |
|---|---|---|
| `d03cae1c61e92adf6e1bf5c3993c83ba7c1d66f9` | 精确25G83 IOSurface ABI与PLANES2独立镜像 | donor/KDK UUID与字节、CPU plane布局、签名/镜像/USB回读 |
| `9da68e7bd5a609dec71478f46fbbe37b66afd43f` | 修复前实际除零复现、修复后Memoji定向验收 | 独立panic/NVRAM、同boot/PID、308.619秒观察、花屏仍存在 |
| `83fde64b15475443743f2ef16d9c8477ae09bdbf` | 五工具、真实A/B/C捕获、fixtures/原生构建日志 | 独立Expected与两套auditor、24CPU/13adversarial、原生源码hash、导出hash一致 |
| `cdeac55f369467fb47b1892fa3d3a16996e495bd` | 有界只观测Blit hook、构建签名、独立镜像交付 | 802次CPU ASan/UBSan合同、tail-forward反汇编、100文件原生只读回读、整盘hash |

本索引与新的桌面ROI/四份汇总报告/完整性审计同一提交；该提交自身SHA可通过
`git log -1 --format='%H %s' -- ga415/reports/GIT-COMMITS.md`查询。

以上提交不声称观察版已经启动、根因已经证实或花屏已修复。
