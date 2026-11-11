# 自定义组件源码索引与从源码重编译指南 (Custom Component Source Index & From-Source Rebuild Guide)

> 本文档与 [`docs/clean-install-guide.md` 第 8 节](clean-install-guide.md) 保持完全同步，完整记录 HP EliteBook 840 G8 (`880D`) / HP Elite Dragonfly G2 (`8716`) macOS Tahoe 26 (`25A354` / `25G83`) 全部 15 项自定义/修改版组件的源码路径、SHA256 校验值、修改细节及从源码重编译命令。

本节完整列出本机型（HP Elite Dragonfly G2 `8716` / 同平台 HP EliteBook 840 G8 `880D`）在 **macOS Tahoe 26（`26.6.2` / `25G83`）** 下所使用的全部自定义内核扩展（Kexts）、ACPI SSDT 热补丁（`.dsl` -> `.aml`）、用户态守护进程/动态库 Shim、音频/背光/蓝牙/持久化日志脚本以及 GPU 辅助组件的**精确源码路径、SHA256 校验值与从源码重编译命令**（独立单册版同步维护于 [docs/from-source-rebuild-guide.md](from-source-rebuild-guide.md)）。所有本地交叉编译、链接、签名与 IASL 编译均可在 Linux 开发机（`/srv/mac-for-elitebook`）通过仓库根目录的 [flake.nix](../flake.nix)（`nix develop`）零外部依赖复现，亦可在 macOS 本机使用 Xcode Command Line Tools 原生编译。

---

## 1. 核心内核扩展 (Kexts) 源码与重编译流程

| 内核扩展名称 | 版本 / 补丁标识 | 源码目录与核心源文件 | 仓库跟踪补丁 / 构建脚本 | 产物二进制路径与 SHA256 |
| --- | --- | --- | --- | --- |
| **`NootedGreen.kext`** | `1.0.0` (`com.StezzaPilot.NootedGreen`, `R32-PCFIX38-WAKECOLOR` + `PCFIX36` + Phase 10 `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16`, `LC_UUID` `4C4C4414-5555-3144-A1AA-872C6E2C7F61`) | 源码树：`.local/driver-repair-20261103/repair32-readback/source/`<br>核心实现：`kern_gen11.cpp` (`707,349` B, SHA256 `e4d257e6784f549cac2635c0762312ad1be03436039bdde6ae018afa613f231f`)、`kern_green.cpp` (`50,913` B, SHA256 `eb0f7c9a3b379c6cb77641bfd3f3beacd9c8c5e4fbd176934914a3db49fd3db5`)、`kern_gen11.hpp` (`86,202` B)、`kern_green.hpp` (`10,703` B)、`kern_start.cpp` (`1,877` B) | 完整累积补丁：[patches/nootedgreen-r32-pcfix38-wakecolor-20261111.patch](../patches/nootedgreen-r32-pcfix38-wakecolor-20261111.patch) (`94,790` B, SHA256 `9f589c710f30c7975713940b79c3cce3aa6ad44e2a9eb09403bcd8c93549b1dc`)<br>历史演进补丁：[nootedgreen-r32-pcfix27-20261106.patch](../patches/nootedgreen-r32-pcfix27-20261106.patch)、[nootedgreen-r32-pcfix31-backlight-20261107.patch](../patches/nootedgreen-r32-pcfix31-backlight-20261107.patch)、[nootedgreen-r32-pcfix32-s0ix-20261107.patch](../patches/nootedgreen-r32-pcfix32-s0ix-20261107.patch)、[nootedgreen-r32-pcfix33-s0ix-20261108.patch](../patches/nootedgreen-r32-pcfix33-s0ix-20261108.patch)、[nootedgreen-r32-pcfix34-s0ix-drm-20261108.patch](../patches/nootedgreen-r32-pcfix34-s0ix-drm-20261108.patch)、[nootedgreen-r32-pcfix35-blitalign-20261108.patch](../patches/nootedgreen-r32-pcfix35-blitalign-20261108.patch)、[nootedgreen-r32-pcfix36-wakecolor-20261109.patch](../patches/nootedgreen-r32-pcfix36-wakecolor-20261109.patch)<br>构建脚本：`build.py` + `offline-wrapper.py` | `NootedGreen` (`540,880` B, SHA256 `46c21a3f853aada549dd2a18dee3a2f773667fe0c8cc6d3ef6ff5d21d5b717bb`)<br>`Info.plist` (`3,700` B, SHA256 `b5fd1d0fe125a48f6045c3b07a8f5894f76fc406caf5065f126830a63ea4738e`)<br>回执：`build-receipt.json` |
| **`S0ixStandby.kext`** | `v0.4.4` (`com.labrouss.S0ixStandby`, commit `8b37bb4` + Phase 17/22 USB 唤醒屏蔽、`CNVW` 纯 PCI `PMCSR` `D3hot` + `_PS3/_PS0` `PC8` 修复、唤醒 `EC0._Q06/_Q09` AC/电池同步与 `dispPlaneSleep`/`dispPlaneWake` RGB 规范化) | 源码仓库：`.local/peripheral-prep-20261105/S0ixStandby-repo/`<br>核心实现：`S0ixStandby.cpp` (`73,955` B, SHA256 `f76c03302986e4388014acd262919e7a69f687238395e35be4c44add506de647`)、`S0ixGPU.cpp` (`29,958` B, SHA256 `b0aa17ac6b18eda3605c6f6a740ea97e090563f3fe720be8ee70aedde038d7c0`)、`S0ixStandby.hpp` (`11,367` B, SHA256 `ebd73e27aaf51394531718e7b1af83ead5ea6ab35a74a50fa9788e4210255d93`)、`kmod_info.c` (`733` B) | `Makefile` (`2,805` B, SHA256 `c963731d0467504b32f27da6d2b1e893b8a4378863ee0cfe18872b68f9e0a14d`) | 预备包：`.local/driver-repair-20261103/s0ix-standby-prep-20261107/S0ixStandby.kext`<br>二进制：`S0ixStandby` (`74,824` B, SHA256 `79f27da6a2124f9d476500f8bebde51af09d5b230d78d7833a0ab2dcb060ba55`)<br>`Info.plist` (`4,668` B, SHA256 `4e82da9599fb42a99fdd2e317e29587f0343d661397ec2907a5dfbf5f18d473e`) |
| **`TGLDmic.kext` & `TGLDmic.driver`** | `v0.5.0` (`com.labrouss.TGLDmic` & `com.labrouss.TGLDmic.driver`, commit `d13dafa`) | 源码仓库：`.local/peripheral-prep-20261105/TGLDmic-repo/`<br>Kext 源码：`TGLDmic.cpp` (`19,556` B)、`DspBoot.cpp` (`20,788` B)、`Capture.cpp` (`18,737` B)、`TGLDmicUserClient.cpp` (`4,089` B)、`IpcReplay.hpp`、`Regs.hpp`、`DmaBuffer.hpp`、`TGLDmicShared.h`、`sof-tgl.ri`<br>HAL 插件与工具：`TGLDmicDriver.cpp` (`42,856` B, SHA256 `4d1caf88cae4a0a550945c4e80b712806434baad603293492d30ae98d20cf4e8`)、`tgldmic-probe.c` (`3,980` B) | Kext：`kext/Makefile` (`1,890` B) + `tools/gen-fw.py`<br>HAL：`hal/Makefile` (`915` B) + `hal/install-hal.sh` | Kext 预备包：`TGLDmic.kext`（二进制 `TGLDmic` `1,199,424` B, SHA256 `b0d0715dfb49b6ea15208cdfa0f99373e2e62ee4e2a02448462252ef6721b416`；`Info.plist` `1,646` B, SHA256 `ea026bd65b79ed171615f5df3f8a1cd72f6d76b97c3a01be9c2a5b523f3471f0`）<br>HAL 插件：`TGLDmic.driver`（二进制 `TGLDmic` `48,352` B, SHA256 `6e75f82f6a0237a40f20810df591b90e9c2161e34c389c5eb5e7534180eddca0`） |
| **`SimpleHDA.kext` & `AppleALC.kext`** | `SimpleHDA 1.0.1` (commit `18a16d4`) + `AppleALC 1.9.8` (`0xa0c8` + `layout-id 71`) | `SimpleHDA` 源码树：`.local/peripheral-prep-20261105/SimpleHDA-repo/`<br>`AppleALC` 定制包：`.local/driver-repair-20261103/audio-ridgekey-fix-20261107/stage-oc/Kexts/AppleALC.kext` | `prepare_audio_config.py` | `SimpleHDA` (`4,458,280` B, SHA256 `5a1beec91f121a018072ac085c51543d5eaea85347e6417cd2e37d254d9383c1`)<br>`AppleALC` (`3,810,852` B, SHA256 `690b96189491b9d6f64aa552da6684714d80ade4ad4ec9027251c3257a2d16e8`) |

#### 1. `NootedGreen.kext` (`R32-PCFIX38-WAKECOLOR` + Phase 10 `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16`) 源码补丁应用与本地交叉编译

