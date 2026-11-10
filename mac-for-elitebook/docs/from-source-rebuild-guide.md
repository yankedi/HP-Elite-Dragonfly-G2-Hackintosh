# 自定义组件源码索引与从源码重编译指南 (Custom Component Source Index & From-Source Rebuild Guide)

> 本文档与 [`docs/clean-install-guide.md` 第 8 节](clean-install-guide.md) 保持完全同步，完整记录 HP EliteBook 840 G8 (`880D`) / HP Elite Dragonfly G2 (`8716`) macOS Tahoe 26 (`25A354` / `25G83`) 全部 12 项自定义/修改版组件的源码路径、SHA256 校验值、修改细节及从源码重编译命令。

本节完整列出本机型（HP Elite Dragonfly G2 `8716` / 同平台 HP EliteBook 840 G8 `880D`）在 **macOS Tahoe 26（`26.6.2` / `25G83`）** 下所使用的全部自定义内核扩展（Kexts）、ACPI SSDT 热补丁（`.dsl` -> `.aml`）、用户态守护进程/动态库 Shim、音频/背光脚本以及 GPU 二进制补丁脚本的**精确源码路径、SHA256 校验值与从源码重编译命令**（独立单册版同步维护于 [docs/from-source-rebuild-guide.md](file:///srv/mac-for-elitebook/docs/from-source-rebuild-guide.md)）。所有本地交叉编译、链接、签名与 IASL 编译均可在 Linux 开发机（`/srv/mac-for-elitebook`）通过仓库根目录的 [flake.nix](file:///srv/mac-for-elitebook/flake.nix)（`nix develop`）零外部依赖复现，亦可在 macOS 本机使用 Xcode Command Line Tools 原生编译。

---

## 1. 核心内核扩展 (Kexts) 源码与重编译流程

| 内核扩展名称 | 版本 / 补丁标识 | 源码目录与核心源文件 | 仓库跟踪补丁 / 构建脚本 | 产物二进制路径与 SHA256 |
| --- | --- | --- | --- | --- |
| **`NootedGreen.kext`** | `1.0.0` (`com.StezzaPilot.NootedGreen`, `R32-PCFIX33-S0IX` + Phase 10 `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16`, `LC_UUID` `4C4C44C0-5555-3144-A178-618CB8A052CE`) | 源码树：[.local/driver-repair-20261103/repair32-readback/source/](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/source)<br>核心实现：[kern_gen11.cpp](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/source/src/NootedGreen/kern_gen11.cpp) (`702,685` B, SHA256 `0be6ad5122f4ea44d04a76da7154d3c705814432b13b05800bb1d5cb6f1e61ef`)、[kern_green.cpp](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/source/src/NootedGreen/kern_green.cpp) (`50,913` B, SHA256 `eb0f7c9a3b379c6cb77641bfd3f3beacd9c8c5e4fbd176934914a3db49fd3db5`)、[kern_gen11.hpp](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/source/src/NootedGreen/kern_gen11.hpp) (`86,202` B)、[kern_green.hpp](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/source/src/NootedGreen/kern_green.hpp) (`10,703` B)、[kern_start.cpp](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/source/src/NootedGreen/kern_start.cpp) (`1,877` B) | 完整累积补丁：[patches/nootedgreen-r32-pcfix35-blitalign-20261108.patch](file:///srv/mac-for-elitebook/patches/nootedgreen-r32-pcfix35-blitalign-20261108.patch) (`88,645` B, SHA256 `431541a3e61537db7d3f7fdae224e979bf1ca4618826267474ada5a01f7e1cfa`)<br>历史演进补丁：[nootedgreen-r32-pcfix27-20261106.patch](file:///srv/mac-for-elitebook/patches/nootedgreen-r32-pcfix27-20261106.patch)、[nootedgreen-r32-pcfix31-backlight-20261107.patch](file:///srv/mac-for-elitebook/patches/nootedgreen-r32-pcfix31-backlight-20261107.patch)、[nootedgreen-r32-pcfix32-s0ix-20261107.patch](file:///srv/mac-for-elitebook/patches/nootedgreen-r32-pcfix32-s0ix-20261107.patch)、[nootedgreen-r32-pcfix33-s0ix-20261108.patch](file:///srv/mac-for-elitebook/patches/nootedgreen-r32-pcfix33-s0ix-20261108.patch)<br>构建脚本：[build.py](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/build.py) + [offline-wrapper.py](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/build/offline-wrapper.py) | [NootedGreen](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/build/snapshot/NootedGreen.kext/Contents/MacOS/NootedGreen) (`535,984` B, SHA256 `ffa4b51e34ffbeb5aae68f55a8e79bc0794f7499c823b84ac58bde6057a96b15`)<br>[Info.plist](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/build/snapshot/NootedGreen.kext/Contents/Info.plist) (`3,700` B, SHA256 `b5fd1d0fe125a48f6045c3b07a8f5894f76fc406caf5065f126830a63ea4738e`)<br>回执：[build-receipt.json](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/build-receipt.json) |
| **`S0ixStandby.kext`** | `v0.4.4` (`com.labrouss.S0ixStandby`, commit `8b37bb4` + Phase 11 定时器过早释放修复 & `-s0ixcnvwd3`) | 源码仓库：[.local/peripheral-prep-20261105/S0ixStandby-repo/](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo)<br>核心实现：[S0ixStandby.cpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo/S0ixStandby/S0ixStandby.cpp) (`46,144` B, SHA256 `5a177cb6f5a3694c9cf1086f9cc4681f5a71c55f99c2eac113c70eade4e4f46a`)、[S0ixGPU.cpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo/S0ixStandby/S0ixGPU.cpp) (`23,777` B, SHA256 `e22b3d1874e7cf38196669354f712c5cb880bfad7423299d84d18681faef58c1`)、[S0ixStandby.hpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo/S0ixStandby/S0ixStandby.hpp) (`10,059` B, SHA256 `05217538683a1594ea58ccaf977d76212ab85cad266724cad89d4fe38501ebed`)、[kmod_info.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo/S0ixStandby/kmod_info.c) (`733` B) | [Makefile](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo/Makefile) (`2,805` B, SHA256 `c963731d0467504b32f27da6d2b1e893b8a4378863ee0cfe18872b68f9e0a14d`) | 预备包：[.local/driver-repair-20261103/s0ix-standby-prep-20261107/S0ixStandby.kext](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/S0ixStandby.kext)<br>二进制：[S0ixStandby](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/S0ixStandby.kext/Contents/MacOS/S0ixStandby) (`65,192` B, SHA256 `a2baf7bddbb2768cfb53f4b7b991b36904d0730de2d96841489c6bdb25297ec3`)<br>[Info.plist](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/S0ixStandby.kext/Contents/Info.plist) (`4,668` B, SHA256 `4e82da9599fb42a99fdd2e317e29587f0343d661397ec2907a5dfbf5f18d473e`) |
| **`TGLDmic.kext` & `TGLDmic.driver`** | `v0.5.0` (`com.labrouss.TGLDmic` & `com.labrouss.TGLDmic.driver`, commit `d13dafa`) | 源码仓库：[.local/peripheral-prep-20261105/TGLDmic-repo/](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo)<br>Kext 源码：[TGLDmic.cpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/kext/TGLDmic/TGLDmic.cpp) (`19,556` B)、[DspBoot.cpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/kext/TGLDmic/DspBoot.cpp) (`20,788` B)、[Capture.cpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/kext/TGLDmic/Capture.cpp) (`18,737` B)、[TGLDmicUserClient.cpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/kext/TGLDmic/TGLDmicUserClient.cpp) (`4,089` B)、[IpcReplay.hpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/kext/TGLDmic/IpcReplay.hpp)、[Regs.hpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/kext/TGLDmic/Regs.hpp)、[DmaBuffer.hpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/kext/TGLDmic/DmaBuffer.hpp)、[TGLDmicShared.h](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/kext/TGLDmic/TGLDmicShared.h)、[sof-tgl.ri](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/firmware/intel/sof-tgl.ri)<br>HAL 插件与工具：[TGLDmicDriver.cpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/hal/TGLDmicDriver.cpp) (`42,856` B, SHA256 `4d1caf88cae4a0a550945c4e80b712806434baad603293492d30ae98d20cf4e8`)、[tgldmic-probe.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/hal/tgldmic-probe.c) (`3,980` B) | Kext：[kext/Makefile](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/kext/Makefile) (`1,890` B) + [tools/gen-fw.py](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/tools/gen-fw.py)<br>HAL：[hal/Makefile](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/hal/Makefile) (`915` B) + [hal/install-hal.sh](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/hal/install-hal.sh) | Kext 预备包：[TGLDmic.kext](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/audio-ridgekey-fix-20261107/tgldmic-prep-20261107/TGLDmic.kext)（二进制 [TGLDmic](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/audio-ridgekey-fix-20261107/tgldmic-prep-20261107/TGLDmic.kext/Contents/MacOS/TGLDmic) `1,199,424` B, SHA256 `b0d0715dfb49b6ea15208cdfa0f99373e2e62ee4e2a02448462252ef6721b416`；[Info.plist](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/audio-ridgekey-fix-20261107/tgldmic-prep-20261107/TGLDmic.kext/Contents/Info.plist) `1,646` B, SHA256 `ea026bd65b79ed171615f5df3f8a1cd72f6d76b97c3a01be9c2a5b523f3471f0`）<br>HAL 插件：[TGLDmic.driver](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-audio/Library-Audio-Plug-Ins-HAL/TGLDmic.driver)（二进制 [TGLDmic](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-audio/Library-Audio-Plug-Ins-HAL/TGLDmic.driver/Contents/MacOS/TGLDmic) `48,352` B, SHA256 `6e75f82f6a0237a40f20810df591b90e9c2161e34c389c5eb5e7534180eddca0`） |
| **`SimpleHDA.kext` & `AppleALC.kext`** | `SimpleHDA 1.0.1` (commit `18a16d4`) + `AppleALC 1.9.8` (`0xa0c8` + `layout-id 71`) | `SimpleHDA` 源码树：[.local/peripheral-prep-20261105/SimpleHDA-repo/](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/SimpleHDA-repo)<br>`AppleALC` 定制包：[.local/driver-repair-20261103/audio-ridgekey-fix-20261107/stage-oc/Kexts/AppleALC.kext](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/audio-ridgekey-fix-20261107/stage-oc/Kexts/AppleALC.kext) | [prepare_audio_config.py](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/audio-ridgekey-fix-20261107/prepare_audio_config.py) | [SimpleHDA](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/audio-ridgekey-fix-20261107/stage-oc/Kexts/SimpleHDA.kext/Contents/MacOS/SimpleHDA) (`4,458,280` B, SHA256 `5a1beec91f121a018072ac085c51543d5eaea85347e6417cd2e37d254d9383c1`)<br>[AppleALC](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/audio-ridgekey-fix-20261107/stage-oc/Kexts/AppleALC.kext/Contents/MacOS/AppleALC) (`3,810,852` B, SHA256 `690b96189491b9d6f64aa552da6684714d80ade4ad4ec9027251c3257a2d16e8`) |

#### 1. `NootedGreen.kext` (`R32-PCFIX33-S0IX` + Phase 10 `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16`) 源码补丁应用与本地交叉编译

1. **从上游干净基线应用跟踪补丁（或直接使用已就绪源码树）**：
   - 本地源码树位于 [.local/driver-repair-20261103/repair32-readback/source/](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/source)（上游基线 `ChefKissInc/NootedGreen` / `NootedGreen-NP550XDA` commit `6f03560`；核心文件 [`kern_gen11.cpp`](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/source/src/NootedGreen/kern_gen11.cpp) `702,685` B，SHA256 `0be6ad5122f4ea44d04a76da7154d3c705814432b13b05800bb1d5cb6f1e61ef`）。
   - 仓库跟踪的统一 diff 补丁 [patches/nootedgreen-r32-pcfix35-blitalign-20261108.patch](file:///srv/mac-for-elitebook/patches/nootedgreen-r32-pcfix35-blitalign-20261108.patch)（`88,645` B，SHA256 `431541a3e61537db7d3f7fdae224e979bf1ca4618826267474ada5a01f7e1cfa`）包含 `R32-PCFIX33-S0IX` 与 Phase 10 的全部核心改动：
     - **单端口 Execlist 串行化与 `ELSQWAIT`**：拦截 `submitToRing` 与 `processExeclist`，读取 `RING_EXECLIST_STATUS_LO` (`0x2234`) 确保 RCS0 硬件空闲后再写 `ELSQ`，消除跨上下文抢占覆盖；
     - **内核级 `hpSanitizeComputeEncoder` (`PCFIX27`)**：在内核提交前原地净化 3D/Compute 批处理缓冲，修补 `0x7a000004` `PIPE_CONTROL` 尾刷新位并在 `endOffDw` 追加读写缓存屏障，禁用 POSH (`cs + 0x10` `fAccelerator`)；
     - **内屏 eDP 硬件 PWM 背光缩放 (`XE-BLR` / `-ngreenblr`)**：拦截 `0xC8254` (`SBLC_PWM_FREQ`) 与 `0xC8258` (`SBLC_PWM_DUTY`) 全部 3 条 MMIO 写入路径；
     - **macOS 26 Tahoe S0ix 睡眠/唤醒全链路修复 (`PCFIX32` + `PCFIX33`)**：将 `AppleIntelBaseController::hwSaveNVRAM()` 路由为空操作（消除 `IODTPlatformExpert::_RESERVEDIODTPlatformExpert1` 内核 Panic）；在 `Gen11::wrapSetFramebufferPowerState` 中同时拦截 `FB0`/`FB1`/`FB2` 并在睡眠/唤醒转换时显式调用 `IOFramebuffer::handleEvent(fb, 3/4, (void *)1)`（消除唤醒绿屏与 `WindowServer` 120s Watchdog）；路由 `IGHardwareCommandStreamer5::resetOnWake()` 至 `hpCsResetOnWake`，在 `HWS_PGA` (`0x2080`) 非零时跳过硬件状态页清零并同步软件读指针 `*(cs + 0x1c04)`；
     - **Phase 10 `isRealTGL && Tahoe` 启用 `HP-BLITALIGN`、`HP-BLITFIX` 与 `HP-BLIT16`**：放宽 `blit2d_common_supported` / `blit2d_fast_supported` 的 64B 对齐检查，将软解 `420v` 32B 非 64B 对齐 `IOSurface` 平面（`Plane 0` 偏移 `0x20`、`Plane 1` 偏移 `0x1fe020` 或行距非对齐）路由至 `BCS0` `XY_SRC_COPY_BLT` 2D 拷贝（避免回退至 `RCS0` `Blit3D` 导致 `RGB(0, 136, 0)` 纯绿屏与 `RCS0` 停滞），并强制剩余 `Blit3D` 像素着色器使用 `SIMD16`，彻底根治 `420v` 视频播放绿屏与卡顿。

2. **一键交叉编译命令（使用 [build.py](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/build.py) 与 [offline-wrapper.py](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/build/offline-wrapper.py)）**：
   ```sh
   cd /srv/mac-for-elitebook
   # 验证源码与补丁 SHA256
   sha256sum \
     patches/nootedgreen-r32-pcfix35-blitalign-20261108.patch \
     .local/driver-repair-20261103/repair32-readback/source/src/NootedGreen/kern_gen11.cpp \
     .local/driver-repair-20261103/repair32-readback/source/src/NootedGreen/kern_green.cpp

   # 在 Nix 开发环境中执行交叉编译、$LD64_LLD 链接与 rcodesign 签名
   nix develop -c python3 .local/driver-repair-20261103/repair32-readback/build.py

   # 核验生成的 NootedGreen 二进制哈希 (应为 535,984 B, SHA256 ffa4b51e34ffbeb5aae68f55a8e79bc0794f7499c823b84ac58bde6057a96b15, LC_UUID 4C4C44C0-5555-3144-A178-618CB8A052CE)
   sha256sum .local/driver-repair-20261103/repair32-readback/build/snapshot/NootedGreen.kext/Contents/MacOS/NootedGreen
   ```

3. **底层 `$CLANG_APPLE` + `$LD64_LLD` + `rcodesign` 等价编译命令明细**：
   [offline-wrapper.py](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/build/offline-wrapper.py) 在内部对 `info.c`、[src/NootedGreen/](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/repair32-readback/source/src/NootedGreen) 下的 12 个 C++ 编译单元（`DisplayMergeNub.cpp`、`DYLDPatches.cpp`、`Firmware.cpp`、`FirmwareADLP.cpp`、`HDMI.cpp`、`IntelDPLinkTraining.cpp`、`kern_gen11.cpp`、`kern_genx.cpp`、`kern_green.cpp`、`kern_patcherplus.cpp`、`kern_start.cpp`、`kern_xepm.cpp`）及 `Lilu` 插件入口 `plugin_start.cpp` 执行的精确编译、链接与签名参数如下（仓库内亦归档了独立内核头文件与静态库副本 [.local/build-readiness/isolated/WhateverGreen/MacKernelSDK/](file:///srv/mac-for-elitebook/.local/build-readiness/isolated/WhateverGreen/MacKernelSDK) 与 [.local/build-readiness/isolated/WhateverGreen/Lilu.kext/Contents/Resources/](file:///srv/mac-for-elitebook/.local/build-readiness/isolated/WhateverGreen/Lilu.kext/Contents/Resources)）：
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

- **源码位置**：[.local/peripheral-prep-20261105/S0ixStandby-repo/](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo)（包含 [Makefile](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo/Makefile)、[S0ixStandby/S0ixStandby.cpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo/S0ixStandby/S0ixStandby.cpp) `46,144` B SHA256 `5a177cb6f5a3694c9cf1086f9cc4681f5a71c55f99c2eac113c70eade4e4f46a`、[S0ixStandby/S0ixGPU.cpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo/S0ixStandby/S0ixGPU.cpp) `23,777` B、[S0ixStandby/S0ixStandby.hpp](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo/S0ixStandby/S0ixStandby.hpp) `10,059` B SHA256 `05217538683a1594ea58ccaf977d76212ab85cad266724cad89d4fe38501ebed`、[S0ixStandby/kmod_info.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo/S0ixStandby/kmod_info.c) `733` B、[S0ixStandby/Info.plist](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo/S0ixStandby/Info.plist) 及诊断脚本 [macos/s0ix-status.sh](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo/macos/s0ix-status.sh)）。
- **重编译命令**（支持在 Linux 开发机通过 `nix develop` 交叉编译，或在 macOS 本机调用 [Makefile](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/S0ixStandby-repo/Makefile) 的 `SDK` / `COMMON` / `CXXFLAGS` / `CFLAGS` / `LDFLAGS` 构建）：
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

  # 核验已部署预备包二进制 SHA256 (应为 65,192 B, SHA256 a2baf7bddbb2768cfb53f4b7b991b36904d0730de2d96841489c6bdb25297ec3)
  sha256sum /srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/S0ixStandby.kext/Contents/MacOS/S0ixStandby
  ```

#### 3. `TGLDmic.kext` (`v0.5.0`) 与 `TGLDmic.driver` CoreAudio HAL 插件重编译流程

- **源码位置**：[.local/peripheral-prep-20261105/TGLDmic-repo/](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo)，分为内核驱动目录 [kext/](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/kext)（[kext/Makefile](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/kext/Makefile)）与用户态 CoreAudio AudioServerPlugIn 目录 [hal/](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/hal)（[hal/Makefile](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/TGLDmic-repo/hal/Makefile)）。
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
| **`SSDT-EC0-ITLB.aml`** | [SSDT-EC0-ITLB.dsl](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC0-ITLB.dsl)<br>`7,231` B<br>SHA256 `30dd9d79d501cb83cab902fe9acc3f46553ef6efafc5878641fe1174387186ed` | [SSDT-EC0-ITLB.aml](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC0-ITLB.aml)<br>`1,572` B<br>SHA256 `122a5b9d778c6429d32f73f1da7e695ba7498e6714e172f708b22894bd8ddaf8` | 配合 4 条 `Count=1` 精确重命名（`DSDT`: `ITLB\0 -> XTLB\0`；`NVTEC`: `EC12\0 -> XC12\0`、`EC13\0 -> XC13\0`；`DptfTabl`: `ODVP\x08 -> XDVP\x08`）+ 1 条 `ACPI -> Delete`（丢弃 `OemTableId="HP_XHC_P"` `TableLength=2362` 的 `SSDT13`），将 `ECEnabler` 挂载前（`t=1.93s`）访问的 4 个 16-bit EC 寄存器（`BDC`/`BFC`/`BDV`/`ACPR`）拆分为 8-bit 字节对，实现冷启动 **`0` 次 ACPI Error/Exception** 并完整走通 `ECRI -> ITLB -> SBTN -> PRIT` |
| **`SSDT-DEEPIDLE.aml`** | [SSDT-DEEPIDLE.dsl](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/SSDT-DEEPIDLE.dsl)<br>`2,333` B<br>SHA256 `f4faa4dc19ce4efd9bdc22436c9db1e8d03452faabc790b9c45620ef5dcd65e8` | [SSDT-DEEPIDLE.aml](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/SSDT-DEEPIDLE.aml)<br>`320` B<br>SHA256 `2161e6750a303ad7a23c8feeae5f2a5b68567aec7418e99f0a6c065afaa5a676` | 配合 `OemTableId="MS-SSDT"` 限定重命名 `14275F53544100 -> 14275853544100`（`PEPD._STA -> XSTA`, `Count=1`），在 Darwin 下注入 `\_SB.LPS0 = One`、`\_GPE.LXEN = One`、使 `\_SB.PEPD._STA` 置 `S0ID = One` 返回 `0x0F`，并为 `\_SB.LID` 与 `\_SB.SLPB` 注入 `_PRW`/`PRW0` (`Package (0x02) { 0x6E, 0x04 }`) 与 `_S0W` (`0x04`)，无需全局 `_OSI -> XOSI` 即可激活 `IOPMDeepIdleSupported = Yes`、`S0ixStandby.kext` 与 GPE `0x6E` S0ix Deep Idle 开盖即刻唤醒 |
| **`SSDT-PLUG.aml`** | [SSDT-PLUG.dsl](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-PLUG.dsl)<br>`1,355` B<br>SHA256 `b49fccae93979f77d61f34b3b0ed22920d93ac4ed87dfe73bdb42c2f9743654a` | [SSDT-PLUG.aml](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-PLUG.aml)<br>`113` B<br>SHA256 `24956a41669b37fce98f09b9b6d28475a099693bb3522391d35609415e0ffed2` | 在 `\_SB.PR00` 注入 `plugin-type = 1`，配合 `Cpuid1Data` 仿冒 `0x706E5` 挂载 `X86PlatformPlugin`（`39` 档 P-States） |
| **`SSDT-EC-USBX-HP.aml`** | [SSDT-EC-USBX-HP.dsl](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC-USBX-HP.dsl)<br>`2,602` B<br>SHA256 `6ef5245418774d2bb84c177065f6294eeac7d57cd6202866b0be5f0bda400b45` | [SSDT-EC-USBX-HP.aml](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC-USBX-HP.aml)<br>`372` B<br>SHA256 `296212e084666dfc9ed0ab69fbbecaaa3525da71f528526c2d22d0d81d7f6781` | 导出伪 `\_SB.PCI0.LPCB.EC` 与 `\_SB.USBX` USB 供电属性（`kUSBSleepPowerSupply = 5100`、`kUSBWakePowerSupply = 5100`） |
| **`SSDT-RHUB-HP.aml`** | [SSDT-RHUB-HP.dsl](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-RHUB-HP.dsl)<br>`1,050` B<br>SHA256 `6c0c75476502328fba31c6b77d8b144ac5dde53ed29eb3eea3fdaa33759c9498` | [SSDT-RHUB-HP.aml](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-RHUB-HP.aml)<br>`108` B<br>SHA256 `4cf78eacb8f2529a3a93a3bb9406ad4cc5446fe19828c49241130ab0503daec9` | 在 Darwin 下为 `\_SB.PC00.XHCI.RHUB` 注入 `_STA = 0`，强制 `AppleUSBXHCISPT` 直接从硬件寄存器枚举 PCH XHCI 端口 |
| **`SSDT-PNLF-HP-GA419.aml`** | [SSDT-PNLF-HP-GA419.dsl](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-PNLF-HP-GA419.dsl)<br>`1,297` B<br>SHA256 `a442ccf1ed4f563e691c0a96b1c431fc9c0b07314615f89af1c19a76ba980911` | [SSDT-PNLF-HP-GA419.aml](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-PNLF-HP-GA419.aml)<br>`142` B<br>SHA256 `72ec07163115d8c327f1c7f143b0375b7b0262adc9422c2628ab2177cc71414e` | 在 `\_SB.PC00.GFX0` 下注入 `PNLF` 背光设备（`_HID = "APP0002"`，`_UID = 0x13`） |
| **`SSDT-HP-Hotkeys.aml`** *(归档备查)* | [SSDT-HP-Hotkeys.dsl](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/brightness-fix-20261107/SSDT-HP-Hotkeys.dsl)<br>`3,389` B<br>SHA256 `a02df811c0ce77f01b0d5e9c6a4aecfec17fd432b3f08f802b0beb35d5d7e445` | [SSDT-HP-Hotkeys.aml](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/brightness-fix-20261107/SSDT-HP-Hotkeys.aml)<br>`692` B<br>SHA256 `ba463a93a38fd9a8b8a79850d4c9fab184f1603ff07b6ee8a555d220863577f8` | 早期 EC `_Q86`/`_Q87` 与 WMI `GVWE` 队列排空转 `PS2K` 通知实验表；因实机顶排 16 键已通过原生 `i8042` 扫描码 + `VoodooPS2Keyboard` `24` 条 `Custom ADB Map` 完整驱动，生产环境 `config.plist` 不加载此表 |

#### 从 `.dsl` 源码重编译全部 `.aml` 并执行 OpenCore `ocvalidate` 校验

```sh
cd /srv/mac-for-elitebook

# 1. 使用 nix develop 中的 iasl 编译器重编译全部 6 张生产环境 SSDT
nix develop -c iasl -ve \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC0-ITLB.dsl \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/SSDT-DEEPIDLE.dsl \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-PLUG.dsl \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC-USBX-HP.dsl \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-RHUB-HP.dsl \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-PNLF-HP-GA419.dsl

# 2. 校验生成的 .aml 二进制 SHA256
sha256sum \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC0-ITLB.aml \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/SSDT-DEEPIDLE.aml \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-PLUG.aml \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-EC-USBX-HP.aml \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-RHUB-HP.aml \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/subsystem-audit-3b5cd162/live-acpi/SSDT-PNLF-HP-GA419.aml

# 3. 使用与 OpenCore 1.0.8 版本严格匹配的 ocvalidate 校验 config.plist (应输出 No issues found.)
.local/opencore-1.0.8/Utilities/ocvalidate/ocvalidate.linux \
  .local/driver-repair-20261103/s0ix-standby-prep-20261107/config.plist
```

---

## 3. 用户态守护进程、Shim 与音频/背光/指纹辅助工具源码索引

本机型所有用户态组件均支持在本地 Linux 开发机通过 `nix develop`（使用 `$CLANG_APPLE` / `clang` + `ld64.lld` + `rcodesign` 配合本地轻量级 TBD 桩库目录 [.local/driver-repair-20261103/brightness-fix-20261107/stubs/](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/brightness-fix-20261107/stubs) 或 `$SDKROOT`）直接交叉编译，或在目标机 macOS 终端下使用系统 `clang` 编译。

#### 1. 用户态组件源码与部署路径总表

| 组件名称与目标机安装路径 | 源码文件、大小与 SHA256 | 预备产物路径与 SHA256 | 核心职责与运行机制 |
| --- | --- | --- | --- |
| **`libhp_cb_shim.dylib` / `hp-cb-shim.dylib`**<br>`/usr/local/lib/libhp_cb_shim.dylib`<br>`/usr/local/lib/hp-cb-shim.dylib` | [hp-cb-shim.m](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/brightness-fix-20261107/hp-cb-shim.m)<br>`19,545` B<br>SHA256 `14e276f659660bda1926e1b3b0f622c2f1fae87f2112f16142270fbfdf85327a` | [libhp_cb_shim.dylib](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/brightness-fix-20261107/libhp_cb_shim.dylib) / [hp-cb-shim.dylib](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-brightness-hotkeys/usr-local-lib/hp-cb-shim.dylib)<br>`35,456` B<br>SHA256 `e3b8378dc67e8ad9d19cdf5e025710660e73a6ce23885a82f910ac69b689b798` | 通过 Mach-O `__DATA,__interpose` 与 `CoreBrightness.framework` GOT 补丁拦截 `IODisplayCopyParameters` 与 `IODisplayGet/SetIntegerRangeParameter`，将 `corebrightnessd` 所需的 `"brightness"` / `"linear-brightness"` / `"usable-linear-brightness"` / `"commit"` 字典实时桥接至内核 `AppleBacklightDisplay` 的 `"bklt"` (`600..65535`)，恢复右上角控制中心与系统设置原生亮度滑块 |
| **`hp-cb-shim-loader.sh`**<br>`/usr/local/bin/hp-cb-shim-loader.sh`<br>守护配置：`/Library/LaunchDaemons/com.hp.cb-shim-loader.plist` | [hp-cb-shim-loader.sh](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/brightness-fix-20261107/hp-cb-shim-loader.sh)<br>`4,613` B<br>SHA256 `7c0473c54a6726bfde19e92e1641d9b2582a6d1acc4a8967ca611979ce153226`<br>Plist：[com.hp.cb-shim-loader.plist](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/brightness-fix-20261107/com.hp.cb-shim-loader.plist) (`602` B, SHA256 `7f7c0cb7d04c69c39aa2ed8eb9bef179c72d38daf7ab80e2767fcb7c5026350f`) | [stage3-brightness-hotkeys/usr-local-bin/hp-cb-shim-loader.sh](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-brightness-hotkeys/usr-local-bin/hp-cb-shim-loader.sh)<br>SHA256 `7c0473c54a6726bfde19e92e1641d9b2582a6d1acc4a8967ca611979ce153226` | 开机等待 `AppleBacklightDisplay` 与 `WindowServer` 就绪后，在 `/private/var/run/com.apple.corebrightnessd-shim.plist` 生成带 `DYLD_INSERT_LIBRARIES=/usr/local/lib/hp-cb-shim.dylib` 的服务定义并热切换原厂 `/usr/libexec/corebrightnessd`（保留 `CS_PLATFORM_BINARY`），规避 macOS 26 `/usr/local/lib` firmlink `Bootstrap failed: 5` 与 `PETRIFIED` 竞态 |
| **`hp-bridge`**<br>`/usr/local/bin/hp-bridge`<br>守护配置：`/Library/LaunchAgents/com.hp.bridge.agent.plist` | [hp-bridge.m](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/brightness-fix-20261107/hp-bridge.m)<br>`76,495` B<br>SHA256 `3944f83947599a58cea6968faab3ac6ff042046212bb2b6ce72bcb81f7d2a52f`<br>Plist：[com.hp.bridge.agent.plist](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/brightness-fix-20261107/com.hp.bridge.agent.plist) (`588` B, SHA256 `eb13a287fbf21187d4f7ce8ff377ee64eb9547038f29f7cdbd4d5278edbd6194`) | [hp-bridge](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/brightness-fix-20261107/hp-bridge) / [stage3-brightness-hotkeys/usr-local-bin/hp-bridge](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-brightness-hotkeys/usr-local-bin/hp-bridge)<br>`64,992` B<br>SHA256 `2dd080fbb738a1926c5cb06fb2ac60bdc6b05b3e2d2deea080ba1fa3f6ad8f69` | 用户态全功能热键、背光、音频与菜单栏常驻桥接守护进程：注册 11 项 Carbon 全局热键（无需 TCC 权限）与 `IOHIDManager` Consumer 监听，双向同步 `CoreDisplay` / `DisplayServices` 与硬件 `"bklt"` (`600..65535`)，驱动 `ALC285` AFG `0x01` GPIO `IO[2]` (`f5` 扬声器静音橙色 LED) 与 `IO[0]` (`f8` 麦克风静音橙色 LED)，并提供右上角菜单栏控制面板 |
| **`hp-brightness`**<br>`/usr/local/bin/hp-brightness` | 包装脚本：[hp-brightness](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-brightness-hotkeys/usr-local-bin/hp-brightness) (`449` B, SHA256 `8396b8330bd683e8d78c879df29d6c5db005f18a9f07481ac82fe0ff1bf5de6c`)<br>独立前身源码：[hp-brightness-daemon.m](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/brightness-fix-20261107/hp-brightness-daemon.m) (`35,403` B, SHA256 `0752fb097833423643061cc9c638e9dddcff71dcf73dec5b2742a1aa3ac17235`) | [stage3-brightness-hotkeys/usr-local-bin/hp-brightness](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-brightness-hotkeys/usr-local-bin/hp-brightness)<br>SHA256 `8396b8330bd683e8d78c879df29d6c5db005f18a9f07481ac82fe0ff1bf5de6c` | 命令行背光查询与调节入口（支持 `hp-brightness --get`、`hp-brightness --set <0.0..1.0>`、`hp-brightness --up/--down`、`hp-brightness --probe-ds`），转发至 `/usr/local/bin/hp-bridge` |
| **`hp-alc285-ampinit.sh`**<br>`/usr/local/bin/hp-alc285-ampinit.sh`<br>守护配置：`/Library/LaunchDaemons/com.hp.alc285.ampinit.plist` | [hp-alc285-ampinit.sh](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/wake-helper/hp-alc285-ampinit.sh)<br>`2,229` B<br>SHA256 `2c9056f67333717c5d21598a1f51c2f9d43d4b5717ddf3f985fd86932e2af41c`<br>（初始版：[hp-alc285-ampinit.sh](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/audio-ridgekey-fix-20261107/tgldmic-prep-20261107/hp-alc285-ampinit.sh) `1,312` B，SHA256 `430d584e7e4592588c040297e2185646240155cb8a27d57407e4ca80c2f169f9`）<br>Plist：[com.hp.alc285.ampinit.plist](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-audio/Library-LaunchDaemons/com.hp.alc285.ampinit.plist) (`606` B, SHA256 `7d964e9e6d9d1c5ddc267f92a056d80c6c9b7eb9f0027360c4afeee403090503`) | [stage3-audio/usr-local-bin/hp-alc285-ampinit.sh](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-audio/usr-local-bin/hp-alc285-ampinit.sh)<br>`2,229` B<br>SHA256 `2c9056f67333717c5d21598a1f51c2f9d43d4b5717ddf3f985fd86932e2af41c` | 开机或 S0ix 唤醒后等待 `ALCUserClientProvider` 就绪，下发 Bang & Olufsen 功放初始化动词（`0x20 SET_COEF_INDEX 0x65`、`SET_PROC_COEF 0x0000`）与 3.5mm 耳麦麦克风通路增益（`0x19`/`0x23`/`0x08`），并依次调用 `hp-select-speaker` 与 `hp-select-dmic.py` |
| **`hp-wake-helper`**<br>`/usr/local/bin/hp-wake-helper`<br>守护配置：`/Library/LaunchDaemons/com.hp.alc285.ampinit.plist` (`KeepAlive`) | [hp-wake-helper.m](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/wake-helper/hp-wake-helper.m)<br>`10,582` B<br>SHA256 `1974b8dbd5fdfe37d60be711c38a818c2dbbe20c863b7852260862c3c1ec74a6`<br>Plist：[com.hp.alc285.ampinit.plist](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/wake-helper/com.hp.alc285.ampinit.plist) (`606` B, SHA256 `7d964e9e6d9d1c5ddc267f92a056d80c6c9b7eb9f0027360c4afeee403090503`) | 本地构建：[hp-wake-helper](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/wake-helper/hp-wake-helper) / [stage3-audio/usr-local-bin/hp-wake-helper](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-audio/usr-local-bin/hp-wake-helper)<br>`31,376` B<br>SHA256 `712d422632c15355cb056a1c89b5f9c182421e96bc49cf866f33a855e84966bc` | S0ix 睡眠/唤醒常驻守护进程：监听 `IORegisterForSystemPower`（`kIOMessageSystemHasPoweredOn`）与 `AppleClamshellState`，开盖唤醒时自动声明用户活动唤醒屏幕、重运行 `/usr/local/bin/hp-alc285-ampinit.sh --wake` 恢复 `ALC285` B&O 功放与 `TGLDmic`，并在 `corebrightnessd` 未注入垫片时触发热重载 |
| **`hp-select-speaker`**<br>`/usr/local/bin/hp-select-speaker` | [hp-select-speaker.m](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/audio-ridgekey-fix-20261107/hp-select-speaker.m)<br>`4,354` B<br>SHA256 `550b57c570c55983c19137ed02e72af80bf42db226224c72bd62ab4b4718c95c` | [stage3-audio/usr-local-bin/hp-select-speaker](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-audio/usr-local-bin/hp-select-speaker)<br>`27,360` B<br>SHA256 `7badbe2d61eeaccf632ac2a84a580ae7572bd9bf1b3319f656a2367c3e10849a` | 枚举 CoreAudio `'dev#'` 列表，匹配 UID 含 `"1F,3,0,1,3"` 的 `Built-in Speaker` 并将其设为系统默认输出（`'dOut'`）与系统音效输出（`'sOut'`） |
| **`hp-select-dmic.py`**<br>`/usr/local/bin/hp-select-dmic.py` | [hp-select-dmic.py](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/audio-ridgekey-fix-20261107/tgldmic-prep-20261107/hp-select-dmic.py)<br>`2,513` B<br>SHA256 `c636d9cf2ce4c33ada6493801722f6e3b385db2a22f40883ee9491982c330f22` | [stage3-audio/usr-local-bin/hp-select-dmic.py](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-audio/usr-local-bin/hp-select-dmic.py)<br>SHA256 `c636d9cf2ce4c33ada6493801722f6e3b385db2a22f40883ee9491982c330f22` | 检测 `ioreg` 中 `TGLDmic` 激活后，通过 `ctypes` 调用 `AudioObjectSetPropertyData` 将 `TGLDmic_InternalMic_UID`（`Internal Microphone (TGLDmic)`）设为系统默认输入设备（`'dIn '`） |
| **`libxedrv.dylib`**<br>`/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib` | [libxedrv.m](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/vt-audio-fix-20261106/libxedrv.m)<br>`51,712` B<br>SHA256 `ea4b9ec3c14a902863c1ce41fc3a6e40c54eb350d747833ad702087a69429406` | 本地构建：[libxedrv.dylib](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/vt-audio-fix-20261106/libxedrv.dylib) (`65,280` B, SHA256 `312ecf603a27526df87417980fd64fddd2d51e16754aa5deff8a1deeb76226b2`)<br>安装套件同步版：[libxedrv.dylib](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage2-gpu/Library-GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle/Contents/MacOS/libxedrv.dylib) (`65,280` B, SHA256 `312ecf603a27526df87417980fd64fddd2d51e16754aa5deff8a1deeb76226b2`) | 注入 `AppleIntelTGLGraphicsMTLDriver`（`16.0.32`）的 Metal ABI 适配层（`xedrv17`）：转换 Tahoe `MTLRenderPipelineDescriptorPrivate` 结构体偏移与 `misc` 位域，重写 `newTextureViewWithPixelFormat:` 避免 `RCS0` `fmt=123` Blit3D 挂死，配合内核 `HP-BLITALIGN`/`HP-BLITFIX`/`HP-BLIT16` 处理 `420v` 纹理视图，并在 `VTDecoderXPCService` 中安全返回 `nil`（不提前调用 `[self release]` 且默认不写 `/tmp/xedrv-*.log` 防止沙盒拒绝与 `SIGSEGV`） |
| **`va` (`AppleIntelTGLGraphicsVADriver.bundle` 补丁脚本)** | 自包含安装脚本：[.local/driver-repair-20261103/vadriver-build/va](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/vadriver-build/va) (`7,242` B, SHA256 `2f373a56d389a80ba4056d162dd15327c2baec225a740097f2c7ecc7d465e559`)<br>模块化补丁脚本集：[.local/clean-upstream-20261102/source/macos/vadriver/](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/source/macos/vadriver) ([build-vadriver.sh](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/source/macos/vadriver/build-vadriver.sh) `3,369` B, SHA256 `1e4ca0a8d0980670f6801c991a65440c02a50580655c8e4fee4745806482562f`)<br>回执：[deploy-receipt.json](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/vadriver-build/deploy-receipt.json) | 原版未修补：[AppleIntelTGLGraphicsVADriver](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/build/install-stage/sle/AppleIntelTGLGraphicsVADriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsVADriver) (`8,450,544` B, SHA256 `d265f2038135c2c5c3649b621d9aea48cf1cb74a1fb36069bb1b3562b3750129`)<br>补丁后未签名 SHA256：`b4ab647b23e448d6835e069a60cd4bd174865b01fcdbf67d27ef703e149fb7c0`<br>本地签名版：[AppleIntelTGLGraphicsVADriver](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/vadriver-build/AppleIntelTGLGraphicsVADriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsVADriver) (`8,450,368` B, SHA256 `cb82639fb7b6af838d36e70a7bfc83bb9cc17ae87cf56e15752594c1104c659b`)<br>安装套件重签名版：[AppleIntelTGLGraphicsVADriver](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage2-gpu/Library-GPUBundles/AppleIntelTGLGraphicsVADriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsVADriver) (`8,463,472` B, SHA256 `6291f574afa064ed2dd56f6787cd92bcf79750b16cc13ef6d07a49e599934dff`) | 对 Big Sur 11.4 原版 `AppleIntelTGLGraphicsVADriver`（`16.0.32`）依次应用 8 个 Python 机器码修补脚本（修复 Tahoe 80B/88B Surface Node 布局、Pitch/Height/Offset、HCP_SURFACE_STATE 与 HEVC Last Slice 等），签名并部署至 `/Library/GPUBundles/` |
| **`RidgeKey` (`06cb:00f0` 指纹认证套件)**<br>`/usr/local/ridgekey/` & `/Applications/RidgeKey.app` | 源码仓库：[.local/peripheral-prep-20261105/RidgeKey-repo/](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo) (HEAD commit `4968672`；预编译发行包 [BUILDINFO.txt](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-ridgekey/usr-local-ridgekey/BUILDINFO.txt) CI commit `dcd9e47`)<br>构建定义：[src/meson.build](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/src/meson.build) (`3,215` B)、[app/Package.swift](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/app/Package.swift)、[scripts/build-app.sh](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/scripts/build-app.sh)、[scripts/build-pkg.sh](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/scripts/build-pkg.sh)、[scripts/install.sh](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/scripts/install.sh)<br>防全擦除补丁：[patches/libfprint/](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/patches/libfprint) | 安装套件目录：[stage3-ridgekey/](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-ridgekey)<br>[ridgekeyd](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-ridgekey/usr-local-ridgekey/bin/ridgekeyd) (SHA256 `f20da2a091aef6d65feaa55b3501c246d364d9b54ff78e723b7a0a50201cc6f4`)<br>[ridgekeyctl](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-ridgekey/usr-local-ridgekey/bin/ridgekeyctl) (SHA256 `6577e8d3260d24b30372cc66497d77ff112a8175fddfa82c64bdc0d5e8a5a4e3`) | 基于 `libfprint-2` 的用户态 Synaptics `06cb:00f0` Match-On-Chip 指纹守护进程（`ridgekeyd`）、CLI（`ridgekeyctl`）、`sudo` PAM 模块（`pam_ridgekey.so`）、锁屏代理（`RidgeKeyAgent.app`）、管理员授权插件（`RidgeKey.bundle`）与 SwiftUI 管理应用（`RidgeKey.app`） |

#### 2. 背光、热键、音频与 Metal 垫片本地交叉编译命令（`nix develop`）

在 `/srv/mac-for-elitebook` 下，使用 `nix develop` 与本地桩库目录 [.local/driver-repair-20261103/brightness-fix-20261107/stubs/](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/brightness-fix-20261107/stubs) 即可直接从 `.m` 源码交叉编译并签名 `libhp_cb_shim.dylib`、`hp-bridge`、`hp-select-speaker` 与 `libxedrv.dylib`（其中 `libhp_cb_shim.dylib` 与 `hp-bridge` 在本地构建后产生与仓库预备产物 **逐字节完全一致** 的 SHA256）：

```sh
cd /srv/mac-for-elitebook
STUBS=".local/driver-repair-20261103/brightness-fix-20261107/stubs"

# 1. 编译并签名 corebrightnessd 动态注入库 libhp_cb_shim.dylib (hp-cb-shim.m)
# 精确复现 35,456 B 与 SHA256 e3b8378dc67e8ad9d19cdf5e025710660e73a6ce23885a82f910ac69b689b798
nix develop -c bash -c "
  clang -target x86_64-apple-macos13.0 -O2 -fPIC -c \
    .local/driver-repair-20261103/brightness-fix-20261107/hp-cb-shim.m \
    -o .local/driver-repair-20261103/brightness-fix-20261107/hp-cb-shim.o
  ld64.lld -dylib -arch x86_64 -platform_version macos 13.0 13.0 \
    -install_name /usr/local/lib/libhp_cb_shim.dylib \
    .local/driver-repair-20261103/brightness-fix-20261107/hp-cb-shim.o \
    \"$STUBS/libSystem.tbd\" \"$STUBS/CoreFoundation.tbd\" \
    \"$STUBS/IOKit.tbd\" \"$STUBS/CoreDisplay.tbd\" \
    -o .local/driver-repair-20261103/brightness-fix-20261107/libhp_cb_shim.dylib
  rcodesign sign .local/driver-repair-20261103/brightness-fix-20261107/libhp_cb_shim.dylib
"

# 2. 编译并签名全功能热键/背光/音频守护进程 hp-bridge (hp-bridge.m，必须启用 -fobjc-arc)
# 精确复现 64,992 B 与 SHA256 2dd080fbb738a1926c5cb06fb2ac60bdc6b05b3e2d2deea080ba1fa3f6ad8f69
nix develop -c bash -c "
  clang -target x86_64-apple-macos12.0 -O2 -fobjc-arc -c \
    .local/driver-repair-20261103/brightness-fix-20261107/hp-bridge.m \
    -o .local/driver-repair-20261103/brightness-fix-20261107/hp-bridge.o
  ld64.lld -arch x86_64 -platform_version macos 12.0 12.0 \
    .local/driver-repair-20261103/brightness-fix-20261107/hp-bridge.o \
    \"$STUBS/libSystem.tbd\" \"$STUBS/libobjc.tbd\" \"$STUBS/CoreFoundation.tbd\" \
    \"$STUBS/Foundation.tbd\" \"$STUBS/AppKit.tbd\" \"$STUBS/CoreGraphics.tbd\" \
    \"$STUBS/IOKit.tbd\" \"$STUBS/CoreAudio.tbd\" \"$STUBS/Carbon.tbd\" \
    \"$STUBS/CoreDisplay.tbd\" \"$STUBS/DisplayServices.tbd\" \
    -o .local/driver-repair-20261103/brightness-fix-20261107/hp-bridge
  rcodesign sign .local/driver-repair-20261103/brightness-fix-20261107/hp-bridge
"

# 3. 编译并签名扬声器默认输出切换工具 hp-select-speaker (hp-select-speaker.m)
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

# 4. 交叉编译并签名 Metal ABI 适配层 libxedrv.dylib (libxedrv.m，必须使用 -fno-objc-arc)
nix develop -c bash -c '
  "$CLANG_APPLE" -target x86_64-apple-macos13.0 -isysroot "$SDKROOT" \
    -O2 -fPIC -fno-objc-arc -c \
    .local/driver-repair-20261103/vt-audio-fix-20261106/libxedrv.m \
    -o /tmp/libxedrv.o
  "$LD64_LLD" -dylib -arch x86_64 -platform_version macos 13.0 13.0 -syslibroot "$SDKROOT" \
    -install_name @loader_path/libxedrv.dylib \
    /tmp/libxedrv.o -lSystem -lobjc -framework Foundation -framework Metal -framework IOKit \
    -o /tmp/libxedrv.dylib
  rcodesign sign /tmp/libxedrv.dylib
  rm -f /tmp/libxedrv.o /tmp/libxedrv.dylib
'
```

> [!TIP] **在目标机 macOS 原生编译等价命令**
> 若在目标机 macOS 终端（已安装 Xcode Command Line Tools）直接编译上述工具，可使用系统框架直接编译签名：
> ```sh
> clang -dynamiclib -O2 -arch x86_64 -mmacosx-version-min=13.0 \
>   -install_name /usr/local/lib/libhp_cb_shim.dylib \
>   -framework CoreFoundation -framework IOKit -F/System/Library/Frameworks -framework CoreDisplay \
>   hp-cb-shim.m -o libhp_cb_shim.dylib && codesign -f -s - libhp_cb_shim.dylib
>
> clang -O2 -fobjc-arc -arch x86_64 -mmacosx-version-min=12.0 \
>   -framework Cocoa -framework Carbon -framework CoreAudio -framework CoreFoundation \
>   -framework CoreGraphics -framework IOKit -F/System/Library/PrivateFrameworks \
>   -framework CoreDisplay -framework DisplayServices \
>   hp-bridge.m -o hp-bridge && codesign -f -s - hp-bridge
>
> clang -O2 -arch x86_64 -mmacosx-version-min=13.0 \
>   -framework CoreAudio -framework CoreFoundation \
>   hp-select-speaker.m -o hp-select-speaker && codesign -f -s - hp-select-speaker
>
> clang -dynamiclib -O2 -fno-objc-arc -arch x86_64 -mmacosx-version-min=13.0 \
>   -install_name @loader_path/libxedrv.dylib \
>   -framework Foundation -framework Metal -framework IOKit \
>   libxedrv.m -o libxedrv.dylib && codesign -f -s - libxedrv.dylib
> ```

#### 3. `AppleIntelTGLGraphicsVADriver.bundle` 8 个模块化修补脚本与自包含脚本（[va](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/vadriver-build/va)）技术明细

上游模块化补丁脚本集位于 [.local/clean-upstream-20261102/source/macos/vadriver/](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/source/macos/vadriver)（主控构建脚本 [build-vadriver.sh](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/source/macos/vadriver/build-vadriver.sh)，`3,369` B，SHA256 `1e4ca0a8d0980670f6801c991a65440c02a50580655c8e4fee4745806482562f`），而 [.local/driver-repair-20261103/vadriver-build/va](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/vadriver-build/va)（`7,242` B，SHA256 `2f373a56d389a80ba4056d162dd15327c2baec225a740097f2c7ecc7d465e559`）将这 **8 个 Python 机器码修补阶段**合并为单文件自包含脚本。对 Big Sur 11.4 移植版原版 [AppleIntelTGLGraphicsVADriver](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/build/install-stage/sle/AppleIntelTGLGraphicsVADriver.bundle/Contents/MacOS/AppleIntelTGLGraphicsVADriver)（`8,450,544` B，未修补 SHA256 `d265f2038135c2c5c3649b621d9aea48cf1cb74a1fb36069bb1b3562b3750129`）依次执行以下 8 项修补后，确定性产出未签名 SHA256 `b4ab647b23e448d6835e069a60cd4bd174865b01fcdbf67d27ef703e149fb7c0`（本地 `codesign` 签名版 SHA256 `cb82639fb7b6af838d36e70a7bfc83bb9cc17ae87cf56e15752594c1104c659b`）：

1. **[`patch-vadriver.py`](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/source/macos/vadriver/patch-vadriver.py)**（`1,832` B，SHA256 `1f7736935da713295aafd1a47046f0e0c9b53524103bbea37413de2ccb5020f2`）：
   - `0x130aa` (`CreateDriverContext` 清理分支)：`e8 e3 d0 4d 00` -> `90 90 90 90 90`（NOP 掉清理分支中因 Tahoe 结构体布局变化导致崩溃的 `vtable+0x30` 调用）；
   - `0x13172` (`CreateContext` 版本号检查)：`0f 85 17 01 00 00` -> `90 90 90 90 90 90`（移除 `ctx+0x8 == 0x201` 版本强校验，兼容 Tahoe AppleGVA 传入的 `0x202`）；
   - `0x15456` (`CodecHalDecodeCreate` 分配失败检查)：`74 61` -> `90 90`（当 `0x2b8` 处为空时继续执行而非直接中止）；
   - `0x1545c` (`CodecHalDecodeCreate` 返回值覆写)：`e8 e9 4e 4b 00 41 89 c6` -> `31 f6 90 90 90 90 90 90`（强制 `r14d = 0` 返回成功）；
   - `0x1623c` (`DestroyContext`)：`48 8b 07 ff 50 20` -> `90 90 90 90 90 90`（当 Decoder 对象为空时跳过 `vtable+0x20` 析构调用）。
2. **[`patch_nodes.py`](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/source/macos/vadriver/patch_nodes.py)**（`2,784` B，SHA256 `1082da6644052bf3616dc9d964a508da03c7605e9a2c039f14b4d0edeaf22f4f`）：
   - `0x24361f` & `0x24364f`：将两处 `80 7c 08 58 00`（检查 88B 步长的 `[rax+rcx+0x58]` 字节）修补为 `80 3c 08 00 90`（检查 `[rax+rcx+0x00]` 处的 surface node ID），并配合后续步长修补适配 Tahoe AppleGVA 的 80B Surface Node。
3. **[`patch_nodelayout.py`](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/source/macos/vadriver/patch_nodelayout.py)**（`9,138` B，SHA256 `34a99cd183039dfd4fe33001902e0ea6aeacca1b4643501ed56c35abe262e612`）：
   - `0x2bbe7`：将 `add rcx, 0x58`（88B 步长）改为 `add rcx, 0x50`（80B 步长）；
   - `0x2bc7e .. 0x2be1b`：在 `GetSurfaceInfo` 中重写 11 处 `imul reg, reg, 0x58` 为 `0x50`，并将旧 88B Node 偏移 `+0x1a`/`+0x18`/`+0x08` 重映射至 Tahoe 80B Node 的 `+0x08` (width) / `+0x0a` (height) / `+0x10` (bo_ptr)。
4. **[`patch_payloadhdr.py`](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/source/macos/vadriver/patch_payloadhdr.py)**（`1,419` B，SHA256 `680fa20e0d6be7b63eb2b18e4e5682c35695913f063ac2c8a67c302ad57c8d0b`）：
   - 在 `__TEXT` 头部空洞写入三段跳板机器码：`0x0d00`（`GetSurfaceInfo` 入口转换器：将 Tahoe 88B 新式 Node 头部 `hdr == 0x00010002` 原地转换为 Big Sur 驱动期望的字段布局）、`0x0b00`（`os_resource` 对象填充器）、`0x1100`（`gmm_res_info` 伪对象构造器，使 `[gmm+0x120]` 返回 TileY `1`、vtable 槽位返回有效对齐与尺寸），并将 `0x2bb2a` 重定向至 `0x0d00`。
5. **[`patch_pitchdelta.py`](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/source/macos/vadriver/patch_pitchdelta.py)**（`2,414` B，SHA256 `35bdcbf2c2266a96ff020fc2b3fe9de99edc8db9e9b93ba2d27370dc73a75c2d`）：
   - 在 `0x0e00` 注入 `SendSurfaceState` 循环前置修正跳板（当 `os_res+0x28` 的 pitch/height/Y-offset 为 `0` 时，从 `frame_desc` 动态回填对齐后的 pitch、height 及 UV 平面偏移 `aligned_h`），并将 `0x6453c` 跳转至 `0x0e00`、在 `0x64a15` 将 `lea r8, [r15+rax*8]` 修补为 `mov r8, r15; nop`。
6. **[`patch_spsshift.py`](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/source/macos/vadriver/patch_spsshift.py)**（`1,729` B，SHA256 `e6f1f7950d9ac10f1c60397a56301f650527d7d7dac9da27055359a691f3b92a`）：
   - 修复 Tahoe AppleGVA HEVC SPS 参数缓冲区偏移右移 `+4` 字节的 ABI 差异：在 `0x228e3f` 注入 `add r12, 4`（跳转至 `0x0f00` 跳板并在 `0x193543` 挂载），并在 `0x229740`（PicWidth/PicHeight 读取）与 `0x229655`（ChromaFormat 读取）同步修正 `+4` 偏移。
7. **[`patch_hcpsurface.py`](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/source/macos/vadriver/patch_hcpsurface.py)**（`2,202` B，SHA256 `7f6dc846ad86a73c0c375824084e6545c74674e0e12b3a906bc1f0f392ca0491`）：
   - 在 `0x0f00` 写入 `AddHcpSurfaceCmd` 跳板（当 `[rcx+0x10]` 处的 `YPlaneOffset.iYOffset == 0` 时，自动从 `params+0x08` 读取 `recon_surface` 的高度补齐 UV 偏移，防止 `HCP_SURFACE_STATE` DW2 全零导致色度平面与亮度平面重叠绿屏）。
8. **[`patch_hevclastslice.py`](file:///srv/mac-for-elitebook/.local/clean-upstream-20261102/source/macos/vadriver/patch_hevclastslice.py)**（`2,704` B，SHA256 `761f298ba1bd634bc1e97b4e2ac1a6d508c6d32902036df4659bf3201444fc10`）：
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

- **源码树**：[.local/peripheral-prep-20261105/RidgeKey-repo/](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo)（上游 `labrouss/RidgeKey` `v1.0.0`，本地仓库 HEAD commit `4968672`；安装套件预编译产物见 [BUILDINFO.txt](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/stage3-ridgekey/usr-local-ridgekey/BUILDINFO.txt)，对应上游 CI commit `dcd9e47`）：
  - **C 守护进程与安全插件（Meson 构建系统，[src/meson.build](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/src/meson.build)）**：
    - `ridgekeyd` 根守护进程：[src/daemon/ridgekeyd.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/src/daemon/ridgekeyd.c)、[store.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/src/daemon/store.c)、[secret.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/src/daemon/secret.c)、[console.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/src/daemon/console.c)、[peer.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/src/daemon/peer.c)、[prompt.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/src/daemon/prompt.c)、[actions.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/src/daemon/actions.c)（依赖 `libfprint-2`、`glib-2.0`、`gio-2.0`）；
    - `ridgekeyctl` 命令行客户端：[src/ctl/ridgekeyctl.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/src/ctl/ridgekeyctl.c)（仅依赖 macOS 系统 SDK XPC + `libdispatch`）；
    - `pam_ridgekey.so`（`sudo` PAM 模块）：[src/pam/pam_ridgekey.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/src/pam/pam_ridgekey.c)（依赖 `libpam` + `CoreFoundation`）；
    - `ridgekey-agent`（`RidgeKeyAgent.app` 锁屏解锁代理）：[src/agent/ridgekey-agent.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/src/agent/ridgekey-agent.c)（依赖 `CoreFoundation`、`CoreGraphics`、`Security`、`ApplicationServices`）；
    - `RidgeKey.bundle`（`authorizationhost` 管理员弹窗插件）：[src/authplugin/ridgekey-authplugin.c](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/src/authplugin/ridgekey-authplugin.c)（依赖 `Security`、`CoreFoundation`）。
  - **SwiftUI 设置应用（`RidgeKey.app`）**：[app/Package.swift](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/app/Package.swift) 与 [scripts/build-app.sh](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/scripts/build-app.sh)。
  - **`libfprint` 安全补丁**：[patches/libfprint/](file:///srv/mac-for-elitebook/.local/peripheral-prep-20261105/RidgeKey-repo/patches/libfprint)（移除全传感器擦除指令，保护同芯片存储的 Windows Hello 与 BIOS 指纹）。
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
      /tmp/rk-build/ridgekey-agent.o -framework CoreFoundation -framework CoreGraphics \
      -framework Security -framework ApplicationServices -framework SkyLight -lSystem \
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
| **`HP-Tahoe-PostInstall-20261108.tar.gz`** | 本地：[`.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108.tar.gz`](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108.tar.gz)<br>内置盘预置：`/Volumes/系统/hpdiag/HP-Tahoe-PostInstall-20261108.tar.gz`（NixOS `/mnt/win_sys/hpdiag/HP-Tahoe-PostInstall-20261108.tar.gz`） | `125,550,064` B（约 `120 MB`），SHA256 `c432d2cfbb7438781b7b0943a9950c315fd95ff97e1990a633960c5de7c12ccd` |
| **`SHA256SUMS.txt`** | [`.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/SHA256SUMS.txt`](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/SHA256SUMS.txt) | `63,835` B（`426` 个打包文件），SHA256 `70eb00d42712a404b3ea515079eaafe56400608810327e3b9926d5ff35dd9ff9` |
| **`bundle-receipt.json`** | [`.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/bundle-receipt.json`](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/bundle-receipt.json) | `3,541` B，SHA256 `2d4ca54bd58ea790f912f7e8ce0d960444f25201e165b8106be4c01367cf9f79` |
| **`verify-postinstall.sh` / `verify-phase10-lidwake-and-video.sh` / `test_420v_blitalign`** | [`.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108/`](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/postinstall-bundle-20261108/HP-Tahoe-PostInstall-20261108) | `verify-postinstall.sh`：`8,017` B，SHA256 `93ec78c817797fbcdb15a29b0b5c4837e8e2fdb0fbab571e8fb31a2ff964e107`<br>`verify-phase10-lidwake-and-video.sh`：`7,639` B，SHA256 `eeebfac56d8e79b59fc42db33e3672112d9eeb8bf136148018ac5024762ea218`<br>`test_420v_blitalign`：`51,680` B，SHA256 `887743ebd0b11797fa46553fa2420df21adf266c76ce6d0d540ac51e415e75bf` |
| **`HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`** | [`.local/driver-repair-20261103/s0ix-standby-prep-20261107/HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img`](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/HP-UPSTREAM-6F03560-REPAIR32-PCFIX33-S0IX-RECOVERY.img)（FAT32 偏移 `@@1048576`） | `1,343,225,856` B（`1.25 GiB`），SHA256 `7493cb368147bd5cd6ec94e88b08c65acfe206e495a5fcfa16bd34706f18aa98` |
| **`after-lidwake-greenfix-boot-oc.tar`** | [`.local/driver-repair-20261103/s0ix-standby-prep-20261107/post-wake-ebaba2ee/after-lidwake-greenfix-boot-oc.tar`](file:///srv/mac-for-elitebook/.local/driver-repair-20261103/s0ix-standby-prep-20261107/post-wake-ebaba2ee/after-lidwake-greenfix-boot-oc.tar)（内置盘 `/boot/EFI/OC` 回读归档） | SHA256 `67bf46b0945e58f3a86e21ff27a01743de60a718a29d747670d5f74f66a21061` |

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
