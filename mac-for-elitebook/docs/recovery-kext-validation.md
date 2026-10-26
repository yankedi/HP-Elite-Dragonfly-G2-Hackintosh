# 无安装 Recovery / XNU / kext 验证

## 已解决的下载阻塞与准确系统输入

之前记录的 1 MiB 截断不是本路线的最终结论。重新取得 Apple Recovery
session 与 AssetToken 后，开放结尾的 `Range: bytes=1048576-` 实际返回
**959,481,745 bytes**，与原先的 1,048,576-byte 前缀拼接后得到
**960,530,321-byte** 完整 DMG。没有关闭 HTTPS 证书校验。

- Apple 产品号：`140-93589`。
- `BaseSystem.dmg` SHA-256：`edddd0d5869caaa12e29e6996a04f11590280580976a119dbd42c24fa62fe18e`。
- `BaseSystem.chunklist` SHA-256：`06f7c498f856341f467ba1faedf2717fb2c172ae0aff4658a1467cbf46b711f9`。
- OpenCore 1.0.8 原始 `macrecovery.py`：Apple RSA 签名及 **92/92** 个分块通过，
  没有额外尾部数据；已有诊断脚本也再次验证通过，签名篡改反例仍拒绝。
- 镜像内 `System/Library/CoreServices/SystemVersion.plist`：
  **macOS 26.6.2 / 25G83**；不是从镜像下载名称猜测版本。
- `BootKernelExtensions.kc`：67,584,000 bytes，SHA-256
  `c80161fa3065883753fc285339281361a8469cbb6fb27653c88e2a22eb4807a4`。
- KC 与实际启动日志的 Darwin 版本一致：**25.6.0**，
  `xnu-12377.161.14~5/RELEASE_X86_64`。

提取使用 7zz **26.04**，binary SHA-256 为
`3e3a0fa5d764701c81076b1574012b7ecb1563b24439d548eb5da498e6875d6f`；
本地包 NAR / binary pin 见 `.local/recovery-repair/extraction-toolchain.json`。

这是本轮 VM 的独立输入，既有 HP 适配候选 `26.6 / 25G72` 没有被自动替换。
源码、系统 build、SDK build 也不能互相替代：booter 的 SDK build 为 `25G74`，
实际 SystemVersion / `kern.osversion` 才是这里的 `25G83`。