1. **从上游干净基线应用跟踪补丁（或直接使用已就绪源码树）**：
   - 本地源码树位于 `.local/driver-repair-20261103/repair32-readback/source/`（上游基线 `ChefKissInc/NootedGreen` / `NootedGreen-NP550XDA` commit `6f03560`；核心文件 `kern_gen11.cpp` `707,349` B，SHA256 `e4d257e6784f549cac2635c0762312ad1be03436039bdde6ae018afa613f231f`）。
   - 仓库跟踪的统一 diff 补丁 [patches/nootedgreen-r32-pcfix38-wakecolor-20261111.patch](../patches/nootedgreen-r32-pcfix38-wakecolor-20261111.patch)（`94,790` B，SHA256 `9f589c710f30c7975713940b79c3cce3aa6ad44e2a9eb09403bcd8c93549b1dc`）包含 `R32-PCFIX38` 及此前各阶段全部核心改动：
     - **单端口 Execlist 串行化与 `ELSQWAIT`**：拦截 `submitToRing` 与 `processExeclist`，读取 `RING_EXECLIST_STATUS_LO` (`0x2234`) 确保 RCS0 硬件空闲后再写 `ELSQ`，消除跨上下文抢占覆盖；
     - **内核级 `hpSanitizeComputeEncoder` (`PCFIX27`)**：在内核提交前原地净化 3D/Compute 批处理缓冲，修补 `0x7a000004` `PIPE_CONTROL` 尾刷新位并在 `endOffDw` 追加读写缓存屏障，禁用 POSH (`cs + 0x10` `fAccelerator`)；
     - **内屏 eDP 硬件 PWM 背光缩放 (`XE-BLR` / `-ngreenblr`)**：拦截 `0xC8254` (`SBLC_PWM_FREQ`) 与 `0xC8258` (`SBLC_PWM_DUTY`) 全部 3 条 MMIO 写入路径；
     - **macOS 26 Tahoe S0ix 睡眠/唤醒全链路修复 (`PCFIX32` + `PCFIX33` + `PCFIX34`)**：将 `AppleIntelBaseController::hwSaveNVRAM()` 路由为空操作（消除 `IODTPlatformExpert::_RESERVEDIODTPlatformExpert1` 内核 Panic）；在 `Gen11::wrapSetFramebufferPowerState` 中同时拦截 `FB0`/`FB1`/`FB2` 并在睡眠/唤醒转换时显式调用 `IOFramebuffer::handleEvent(fb, 3/4, (void *)1)`；路由 `IGHardwareCommandStreamer5::resetOnWake()` 至 `hpCsResetOnWake`，在 `HWS_PGA` (`0x2080`) 非零时跳过硬件状态页清零并同步软件读指针 `*(cs + 0x1c04)`；
     - **Phase 10 `isRealTGL && Tahoe` 启用 `HP-BLITALIGN`、`HP-BLITFIX` 与 `HP-BLIT16` (`PCFIX35`)**：放宽 `blit2d_common_supported` / `blit2d_fast_supported` 的 64B 对齐检查，将软解 `420v` 32B 非 64B 对齐 `IOSurface` 平面路由至 `BCS0` `XY_SRC_COPY_BLT` 2D 拷贝，并强制剩余 `Blit3D` 像素着色器使用 `SIMD16`，根治 `420v` 视频播放绿屏与卡顿；
     - **Phase 17 S0ix 唤醒绿屏根除与 `PLANE_CTL_1_A` RGB 强制规范化 (`PCFIX36` + `PCFIX38`)**：新增 `xeNormalizePlane1AColor`，无损保留 `WindowServer` 写入 `PLANE_CTL_1_A` (`0x70180`) 的 Tiger Lake 10-bit Deep Color RGB 编码 `0x82000400` (`PLANE_CTL_FORMAT_XRGB_2101010`，避免误改写为 8-bit `0x84000400` `XRGB_8888` 造成桌面位域错位花屏)，并在唤醒点位将 `PLANE_COLOR_CTL_1_A` (`0x701CC`) 设为 `0x2000`、`CSC_MODE_A` (`0x4A480`) 清零，通过 `gXeWakeHoldActive` 维持最长 `820 ms`（桌面新帧翻转后 `120 ms` 提前释放，保底 `450 ms`）的硬件 PWM 背光保持，并在 IORegistry 导出 `ngreen-wake-xrgb10-preserved = 1`。

2. **一键交叉编译命令（使用 `build.py` 与 `offline-wrapper.py`）**：
   ```sh
   cd /srv/mac-for-elitebook
   # 验证源码与补丁 SHA256
   sha256sum \
     patches/nootedgreen-r32-pcfix38-wakecolor-20261111.patch \
     .local/driver-repair-20261103/repair32-readback/source/src/NootedGreen/kern_gen11.cpp \
     .local/driver-repair-20261103/repair32-readback/source/src/NootedGreen/kern_green.cpp

   # 在 Nix 开发环境中执行交叉编译、$LD64_LLD 链接与 rcodesign 签名
   nix develop -c python3 .local/driver-repair-20261103/repair32-readback/build.py

   # 核验生成的 NootedGreen 二进制哈希 (应为 540,880 B, SHA256 46c21a3f853aada549dd2a18dee3a2f773667fe0c8cc6d3ef6ff5d21d5b717bb, LC_UUID 4C4C4414-5555-3144-A1AA-872C6E2C7F61)
   sha256sum .local/driver-repair-20261103/repair32-readback/build/snapshot/NootedGreen.kext/Contents/MacOS/NootedGreen
   ```

3. **底层 `$CLANG_APPLE` + `$LD64_LLD` + `rcodesign` 等价编译命令明细**：
   `offline-wrapper.py` 在内部对 `info.c`、`src/NootedGreen/` 下的 12 个 C++ 编译单元（`DisplayMergeNub.cpp`、`DYLDPatches.cpp`、`Firmware.cpp`、`FirmwareADLP.cpp`、`HDMI.cpp`、`IntelDPLinkTraining.cpp`、`kern_gen11.cpp`、`kern_genx.cpp`、`kern_green.cpp`、`kern_patcherplus.cpp`、`kern_start.cpp`、`kern_xepm.cpp`）及 `Lilu` 插件入口 `plugin_start.cpp` 执行的精确编译、链接与签名参数如下（仓库内亦归档了独立内核头文件与静态库副本 `.local/build-readiness/isolated/WhateverGreen/MacKernelSDK/` 与 `.local/build-readiness/isolated/WhateverGreen/Lilu.kext/Contents/Resources/`）：
   ```sh
   nix develop -c bash -c '
     SRC="/srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/source/src/NootedGreen"
     OBJ="/srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/build/objects/snapshot/NootedGreen"
     OUT="/srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/build/snapshot/NootedGreen.kext"
     OLD="/srv/tgl26-usb/GA43-AppleTGL-Tahoe/inputs/upstream/nootedgreen"

     # 编译单个 C++ 内核源文件 (以 kern_gen11.cpp 为例)
     "$CLANG_APPLE" -target x86_64-apple-macos13.0 -mkernel -nostdinc \
       -fno-builtin -fno-common -fno-stack-protector -mmmx -msse -msse2 \
       -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT -DDEBUG=1 \
       -isystem "$OLD/MacKernelSDK/Headers" -I"$SRC" -O2 -g \
       -fno-use-cxa-atexit -fno-register-global-dtors-with-atexit \
       -mllvm -disable-atexit-based-global-dtor-lowering \
       -fno-asynchronous-unwind-tables \
       -DAPPLE_KEXT_ASSERTIONS=1 -DPRODUCT_NAME=NootedGreen -DMODULE_VERSION=1.0.0 \
       -I"$OLD/Lilu.kext/Contents/Resources" \
       -std=gnu++17 -nostdinc++ -fno-exceptions -fno-rtti -fapple-kext \
       -Wno-deprecated-declarations -Wno-inconsistent-missing-override -Wno-unused-parameter \
       -c "$SRC/kern_gen11.cpp" -o "$OBJ/kern_gen11.o"

     # 使用支持 -kext 的 $LD64_LLD 链接生成 Mach-O MH_KEXT_BUNDLE 并执行 Ad-hoc 签名
     "$LD64_LLD" -kext -arch x86_64 -platform_version macos 13.0 26.5 -export_dynamic \
       -o "$OUT/Contents/MacOS/NootedGreen" \
       "$OBJ"/*.o "$OLD/MacKernelSDK/Library/x86_64/libkmod.a"

     "$RCODESIGN" sign --config-file /dev/null --timestamp-url none "$OUT"
   '
   ```

#### 2. `S0ixStandby.kext` (`v0.4.4`) 源码与重编译流程

- **源码位置**：`.local/peripheral-prep-20261105/S0ixStandby-repo/`（包含 `Makefile`、`S0ixStandby/S0ixStandby.cpp` `73,955` B SHA256 `f76c03302986e4388014acd262919e7a69f687238395e35be4c44add506de647`、`S0ixStandby/S0ixGPU.cpp` `29,958` B SHA256 `b0aa17ac6b18eda3605c6f6a740ea97e090563f3fe720be8ee70aedde038d7c0`、`S0ixStandby/S0ixStandby.hpp` `11,367` B SHA256 `ebd73e27aaf51394531718e7b1af83ead5ea6ab35a74a50fa9788e4210255d93`、`S0ixStandby/kmod_info.c` `733` B、`S0ixStandby/Info.plist` 及诊断脚本 `macos/s0ix-status.sh`）。
- **重编译命令**（支持在 Linux 开发机通过 `nix develop` 交叉编译，或在 macOS 本机调用 `Makefile` 的 `SDK` / `COMMON` / `CXXFLAGS` / `CFLAGS` / `LDFLAGS` 构建）：
  ```sh
  # 方式 A：在本地 Linux 开发机通过 nix develop + MacKernelSDK 交叉编译 S0ixStandby.kext (v0.4.4)
  nix develop -c bash -c '
    set -e
    SDK="/srv/mac-for-elitebook/.local/build-readiness/isolated/WhateverGreen/MacKernelSDK"
    REPO="/srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo"
    TMP=$(mktemp -d)
    trap "rm -rf $TMP" EXIT

    COMMON="-target x86_64-apple-macos10.13 -mkernel -nostdinc -fno-builtin -fno-common -fno-stack-protector -mmmx -msse -msse2 -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT -I$SDK/Headers -Wall -Wextra -Wno-unused-parameter -Os -fno-use-cxa-atexit -fno-register-global-dtors-with-atexit -mllvm -disable-atexit-based-global-dtor-lowering -fno-asynchronous-unwind-tables"
    "$CLANG_APPLE" $COMMON -std=gnu++17 -fapple-kext -fno-rtti -fno-exceptions -c "$REPO/S0ixStandby/S0ixStandby.cpp" -o "$TMP/S0ixStandby.o"
    "$CLANG_APPLE" $COMMON -std=gnu++17 -fapple-kext -fno-rtti -fno-exceptions -c "$REPO/S0ixStandby/S0ixGPU.cpp" -o "$TMP/S0ixGPU.o"
    "$CLANG_APPLE" $COMMON -std=gnu11 -DKEXT_BUNDLE_ID=com.labrouss.S0ixStandby -DKEXT_VERSION=\"0.4.4\" -c "$REPO/S0ixStandby/kmod_info.c" -o "$TMP/kmod_info.o"
    "$LD64_LLD" -kext -arch x86_64 -platform_version macos 10.13 26.5 -export_dynamic \
      "$TMP/S0ixStandby.o" "$TMP/S0ixGPU.o" "$TMP/kmod_info.o" \
      "$SDK/Library/x86_64/libkmod.a" "$SDK/Library/universal/libkmodc++.a" \
      -o "$TMP/S0ixStandby"
    "$LLVM_BIN/llvm-nm" -gU "$TMP/S0ixStandby" | grep -E "kmod_info|_start"
  '

  # 方式 B：在 macOS Xcode Command Line Tools 环境下直接运行上游 Makefile
  # cd /srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo
  # make SDK=/srv/mac-for-elitebook/.local/build-readiness/isolated/WhateverGreen/MacKernelSDK

  # 核验已部署预备包二进制 SHA256 (应为 74,824 B, SHA256 79f27da6a2124f9d476500f8bebde51af09d5b230d78d7833a0ab2dcb060ba55)
  sha256sum /srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/S0ixStandby.kext/Contents/MacOS/S0ixStandby
  ```

