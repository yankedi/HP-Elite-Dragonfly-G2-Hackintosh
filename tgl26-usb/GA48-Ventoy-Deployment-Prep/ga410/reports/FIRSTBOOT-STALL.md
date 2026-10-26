# 首次TGL实机启动失败：已取回匹配panic

> 后续更新：用户已授权直接修改，独立NG副本已启用原作者现有f13b并重建；下一次入口及实际交付以[R2说明](R2-NEXT.md)和`TGL-R2.json`为准。下面是该次失败与修复前状态的历史记录。

## 当前状态

**BLOCKED_REAL_ERROR：WindowServer打开TGL framebuffer时发生`__cxa_pure_virtual` panic。**
Recovery SSH已恢复，机器保持开机。没有重启/关机、恢复原驱动或再次注册KC。
原先FIRSTBOOT-STATE/HANDOFF-DELIVERY是首次启动前时点；本报告及FIRSTBOOT-PANIC.json为最新失败证据。

## 已保存的本次证据

1. 用户屏幕照片：NG framebuffer启动后，两次报`IGPU: Failing probe (-allow3d is NOT set in boot-arg)!`。
2. 内盘collector记录：boot session `REDACTED-SESSION-ID`，marker存在但未完成；只留下空identity输出。
   原始pax已回读NixOS，SHA256 `9996248809653e6f42d2f268f625e31f3804e932a947d89a8e373d42d43de959`。
3. 新OC日志`opencore-2020-01-01-000104.txt`，完整原始262144字节已保存；末尾NUL属于预分配。
   原始SHA256 `03b5d8654b81c18e89bcf01e61bf498e9ade8ac3079d1b269d6e1277fd4b2ac9`。
   明确记录本次NG boot-args及AMFI参数，缺少`-allow3d`与`-disablegfxfirmware`；boot.efi输出CSR为`0x243`。
   配置Add是0x203，两者有0x40差异；未捕获实际kernel CSR，不能声称实测runtime值是0x203。
4. 当前Recovery NVRAM中`aapl,panic-info`为4781字节packed 7-bit ASCII。
   解码后匹配本次NG boot-args、25G83、内核UUID及已安装FB/HookCase UUID；7-bit编码逐字节回环一致。
   原始payload SHA256 `ed531603e29f9d40aa275631b79f404c3e5fd883a164e87c5812cf836e37a0b6`。
   解码文本SHA256 `daa5ebde3d65d26d86b0596e329889c21929a43836eb26cadc55619723531b03`。
5. `.contents.panic`是较早的WEG/lilucpu/igfxtgl参数记录，**不作为本次NG故障证据**。
6. 新TGL镜像只增加上述OC日志，全部EFI文件及原有载荷哈希保持一致。

## 真正的崩溃点

```text
panic(cpu 2 ...): __cxa_pure_virtual @OSRuntime.cpp:103
Panicked task ... pid 197: WindowServer
AppleIntelPort::probePortState() + 0x207
AppleIntelBaseController::enableController(...) + 0x12c
AppleIntelFramebuffer::enableController() + 0x10d
IOFramebuffer::open()
```

uptime约43.779秒。FB UUID `B96A8448-9D17-3F78-B76D-15A0B359A9A0`，HookCase UUID `4C4C4459-5555-3144-A1DA-AC5685822B59`。
这证明这两个匹配组件实际进入了内核；不等于正常签名信任或完整驱动栈成功。
照片上缺少allow3d是另一项已确认错误，**仅补它不能视为本次panic的已验证修复**。

## 对应的原作者现有代码

固定基准`6a1afb337d1fb1ff07ca032b5c1868fe2bd005ef`已经包含`f13b/r13b`，应用行被注释。
当前GA47 `src/NootedGreen/kern_gen11.cpp:1453–1454,1603–1605`同时声明：不应用会在probePortState中pure-virtual并于WindowServer enableController时panic。

- f13b：`ff9090010000498b0e4c89f789c6ff9138010000`
- r13b：`c7c001000000498b0e4c89f789c6ff9138010000`
- 本机FB唯一匹配文件偏移`0x2eb0b`；probePortState符号文件偏移`0x2e90a`。
- 差值`0x201`，其中虚调用指令长6字节，返回位置**正是panic的+0x207**。
- 已发布AuxKC中相同原始模式也唯一存在。

以上是精确源码/二进制/实机三方匹配，不是只凭末行猜测。
**尚未改动GA47源码、驱动二进制或AuxKC**。此前“不改驱动功能源码”的约束仍适用；启用原作者这一现有旁路需明确变更该约束，不能偷偷当成纯boot-args修正。

## 已做的可逆准备

- 参数候选R1追加`-allow3d -disablegfxfirmware`，221字节；同版ocvalidate、mtools EFI回读及原生完整清单/哈希通过。
- 在NVRAM panic解码后，该R1被标为**HOLD**，没有提供为可启动修复版本；它未启用f13b，未物理启动。
- 原collector输出及marker归档后，将marker移为`.failed-91FA7AAF-AE29-486E-BEE5-7F946FF512B9`，保留原文件；新collector增添命令前后progress标记，优先收集kernel args。
- Recovery恢复工具修正“MountPoint存在但为空”的实际分支，成功挂载原Preboot并采集；不是修改磁盘/卷布局。
- 完整备份22项、组件204项、当前AuxKC及其余原KC再次校验通过。

## 下一步

保持当前Recovery与SSH。暂不重复原TGL或R1启动。
下一项针对性修复是：在独立NG实验副本启用**原作者现有f13b**并完成重建/签名/镜像验证；不是重新研发驱动，也不是扩大SIP/AMFI或重做KC。
本轮已完成日志提取、确定崩溃指令和参数候选，f13b功能变更尚未应用。

当前SSH连接仍使用`SSH-ACCESS.md`中的专用Recovery2222身份，无需重新设置密码/密钥。
本轮新增手册与原始证据保存在`/Volumes/TARGET_VOLUME/GA410-Stall-Repair-20261023/`及目标Data同名工作子目录。
