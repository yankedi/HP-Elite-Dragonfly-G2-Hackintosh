# GA4.11：native TGL 压缩／纹理完整兼容链本地审核

## 1. 当前结论与启动决定

**已定位上游兼容链在 native TGL 上的门控缺口；尚未定位花屏／Managed RT 读回错误的唯一根因，也没有取得像素 FAIL→PASS 的新实机证据。当前不准备新实验镜像。**

关键结果：

1. R6 的 **NOCCS3 确实命中**，但 NOCCS 属性注入、NOAUX、NODEPTH、RCPOLICY、BLITALIGN 没有进入 native 分支；PLANES2 被明确禁用；PAGESYNC 的 hook 安装依赖原始 `-ngreenxefix` 参数，R6没有该参数。
2. NOCCS3 是跳过实际 CCS resolve 提交；其上层仍可能更新资源的“已 resolve”软件状态。**成功返回不证明执行过转换。**
3. `RenderCompressionMode=0` 不能等同禁压缩。固定上游的实验文档明确说它选择压缩类型；`allowGPUOptimizedContents=NO` 的尝试也被上游记录为未达到禁压缩效果。
4. 已捕获的 Metal 二进制包含 **MTL15**：IOSurface 初始化路径忽略内核提供的一个压缩字段。内核原生压缩路径与 Metal 的这项本地状态可能不一致；尚无同一 surface 的内核 ResourceInfoEntry、AUX 映射、Metal 字段和原始像素联合快照。
5. 旧 Managed RT 测试中，`getBytes` 后把 CPU 数据覆盖到 GPU 结果缓冲区，再验证已知内容。历史 `16705/16705` 是 **CPU 结果错误像素数**；同次 GPU 结果没有独立的 expected 检查，不能凭该回执认定 GPU 全部正确。
6. RCPOLICY 有真实 donor 的精确匹配和 framebuffer→setter 的静态调用证据，但尚无 R6 `+0x1474` 内存读数；它影响 display/IOSurface 分配与 flip，**不能直接推出它能修复不显式绑定 IOSurface 的 Managed RT**。

这里的“门控缺口”指上游算法在HP路径不可达，不表示所有被跳过的RPL绕过都应移植。尤其PAGESYNC的原始动机，是弥补RPL特意绕过的Apple跨引擎barrier；native TGL保留原barrier，适用前提不同。

## 2. 固定材料与证据等级

- 上游 `JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe`，git对象 `6a1afb337d1fb1ff07ca032b5c1868fe2bd005ef`。
- GA47封存checkout `a9ae966cd56075db59cc6ff2878e3958022d91b7`，审核时clean。GA47已有HP适配，不能将整个checkout称为原上游。
- 上游 `kern_gen11.cpp` SHA256：`1e80a8d96bfbb6fb50c8e1e359bfecb740318d4fc2bfaac66159fdd8e30ff986`。
- R6 `kern_gen11.cpp` SHA256：`78e1702c7aecfc9e3d3cd29ff8dc5543f873c6306d3a28b62efa315eade869ea`，与 `NG-R6-BUILD.json` 对照。
- R6 `kern_green.cpp` SHA256：`39d83e188bc8565e2ea94dacf421f847539f2f934714601be64ebdbcc481d194`，与同份构建回执对照。
- libxedrv源码 SHA256：`86927be5089655d7d9dd11b468a59ad2c9cc5e4b417e0190aafb59acce2ce6a5`，逐字节等于固定上游git对象。
- 最后有实机证据的是R6，boot session `49C2714E-5FB9-49BC-932A-4DCAB42A4771`，NG UUID `4C4C44D0-5555-3144-A111-5710B37AE86F`。R7没有实启证据，继续封存。

证据分四层：**S**源码可达性、**B**精确二进制/反汇编、**R**既有运行命中/状态、**P**真实像素比较。低一层不自动推出高一层。

机器可复核索引：[LOCAL-EVIDENCE.json](LOCAL-EVIDENCE.json)。生成器：`python3 ga411/tools/audit-local.py`。它只读封存材料并写本轮派生JSON，不连接目标机。

以下源码行号以R6 `ga410/private/ng-r6/source/src/NootedGreen/kern_gen11.cpp` 为准；原算法来源已用固定上游git对象交叉核对。私有原始文件均保留，不复制凭据。

