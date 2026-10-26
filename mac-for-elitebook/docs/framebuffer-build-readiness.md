# Patched WhateverGreen CLI 构建就绪度

**当前结论：已在 Linux 本机完成 patched WEG 的编译和真实 `MH_KEXT_BUNDLE` 链接**，没有使用 Apple SDK 或 Xcode。产物仅保存在 `.local/framebuffer-build/`，没有被 macOS loader 或 HP 实机验证。来源、二进制摘要和验证边界见 [链接核查](../manifests/framebuffer-link-check.json)。下文先保留初始缺口，再记录如何逐项解决。

## 初始就绪度探测

- 基准是 WEG `0762cecc2a70054cd4dc3cf4d08979aca6acd9bb`，Latitude `1010490d3421628c9d6fd0bd518b6c4b6f8ee33c` 的 0001–0003 已按序应用，见[补丁核查清单](../manifests/framebuffer-patch-check.json)。固定脚本 SHA-256、资源及本机探测结果见[本记录清单](../manifests/framebuffer-build-readiness.json)。
- clang 21.1.8 用 `x86_64-apple-macos10.6` 和脚本的 kext C++ 选项成功产生了一个 Mach-O x86_64 探测对象；隔离副本中，加入 Lilu 1.7.2 resources 与 MacKernelSDK 后，20 个 C++ translation units 有 19 个通过 `-fsyntax-only`。唯一失败是 `kern_shiki.cpp` 找不到生成文件 `kern_resources.hpp`。这不是完整编译或链接证据。
- WEG 项目通过 `ResourceConverter` 目标生成 `kern_resources.cpp/.hpp`。它的 `main.mm` 导入 Foundation/Cocoa；项目的 `ResourceConverter/generate.sh` 先调用 codesign 再执行该工具。Latitude CLI 脚本没有生成这两个文件的步骤。当前系统对 `ResourceConverter/main.mm` 的语法探测因缺少 `Foundation/Foundation.h` 失败；MacKernelSDK 不是 Foundation/Cocoa SDK 的替代品。
- Linux clang 的最小链接探测实际落到 GNU ld.bfd 2.46，失败于 `unrecognised emulation mode: llvm`。没有 `ld64.lld` / `ld.lld`。脚本还链接 `-lkmodc++ -lkmod -lcc_kext -lkmod`；脚本未固定 MacKernelSDK 版本。探测用的 MacKernelSDK `3f750085caa17ec3a7880f11c11bf4f48cd6a164` 有 `Library/x86_64/libkmod.a` 和 `Library/universal/libkmodc++.a`，但没有脚本搜索目录下的 `libkmodc++.a`，也没有 `libcc_kext.a`。后两项的适用版本及实际提供方仍须确定。

## SDK 与后处理边界

WEG kext 的 C++ 编译参数使用 `-nostdinc`，并显式包含 MacKernelSDK 与 Lilu headers；这说明内核代码的头文件路径可由 MacKernelSDK 代替完整 macOS SDK。无 Apple SDK 的 Linux 交叉编译路线**仅对已生成资源的 kext 源码编译阶段有初步证据**，完整链接尚未证明。若从固定源重建，ResourceConverter 确实需要 macOS Foundation/Cocoa SDK（或可信的生成后 `kern_resources.cpp/.hpp`）；不需要据此推断必须安装完整 Xcode IDE 或运行 `xcodebuild`。

`strip` 在链接之后：本机 GNU strip 既不认 `-T`，回退形式也不识别 Mach-O，因此不是链接前置条件，但会阻止脚本原样完成后处理。`plutil -lint` 也在链接和 plist 生成之后；本机缺少 plutil，但 Python `plistlib` 可解析源 Info.plist。最终 kext 的 `codesign` 在 CLI 脚本中以 `|| true` 忽略失败；ResourceConverter 的生成脚本则单独、未忽略地调用 codesign。

## 最小下一步

在隔离副本中补齐并固定 Lilu resources、兼容的 MacKernelSDK/静态库和 Mach-O linker；先用 Apple macOS SDK/CLT 生成并核验 `kern_resources.cpp/.hpp`（或提供可信的生成文件）。随后才可尝试下列完整脚本调用；当前 Linux 环境尚不满足这些前提：

```sh
bash .local/build-readiness/inputs/build-weg-clt.sh \
  "$PWD/.local/build-readiness/isolated/WhateverGreen" \
  "$PWD/.local/build-readiness/isolated/out"
```

本轮未运行该脚本或完整 kext 构建，未取得 Apple 系统镜像，未访问远端机器或 USB。MacKernelSDK 中社区预编译 `libkmod.a` 是脚本所需链接输入，不是禁止项。