#### 3. `TGLDmic.kext` (`v0.5.0`) 与 `TGLDmic.driver` CoreAudio HAL 插件重编译流程

- **源码位置**：`.local/peripheral-prep-20261105/TGLDmic-repo/`，分为内核驱动目录 `kext/`（`kext/Makefile`）与用户态 CoreAudio AudioServerPlugIn 目录 `hal/`（`hal/Makefile`）。
- **从源码重编译步骤**（支持在本地 Linux 开发机通过 `nix develop` 全量交叉编译 `TGLDmic.kext`、`TGLDmic.driver` 与 `tgldmic-probe`，或在 macOS 本机执行 `make`）：
  ```sh
  # 方式 A：在本地 Linux 开发机通过 nix develop 交叉编译 TGLDmic.kext + TGLDmic.driver + tgldmic-probe
  nix develop -c bash -c '
    set -e
    SDK="/srv/mac-for-elitebook/.local/build-readiness/isolated/WhateverGreen/MacKernelSDK"
    DMIC_REPO="/srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo"
    TMP=$(mktemp -d)
    trap "rm -rf $TMP" EXIT

    # 1) 生成内置 Intel SOF 固件源文件 Firmware.c 并交叉编译 TGLDmic.kext
    python3 "$DMIC_REPO/tools/gen-fw.py" \
      --tgl "$DMIC_REPO/firmware/intel/sof-tgl.ri" \
      --cml "$DMIC_REPO/firmware/intel/sof-cml.ri" \
      -o "$TMP/Firmware.c"

    DMIC_COMMON="-target x86_64-apple-macos10.15 -mkernel -nostdinc -isystem $SDK/Headers -fno-builtin -fno-common -fno-stack-protector -mmmx -msse -msse2 -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT -O2 -fno-use-cxa-atexit -fno-register-global-dtors-with-atexit -mllvm -disable-atexit-based-global-dtor-lowering -fno-asynchronous-unwind-tables"
    for f in TGLDmic DspBoot Capture TGLDmicUserClient; do
      "$CLANG_APPLE" $DMIC_COMMON -std=gnu++17 -Wall -Wno-unused-private-field \
        -fapple-kext -fno-rtti -fno-exceptions -I"$DMIC_REPO/kext/TGLDmic" \
        -c "$DMIC_REPO/kext/TGLDmic/$f.cpp" -o "$TMP/$f.o"
    done
    "$CLANG_APPLE" $DMIC_COMMON -std=gnu11 -c "$TMP/Firmware.c" -o "$TMP/Firmware.o"
    "$CLANG_APPLE" $DMIC_COMMON -std=gnu11 -c "$DMIC_REPO/kext/TGLDmic/kmod_info.c" -o "$TMP/kmod_info.o"
    "$LD64_LLD" -kext -arch x86_64 -platform_version macos 10.15 26.5 -export_dynamic \
      "$TMP/TGLDmic.o" "$TMP/DspBoot.o" "$TMP/Capture.o" "$TMP/TGLDmicUserClient.o" \
      "$TMP/Firmware.o" "$TMP/kmod_info.o" \
      "$SDK/Library/x86_64/libkmod.a" "$SDK/Library/universal/libkmodc++.a" \
      -o "$TMP/TGLDmic.kext.bin"

    # 2) 交叉编译用户态 CoreAudio HAL 插件 TGLDmic.driver 与诊断工具 tgldmic-probe
    "$CLANG_APPLE" -target x86_64-apple-macos10.15 -isysroot "$SDKROOT" \
      -isystem "$SDKROOT/usr/include/c++/v1" -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter \
      -c "$DMIC_REPO/hal/TGLDmicDriver.cpp" -o "$TMP/TGLDmicDriver.o"
    "$LD64_LLD" -bundle -arch x86_64 -platform_version macos 10.15 26.5 -syslibroot "$SDKROOT" \
      "$TMP/TGLDmicDriver.o" -lSystem -lc++ \
      -framework CoreAudio -framework CoreFoundation -framework IOKit \
      -o "$TMP/TGLDmic.driver.bin"

    "$CLANG_APPLE" -target x86_64-apple-macos10.15 -isysroot "$SDKROOT" -std=c11 -O2 -Wall \
      -c "$DMIC_REPO/hal/tgldmic-probe.c" -o "$TMP/tgldmic-probe.o"
    "$LD64_LLD" -arch x86_64 -platform_version macos 10.15 26.5 -syslibroot "$SDKROOT" \
      "$TMP/tgldmic-probe.o" -lSystem -framework IOKit -framework CoreFoundation \
      -o "$TMP/tgldmic-probe"
  '

  # 方式 B：在 macOS Xcode Command Line Tools 环境下直接运行上游 Makefile
  # make -C /srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/kext SDK=/srv/mac-for-elitebook/.local/build-readiness/isolated/WhateverGreen/MacKernelSDK
  # make -C /srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/hal

  # 3) 核验已部署预备包二进制 SHA256
  sha256sum \
    /srv/mac-for-elitebook/.local/driver-repair-20261103/audio-ridgekey-fix-20261107/tgldmic-prep-20261107/TGLDmic.kext/Contents/MacOS/TGLDmic \
    /srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-audio/Library-Audio-Plug-Ins-HAL/TGLDmic.driver/Contents/MacOS/TGLDmic
  ```

---

## 2. ACPI SSDT 热补丁源码 (`.dsl` -> `.aml`) 与 `iasl` 编译命令

本机 `/EFI/OC/ACPI/` 下挂载的全部 6 张生产环境热补丁表（及 1 张归档备查表）均配有完整的 `.dsl` ASL 源码，在本地开发机通过 `nix develop -c iasl -ve`（ACPICA ASL Optimizing Compiler）实现 **`0` Errors、`0` Warnings** 确定性编译：

| SSDT 表名称 | `.dsl` 源码路径、字节数与 SHA256 | `.aml` 产物路径、字节数与 SHA256 | 配套 `config.plist` `ACPI -> Patch / Delete` 与功能说明 |
| --- | --- | --- | --- |
| **`SSDT-EC0-ITLB.aml`** | 仓库跟踪：[`acpi/SSDT-EC0-ITLB.dsl`](../acpi/SSDT-EC0-ITLB.dsl)（本地源：`SSDT-EC0-ITLB.dsl`）<br>`7,231` B<br>SHA256 `30dd9d79d501cb83cab902fe9acc3f46553ef6efafc5878641fe1174387186ed` | `SSDT-EC0-ITLB.aml`<br>`1,572` B<br>SHA256 `122a5b9d778c6429d32f73f1da7e695ba7498e6714e172f708b22894bd8ddaf8` | 配合 4 条 `Count=1` 精确重命名（`DSDT`: `ITLB\0 -> XTLB\0`；`NVTEC`: `EC12\0 -> XC12\0`、`EC13\0 -> XC13\0`；`DptfTabl`: `ODVP\x08 -> XDVP\x08`）+ 1 条 `ACPI -> Delete`（丢弃 `OemTableId="HP_XHC_P"` `TableLength=2362` 的 `SSDT13`），将 `ECEnabler` 挂载前（`t=1.93s`）访问的 4 个 16-bit EC 寄存器（`BDC`/`BFC`/`BDV`/`ACPR`）拆分为 8-bit 字节对，实现冷启动 **`0` 次 ACPI Error/Exception** 并完整走通 `ECRI -> ITLB -> SBTN -> PRIT` |
| **`SSDT-DEEPIDLE.aml`** | 仓库跟踪：[`acpi/SSDT-DEEPIDLE.dsl`](../acpi/SSDT-DEEPIDLE.dsl)（本地源：`SSDT-DEEPIDLE.dsl`）<br>`2,793` B<br>SHA256 `1f569b6bbb0d4305a27fcadeedf69a463c18f47b581d5140fb8acb2ecccfb1b9` | `SSDT-DEEPIDLE.aml`<br>`371` B<br>SHA256 `280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1` | 配合 `OemTableId="MS-SSDT"` 限定重命名 `14275F53544100 -> 14275853544100`（`PEPD._STA -> XSTA`, `Count=1`），在 Darwin 下注入 `\_SB.LPS0 = One`、`\_GPE.LXEN = One`、`\_SB.PEPD._STA` 置 `S0ID = One` 返回 `0x0F`，置 `\USWE = Zero` 全局屏蔽 USB/XDCI/Thunderbolt `_PRW` 唤醒（支持 `-s0ixusbwake` 动态覆盖），并为 `\_SB.LID` 与 `\_SB.SLPB` 注入 `_PRW`/`PRW0` (`Package (0x02) { 0x6E, 0x04 }`) 与 `_S0W` (`0x04`)，激活 `IOPMDeepIdleSupported = Yes`、`S0ixStandby.kext` 与 GPE `0x6E` 开盖/电源键唤醒 |
| **`SSDT-PLUG.aml`** | 仓库跟踪：[`acpi/SSDT-PLUG.dsl`](../acpi/SSDT-PLUG.dsl)（`715` B，SHA256 `aab42b4ec4d952cadfe40704a1e561e528f81cb4f9b1fed2fd3aacca84ef570f`）<br>`iasl -d` 往返源：`SSDT-PLUG.dsl`（`1,355` B，SHA256 `b49fccae93979f77d61f34b3b0ed22920d93ac4ed87dfe73bdb42c2f9743654a`） | `SSDT-PLUG.aml`<br>`113` B<br>SHA256 `24956a41669b37fce98f09b9b6d28475a099693bb3522391d35609415e0ffed2` | 在 `\_SB.PR00` 注入 `plugin-type = 1`，配合 `Cpuid1Data` 仿冒 `0x706E5` 挂载 `X86PlatformPlugin`（`39` 档 P-States） |
| **`SSDT-EC-USBX-HP.aml`** | 仓库跟踪：[`acpi/SSDT-EC-USBX-HP.dsl`](../acpi/SSDT-EC-USBX-HP.dsl)（`1,828` B，SHA256 `f9db2e03453d4c593aec344a3a07ca966c136d3ff1a48c550ec6837f8ec290df`）<br>`iasl -d` 往返源：`SSDT-EC-USBX-HP.dsl`（`2,602` B，SHA256 `6ef5245418774d2bb84c177065f6294eeac7d57cd6202866b0be5f0bda400b45`） | `SSDT-EC-USBX-HP.aml`<br>`372` B<br>SHA256 `296212e084666dfc9ed0ab69fbbecaaa3525da71f528526c2d22d0d81d7f6781` | 导出伪 `\_SB.PCI0.LPCB.EC` 与 `\_SB.USBX` USB 供电属性（`kUSBSleepPowerSupply = 5100`、`kUSBWakePowerSupply = 5100`） |
| **`SSDT-RHUB-HP.aml`** | 仓库跟踪：[`acpi/SSDT-RHUB-HP.dsl`](../acpi/SSDT-RHUB-HP.dsl)（`997` B，SHA256 `2d441f3d40dfac5e91586fd4bc89ecd68c13b525ab143e25a555ed7a6799cf48`）<br>`iasl -d` 往返源：`SSDT-RHUB-HP.dsl`（`1,050` B，SHA256 `6c0c75476502328fba31c6b77d8b144ac5dde53ed29eb3eea3fdaa33759c9498`） | `SSDT-RHUB-HP.aml`<br>`108` B<br>SHA256 `4cf78eacb8f2529a3a93a3bb9406ad4cc5446fe19828c49241130ab0503daec9` | 在 Darwin 下为 `\_SB.PC00.XHCI.RHUB` 注入 `_STA = 0`，强制 `AppleUSBXHCISPT` 直接从硬件寄存器枚举 PCH XHCI 端口 |
| **`SSDT-PNLF-HP-GA419.aml`** | 仓库跟踪：[`acpi/SSDT-PNLF-HP-GA419.dsl`](../acpi/SSDT-PNLF-HP-GA419.dsl)（`593` B，SHA256 `f24fc67b2ae9d9314895b33536860a1e099e4b1a0b7637dd2a96725371616cd5`）<br>`iasl -d` 往返源：`SSDT-PNLF-HP-GA419.dsl`（`1,297` B，SHA256 `a442ccf1ed4f563e691c0a96b1c431fc9c0b07314615f89af1c19a76ba980911`） | `SSDT-PNLF-HP-GA419.aml`<br>`142` B<br>SHA256 `72ec07163115d8c327f1c7f143b0375b7b0262adc9422c2628ab2177cc71414e` | 在 `\_SB.PC00.GFX0` 下注入 `PNLF` 背光设备（`_HID = "APP0002"`，`_UID = 0x13`） |
| **`SSDT-HP-Hotkeys.aml`** *(归档备查)* | `SSDT-HP-Hotkeys.dsl`<br>`3,389` B<br>SHA256 `a02df811c0ce77f01b0d5e9c6a4aecfec17fd432b3f08f802b0beb35d5d7e445` | `SSDT-HP-Hotkeys.aml`<br>`692` B<br>SHA256 `ba463a93a38fd9a8b8a79850d4c9fab184f1603ff07b6ee8a555d220863577f8` | 早期 EC `_Q86`/`_Q87` 与 WMI `GVWE` 队列排空转 `PS2K` 通知实验表；因实机顶排 16 键已通过原生 `i8042` 扫描码 + `VoodooPS2Keyboard` `24` 条 `Custom ADB Map` 完整驱动，生产环境 `config.plist` 不加载此表 |