## 3. 九组补丁的真实逻辑与R6状态

| 名称 | 上游算法/目标 | R6实际条件与证据 | 不能据此认定的事项 |
|---|---|---|---|
| XE-NOCCS | `Gen11::start` 中同时向 `Development` 和service顶层写 `RenderCompressionMode=0`、`AllowIOSurfaceRenderCompression=0`（5330–5347） | 整块仍在5303的 `!isRealTGL` 分支。R6日志记录5373的native skip，无NOCCS注入命中；本轮晚期只读IORegistry实际读到Development.Allow=1，未见RenderCompressionMode | 没有配置bits/内存快照；属性读数不能证明所有surface实际压缩，更不能把mode=0称为禁压缩 |
| XE-NOCCS3 | `IntelAccelerator::submitCCSResolve` 入口改 `xor eax,eax; ret`（2248–2263） | R4扩展到真实TGL/Tahoe；R6日志 `aplicado`。原donor唯一匹配VA `0x2c84c` | 不执行该函数原有的resolve提交；并非数据转换正确 |
| XE-NOAUX | `fillSurfaceStateAuxInfo` 的条件跳转改NOP，让surface state低3位始终AUX_NONE（2306–2313、2394–2397） | 仍在2266的 `!isRealTGL` 内；`-ngreenccs` 可关闭，但移除该参数也不能越过外层门控。原donor唯一匹配VA `0x73fc6` | 此补丁只改surface state生成，不等于清掉所有资源标志或取消所有AUX分配；未证明HP缺AUX-TT |
| XE-RCPOLICY | 启动写值1→0、`callPlatformFunction("renderCompression")` setter强制0（2399–2421） | 外层 `!isRealTGL`，内层 `xeFixEnabled() && !-ngreennorc`。R6的xeFixEnabled又对真实TGL直接false（3629–3634）。两个原donor唯一匹配VA `0x246d3`、`0x2b872` | 两个字节匹配只证明适配这个donor；不证明R6执行过setter、值曾为1、或其与Managed RT失败因果 |
| XE-NODEPTH | `submitDepthResolve` 入口返回0（2292–2304） | 仍为non-native，`-ngreendepthresolve`恢复原调用。原donor唯一匹配VA `0x2c656` | 同为绕过，不是HiZ转换修复；本轮RGBA8 RT不含depth/stencil，不应先加它 |
| XE-FMT | `performTransaction` 不再从IOSurface+0xa4读取格式，直接写 `'BGRA'`（2228–2236） | GA47扩展为 `!isRealTGL || -ngreentgltahoe`；R6日志命中。原donor唯一匹配VA `0x81361` | 是desktop格式强制值，不是通用多格式decoder；对普通非scanout Managed RT的读回没有直接修复证据 |
| XE-PLANES2 | `calculateIOSurfaceDeviceCacheVRAMBytes` 将planes读取从+0xb0改+0x98；可选xor为非平面（2237–2244） | 可达性与FMT相同，但R6实参含 `-ngreennoplanesfix`，所以未应用；无命中符合实参。原donor唯一匹配VA `0x7287d` | +0x98来自上游25G241；不能未经25G83 IOSurface ABI核实启用。xor会丢失多平面语义 |
| XE-BLITALIGN v2 | src/dst地址掩码0x3f→0x0f；只把大、非fast且非64B对齐的linear copy改路由到2D，已对齐仍走原3D（2350–2373） | 整体仍在non-native；`-ngreennoblitalign`关闭。三个原donor唯一匹配VA `0x301a9`、`0x30204`、`0x2c228` | 不能移植旧v1“所有大copy走2D”，上游已记录它让图标丢失。HP各copy分支是否错误尚未测 |
| XE-PAGESYNC | pageon/pageoff调用原函数后，CPU等待resource+0x18→accel+0x380 event machine的vtable+0x188 finishEvent（623–644、684–707） | 包装器代码无native判定，但**安装**位于1919的原始 `checkKernelArgument("-ngreenxefix")` 内；R6无此参数，包装器没有安装。`-ngreennopagesync`仅控制包装器内部等待 | 不是xeFixEnabled门控，不能混淆。native `barrierSubmission` 在8220仍调用Apple原函数，不具有RPL默认ret1绕过的相同前提 |

原donor10个pattern均只有一个匹配，位置/符号/函数内偏移写入JSON。此处没有应用任何补丁。

