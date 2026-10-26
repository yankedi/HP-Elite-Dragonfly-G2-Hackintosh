# GA4.13 — R6 Managed RT 三 Command Buffer 对照

## 结论

**实验完成，采集有效，结果为 `PIXEL_FAIL`：把 render、synchronizeResource、GPU copy 分成三个分别等待完成的 CB，仍未恢复 CPU getBytes。**

| 全图有效字节比较 | GA4.12 legacy（一个 CB） | GA4.13 staged-boundary（三个 CB） |
|---|---:|---:|
| GPU vs Expected：错误字节 / 像素 | 0 / 0 | 0 / 0 |
| CPU vs Expected：错误字节 / 像素 | 47,639 / 16,705 | **47,621 / 16,705** |
| CPU vs GPU：错误字节 / 像素 | 47,639 / 16,705 | **47,621 / 16,705** |
| 显式 CB 正常完成 | 1 / 1 | **3 / 3** |
| 探针退出码 | 0 | 0 |

每图 257×65，共 16,705 像素、66,820 有效字节；完整文件 83,200 字节。比较排除 row padding；完整文件和有效字节的 SHA256 分别保存。

三 CB 结果不支持“仅将这三个操作拆开并逐个等待即可恢复该用例”的假设。它没有排除驱动内部同步／resolve 本身的错误，也没有证明 NOCCS3 是本次资源的根因。新旧 CPU 数据很接近，18 个错误字节的净减少不是可归因的修复收益。

## 运行身份与健康窗口

用户在场，SSH 失联后亲自重启，再明确要求继续目标。此次只执行了一次新 GPU 探针。

- HP Elite Dragonfly G2，真实 PCI `8086:9A49`；macOS `26.6.2 / 25G83`。
- 本次 boot session：`REDACTED-SESSION-ID`。
- 启动时间：2026-10-24 **12:44:18 本地 / 04:44:18 UTC**。
- 实际加载 R6 NootedGreen UUID：`4C4C44D0-5555-3144-A111-5710B37AE86F`。
- 延用封存的 JulioNectar 基线 `6a1afb337d1fb1ff07ca032b5c1868fe2bd005ef` + 已有 HP R6 功能栈；来源与差异说明见 [GA4.12 总报告](../ga412/FINAL-REPORT.md)。本轮核对的是实际加载身份和现有 MTLDriver/libxedrv 哈希。
- 最新已有 gpuRestart 报告为 **12:42:26**，早于本次启动；没有将它算成本轮 reset。
- 启动初期 1 分钟负载 52.66，构建期降至 2.12，最终预检降至 1.43 后才执行。
- 实际采集：**2026-10-24 04:54:23 UTC / 12:54:23 本地**。
- GPU 前、后、延迟只读健康采样 UTC 分别为 `04:54:23.314281`、`04:54:24.203304`、`04:55:05.548919`；均通过门槛、无本次启动的新 gpuRestart 报告，WindowServer 始终 PID 197 / `Ss`。

延迟采样仅比执行晚约 42 秒。这是短时服务／诊断目录观察，不是长期稳定性证明，也不是桌面无花屏证明。

已知 Recovery / VESA IMG 均存在、各 1,343,225,856 字节；本轮仅核对存在和大小，没有重新计算整盘哈希或实启。完整路径和观察限制见 [HEALTH-WINDOW.json](reports/HEALTH-WINDOW.json)。没有自动重启或修改系统引导／驱动配置。

实际用户态驱动文件哈希与 GA4.12 一致：

```text
AppleIntelTGLGraphicsMTLDriver
e3242693959408c9cef14140df81ce98ff1e04d5dd83aa9aeaddb463271ac65d

libxedrv.dylib
b274aa7293acc9ba4c00acaefa564b4c9367ed29042659371ce42b62dd651259
```

## 唯一工作负载变量

```text
GA4.12：CB1 [Render → SynchronizeResource → Texture-to-Buffer Copy] → Wait
GA4.13：CB1 [Render] → Wait → CB2 [SynchronizeResource] → Wait → CB3 [Copy] → Wait
两者：GPU snapshot 冻结 → CPU getBytes
```

沿用 R8 输入、257×65、RGBA8 Managed RT、相同 shader 和图案、storage／usage／描述符、资源保活范围、input pitch 512、output pitch 1280、Shared readback 原分配 332,800 字节、相同 getBytes 参数。没有额外同步前 copy。变化包括三个 CB 对象及对应创建／提交／完成等待和记录；CB 间记录开销属于本次边界实验，不能解读为严格相等的执行时延。

[SOURCE-SCOPE.json](reports/SOURCE-SCOPE.json) 通过源码区域逐字比较核对五组不变量（render CB 变量名作唯一文本归一化），并确认 render／synchronize／copy 各一次。目标纹理在三个 CB 收据中保持同一对象 `0x7fb97d033400`，source 也未改变。隐含驱动操作不在显式 API 操作计数内。