#### 从 `.dsl` 源码重编译全部 `.aml` 并执行 OpenCore `ocvalidate` 校验

```sh
cd /srv/mac-for-elitebook

# 1. 使用 nix develop 中的 iasl 编译器将仓库跟踪的 acpi/*.dsl 编译至 /tmp/acpi-out
nix develop -c bash -c '
  mkdir -p /tmp/acpi-out
  for dsl in \
    acpi/SSDT-EC0-ITLB.dsl \
    acpi/SSDT-DEEPIDLE.dsl \
    acpi/SSDT-PLUG.dsl \
    acpi/SSDT-EC-USBX-HP.dsl \
    acpi/SSDT-RHUB-HP.dsl \
    acpi/SSDT-PNLF-HP-GA419.dsl; do
    iasl -ve -p "/tmp/acpi-out/$(basename "${dsl%.dsl}")" "$dsl"
  done
'

# 2. 校验生成的 6 张 .aml 二进制 SHA256（与生产环境 EFI-OC/OC/ACPI/*.aml 100% 逐字节一致）
sha256sum \
  /tmp/acpi-out/SSDT-EC0-ITLB.aml \
  /tmp/acpi-out/SSDT-DEEPIDLE.aml \
  /tmp/acpi-out/SSDT-PLUG.aml \
  /tmp/acpi-out/SSDT-EC-USBX-HP.aml \
  /tmp/acpi-out/SSDT-RHUB-HP.aml \
  /tmp/acpi-out/SSDT-PNLF-HP-GA419.aml

# 3. 使用与 OpenCore 1.0.8 版本严格匹配的 ocvalidate 校验 config.plist (应输出 No issues found.)
.local/tools/OpenCorePkg/1.0.8/ocvalidate.linux \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/config.plist
```

---

## 3. 用户态守护进程、Shim 与音频/背光/指纹辅助工具源码索引

本机型所有用户态组件均支持在本地 Linux 开发机通过 `nix develop`（使用 `$CLANG_APPLE` / `clang` + `ld64.lld` + `rcodesign` 配合本地轻量级 TBD 桩库目录 `.local/driver-repair-20261103/brightness-fix-20261107/stubs/` 或 `$SDKROOT`）直接交叉编译，或在目标机 macOS 终端下使用系统 `clang` 编译。

#### 1. 用户态组件源码与部署路径总表