## 4. 两个属性究竟控制哪里

精确accelerator反汇编 `ga410/private/r4-code-evidence/tgl-accelerator.asm`：

- `0x2732d`：取 `AllowIOSurfaceRenderCompression`，默认参数1；`0x27343`左移22位，`0x27346..0x27358`将结果并入 `accel+0x1190` 的bit22。
- `0x27360`：取 `RenderCompressionMode`，默认参数1；`0x27374..0x2738c`保留低2位、左移20位，并入 `accel+0x1190` 的bits20–21。
- `utilGetProperty<unsigned>` 在 `0x280a6`，读取值、类型转换/默认回退均有原始反汇编；**不应仅因某一层IORegistry可见一个0就认定有效配置变了**。
- 它们不是 `+0x1474` 的同义配置。`+0x1474` 另有启动写入和平台setter；“属性已为0”即使成立，也不能推出display policy不会重新变1。

固定上游 `docs/EXPERIMENTS.md` #28、`docs/HISTORY.md` §9.2 明确记载mode=0选择类型而不禁压缩。源码早期注释“desliga compressão”不能覆盖其后的失败实验结论。

R6历史 `ioreg-accelerator.stdout` 为 **0字节而rc=0**；这是采集对象未产生内容，不是“压缩属性不存在/已关闭”的证据。历史 `ioreg-pci.stdout`有FB的 `FeatureControl.YTiling=1`，却不包含有效accelerator压缩配置。

本地审核后，本轮追加一次只读 `/usr/sbin/ioreg -r -c IOAccelerator -l -w0`，实际获得 `IntelAccelerator`，registry ID `0x100000578`。**当前Development.AllowIOSurfaceRenderCompression=1，输出未见RenderCompressionMode，也未见NOCCS顶层两个0。** 这已超出包内默认推断，证明现有service未带上NOCCS所注入的零属性策略；仍不能代替populateAccelConfig实际读取时的配置bits或 `+0x1474` 内存读数。完整原始回执 `ga410/private/commands/ga411-readonly-accelerator-late-properties.json`、hash及选定属性已收入LOCAL-EVIDENCE.json。

## 5. framebuffer是否会改写+0x1474

使用GA47封存FB实物做本地反汇编，并与上游注释交叉核对：

1. `0x3d70a` 引用字符串 `renderCompression`（位于 `0x1046da`），`0x3d716` 保存symbol到FB+0x4af0。
2. `AppleIntelFramebuffer::setDisplayMode` 的 `0x47db0..0x47e21` 检查controller的accelerator指针与FB+0x4a18；`0x47de1` 调用 `hasExternalDisplay`（`0x66470`）。
3. `0x47df0` 对布尔结果xor1，将 `!hasExternalDisplay()` 存到栈，再以FB+0x4af0的symbol及该值调用accelerator虚表+0x6b8。
4. accelerator `callPlatformFunction` 的 `0x2b872..0x2b875` 从传入指针读一个byte并写 `accel+0x1474`。RCPOLICY精确改的是这里。
5. accelerator start的 `0x246c3` 先写初始化值；`0x246d3` 起的条件分支在特定标志下再写1。RCPOLICY包含两处修改。

**静态结论：存在真实的FB→accelerator改写路径，两个属性不会封住它。** 上游将FB+0x4a18与YTiling联系；本机有YTiling=1配置，但该字段也有其他条件写入，所以尚不能仅用这个property推断本次调用必然执行。

R6没有 `rc1474=`日志。原诊断需 `-ngreenxefix` 安装capture hook，未安装不等于该字段为0。现有记录没有setter调用实参、`+0x1474` 的时序读数或模式切换前后快照，故**运行时是否改写、何时改写、当前值是多少仍未证实**。

## 6. surface/AUX/CCS如何进入与退出

同份accelerator实物显示：

