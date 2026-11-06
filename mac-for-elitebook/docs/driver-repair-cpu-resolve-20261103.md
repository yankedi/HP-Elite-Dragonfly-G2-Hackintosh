# REPAIR6：恢复真实 CCS resolve 与 CPU 可见路径

## 已验证事实

- 固定上游仍为 `6f03560ef9694f9826caae15624d4a6cb1bf9ffc`，直接继承 REPAIR5 新基底。
- R5 的实际截图证明局部花屏；一次 R8 的 GPU copy 全部 16705 像素正确，CPU getBytes 全错。
- R5 的 NOCCS3 把 `IntelAccelerator::submitCCSResolve` 入口改成 `xor eax,eax; ret`。实际调用者 `IGAccelResource::submitCCSResolve` 在返回后无条件清除 dirty/resolve 状态。用户态 `resolveCCS` 返回 true 不证明 kernel 真正执行了解压。
- donor `resolve_ccs` 调用 `getBufferPtrNoInc(2)`，实际 Tahoe IOAF 只检查 **2 DWORD** 可用；不是“缓冲区索引 2”。随后 donor 从这个指针计算一整页的命令和状态，并且只把 cursor 推进到命令末尾。缺少完整容量检查，状态空间也可能被后续分配覆盖。
- 新鲜同 boot 日志还证实 uptime 941.246501 秒的 RCS hang。完整第一 reset 采集三项均 exit0；新报告只有一份 gpuRestart。日志有 `reset RCS ret=1`、`GPURestartEnd`，系统同 boot 继续运行；这证明恢复流程返回，不等于绘图恢复正常，更不是没有 hang。

## 候选修改

只改 `kern_gen11.cpp`、`kern_green.cpp`、`hp_repair_policy.hpp`：

1. 真 TGL/Tahoe 恢复实际 CCS resolve，保留原 compression/AUX 策略和 R5 的 ROW、rect、IOSurface、原生拓扑修补。
2. 每组至多 32 个矩形，完整预留经过验证的页内命令/状态空间；检查 rollover 后真实 backing、cursor、limit。
3. donor 写完后插入 PPGTT `MI_BATCH_BUFFER_START`，跳过非命令状态；cursor 前进至页内 `0xfc0`，避免状态在 GPU 读取前被复用，也不把状态当指令执行。
4. per-thread/nested scope 传播失败。调用者在失败时跳到 vector cleanup，保留 dirty 状态；资源入口返回 false。
5. 只有精确 donor 字节、IOAF helper 和全部 routes 就绪才激活。实测主机门控改为 CCS6 安装/实际提交证据，保留原像素失败历史。

## 本地验证与制品

`.local/driver-repair-20261103/repair6-cpu-resolve/` 保存源码、diff、构建、IMG 及全部收据。

- 实际 Mach-O donor emitter 原机器码在本地执行 **512 组**：32 组尺寸 × 16 组 global/可选 packet 分支；仅外部 pool/地址/memcpy 调用由本地替身绑定。命令不越界、不覆盖状态，binding offset 与真实状态偏移一致，页尾保留区未写。
- production layout predicate 全部 DWORD 边界、无效对齐/count/下溢检查通过。
- 无新增未定义导入，warnings 类别和数量与 R5 一致；签名页及 special slots 检查通过。
- 98 EFI 文件只有 NG 二进制变化，配置 SHA 保持 `7df7f1f674e485195bfb5e8c94779047976131e5da7b2b573e4043d181ac71fd`；匹配的 OC 1.0.8 ocvalidate、FAT 只读检查通过。
- IMG `HP-UPSTREAM-6F03560-REPAIR6-CPU-RESOLVE.img` SHA256 `e4e11c97576e75724519c8e522a1762676e8b7a1c2c449e5cfe649d5e95471a2`。
- NG SHA256 `3e2cdf8997a3d715874141892db1ee84c5729b4d8506dca1705c7f81940f07c1`，UUID `4C4C44A7-5555-3144-A196-E6B73D107542`。
- source diff SHA256 `f4ff3fe1fe6d52a794a9ee4222eb9a513d31fdd13bf6f6262c296da81e402d25`。

补充集成审计 `additional-integration-audit.json`：实际 AL guard 1024 输入执行通过；当前 IOAF `setBufferPtr` 恰为14字节（含尾部NOP），LongJump14不会覆盖相邻 `getGPUVirtualAddress`。后者实际机器码使用 backing GPU VA + CPU pointer - backing CPU base；与 submission start 无关。跳转 opcode 与固定 Linux 的 `MI_BATCH_BUFFER_START_GEN8 | BIT(8)` 一致。

这些是候选的本地验证，尚未证明 CPU、花屏或延迟 hang 修好。CCS 缺口是明确代码事实，但花屏与晚发 hang 的唯一因果仍待实机。

## 实测准备

测试前完整保存当前现场。为了进入下一候选，独立部署控制器在制品和采集就绪后可进行必要的系统切换；macOS 测试脚本不会在失败、完成或 reset 时自动回程重启。新的 R8 使用原可执行文件，仅扩展 tracer 读取本进程实际 locked backing；仍只有一次原 render/sync/copy command buffer。先核对像素/真实桌面，再按健康门控进行 Metal，并持续观察晚发 hang。

独立控制器 `deploy-and-test.py` 已启动：先完整回收当前同boot的nvram、dmesg、全部用户/root/system DiagnosticReports及进程状态；全部exit0后才请求部署阶段正常切换到NixOS。等待旧观察器的完整终态EFI/APFS采集及root补收完成，再新鲜核对USB旧98EFI/consumed target，交付/整图回读/武装R6并进入实测。阶段事件在 `deployment/events.ndjson`；不能把控制器启动当作已交付或已通过。
