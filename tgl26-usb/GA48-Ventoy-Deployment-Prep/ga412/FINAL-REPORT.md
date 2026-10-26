# GA4.12 — 新 R6 单次 Managed RT 像素诊断交付

## 结论先行

**本次采集有效，像素结果为 `PIXEL_FAIL`，不是缺数据的INVALID。**

在用户手动重启R6并明确要求继续后，完成了真实编译链接、observer ABI修正、CPU回归和**仅一次**R8 legacy实机采集。一个显式Command Buffer正常完成、无error；三份完整数据独立保存。NixOS逐字节复核结果：

| 比较（排除行padding） | 不同字节 | 错误像素／16705 |
|---|---:|---:|
| GPU copy快照 vs 独立expected | **0** | **0** |
| CPU getBytes vs 独立expected | **47639** | **16705** |
| CPU getBytes vs GPU copy快照 | **47639** | **16705** |

这次真正取得了**同一次运行中GPU copy读回正确、CPU getBytes错误**的联合证据。GPU快照仍是copy/readback代理，不是独立于压缩和copy实现的绝对原始VRAM真值。

**花屏根因仍为 `ROOT_CAUSE_UNVERIFIED`。没有修改驱动，没有像素FAIL→PASS，不宣称修复花屏或稳定性。** 本报告完成的是此次单次诊断及工具交付，不是整个Tiger Lake图形兼容问题已解决。

## 1. 本次身份、保活和健康

- 新boot session：`REDACTED-SESSION-ID`。
- R6 NootedGreen UUID：`4C4C44D0-5555-3144-A111-5710B37AE86F`。
- 系统：macOS 26.6.2 / 25G83。设备registry ID `0x100000578`；设备名仍为`Intel(R) TGL Unknown`，不能用这个名称推翻已确认的真实TGL硬件。
- 临时PID991 `caffeinate -ims -t 7200`、PID1082 `caffeinate -d -t 6600`，系统已验证断言。按目标机时钟分别约09:25和09:20到期，自动释放；未修改持久电源配置。
- 直接stat确认VESA/Recovery镜像均存在、各1,343,225,856字节；本次没有重新校验整张介质hash或启动验证。
- 紧邻运行前07:58:16、运行后07:58:45（+0800）SSH均rc0，同一boot session，WindowServer PID197/Ss，最近诊断文件列表相同，未看到本次新增reset/watchdog报告。
- 运行后WindowServer RSS约2.85GiB。之前持续增长仍是资源占用线索；没有把Ss或一次无hang写成稳定性证明。

关于上次SSH问题，详见[故障取证](reports/R6-SSH-RECOVERY.md)：旧02:40已有RCS hang/reset；随后身份SSH仍成功，目录搜索find在lifs路径采样，sshd会话仍存在；旧WindowServer watchdog记录GPU Busy Surface及约10.22GiB内存。**目录搜索超时有直接线索，sshd死亡、睡眠或GPU故障导致SSH不可达的完整因果链未证。**

## 2. 实际修复了哪些诊断缺陷

所有新源码位于`ga412/tools/`；没有修改GA4.0–GA4.11已封存源码或报告。

| 源码 | 确定的问题与修改 | 验证 |
|---|---|---|
| `trace-managed-cpu.m` | 旧lock guard要求返回`^v`，实机实际编码为`Q`；改为精确64位ABI | 原生CPU-only读取实际driver metadata，四方法安装成功；实机采集观察到真实lock返回 |
| 同上 | 旧observer遗漏实际的`unlockForCPUAccess:readOnly:` | 新增参数和有符号byte返回观察，不主动调用unlock |
| 同上 | 旧get/resolve没有完整类型门槛、全局计数无并发保护、private pointer直接解引用 | 四项ABI全部验证后才安装；线程局部日志重入保护、序列化JSON；有界自身地址空间读取，不写flags |
| `managed-rt-probe.m` | 旧版本只在wait返回后记录CB状态，失败时缺部分进度，缺CB身份/时序 | 创建、commit、wait、完成callback、error及资源属性即时记录，另存`command.json`；失败不认证PASS |
| 同上 | 保留GA4.11已修正的独立GPU/CPU/expected，不再重现R4覆盖GPU快照的错误 | GPU深拷贝、写盘完成后才getBytes；地址区间独立检查；实机完整dump取回 |
| `verify-pixel-dump.py` | 旧版本使用assert作为关键门槛，Python `-O`可移除；命令失败与像素失败混在FAIL中 | 显式拒绝无效metadata/CB/时序/文件；INVALID与有效PIXEL_FAIL分离，正常/-O一致 |
| 同上 | 缺少周期、通道、行/块重复等统计 | 增加64/128/256/512物理偏移统计、通道/行错误、全零/FF、重复前行/前块；仅描述规律 |
| `expected-pattern.py` | 将独立图案生成从probe解耦 | Python独立重建R8输入和RGBA expected；已知首像素、第二行和最后像素坐标检查 |
| `inspect-texture-abi.m`、`test-trace-cpu.m`、`build-darwin.sh` | 提供无需GPU提交的真实ABI/链接与回归流程 | 下节 |