- `calculateIOSurfaceDeviceCacheVRAMBytes` `0x730b9` 检查 `accel+0x1474`，结合格式/尺寸决定额外计算路径。这支持RCPOLICY与IOSurface布局有关，不是泛化的GPU所有压缩开关。
- `enableRenderCompressionWithAccelTask` `0x73774`：读取 `ResourceInfoEntry+0x91`；通过 `IGAuxPageTable::mapRange`（`0x73908`、`0x73988`）设置映射；`0x739a4` 设置bit0、`0x739af` 设置bit1，部分条件下调用resource resolve。
- `fillSurfaceStateAuxInfo` `0x73fc2`：读entry+0x91 bit1；未置位时清surface state+0x18低3位，置位则进入配置AUX路径。R6没有NOAUX修改，保留原逻辑。
- `disableRenderCompression` `0x73f74`：有dirty face时先调用resource resolve，再于 `0x73faf` 清entry+0x91 bit1。
- resource resolve在 `0x73e99` 调用已被NOCCS3绕过的accelerator resolve，随即 `0x73eb1` 清对应dirty bits、`0x73eb6` 清entry+0x64，`0x73f0f` 返回true，**未检查底层返回值**。

因此R6仍可能分配AUX/CCS、给surface state选择AUX，同时跳过部分真实resolve并更新软件状态。这里证明的是**代码路径存在这种语义缺口**，不是已抓到某一张损坏RT实际进入所有这些分支。

缺少的关键联合记录：同一资源的handle/registry关联、尺寸/格式/storage、内核entry+0x91/dirty/CCS范围/AUX映射、最终surface state、Metal m_Info字段、每个命令完成和原始像素。现有日志没有足够信息列出“所有哪些surface实际保留AUX”的运行清单。

## 7. resolveCCS_result=1究竟证明什么

`-[MTLIGAccelTexture resolveCCS:slice:waitForCompletion:]` 在 `mtl-driver.asm` 的 `0x1d179..0x1d3c1`：先FinishEvent，构造参数后在 `0x1d383` 选selector `0x16`，调用 `IOConnectCallMethod`。只要该调用返回0，就置返回byte为1；wait参数为真时再FinishEvent。

CPU lock `0x19b82` 检查 `m_Info+0x1ad` bit2 **或** `resource+0x1c` bit0，决定是否调用上述resolve；之后返回IOSurface base或资源映射地址。它不验证转换后的每一个像素。

R4 tracer实录：三个实际RT均为format70（RGBA8）、257×65、storage1，pitch108=1536、pitch10c=1040、bpp=4、tiling=3、flags16a=0208、flags1ac=1206、resource1c=1，且 `resolveCCS_result=1 wait=1`。

- `resource1c` bit0足以触发这里的CPU resolve分支，即使flags1ac不含另一触发位。
- tiling=3、flags0208/1206本身不是可擅自命名的“CCS已转换”标志，也不是GPU实际surface state/AUX映射。
- tracer看到userland方法进入/返回，没有追踪到同一handle的kernel分支，**不能据此断言这三次一定发起了真正GPU解压**。
- NOCCS3实际命中加上上述返回规则，解释了为何API success可以与错误读回同时存在；没有证明NOCCS3是所有错误的唯一原因。

## 8. Metal/libxedrv与内核的状态视图

固定上游libxedrv在302–308复制descriptor并将 `allowGPUOptimizedContents=NO`；373–391包装device/IOSurface/heap创建入口，无native TGL设备判定。R6 WindowServer实录 `sem compressão: dev=1 ios=1 heap=1 heapoff=1 heapsize=1`，证明hook安装；不能证明每张texture禁压缩。

上游 `docs/CATALOG.md` §4的v12记载此尝试“no effect”，旧driver通过私有struct读descriptor；`docs/HISTORY.md` §13也记录MTL15/NOAUX后的RT仍有压缩特征、hang未改变。这些是作者在其RPL机器上的结论，不能当HP的对照实验。

本地捕获MTL实物 `AppleIntelTGLGraphicsMTLDriver` 在offset `0x18c28` 的3字节为 `31 c9 90`，反汇编为xor ecx/ecx; nop，随后把0写到 `m_Info+0x160`。这就是MTL15，原来会读取shared resource+0x18。它发生在IOSurface初始化路径，**不是本轮新增功能**。

因此不能只看某一侧字段就认定压缩状态一致：Metal一个字段已被置0，kernel policy/entry仍可能为压缩；其他Metal flags与shared resource bits也继续参与CPU锁路径。尚缺同一surface的前后联合快照来判断具体错配。

## 9. upload/blit顺序修复是否已经执行

必须区分三个不同位置：