| 组件名称与目标机安装路径 | 源码文件、大小与 SHA256 | 预备产物路径与 SHA256 | 核心职责与运行机制 |
| --- | --- | --- | --- |
| **`libhp_cb_shim.dylib` / `hp-cb-shim.dylib`**<br>`/usr/local/lib/libhp_cb_shim.dylib`<br>`/usr/local/lib/hp-cb-shim.dylib` | `hp-cb-shim.m`<br>`19,545` B<br>SHA256 `14e276f659660bda1926e1b3b0f622c2f1fae87f2112f16142270fbfdf85327a` | `libhp_cb_shim.dylib` / `hp-cb-shim.dylib`<br>`35,456` B<br>SHA256 `e3b8378dc67e8ad9d19cdf5e025710660e73a6ce23885a82f910ac69b689b798` | 通过 Mach-O `__DATA,__interpose` 与 `CoreBrightness.framework` GOT 补丁拦截 `IODisplayCopyParameters` 与 `IODisplayGet/SetIntegerRangeParameter`，将 `corebrightnessd` 所需的 `"brightness"` / `"linear-brightness"` / `"usable-linear-brightness"` / `"commit"` 字典实时桥接至内核 `AppleBacklightDisplay` 的 `"bklt"` (`600..65535`)，恢复右上角控制中心与系统设置原生亮度滑块 |
| **`hp-cb-shim-loader.sh`**<br>`/usr/local/bin/hp-cb-shim-loader.sh`<br>守护配置：`/Library/LaunchDaemons/com.hp.cb-shim-loader.plist` | `hp-cb-shim-loader.sh`<br>`4,617` B<br>SHA256 `a3de1c6667ae927ec9f166bcec7cdc27ef721bc9a8e19f31b03c4103f6008fb8`<br>Plist：`com.hp.cb-shim-loader.plist` (`610` B, SHA256 `12795cbacc89b36bf3828925f4a498d4f488a426519a362c9b58b1a7a883a9eb`) | `stage3-brightness-hotkeys/usr-local-bin/hp-cb-shim-loader.sh`<br>`4,617` B<br>SHA256 `a3de1c6667ae927ec9f166bcec7cdc27ef721bc9a8e19f31b03c4103f6008fb8` | 开机等待 `AppleBacklightDisplay` 与 `WindowServer` 就绪后，在 `/private/var/run/com.apple.corebrightnessd-shim.plist` 生成带 `DYLD_INSERT_LIBRARIES=/usr/local/lib/hp-cb-shim.dylib` 的服务定义并热切换原厂 `/usr/libexec/corebrightnessd`（保留 `CS_PLATFORM_BINARY`，日志落盘 `/var/log/hp-cb-shim-loader.log`），规避 macOS 26 `/usr/local/lib` firmlink `Bootstrap failed: 5` 与 `PETRIFIED` 竞态 |
| **`hp-bridge`**<br>`/usr/local/bin/hp-bridge`<br>守护配置：`/Library/LaunchAgents/com.hp.bridge.agent.plist` | 现役源码：`hp-bridge.m` (`96,624` B, SHA256 `6a8ed260f9925bcfb5c41683d006815ad6e9dadc3082788456f6c9927ff8e912`；初版：`hp-bridge.m` `76,495` B)<br>Plist：`com.hp.bridge.agent.plist` (`596` B, SHA256 `514a849a596dfea3fe0000be896a12ba323c8bd4389f6f32eb3269630e80ff20`) | `stage3-brightness-hotkeys/usr-local-bin/hp-bridge`<br>`79,776` B<br>SHA256 `aadfbf21e6e26281c4436ec99a058b875ab2480078b6bb93717970d1c3712252` | 用户态全功能热键、背光、音频与菜单栏常驻桥接守护进程：注册 Carbon 全局热键（含 `kEventHotKeyPressed`/`Released` 长按状态机，无需 TCC 权限）与 `IOHIDManager` Consumer 监听（自动屏蔽 `BrightnessKeys.kext` 重复步进），实现 `f3`/`f4` 按速自适应无级调光（`1%–15%` + `64` 格原生 OSD）并将 `prt scr`/`Ctrl+prt scr`（`F19`）绑定至 `SkyLight` `AppleSymbolicHotKeys` `30`/`31`（由 `SystemUIServer` 原生执行十字框选截屏、右下角浮动缩略图与直接剪贴板拷贝，零 TCC 依赖），双向同步 `CoreDisplay` / `DisplayServices` 与硬件 `"bklt"` (`600..65535`)，驱动 `ALC285` AFG `0x01` GPIO `IO[2]` (`f5` 扬声器静音橙色 LED) 与 `IO[0]` (`f8` 麦克风静音橙色 LED)，日志持久化输出至 `/var/log/hp-bridge.log` |
| **`hp-brightness`**<br>`/usr/local/bin/hp-brightness` | 包装脚本：`hp-brightness` (`449` B, SHA256 `8396b8330bd683e8d78c879df29d6c5db005f18a9f07481ac82fe0ff1bf5de6c`)<br>独立前身源码：`hp-brightness-daemon.m` (`35,403` B, SHA256 `0752fb097833423643061cc9c638e9dddcff71dcf73dec5b2742a1aa3ac17235`) | `stage3-brightness-hotkeys/usr-local-bin/hp-brightness`<br>SHA256 `8396b8330bd683e8d78c879df29d6c5db005f18a9f07481ac82fe0ff1bf5de6c` | 命令行背光查询与调节入口（支持 `hp-brightness --get`、`hp-brightness --set <0.0..1.0>`、`hp-brightness --up/--down`、`hp-brightness --probe-ds`），转发至 `/usr/local/bin/hp-bridge` |
| **`hp-alc285-ampinit.sh`**<br>`/usr/local/bin/hp-alc285-ampinit.sh`<br>守护配置：`/Library/LaunchDaemons/com.hp.alc285.ampinit.plist` | `hp-alc285-ampinit.sh`<br>`2,229` B<br>SHA256 `2c9056f67333717c5d21598a1f51c2f9d43d4b5717ddf3f985fd86932e2af41c`<br>Plist：`com.hp.alc285.ampinit.plist` (`606` B, SHA256 `7d964e9e6d9d1c5ddc267f92a056d80c6c9b7eb9f0027360c4afeee403090503`) | `stage3-audio/usr-local-bin/hp-alc285-ampinit.sh`<br>`2,229` B<br>SHA256 `2c9056f67333717c5d21598a1f51c2f9d43d4b5717ddf3f985fd86932e2af41c` | 开机或 S0ix 唤醒后等待 `ALCUserClientProvider` 就绪，下发 Bang & Olufsen 功放初始化动词（`0x20 SET_COEF_INDEX 0x65`、`SET_PROC_COEF 0x0000`）与 3.5mm 耳麦麦克风通路增益（`0x19`/`0x23`/`0x08`），并依次调用 `hp-select-speaker` 与 `hp-select-dmic.py` |
| **`hp-wake-helper`**<br>`/usr/local/bin/hp-wake-helper`<br>守护配置：`/Library/LaunchDaemons/com.hp.alc285.ampinit.plist` (`KeepAlive`) | 现役源码：`hp-wake-helper.m` (`26,516` B, SHA256 `c215d14ead47f760eaa81e6cbd5c01ba2f022885928341f62cc8f15e7745b343`；初版：`hp-wake-helper.m` `10,582` B)<br>Plist：`com.hp.alc285.ampinit.plist` (`606` B, SHA256 `7d964e9e6d9d1c5ddc267f92a056d80c6c9b7eb9f0027360c4afeee403090503`) | `stage3-audio/usr-local-bin/hp-wake-helper`<br>`50,112` B<br>SHA256 `b592620b3ef2f816b006d0fa6414e206b142da5779ece3b82604b6bf12f7b491` | S0ix 睡眠/唤醒常驻守护进程：监听 `IORegisterForSystemPower` 与 `IODisplayWrangler`（忽略 `wps==3` halfdim，仅在真正 `wps <= 2` 灭屏时预存背光并遮黑），唤醒阶段配合内核 `ngreen-wake-xrgb10-preserved` 执行 `820 ms` `bklt=16/0` 背光保持、刷新 ColorSync/Gamma，并重初始化 `ALC285` B&O 功放、`TGLDmic` 与 `AirportItlwm` Wi-Fi（日志 `/var/log/hp-alc285-ampinit.log`） |
| **`hp-select-speaker`**<br>`/usr/local/bin/hp-select-speaker` | `hp-select-speaker.m`<br>`4,354` B<br>SHA256 `550b57c570c55983c19137ed02e72af80bf42db226224c72bd62ab4b4718c95c` | `stage3-audio/usr-local-bin/hp-select-speaker`<br>`27,360` B<br>SHA256 `7badbe2d61eeaccf632ac2a84a580ae7572bd9bf1b3319f656a2367c3e10849a` | 枚举 CoreAudio `'dev#'` 列表，匹配 UID 含 `"1F,3,0,1,3"` 的 `Built-in Speaker` 并将其设为系统默认输出（`'dOut'`）与系统音效输出（`'sOut'`） |
| **`hp-select-dmic.py`**<br>`/usr/local/bin/hp-select-dmic.py` | `hp-select-dmic.py`<br>`2,513` B<br>SHA256 `c636d9cf2ce4c33ada6493801722f6e3b385db2a22f40883ee9491982c330f22` | `stage3-audio/usr-local-bin/hp-select-dmic.py`<br>SHA256 `c636d9cf2ce4c33ada6493801722f6e3b385db2a22f40883ee9491982c330f22` | 检测 `ioreg` 中 `TGLDmic` 激活后，通过 `ctypes` 调用 `AudioObjectSetPropertyData` 将 `TGLDmic_InternalMic_UID`（`Internal Microphone (TGLDmic)`）设为系统默认输入设备（`'dIn '`） |
| **`libxedrv.dylib`**<br>`/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib` | `libxedrv.m`<br>`51,712` B<br>SHA256 `ea4b9ec3c14a902863c1ce41fc3a6e40c54eb350d747833ad702087a69429406` | 本地构建：`libxedrv.dylib` (`65,280` B, SHA256 `312ecf603a27526df87417980fd64fddd2d51e16754aa5deff8a1deeb76226b2`)<br>安装套件同步版：`libxedrv.dylib` (`65,280` B, SHA256 `312ecf603a27526df87417980fd64fddd2d51e16754aa5deff8a1deeb76226b2`) | 注入 `AppleIntelTGLGraphicsMTLDriver`（`16.0.32`）的 Metal ABI 适配层（`xedrv17`）：转换 Tahoe `MTLRenderPipelineDescriptorPrivate` 结构体偏移与 `misc` 位域，重写 `newTextureViewWithPixelFormat:` 避免 `RCS0` `fmt=123` Blit3D 挂死，配合内核 `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16` 处理 `420v` 纹理视图，并在 `VTDecoderXPCService` 中安全返回 `nil` |
| **`xe-h264sw-fixd`**<br>`/usr/local/libexec/xe-h264sw-fixd`<br>守护配置：`/Library/LaunchDaemons/com.elitebook.h264swfix.plist` | `xe-h264sw-fixd.c`<br>`10,549` B<br>SHA256 `7c268fbb7b18a2f5bd5ba1b69bf7efcb89ad2f30b96d89f72a895d28efba2507`<br>Plist：`com.elitebook.h264swfix.plist` (`612` B, SHA256 `a94459225efeb6eed418475c6d16a2bb82be2ff913889fa16a47eb3c2973c9cf`) | `stage2-gpu/usr-local-libexec/xe-h264sw-fixd`<br>`24,496` B<br>SHA256 `4e388dfd1720d25e73d5701b4be0919cac190cca38ee03fc7ee9a7532048d5af`<br>`LC_UUID` `4C4C44B3-5555-3144-A1E7-A919CC286F49` | 监听 `VTDecoderXPCService` 进程并原地修复 macOS 26 `AppleH264SW` 软件解码路径的 `fill_frame_num_gap` 补帧异常（配合生产环境 `/Library/GPUBundles/` 故意省略实验性 `VADriver.bundle` / `VAME.bundle`，确保 H.264/HEVC 视频由软解 + `BCS0` `HP-BLITALIGN` 零绿屏零挂死渲染；日志 `/var/log/hp-xe-h264sw-fixd.log`） |
| **`hp-bt-compat-check.sh`**<br>`/usr/local/bin/hp-bt-compat-check.sh`<br>守护配置：`/Library/LaunchDaemons/com.hp.bt-compat-check.plist` | `hp-bt-compat-check.sh`<br>`2,647` B<br>SHA256 `2959d4b84802e12c6d2f23fd4bc41ae154c4429b799f475ab1bb425232ea09cb`<br>Plist：`com.hp.bt-compat-check.plist` (`614` B, SHA256 `156950587f27a14b52fb56dfcce88a7198607ff22fdebd103583acc47847f208`) | `stage3-bluetooth/usr-local-bin/hp-bt-compat-check.sh`<br>`2,647` B<br>SHA256 `2959d4b84802e12c6d2f23fd4bc41ae154c4429b799f475ab1bb425232ea09cb` | 开机检测剥离废弃 `--Compat` 参数并核验 Intel AX201 蓝牙（`8087:0026`，Firmware `v8787 c8787`）控制器在线状态；若检测到 `bluetoothd` 发生 APFS `decmpfs` 簇缺页崩溃循环则自动执行 `bootout` + `/usr/sbin/purge` + `bootstrap` 自愈（日志 `/var/log/hp-bt-compat-check.log`） |
| **`hp-syslogger.py` (`v1.1`)**<br>`/usr/local/bin/hp-syslogger.py`<br>守护配置：`/Library/LaunchDaemons/com.hp.syslogger.plist` + `/etc/newsyslog.d/com.hp.conf` | `hp-syslogger.py`<br>`13,043` B<br>SHA256 `9f22348437736568d9ca6906b2934e5358432200615fe4503729b851e2f89f59`<br>Plist：`com.hp.syslogger.plist` (`687` B, SHA256 `a9cdc00c697e9de435473f9798f203b6f4d719c6ba6332bc5d531003bc7f78f7`)<br>轮转配置：`com.hp.conf` (`673` B, SHA256 `147ee168926622c2f5567c99bd602c1a15dea4f55d47f59946af4f7fa87ba374`) | `stage3-logging/usr-local-bin/hp-syslogger.py`<br>`13,043` B<br>SHA256 `9f22348437736568d9ca6906b2934e5358432200615fe4503729b851e2f89f59` | 跨重启持久化日志与 `/usr/sbin/bluetoothd` 页锁定常驻守护进程：通过 `mmap` + `mlock` 锁定 `bluetoothd` `[0x0..0xab0000)` 防止 `BlueToolFixup.kext` 内存补丁页与 `decmpfs` 16KB 压缩簇部分逐出引发 `EBADMSG (error 94)` `SIGBUS`；按每次启动 UUID 在 `/var/log/hp/boot-<STAMP>-<UUID8>/`（`/var/log/hp/current` 软链，保留最近 15 次启动）持续归档 `dmesg`、`pmset`、Unified 错误流（过滤 `symptomsd` `"Out of range RSSI value"` 噪声并支持 `20 MiB` 单备份滚动轮转）、`STOP_EVENT.wait()` 零空闲唤醒轮询与 `SIGTERM` 关机快照 |
| **`va` (`AppleIntelTGLGraphicsVADriver.bundle` 归档补丁脚本)** *(生产环境不部署)* | 自包含安装脚本：`.local/driver-repair-20261103/vadriver-build/va` (`7,242` B, SHA256 `2f373a56d389a80ba4056d162dd15327c2baec225a740097f2c7ecc7d465e559`)<br>模块化补丁脚本集：`.local/clean-upstream-20261102/source/macos/vadriver/` (`build-vadriver.sh` `3,369` B, SHA256 `1e4ca0a8d0980670f6801c991a65440c02a50580655c8e4fee4745806482562f`)<br>回执：`deploy-receipt.json` | 原版未修补：`AppleIntelTGLGraphicsVADriver` (`8,450,544` B, SHA256 `d265f2038135c2c5c3649b621d9aea48cf1cb74a1fb36069bb1b3562b3750129`)<br>补丁后未签名 SHA256：`b4ab647b23e448d6835e069a60cd4bd174865b01fcdbf67d27ef703e149fb7c0`<br>套件归档备查版：`AppleIntelTGLGraphicsVADriver` (`8,463,472` B, SHA256 `6291f574afa064ed2dd56f6787cd92bcf79750b16cc13ef6d07a49e599934dff`) | 对 Big Sur 11.4 原版 `AppleIntelTGLGraphicsVADriver`（`16.0.32`）应用 8 个机器码修补脚本的实验性归档产物；**注意：生产环境 `/Library/GPUBundles/` 仅部署 `AppleIntelTGLGraphicsMTLDriver.bundle` 与 `AppleIntelGraphicsShared.bundle` 2 个核心 Bundle（`install-stage2-gpu.sh` 会自动清理残留的 `VADriver.bundle` 与 `VAME.bundle`）**，由软解 + `xe-h264sw-fixd` + `HP-BLITALIGN` 保障全场景稳定播放 |
| **`RidgeKey` (`06cb:00f0` 指纹认证套件)**<br>`/usr/local/ridgekey/` & `/Applications/RidgeKey.app` | 源码仓库：`.local/peripheral-prep-20261105/RidgeKey-repo/` (HEAD commit `4968672`；预编译发行包 `BUILDINFO.txt` CI commit `dcd9e47`)<br>构建定义：`src/meson.build` (`3,215` B)、`app/Package.swift`、`scripts/build-app.sh`、`scripts/build-pkg.sh`、`scripts/install.sh`<br>防全擦除补丁：`patches/libfprint/` | 安装套件目录：`stage3-ridgekey/`<br>`ridgekeyd` (SHA256 `f20da2a091aef6d65feaa55b3501c246d364d9b54ff78e723b7a0a50201cc6f4`)<br>`ridgekeyctl` (SHA256 `6577e8d3260d24b30372cc66497d77ff112a8175fddfa82c64bdc0d5e8a5a4e3`) | 基于 `libfprint-2` 的用户态 Synaptics `06cb:00f0` Match-On-Chip 指纹守护进程（`ridgekeyd`）、CLI（`ridgekeyctl`）、`sudo` PAM 模块（`pam_ridgekey.so`）、锁屏代理（`RidgeKeyAgent.app`）、管理员授权插件（`RidgeKey.bundle`）与 SwiftUI 管理应用（`RidgeKey.app`） |

