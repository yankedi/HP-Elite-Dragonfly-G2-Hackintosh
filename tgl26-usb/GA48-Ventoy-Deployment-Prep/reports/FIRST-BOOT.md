# 首次启动诊断清单（待单独授权，不在本轮执行）

> GA49补充的真实安装前提和Caches纠错见 [GA49-CORRECTION](GA49-CORRECTION.md)；原IMG和本清单的逐层启动原则保持，未进行首启。

## 使用 GA48 之前

- [ ] 当前HP/25G83状态重新确认，GA48/原包/VESA SHA与交付一致。
- [ ] staging原生签名/资源seal/entitlement、加载信任和完整依赖解析通过，有原始日志。
- [ ] HookCase、TGL FB/accelerator、全部userland与xe.bundle按精确布局就位。
- [ ] KC注册全部rc0，inspect显示正确依赖和版本；KDK、active Preboot状态有证据。
- [ ] 安全策略/SSV/签名方案得到精确单独批准；没有自动照抄上游A13或AMFI。
- [ ] 原系统文件、AuxKC/Preboot、安全状态已备份且Recovery可读取；逆向步骤可执行。
- [ ] 独立VESA可选；用户知道回到原Ventoy菜单，不选择GA32b Hang。
- [ ] 用户批准本次物理启动和boot-args Delete/Add；不改内部EFI、默认启动项，不自动重启。

**当前以上加载/安装前提尚未满足，所以本轮不进入首启。**

## 授权后依次观察，失败即停

1. OpenCore自身日志：加载的配置/镜像确为GA48，Lilu先于NG，WhateverGreen不再加载。
   确认有效boot-args无 `-igfxvesa`、无ICL spoof/Hang/ADLP参数，默认有 `-ngreennoplanesfix`。
2. PCI/IORegistry：IGPU vendor8086/device9A49、native `isRealTGL=1`，没有8A5A伪装。
3. `kmutil showloaded`/原生日志：NG、HookCase、AppleTGLGraphicsFramebuffer、AppleTGLGraphics及其provider正确。
   仅NG出现或仅7MB/VESA不算加载成功。当前真实bundle IDs见PACKAGE.json。
4. framebuffer/accelerator绑定、eDP画面与SSH：检查panic/黑屏/补丁未命中。
   FMT、VALD及其他ABI依然未验证；默认PLANES2应未应用，不能看到未日志就假定安全。
5. 只有kernel层成立后，另批原生MetalDevice查询；记录实际MTLDriver、libxedrv及共享库加载路径。
6. 再另批最小ShaderCompile：捕获SerializedBitcode→WithOptions、TGLLP IGC、LLVM32023路径、
   真实request/reply与诊断。遇3802/3902加载失败如实定位，不删上游组件或转GA46隔离版。
7. 编译真实成功后再另批最小GPU工作：单个可验证结果、完成状态、超时边界；不直接跑桌面压力测试。
8. 无画面、panic、hang、编译桥失败：本次立即结束，保存日志，用户选择独立VESA/Recovery并按逆向计划恢复。
   不自动切full-PLANES2候选，不自动重启重试，不把“设备枚举成功”当Metal可用。

每层记录系统build/当前安全状态/镜像与包hash/命令rc/日志时间。原生只读状态查询不等于允许新GPU程序执行。