## 后续 Linux 路线（独立于上面的初始探测）

后续主代理已通过临时 Nix shell 取得 LLVM/LLD 21.1.8，无永久 profile 安装。实际 `ld64.lld -kext` 会发出 `Option -kext is undocumented` 并忽略该输出类型，继续寻找 `_main`；因此 **LLD 21 的存在不等于具备 kext linker**。不能把普通 dylib/bundle 改名为 kext 来绕过检查。

继续在本机推进两个可消除的缺口：将固定 ResourceConverter 的 plist→C++ 转换移植为 Python，并准备真正支持 `MH_KEXT_BUNDLE` 的开源 ld64。前述 Foundation 缺失只阻挡原生 Objective-C++ 生成器路径，不排除有语义验证的转换器移植。构建脚本 `scripts/build_framebuffer.py` 使用全新私有目录、重新核对原始归档/补丁/依赖哈希，再编译与链接；产物不能自动进入 VESA 原型或外部介质。

已实测的进一步进展：

- Python 生成器已生成固定资源并回读检查 6 个 mod / 14 个 patch / legacy 32、modern 34 条 process；section enum 确定性排序，尚无 macOS 原生生成器输出作字节级对照。
- 首次完整编译已产生 **23 个 x86_64 Mach-O 对象**：21 个 C++（含生成资源和 Lilu plugin_start）、1 个汇编及 1 个模块声明 C 文件；链接仍须独立验证。
- LLVM 21 对全局析构的后端 lowering 会引入 `___cxa_atexit` 和 `___dso_handle`；固定 CLI 原始选项及 `-fno-register-global-dtors-with-atexit` 均没有消除此行为。不能仅因编译退出 0 就忽略这个内核运行时差异。
- 单对象对照已验证 `-mllvm -disable-atexit-based-global-dtor-lowering` 保留 `__mod_init_func` / `__mod_term_func`，并消除上述 userspace atexit 导入。构建脚本明确记录此 LLVM 21 适配，不禁用析构函数，也不伪造缺失库或符号。

加入该后端选项后，新的完整对象构建再次通过 23/23，逐对象检查确认不再导入 `___cxa_atexit` / `___dso_handle` / `_atexit` / `_main`。`SOURCE_DATE_EPOCH=1792022400` 是显式固定的 recipe 日期，并非上游 commit 时间；源码路径使用 file-prefix-map，便于后续比较不同私有构建目录中的产物。

复跑入口（依赖固定缓存输入和 LLVM 21）：`make framebuffer-objects LLVM_BIN=<llvm-bin>`；真实 ld64 准备好后使用 `make framebuffer LLVM_BIN=<llvm-bin> LINKER=<ld64>`。两者均只写 `.local/framebuffer-build/`，不改 VESA EFI。

## 真实链接已完成

GPT-6 Luna 已在本机构建 cctools-port 的 **ld64 956.6**，固定提交 `904de2a71d4da6a9b30d2efaf912a10ddc7d9ddb`。Linux ELF 链接器 SHA-256 为 `61dd272a95b54bace182f414510818463435d834b2044ec4889e65c99ab768ee`；源树归档、构建参数与依赖见 [工具链清单](../manifests/macho-toolchain.json)。仅构建 linker 的 3 个 make 子目录，关闭 LTO/TAPI/XAR，使用 libdispatch/BlocksRuntime；没有执行系统安装。

主代理使用该 ld64 执行 `make framebuffer`：23/23 对象编译且与上次 compile-only 的对象摘要全部相同，链接退出 0。产物为 x86_64 `MH_KEXT_BUNDLE`（filetype 11），flags `0x85`；无 userspace dylib load command，存在模块入口及原生构造/析构段。使用 SDK 中真实的 universal `libkmodc++.a` 和 x86_64 `libkmod.a`；没有伪造缺失的 `libcc_kext`。

最终二进制 SHA-256：`b9181fd2b090c03731f8fe842cfd654615bc5e28553fabd99b51e76e75c257de`。421 个未定义导入比 stock WEG 1.7.1 多 17 个，未少任何 stock 导入；查询的 18 个 Lilu 类相关导入均在固定 Lilu 1.7.2 RELEASE 导出表中存在。**这仍不是 Tahoe kernel 导出/ABI、kext 加载或 HP framebuffer 成功的证明。** 当前未 strip、未签名，也没有 macOS 原生生成器输出作字节级比较。

初始快照中“缺 SDK / linker / 生成资源”的本机构建缺口已经通过上述 Linux 路线解决，后续不能继续把它们列为必然外部阻塞。真正剩余的是目标 build 的系统环境、macOS loader/内核接口与实机显示验证；仍需遵守禁止重启和保留介质的约束。
