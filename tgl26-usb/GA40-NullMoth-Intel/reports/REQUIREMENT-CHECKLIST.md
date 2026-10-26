# 提示要求 → 实物证据验收清单

目标是完成GA40本轮授权的离线源码审计、可运行复用原型、Intel原生编译尝试、精确内核缺口、三独审、中文决策与私有封存。完整macOS GPU驱动是长期目标，本轮不以伪造设备、ioctl成功或软件Vulkan替代它。下面逐项区分本轮交付与未达成的硬件能力。

## A — 来源、能力与许可

| 明确要求 | 实物/命令/结果 | 验收边界 |
|---|---|---|
| GA3.1–3.9只读，先核历史 | `logs/ga39-entry-verify.json`；`logs/ga39-exit-verify-035/{receipt.json,stdout.txt}`，退出0，manifest同为1e039df9… | 本轮未改旧树；不是重新执行旧实验 |
| NullMoth完整commit/关键SHA/干净来源 | `sources/provenance.json`、`sources/nullmoth-tracked-manifest.json`，639文件；独审`audit/api-license/audit.json`与recheck002 | 47f818b…/v2.4.3，源码字节和身份，不是Apple运行验证 |
| 指定README、HOW-IT-WORKS、CARD-SUPPORT、TROUBLESHOOTING、CHANGELOG、LICENSE及plugin/translator/nvk/kexts | `reference/nullmoth-api-inventory/{README.md,source-pin.json,file-provenance.json}`；metal两报告、drm/FB报告 | 全639文件provenance；实际依赖判断有函数/文件/行号，不凭目录名推断完整实现 |
| Mesa对应身份与构建差别 | `reference/MESA-VERSION-DISTINCTION.md`；021/022原始HTTP响应；Intel两报告及manifest | NullMoth base为26.3.0-devel，本轮26.2.3；不混同patch适用性 |
| NMDRM VERSION/GET_CAP/query/GEM/VA/context/mmap/submit/sync是否存在 | `drm/NMDRM-AUDIT.md`、`drm/I915-UAPI-MATRIX.md`、`reference/kernel-inventory/ERRATA.md` | 仅4generic cases；i915默认ENOTTY；GETCAP.value为标量0合法否定 |
| NMXGPU/NMXAccel是否公开完整、IntelFB是否加速 | `metal/API-DEPENDENCY.md`、`display/NMINTELFB-AUDIT.md` | 固定来源未找到完整Intel执行后端；FB只有固件scanout参考 |
| 文件级许可，PolyForm/LGPL/Mesa/NVIDIA | `reference/licenses/`、`reference/nullmoth-api-inventory/file-provenance.json`、`reference/mesa-licenses/file-level.json`及023 | 逐文件证据/Unknown均保留；不是全库MIT或法律清权 |
| 外部AIR及NVIDIA头冲突 | G1初审及recheck、`reference/licenses/LICENSES.md` | 外部AIR运行时未归档/许可Unknown；两NVIDIA头冲突未解决，不公开分发 |

## B/F1 — 真实Metal链与运行原型

| 明确要求 | 实物/实际结果 | 验收边界 |
|---|---|---|
| Device Registry→Metal Device/Queue/Buffer/Encoder/Resource/Pipeline→Vulkan | `metal/API-DEPENDENCY.md`，`reference/nullmoth-api-inventory/`调用库存；25入口 | NVMTLDevice包含nvmtl_vk.c同TU，未构建整个ObjC插件 |
| 标准Vulkan/扩展/NVK/NVRM/macOS私有依赖逐函数分开 | `metal/VULKAN-BACKEND-AUDIT.md`、G1独审；19扩展库存 | IOSurface假fd+NVK私有hook、CPU事件、非swapchain展示不标通用API已可替换 |
| 尽可能真实复用而非全新Metal | `nm_backend.c`原样include上传helper；测试原sample-position helper；实际Rustcrate源未改 | C facade是Metal-like有限接口；未冒充MTLDeviceABI |
| 能力协商/unsupported拒绝 | `metal/backend-adapter/{nm_backend.h,nm_backend.c}`、`prototype/tests/backend_test.c`；007/008 | NVIDIA/IOSurface/硬件能力明确拒绝，不空实现 |
| Device、Buffer/Image生命周期、copy/fill、编码/submit/wait/回读/释放、失败清理 | 006–011 release及ASan+UBSan双后端全exit0；G3独立对抗probe | Image只create/bind/destroy；没有render或共享；CPU submit是模型而非GPU |
| CPU+固定Lavapipe身份/禁止硬件发现 | `build/backend-release/receipt.json`固定ICD SHA；007/008软件身份输出 | 直接dlopen软件ICD，不走loader自动硬件发现 |
| 多线程、过期handle、队列顺序、资源busy、配额、多设备、注入失败 | `audit/drm-safety/{AUDIT.md,audit.json,COMMANDS.md}`及logs | 没有并发close契约；close要求join所有使用者，已披露 |
| CPU模型→facade→adapter→CPU/软件Vulkan→独立回读 | 018/019，`prototype/results/cross-component-001/`的input.bin/output/result | 显式CPU copy，不是BO mmap、zero-copy或真实ANV |
| 实际Rust AIR/SPIR-V部分复用 | `metal/translator-prototype/{REPORT.md,build-source/,results/manifest.json}`；032摘要核验 | 8选定LLVMIR样本+validator通过；24/38targets通过，14非通过保留；真实metallib未验 |

