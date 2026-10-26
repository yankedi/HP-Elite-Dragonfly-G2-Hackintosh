# GA415 PLANES2：25G83 IOSurface 除零 panic 修复镜像

## 核实结果

这次 panic 的故障指令是 Apple TGL 驱动的 `0x72bcd: div r15d`，
寄存器 `R15D=0`，触发进程为 `AvatarPickerMemojiPicker`。
详见 [死机取证报告](reports/FREEZE-20261024-175953.md)。

从目标机取得的 **25G83 KDK IOSurface** 与实际加载版本的 x86_64 UUID
均为 `8E1FFEDA-8C53-336F-B59B-776024E3B66D`。其
`IOSurface::getPlaneCount()` 在 `0xa774` 明确读取 `[rdi+0x98]`。
旧 TGL 驱动的对应函数在 `0x7287d` 读取 `[rbx+0xb0]`。

GA414 已签名的 NootedGreen 包含上游 `XE-PLANES2`，将这一次读取从
`+0xb0` 改为 `+0x98`，但原启动参数 `-ngreennoplanesfix` 关闭了它。
本次复用该补丁，使用实际 plane count，保留双平面/YUV 路径。

## 修复产物

```text
HP-Tahoe-TGL-GA415-PLANES2.img
```

以已验收 NOAUX 的 GA414 镜像为基线，唯一文件变化为
`EFI/OC/config.plist`，唯一配置变化为移除 `-ngreennoplanesfix`。
镜像中的 OpenCore、所有 kext、NG 签名和依赖均与 GA414 逐字节相同。
OpenCore 原配置的 `NVRAM/Delete/boot-args` 保留，避免继承旧禁用参数。

核验脚本及记录：

- `tools/verify-planes-abi.py` → `reports/PLANES2-ABI.json`
- `tools/make-planes2-image.py` → `reports/PLANES2-IMAGE.json`
- `tools/deliver-planes2-image.py` → 成功交付后生成 `reports/PLANES2-DELIVERY.json`
- `tools/planes2-cpu-layout.m` → 本机 CPU-only 非平面/双平面布局检查
- `tools/audit-planes2-delivery.py` → 交付后的独立离线证据审核

CPU-only 布局检查已在 HP 原生编译并运行：BGRA 的 plane count 为 0，
420v、420f 均为 2，各 plane 宽高、BPR 与 element size 有效。
这验证当前系统的合法布局，尚不代表修复补丁已在内核运行。

## 启动与验收

在交付完成后，由用户重启，在 Ventoy 选择 **GA415-PLANES2** 镜像。
这不是当前的 R6 镜像；也不是未开启 PLANES2 的旧 GA414 镜像。

启动后先只读取身份和日志，确认：

1. NG UUID 仍为 `4C4C44E9-5555-3144-A1E4-CB51FF5A72E6`。
2. 启动参数有 `-ngreentgltahoe`，没有 `-ngreennoplanesfix`、
   `-ngreenplanesxor`、`-ngreenxefix`、`-ngreenccs`。
3. `XeNG PLANES2: ... IOSurface+0x98: aplicado`。
4. GA414 NOAUX 的身份门槛、pre/postflight 和 NOCCS3 仍通过。
5. 无新的 panic、GPU reset、WindowServer 异常。

身份核实后，在用户在场并批准的情况下，再有限次检查头像选择器和
普通/双平面 IOSurface 资源。不要直接套用绑定旧 boot session 的
GA415 A/B/C runner；不能把启动日志或 API success 当作像素与稳定性验收。

## 实机验收更新

已启动新镜像并核实 PLANES2、NOAUX、NOCCS3 命中。修复前 R6 的同一次
设置导航已经取得新 panic 和 NVRAM 证据，确认 `0x72bcd / div r15d / R15=0`。
修复后相同脚本正常完成，进一步打开了 Memoji 面板，观察 308.619 秒后仍为
同一 boot session、同一 WindowServer/MemojiPicker PID，没有新增相关诊断。

当前结果：**`PLANES2_TARGETED_PANIC_RETEST_PASS`**。
Memoji 缩略图和桌面花屏仍存在，像素正确性与长期稳定性未通过验收。
详见 [实机报告](reports/PLANES2-RUNTIME.md) 和 `reports/PLANES2-RUNTIME-RESULT.json`。