1. **libxedrv nocopy（435–480）**：offset非256对齐且单层/单slice的2D texture，改为managed纹理并 `replaceRegion`。不依赖native/xefix。R6 WindowServer有实际记录：935×15、fmt80、offset0x20、bpr3744→copy；这是一处真实运行证据。
2. **libxedrv fill/buffer-copy（482–585）**：fill改用shared pattern buffer的相对offset4 copy；aligned buffer→buffer copy改为经temporary的两次不对齐copy，使其走3D路径；command buffer完成后归还temporary。env `XE_FILL_NATIVO`、`XE_COPIA_NATIVA`可关闭。R6有 `fillfix: fill=1 fill4=1 cópia2D->3D=1` 安装记录；该WindowServer节选无FILL/COPIA命中，不能说对应每次上传都执行修正。
3. **kernel BLITALIGN/PAGESYNC**：如矩阵所示在R6未启用。这不是libxedrv“没加载”；它们处理的pageon/pageoff与texture blit也不等于buffer→buffer包装。

尤其PAGESYNC：上游原文说它补偿V130跳过Apple barrier。R6 `Gen11::barrierSubmission` 对真实TGL直接调用原函数。需要观察实际event/完成状态才能判定HP是否仍有跨引擎同步缺口，不能单凭少了PAGESYNC就宣称复制它可修好。

## 10. R4/R5/R6像素证据重新分类

| 回执/阶段 | 实际结果 | 可以得出的结论 |
|---|---|---|
| R4 odd-size upload/sample | R8/RGBA8/BGRA8，shared/private各0/16705错误 | 这些CPU上传→GPU compute读回在当次测试通过；不是Managed RT GPU结果的替代 |
| R4 managed-source | 三种源格式各0/16705 | managed源→private RGBA8 RT→GPU copy的相应路径当次通过 |
| R4 IOSurface CPU source | 三种源格式各0/16705 | 相应CPU生产纹理可被GPU读取 |
| R4 managed-target | CPU/GPU不同字节47630、4、195；CPU错误像素16705、1、49（总16705） | 有真实、可重复的读回差异，不是仅显示扫描问题；输出RT始终RGBA8，不是三个不同RT格式 |
| R4带tracer复现 | 第一组不同字节47624/47645，仍16705/16705；另外两组4/195及1/49 | 全错模式重复但错误内存字节数会变；不能凭pattern相似给出确定tile/压缩原因 |
| R5 no-copy控制 | 在设备初始化处阻塞，晚于既有RCS hang约85秒 | 没有提交测试GPU命令，无像素结果，不能计FAIL/PASS或归咎它触发hang |
| R6 | 池容量与padding命中、用户确认花屏未改善；只有无GPU提交的surface参数控制 | 没有R6版Managed RT逐路径像素新回执；不能将R4的错误数写成R6测量 |

旧探针96–104行先计算CPU vs GPU字节差异，随后 `memcpy(out.contents,cpu,...)`。105–117行expected比较此时读的是CPU数据。所以GPU在**同次**managed-target测试各自错多少、两条路径是否都错，没有被完整记录。

旧回执也没有逐字节完整dump，只打印前四个错误；既有数字不能反推出未保存的原始内存。新诊断必须分别保存GPU、CPU、expected缓冲区及文件hash。

R5的80EU/10SS/5 dispatcher保留为已验证事实；L3=8为回退。R6池扩容/padding保留为已验证事实；短时无新报告不是hang恢复或长期稳定性验收。R7参数转换和submitBlit空context均不改变本轮主线。

## 11. 可重复的分阶段诊断材料

- `ga411/tools/managed-rt-probe.m`：从旧managed-target用例提取同一图案/三角形/nearest shader/尺寸/clear与storage，**一次进程只测一个源格式**，RT固定RGBA8 Managed。
- `ga411/tools/trace-managed-cpu.m`：直接include旧 `trace-texture-cpu.m` 的getBytes/resolve observer，再加带ABI检查的lock observer；只在原方法周围观察，不主动调用额外resolve。
- `ga411/tools/verify-pixel-dump.py`：在Linux离线重建expected、检查input图案、资源属性、每个CB状态与完整dump，计算三组差异及SHA256；不信任result.json里的PASS标签。
- [PIXEL-PROTOCOL.md](PIXEL-PROTOCOL.md)：运行阶段、完整dump、判定规则、单因素比较和缺口。该文档是准备材料，不是已执行回执。

两个模式应分别对照：