## C/F2/F3 — Intel用户态、原生编译与分里程碑

| 明确要求 | 实物/实际结果 | 验收边界 |
|---|---|---|
| 固定支持8086:9A49的Mesa | 26.2.3/31e9a6b…；官方/mirror tagrefs一致；12816 trackedSHA | 静态build-table身份，不是真实GPU探测 |
| Intel compiler/dev/ISL/common/vulkan、资源/URB/RT/pipeline/command/submit | `intel/`报告、UAPI矩阵、G2审查源级路径与feature gates | 本轮使用真实成熟源码；完整device/resource合同仍缺 |
| 实际构建Intel组件，无算法重写 | `reference/intel-build/build-adaptation.patch`、harness、manifest及008–012 | 构建图改动隔离在副本；四库实构建，TGL实际BRW，Jay不用于输出 |
| SPIR-V→NIR→Intel Compiler→TGL候选→IGA尝试 | SPV1020B→208B候选a4ee1b…；直接NIR336B另列；036哈希整合 | 完整IGA最后8B失败，前缀200/328B解码；不是完整静态验证/数值证明 |
| 明确编译前提与失败 | Intel报告harness断言日志、lowering/push/callback补齐 | 不关闭编译器断言骗通过；离线driver-supplied值不是GPU绑定证明 |
| 原生命令生成子集 | 020、`prototype/vulkan/NATIVE-PACKET-REPORT.md`，原样genxml pack8B NOOP+BBE | 只格式；没有完整ANV command workload或dispatch |
| 真正ANV build与Darwin首失败 | `logs/intel-anv-attempt-022/` CLC requires LLVM；023缺SDK/sysroot | 无ICD，无加载、枚举、init或提交；不是已运行ANV后的内核失败 |
| 不能拼接独立成果成端到端shader链 | FINAL/Intel/translator报告均明确输入来源 | Intel输入来自glslang，未消费真实Rust输出；transfer成功与shader生成独立 |

## D/E — 精确ABI、模拟边界与显示

| 明确要求 | 实物/实际结果 | 验收边界 |
|---|---|---|
| 优先TGL i915，不能直接套xe | `drm/I915-UAPI-MATRIX.md`与JSON，KMD按drivername选而非PCI直接选 | 本库存针对i915，xe为不同UAPI |
| VERSION/CAP/GETPARAM/QUERY/GEM/close/mapping/context/VM/submit/sync/region/tiling/cache/engine | `reference/i915-abi/`47组requests+255布局项，原头probe和输出 | Linux/Darwin分开，10请求不同；顶层结构与nestedcopyin/out明确 |
| 实际NMDRM errno和Darwin方向 | 源码静态表、repairs001/002 | Darwin正errno与Linux负内核返回分开；不是实机ioctl结果 |
| 精确C布局→可运行CPU模型 | `drm/mock/layout_probe.c`→uapi-v2 ABI，`i915_model.py`；016/017/029 | 40B sync wait/deadline32，synthetic arena；真实映射/submit拒绝 |
| 生命周期、错误、overflow、并发、假设备拒绝 | 14模型测试；G3独审69控制；KMD原函数030031七CPUstub控制 | Mockidentity拒绝；CPU context/VM ID不是GPU对象/VA，CPUsignal非GPUfence |
| 原失败/真实修前源/diff | 015，`reference/repairs/uapi-initial/`、`drm-safety-001/`、G3原反例及recheck | 原VERSION nullptr成功真实复现，修后EFAULT，零长度query仍允许 |
| 最早device init及第一个内核缺口 | `reports/DEVICE-INIT-BLOCKERS.md` | transport/PCI→nmdrm身份→timestamp/topology→GEM/mmap→VM/context/submit/sync；无FakeSuccess |
| PCI/BAR/Apple竞争、GEM页所有权、GGTT/PPGTT、IRQ/reset/PM/固件 | `reports/INTEL-NATIVE-PORT-PLAN.md`、G3静态审查 | 规划/缺口，未实现硬件动作；GuC/HuC不是NVIDIA GSP |
| DisplayVersion/9A49/eDP/scanout/BAR/pixel/stride/vblank/IOSurface | `display/NMINTELFB-AUDIT.md`有源码行/边界 | firmware linear XRGB8888；无GPUrender/真实vblank或WindowServer完成合同 |
| DISPLAY_ONLY/COMPUTE/RENDER独立验收 | 显示报告与实施计划 | 全部本轮实机NOT_TESTED；FB显示不提升加速状态 |

