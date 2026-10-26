# GA4.12 后续：CPU swizzle、NOCCS3 与上游 issue 的因果核对

本轮依据用户“可以SSH，暂时不能重启测试新引导/驱动”的安排继续分析。目标机只读取现有状态/日志/驱动副本；新计算和C参考验证全部在本地执行。本轮新增GPU实验0次，未安装上游更新，未重启。

## 目前最强的故障机制线索

**领先假设：GPU能读取正确内容，但CPU拿到的backing还不是可直接解释为RGBA的未压缩像素；正常resolve链报告成功后，CPU只做了去tiling，因而把错误的表示读成像素。NOCCS3跳过实际resolve提交，是这条链上的首要可疑点。**

这里“去tiling”和“解压缩”是两种不同操作。已经证实前者被选择、返回的数据不满足RGBA像素不变量；尚未证实该资源在内核具体经过了哪个resolve分支，也没有对其压缩格式成功解码。因此仍是`ROOT_CAUSE_UNVERIFIED`，不是已找到且修好的最终根因。

### 证据等级

| 项目 | 等级 | 证据与限制 |
|---|---|---|
| 同一次R8基线：GPU copy全对，CPU全图错误 | DATA_CONFIRMED | 0 vs 16705错误像素；CPU差47639有效字节，独立全图验证 |
| 实测getBytes必走CPU swizzle分支 | BINARY + TRACE_CONFIRMED | `m_Info+0x1ac=0x1206`，代码在`0x19eed`测试bit2，跳转`0x19f5c` |
| 选中Tile Y、源pitch1536 | BINARY + TRACE_CONFIRMED | 枚举3，真实指针表和descriptor masks解析，非凭枚举名称猜测 |
| 单纯替换常见tiling/pitch即可恢复本图 | OFFLINE_MODEL_REJECTED | 9个限定模型的所有“已定义重叠区域”都有错误；不代表穷尽未知offset/backing |
| NOCCS3跳过转换，上层仍清dirty/返回成功 | BINARY_CONFIRMED | accelerator入口stub和resource调用后代码的静态事实；该资源本次走到此内核调用点尚未动态关联 |
| CPU读到了未resolve的压缩主表面 | LEADING_HYPOTHESIS | 与正确GPU copy、通道不变量破坏、NOCCS3一致；没有原始backing/AUX联合证据或压缩解码 |
| CPU错误就是桌面所有花屏与后续hang的唯一共同原因 | UNVERIFIED | 尚缺WindowServer具体出错资源/命令关联和同测试FAIL→PASS |

## 1. 使用的二进制确实是正在安装的副本

通过SSH只读取`/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsMTLDriver`。它与历史反汇编对应的`ga410/private/r4-code-evidence/AppleIntelTGLGraphicsMTLDriver` **5,324,208字节逐字节相同**：

```text
SHA256 e3242693959408c9cef14140df81ce98ff1e04d5dd83aa9aeaddb463271ac65d
```

上次采集四个original IMP均指向这个GPUBundles副本。因此下面分析不是把另一个Extensions副本或任意版本的偏移套到实测路径上。

工具`ga412/tools/analyze-cpu-swizzle.py`自行解析Mach-O64的file-backed segment和RIP-relative LEA；不加载/运行Apple二进制。

## 2. getBytes到底做了什么

### 2.1 lock / resolve / backing

历史反汇编`mtl-driver.asm`，与上面逐字节匹配的image对应：

| VA | 行为 |
|---|---|
| `0x19b9d` | 测`m_Info+0x1ad` bit2；若有则调用resolve |
| `0x19bab` | 否则测`*(m_Info+0)+0x1c` bit0；有则调用resolve |
| `0x19bc7` | 正常`resolveCCS(level,slice,wait=1)`；随后没有用其返回值决定是否继续lock |
| `0x19bdc` | `IOAccelResourceLock` |
| `0x19bf6` | `IOAccelResourceGetDataBytes`，其返回值就是后续swizzle使用的base |
| `0x19d00` | getBytes调用lock，保存返回的base |

实测`m_Info+0x1ac=0x1206`：高byte为0x12，第一项`0x12 & 4=0`；resource+0x1c=1使第二项成立。这解释了为何正常getBytes自然触发resolve，不需要observer主动调用它。

实测lock返回`0x108ac3000`，是64位值；这个进程已经退出，不能再向当前WindowServer或另一个进程按该旧地址读取。此次没有重新创建资源以补采backing。

### 2.2 Tile Y表的实际解码

`getBytes`在`0x19eed`检查flags bit2。本次bit2=1，因此跳过逐行memcpy分支，进入`CpuSwizzleBlt`参数构造：

