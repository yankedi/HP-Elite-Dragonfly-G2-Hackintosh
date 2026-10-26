# GA38 独立敌手 / 变异体 oracle

本目录由子代理独立编写，只属于 `tests/oracles/` 与 `tests/mutants/` 两个目录，
不修改任何其它代码、状态或历史（GA32–37、`corpus/`、`ir/`、`dependency/`、
`validator/`、`tools/` 一律只读，原始候选字节保持原样）。

## 1. 目标

为主代理的语义 IR / 消息合同 / 调度（SWSB-SBID）/ 12 层比较提供**独立期望值**：

- 期望值由**原始字节、固定版本 Intel IGA 汇编器/反汇编器、Intel IGA 源码规则**人工编写；
- **不导入**主代理任何模块（`common` / `semantic_ir` / `message_ir` /
  `dependency_graph` / `compare_program` / `gen12_schedule_check`），
  也不复制主分析器输出作为期望；
- IGA 只用于**物化字节变异体**与**独立校验**变异体能否解码（合法/非法），
  以及记录命令与哈希；不用于生成期望语义。

固定版本：IGA `c36a504a4e6c68030c3302646aa396b8b59b22cb`，
Mesa `863338275d915e867319c3690ffd3272b06303c3`。

## 2. 目录

```
tests/oracles/
  generate.py    可复现生成器（仅用标准库 + 固定 IGA 子进程）
  oracles.json   机器可读 oracle（见第 4 节 schema）
  ERRATA.json    ERRATA-1 修正叠加层（见第 9 节）
  checkpoint/    修正前原始副本（oracles.v1.pre-errata.json / generate.v1.pre-errata.py）
  README.md      本文件
tests/mutants/
  M*.bin S*.bin T*.bin N*.bin   变异体/负例字节（不改 corpus）
  asm/*.asm                     汇编源归档（asm/synthetic 方法）
  ir/F01-…json                  伪造 IR fixture（deleteimplicitdependency）
```

## 3. 复现

```sh
python3 -B tests/oracles/generate.py
# 或指定 IGA:
python3 -B tests/oracles/generate.py --iga /path/to/iga64
```

`generate.py` 只读取 `corpus/` 与固定 IGA，只写 `tests/oracles/`、`tests/mutants/`。
重新运行得到相同字节与相同 `sha256`（汇编器固定版本、无时间戳）。

变异体构造方法：

- `asm`：用 IGA 反汇编基准程序 → 文本级单点替换 → IGA 汇编回字节；
  归档改写后的 `.asm`；记录 `byte_diff`（偏移/原值/新值）。
- `bytes`：直接对候选字节切片/置位（截断、illegal compact）。
- `synthetic`：内嵌最小汇编程序并汇编（实际候选无法表达的类）。
- `ir_fixture`：人工伪造 IR JSON（非机器字节），用于 implicit dependency。

## 4. `oracles.json` 主要键

- `schema_version`, `generated_by`, `title`
- `independence`：独立性声明、IGA 角色、pin、iga 二进制路径
- `status_categories`：`COUNTEREXAMPLE` / `UNKNOWN` / `REJECTED` / `CHECKED` 定义
- `corpus_reference`：每个基准程序的 `path/sha256/bytes/platform/eu_window_offset`
- `required_classes` / `covered_classes` / `missing_classes`
- `mutants[]`，每条：
  - `id`, `class`, `method`, `file`, `sha256`, `bytes`
  - `construction`：基准路径/哈希、平台、`eu_window_offset`、IGA 命令、patch、asm 归档
  - `byte_diff`：`[[offset, old, new], …]`
  - `target`：目标指令偏移等坐标
  - `expected_field_change`：期望**解码字段**变化
  - `expected_detection`：`layer` / `status` / `primary_rule` / `detail` / `assumptions`
  - `iga_decode_receipt`：IGA 命令、exit、stdout/stderr 哈希、解码出的指令摘要
  - `notes`
- `negative_fixtures[]`：同结构（负例）
- `unknown_sfid_resource_cases[]`：必须保持 UNKNOWN 的场合
- `hardware_validated`：恒为 `false`

## 5. 变异体与期望（核心表）

基准：`PS0/PS-KP1/PS-KP2/VS` = Gen12 候选（platform `12p1`），
`PS0src` = Gen11 源（platform `11`，`eu_window_offset=64`）。