这些是诊断软件修正，不是新的GPU兼容hook。观察器只在自身probe/CPU测试进程内替换方法，不注入WindowServer；每个wrapper调用原方法一次，未主动resolve或修改资源状态。

## 3. 哪些真正编译、运行和测试过

### `DARWIN_LINKED`

Apple clang 21.0.0，x86_64-apple-darwin25.6.0；`-fobjc-arc -fno-modules -Wall -Wextra -Werror`，链接Foundation、Metal。

- GA4.11原始probe和tracer先原样真实链接成功，保留对照产物。
- GA4.12新probe、tracer dylib、ABI inspector和两种CPU harness全部真实链接。
- 交付的`build-darwin.sh`已在目标机实际执行，含CPU测试，**不会调用GPU probe**。
- 实际运行的probe SHA256：`b324901b7c4dd8b62f812fb08b0e98950eb303c160a2bc9764302178d930db37`。
- 实际tracer SHA256：`642fc8a409b198253fdca4fb9f32b6f980bf119573d2f868794aafdc234648e9`。
- 五个自产Mach-O产物已取回到ignored目录`ga412/private/native-build-v2/`；关键三个hash与原生构建回执一致。

重要纠正：`/Library/Extensions/`和`/Library/GPUBundles/`内MTLDriver副本hash不同。本次最终ABI验证针对真正GPUBundles副本；实际采集的四个original IMP也全部解析到该副本。不是拿另一个副本的ABI冒充正在执行的ABI。

### `CPU_TEST_PASS`

- 原生假纹理测试：四线程，16次getBytes及其自然嵌套lock/resolve/unlock；128条enter/exit事件全部平衡且序列号连续。
- 验证所有参数、完整64位lock返回、负值resolve/unlock返回均原样转发；重复安装不循环hook。
- 故意错误lock ABI：拒绝安装，getBytes IMP保持原值，没有部分安装。
- 实际driver CPU-only dlopen及metadata安装检查：四方法ABI通过，调用计数全0；这一步没有创建Metal设备或提交GPU命令。
- 离线27个fixture、每组正常/-O各一次，共54次CLI执行；截断、缺失、stride、两侧同错、命令失败/超时、时序、alias、周期、行重复、块重复及固定通道均通过预期判定。

[原生证据](reports/NATIVE-BUILD.json)；[fixture结果](reports/SYNTHETIC-VALIDATION.json)。CPU fixture中的PIXEL_PASS不是GPU运行结论。

## 4. 唯一实机采集的真实过程

固定R8源257×65，源pitch512、Shared/ShaderRead；输出RGBA8、Managed/RenderTarget，输出row pitch1280；一个mip/slice/sample。shader、完整三角形、nearest采样、图案和清屏色沿用GA4.11/历史工作负载。

仍是一个显式CB，依次render、synchronizeResource、texture-to-shared-buffer copy、waitUntilCompleted；没有额外GPU copy、主动resolve或第二个GPU用例。

- CB ID：`pid-1576-cb-1-0x7fd3d88091c0`。
- 完成status=4，error/domain为空、error code0，wait返回；probe退出0只代表采集完成，程序**不自报像素PASS**。
- GPU readback Buffer为Shared，长度332800；每份GPU/CPU/expected快照83200字节，有效像素66820字节，排除16380字节行padding。
- 单调时钟：完成观察`2160192761000`ns → GPU快照冻结`2160193792000`ns → CPU getBytes开始`2160193888000`ns → CPU结束`2160194569000`ns。
- CPU getBytes使用row1280、bytesPerImage0、origin(0,0,0)、size(257,65,1)、level/slice0。
- 12条完整trace中，源上传4条，目标CPU读回8条；按对象身份区分，不把源上传lock误认作目标读回。