#### 2. 背光、热键、音频、软解守护与 Metal 垫片本地交叉编译命令（`nix develop`）

在 `/srv/mac-for-elitebook` 下，使用 `nix develop` 与 `$SDKROOT`（或本地桩库目录 `.local/driver-repair-20261103/brightness-fix-20261107/stubs/`）即可直接从 `.m`/`.c` 源码交叉编译并签名 `libhp_cb_shim.dylib`、`libxedrv.dylib`、`xe-h264sw-fixd`、`hp-wake-helper`、`hp-bridge` 与 `hp-select-speaker`（其中 `libhp_cb_shim.dylib`、`libxedrv.dylib` 与 `hp-bridge` 均产生与仓库预备产物 **逐字节完全一致** 的 SHA256，`xe-h264sw-fixd` 的 Mach-O 代码/数据段 `[0x0000..0x47b0)` 与 `LC_UUID` 逐字节完全一致）：

```sh
cd /srv/mac-for-elitebook
STUBS=".local/driver-repair-20261103/brightness-fix-20261107/stubs"

# 1. 编译并签名 corebrightnessd 动态注入库 libhp_cb_shim.dylib (hp-cb-shim.m)
# 精确复现 35,456 B 与 SHA256 e3b8378dc67e8ad9d19cdf5e025710660e73a6ce23885a82f910ac69b689b798
nix develop -c bash -c "
  clang -target x86_64-apple-macos13.0 -O2 -fPIC -c \
    .local/driver-repair-20261103/brightness-fix-20261107/hp-cb-shim.m \
    -o /tmp/hp-cb-shim.o
  ld64.lld -dylib -arch x86_64 -platform_version macos 13.0 13.0 \
    -install_name /usr/local/lib/libhp_cb_shim.dylib \
    /tmp/hp-cb-shim.o \
    \"$STUBS/libSystem.tbd\" \"$STUBS/CoreFoundation.tbd\" \
    \"$STUBS/IOKit.tbd\" \"$STUBS/CoreDisplay.tbd\" \
    -o /tmp/libhp_cb_shim.dylib
  rcodesign sign /tmp/libhp_cb_shim.dylib
  sha256sum /tmp/libhp_cb_shim.dylib
  rm -f /tmp/hp-cb-shim.o /tmp/libhp_cb_shim.dylib
"

# 2. 交叉编译并签名 Metal ABI 适配层 libxedrv.dylib (libxedrv.m，必须使用 -fno-objc-arc)
# 精确复现 65,280 B 与 SHA256 312ecf603a27526df87417980fd64fddd2d51e16754aa5deff8a1deeb76226b2
nix develop -c bash -c '
  "$CLANG_APPLE" -target x86_64-apple-macos15.0 -isysroot "$SDKROOT" \
    -O2 -fPIC -fno-objc-arc -c \
    .local/driver-repair-20261103/vt-audio-fix-20261106/libxedrv.m \
    -o /tmp/libxedrv.o
  "$LD64_LLD" -dylib -arch x86_64 -platform_version macos 15.0 26.5 -syslibroot "$SDKROOT" \
    -install_name /Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib \
    /tmp/libxedrv.o -lSystem -framework Foundation -framework CoreFoundation \
    -lobjc -framework Metal -framework IOSurface \
    -o /tmp/libxedrv.dylib
  rcodesign sign /tmp/libxedrv.dylib
  sha256sum /tmp/libxedrv.dylib
  rm -f /tmp/libxedrv.o /tmp/libxedrv.dylib
'

# 3. 交叉编译并签名 H.264 软解修复守护进程 xe-h264sw-fixd (xe-h264sw-fixd.c)
# 精确复现 24,496 B、Mach-O 主体 [0..0x47b0) 与 LC_UUID 4C4C44B3-5555-3144-A1E7-A919CC286F49
nix develop -c bash -c '
  "$CLANG_APPLE" -target x86_64-apple-macos15.0 -isysroot "$SDKROOT" \
    -fuse-ld=lld --ld-path="$LD64_LLD" -O2 \
    .local/driver-repair-20261103/s0ix-standby-prep-20261107/live-846ba6e6/xe-h264sw-fixd.c \
    -o /tmp/xe-h264sw-fixd
  rcodesign sign /tmp/xe-h264sw-fixd
  rm -f /tmp/xe-h264sw-fixd
'

# 4. 交叉编译并签名现役睡眠/唤醒与背光/音频守护进程 hp-wake-helper 及热键桥接守护进程 hp-bridge
nix develop -c bash -c '
  "$CLANG_APPLE" -target x86_64-apple-macos15.0 -isysroot "$SDKROOT" \
    -fuse-ld=lld --ld-path="$(which ld64.lld)" -O2 -fobjc-arc \
    -framework Foundation -framework CoreWLAN -framework CoreAudio \
    -framework CoreGraphics -framework IOKit -framework CoreFoundation \
    .local/driver-repair-20261103/s0ix-standby-prep-20261107/live-846ba6e6/hp-wake-helper.m \
    -o /tmp/hp-wake-helper
  rcodesign sign /tmp/hp-wake-helper

  "$CLANG_APPLE" -target x86_64-apple-macos15.0 -isysroot "$SDKROOT" \
    -fuse-ld=lld --ld-path="$LD64_LLD" -O2 -fobjc-arc \
    -F"$SDKROOT/System/Library/PrivateFrameworks" \
    -framework Cocoa -framework Carbon -framework CoreAudio -framework CoreFoundation \
    -framework CoreGraphics -framework IOKit -framework DisplayServices \
    -framework CoreDisplay -framework AppKit -framework Foundation \
    .local/driver-repair-20261103/s0ix-standby-prep-20261107/live-846ba6e6/hp-bridge.m \
    -o /tmp/hp-bridge
  rcodesign sign /tmp/hp-bridge
  rm -f /tmp/hp-wake-helper /tmp/hp-bridge
'

# 5. 编译并签名扬声器默认输出切换工具 hp-select-speaker (hp-select-speaker.m)
nix develop -c bash -c "
  clang -target x86_64-apple-macos13.0 -O2 -c \
    .local/driver-repair-20261103/audio-ridgekey-fix-20261107/hp-select-speaker.m \
    -o /tmp/hp-select-speaker.o
  ld64.lld -arch x86_64 -platform_version macos 13.0 26.5 \
    /tmp/hp-select-speaker.o \
    \"$STUBS/CoreAudio.tbd\" \"$STUBS/CoreFoundation.tbd\" \"$STUBS/libSystem.tbd\" \
    -o /tmp/hp-select-speaker
  rcodesign sign /tmp/hp-select-speaker
  rm -f /tmp/hp-select-speaker.o /tmp/hp-select-speaker
"
```

