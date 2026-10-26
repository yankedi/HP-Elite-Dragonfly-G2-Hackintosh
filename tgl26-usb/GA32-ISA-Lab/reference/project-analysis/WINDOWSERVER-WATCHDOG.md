# WindowServer watchdog 与系统重启（任务 H/I）

## 时间线（GA3.2b 启动 = 04:02:2x）

| 时间 | 事件 | 证据 |
|---|---|---|
| ~04:02:2x | GA3.2b 启动 | uptime 推算（记录 ms=51278 对应 04:03:21 的 gpuRestart） |
| 04:03:21 | GPU Hang #1（ctx6，BB 0x40b75ed8）→ THAG 记录 0（拒绝） | Kernel_...040321.gpuRestart |
| 04:03:40 | displaypolicyd SIGABRT（uptime 63s） | displaypolicyd-040340.ips |
| 04:03:41 | GPU Hang #2（ctx5，BB 0x426fe104）→ THAG 记录 1（成功） | 040341.gpuRestart |
| 04:03:41 | GPU Hang #3（ctx6，BB 0x435b8520）— 未采集（hangCaptured 已置位） | 040341-1.gpuRestart |
| 04:03:51 | GPU Hang #4（ctx5，BB 0x42ace74c）— 未采集 | 040351.gpuRestart |
| 04:04:22 | WindowServer watchdog 终止 #1（uptime 110s） | WindowServer-040422.ips + spin |
| 04:05:02 | WindowServer watchdog 终止 #2 | WindowServer-040502.ips + spin |
| 04:07:03 | 当前启动（GA32a）开始 | kern.boottime |

## 故障分类（任务 I）

1. **WindowServer 被 watchdog 终止**，不是崩溃：`termination.namespace = WATCHDOG`，
   indicator "monitoring timed out for service"；`reportNotes` 明示 watchdog 终止。
2. **watchdog 等待的服务**：`WindowServer` 主线程（"unresponsive work processor(s):
   WindowServer main thread"，40s 无 checkin）。
3. **主线程阻塞栈**（.spin 采样 12/12）：
   - 报告 1：`WindowServer → IOAccelerator +27287 → IOAcceleratorFamily2 ×2`
     （内核 IOKit 加速器调用路径），最后一次运行 30.9s 之前；
   - 报告 2：`WindowServer → SkyLight ×3`（框架内部路径），70.9s 未运行。
   两者都表明主线程卡在**图形提交/同步路径**，与 GPU hang 时间上直接相邻；
   IOAccelerator 内核路径阻塞与"GPU 引擎不完成"一致，但**未直接证明**因果。
4. **GPU Reset 与进程重建**：gpuRestart 报告成对出现（每次 hang 一份），
   WindowServer 在 hang 后仍运行 ~40-60s 才被判无响应；无 WindowServer 崩溃报告。
5. **`pgrep -fl WindowServer` 无结果**：在被 watchdog 终止后、未重启前进程确实不存在；
   当前 GA32a 启动中 WindowServer 正常（用户可 SSH、界面在）。
6. **自动重启**：无 panic、无 shutdown 日志、无 watchdog 重启标记；04:07:03 的启动
   与两次 watchdog 终止时间上连贯（后者支持"watchdog 触发重启"），但也与用户手动重启一致。
   **证据强度：弱到中等**（时间线一致，无直接因果记录；统一日志无权限读取）。
7. **Kernel Panic 证据：无**。`/Library/Logs/DiagnosticReports/` 中 4 份 `Kernel-2020-01-01-*.panic`
   均为 RTC 未设置时代的旧实验（早于 10-17 22:00），GA3.x 会话没有 panic 文件。
8. **displaypolicyd SIGABRT**：GA2b/GA3.1b/GA3.2b/当前 GA32a 启动均在 ~50-70s 后
   SIGABRT（EXC_CRASH, code 6）——**历史一致性行为**，非 GA3.2 回归。
9. **鼠标指针短暂显示**：指针由 WindowServer 绘制；在 watchdog 终止前它可能仍显示
   （介绍性帧/光标平面由 framebuffer 保留），其消失与 WindowServer 生命周期相关；
   本轮无直接截屏证据，标为弱证据。指针可移动说明 CPU/显示管线与输入路径存活，
   **不能**说明 GPU 3D 管线或 Metal 提交正常（软件光栅化下亦然）。
