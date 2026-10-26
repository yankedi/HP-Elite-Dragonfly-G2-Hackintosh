# GA420：无实验图形栈的内存 panic 对照引导

**GA420C已进入桌面并验收基本显示/实验GPU栈未运行，稳定性对照正在进行。** boot`REDACTED-MACHINE-ID`，1920×1080，实际`IONDRVFramebuffer/.Display_boot`，TGL framebuffer/accelerator、HookCase、NGreen均未加载，无实际IntelAccelerator；WEG1.7.1存在。全量流`all-debug-20261026T172026Z`正在持续，不能因会话结束停止。见`SOFTWARE-TRIAL-01.md`、`reports/SOFTWARE-RUNTIME-01.json`。下面“C尚未启动”仅交付历史；运行时成功不代表长期稳定性或图形因果已证明。

**最新用户要求：保留屏幕和正常桌面，CPU软件渲染，允许卡顿。请用GA420C候选：`ISO/linux/HP-Tahoe-GA420C-CPU-SOFTWARE-DISPLAY.img`。** A的Exclude和B的Disable均实测三项Unsupported，均未建立有效对照。C不再依赖Kernel Block，保留固件显示，通过不匹配的PCI device-id及原WEG1.7.1虚拟配置读取避免TGL接管，附igfxvesa guard。没有GPU关断。C已USB独立回验，尚未启动，实际桌面和软件渲染必须验收。见`GA420C-SOFTWARE.md`、`reports/SECOND-TRIAL-ANALYSIS.json`、`reports/BUILD-SOFTWARE.json`和`reports/USB-DELIVERY-SOFTWARE.json`。下面A/B操作与“当前”均为历史，不再建议原样重复启动。

**当前请测试GA420B：`ISO/linux/HP-Tahoe-GA420B-NO-GRAPHICS-DISABLE.img`。** 初版三个Exclude全部实测Unsupported，对照无效；B版改用KC-aware Disable，已独立USB回验，尚未启动。操作与验收见`GA420B-DISABLE.md`。本页下面GA420初版配置和路径保留为历史，不再建议原样重复启动。

用户授权制作并放到HP U盘测试。以当前内部GA419的完整OC为基线，保留触控板/蓝牙/电池/Wi-Fi/RTC等配置，独立启动相同macOS安装。

**首次实机结果：用户报告停在verbose画面，两次macOS SSH均不可达；未到桌面，实际图形排除尚未核验。** 详见`FIRST-TRIAL.md`。本次尚不能作为内存panic的有效无图形稳定性对照；下一步由用户手动回NixOS提取本次引导日志/可能的固件panic。

## 启动

1. 用户手动重启，选择HP上的Ventoy U盘。
2. 在Ventoy选 **`ISO/linux/HP-Tahoe-GA420-NO-GRAPHICS.img`**。
3. 在新OpenCore中选择已有macOS。请不要选择内部硬盘GA419入口，那是原图形组合。
4. 到桌面后先告知代理，以便验证本次boot和开始全量日志采集，再进行日常操作。

本轮预期使用固件基本显示，动画/视频可能明显变慢。不是Metal加速测试，不通过亮度或图形性能判断本轮成败。

## 图形隔离

- EFI中删除NootedGreen、原本已禁用的WhateverGreen目录和注入项。
- 移除TGL平台属性与NGreen/IGLogLevel/allow3d/disablegfxfirmware参数。
- 加入启动标记`ga420nogfx=1`。原NVRAM boot-args Delete+Add和WriteFlash=false保持。
- 使用OpenCore1.0.8 `Kernel/Block`、`Strategy=Exclude`排除系统缓存中的两个TGL驱动及其共同依赖HookCase：
  - `com.xxxxx.driver.AppleIntelTGLGraphics`
  - `com.xxxxx.driver.AppleIntelTGLGraphicsFramebuffer`
  - `org.smichaud.HookCase`
- 既有GA419运行时HookCase引用计数2，其两个已知消费者就是这两个TGL驱动；按依赖闭包同时排除。官方说明Exclude会删除缓存条目/代码，不能只排除仍被其他驱动依赖的provider。
- 这不是仅设置`-igfxvesa`：该参数通常需要WhateverGreen处理，本镜像没有加载WhateverGreen。
- macOS磁盘上的TGL/HookCase/Metal文件与AuxKC仍保留。新引导实施启动期排除，真正是否停用必须由本次运行时证据确认。

OpenCore文档：<https://github.com/acidanthera/OpenCorePkg/blob/1.0.8/Docs/Configuration.tex>，Kernel Block/Strategy。Context7官方仓库文档已复核。

## 有效试次验收

代理先收集有效boot-args、新boot UUID、完整加载kext、完整IORegistry与图形system_profiler，确认：

1. `ga420nogfx=1`生效；
2. 无NootedGreen/WhateverGreen、TGL framebuffer/accelerator及HookCase加载；
3. 无IntelAccelerator服务/Metal设备，基本显示和SSH可用。

若仍有实验图形组件加载，本次不能计作“无图形对照”。只有启动成功、观察数分钟不能证明修复。之前四次失败约4.2–5.7分钟；先观察至少20–30分钟并记录实际工作负载，再继续较长时间；短期不崩不等于排除低频故障。若再次卡死，保留末屏，用户手动回NixOS取固件panic，无需反复进入macOS。

全量日志仍按用户要求先无过滤传到开发机、无时长/大小限制保存，之后本地筛选。观察时长建议不会让采集器自动停止。

## 回退与验证

切回内部硬盘 **`macOS (GA419 peripherals test)`** 或原GA416/GA417镜像即可选择原组合。GA420是新增文件，不替换原镜像。交付时记录并核对内部ESP、固件Boot/Loader变量、分区表、Ventoy EFI分区和四个原IMG前后哈希。

构建验证：OpenCore1.0.8 ocvalidate、全部启用路径/插件依赖、ACPI校验和、MBR/分区边界、全新FAT及全文件回读。USB交付独立只读loop挂载、fsck和逐文件/整IMG SHA复核。回执位于`reports/BUILD.json`、`reports/USB-DELIVERY.json`；这些静态检查不冒充实际启动通过。
