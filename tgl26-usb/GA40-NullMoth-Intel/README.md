# GA4.0 — NullMoth Intel Native Acceleration Port

**当前：本轮离线工程和三轨独审已完成整合，最终完整性请核验封存回执。** 所有源码、构建、测试和记录只在本目录；GA3.1–GA3.9保留只读。目标是验证NullMoth/Metal→Vulkan→Intel原生栈的可信复用边界，不将CPU/软件Vulkan或Framebuffer接管当成GPU加速。

## 已实际运行的入口

| 工件 | 已取得的证据 |
|---|---|
| `sources/provenance.json` | NullMoth完整commit47f818b…；Mesa26.2.3完整commit31e9a6b…；完整tracked文件SHA；官方Mesa与镜像tag原始refs相同 |
| `metal/backend-adapter/` | 真实C能力/资源/命令/同步接口，原样复用NullMoth upload policy；CPU与固定直接Lavapipe运行、回读与生命周期通过 |
| `prototype/api/` | C Metal-like facade，仅研究API子集，不是MTLDevice ABI |
| `drm/mock/` | 固定Mesa头生成的精确Linux x64布局；显式CPU BO/Context/VM/sync模型，真实GPU路径拒绝 |
| `metal/translator-prototype/` | 实际上游Rust翻译器构建，8个选定LLVMIR fixture→SPIR-V并独立验证；24/38上游测试target通过，所有非通过保留 |
| `prototype/results/cross-component-001/` | CPU模型backing bytes→C adapter→CPU/Lavapipe→独立Python预期回读PASS |
| `prototype/vulkan/NATIVE-PACKET-REPORT.md` | 原样Mesa Gen12 packer→8B NOOP/BBE格式验证，NOT_FOR_HARDWARE；不代表dispatch/ANV工作负载 |
| `intel/GEN12-COMPILER-REPORT.md` | 四IntelCompiler库实构建；真实SPIR-V→NIR→BRW→208B TGL候选，另有336B直接NIR候选；完整IGA最后8B失败，只有前缀解码通过 |
| `intel/ANV-BUILD-REPORT.md` | 实际配置止于CLC requires LLVM；无ANV ICD。Darwin probe另缺Apple SDK/sysroot；未初始化设备 |
| `intel/INDEPENDENT-AUDIT-ADDENDUM.md` | G2独立debug重放一致，末8B为编译器pad NOP，仍仅prefix IGA；19扩展条件和descriptor/ISL/URB未验证边界 |
| `audit/` | 三轨独立有界审查；初始反例与修前工件保留，复审只针对具体问题 |

`metal/API-DEPENDENCY.md`、`VULKAN-BACKEND-AUDIT.md`、`drm/NMDRM-AUDIT.md`、`display/NMINTELFB-AUDIT.md`给出源码函数/调用路径。NMDRM目前只是通用枚举节点；完整公开NMXGPU/NMXAccel实现未找到；NMIntelFB属于固件scanout接管参考。

最终交付入口：`FINAL-REPORT.md`、`reports/FINAL-STATUS.json`、`reports/AUDIT-CLOSURE.json`、`reports/REQUIREMENT-CHECKLIST.md`。三轨审查0open；最终manifest摘要及实际验证结果分别在 `manifest.sha256` 与 `logs/seal-verification.json` / `.txt`。只读核验：`python3 -B tools/seal.py verify`、`python3 -B tools/verify_manifest_independent.py`、`sha256sum -c manifest.sha256`。

版本特别注意：NullMoth的短Mesa基线17ca6174实际对应26.3.0-devel，与本轮选择的Mesa26.2.3不同；原始响应、完整SHA及区别见 `reference/MESA-VERSION-DISTINCTION.md`。原NVK macOS私有patch没有套用到ANV。

## 测试和证据

- `logs/backend-build-006`～`backend-sanitize-lavapipe-011`：release/ASan+UBSan两后端、256线程资源生命周期；全exit0。
- `logs/uapi-model-tests-015`：真实初始失败保留。修前源/diff `reference/repairs/uapi-initial/`；016/017新C布局与12模型测试通过。
- 独立G3发现VERSION非零copy长度/nullptr假成功；真实修前源/diff在 `reference/repairs/drm-safety-001/`，修后029共14模型测试通过；recheck001独立69控制+14tests、前后对照确认关闭。
- `logs/pipeline-build-018`、`cross-component-019`：跨组件双后端回读PASS。
- `logs/native-pack-020`：原生命令pack极小子集PASS。
- `logs/repository-check-024`：项目 `make check` PASS。
- `logs/reuse-helper-recipe-build-025`、`reuse-helper-recipe-run-026`：独审纠正的include-and-call recipe，106 CPU checks PASS。原不正确flags的失败仍在审计目录。
- `logs/kmd-identity-build-fixed-030`、`kmd-identity-run-031`：原样Mesa KMD分类函数7个CPU依赖stub控制通过，nmdrm/GA40mock拒绝；没有ANV初始化。
- `logs/translator-integration-selfhash-032`：真实译器交付的源码/输入/输出/工具/报告摘要自检PASS。

Intel编译、NullMoth翻译器与transfer原型是三项独立结果：Intel输入来自glslang，并非真实译器输出；未拼成同一端到端shader/dispatch链。最新状态/待办见 `state.json`、`continuation.md`，历史只追加在 `history.json`。

## 复现与私有迁移

构建命令及输入hash在各build receipt，运行命令/stdout/stderr/exit在logs。原始构建/日志路径均是一次性新目录，不覆盖旧反例。最终封存后仅运行只读verify；所有重放应在完整私有副本且使用新输出目录中进行。

Rust debug测试构建曾耗尽开发机空间：75个已完成派生产物作无损gzip替换，逐个解压SHA已核，清单 `logs/translator-build-compression-001.jsonl`；未删源码、结果、日志或releasebinary。恢复时依清单原path/mode解压，禁止在封存原件恢复。

仓库不是MIT整体：NullMoth PolyForm Noncommercial、translator LGPL、Mesa逐文件许可、NVIDIA混合头冲突分别记录在reference。外部Apple AIR运行时未归档且许可Unknown，不属于已清许可复用。没有公开上传或创建PR/issues。

## 后续唯一方向

`reports/GA41-NEXT-STEPS.md`推荐“真实设备探测与GEM内存对象闭环”；本轮只规划。真实IntelGPU提交、显示加速和macOS Metal硬件加速均 **NOT_TESTED**；`READY_FOR_HARDWARE_APPROVAL=NO`。
