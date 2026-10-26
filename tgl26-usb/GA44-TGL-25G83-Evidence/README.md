# GA4.4 — Tahoe 25G83 实机证据与 Apple TGL 兼容性

目标：HP Elite Dragonfly G2 / i5-1135G7 / Iris Xe `8086:9A49` /
macOS 26.6.2 / 25G83 / x86_64。

本轮通过现有 SSH 连接执行**只读**目标检查，采集了 25G83 的
Metal/MTLCompiler/GPUCompiler/IOSurface、IOAcceleratorFamily2 符号和当前
GPU 状态；没有安装、加载、替换或修改目标系统。

## 关键结论

- 目标确为 25G83 / 9A49，但当前只有 `IONDRVFramebuffer`，VRAM 7 MB，
  **没有 IntelAccelerator、没有 TGL kext、没有 Metal 硬件加速**。
- 25G83 自带 ICL/KBL/CFL 24.5.8，**没有 AppleIntelTGLGraphics**。
  TGL 16.0.32 仍只存在于 GA4.3 固定的 NootedGreen donor。
- 目标 `libMTLIGCCompilerPlugin` 是新 API（有
  `MTLCompilerBuildRequestWithSerializedBitcode`），但其 `libigc` **没有
  gen12**；donor 插件是旧 API，但 `libigc` 有 gen12/TGLLP。因此
  adapter/bridge 仍需要。
- 目标 IOAF2 487.4.3 的内核集合符号包含 NootedGreen 所需的
  `waitForStamp`、`IOAccelDisplayPipe` 事务、命令池、orphan pool、
  `IOAccelSysMemory` lock/unlock 等；`IOAccelLegacySurface::set_id_mode` 缺失。
- 目标没有 stock TGL 是 `EXPECTED_ABSENT`；donor 16.0.32 才是补丁对象。
  FMT/PLANES2/VALD/MTL 的 donor 字节已验证，目标 25G83 ABI/runtime 仍需探针。
- 已提出并编译验证一个 NootedGreen 原生-TGL 补丁层：
  `patches/nootedgreen-tgl-native.patch`，新增 `-ngreentgltahoe`，把
  XE-FMT/XE-PLANES2 从 RPL-only 分支分离，并对 display 13/GTFREQ/
  IDLEBOUND/FBDPMS/forceWake 加真 TGL 门。

## 目录

- `reports/REMOTE-EVIDENCE.md`：SSH、系统、GPU、采集清单
- `reports/COMPILER-25G83.md`：目标/donor 编译器对比
- `reports/IOAF2-25G83.md`：IOAF2 符号与补丁影响
- `reports/PATCH-REVALIDATION.md`：逐补丁目标证据
- `reports/BOOT-BASELINE-AUDIT.md`：GA31/GA32 镜像与历史显示基线
- `reports/NEEDS-TARGET-REASSESSMENT.md`：donor/目标 ABI 语义修正
- `FINAL-REPORT.md`：最终中文报告
- `evidence/25g83-system.json`：机器可读证据摘要
- `configs/25g83-evidence.json`：stock/installed/donor 分离配置
- `tools/check-tgl-compat.py`：继承并扩展的只读预检器
- `patches/nootedgreen-tgl-native.patch`：待审阅的源码补丁
- `input/tahoe-frameworks/`：Apple 二进制（Git 忽略，仅本地）
- `input/target-preflight/`：仅当 donor 部署到目标后使用的目标文件目录；当前为空
- `logs/`：原始/过滤后的远程与本地日志
- `evidence/raw/`：含敏感字段的原始远程输出（Git 忽略）

Apple 专有二进制不进入 Git；详见 `NOTICE.md`。