```text
source.pBase    = lock返回的地址
source.Pitch    = m_Info+0x108 = 1536
source.Height   = m_Info+0x110（本次未观测）
source.pSwizzle = table[m_Info+0x134 - 1]
destination    = 独立CPU输出缓冲，row=1280
```

LEA位于`0x19f8f`，下一指令地址`0x19f96`加其有符号disp32，真实表VA=`0x480ee8`。枚举3对应slot2，指向`0x2c7098`，三个32位mask为：

```text
X = 0x0e0f
Y = 0x01f0
Z = 0x0000
```

与Intel公开`CpuSwizzleBlt.c`中的`INTEL_TILE_Y`逐mask相符：128-byte×32-row、4096-byte tile。源pitch1536恰为12个tile宽；输出1280与内部源pitch不同符合“tiled→linear”的职责分工，**这两个数不同不是pitch错误的充分证据**。`+0x10c=1040`也不是这个分支实际装入source.Pitch的字段。

本次mip/slice偏移表内容没有采到，以下布局反演均明确采用zero-origin模型；不伪称已观测其内容。

### 2.3 本地运行了真正的Intel参考代码

固定Intel gmmlib commit：`733c91a19baa65c40f4b1cf95a3991cc8c84d866`。

- 下载原始`CpuSwizzleBlt.c`及其`assert.h`，原件保留，不做功能修改。
- 本地`cc -O2 -shared -fPIC -msse4.1`编译`swizzle-reference.c`适配层；只生成Linux CPU共享库。
- Python独立地址模型与Intel `SwizzleOffset`对Y、X、Yf32、Ys32各66820个坐标完整交叉验证，共**267280个地址一致且各映射无alias**。
- 对四种布局分别构造合成tiled内容，调用Intel原版`CpuSwizzleBlt`读回，全部66820个有效字节正确。

这是CPU算法/参数解释验证，**不等于Apple私有函数已在Linux执行，也不等于真实GPU修复**。初次C构建缺`<limits.h>`而失败，修正仅在适配层；失败日志`ga412/out/swizzle-analysis-v1/build.json`完整保留。随后一次报告生成因相对路径处理失败；两次失败均未涉及目标机。最终v3完整成功。

机器报告：[CPU-SWIZZLE-ANALYSIS.json](CPU-SWIZZLE-ANALYSIS.json)。

## 3. 实测数据是否只是选错tiling或pitch

本用例R8采样输出RGBA为`(R,0,0,255)`。任何只重新排列**有效RGBA像素**、保持byte内通道位置的空间tiling，均应维持G=0、B=0、A=255。

CPU数据实际违反这些条件：

- G非零：7415个像素；
- B非零：6987个像素；
- A不是255：16573个像素。

因此“所有像素仍正确，只是整像素空间顺序错了”不足以解释结果。若读到了padding、错误backing、错误offset，通道条件可以被破坏，所以这些替代解释仍保留。

进一步，按driver选定Y/1536的地址映射，对照各种候选未压缩backing。**只比较候选中由真实expected有效像素定义的地址交集**，不知道的区域不补零、不拿fixture冒充实测：

| 假设实际backing布局 | pitch | 可比较字节 | 错误字节 |
|---|---:|---:|---:|
| Linear | 1040 | 50756 | 36221 |
| Linear | 1280 | 52880 | 37734 |
| Linear | 1536 | 44492 | 31737 |
| Tile Y | 1280 | 58120 | 41462 |
| Tile Y | 1536 | 66820 | 47639 |
| Tile X | 1536 | 49324 | 35204 |
| Tile Yf32 | 1280 | 57804 | 41257 |
| Tile Yf32 | 1536 | 66180 | 47208 |
| Tile Ys32 | 1536 | 34060 | 24259 |

这些限定假设都被否定。不能据此断言已经穷尽所有offset、aux模式或格式。

条件反演的开头16字节是`00 10 00 00 00 e0 1f 00 68 00 3a 00 15 40 03 38`，不是期望的RGBA起点。这种结构化bit-packed外观与压缩内容相容，但仅凭外观不能命名某种Intel压缩格式。

## 4. NOCCS3为什么仍是首要嫌疑

### 4.1 返回1到底证明了什么

`MTLIGAccelTexture resolveCCS`在`0x1d383`使用IOConnect selector0x16，`0x1d38f`调用`IOConnectCallMethod`。

`0x1d394`检查的是I/O调用返回码；为0时`0x1d398`置返回true。wait=1时再等待resource finish event，**没有任何像素内容验收，也没有软件解压缩步骤**。

随后getBytes的CpuSwizzleBlt只根据地址mask去tiling；它没有颜色压缩解码逻辑。若base仍指向压缩主表面，正确去tiling也不会产生正确RGBA。

### 4.2 静态状态链存在确定的一致性缺口

