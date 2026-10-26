# GA47 完整包复核与 kext 清单

> GA48时点的原生包签名未知项已在GA49获批staging中实际检查；当前结果见 `../ga49/reports/RESULTS.md`。包本身没有重签或改字节。

封存仓库 HEAD/tag：`a9ae966cd56075db59cc6ff2878e3958022d91b7` / `GA47_OFFLINE_DELIVERY`，
上游基线 `6a1afb337d1fb1ff07ca032b5c1868fe2bd005ef`。本轮未修改历史树。

| 项目 | 本轮重新检查结果 |
|---|---|
| 归档 | 83,106,926 字节，79.257 MiB |
| SHA256 | `51aaffade75da6d5076071e304e4634aefe60e68d7e0cdd12d79981e31f1b143` |
| Inventory | 246 项文件/链接全匹配，另有包根目录之外的嵌入 manifest 收据 |
| Mach-O | 31 个，真实头、load commands、代码页重新检查 |
| CodeDirectory | 51,898 个 x86_64 代码页哈希匹配；不等于 Apple 信任/完整 bundle seal |
| donor | Apple 16.0.32 来源，MTL 10 项、旧 plugin 12 项精确上游补丁，6 个资源匹配 |
| 功能源码差异 | 仅 GA47 的 `src/NootedGreen/kern_gen11.cpp`；本轮不开发新驱动 |

完整布局 `efi-add/`、`payload/Library/Extensions/`、`payload/Library/GPUBundles/`、
`payload/System/Library/Caches/xe.bundle/`、`config-proposal/` 均存在；没有空壳补齐。
`tools/verify-package.py` 直接重新读取归档，在本阶段私有目录解包核验，
仅调用历史核验器的只读函数，没有运行其会写回 GA47 manifest 的 main。

## 三个核心 kext

| 组件 | ID / 版本 | 依赖与类型 |
|---|---|---|
| Lilu | `as.vit9696.Lilu` / 1.7.2，compatible 1.2.0 | MH_KEXT_BUNDLE；与 GA47 头文件/runtime 一致 |
| NootedGreen | `com.StezzaPilot.NootedGreen` / 1.0.0 | MH_KEXT_BUNDLE；最低 Lilu 1.6.4，1.7.2 满足版本范围 |
| HookCase | `org.smichaud.HookCase` / 8.0.1 | MH_KEXT_BUNDLE；TGL 两驱动需 >=1.0；无 IOKit personality；真实 `_strnstr` 导出 |

NootedGreen SHA256：`21900f4574975c569e3119f14a5f2adf0fa52e1e767e78d6bc788b6c64f5cef2`。
HookCase SHA256：`dc69d6d0448e0558d8170bc4ecc4c88ef9c961395bfce30cd39ceb3607ecd728`。
加速器 bundle 版本按上游安装器为 16.0.2，framebuffer 16.0.0；不是把它们的 bundle 版本误写成 donor 来源16.0.32。

libxedrv、Compiler Adapter、LLVM Bridge 逐文件哈希匹配封存包，均为真实 `MH_DYLIB`。
原 SerializedBitcode 导出、旧 WithOptions 导出、重导出链、Gen12/TGLLP IGC 与上游真实 shader
request/reply 实现保留，没有换成 GA46 的拒绝设备/null/mock 路径。
完整库依赖、所有核心 kext 的 Info 与镜像总计 13 个 Enabled kext 条目见 `PACKAGE.json`、`IMAGE.json`。

**LLVM3802/3902 仍为未解决的运行时前提**：原样 Shared stock plugin 指向3902，libIGIL-Metal 指向3802。
包未提供两套旧系统 LLVM。主 adapter/bridge 指向32023，不证明上述 legacy 组件不会被动态加载。
25G83 shared-cache/getSerializedModule 扫描、descriptor、C++ ABI、shader 请求回复仍无运行实证。

## 原生签名边界

Lilu DEBUG、donor framebuffer 保留上游 unsigned 状态；加速器 Info.plist 有上游两项编辑，
即使二进制代码页匹配也不能宣称其完整 bundle seal 有效。新产物的 ad-hoc 签名不是受信任的 Apple 签名。
本轮包没有写入目标，所以包的原生 `codesign --verify --strict --deep` **尚未执行**。
目标实际原生工具、已有系统 kext 与 KC 的只读检查见 `TARGET-PREFLIGHT.md`；它们不替代此项。