旧 legacy 是另一 boot 的已封存有效采集；本轮没有重跑 legacy。固定源码／文件哈希不代表两次内核私有资源状态完全相同。

## CB 真实状态和完成时序

| CB | ID | status | error/domain/code | commit 到 wait 返回 | callback 到 wait 返回 |
|---|---|---:|---|---:|---:|
| CB1 Render | `pid-996-cb-1-0x7fb97c807620` | 4 | 空 / 空 / 0 | 2.989 ms | 0.108 ms |
| CB2 Synchronize | `pid-996-cb-2-0x7fb97bf07c10` | 4 | 空 / 空 / 0 | 0.711 ms | 0.093 ms |
| CB3 Copy | `pid-996-cb-3-0x7fb97c807b40` | 4 | 空 / 空 / 0 | 0.858 ms | 0.121 ms |

三个真实 completion callback 均被观察，wait 均返回、timeout 均为 false。CB2 在 CB1 wait 返回后创建，CB3 在 CB2 wait 返回后创建。以下为同进程 `CLOCK_MONOTONIC` 纳秒原值，不与跨 boot 的时钟值相减：

| CB | created_ns | commit_ns | wait_begin_ns | callback_ns | completion_observed_ns |
|---|---:|---:|---:|---:|---:|
| 1 | 605676250000 | 605676686000 | 605676748000 | 605679567000 | 605679675000 |
| 2 | 605680108000 | 605680265000 | 605680318000 | 605680883000 | 605680976000 |
| 3 | 605681330000 | 605681462000 | 605681481000 | 605682199000 | 605682320000 |

GPU 文件先独立冻结于 `605683193000`；CPU getBytes 为 `605683273000 → 605683710000`。独立 CB JSON、stdout 事件和 result 中的收据相互一致，见 [R8-STAGED-RESULT.json](reports/R8-STAGED-RESULT.json)。历史 legacy 的 status 同为 4、error 为空；完整原始单 CB 收据见 [R8-LEGACY-RESULT.json](../ga412/reports/R8-LEGACY-RESULT.json)。

## 错误位置、行和周期

两次 CPU 结果的全部 **16,705 个错误像素位置相同**，但完整错误字节掩码并非完全相同：

- 共同错误字节位置：47,599；仅 legacy 错：40；仅三 CB 错：22。
- 共同错误位置中，47,540 个字节的错误值也相同。
- CPU 有效数据总共仅 **121 / 66,820 字节**变化；GPU、input、expected 完整文件逐字一致。
- RGBA 通道错误字节：legacy `[16664, 7415, 6987, 16573]`，三 CB `[16663, 7408, 6982, 16568]`。
- 每行有效字节错误数：legacy 671–758，三 CB 665–758；全部 65 行都有错误。只有 0-based 行 `8,12,16,20,24,64` 的错误计数变化，分别 `-6,-3,+3,-3,-3,-6`；完整逐行值在比较报告中。

物理行间距包含 padding 后的错误位置 lag 统计：

| lag（字节） | legacy 错误位置配对数 | 三 CB 错误位置配对数 |
|---|---:|---:|
| 64 | 31,220 | 31,190 |
| 128 | 40,283 | 40,292 |
| 256 | 34,786 | 34,786 |
| 512 | 33,871 | 33,879 |

四种 period 的 residue 均有错误；完整 64／128／256／512 residue histogram、row 数组、各三组比较、错误掩码 hash 见 [BOUNDARY-COMPARISON.json](reports/BOUNDARY-COMPARISON.json)。这些仅说明错误模式高度接近，不是对 Intel tile／CCS 格式的识别。

## 独立数据 SHA256

完整文件：

| 文件 | GA4.12 legacy | GA4.13 三 CB |
|---|---|---|
| input.bin | `73408ccc08d3d8d24efd38d6da6665b0284544c9c28bb921f01b3dc904041d8e` | 同左 |
| expected.bin | `b4ce8521077ad3c0b95f575064f24e458581c10255d1b5e50171ff95640ee549` | 同左 |
| gpu.bin | `2b124f90ea8a8478e971d810f9ec6d47c119c0414500d8a27e2776efe6a6c248` | 同左 |
| cpu.bin | `03ff4222462a6fa67370a99c42426ab5a63924b11fbcd5c63eb616f2256c3a59` | `071372b53fc53fd91735a8d421575485742747d984bbcf26448437b1e72f3bb3` |

有效字节（逐行取 1,028 字节再串接）：