HP R6源码将上游NOCCS3门槛扩大到原生TGL/Tahoe；有既有运行日志证明该patch命中。它把`IntelAccelerator::submitCCSResolve`入口改为`xor eax,eax; ret`。

accelerator donor反汇编的resource层：

```text
0x73e99 call IntelAccelerator::submitCCSResolve
0x73e9e ... 构造dirty掩码（未检查返回值）
0x73ea4 mov eax,3                  # 原返回eax被覆盖
0x73eb1 and [entry+0x4c+...],eax    # 清对应dirty位
0x73eb6 mov [entry+0x64],0
...
0x73f0f mov al,1                   # 上层返回true
```

所以当此分支被执行时，**跳过实际GPU resolve与“上层宣布已处理”可以同时发生**。这是patch与调用者组合的真实行为，不是仅凭函数名猜测。但目前缺该实测纹理handle到这个内核entry/分支的关联，不把这段静态行为自动写成本次动态分支已确认。

另一个相关路径`disableRenderCompression`在`0x73faa`调用resolve后，`0x73faf`无条件清entry+0x91 bit1；若resolve被stub，盲目清压缩标志同样可能制造“描述为未压缩、数据仍压缩”的状态。因此不应把强行禁压缩或清private flag当成无风险诊断。

`fillSurfaceStateAuxInfo`在`0x73fc6`读取entry+0x91 bit1，决定AuxiliarySurfaceMode=NONE或4/5；`0x7406d`取client-shared RO private后，`0x74072`置+0x1c bit0。用户态初始化则通过`IOAccelResourceGetClientSharedPrivate`将共享指针写入m_Info首字段。这给实测resource+0x1c=1提供了压缩/resolve相关的静态语义线索，仍不能把共享hint当作实时完整内核CCS/AUX状态。

### 4.3 为什么此时不移除NOCCS3

它原本绕开过Tahoe command pool ABI崩溃；R6做过池扩容，并不自动证明所有resolve/HIZ/事件路径均已兼容。没有恢复该链的原生ABI/边界证据，也无法由用户在外面配合物理恢复。本轮只分析，不把定位假设直接部署到内核。

## 5. GitHub issue的新进展及本机适用性

公开快照时间为2026-10-24 03:10 UTC，抓取了全部6个issue、相关12条评论，并核对分页未截断。原始响应、时间、URL、SHA256见[UPSTREAM-ISSUES-SNAPSHOT.json](UPSTREAM-ISSUES-SNAPSHOT.json)。这是本轮快照，不是永久后台订阅。

### #6：图片绿/黑块，已有作者实测修复报告