| id | 类 | 基准/偏移 | 字节变化(offset:old→new) | 期望字段 | 期望类别 / 规则 |
|---|---|---|---|---|---|
| M01 | deletewait | PS0 @0x60 | 97: 0x20→0x00 | 去掉 `{$0.dst}` | **COUNTEREXAMPLE** / SEND-RESPONSE-WAIT |
| M02 | reducepayloadlength | PS0 @0x50 | 88: 0x0c→0x04 | desc Mlen 1→0 | **COUNTEREXAMPLE** / SEND-CARRIER（并触发 MESSAGE_LENGTH_CARRIER_MISMATCH） |
| M03 | SFIDchange | PS0 @0x50 | 91: 0x20→0x60 | SFID SMPL(2)→URB(6) | **COUNTEREXAMPLE** / SEND-GENERATION-CONTRACT |
| M04 | responseLengthchange | PS0 @0x50 | 86: 0x24→0x44 | desc Rlen 4→8 | **COUNTEREXAMPLE** / SEND-CARRIER |
| M05 | regionchange | PS0 @0x00 | 12: 0x05→0x25 | src2 子寄存器 `sr` 0→1（rgn 不变） | **COUNTEREXAMPLE** / EU-REGION |
| M05b | regionchange | PS0src @0x00 | 11: 0x07→0x47 | 已知 GRF src1 `sr` 0→1（dst 仍 `acc0:nf`） | **COUNTEREXAMPLE** / EU-REGION（NF 不得掩盖已知操作数 region） |
| M06 | earlyEOT | PS0 @0x50 | 84: 0x00→0x04 | 非末条 SEND 置 EOT | **REJECTED** / EOT_FRAMING（两条 EOT） |
| M07 | executionSizechange | PS0 @0x60 | 98: 0x03→0x04 | es 8→16 | **COUNTEREXAMPLE** / EXECUTION-SIZE |
| M08 | ACCchange | PS0 @0x00 | 6:0x04→0x00,7:0x7a→0x20 | dst GRF→ACC | **UNKNOWN** / EU-ACC-NF（ACC 精度/打包无证据） |
| M09 | predicatechange | PS0 @0x00 | 3: 0x80→0x11 | 谓词 `~f0.0` | **COUNTEREXAMPLE** / MASK-PREDICATE |
| M10 | debugSwitchchange | PS0src @0x10 | 17: 0x80→0x00 | 清除 `{Switch}` | **UNKNOWN** / EU-DEBUG-SWITCH（仅控制字段差异，不声明硬件语义） |
| M11 | deletewait | PS-KP1 @0x130 | 305: 0x20→0x00 | 第二个响应消费去等待 | **COUNTEREXAMPLE** / SEND-RESPONSE-WAIT |
| M12 | earlySBIDreuse | VS @0x110 | 273: 0x91→0x90 | 第二条 URB SEND 复用 SBID0（均为空响应） | **UNKNOWN** / SBID-REUSE-SYNC-UNPROVEN（K3 仅实现证据；K5/U1 空响应 `.dst` 未定义） |
| S01 | earlySBIDreuse | 合成 64B | — | 两条 SEND 均 set SBID0，之后才有 `$0.dst` | **UNKNOWN** / SBID-REUSE-SYNC-UNPROVEN（无法仅凭解码 SBID 相等证明违反） |
| F01 | deleteimplicitdependency | 伪造 IR | — | 删除 `mac` 的隐式 ACC 读 | **REJECTED** / MAC-IMPLICIT-ACC-READ-REQUIRED（IR 完整性违规） |
| T01 | truncatedcompact | PS0[:116] | — | 紧凑指令剩 4B | **REJECTED** / TRUNCATED_COMPACT |
| T02 | truncatednative | PS0[:148] | — | 原生指令剩 12B | **REJECTED** / TRUNCATED_NATIVE |

14 个指定类全部覆盖：`missing_classes = []`。

### 负例

| id | 内容 | 期望 |
|---|---|---|
| N01 | 合成含 `jmpi` | **REJECTED** / CONTROL_FLOW_UNSUPPORTED |
| N02 | 合成 SEND 扩展描述符为 `a0.0`（动态） | **UNKNOWN** / DYNAMIC-DESCRIPTOR |
| N03 | PS0 置位 dword0 bit29（byte3 |=0x20，ilegal compact） | **REJECTED** / PROTOCOL_OR_DECODE_BOUNDARY |
| N04 | 合成 `send.gtwy` + sampler 描述符 | **UNKNOWN** / UNMODELED-MESSAGE-FAMILY（编码 SFID 已知 =3 GTWY，仅 family 未建模） |

