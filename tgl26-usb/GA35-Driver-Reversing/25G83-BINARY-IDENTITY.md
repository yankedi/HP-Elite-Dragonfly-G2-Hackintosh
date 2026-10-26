# Tahoe 25G83 精确二进制身份

## 结论及范围

**已取得本机25G83磁盘上的真实Kernel Collection，并将三个目标映像的UUID、版本与采集前后已加载元数据逐项对应。** 这不是运行态指令字节认证；Lilu/WhateverGreen已经加载，其内存补丁不会改变Mach-O UUID。本轮没有读取内核RAM。

来源为普通账户`user`、uid501的只读SSH。`logs/remote-identity.stdout`、`remote-loaded.stdout`、`remote-loaded_postcopy.stdout`和对应JSON回执保留命令、退出码、时间、stdout/stderr SHA。前后`kern.boottime`一致。版本为26.6.2 / **25G83**、x86_64、XNU12377.161.14~5。没有sudo或远端暂存文件。

## 完整原件

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
|BootKernelExtensions.kc|67584000|`c80161fa3065883753fc285339281361a8469cbb6fb27653c88e2a22eb4807a4`|
|SystemKernelExtensions.kc|361922560|`fbab2d48bf1470fb0ec15dd62a6bb90c39d8bb45ed68240d3c73f1e43e770dee`|
|AuxiliaryKernelExtensions.kc|917504|`5d6170588133eae3fe1d4f0024f67960f0ce6aeb6d2f3266e9865d96ddfa8fcd`|

原件位于`inputs/macos-readonly/`的原绝对路径镜像下。每份完整输入都有远端复制前SHA、本地SHA、远端复制后SHA三方一致回执：`logs/fetch-receipt.json`、`fetch-resume-receipt.json`。首次SystemKC传输外层120秒超时留下128450560B部分文件，SHA `2aec52060acddf3ec7309fcd17e19ebcce957bdc0cc40aa24a7749f4400893ad`，另存`.partial-first-timeout`，不进入有效库存。

磁盘三个kext bundle均有Info.plist，但**没有Contents/MacOS独立可执行文件**，见`remote-bundle_inventory.stdout`。因此不拿空bundle代替驱动二进制，也没有使用其他OS版本。SystemVersion.plist和三份Info.plist同样复制并核验。

## 映像与坐标

|映像|版本|Mach-O UUID|KC header/file offset与KC VA|loaded报告地址|
|---|---|---|---|---|
|AppleIntelICLGraphics|24.0.5|`B7DF3049-D3A9-3070-9843-6E5AE47673D7`|`0x13e9f000`|`0xffffff7f94b84000`|
|AppleIntelICLLPGraphicsFramebuffer|24.0.5|`7949B335-4901-3B40-9EB6-3D9A34FE65C7`|`0x13fd9000`|`0xffffff7f94cbe000`|
|IOAcceleratorFamily2|487.4.3|`B77A42EC-6B0C-3A8D-89A2-B8F4CDBAC8C9`|`0x14582000`|`0xffffff7f95267000`|

SystemKC/BootKC 的机器会话标识已省略；其 kernel 映像 UUID 为 `39CC2C26-3F72-3565-89C4-94DFE36DFDF2`。

本KC的目标Mach-O使用低地址容器坐标，不能把`0x13ec39f6`当作可直接调用的内核指针。三个目标一致满足：

```
metadata-derived runtime VA = KC-coordinate VA + 0xffffff7f80ce5000
```

这里是**运行加载bias（包含KC映射origin）**，不是独立确定的KASLR随机slide。另一次只读`kern.slide`返回0；不把它套用为SystemKC的映射bias。随机部分无法由本轮元数据单独分离。`analysis/binary-identity.initial-terminology.json`保留最初误称derived_image_slide的工件，当前正确字段为`derived_kc_runtime_load_bias`。

每个segment的KC虚拟范围、fileoff/filesize/vmsize/protection完整保存在`analysis/kc/SystemKernelExtensions.kc.json`及`analysis/binary-identity.json`。loaded工具报告的size单列，不能等同所有共享LINKEDIT/数据段的完整映射范围。衍生运行地址只作元数据映射说明，未用于读写。

## 符号、字节和反汇编

主ICL映像保留5440符号，Framebuffer3835、IOAccelerator4705；另外存IOGPUFamily/IOGraphicsFamily库存。`analysis/expanded/*.all.json.gz`保留五映像共11416个符号上界片段、原始完整bytes/SHA、469052条实际解码指令、每条fileoff/VA与函数入口。`logs/fragment-verification.json`重新从KC核验全部输出字节和坐标。**符号上界不是已恢复CFG，线性解码不是可达性证明；undecoded tail仍在raw_bytes中。**

Capstone5.0.9库路径和SHA在`analysis/disassembly/decoder-provenance.json`。反汇编不构造“可加载提取kext”；KC链式指针仍需按格式解析。`tools/cache_fixups.py`依据固定Apple dyld头验证format11链成员，保留原始链指针与cacheLevel/target，解析stub及有界vtable候选；没有将编码指针直接当VA。

GA3.3两个Hook符号的原始入口、相对偏移、首指令bytes与ABI说明在`analysis/hook-abi.json`和[HOOK-ABI-AUDIT.md](HOOK-ABI-AUDIT.md)。25G72注释/旧offset只列作历史参考，不参与本次身份验证。

全部Apple二进制、衍生反汇编和运行态私有信息仅保存在本目录，未公开上传。
