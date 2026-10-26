# GA3.5：25G83驱动逆向与Fault诊断边界

私有离线研究目录。入口：[FINAL-REPORT.md](FINAL-REPORT.md)。准确驱动已取得，真实Fault采样仍阻塞；没有新增真实Hook/backend、部署或测试镜像。

## 报告

1. [精确二进制身份](25G83-BINARY-IDENTITY.md)
2. [Apple Forcewake调用图](APPLE-FORCEWAKE-CALLGRAPH.md)
3. [GT ACK/电源审计](GT-FORCEWAKE-AUDIT.md)
4. [Hang/Clear/Reset时间线及十问](GPU-RESET-TIMELINE.md)
5. [Fault协议/状态机/一致性安全](FAULT-CAPTURE-SAFETY.md)
6. [Hook ABI审计](HOOK-ABI-AUDIT.md)
7. [真实测试与复现](TEST-REPORT.md)
8. [下一步前提](NEXT-EXPERIMENT.md)

## 实际工件

- `inputs/macos-readonly/`：只读SSH取得的KC/plist原件及保留的首次超时部分文件；全部Apple专有内容仅本地私有。
- `analysis/kc/`：fileset、UUID、segment/section/symbol库存。
- `analysis/disassembly/`：重点函数逐条bytes、KC fileoff/VA、入口/符号、direct/indirect edges。
- `analysis/expanded/`：五映像完整符号上界片段语料，gzip JSON含原始bytes；它不是完整CFG证明。
- `analysis/cache-fixups.json`：format11链成员、静态stub/vtable候选，不猜动态receiver。
- `analysis/safety-callgraph.{json,dot}`：有证据callsites及未解indirect图。
- `reference/timeline-index/`：49个CSB/上下文/reset/watchdog相关片段及边界摘要。
- `diagnostic-src/`：独立默认关闭GA34核心逐字节副本，无真实接入。
- `audit/ga34-review/`：历史manifest/20项修复/独立构建回归。
- `audit/tool-review/`：DeepSeek初始反例、修复后closure；失败证据未覆盖。
- `audit/forcewake-binary/`、`audit/safety-review/`：关键二进制与隔离安全独立审查。
- `audit/main-fixes/before/`：修复前工具/分析快照及manifest。
- `logs/`：只读采集回执、测试/构建/逐字节核验日志。

## 校验与迁移

封存后执行`python3 -B tools/seal.py verify`只读核验全部文件和manifest自SHA；例外仅manifest自引用和两份封存收据，清单显式列出。需要再次分析时先复制目录，在新副本中重生成；不覆盖已封存证据。

迁移须私下传输整个本目录、原始历史捕获及其manifest，不可只复制Git仓库。本目录包含Apple二进制和私有证据，不公开上传。旧GA31/32/33、ISA-Lab、GA34均作为只读来源，不重放其历史硬件待办。
