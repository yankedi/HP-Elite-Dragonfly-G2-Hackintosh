# GA420C：保留屏幕，CPU软件渲染桌面的对照候选

**首次实机验收已通过：用户进入桌面，实际IONDRVFramebuffer/1920×1080，完整kext没有TGL/HookCase/NGreen，且没有实际IntelAccelerator服务。** 全量日志持续采集中，稳定性尚待观察。实际证据`SOFTWARE-TRIAL-01.md`与`reports/SOFTWARE-RUNTIME-01.json`；下方“未测”保留为候选制作时边界。

## 用户目的

用户：“你让cpu硬算图形就行了不要关闭图形显示啊，已到nixos”。保持正常可见桌面，接受卡顿，让CPU执行软件渲染，观察之前的内存panic是否仍出现。不是关屏测试，也不是测试没有桌面的系统能否不panic。

## 启动

用户手动从Ventoy选择 **`ISO/linux/HP-Tahoe-GA420C-CPU-SOFTWARE-DISPLAY.img`**，在OpenCore中选择已有**macOS系统卷**。不要再次选择名为GA420的EFI/引导卷。到桌面后先告诉代理，核对运行时软件渲染路径后开始全量日志。

## 本次机制

- 内部GA419所有非图形配置与驱动继续保持，EFI移除NootedGreen，保留原GA419中已有的同字节WhateverGreen1.7.1并启用。
- 移除A/B两次均实测Unsupported的三个Kernel Block条目，不再依赖该失败路径。
- 核显仍作为VGA设备存在；保留ACPI、PCI class/BAR和固件已建立的扫描输出，不加disable-gpu、不用wegnoigpu、不执行_OFF/设备关断。
- 将本次启动核显`device-id`软件报告为不受支持的`0xffff`。真实硬件不变；WhateverGreen的PCI ConfigRead16/32钩子使驱动读取和IORegistry属性保持一致，防止两个实验TGL驱动按原0x9a49匹配设备，留下固件基本帧缓冲供软件桌面使用。
- 固定GA419完整IORegistry原件里，TGL framebuffer的PrimaryMatch只有ff20/9a49/a7a0，accelerator只有9a49；两者均没有ffff匹配项。构建器实际读取并验证这两条运行时personality，非仅参考上游plist。
- `-igfxvesa`作为WhateverGreen禁用Intel加速的补充guard；不把它单独当作可拦截自定义TGL的保证。**本次防止自定义TGL接管的主要机制是PCI匹配隔离。** WhateverGreen1.7.1的Intel模块并非自定义TGL插件。
- 标记`ga420csw=1`；不改系统端TGL/Metal文件或KC，不改SIP/AMFI/RTC/外围等其他变量。

源码核对：固定WhateverGreen1.7.1 `kern_weg.cpp`的processBuiltinProperties和wrapConfigRead16/32；`kern_start.cpp`允许到Tahoe；`kern_igfx.cpp`的igfxvesa guard。原件本地`private/weg-source/`。

## 验收

这是尚未实机验收的软件渲染**候选**，不保证Tahoe在当前安装上一定能回退软件桌面。

1. 有效标记，核显仍发布为VGA设备且device-id是ffff；
2. 可见桌面、能交互；完整IORegistry看到固件基本显示/AppleEFIFB路径，实验TGL framebuffer/IntelAccelerator不attach；
3. 完整kext列表、显示system_profiler与IORegistry确认没有可用Intel GPU/Metal加速；同时记录HookCase是否仍加载。若HookCase仍独立加载则不能称整个图形内核补丁栈均已清除，需要明确控制范围；
4. 仅桌面卡顿不算失败；以相似工作负载和同样无过滤无时长/大小上限日志记录原类内存panic是否出现。先观察20–30分钟，再继续更长时间，短期不崩仍不能独立证明根因；
5. 若仍无桌面，先取本次日志与图形加载证据，不把启动故障等同原内存panic。

回执：`reports/BUILD-SOFTWARE.json`、`reports/USB-DELIVERY-SOFTWARE.json`。原六份镜像、内部EFI、Ventoy分区/固件变量保持；重启由用户操作。