目标上的正常调用链为：

```text
getBytes enter
  lockForCPUAccess(readOnly=1, level=0, slice=0) enter
    resolveCCS(level=0, slice=0, wait=1) enter
    resolveCCS exit -> 1
  lock exit -> 4440469504 (完整64位返回值)
  unlockForCPUAccess(seed=1, readOnly=1) enter
  unlock exit -> 1
getBytes exit
```

目标的有界用户态读数在这八条事件中保持一致：m_Info+0x108=1536、+0x10c=1040、+0x114=4、+0x134=3、+0x16a=0x0208、+0x1ac=0x1206、resource+0x1c=1。

**这些raw offset值不等于内核压缩状态。** requested row1280与内部1536/1040不同，本身不证明pitch错误；driver有责任完成布局转换，不能因不同就硬套tile修复。

## 5. 独立验算和hash

`verify-pixel-dump.py`重新生成expected，核对输入、资源、CB完成、四方法安装、快照时序与文件独立性，再完整逐字节比较。另用不调用verifier.compare的packed全图计算二次核验，数字一致。

CLI退出 **1**，对应有效`PIXEL_FAIL`；已保留非零返回码，不用probe退出0改写为PASS。

| 原始文件 | 大小 | 完整文件SHA256 |
|---|---:|---|
| `input.bin` | 33280 | `73408ccc08d3d8d24efd38d6da6665b0284544c9c28bb921f01b3dc904041d8e` |
| `expected.bin` | 83200 | `b4ce8521077ad3c0b95f575064f24e458581c10255d1b5e50171ff95640ee549` |
| `gpu.bin` | 83200 | `2b124f90ea8a8478e971d810f9ec6d47c119c0414500d8a27e2776efe6a6c248` |
| `cpu.bin` | 83200 | `03ff4222462a6fa67370a99c42426ab5a63924b11fbcd5c63eb616f2256c3a59` |

GPU与expected完整hash不同是因为padding不同；**排除padding后的active SHA256相同**，其全部有效像素逐字节一致。CPU不是padding-only差异，四通道错误字节数为[16664,7415,6987,16573]。

- [完整三组差异、首32处和周期/布局统计](reports/R8-LEGACY-PIXEL-VERIFY.json)
- [实际CLI非零返回及第二种全图核验](reports/R8-LEGACY-VERIFICATION-RECEIPT.json)
- [时序/trace/资源/14份原始证据hash汇总](reports/R8-LEGACY-RESULT.json)
- 原始完整dump与日志：`ga412/private/r8-legacy-capture/`。

## 6. 对NOCCS3、CCS/AUX和花屏假设的影响

既有[BINARY_CONFIRMED审核](../ga411/reports/LOCAL-AUDIT.md)确认：

- NOCCS3把accelerator submitCCSResolve入口改成`xor eax,eax; ret`，跳过原有提交。
- resource resolve在0x73e99调用该入口后，0x73eb1清dirty bits、0x73eb6清entry+0x64，0x73f0f返回true，未检查底层返回。
- 用户态resolveCCS通过selector0x16的IOConnectCallMethod成功状态生成返回1；返回1不是像素转换验收。

**新证据进一步收窄到CPU读回/表示转换链：** 对同一Managed RT、同一CB，copy代理已正确，随后CPU lock→resolve返回成功仍得到整幅错误像素。这支持排查CPU-visible表示、同步或压缩转换软件状态；不支持直接把该用例归咎于shader完全错误、显示线缆或单纯scanout。

但仍不能独立区分：

1. NOCCS3使上层完成状态与实际转换不一致；
2. CPU lock/getBytes取得错误backing、缓存、pitch或布局；
3. GPU copy路径做了CPU路径没有做的隐式转换；
4. Apple TGL用户态与Tahoe接口差异。

未取得同一资源内核handle映射、entry+0x91、dirty、AUX映射、surface state以及accel+0x1190/+0x1474联合观测；这些项仍为NOT_OBSERVED。用户态resource指针不冒充内核entry地址。不能把NOCCS3选为已证根因，不能把RenderCompressionMode=0当禁压缩，更不能据此开启整套xefix/RPL workaround。

RCPOLICY的已证范围仍偏向display/IOSurface，当前普通Managed RT没有相应因果证据。FRAMEBUFFER/FMT、PLANES2及scanout问题也不能仅凭这个小图案排除，但不应优先用它们解释已经明确的CPU读回错误。

