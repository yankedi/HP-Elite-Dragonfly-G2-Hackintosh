# 不启动 macOS 的图形组件验证

**结论：可以继续做有价值的动态组件验证。** 上一阶段的“首次启动受阻”只阻挡整机验收，并不阻挡源码级逻辑测试、二进制接口审计或受控 ACPI 解释执行。

## 这次实际验证了什么

新增 `make nonboot-graphics`：在 Linux 用户态运行固定 framebuffer 补丁的**原始 C++ 方法**，不是只做编译，也不是另写一个映射算法替代被测实现。

流程是重新验证固定 WEG 归档和 0001–0003 补丁的摘要，解压到全新私有目录并依次应用，再提取 `TigerLakeRegisterMap` 类声明、`TGLReg` 和 11 个原方法。方法体保持原样；仅将私有成员开放给测试。MMIO 回调连接内存中的寄存器字典，IORegistry/NVRAM 调用连接计数器；不会访问真实设备或固件。

本轮 **7 组测试通过，执行 655,454 次断言**。断言数量主要来自寄存器地址扫描、DPLL fraction 遍历和 PWM 单调性扫描，不代表同数量的独立硬件场景。AddressSanitizer / UndefinedBehaviorSanitizer 均未报告错误。

| 测试组 | 实际检查 |
| --- | --- |
| CPU/参数门控 | `0x8c/0x8d` 与非 TGL model；缺省关闭；显式 `igfxtglmap=0` 优先于开关；背光上限参数边界 |
| 地址映射 | DP transport、eDP transcoder、DPLL golden vectors；相邻寄存器不误改；关闭映射时保持原地址 |
| 位域与舍入 | DDI/clock 位编码；有效域往返；DPLL 小数转换保留无关位，往返误差不超过一个 LSB |
| 实际 read/write | Lazy eDP 读激活；firmware PLL 保留；38.4MHz 参考时钟的小数转换 |
| 写入时序 | transcoder clock / function 必须先于 DP link enable；disable 不额外清除 clock/function；防止 active link 被零 clock 写入破坏 |
| PWM | 正亮度单调、有界、最小非零；零 duty 用于断电；重新 enable 时按序恢复保存的 duty |
| 发布开关 | 默认 mask 不触发发布；NVRAM opt-in 与预算；禁止中断时不发布（全部使用内存替身） |

Golden 地址与编码另外核对了 Intel 的固定 Linux v6.18 `intel_display_regs.h`，并非从被测函数计算期望值。来源、原文件/提取块/脚本/日志摘要保存在私有报告；可提交摘要见 [nonboot-graphics-check.json](../manifests/nonboot-graphics-check.json)。

## 证明测试能发现真实回归

另在私有副本注入两种故障，原始缓存和 kext 均未改动：

1. 将 DP transport 目标地址从 `0x60540` 错改为 `0x60544`，测试在 golden 地址断言处失败。
2. 吞掉 PWM 的零 duty 写入，测试在断电路径断言处失败。

两次故障构建均能编译，运行均在预期断言处退出 1。这说明测试可以拦住“编译/链接通过但关键行为错误”的组件级回归。

还有一个可离线发现的文档差异：上游 `ScaleBacklight` enum 注释仍写“never write a zero duty”，实际当前 `write()` 已明确把零 duty 传给设备，并在 PWM enable 后恢复亮度。本轮验证的是实际实现；不能依据旧注释重新加入“永不写零”的行为。

## 这些结果的精确边界

这是原始逻辑的 **host test**，没有把 macOS kext 加载进 Linux，也没有模拟完整 Intel 显示硬件。异步 trace、lateCheck 和线程执行被替换，未覆盖并发/锁/时序延迟。测试输入是合成的，尚不是本机 Apple framebuffer 的真实调用序列。

因此可以先排除地址计算、位域转换、零值边界和写入顺序中的一批错误；物理 eDP link training、PLL 锁定、HP PWM 电气行为、真实中断和 Metal 仍需要对应系统及硬件观察。完整 macOS 驱动与 kernel 的接口审计也需要精确 build 的系统组件，不能由本测试推出。

## 复跑

```sh
make nonboot-graphics
```

需要已有固定源码/补丁缓存，以及带 Linux sanitizer runtime 的 clang++。输入在 `manifests/framebuffer-patch-check.json` 中逐项锁定；每次运行写入新的 `.local/nonboot-graphics/run-*/`，保留编译、执行和故障注入日志。无需 SSH、U 盘、Apple SDK 或启动任何 macOS。
