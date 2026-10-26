# GA43 需求到工件/命令/真实结果的验收映射

本表逐项区分“工程/调查已经执行”与“目标已经实现”。证据路径相对GA43；历史GA42
输入路径仅只读。FAIL/BLOCKED/NOT_TESTED不因测试框架exit0而改成PASS。
最终seal/index/receipt在`evidence-manifest/`及排除的`logs/seal-verification/`，
最终Git HEAD/完整SHA集合由receipt补齐自引用最后提交。

| ID | 明确需求/输入/命令 | 工件及真实证据 | 验收 |
|---|---|---|---|
| 01 | GA40/41/42只读，新目录/独立分支，固定3源码pin | `GA43-INHERITANCE.md`、`inherit-seal-002`、baseline a60352c、Git无remote | 来源继承PASS |
| 02 | 读取GA42 FINAL、ANV-DARWIN、DRM-INTEGRATION、NULLMOTH-INTEGRATION、GIT-COMMITS、NEXT-STEPS | 规定报告读证及`GA43-INHERITANCE.md`；NEXT-STEPS实际不存在，依赖链在原FINAL E节 | 前5已读；缺文件明确记录 |
| 03 | GA42 HEAD ebc63b2、receipt/hash/封存一致 | `inherit-seal-002`四组标准sha256sum；`verify-inherited-native.py`固定receipt/index/source seal | PASS来源，不是驱动PASS |
| 04 | 原生编译/链接失败及早期下载证据 | 原GA42失败日志、`reports/OFFLINE-EXCEPTION.md`；本轮新原始日志独立目录 | 历史违规保留，未追认；GA43无下载 |
| 05 | 本地Clang targets、LLD/cctools/osxcross、SDK/sysroot、CMake/Meson/Ninja、LLVM工具、KDK | `TOOLCHAIN.md`、inventory/derivation/cache日志；/opt不可读明确限定 | 调查PASS；工具链完整性BLOCKED |
| 06 | 真实用户SDK、libSystem/libc++/tbd、合法官方获取步骤 | `TOOLCHAIN.md`、`GA43-ANV.md`；gate缺输入/拒kernelSDK原始exit2 | 未找到合法完整输入；无假SDK |
| 07 | C Mach-O对象真实编译/arch/hash检查 | `darwin-probes-003/01-c-object`、LLVM及contract-c_object、sha256 | PASS编译 |
| 08 | 最小dylib真实严格链接、installname/rpath/符号/import | `darwin-probes-003/02-minimal-dylib`、`inspect-darwin-probe.py` | FAIL dyld_stub_binder；诊断dylib不是成功替代 |
| 09 | C++/libc++探针 | `03-libcxx-object`及`03-libcxx-link` | FAIL string/c++/System缺失 |
| 10 | 用户SDK/libSystem探针 | `04-system-object`及`04-system-link` | FAIL stdlib/System缺失 |
| 11 | ICD导出名探针、Mach-O/exports | `05-icd-names-object`/`05-icd-names-link` | 对象PASS；严格linkFAIL；仅data symbol fixture，不是Vulkan ABI |
| 12 | 每探针argv/cwd/stdout/stderr/exit/hash；不能以空输出/动态lookup过gate | unique logs，`probe-negative-witness-assert-001`、`probe-contract-reject-dynamic-001` | 八rawexit0零输出仍strictfalse；unbound binder拒绝 |
| 13 | 首两步失败先定位，ANV不立即完整Meson调试 | `anv-reviewed-gate-001` exit2；内部fresh probe，不信caller JSON | Gate负测PASS；合法SDK正向仍未验 |
| 14 | 固定Mesa原patch/crossfile/platform/exports/依赖隔离 | `anv/patches`原样、`tools/anv-darwin-attempt.py`/`GA43-ANV.md`；git archive、fuzz0、nodownload、crosslink/pkgconfig | 工程推进PARTIAL；未重跑已通过Linux构建 |
| 15 | libvulkan_intel.dylib/intel_icd.json，x86_64MachO/系统依赖/loaderABI/CLC | 无实际完整产物；最后前置错误见gate/probes；无LinuxELF替代 | BLOCKED，非ANV初始化PASS |
| 16 | XNU真正模块/包、target flags、libkmod/IOKit/libkern/C++ imports | `GA43-XNU-LINK.md`、`native-module-link-reviewed-001` | FAIL旧LLD忽略-kext，无MH_KEXT_BUNDLE |
| 17 | 不停留更多.o，实际链接单元与KDK必要性 | `native-relocatable-reviewed-001`、MH_OBJECT/imports/hash；精确KDK非-r硬前提 | 实际-r PASS；最终模块/KC仍BLOCKED |
| 18 | 内核对象来源/ABI不可混旧gx_client布局 | f8b5911：新5同编译，继承4对象固定seal/source/layout/SDK检查；任意旧path负测 | GatePASS；目标25G83 ABI未知 |
| 19 | Tahoe KPI/legacy kext/DriverKit/KC及SIP/AMFI边界 | `GA43-XNU-LINK.md`及初审；缺匹配exports，不推断KPI已移除 | 目标兼容性NOT_TESTED；未安装/改策略 |
| 20 | DRMfd→每openclient→GEM→XNU、render/cdev或兼容transport | `GA43-TRANSPORT.md`、现有GX42Service/IOUserClient/gx_client | client/backend部分有真代码；nativefd/render/pager/用户IOConnect仍BLOCKED |
| 21 | Linux/BSD ioctl方向位、nestedpointer、真实身份 | be618d1、`drm-wire-tests-001`，保留原样intel_get_kmd_type拒nmdrm | CPU合同PASS；不谎报i915或枚举GPU |
| 22 | mmapoffset/地址/引用/close/death/detach/copyout/并发 | 2ba885e、mmap-tests002、受锁client、原reaper；33f2099 alternateclose回收 | 标准cookie＋私有CPU-map代码PASS；不是fd mmap/原生runtime |
| 23 | 官方i915 VM/context/BO/VA生命周期与许可 | `upstream_vm_destroy.inc`、`gx_vm.c`、`VM-CONTEXT.md`、`OFFICIAL-REUSE.md`、upstream exact比对 | host所有权/原函数复用PASS；不是PPGTT/hardwarecontext |
| 24 | 请求/失败/资源保活/fence寿命基础，不得假执行 | a519e82、`request-error-tests-001`、`request-error-darwin-001` | host请求有界/首错/取消/释放PASS；无GPU fence/success signal |
| 25 | 真GPU VM/residency/cache/DMA/engine/exec/scheduler/IRQ/reset | 未形成后端；原ANV调用追踪在`GA43-FRONTEND.md` | NOT_IMPLEMENTED/NOT_TESTED；本轮硬件操作禁止 |
| 26 | 四份NullMoth补丁，Intel/AMD/NVIDIA路由/冻结/冲突/私有隔离 | 原样`nullmoth/patches/0001..0004`，继承封存及原报告合同 | 保留PASS来源；不重跑旧测试冒充新runtime |
| 27 | NMXGPU/Accel/plugin/同PCI/DeviceQueueBuffer连续链 | `GA43-FRONTEND.md`真实源码定位表 | 源码路径可定位；无目标claim/VkDevice/queue/buffer证据 |
| 28 | 合法已有同来源AIR/SPIRV shader受限端到端尝试 | 同一sp1.ll/spv/tool SHA、validatorexit0、新Intel桥接SIGSEGV-11/gdb栈；无Gen12输出 | 尝试已执行，链FAIL；非Metal/GPU成功 |
| 29 | 每实质单元相关测试/diffcheck/范围/指定add/localcommit/完整SHA，无push | `GIT-COMMITS.md`、Git完整log、unique test/build logs、receipt | 逐单元本地提交；SDK/KDK/密钥/缓存不入Git |
| 30 | 独立审查、必要修复、原审查保留 | `audit/ga43-initial-native-review/`、`audit/ga43-resource-review/`、F4澄清/FOLLOWUP及各修复SHA | 按实际独立followup结果交付，不把主代理核验作独立PASS |
| 31 | 九级测试边界 | `ACCEPTANCE.md`分级表及各rawexit | HOST/CPU/CROSS/-r不推出module/runtime/GPU/Metal |
| 32 | 中文报告、清单、link/ANV/XNU/DRM/许可/SHA/首次Compute链、七问 | 本表＋`FINAL-REPORT.md`、`TOOLCHAIN.md`、各GA43报告、`OFFICIAL-REUSE.md`、`ACCEPTANCE.md` | 严格总目标需真实产物；缺输入只能PARTIAL/UNMET |
| 33 | 持久记录、配套makecheck、最终内容/成员/hash封存与停止 | companion config/continuation/historyhp104起、最终makecheck日志、seal/receipt | 以最终实际回执为准；无IMG/USB/EFI/目标变更，IMG均null |

本表不以“表行已填满”代表33项全PASS；明确标出的最终产物/运行缺失保持未达成。
