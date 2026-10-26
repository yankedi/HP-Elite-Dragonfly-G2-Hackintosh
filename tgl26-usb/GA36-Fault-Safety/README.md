# GA3.6 · Fault Safety & Capture Reliability

**已纠正可得GA33源码中的CAS writer门控与失败终态，交付并发CPU核心及准确25G83有界路径证据；真实Gen12 Fault采样仍BLOCKED，实机审批NO。**

入口：[FINAL-REPORT.md](FINAL-REPORT.md)（15问、11状态）、[NEXT-EXPERIMENT.md](NEXT-EXPERIMENT.md)（最小缺口与回滚）、[continuation.md](continuation.md)、[state.json](state.json)。

- TrackA：CAS-ROOT-CAUSE、CAS-FIX.patch、CAPTURE-PIPELINE、TEST-REPORT；baseline为原三文件副本，candidate为独立修正及无硬件CPU核心。旧GPU捕获在candidate强制关闭。
- TrackB：五份请求/引用/PM/reset/候选点报告，24函数精确bytes/VA/fileoff/UUID/SHA，未解析indirect保留。
- TrackC：GA34兼容108B核心、九条件四值default-deny gate、真实CPU构建及within-sample torn-tuple反例，无真实reader。
- audit：独立审查、closure及已纠正工具副作用；reference：历史来源清点与固定上游ThreadCall契约。
- logs：实际编译测试/验证；manifest为本目录私有工件及外部历史来源逐文件SHA256。

封存后仅运行只读核验：

```sh
python3 -B tools/seal.py verify
```

重跑构建/分析前复制到新私有目录。编译命令见track-a/TEST-REPORT.md及track-c/run_tests.sh。Apple专有bytes/派生片段与私有raw输入不公开；迁移须私下携带本目录及GA35 KC、GA34/GA33/GA32引用工件，单独Git仓库不够。本轮没有发布、提交或部署。
