# 08 · 上游翻译器：本机真实输入评估

来源及GA4–GA11完整审计另见 `08-upstream-source-audit.md`。固定上游 `1010490d3421628c9d6fd0bd518b6c4b6f8ee33c`；Mesa23.3.6 `863338275d915e867319c3690ffd3272b06303c3`。`tools/mesa-eu/adapter/` 是隔离的Linux构建适配副本（含上游 acc1 emitter patch 和 stub），不是 pristine Mesa。两次构建日志保留，首次缺a1 header后补齐重试成功；原树未变。

运行 `bash tools/mesa-eu/build-adapter.sh`、`python3 tools/evaluate_upstream.py`。

额外GCC16.2适配构建：`CC=gcc OUT=build-gcc EXTRA_FLAGS='-std=gnu11 -include unistd.h' bash tools/mesa-eu/build-adapter.sh`（在提供GCC的Nix shell内）。PS/VS两输出与Clang逐字节相同，回执 `analysis/mesa-gcc-comparison.json`。首次默认C23/C11线程typedef冲突、第二次POSIX read/close prototype缺失均留日志，不把初始失败抹去。

`python3 tools/verify_mesa_sources.py` 实际逐文件对照pristine源码：差异仅两个stub头 `brw_compiler.h`/`brw_shader.h` 与 `brw_eu_emit.c` 的acc1断言补丁，其余拷入的Mesa EU源码逐字节相同；24个适配/依赖源摘要和完整diff在 `analysis/mesa-adapter-provenance.json`。

| 本机入口 | 输入/输出长度 | 输入/目标指令数 | 上游返回 | Mesa Gen12 validator | 独立IGA Gen12解码 | IGA目标二进制round-trip |
|---|---|---|---|---|---|---|
| PS0 | 152 / 152 B | 11 / 11 | 成功 | passed | 退出0，无诊断 | 逐字节相同 |
| VS | 288 / 288 B | 24 / 24 | 成功 | passed | 退出0，无诊断 | 逐字节相同 |
| PS KP1 | 440 / 440 B | 29 / 29 | 成功 | passed | 退出0，无诊断 | 逐字节相同 |
| PS KP2 | 216 / 216 B | 15 / 15 | 成功 | passed | 退出0，无诊断 | 逐字节相同 |

真实stdout/stderr在 `logs/upstream-*`；输出 `analysis/upstream-{ps,vs,ps-kp1,ps-kp2}-gen12.bin`；逐条 source→target offset/operand/SWSB 映射及差异在 `analysis/upstream-semantic-review.json`。四份程序无branch，顺序映射均保持，末条EOT仍在；生成器强制source/target解码成功及一对一指令数一致，禁止静默zip截断。

## 仍不能称为等义完整 Shader

* PS的 `acc0:nf` 被替换为 `r122:f`：NF中间精度/舍入/accumulator语义与GRF浮点不同，**validator不检查数学等价性**。
* 两个program的debug ARF MOV `{Switch}`被替换为 `mov null,0`，原效果被主动改变。
* Gen11 split SEND转Gen12 SEND：descriptor/SFID位重编码、payload length和RT/URB约定需要跨代语义核验；目标可解码只证明可表达，不证明消息正确。
* 插入/编码的`@1`和`$n`不同于Gen11依赖机制；本样本无分支减少CFG风险，但仍须证明GRF/accumulator/消息读写依赖完备。

因此上游输出的等级是 **ROUNDTRIP_VALIDATED（编码）**，不是整个shader的STATIC_SEMANTICS_CHECKED，更不是硬件执行正确。没有逐指令“解析失败”项不等于无语义阻塞。实际严格原型拒绝清单见report09。

## 前端安全限制

原上游 `g11to12.c` 的disassemble循环只检查剩8B却可读16B，且直接把输出缓冲当 `disasm_info*` 传validator；旧dis12对原始Gen11字节曾崩溃。本轮独立IGA用于非法/截断输入；上游前端仅给已核验的完整ICL有界程序。Sanitizer对本机正样本的结果单列，不把它推广为任意输入安全。