## 7. 旧结果与新结果的边界

- R4的16705/16705是旧CPU expected失败；旧程序覆盖过GPU缓冲，不能补写成当年GPU快照已独立通过。
- 本次的新结论来自新R6 session的三份独立dump，不是重复引用R4数字。47639是本次有效字节差，不是旧47630。
- R5旧RCS hang、R6已生效command pool扩容、上次R6 02:40 reset都保留各自证据；没有重新归咎于96EU拓扑，也不把R5旧pool状态冒充本次状态。
- 旧GA4.11前置超时的INVALID报告保持原样。本次VALID/PIXEL_FAIL不覆写它。

## 8. 唯一后续实验与当前完成边界

建议只改变**Command Buffer分组/完成等待边界**：render、sync、copy各分一CB，GPU命令与copy次数保持原样。详见[NEXT-EXPERIMENT.md](NEXT-EXPERIMENT.md)。

特别纠正：GA4.11已有staged模式额外做一次同步前copy，它不是纯边界对照。不要直接将它作为本次单因素候选执行。当前交付探针强制只接受R8 legacy，尚未加入或运行新候选。

当前已完成这次单次诊断、实用工具及真实证据交付；尚未解决桌面花屏、长期hang或完整压缩状态一致性。没有新增驱动功能补丁或IMG。

## 9. 要求—产物审计

| 要求 | 对应实际证据 |
|---|---|
| 新R6身份/保活/介质/健康门槛 | ready及immediate preflight、post-health原始回执；SSH报告 |
| 原生严格编译链接、必要ABI | NATIVE-BUILD.json、原始构建回执及本地Mach-O |
| 正常CPU链观察、无额外resolve | 新tracer源码；12条按对象关联trace，实际IMP image记录 |
| 一次R8/257×65/RGBA8 Managed/legacy | 本地latch、远端once-claim、唯一execution rc0、单CB command.json |
| GPU在getBytes前独立冻结、CPU/expected完整 | 源码深拷贝/独立区间、单调时序、各83200字节文件 |
| 三组完整diff、padding排除、独立expected和hash | PIXEL-VERIFY、VERIFICATION-RECEIPT、RESULT三个JSON |
| 故障/失败不伪造通过 | verifier实际rc1保留，PIXEL_FAIL；旧INVALID仍封存 |
| 不改驱动、安全策略、镜像，不自动恢复 | 本轮已保存远端命令只含用户态构建/CPU检查/一次probe/临时保活/取回；未执行安装或重启命令 |
| 唯一后续单因素建议，不实施 | NEXT-EXPERIMENT，明确旧staged混杂因素及新候选尚未运行 |

## 10. Git提交

分支`ga412/metal-pixel-integrity`，均仅本地，未push：

| Commit | 内容 | 验证 |
|---|---|---|
| `a92e708` | 新R6临时保活/旧SSH超时证据与离线提取器 | 13份证据hash、JSON复现、链接和Python编译检查 |
| `4ef2ea4` | 新probe、四方法observer、ABI/CPU工具、原生构建脚本及索引 | 真实严格链接、原生CPU测试、实际driver ABI |
| `cb22b8c` | 独立expected、fail-closed像素复核器和27组fixtures | 54次正常/-O执行通过 |
| `aa7e601` | fixture可指定新输出路径，保留之前原始测试日志 | 改动后重新54次执行通过 |

最终采集/报告提交可用`git log --oneline -- ga412`查询；不将提交自身hash写入自身文件制造循环。每次提交前均执行`git diff --cached --check`。

## 后续只读／离线分析补充

用户暂时不能重启测试新引导/驱动后，继续分析见[OFFLINE-CAUSE-ANALYSIS.md](reports/OFFLINE-CAUSE-ANALYSIS.md)。已解析实测getBytes实际选择的Tile Y/1536转换；Intel原版CPU代码267280地址交叉验证通过，九种简单未压缩布局模型不能解释数据。NOCCS3与未正确resolve的表示仍是领先机制假设，尚未因果确认。

此外，11:10的只读回执发现同一R6启动在10:32–11:07有至少8份新gpuRestart。原报告07:58采集后“短时未见新增报告”的结论保留其时效，**不能延伸成长期健康**。后续代表报告为WindowServer context5 / PIPE_CONTROL家族。上游#2/#3/#5/#6的新评论与XE-BLITFIX实际门槛已逐项核对；本轮未安装更新或运行第二次GPU实验。
