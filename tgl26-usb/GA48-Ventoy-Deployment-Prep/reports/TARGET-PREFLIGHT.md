# HP 25G83 真实只读预检

> GA48历史记录。GA49已完成获批staging的真实包原生检查，并撤回下述旧Caches推断，见 [纠错](GA49-CORRECTION.md) 与 `../ga49/reports/RESULTS.md`。

本轮 SSH 使用已有系统命令。原始 stdout/stderr/返回码/时间保存在忽略的 `private/native/`，
命令收据为 `NATIVE-COMMANDS.json`。ESP 只读回取使用已授权 sudo；密码不落盘。

| 实际命令/对象 | 实际结果 | 能证明什么 |
|---|---|---|
| `sw_vers` | 26.6.2 / 25G83 | 当前目标版本 |
| `csrutil status` | enabled | 当前 SIP 未放宽 |
| `csrutil authenticated-root status` | enabled | 当前 authenticated-root 未放宽 |
| `mount` | `/` sealed、read-only | 仅说明根卷；GA49证实Caches属于Data，不能据此判它不可写 |
| `nvram -p` | CSR=0；VESA boot-args | 现有变量与候选不同；不是启动过 GA48 |
| `ioreg IGPU` | 8086:9A49、HP103c:8716 | 本机真实 TGL；当前 VESA platform-id 为 ffffffff |
| `ioreg IONDRVFramebuffer` | `.Display_boot` active，IOFBMemorySize=8294400 | 当前固件帧缓冲环境，不是 Metal |
| `codesign --verify --strict --verbose=4 /usr/bin/true` | rc=0 | 原生校验器可执行、正常处理正对照 |
| 同命令检查 stock AppleIntelICLGraphics.kext | rc=1：code object is not signed at all | 此 stock standalone/elided bundle 不提供可校验的独立代码签名；**不说明 stock KC 不可信** |
| `kmutil showloaded` / `kextstat -l` | rc=0 | 当前 Lilu1.7.2、WhateverGreen1.7.1；无 TGL、HookCase、ICL accelerator |
| `kmutil inspect` boot/system | rc=0 | provider ID/版本与原有 ICL 代码在 stock KC 内可见 |
| `kmutil inspect` AuxKC | rc=0 | 只有 AppleMobileDevice、HighPointIOP、HighPointRR；无 TGL/HookCase |
| `ls` 目标 TGL/HookCase、xe.bundle | rc=1，No such file | 当前完整系统栈未部署；GPUBundles 为空 |
| `ls /Library/Developer/KDKs` | rc=1，不存在 | 常规位置无 KDK，不能默认精确25G83重建条件满足 |

当前 AuxKC 917,504 字节，SHA256：
`5d6170588133eae3fe1d4f0024f67960f0ce6aeb6d2f3266e9865d96ddfa8fcd`。
已读取 active Preboot KC 目录清单，含 BootKernelExtensions.kc 及各 im4m；后续备份必须包括该目录。
本轮未备份到目标、未注册、未重建、未加载、未运行新程序。

## 依赖/KC 可能失败的位置

`DEPENDENCIES.json` 将所有16类声明依赖与实际 KC/包核对：
IOAcceleratorFamily2=487.4.3（compatible2.0.0）、IOSurface=393.5.8（compatible1.0）、
IOPCIFamily=2.9（compatible1.0.0b1）、IOGraphicsFamily=600、IOReportFamily=47、
AppleGraphicsDeviceControl=8.1.12、IOACPIFamily=1.4 可见。
KPI=25.6.0。部分 elided/system pseudo-bundle 没有可读取的对应 Info.plist，不能补造兼容版本。
Lilu 的 `com.apple.kernel.6.0` 是未在 KC ID 清单中列出的 legacy pseudo-library，需原生解析验证；
当前 Lilu 已加载不等于新整套 kext 的符号/ABI 均可解析。

实际 `kmutil load --help` 支持 `--load-style match-only`，`-z` 明确是 skip approval。
本轮不复制这个绕过参数。`kmutil install --help` 明确自macOS13起重建需要匹配 KDK；
不以 `--allow-missing-kdk` 绕过。只读 inspect **不是依赖链接 dry-run**。
当前没有在授权范围内既能完成真实注册又不改状态的证明途径，故未尝试 load/install。

## 需要原生验证包时的精确新增写入请求（本轮未执行）

下一轮若批准，仅新建 APFS 上的 `/Users/Shared/GA48-preflight/`：

1. 从本机复制原归档到该目录；预期83,106,926字节、SHA256见 PACKAGE-CHECK。
2. 原生 `shasum -a 256` 核对，`tar -xzf` 仅解包至同一新目录；保留链接、mode，不写 EFI/L/E。
3. 另复制本地 `out/PACKAGE-SHA256SUMS`、审查后的脚本；不赋予自动执行或登录启动能力。
4. 仅运行已有 `codesign`、`plutil`、`otool -L`/可用工具检查解包目录的真实 bundle/dylib；
   不运行包内程序，不用 `spctl --add`、codesign重新签名、kmutil load/install。
5. 记录每项 rc/stdout/stderr，unsigned/seal问题单独报告；若需重新签名，须另批并重做哈希。
6. 清理只限这个新 staging 目录，另行确认后进行；这是该只读验证写入请求的完整影响范围。

单独批准上述 staging 仍不包含系统安装、SIP/SSV/AMFI变更、KC注册、重启或 GPU 实验。