> [!TIP] **在目标机 macOS 原生编译等价命令**
> 若在目标机 macOS 终端（已安装 Xcode Command Line Tools）直接编译上述工具，可使用系统框架直接编译签名：
> ```sh
> clang -dynamiclib -O2 -arch x86_64 -mmacosx-version-min=13.0 \
>   -install_name /usr/local/lib/libhp_cb_shim.dylib \
>   -framework CoreFoundation -framework IOKit -F/System/Library/Frameworks -framework CoreDisplay \
>   hp-cb-shim.m -o libhp_cb_shim.dylib && codesign -f -s - libhp_cb_shim.dylib
>
> clang -O2 -fobjc-arc -arch x86_64 \
>   -framework Foundation -framework CoreWLAN -framework CoreAudio \
>   -framework CoreGraphics -framework IOKit -framework CoreFoundation \
>   hp-wake-helper.m -o hp-wake-helper && codesign -f -s - hp-wake-helper
>
> clang -O2 -fobjc-arc -arch x86_64 \
>   -framework Cocoa -framework Carbon -framework CoreAudio -framework CoreFoundation \
>   -framework CoreGraphics -framework IOKit -F/System/Library/PrivateFrameworks \
>   -framework CoreDisplay -framework DisplayServices \
>   hp-bridge.m -o hp-bridge && codesign -f -s - hp-bridge
>
> clang -O2 -arch x86_64 xe-h264sw-fixd.c -o xe-h264sw-fixd && codesign -f -s - xe-h264sw-fixd
>
> clang -O2 -arch x86_64 -mmacosx-version-min=13.0 \
>   -framework CoreAudio -framework CoreFoundation \
>   hp-select-speaker.m -o hp-select-speaker && codesign -f -s - hp-select-speaker
>
> clang -dynamiclib -O2 -fno-objc-arc -arch x86_64 -mmacosx-version-min=15.0 \
>   -install_name /Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib \
>   -framework Foundation -framework CoreFoundation -framework Metal -framework IOSurface \
>   libxedrv.m -o libxedrv.dylib && codesign -f -s - libxedrv.dylib
> ```

#### 3. `AppleIntelTGLGraphicsVADriver.bundle` 8 个模块化修补脚本与自包含脚本（`va`，归档备查）技术明细

> [!NOTE] **生产环境说明**
> 在 macOS Tahoe `26.6.2` (`25G83`) 生产环境中，`/Library/GPUBundles/` **不安装** `AppleIntelTGLGraphicsVADriver.bundle` 与 `AppleIntelTGLGraphicsVAME.bundle`（由 `install-stage2-gpu.sh` 自动移除残留），使 VideoToolbox 稳定走软件解码 + `/usr/local/libexec/xe-h264sw-fixd` + 内核 `HP-BLITALIGN` 2D 拷贝路径。以下 8 个机器码修补脚本及归档产物保留在仓库与安装套件目录中供硬件解码研究备查。

上游模块化补丁脚本集位于 `.local/clean-upstream-20261102/source/macos/vadriver/`（主控构建脚本 `build-vadriver.sh`，`3,369` B，SHA256 `1e4ca0a8d0980670f6801c991a65440c02a50580655c8e4fee4745806482562f`），而 `.local/driver-repair-20261103/vadriver-build/va`（`7,242` B，SHA256 `2f373a56d389a80ba4056d162dd15327c2baec225a740097f2c7ecc7d465e559`）将这 **8 个 Python 机器码修补阶段**合并为单文件自包含脚本。对 Big Sur 11.4 移植版原版 `AppleIntelTGLGraphicsVADriver`（`8,450,544` B，未修补 SHA256 `d265f2038135c2c5c3649b621d9aea48cf1cb74a1fb36069bb1b3562b3750129`）依次执行以下 8 项修补后，确定性产出未签名 SHA256 `b4ab647b23e448d6835e069a60cd4bd174865b01fcdbf67d27ef703e149fb7c0`（本地 `codesign` 签名版 SHA256 `cb82639fb7b6af838d36e70a7bfc83bb9cc17ae87cf56e15752594c1104c659b`）：

1. **`patch-vadriver.py`**（`1,832` B，SHA256 `1f7736935da713295aafd1a47046f0e0c9b53524103bbea37413de2ccb5020f2`）：
   - `0x130aa` (`CreateDriverContext` 清理分支)：`e8 e3 d0 4d 00` -> `90 90 90 90 90`（NOP 掉清理分支中因 Tahoe 结构体布局变化导致崩溃的 `vtable+0x30` 调用）；
   - `0x13172` (`CreateContext` 版本号检查)：`0f 85 17 01 00 00` -> `90 90 90 90 90 90`（移除 `ctx+0x8 == 0x201` 版本强校验，兼容 Tahoe AppleGVA 传入的 `0x202`）；
   - `0x15456` (`CodecHalDecodeCreate` 分配失败检查)：`74 61` -> `90 90`（当 `0x2b8` 处为空时继续执行而非直接中止）；
   - `0x1545c` (`CodecHalDecodeCreate` 返回值覆写)：`e8 e9 4e 4b 00 41 89 c6` -> `31 f6 90 90 90 90 90 90`（强制 `r14d = 0` 返回成功）；
   - `0x1623c` (`DestroyContext`)：`48 8b 07 ff 50 20` -> `90 90 90 90 90 90`（当 Decoder 对象为空时跳过 `vtable+0x20` 析构调用）。
2. **`patch_nodes.py`**（`2,784` B，SHA256 `1082da6644052bf3616dc9d964a508da03c7605e9a2c039f14b4d0edeaf22f4f`）：
   - `0x24361f` & `0x24364f`：将两处 `80 7c 08 58 00`（检查 88B 步长的 `[rax+rcx+0x58]` 字节）修补为 `80 3c 08 00 90`（检查 `[rax+rcx+0x00]` 处的 surface node ID），并配合后续步长修补适配 Tahoe AppleGVA 的 80B Surface Node。
3. **`patch_nodelayout.py`**（`9,138` B，SHA256 `34a99cd183039dfd4fe33001902e0ea6aeacca1b4643501ed56c35abe262e612`）：
   - `0x2bbe7`：将 `add rcx, 0x58`（88B 步长）改为 `add rcx, 0x50`（80B 步长）；
   - `0x2bc7e .. 0x2be1b`：在 `GetSurfaceInfo` 中重写 11 处 `imul reg, reg, 0x58` 为 `0x50`，并将旧 88B Node 偏移 `+0x1a`/`+0x18`/`+0x08` 重映射至 Tahoe 80B Node 的 `+0x08` (width) / `+0x0a` (height) / `+0x10` (bo_ptr)。
4. **`patch_payloadhdr.py`**（`1,419` B，SHA256 `680fa20e0d6be7b63eb2b18e4e5682c35695913f063ac2c8a67c302ad57c8d0b`）：
   - 在 `__TEXT` 头部空洞写入三段跳板机器码：`0x0d00`（`GetSurfaceInfo` 入口转换器：将 Tahoe 88B 新式 Node 头部 `hdr == 0x00010002` 原地转换为 Big Sur 驱动期望的字段布局）、`0x0b00`（`os_resource` 对象填充器）、`0x1100`（`gmm_res_info` 伪对象构造器，使 `[gmm+0x120]` 返回 TileY `1`、vtable 槽位返回有效对齐与尺寸），并将 `0x2bb2a` 重定向至 `0x0d00`。
5. **`patch_pitchdelta.py`**（`2,414` B，SHA256 `35bdcbf2c2266a96ff020fc2b3fe9de99edc8db9e9b93ba2d27370dc73a75c2d`）：
   - 在 `0x0e00` 注入 `SendSurfaceState` 循环前置修正跳板（当 `os_res+0x28` 的 pitch/height/Y-offset 为 `0` 时，从 `frame_desc` 动态回填对齐后的 pitch、height 及 UV 平面偏移 `aligned_h`），并将 `0x6453c` 跳转至 `0x0e00`、在 `0x64a15` 将 `lea r8, [r15+rax*8]` 修补为 `mov r8, r15; nop`。
6. **`patch_spsshift.py`**（`1,729` B，SHA256 `e6f1f7950d9ac10f1c60397a56301f650527d7d7dac9da27055359a691f3b92a`）：
   - 修复 Tahoe AppleGVA HEVC SPS 参数缓冲区偏移右移 `+4` 字节的 ABI 差异：在 `0x228e3f` 注入 `add r12, 4`（跳转至 `0x0f00` 跳板并在 `0x193543` 挂载），并在 `0x229740`（PicWidth/PicHeight 读取）与 `0x229655`（ChromaFormat 读取）同步修正 `+4` 偏移。
7. **`patch_hcpsurface.py`**（`2,202` B，SHA256 `7f6dc846ad86a73c0c375824084e6545c74674e0e12b3a906bc1f0f392ca0491`）：
   - 在 `0x0f00` 写入 `AddHcpSurfaceCmd` 跳板（当 `[rcx+0x10]` 处的 `YPlaneOffset.iYOffset == 0` 时，自动从 `params+0x08` 读取 `recon_surface` 的高度补齐 UV 偏移，防止 `HCP_SURFACE_STATE` DW2 全零导致色度平面与亮度平面重叠绿屏）。
8. **`patch_hevclastslice.py`**（`2,704` B，SHA256 `761f298ba1bd634bc1e97b4e2ac1a6d508c6d32902036df4659bf3201444fc10`）：
   - 在 `0x13fee0` 拦截 `IsHevcLastSlice` 判定并跳往 `0x0f40` 跳板（强制 `al = 1`，解决 Tahoe AppleGVA 单 Slice 帧缓冲缩减 4 字节导致 `[r8+0x73]` 恒为 `0`、从不写入 `HCP_BSD_OBJECT` 进而引发 `VDBOX` 解码超时的问题）。

在本地开发机从原版二进制重现上述 8 步修补并验证未签名 SHA256 的命令如下：

```sh
cd /srv/mac-for-elitebook
cp .local/clean-upstream-20261102/build/install-stage/sle/AppleIntelTGLGraphicsVADriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsVADriver /tmp/va_repro
for s in patch-vadriver.py patch_nodes.py patch_nodelayout.py patch_payloadhdr.py patch_pitchdelta.py patch_spsshift.py patch_hcpsurface.py patch_hevclastslice.py; do
  python3 ".local/clean-upstream-20261102/source/macos/vadriver/$s" /tmp/va_repro
done
sha256sum /tmp/va_repro
# 输出: b4ab647b23e448d6835e069a60cd4bd174865b01fcdbf67d27ef703e149fb7c0  /tmp/va_repro
rm -f /tmp/va_repro
```

#### 4. `RidgeKey` (`06cb:00f0`) 源码结构与构建命令

