# Managed RT 单进程采集协议（准备材料）

## 状态与边界

本协议尚无新GPU运行回执。旧R5启动有RCS hang，不能把30秒进程alarm当作GPU复位保障。运行需要用户批准；不启动新镜像、不修改系统driver/KC、内部EFI或安全设置。先保留R6健康/版本身份再决定是否运行。

## 固定输入

- GPU：真实8086:9A49；macOS 25G83；NG应为R6 UUID `REDACTED-SESSION-ID`。boot session必须单独记录，不能假定仍为旧session。
- 257×65，16705像素，单mip/单slice/单sample。
- source依次可选R8Unorm、RGBA8Unorm、BGRA8Unorm；每次只测一个。
- 原始channel图案 `(x*13+y*29+c*61)&255`；source shared、shader-read、allowGPUOptimizedContents请求NO；source row pitch按256对齐：R8=512，其他=1280。
- target固定RGBA8Unorm、Managed、RenderTarget（不额外加ShaderWrite）、allowGPUOptimizedContents请求NO；输出row pitch1280。clear=(1,0,1,1)，完整三角形覆盖、nearest采样，沿用旧shader。
- 格式标签是**source**，不是target；BGRA源的R/B在expected中互换，R8采样的非R通道为0、0、255。

## 实机运行前的本地/只读身份核对

先读取sw_vers、kern.bootsessionuuid、kern.bootargs、WindowServer PID/状态、现有DiagnosticReports清单和加载NG UUID；记录源文件/可执行文件/tracer/MTLDriver/libxedrv的SHA256。只选所需环境变量记录，不打印整个环境或凭据。

本轮静态证据表明两个禁压缩属性有效值、+0x1474及kernel surface标志未被旧回执采到。即使新probe像素通过，也不能补记为这些状态已经观察。

## 构建与执行约束

原生构建材料为Foundation、Metal及历史tracer引用的ObjC runtime。探针用ARC构建；tracer也是进程内dylib。可以先仅 `clang -fsyntax-only`，它不会创建Metal device或提交GPU工作。

批准执行后，构建放独立用户态临时目录，记录原生编译器输出。首次只运行一个 `R8 legacy`，启用进程内tracer，输出到全新目录；不自动循环。后续RGBA8/BGRA8/staged需先审阅前一回执及健康状态。

调用接口：`managed-rt-probe R8|RGBA8|BGRA8 legacy|staged NEW_OUTPUT_DIRECTORY`。`GA411_TRACE_DYLIB`指定tracer；不注入到WindowServer、不改launchd环境。源码设置30秒alarm，但不能保证在driver阻塞时退出。

## 阶段及可观察内容

| 阶段 | legacy | staged | 记录 |
|---|---|---|---|
| CPU upload | replaceRegion | 相同 | source原始字节、pitch、资源属性 |
| GPU write | render encoder | 相同 | legacy与后续同CB；staged单独CB完成状态 |
| GPU read before explicit sync | 未单列 | texture→shared buffer copy，另一个CB | 完整gpu-before-sync.bin和expected diff；copy本身可能触发driver内部转换，不称为raw VRAM |
| 显式sync | 与render/copy同CB，位于copy之前 | 独立sync CB | 每CB status/error；此API不直接证明kernel CCS resolve已提交 |
| GPU read after sync | 同CB texture→buffer | 独立copy CB | gpu.bin，**在CPU getBytes之前**保存并单独验证 |
| CPU read | getBytes | 相同 | 复用tracer观察getBytes→lock→resolve进入/返回；cpu.bin独立保存 |
| 比较 | 三组比较 | 加pre-sync expected比较 | exact active bytes、错误像素、首32个差异；padding排除 |

staged模式改变命令边界/数量，是诊断A/B因素，不能声称与legacy命令序列相同；不与kernel功能补丁同时改变。

## 产物与判定

每例目录：input.bin、expected.bin、gpu.bin、cpu.bin、result.json；staged另有gpu-before-sync.bin。配套保存stdout/stderr、进程退出码、源/二进制hash、身份、命令超时和健康回执。失败或超时的部分产物仍保留；没有result.json不计PASS。

取回后使用 `python3 ga411/tools/verify-pixel-dump.py DIRECTORY` 重新生成逐路径diff与原始文件SHA256。复核器独立重建expected、检查每条CB状态；退出0仅表示该dump的像素与command状态通过，身份/trace和kernel状态仍需配套证据。它不把两份相同的错误数据判为PASS，也不信任result.json自称成功。

`result.json`记录资源实际class/format/storage/usage/尺寸和commands；requested allowGPUOptimizedContents是**请求值**，不是实际压缩判定。

- GPU_expected错、CPU_expected错：两者都失败，不能仅用它们互相一致来宣称成功。
- GPU_expected通过、CPU_expected失败：把范围收窄到该copy之后的CPU路径/表示或转换；还需同surface的kernel状态才能确定压缩还是布局/同步。
- GPU_expected失败、CPU_expected通过：GPU copy/readback路径有问题，不能直接断言render写错。
- legacy失败、staged通过：存在对command边界/顺序敏感的证据，不是某个kernel fence已被证明错误，更不是持久修复。
- 两条expected通过且所有CB Completed无error：该单例PIXEL_PASS；不能推出桌面全局、视频、depth/stencil、sleep/wake、hang恢复全部正常。

staged还要求同步前GPU快照expected通过；如果它失败而同步后通过，保留该差异并记整体FAIL，不掩盖前段错误。legacy保留历史shared upload/output分配大小；新增日志/快照与单进程单例改变了分配时序，不能宣称复现了旧进程的精确heap地址。

CCS resolve完成判据不能只用 `resolveCCS_result=1`。还需资源状态前后与像素对应；当前进程内tracer没有kernel AUX映射/dirty/rc1474读取能力，缺项明确NOT_OBSERVED。

API依据（通过Context7核对Apple当前文档）：[getBytes](https://developer.apple.com/documentation/metal/mtltexture/getbytes(_:bytesperrow:from:mipmaplevel:)) 本身不负责同步GPU写入；[managed resource synchronization](https://developer.apple.com/metal/synchronizing-a-managed-resource-in-macos) 要求在CPU访问前完成同步命令。调用符合API要求，不代表实验driver实现已经正确。

## 新镜像A/B的进入门槛

只有关联到一个明确上游算法后，才从R6复制出新候选，列出全部功能差异、命中检查、相同probe指标和回退。不得整体启用xefix或附带RPL寄存器修改。每次一项；先保留失败样本，再讨论物理启动。当前未达门槛。