## G–L — 审查、决策、交付和禁止事项

| 明确要求 | 实物/实际结果 | 最终验收条件 |
|---|---|---|
| G1独立API/许可审查 | `audit/api-license/`初审、反例、recheck001/002 | 最终0open，不能丢弃第一次残留失败 |
| G2独立Intel/ANV审查 | `audit/intel-anv/{AUDIT.md,AUDIT.json,FINAL-BINDINGS.json}`；最终6审查文件+4报告SHA实核匹配 | 无MUSTFIX；release/debug重放一致；prefix-only IGA；最终冻结收据feddb7d7…，039中间字节不匹配失败保留 |
| G3独立DRM/XNU安全 | `audit/drm-safety/`初审/recheck001 | 真实F1/F2关闭，69controls+14tests；F3严格模型限制保留披露 |
| 三明确决策及唯一主线 | FINAL五节；`REUSE-MATRIX.md`、`DEVICE-INIT-BLOCKERS.md`、`OLD-VS-NEW-ROUTE.md` | 原生Intel唯一推荐，不把旧NF/ACC未知当准入条件 |
| 唯一GA41工程目标 | `reports/GA41-NEXT-STEPS.md` | Probe&GEM真实设备/内存对象闭环，仅规划，未实施 |
| 规定目录/文件 | `tools/delivery_check.py` REQUIRED列表及逐项状态证据 | 所有规定报告、源码、构建、日志、反例、diff必须实存，不只Markdown |
| 16项状态 | `reports/FINAL-STATUS.json`及FINAL表 | 证据限定、state以SHA绑定，3硬件NOT_TESTED/批准NO |
| 四有界里程碑 | goalplan及FINAL九节/history | 已完成工作不无限重开，同UNKNOWN不无界扩审 |
| 持久记录 | `state.json`、append-only `history.json`、`continuation.md` | 最终记录必须指出真实seal验证回执，不含自指manifesthash |
| make check | `logs/repository-check-024/`退出0 | 仓库源码未改，无需重复整个检查 |
| 真实交付验收 | `tools/delivery_check.py`最终实际日志 | 不仅文件存在，还核来源/SHA/成功stdoutstderr/修前/当前binary/三审绑定 |
| manifest/selfhash/独立verify | `tools/seal.py`、`verify_manifest_independent.py`、033fixture8控制 | 实际create与只读双verify/selfhash通过后才关闭goal；不能先称已封存 |
| 私有迁移与外部依赖 | `reports/PRIVATE-MIGRATION.md`、034记录457外部文件/128ELF扫描 | 非全Nix closure或Apple许可；副本重放，原件只读 |
| 无部署/EFI/固件/门禁/SSH改机/MMIO/Batch/Hang/物理读取/公开上传 | 所有实执行命令在CPU/固定软件ICD范围；state/FINAL边界声明 | 不存在硬件成功证据；不得自动批准，完成本轮后停止 |

最终验收的“通过”指本轮离线交付与诚实边界满足，而非把未实现的ANV、完整ISA验证或硬件能力改成成功。任何开放MUSTFIX、缺最终审查、缺manifest核验均阻止交付完成。