- **源码树**：`.local/peripheral-prep-20261105/RidgeKey-repo/`（上游 `labrouss/RidgeKey` `v1.0.0`，本地仓库 HEAD commit `4968672`；安装套件预编译产物见 `BUILDINFO.txt`，对应上游 CI commit `dcd9e47`）：
  - **C 守护进程与安全插件（Meson 构建系统，`src/meson.build`）**：
    - `ridgekeyd` 根守护进程：`src/daemon/ridgekeyd.c`、`store.c`、`secret.c`、`console.c`、`peer.c`、`prompt.c`、`actions.c`（依赖 `libfprint-2`、`glib-2.0`、`gio-2.0`）；
    - `ridgekeyctl` 命令行客户端：`src/ctl/ridgekeyctl.c`（仅依赖 macOS 系统 SDK XPC + `libdispatch`）；
    - `pam_ridgekey.so`（`sudo` PAM 模块）：`src/pam/pam_ridgekey.c`（依赖 `libpam` + `CoreFoundation`）；
    - `ridgekey-agent`（`RidgeKeyAgent.app` 锁屏解锁代理）：`src/agent/ridgekey-agent.c`（依赖 `CoreFoundation`、`CoreGraphics`、`Security`、`ApplicationServices`、`Carbon`、`HIToolbox`、`SkyLight`）；
    - `RidgeKey.bundle`（`authorizationhost` 管理员弹窗插件）：`src/authplugin/ridgekey-authplugin.c`（依赖 `Security`、`CoreFoundation`）。
  - **SwiftUI 设置应用（`RidgeKey.app`）**：`app/Package.swift` 与 `scripts/build-app.sh`。
  - **`libfprint` 安全补丁**：`patches/libfprint/`（移除全传感器擦除指令，保护同芯片存储的 Windows Hello 与 BIOS 指纹）。
- **本地 Linux 开发机交叉编译仅依赖 macOS 系统框架的 4 个核心组件（`ridgekeyctl`、`pam_ridgekey.so`、`ridgekey-agent`、`RidgeKey.so`）**：
  ```sh
  cd /srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo
  nix develop /srv/mac-for-elitebook -c bash -c '
    mkdir -p /tmp/rk-build
    CFLAGS="-target x86_64-apple-macos13.0 -isysroot $SDKROOT -O2 -Wall -Wextra -std=c11 -Isrc/common"

    # 1. ridgekeyctl
    "$CLANG_APPLE" $CFLAGS -c src/ctl/ridgekeyctl.c -o /tmp/rk-build/ridgekeyctl.o
    "$LD64_LLD" -arch x86_64 -platform_version macos 13.0 13.0 -syslibroot "$SDKROOT" \
      /tmp/rk-build/ridgekeyctl.o -lSystem -o /tmp/rk-build/ridgekeyctl

    # 2. pam_ridgekey.so
    "$CLANG_APPLE" $CFLAGS -fPIC -c src/pam/pam_ridgekey.c -o /tmp/rk-build/pam_ridgekey.o
    "$LD64_LLD" -dylib -arch x86_64 -platform_version macos 13.0 13.0 -syslibroot "$SDKROOT" \
      /tmp/rk-build/pam_ridgekey.o -lpam.2 -framework CoreFoundation -lSystem -o /tmp/rk-build/pam_ridgekey.so

    # 3. ridgekey-agent
    "$CLANG_APPLE" $CFLAGS -Wno-deprecated-declarations -c src/agent/ridgekey-agent.c -o /tmp/rk-build/ridgekey-agent.o
    "$LD64_LLD" -arch x86_64 -platform_version macos 13.0 13.0 -syslibroot "$SDKROOT" \
      -F"$SDKROOT/System/Library/PrivateFrameworks" \
      -F"$SDKROOT/System/Library/Frameworks/Carbon.framework/Frameworks" \
      /tmp/rk-build/ridgekey-agent.o -framework CoreFoundation -framework CoreGraphics \
      -framework Security -framework ApplicationServices -framework Carbon -framework HIToolbox \
      -framework SkyLight -lSystem \
      -o /tmp/rk-build/ridgekey-agent

    # 4. RidgeKey.so (RidgeKey.bundle/Contents/MacOS/RidgeKey)
    "$CLANG_APPLE" $CFLAGS -fPIC -c src/authplugin/ridgekey-authplugin.c -o /tmp/rk-build/ridgekey-authplugin.o
    "$LD64_LLD" -bundle -arch x86_64 -platform_version macos 13.0 13.0 -syslibroot "$SDKROOT" \
      /tmp/rk-build/ridgekey-authplugin.o -framework Security -framework CoreFoundation -lSystem \
      -o /tmp/rk-build/RidgeKey.so

    rm -rf /tmp/rk-build
  '
  ```
- **在目标机 macOS 环境完整编译全部组件（含依赖 Homebrew `libfprint-2` / `glib-2.0` 的 `ridgekeyd` 与 SwiftUI `RidgeKey.app`）**：
  ```sh
  cd /srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo
  # 1. 编译 ridgekeyd, ridgekeyctl, pam_ridgekey.so, ridgekey-agent, RidgeKey.so
  meson setup build src --buildtype=debugoptimized
  meson compile -C build

  # 2. 编译 SwiftUI 设置应用 RidgeKey.app 并打包 .pkg 安装器
  bash scripts/build-app.sh
  ```

---

## 15. 一键后置安装套件与急救恢复镜像组装校验 (Post-Install Bundle & Recovery Image Assembly)

完成上述自定义组件重编译后，可将其同步封装至一键后置安装套件 `HP-Tahoe-PostInstall-20261108.tar.gz` 及 Ventoy 急救恢复镜像 `HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`：

| 归档 / 镜像产物 | 本地归档路径与内置预置路径 | 精确字节数与 SHA256 校验值 |
| --- | --- | --- |
| **`HP-Tahoe-PostInstall-20261108.tar.gz`** | 本地：`.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108.tar.gz`<br>内置盘预置：`/Volumes/系统/hpdiag/HP-Tahoe-PostInstall-20261108.tar.gz`（NixOS `/mnt/win_sys/hpdiag/HP-Tahoe-PostInstall-20261108.tar.gz`，待下次开机进入 NixOS 时同步最新归档） | `125,574,606` B（约 `120 MB`），SHA256 `ca9bc1dcd1549aadda55159e66ad8d6b9445eea716380d5d6bca16e0f9bd9457` |
| **`SHA256SUMS.txt`** | `.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/SHA256SUMS.txt` | `64,420` B（`431` 个打包文件），SHA256 `39ed1fa6b13b45434329abc8b2377b3b56e2352ca53289954401a7f822df65ff` |
| **`bundle-receipt.json`** | `.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/bundle-receipt.json` | `5,334` B，SHA256 `b0defcfa7bcf68403541315ab31a141e7f16d087e87b31c940632e3238a3a6e5` |
| **`verify-postinstall.sh` / `verify-phase10-lidwake-and-video.sh` / `test_420v_blitalign`** | `.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/` | `verify-postinstall.sh`：`8,852` B，SHA256 `499ac36510ffa2c67bf492330377dc7577dc719853fe8280a94ed00e19319387`<br>`verify-phase10-lidwake-and-video.sh`：`7,639` B，SHA256 `eeebfac56d8e79b59fc42db33e3672112d9eeb8bf136148018ac5024762ea218`<br>`test_420v_blitalign`：`51,680` B，SHA256 `887743ebd0b11797fa46553fa2420df21adf266c76ce6d0d540ac51e415e75bf` |
| **`HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`** | `.local/driver-repair-20261103/s0ix-standby-prep-20261107/HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`（FAT32 偏移 `@@1048576`） | `1,343,225,856` B（`1.25 GiB`），SHA256 `52512051c894922bfba791b4aa40fdf89182199a84a68fd249ddee2cc22e7585` |
| **`after-lidwake-greenfix-boot-oc.tar`** | `.local/driver-repair-20261103/s0ix-standby-prep-20261107/post-wake-ebaba2ee/after-lidwake-greenfix-boot-oc.tar`（内置盘 `disk0s6` `/boot/EFI/OC` Phase 19 回读归档；Phase 22 `S0ixStandby` 待唤醒同步） | `41,840,640` B，SHA256 `f123431da76bf520c93653266f49a3899fd0a0af5511b6edfc82fab0e2affaa7` |
| **`scripts/verify_release_artifacts.py` & `Makefile` (`verify-release`)** | [`scripts/verify_release_artifacts.py`](../scripts/verify_release_artifacts.py)<br>[`Makefile`](../Makefile) | `scripts/verify_release_artifacts.py`：`132,501` B，SHA256 `78a133da6c72eadf978f12c1db7dfddb82128e89d61aac0915d8ef342e2e77a9`<br>`Makefile`：`2,019` B，SHA256 `8c9cb233f61f5b7265dd83a7dee74ab88c24d9ba395ac85d0c8da22a5d443157` |

- **使用 `nix develop` (`mtools`) 更新急救恢复镜像并回读校验命令**：
  ```sh
  nix develop /srv/mac-for-elitebook -c bash -c '
    IMG="/srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img"
    PART="${IMG}@@1048576"
    mcopy -o -i "$PART" /srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/SSDT-DEEPIDLE.aml ::/EFI/OC/ACPI/SSDT-DEEPIDLE.aml
    mcopy -o -i "$PART" /srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/build/snapshot/NootedGreen.kext/Contents/MacOS/NootedGreen ::/EFI/OC/Kexts/NootedGreen.kext/Contents/MacOS/NootedGreen
    mcopy -o -i "$PART" /srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/build/snapshot/NootedGreen.kext/Contents/Info.plist ::/EFI/OC/Kexts/NootedGreen.kext/Contents/Info.plist
    mcopy -o -i "$PART" /srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/S0ixStandby.kext/Contents/MacOS/S0ixStandby ::/EFI/OC/Kexts/S0ixStandby.kext/Contents/MacOS/S0ixStandby
    sha256sum "$IMG"
  '
  ```
- **使用 `nix develop -c make verify-release` 执行全仓库端到端发布产物、`9/9` 源码净室重编译与在线 NixOS 实机一致性校验**：
  ```sh
  # 1. 本地全量校验（核心产物 SHA256 + 跨清单一致性、431 文件安装套件与压缩包、112 文件 OpenCore EFI 与恢复镜像、二进制/AML/补丁特征标记、9/9 项源码净室重编译）
  nix develop -c env PYTHONDONTWRITEBYTECODE=1 make verify-release

  # 2. 连同源码净室重编译与在线 NixOS 实机只读核验 /boot/EFI/OC（111 文件 + 5 项关键产物）并生成 JSON 报告
  nix develop -c env PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_release_artifacts.py \
    --check-source-rebuilds \
    --check-live-nixos <user>@<nixos-host> \
    --json-out .local/driver-repair-20261103/s0ix-standby-prep-20261107/post-wake-ebaba2ee/release-verification-report.json
  ```