[作者评论](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/6#issuecomment-6374632015)报告：IOSurface→tiled device cache的较大copy，pitch非64对齐时落到不工作的Blit3D；XE-BLITFIX将其导向XY_SRC_COPY_BLT。作者称8/12 pitch用例及大copy由失败变成功。

候选commit [`df7ab78f79d08a8a792292982b46d2bcf110f052`](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/commit/df7ab78f79d08a8a792292982b46d2bcf110f052)的实际源码也确实检查：

```text
bytes = rectPixelArea * bytesPerPixel
bytes < (bpp==16 ? 0x51001 : 0x20001) -> 保持小copy路径
大copy且源/目的base非64对齐          -> 原BLITALIGN v2规则
大copy且源/目的pitch非64对齐         -> 新规则：XY_SRC_COPY_BLT
否则                                -> 保持Blit3D
```

**对当前R8基线不是相同触发条件：** active字节66820，低于0x20001；Shared输出总分配虽为332800，routing看的是copy面积×bpp，不是缓冲分配长度；源pitch512、目的1280、swizzle源1536均64对齐；目标也不是显式IOSurface。内部字段1040不等于已观测的submitBlit实参。

新patch调用点还位于`!isRealTGL`块内、依赖BLITALIGN成功；直接更新原版不会自动修复HP原生分支。它仍可能解释**另一些桌面IOSurface**图片/字形缺失，但本机缺对应submitBlit参数/计数，不借作者XPS的FAIL→PASS冒充HP修复。

### #3：80EU花屏，最新仍是待测试方案

[03:03 UTC作者评论](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/3#issuecomment-6379072761)已据Linux数据修正：i5-1340P DSS0存在、DSS5关闭，错误主要是非TGL路径硬编码6DSS/96EU；计划提供opt-in 80EU参数，尚未宣布验证成功，并先请报告者试XE-BLITFIX。

HP是真实TGL，80EU/10SS/5 dispatcher已有本机证据；不能因相同80EU标签就把非TGL的96EU硬编码问题重新当本机结论。

### #2：hang后的恢复问题，不等于CPU压缩resolve问题

[作者评论](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/2#issuecomment-6373373983)区分了dummy-page命令取址和reset后RCU_MODE bit0丢失。XE-GPUREC v2恢复的是**Compute Command Streamer（CCS计算引擎）**；本报告NOCCS3涉及的是**Color Control Surface（CCS颜色压缩辅助状态）**，缩写相同但不是同一个“开关”。

该恢复hook同样被`!isRealTGL`门槛排除。HP新日志也没有上游所述dummy-page IPEHR或24–31 compute stamps堆积，详见下一节。

### #5：作者明确原生TGL未实测

[作者说明](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/5#issuecomment-6374754130)其开发机是RPL-P，没有真实TGL验证；TGL-H启动卡死仍是假设中的power/display差异。本HP为TGL-UP3，已经进入桌面并执行Metal小用例，不能将H-series启动冻结直接类比。

## 6. 当前R6确实出现了后续hang，07:58后的短时健康不代表长稳

只读SSH于目标机11:10:51返回0：仍为boot session `REDACTED-SESSION-ID`，WindowServer PID197/Ss，RSS8442272KiB（约8.05GiB）。原限时caffeinate进程已经到期；没有按历史PIDkill或假设仍受保活保护。

最近目录列表显示**至少8份**新gpuRestart（这里只列了head，不能当总数），10:32–11:07。取回两份代表报告：

| 时间（目标机） | Application / context | IPEHR | ACTHD | 相对batch起点 |
|---|---|---|---|---|
| 10:32:25 | WindowServer / 5 | `0x7a000004` | `0x447517e4` | `+0x7e4` |
| 11:07:46 | WindowServer / 5 | `0x7a000004` | `0x453117e4` | `+0x7e4` |

新证据支持重复发生的**RCS PIPE_CONTROL停顿家族**，不是07:58探针CB未完成，也不是已证实的dummy-page跑飞。shader/sampler在有效DSS0–4均done；DSS5全零被报告本身标注为unreliable，符合已关闭的第六DSS，不能借其“not done”证明EU拓扑仍错。

ring片段中可看到含bit28的`PIPE_CONTROL dw1=0x50105021`，与上游NOTCF讨论有相似点；但**ACTHD指向的batch内容没有包含在ring片段内**，不能把ring里某个dw1认定为当前卡住那条指令的dw1。没有据此生成清Tile Cache Flush补丁。

两份报告都把CCS计算ring显示为disabled，但compute stamps24–31均submitted=returned。缺reset前后RCU_MODE，故不能照搬#2“reset丢compute enable导致compute永远不完成”的诊断。

保活到期在时间上早于这些报告，并不证明到期、睡眠或显示熄灭导致hang。取回的WindowServer xedrv日志记录shader/descriptor适配和pipeline创建成功，也不是像素或长期稳定证据。

完整解析：[FOLLOWUP-EVIDENCE.json](FOLLOWUP-EVIDENCE.json)。

## 7. 目前能做与缺少的关键证据

现在已得到比“随便试压缩开关”更具体的定位：

```text
同纹理 GPU copy正确
     ↓
CPU lock因shared resolve hint进入resolveCCS(wait=1)
     ↓
I/O成功返回1，缺内核同资源dirty/AUX/实际转换关联
     ↓
GetDataBytes backing → Tile Y/1536 CpuSwizzleBlt
     ↓
G/B/A像素不变量破坏，九种简单未压缩布局无法解释
```

最关键缺口是**同一纹理的内核资源关联、实际locked backing及resolve前后状态**。没有它们就不能在“压缩未resolve”和“错误backing/offset/cache”之间唯一选择。桌面hang是否与这条链同源也仍待证明。

已记录的唯一下一GPU对照仍是[NEXT-EXPERIMENT.md](../NEXT-EXPERIMENT.md)中的CB分组/完成边界；本轮未实施。新离线证据说明不要把那个实验的PASS/FAIL过度解读成NOCCS3的直接因果验收。用户能配合恢复之后，再决定如何取得上述关联证据及驱动级同测试FAIL→PASS。

## 8. 本地复现

先保留原始公开snapshot和已采集字节。每次使用新目录/新报告名，失败日志不覆盖：

```sh
python3 ga412/tools/analyze-cpu-swizzle.py \
  --output ga412/out/swizzle-analysis-repeat \
  --report ga412/out/swizzle-analysis-repeat.json
python3 ga412/tools/analyze-followup-evidence.py \
  --report ga412/out/followup-evidence-repeat.json
```

前者只在Linux编译/调用Intel公开CPU参考代码；后者只读取已归档的issue、原生源码和日志。两者都没有SSH、Metal或GPU操作。

若要另取公开issue新快照，使用`snapshot-upstream-issues.py NEW_DIRECTORY --report NEW_REPORT`；它只发HTTP GET，不发布评论、不触发安装。当前脚本只抓首10项，分析器会在可能截断时拒绝声称完整，未来issue超过分页容量时需先扩展采集器。