| 数据 | GA4.12 legacy | GA4.13 三 CB |
|---|---|---|
| expected 与 GPU | `743eb209da06b225596c6870bcb0d6ba89353e5c5b21d917005cb4caacee11d1` | 同左 |
| CPU | `5ef3f50a7685aa51e2966b74ef628ddf8c1f62320b6f8c201851f258085d2188` | `c6dbeb76d7c2b64bd06fbda3560faf088055e22f61856da4dd330db0eadfde27` |

GPU 和 expected 的完整 hash 不同是 padding 不同；有效字节完全一致。CPU 错误不是 padding-only。

## 同纹理 trace 与根因边界

共 12 条完整 trace 事件，其中目标 RT 为同一对象／resource 的 8 条嵌套事件：

```text
getBytes enter
  lockForCPUAccess(readOnly=1, level=0, slice=0) enter
    resolveCCS(level=0, slice=0, wait=1) enter → return 1
  lock return_u64 = 4394483712
  unlockForCPUAccess(readOnly=1) enter → return 1
getBytes exit
```

getBytes 的 region 为 `[0,0,0] / [257,65,1]`、row 1280、bytesPerImage 0、mip/slice 0。目标的既有 raw 字段和 legacy 一致：`0x108=1536`、`0x10c=1040`、`0x114=4`、`0x134=3`、`0x16a=520`、`0x1ac=4614`、`resource_0x1c=1`。

这里只保存 lock 返回地址和既有未定型字段，**没有读取该地址对应的 locked backing 字节**，也没有观测同一资源的真实 subresource/base 偏移或内核 AUX／dirty／CCS 状态。`resolveCCS` 返回 1 不等于已证明实际解压完成。

因此，CCS／resolve／CPU backing 仍是优先因果链；NOCCS3 跳过 resolve 而上层清 dirty／返回成功仍是已有静态机制线索，尚未与本次内核资源动态闭环。不能宣布花屏根因已证或驱动已修复。

## 下一步唯一最小验证建议

**对同一 Managed RT，在 `lockForCPUAccess` 返回时有界保存实际 CPU locked backing，并确认 level/slice/base offset 与实际压缩／resolve 状态，然后先离线解码，与本轮 GPU／expected／CPU 全图对照。**

这一步必须先确认真实映射范围、可读长度及布局依据；不能对返回指针盲读，也不能把旧九种未压缩模型的失败冒充实际 backing 证据。需要内核侧关联时，另行设计最小取证方案。本轮到此完成，没有追加 GPU 运行。

三 CB 已经排除了这一具体边界方案的修复效果；继续改 shader、EU 拓扑或叠加更多同步／copy 会重新引入混杂因素。

## 验证、保全与复核

- 原生 macOS clang：`-fobjc-arc -fno-modules -Wall -Wextra -Werror` 严格编译链接。
- 复用封存 tracer 源码；实际 MTLDriver 四方法 ABI 完整核对、安装成功；lock 返回类型为 `Q`，unlock 为真实双参数方法。
- CPU-only：四线程、128 trace 事件、嵌套调用／64 位返回／有符号返回／幂等安装通过；BAD_ABI 零部分安装通过。
- 三 CB verifier：27 组 fixture、54 次普通／`-O` CLI，以及 5 次历史比较 CLI；PASS／PIXEL_FAIL／INVALID 均有覆盖。
- Linux 端独立重建 expected，遍历三组全部有效字节；复核三张独立 dump、各 CB JSON、stdout／stderr、调用时序及前后健康。`summarize-evidence.py` 重新计算结果并与封存比较报告核对。
- 本地与远端一次性标记及 SSH 回执均留存；没有自动重试。未变更驱动、EFI、KC、NVRAM 或安全配置，没有新 IMG 或功能补丁。
- 私有原件保存在 `ga413/private/r8-staged-boundary-capture/`、`ga413/private/commands/`、`ga413/private/native-*`，沿用 `.gitignore` 隔离；公开报告包含原件大小和 SHA256，不含 SSH 凭据。GA4.12 原件保持封存。

本次公开交付索引：

- [R8-STAGED-RESULT.json](reports/R8-STAGED-RESULT.json)：完整 CB、trace、健康摘要、证据 hash。
- [R8-STAGED-PIXEL-VERIFY.json](reports/R8-STAGED-PIXEL-VERIFY.json)：三组全图像素复核。
- [BOUNDARY-COMPARISON.json](reports/BOUNDARY-COMPARISON.json)：历史对照、完整错误位置／行／周期／通道。
- [NATIVE-BUILD.json](reports/NATIVE-BUILD.json)、[SOURCE-SCOPE.json](reports/SOURCE-SCOPE.json)、[VERIFIER-TESTS.json](reports/VERIFIER-TESTS.json)。
- [PREFLIGHT-HEALTH.json](reports/PREFLIGHT-HEALTH.json)、[HEALTH-WINDOW.json](reports/HEALTH-WINDOW.json)。
