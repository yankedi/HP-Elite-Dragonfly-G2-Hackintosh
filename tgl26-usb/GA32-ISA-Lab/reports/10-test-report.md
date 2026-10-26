# 10 · 实际测试与验证手段

## 已执行回执

* `logs/test-translator.txt`：**38个 unittest 方法，0失败**，含多个正/负样本subtest。实际矩阵 `synthetic_samples` 为**22正/21负/1未知**项；另有length/eligibility/故障注入/真实shader组，不能混作同一分母。矩阵与当前translator/IGA源码hash在 `tests/translator-coverage.json`；方法数不能冒充独立硬件实验数。
* `logs/test-evidence.txt`：**8项原字节、偏移、CFG/EOT、真实counterexample及ring断言通过**。
* `analysis/native-matrix.json` 与 `logs/native-matrix.txt`：**44次原生调用**（Clang/GCC/Clang-ASan+UBSan三套IGA ×14输入/平台案例 + Mesa sanitizer两份真实转换）；0 sanitizer诊断，14组跨编译器stdout hash一致。
* 另行构建并执行Mesa参考转换器GCC16.2版，PS/VS两个目标输出与Clang版**逐字节相同**，`analysis/mesa-gcc-comparison.json`。首次GCC默认C23导致旧Mesa C11兼容层和新glibc once_flag冲突，指定gnu11后暴露read/close未声明，再加`-include unistd.h`构建成功；三次真实构建日志均保存。没有修改pristine Mesa或上游转换规则。
* `logs/tool-smoke-iga-*.txt`：原版官方IGA JSONv2示例的SEND `{EOT,A@1}`被固定版工具拒绝；改为`{EOT}`后通过。i-g-t Gen12参考程序、compact长度变化、未知指令和SWSB有效/无效组合的实际CLI输出。
* 最终 `logs/test-all.txt`：**79项全部通过**，38 translator+22 batch+8 evidence+11 review回归。新回归针对真实审计问题：工具timeout/OSError/JSON/schema/text缺失结构化拒绝、主SWSB异常、join/do、位紧凑group、stencil格式与draw长度、额外两个PS入口。
* 最终扩展矩阵 `analysis/native-matrix.json` / `logs/native-matrix.txt` 为**64次调用、0 sanitizer诊断、20组IGA跨build stdout相同**（四入口×三平台案例+8工具样本，乘3版IGA，再加4份Mesa sanitizer转换）。前述44/14是hp-093时的初版检查点；最终交付计数以64/20为准。

## 25类需求到可执行证据

| # | 类别 | 实际测试/样本与期望 |
|---|---|---|
| 1 | 普通EU | translator positive `mov_native_f`/`add_f`/`mul_f`，目标IR与binary往返 |
| 2 | compact | `mov_compact_f`8B源→native目标；真实VS/PS compact counterexample |
| 3 | 混合 | `mixed_stream`：8+16+8B三个单位，映射/源边界一致，非拼接shader |
| 4 | opcode差异 | evidence真实MUL同opcode但语义不同；isa-diff含MOV→SYNC；negative MAC/MAD拒绝 |
| 5 | type差异 | f/ud/d/w/uw正样本，ub/intADD/mixed-typeMOV负样本 |
| 6 | register region | scalar、4x4、8x8、16x16、dst stride变体正样本；ARF/indirect拒绝 |
| 7 | immediate | f/hex-ud正样本；inf/qNaN payload未知拒绝 |
| 8 | predicate | f0.0、W、W&f0.0，IR字段保留 |
| 9 | SIMD | 1/4/8/16，源目标es相同；真实错义MUL es8→16被差分检测 |
| 10 | branch | 8种实际IGA可组装branch全拒，不复制错误offset |
| 11 | SEND | 无EOT SEND与EOT SEND都拒绝；真实message留给上游单独评估 |
| 12 | SWSB | 目标drain形状/依赖报告及regDist/src篡改故障注入 |
| 13 | EOT | 真实PS0/VS末条断言；EOT组合保护拒绝 |
| 14 | unknown opcode | 实际零/FF/未知字节，IGA输出/退出留档；translator白名单拒绝 |
| 15 | invalid instruction | native矩阵非法bytes，prototype SOURCE_INVALID或OPCODE_UNSUPPORTED，非成功输出 |
| 16 | invalid length | 空/超限/长度不齐拒绝，真实variable framing |
| 17 | truncated | compact<8B与native不足16B显式TRUNCATED；IGA本身可能exit0，所以独立前置检查必要 |
| 18 | buffer overflow | 1MiB+1输入拒绝、CLI bounded read；native后端ASan/UBSan真实运行。Python检查不能冒称C所有路径安全 |
| 19 | out-of-range branch | IGA实际拒绝越界JMPI；in-range branch仍由relocation gate拒绝 |
| 20 | address translation | test_batch的地址对齐/64位溢出、SBA/KSP位field；evidence共享窗口断言；**无原PTE重走测试**，缺捕获 |
| 21 | batch length | test_batch对header长度/bias/截断/固定长度矛盾的正负断言 |
| 22 | false-positive headers | test_batch payload中嵌入header扫描候选，但可信顺序解码不把payload升级为命令 |
| 23 | round-trip mismatch | target operand篡改→SEMANTIC_ROUNDTRIP_MISMATCH；目标重编码bytes损坏→BINARY_ROUNDTRIP_MISMATCH |
| 24 | 参考已知样本 | 官方IGA JSONv2原文与修正版、i-g-t Gen12 fill、上游本机转换结果；不是只自编正样本 |
| 25 | 本机真实PS/VS | PS0 4/11、KP1 8/29、KP2 4/15、VS15/24共31独立单位往返；完整shader UNSUPPORTED且full_shader_emitted=false |

## 防过拟合与准确范围

只有一份成功THAG、两个明确入口。真实PS/VS是一个样本族，不应以重复跑编译器放大样本独立性。合成矩阵涵盖多种opcode/type/region/SIMD/predicate/immediate、主动故障注入和负样本；官方/参考样本提供另一来源，但仍不覆盖全ISA。

* **正样本**：预期字段相同与往返；**负样本**：精确错误代码/边界拒绝；**未知样本**：解码成illegal或消息/NF语义未证实。分类在JSON保存。
* **STATIC_SEMANTICS_CHECKED未授予完整shader**：31单位只到ROUNDTRIP_VALIDATED（附operand比对）；没有硬件执行验证。
* ASan/UBSan实际编译并运行C/C++后端，不把Python单测称为sanitizer；GCC/Clang两版输出相同也不排除共同编码或规范理解问题。
* Mesa原上游front-end在任意invalid/truncated输入下存在未修的安全局限，本轮仅给已证有界ICL正样本；严格原型和非法测试使用独立IGA与Pythonframing。
* `tests/samples/run-smoke.sh`是诊断采集器，保存各命令exit，包含预期失败，脚本自身exit0不是“全部case通过”的判据。

最终独立审计见 `11-independent-audit.md`；所有状态必须受上述证据范围约束。
