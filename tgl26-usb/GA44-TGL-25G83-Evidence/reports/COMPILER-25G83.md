# 25G83 Shader Compiler / MTLCompiler ABI 分析

状态：`REMOTE_READ_ONLY` + `LOCAL_BINARY_ANALYSIS`。没有在目标上运行编译器，
没有安装/替换任何组件。

## 1. 目标系统实际栈

| 组件 | 目标 25G83 | 证据 |
|---|---|---|
| `Metal.framework` | 373.7 | Info/version plist |
| `MTLCompiler.framework` | 373.7；`Versions/32023` 和 `32024`，Current=32024 | Info/version plist |
| `GPUCompiler.framework` | `Versions/32023`；`libGPUCompilerImplLazy.dylib` 32023.255.1 | `otool -L`，UUID `F493DEB7-…` |
| `MTLCompiler` 可执行体 | 无独立文件；经 dyld shared cache 解析 | `dyld_info -exports` 成功 |
| `libLLVM.dylib` | 无独立文件；shared cache only | `ls` 失败，`libGPUCompilerImplLazy` 链接它 |
| `libGPUCompilerImpl.dylib` / `libllvm-flatbuffers.dylib` | 无独立文件；shared cache only | `ls` 失败 |
| `AppleIntelGraphicsShared.bundle` | 无 Info.plist；`libigc` + 新插件 | `ls`/`plutil` |

### `MTLCompiler` 导出

`dyld_info -exports` 只看到：

```text
MTLCodeGenServiceBuildRequest
MTLCodeGenServiceCreate
MTLCodeGenServiceDestroy
MTLCodeGenServiceSetPluginPath
```

没有导出 `MTLCompilerBuildRequestWithSerializedBitcode`；该入口在 GPU
插件里。`getSerializedModule` 也没有出现在导出表，说明参考 bridge 的
签名扫描仍是必要手段（而不是可用的公开符号）。

## 2. 目标插件 vs donor 插件：API 方向相反

| 项目 | 目标 25G83 `libMTLIGCCompilerPlugin.dylib` | donor 16.0.32 插件 |
|---|---|---|
| 路径 | `/System/Library/Extensions/AppleIntelGraphicsShared.bundle/Contents/MacOS/` | NootedGreen `sle_Internal/sle/...` |
| 架构 | x86_64h（subtype 8） | x86_64 |
| 大小 | 146,000 | 135,152 |
| SHA-256 | `c55ae0a0…` | `477083cb…` |
| 新入口 | **有** `MTLCompilerBuildRequestWithSerializedBitcode` | 无 |
| 旧入口 | 无 | **有** `MTLCompilerBuildRequestWithOptions` |
| `MTLCompilerSetHelper` | 无 | **有** |
| `MTLCompilerCreate/Delete/ReleaseReply` | 有 | 有 |

这意味着：

- 目标系统已经是一个**新 API** 的 Metal 编译服务；
- 但目标插件不是 TGL 编译器（见下节）；
- donor 插件是 TGL 编译器，但只支持**旧 API**。

参考项目的 `compiler-adapter.cpp` 仍然是对的方向：把新
`BuildRequestWithSerializedBitcode` 映射到旧
`BuildRequestWithOptions`，再让旧插件调用 donor `libigc`。
不能简单地把目标插件换进去，因为它没有 Gen12 后端。

## 3. 目标 `libigc` 是否支持 Gen12？

`strings -a libigc.dylib | grep -E '^gen[0-9]+'`：

```text
目标 25G83:  gen11, gen11lp, gen13, gen83, gen93
donor 16.0.32: gen8, gen8lp, gen9, gen9lp, gen10, gen11, gen11lp, gen12, gen12lp
```

目标 `libigc` **没有 `gen12` / `gen12lp`**；donor 有，并且 donor 里还能看到
`TGLLP`、`_InitTglLpHwWaTable`、`gen12lp` 等字符串。目标 `libigc` 是
Gen11/Gen13 系列，不是 TGL 编译器。

因此：

- 目标 `AppleIntelGraphicsShared.bundle` 不能单独为 TGL 编译 shader；
- donor `libigc` 仍是唯一在本地可得的 Gen12/Xe-LP 编译器；
- 目标插件的新 API 不能直接使用 donor 旧 IGC 的旧接口，仍需要
  adapter/bridge，或等价的 ABI 适配；
- 目标 `MTLCompiler` 373.7/GPUCompiler 32023 的版本信息可用于修正 bridge
  的路径/签名，但不能把“目标有 IGC”误写成“目标支持 TGL”。

## 4. `libLLVM` 路径问题

参考 `llvm-bridge.cpp` 的 `L()` 写死：

```text
/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/32023/Libraries/libLLVM.dylib
```

目标 25G83 上该路径**没有独立文件**；`libLLVM.dylib` 只在 dyld shared
cache 中。`libGPUCompilerImplLazy.dylib` 的 `otool -L` 仍显示这个
install name，说明运行时可由 dyld shared cache 解析，但：

- 用 `dlopen` 打开这个路径是否成功，需要在目标上做受控只读运行时探针；
- 不能把“文件不存在”直接判为“库不存在”；
- 也不能在没有运行时探针的情况下声称 bridge 可用。

状态：`NEEDS_TARGET_RUNTIME_PROBE` / `NOT_TESTED_ON_GPU`。

## 5. 对 GA4.3 结论的修正

GA4.3 说“Tahoe 25G241 的 `MTLCompiler` 调用新入口，旧插件只有旧入口，
所以需要 adapter/bridge”。25G83 的实测补充：

1. 25G83 **目标插件已经有新入口**，但它的 IGC **没有 Gen12**；
2. 25G83 **donor 仍缺新入口**，但它的 IGC **有 Gen12**；
3. 因此 adapter/bridge 仍然需要，但理由从“目标插件缺新入口”变成
   “目标插件缺 Gen12，donor 插件缺新入口”；
4. `libLLVM.dylib` 在目标上只存在于 shared cache，bridge 的路径需要重新
   验证或用 `dyld` 解析；
5. `MTLCompiler` 当前版本是 32024，GPUCompiler 是 32023；参考桥写死 32023
   可能只是 GPUCompiler 版本，不是 MTLCompiler 版本，需按实际路径修正。

## 6. 结论

| 项目 | 状态 |
|---|---|
| 目标 Metal/MTLCompiler/GPUCompiler 版本 | `VERIFIED_SOURCE`/`REMOTE_READ_ONLY` |
| 目标插件新入口 | `VERIFIED_BINARY` |
| 目标 IGC Gen12 支持 | **否**（`VERIFIED_BINARY`） |
| donor IGC Gen12 支持 | **是**（`VERIFIED_BINARY`，本地 donor） |
| adapter/bridge 是否仍需要 | **是**，但需按 25G83 路径/签名重写 |
| `libLLVM` 路径 | `NEEDS_TARGET_RUNTIME_PROBE` |
| TGL shader 实际编译 | `NOT_TESTED_ON_GPU` |