## 6. 关键测量（独立 IGA 结论）

- 紧凑位 = dword0 的 bit 29（字节偏移 3，掩码 0x20）。
- SWSB `$0.dst` 等待位在指令字节偏移 +1 的低半字节标志区（本语料 0x61/0x131）。
- 描述符 Mlen=desc[28:25]、Rlen=desc[24:20]（IGA `MessageDecoder`：`<XE3`），
  但 IGA 把 32 位描述符**位交织**进指令，故必须用固定 IGA 汇编物化，不能只按平面字节改位。
- EOT 位在指令字节偏移 +4 的 bit 2（0x04）。
- Gen12 SFID 由 opcode function-control 决定（`.smpl`/`.urb`/`.rc`…），
  与 Gen11 把 SFID 放在 exDesc[3:0] 不同。

## 7. 必须保持 UNKNOWN / 不越界声明

- M03/N04：SFID 变更或未知消息只证明 **SFID/消息合同** 变化；
  资源 ABI（Surface/BindingTable/URB/RT/thread payload）保持 **UNKNOWN**。
- M08：ACC 变更永远是 **UNKNOWN**，绝不允许被判为 CHECKED。
- M10：仅声明 `debug_switch` 控制字段差异，**不声明**任何硬件调试语义。
- N02：动态描述符 → **UNKNOWN**，不得当成已证明合同。
- 所有 oracle `hardware_validated=false`：未做真实 GPU/MMIO/上机，未执行上位程序。

## 8. 边界

- 未写测试 runner（由主代理编写）；本目录只提供期望与字节。
- 未触碰 EFI/NVRAM/启动项/分区/USB/固件；全程离线。
- 未使用 `ssh`/硬件；未运行会写历史目录的 runner。
- 全程 `python3 -B` / `PYTHONDONTWRITEBYTECODE=1`，无 `.pyc`。

## 9. ERRATA-1（2026-10-19，独立修正）

依据 `reference/rules/RULES.json` 与固定 IGA 源码独立复核，修正三处并新增一处锁定：

| 目标 | 修正前 | 修正后 | 依据 |
|---|---|---|---|
| M12-earlySBIDreuse-vs | COUNTEREXAMPLE / SBID-REUSE-BEFORE-COMPLETE | **UNKNOWN** / SBID-REUSE-SYNC-UNPROVEN | RULES K3（IGA 实现注释）、K5/U1（空响应 `.dst` 未定义）、U2 |
| S01-earlySBIDreuse-syn | COUNTEREXAMPLE | **UNKNOWN** / SBID-REUSE-SYNC-UNPROVEN | RULES K3、U2；仅凭解码 SBID 相等不能证明违反 |
| N04-unknown-message | UNKNOWN / UNMODELED-SFID | **UNKNOWN** / UNMODELED-MESSAGE-FAMILY（SFID 已知=3 GTWY） | IGA SFID 枚举；区分已知 SFID 与未建模 family |
| M05b-regionchange-nf | （新增） | **COUNTEREXAMPLE** / EU-REGION | RULES A5；NF 不得掩盖已知 GRF 操作数 region |

不变项（已确认）：M05 仍为 COUNTEREXAMPLE（已知 GRF src 子寄存器变化）；
M10 仍为 UNKNOWN（仅控制字段差异，不声明硬件语义）。

**独立推理要点**

- K3 明确是“IGA 实现规则，非本地找到的 PRM 语句”；SBID 复用被 IGA 视作隐式同步。
- K5/U1：空响应 SEND 的 `$N.dst` 如何解除，本地证据未定义；IGA 对 null dest 不建写足迹。
- U2：SBID 复用在有中间 `.dst` 消费者时是否安全，是显式未决问题。
- 因此“同一 SBID 被两次 SET”只是**解码相等**，不能证明任何生产者被孤立 → UNKNOWN。
- `earlySBIDreuse` 类仍由 M12/S01 覆盖，只是以精确 UNKNOWN 表达，不伪造失败。

修正叠加层 `ERRATA.json` 提供 `operations[]`（`merge`/`replace`/`append`/`confirm`）与
`citations`，runner 可对 `checkpoint/` 基线施加，或直接采用已修正的 `oracles.json`。
