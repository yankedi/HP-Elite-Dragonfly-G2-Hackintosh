# Gen11 → Gen12 Shader ISA（任务 L/M/N）

## 参考项目（holdmysocks/latitude-7320-detachable-hackintosh）

LAYER4.md 记录 GA4–GA11：Gen11 shader 在 TGL EU 上无法执行是 draw 挂死的根因；
`igfxtglxl=1` 逐 batch 翻译后 draw 可见（GA9+）；残余 hang 为未覆盖 shader 与驱动
fast-clear/resolve。关键差异（LAYER4.md §5 + tgl_xlate.c）：

| Gen11 | Gen12 |
|---|---|
| MOV opcode 0x01 | 0x01 = sync；MOV = 0x61 |
| 无依赖注解 | 软件 scoreboard：每条 `@1`，send 置 token，消费者 `$n.dst`/`sync.nop`，跳转前等待 |
| `sends/sendsc`（拆分 send） | `send/sendc` 双 payload 源 |
| 扩展描述符位仅经 `a0.n` | 常量折叠为立即数或寄存器形式 |
| `mad acc0:NF`（平面评估累加器） | 使用内核未命名的通用寄存器（float） |
| `mov` 到 ARF 0xF0（thread switch） | `mov null, 0` |
| compacted | 逐条重新 compact；部分指令无 Gen12 compact 形式（内核增长，至下一 64B 边界） |
| 跳转距离 | 按新布局重算（jmpi 相对下一条，其余相对自身；join 0x2F 特殊） |

其他方面：SWSB、寄存器区域编码、SEND 描述符（sampler/URB/RT）、SIMD8/16/32、
thread payload、URB、CCS/fast-clear/resolve 差异见 LAYER4.md §5/§6。

## 本项目的直接证据（GA3.2b 捕获）

- 提取：VS kernel（记录 1，VA 0x4271D3C0，7,232B）与 PS kernel（VA 0x4271D040，8,128B）。
- **Mesa Gen11 反汇编器完整解码**（参考项目 g11to12 工具，Mesa 23.3.6）：
  - VS：24 条指令，mul/mac/mad 矩阵变换 + URB send（EOT）；
  - PS：11 条指令，mad/send（sampler sample，Surface 1 Sampler 0）/add.sat/
    RT write（sendsc EOT）。
- **Gen12 反汇编器无法解析这些字节**（解释为 Gen12 时工具崩溃）；反之，
  `xlate` 翻译输出 24/11 条 Gen12 指令，**Mesa Gen12 validator 通过**
  （`analysis/shader/*-xlate.txt`）。
- 结论强度：**强**。捕获的 kernel 是 Gen11 机器码，这就是 VS/CS 无法完成、
  PIPE_CONTROL 永不结束的直接原因；与参考项目结论一致。

## 离线工具（任务 M）

- 构建：Mesa 23.3.6 稀疏克隆 + `setup.sh` + `build.sh`（Linux 适配：clang 数组展开用 zsh；
  新增 `-DUTIL_ARCH_LITTLE_ENDIAN=1 -DUTIL_ARCH_BIG_ENDIAN=0`）。
- 命令：`g11to12 dis11|dis12|xlate <file>`；日志在 `analysis/shader/`。
- 验证：真实样本 24+11 条 Gen11 指令解码；翻译后 Gen12 校验通过。
- GA3.3 **未启用**任何翻译（igfxtglxl 不存在于本分支）；工具仅用于离线分析。

## 未来翻译器架构（任务 N，设计要点）

候选方案对比：内核 hook 内逐 batch 翻译（参考项目路线，成熟但有 kernel 风险：
GA10 machine check 来自读 stolen 占位页） vs shader 首次提交时翻译（需要 hook 提交点）
vs 用户态离线翻译（不改变内核风险面，但需 IPC/文件通道与重签名）。
推荐下一阶段（GA3.4+，非本轮）：
1. 以物理地址+内容哈希为键的缓存；未知指令严格拒绝；翻译失败即跳过（不写回）；
2. 只读取 pmap 验证过的 RAM（沿用现有门禁），**永不**触碰 stolen/占位页（参考项目 GA10 教训）；
3. 超长/跨页 kernel：按 64B 对齐边界增长，必要时压缩；上限 700KB（参考项目 0004g）；
4. 可观测指标：翻译/拒绝计数、拒绝原因、耗时，写入现有记录。
不得假设"只改 MOV opcode"足够；SYNC/SWSB/send 重编码与跳转布局都是必需的。
