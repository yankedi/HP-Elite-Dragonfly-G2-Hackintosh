# GA40 后端中立 C 子集（离线）

本接口是可运行研究子集，**不是 macOS `MTLDevice` ABI，也没有 Intel 硬件后端**。`NM_INTEL_HARDWARE`、IOSurface、NVIDIA SASS、Metal 设备能力明确返回 `NM_UNSUPPORTED`。能力只公布 Buffer、RGBA8 Image 生命周期及 transfer。

## 实际复用边界

- 原样包含固定 NullMoth `plugin/nvmtl_tex_upload.h`：`nvmtl_up_set/before_consume/clear` 决定上传未完成时的访问/释放门禁。本适配器把该真实资源生命周期策略用于显式 pending command；不是把整个 `nvmtl_vk.c` 编译成功。
- 原样包含 `plugin/nvmtl_sample_positions.h` 并执行 4 样本布局/非法坐标测试，验证可移植小模块。
- 新增中立设备/能力、句柄、资源、命令和错误清理胶水。Vulkan 的标准 Buffer/Image/命令/栅栏调用按源审计的同类路径实现；没有声称原插件 Objective-C 前端已经接入本接口。
- 上游工作树未修改。复用文件保留 **PolyForm Noncommercial**，本私有实验不能宣称整体 MIT。

## 运行语义

`NM_CPU_MODEL` 是显式 CPU 模拟：提交只变更状态，wait 才执行 CPU 字节操作并允许完成；未 wait、失败 wait 不会让资源可读/可释放。`NM_LAVAPIPE` 使用编译时固定路径 **直接加载**软件 ICD 的 `vk_icdGetInstanceProcAddr`，不经过 Vulkan loader 自动发现。设备类型必须为 CPU 且名称含 llvmpipe 后才创建设备；无真实 GPU 扫描。实际 ICD 的 SHA 和 Vulkan headers SHA 见 `build/backend-release/receipt.json`。

支持一个 in-flight command，避免 CPU 模型与 Vulkan queue 顺序不一致。资源从编码开始被 command 引用，command destroy 释放引用；pending command 不可销毁。一个互斥锁保护资源、命令及 Vulkan pool/queue 的外部同步。`nm_close` 要求调用者已 join 并停止使用设备（销毁后的指针不是有效 API 对象）。Buffer 上限 16MiB，资源32个、command16个、每command16个操作；超限明确拒绝。Image 当前只验证 create/bind/destroy，未实现 image copy/render/IOSurface。

## 真实命令及结果

在 GA40 根目录执行：

```sh
python3 -B tools/build_backend.py release
build/backend-release/backend-test
build/backend-release/backend-test lavapipe
python3 -B tools/build_backend.py sanitize
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 build/backend-sanitize/backend-test
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 build/backend-sanitize/backend-test lavapipe
```

这些构建脚本只接受新目录；已执行产物应在私有完整副本中使用新输出路径重放，不覆盖原日志。实际收据 `logs/backend-*006` 至 `011`：全部 exit0，两后端回读符合测试内固定输入/预期值、四线程各64个生命周期、同步失败后资源仍受保护，ASan/UBSan 无诊断。跨组件的Python预期另行计算，与C后端实现分开。

跨组件 `prototype/tests/cross_component.py`：i915 ABI **CPU backing store** → 显式 CPU 字节复制 → Metal-like facade → adapter → CPU/Lavapipe → 独立期望回读。`logs/pipeline-build-018`、`logs/cross-component-019`、`prototype/results/cross-component-001/` 均保存真实输入、输出和命令。它不是 DRM BO 导入，也未将模拟 handle、Context、VM 或 GPU VA 传入 Vulkan。

下一条件：独立审查真实错误路径；随后依真实 ANV/i915 前提定义内核合同，不能把此 transfer 子集升级为 WindowServer/Metal 完整兼容声明。