- `legacy`：保持旧的一条command buffer内 render→synchronizeResource→texture-to-buffer copy→wait→CPU getBytes，仅修正测量和数据保存。
- `staged`：render完成→GPU copy快照→显式sync完成→GPU copy快照→CPU getBytes；分开命令边界是**诊断因素**，不能与legacy混作同一测量，也不称为驱动修复。

精确比较有效RGBA8像素字节，排除row padding；分别给GPU vs expected、CPU vs expected、CPU vs GPU的不同字节/错误像素和前32个字节差异，并保存完整二进制。只有两条路径各0字节/0像素错误且所有命令Completed无error，才记PIXEL_PASS。

staged若同步前GPU快照错误，即使同步后两条路径通过，整体仍FAIL并单列各阶段。legacy保留历史shared上传buffer和4倍大小output buffer分配，但诊断增加日志/快照且改为每进程单例，未复现原来的完整进程内堆分配时序；因此必须先建立本探针在R6的实测基线，再对任何功能改动做同探针A/B。

CPU getBytes无单独GPU command status；其resolve/lock返回值只作观察。userland observer仍看不到kernel entry/AUX table或 `+0x1474`；报告不得用NOT_OBSERVED替换为0/PASS。

### 11.1 本轮真实执行的验证

本地审核后进行只读SSH身份与IORegistry采集：目标仍为R6的同一boot session、25G83，WindowServer PID197/state Ss，Apple clang 21.0.0。把两个诊断源码通过stdin送入目标机clang，使用 `-fobjc-arc -fno-modules -Wall -Wextra -Werror -fsyntax-only`；均rc0且无stderr。tracer的历史include在本地展开，stdin hash已记录；probe调整分配大小后重新语法检查也rc0。**没有生成或运行新探针可执行文件，没有创建Metal device或提交GPU工作。** 证据：[NATIVE-CHECK.json](NATIVE-CHECK.json)。该检查不是完整link/运行验证，lock方法ABI仍需执行时核实。

离线dump复核器验证十组人工样本：三种源格式legacy正确样本、GPU错/CPU对、两侧同样错误、命令status错误、缺GPU dump、expected损坏、staged全对、staged同步前错但同步后对。错误/缺失样本均被拒绝；只有人工全对样本通过。结果明确标记 **SYNTHETIC**，不列入GPU PASS：[SYNTHETIC-VALIDATION.json](SYNTHETIC-VALIDATION.json)。

## 12. 最小差异决策

本轮**没有达到生成新驱动/镜像的证据门槛**。

| 候选单因素 | 支持它的证据 | 缺少的直接联系 / 当前决定 |
|---|---|---|
| 仅复用上游RCPOLICY的两个byte patch，独立于xefix/RPL分支 | 精确donor匹配、FB→setter静态链、R6门控阻止它 | 缺+0x1474运行值、受影响surface标识、相应像素对照；暂不实施 |
| 仅NOCCS属性注入 | 分支遗漏确定 | 作者已记录不是完整禁压缩；不能当首个修复 |
| 仅NOAUX或NODEPTH | 原donor精确匹配 | HP AUX-TT缺失未证实；NOAUX单改可能使状态不一致，NODEPTH与当前color RT没有直接因果；暂不实施 |
| 仅PAGESYNC | 上游有同步算法 | native保留原barrier，尚无等待缺失实证；暂不实施 |
| 仅BLITALIGN v2 | 原算法与三个精确匹配 | 未测HP具体offset/copy routing失败；暂不实施 |
| PLANES2 | 上游其他Tahoe build ABI修复 | 25G83偏移未核实、多平面不是本轮RGBA8 RT主变量；保持禁用 |

后续若运行观察证明某一项与特定资源错误直接相连，才做R6→单因素B，保留其他字节、系统11组件、KC及拓扑/池算法，单独命名镜像并保存全差异/回退。不能一次打开全部压缩链补丁，否则结果无法归因。

当前最有价值的下一步是**经授权的一次受控进程内像素采集**，先补齐legacy模式的双路径expected数据及lock/resolve时序。历史有RCS hang，30秒alarm只能终止可调度的用户进程，不保证内核/GPU可取消；故不把这次新运行自动认定为低风险并自行执行。

结论保持：**成套兼容逻辑未完整作用于native TGL已查明；与每类花屏/读回错误的直接因果、以及最小修复的FAIL→PASS尚未定位/验证。**