用户允许官方源失败时走镜像。已找到
[Recovery Collection](https://github.com/A11pwnX/MacOS-Recovery-Collection)
链接的共享恢复镜像目录，及 Archive.org 的 Tahoe 26.3 ISO 条目；没有把它们的
标题当成已验证输入，也没有下载完整第三方 ISO。官方续传已成功，因此本轮实测
使用上述签名通过的 Apple DMG。复现下载器也支持镜像 URL，仍要求同一 Apple
签名验证；镜像路线未作为本轮系统启动输入。

## 实际启动中发现并修复的问题

1. **虚拟 CPU stepping**：仅 UEFI 探针可用的
   `Haswell-noTSX,-pcid,-tsc-deadline,-invpcid` 不足以启动 XNU。
   原始默认 stepping 在内核早期进入
   `Haswell pre-C0 steppings are not supported @machine_check.c:97` 路径。
   通过 QMP 读取 guest 栈和字符串确认，修改的是虚拟 CPU 的 `stepping=3`。
2. **选错 Apple booter**：将 `usr/standalone/i386/boot.efi` 强制设为
   BlessOverride，虽进入 XNU 并挂载 HFS 根卷，却按普通 local 系统尝试 preboot，
   后续 dyld shared cache 加载失败并触发 `initproc failed to start`。
   删除该 override，自动选中 BaseSystem 的
   `System/Library/CoreServices/boot.efi`（日志标识 **bootbase.efi**）后，
   实际进入 BaseSystem 单用户 shell。
3. **DMG 与 raw 的区别**：`com.apple.recovery.boot/BaseSystem.dmg` 配合原始
   chunklist、`DmgLoading=Signed` 也实际越过 booter 进入 XNU；TCG 下 KC 读取约
   208 秒。快速组件对照使用签名验证后的 DMG 经 `qemu-img convert -f dmg -O raw`
   转换的独立可抛弃文件，仍自动选择 CoreServices bootbase；不是安装一个系统。
4. **加载列表不等于插件启用**：首次 `-s` 实验中，`kextstat` 同时列出
   Lilu、VirtualSMC 与 patched WhateverGreen，但 Lilu 明确报告
   `found a disabling argument or no arguments, exiting`，WEG 报告
   `failed to call parent 7`。固定 Lilu 源码的 `getBootArguments()` 明确在
   `-s` 时默认禁用，需文档规定的 **`-liluforce`** 覆盖。
   因而这个实验保留为“已加载、插件未正常启用”的真实反例。

这些修正仅用于独立 VM profile。没有给 HP 增加 CPU stepping/虚拟设备配置。

## 实际 kext 加载与初始化观察

下表每个实验都从独立 OVMF VARS、FAT EFI 文件和完整 Recovery 派生的 raw
文件启动；**6/6 到达 BaseSystem 单用户 shell**，在 guest 内完成 `uname -a`、
`sw_vers`、`kextstat -l`（实际调用 `kmutil showloaded --list-only`）、
三个 `ioreg` 查询和 `sysctl kern.bootargs`，无 panic。六次配置的 OpenCore 1.0.8
`ocvalidate` 均为 0。VM 已通过 QMP 退出；退出本身没有被当作加载成功。
所选串口配置下，VGA 截图停留在早期 XNU 输出，后续 shell 与系统命令的证据来自
实际串口交互；不把这张静止截图当作内核卡死或 Recovery 图形界面成功。

| 私有 run | Lilu | WEG | vCPU | guest 已加载列表 | VirtualSMC 初始化诊断 / AppleSMC 接口 |
| --- | --- | --- | --- | --- | --- |
| `run-rprc0lvt` | DEBUG 1.7.2 | patched 1.7.1 | 2 | 三者均存在 | 无 parent 错误，Generation 2 / MMIO |
| `run-npi57lq6` | DEBUG 1.7.2 | stock 1.7.1 | 2 | 三者均存在 | parent 6、legacy，Generation 1 / PMIO |
| `run-lsdtskss` | RELEASE 1.7.2 | patched 1.7.1 | 2 | 三者均存在 | 无 parent 错误，Generation 2 / MMIO |
| `run-xlg77qoi` | RELEASE 1.7.2 | stock 1.7.1 | 2 | 三者均存在 | parent 6、legacy，Generation 1 / PMIO |
| `run-n2gpklt1` | RELEASE 1.7.2 | patched 1.7.1 | 1 | 三者均存在 | parent 6、legacy，Generation 1 / PMIO |
| `run-61q97_21` | RELEASE 1.7.2 | stock 1.7.1 | 1 | 三者均存在 | 无 parent 错误，Generation 2 / MMIO |

这里“三者”为 **Lilu 1.7.2、VirtualSMC 1.3.8、当次选择的 WhateverGreen 1.7.1**。
stock 与 patched 从不混装。guest `kmutil` 的 WEG UUID 分别为
`1EAB6DC3-887F-37A7-82BB-F86E987ED5A3` 与
`A6898D03-3EB8-39A3-86A6-5E5AB555BAA2`，对照输入二进制摘要不同，
没有仅凭相同的 `1.7.1` 版本号混淆二者。
另从实际输入的 x86_64 Mach-O slice 读取 `LC_UUID`，与六个 guest 的三个
已加载条目逐项对照，**18/18 完全匹配**；收据为
`.local/recovery-repair/loaded-uuid-audit.json`。

DEBUG Lilu 的 patched 实验还实际记录：

- `force enabling due to force flag`，参数状态 `disabled 0`；
- `got load request from WhateverGreen (171)` 和 `... VirtualSMC (138)`；
- 找到并包裹 `_PE_initialize_console`，进入 `PE_initialize_console 6 performing init`；
- 同次运行中，VirtualSMC 的通用初始化路径使 Lilu 路由 `_kernel_trap`；
  WEG 则注册图形驱动加载监听。此处不是 Tiger Lake GPU 中断或 framebuffer callback；
- 后续真实 kext 加载时，Lilu 的 kext-load hook 被调用。

这些是 loader 接受所用 bundle、依赖与链接修正、模块入口执行以及部分插件
初始化路径的实际证据，比“构建成功”或“已注入”更进一步。日志并非零诊断：
例如 `/options` NVRAM 访问失败、authenticated restart 不可用、Darwin 25
默认关闭 Lilu user patcher 均保留；没有据此声称完整运行功能通过。

**VirtualSMC 尚有初始化时序限制**：parent 6 / legacy 出现在三个 case；单 vCPU
对照的 stock/patched 结果与双 vCPU 相反，因此不能把原因归给 stock WEG，
也不能把改为一个 vCPU 描述为修复。尽管这些 case 的 VirtualSMC / AppleSMC
对象仍是 `registered, matched, active`，它们的 Lilu 插件初始化并未都成功。
Lilu 与 WEG 的 registry 对象显示 `!registered, !matched, active`，报告照实保存，
不简化成“所有服务完整匹配”。

固定源码与日志进一步确认：**Error 6 是 `LiluAPI::Error::TooLate`**，表示
VirtualSMC 的 `requestAccess()` 晚于 Lilu 的 `finaliseRequests()`，不是
IOKit 父设备 `start()` 失败。DEBUG 失败 case 明确记录 PE 初始化先于 VirtualSMC
模块入口；成功 case 的两个插件请求均在收口前。

VirtualSMC 1.3.8 在这个分支强制 Gen 1，先于读取 `vsmcgen` 参数，因此
`vsmcgen=2` 不能覆盖该降级。`-liluforce` 只覆盖 Lilu 的单用户启用条件，
`liludelay` 只延迟调试输出；六份配置也已满足 Lilu 在前的依赖顺序。
OpenCore 的 `LoadEarly` 是 UEFI driver 属性。此次源码审阅没有找到可可靠延后
API 收口的现有参数或已验证配置修正，具体触发时序仍未解决。

源码依据为固定 Lilu
[`requestAccess` / `finaliseRequests`](https://github.com/acidanthera/Lilu/blob/e4748cc081bf060302c7d3c44a643ce1d11b7e1d/Lilu/Sources/kern_api.cpp)
及 VirtualSMC
[`forcedGeneration`](https://github.com/acidanthera/VirtualSMC/blob/b15991dd87e36a102bf159ea56490e3126245590/VirtualSMC/kern_vsmc.cpp)
和 [`provider 初始化`](https://github.com/acidanthera/VirtualSMC/blob/b15991dd87e36a102bf159ea56490e3126245590/VirtualSMC/kern_prov.cpp)。
六份 VirtualSMC 二进制另与固定原始 release archive 的
`Kexts/VirtualSMC.kext/Contents/MacOS/VirtualSMC` 逐字节核对一致。
完整有界诊断及固定来源在 `.local/recovery-repair/abi/late-plugin-notes.md`。

## 已验证范围与仍需实机的部分

- 已证实：不安装 macOS 也能运行这个准确 build 的 XNU、执行 guest 系统命令，
  并让 stock / 自编译 patched WEG、Lilu、VirtualSMC 出现在真实已加载列表中。
- 已观察：Lilu 与 WEG 的部分初始化/回调路径、虚拟 SMC 对象及 AppleSMC 子节点。
  VirtualSMC 的晚注册/legacy 现象仍须单独解决，不能以“可启动”覆盖。
- 没有 `8086:9a49`、HP eDP、Synaptics I²C 或 Wacom 的设备直通。
  未执行这些设备的匹配与读写，不能证明 HP framebuffer、背光、触控或 Metal。
- 没有实际运行完整 Recovery GUI、安装器联网、正常多用户 macOS 或实机睡眠。
  单用户环境、DEBUG 插桩与 raw 派生介质的结果不自动外推到它们。

证据汇总见 [Recovery/kext manifest](../manifests/recovery-kext-check.json)。
公开审计器 `scripts/check_recovery_vm.py` 核对 guest 的独立输出标记、准确版本、
已加载 bundle、保存配置/工具/kext 摘要和磁盘隔离，并逐项输出初始化诊断；
它不会因为六个 shell 均可用而将所有插件功能判定为通过。

## 当前 build 的静态符号补充

固定 LLVM 21.1.8 读取 KC：它是 x86_64 `MH_FILESET`，包含 **204** 个
fileset entry / `llvm-nm` 符号组。顶层 `LC_SYMTAB` 为零不代表整个 KC 无符号。

最终 patched WEG 的 421 个 undefined 名称中，376 个匹配当前 KC 的
`com.apple.kernel`，39 个匹配固定 Lilu 1.7.2 DEBUG 导出，4 个匹配
`com.apple.iokit.IOPCIFamily`。另 2 个名称
`__ZN9IOService19_RESERVEDIOService0Ev` 与
`__ZN9IOService19_RESERVEDIOService1Ev` 未出现在这些精确名称集合中。
这种静态缺名不能直接判定 OpenCore 的链接/虚表修正一定失败；实际 loader
观察另列，不能用名称匹配替代运行证据。

当前 Recovery KC 未枚举到 AppleIntel framebuffer / IOGraphics 的 fileset ID。
没有用其他版本的 Apple 显示驱动补作当前 build 的事实。

私有脚本、工具版本、输入摘要、204 组导出和逐名称对照保存在
`.local/recovery-repair/abi/`。固定 Lilu 源码依据：
[`kern_start.cpp`](https://github.com/acidanthera/Lilu/blob/e4748cc081bf060302c7d3c44a643ce1d11b7e1d/Lilu/Sources/kern_start.cpp)
与 [`README.md`](https://github.com/acidanthera/Lilu/blob/e4748cc081bf060302c7d3c44a643ce1d11b7e1d/README.md)。

## 复现入口

下载或续传（`latest` 不是固定 build，重新下载后必须另行核实版本）：

```sh
python3 scripts/fetch_recovery.py --output .local/recovery-download
python3 scripts/fetch_recovery.py --output .local/recovery-download --verify-only
```

镜像入口：在新的 `.local` 输出目录放入对应的 `BaseSystem.chunklist`，并传
`--image-url <mirror-dmg-url>`；或同时传 `--chunklist-url <mirror-chunklist-url>`。
不向镜像发送 Apple AssetToken，不绕过 Apple 签名或分块校验。

启动实测所用隔离配置（工具与 bundle 路径按本地缓存提供，按依赖顺序重复
`--kext`；DEBUG Lilu 可输出初始化证据）：

```sh
python3 scripts/recovery_vm.py launch \
  --qemu <qemu-system-x86_64> \
  --ovmf-code <OVMF_CODE.fd> --ovmf-vars <OVMF_VARS.fd> \
  --recovery .local/recovery-download \
  --raw-system --single-user --force-lilu --lilu-debug \
  --kext <Lilu.kext> --kext <VirtualSMC.kext> --kext <WhateverGreen.kext>

python3 scripts/recovery_vm.py screen --run .local/recovery-vm/<run>
python3 scripts/recovery_vm.py key --run .local/recovery-vm/<run> --keys ret
python3 scripts/recovery_vm.py type --run .local/recovery-vm/<run> \
  --text 'echo VM_PROBE_BEGIN; /usr/bin/uname -a; /usr/bin/sw_vers; /usr/sbin/kextstat -l'
python3 scripts/recovery_vm.py key --run .local/recovery-vm/<run> --keys ret
python3 scripts/recovery_vm.py stop --run .local/recovery-vm/<run>

python3 scripts/check_recovery_vm.py \
  --version 26.6.2 --build 25G83 --kernel 25.6.0 \
  --run .local/recovery-vm/<run>
```

省略 `--raw-system` 可重现原始签名 DMG 路径；该辅助项通常需要发送 Enter。
`launch.json` 固定本次配置、工具、系统输入与每个 kext 可执行文件/Info.plist 摘要；
`control.jsonl` 保存发给 guest 的实际输入。截图和串口日志是观察记录，
`launch` 返回值、配置校验与“可见启动选项”本身均不等于加载验收。
