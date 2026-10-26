# 09 · 严格离线原型设计与边界

实现 `translator/offline_translate.py`，CPU用户态，依赖固定IGA二进制。输入有1MiB上限；显式8/16B framing；IGA按ICL解码→IR字段审查→目标IGA重编码→目标IR对比→二进制round-trip。没有opcode字节替换，没有GPU访问，没有内核Hook。

## 支持与真实结果

* 支持：直接GRF/立即数，MOV同类型f/ud/d/uw/w；ADD/MUL浮点；predicate、mask、execution size/offset、region、src modifiers、saturation保留且逐字段比对。8B compact通过真正ICL decoder展开，目标使用native16B，长度可变化。
* IGA `-Xauto-deps`为独立指令末尾生成`(W) sync.nop null {@1}`，代码显式核查此drain的op/subop/es/wren/src/regDist，不默许任意额外指令。完整调度不是“自动就正确”；本原型只验证隔离片段。
* **PS0 4/11、VS 15/24、PS KP1 8/29、PS KP2 4/15 条**得到 `ROUNDTRIP_VALIDATED`，共31个独立单位，均有源偏移→目标segment和offset映射。输出在`analysis/translated-{ps,vs,ps-kp1,ps-kp2}/unit-*.bin`，各自独立，**不拼成shader**。
* 整program返回`UNSUPPORTED`及非零退出；每个不支持项包含source offset、结构化错误代码与原因。不丢弃未知后继续生成“成功shader”。

## 拒绝清单

| 类型 | 处理 | 原因 |
|---|---|---|
| SEND/SENDC/SENDS/SENDSC/EOT | 全拒 | 保护消息和终止语义，不猜payload/descriptor |
| MAD/MAC与NF | 全拒 | accumulator/中间精度及隐含依赖尚未证明 |
| acc/debug/其他ARF | 全拒 | 不把debug Switch删掉，也不替换为GRF/null |
| Branch/JMPI/IF/ELSE/ENDIF/HALT等 | 全拒，不copy旧偏移 | 目标长度变化时必须整体重定位；不支持时是结构化阻塞，而非错误偏移输出 |
| mixed-type MOV、integer ADD/MUL | 全拒 | 类型转换/宽度溢出语义未证明 |
| 非支持option、未知/invalid opcode | 全拒 | 无静默fallback |
| 截断、空、超1MiB | framing前置拒绝 | 有界输入，不越界 |

本机主要阻塞：PS0的4条MAD（含NF）、debug Switch与两个SEND；VS有acc0目的/来源、MAC/MAD、debug Switch、URB SEND。另两个PS入口也按相同规则拒绝NF/acc/message。逐项offset见report.json。

独立审计后的强化：主指令不允许出现未经预期的SWSB（UNEXPECTED_MAIN_SWSB），drain仍逐字段核查；这不等于全shader依赖等价。IGA超时/启动失败/无效JSON或schema、源ASM与JSON边界不一致均返回结构化拒绝；CLI输入/输出IO错误亦为结构化IO_ERROR。已加故障注入回归，见test_review_fixes.py。

## 分级与未来路线

`DECODED_ONLY`=解码，`ENCODED`=发射，`ROUNDTRIP_VALIDATED`=再解码且目标往返，`STATIC_SEMANTICS_CHECKED`需额外数学/依赖/message证明，`UNSUPPORTED`=明确拒绝。当前31个单位只到ROUNDTRIP_VALIDATED（附IR字段相同检查），不越级称完整静态语义正确。

下一阶段先解决NF/accumulator精度、debug Switch语义、URB/sampler/RT消息、跨完整CFG的SWSB；建立IR解释器/属性测试，分支重定位需对全部源边界与目标labels二遍布局；输出变长不能就地覆盖旧kernel。未知/超长/缺页保持fail-closed。参考上游首4KiB cache和半写无回滚均不可作为未来方案的默认设计。

缓存应至少以完整源内容hash、输入长度、平台、context mapping generation、翻译器版本为键，源页alias/复用须失效；本轮不做物理页缓存或写回。任何将来受控实验须独立授权、完整shader语义通过后才设计，不改变现有GA3.3。
