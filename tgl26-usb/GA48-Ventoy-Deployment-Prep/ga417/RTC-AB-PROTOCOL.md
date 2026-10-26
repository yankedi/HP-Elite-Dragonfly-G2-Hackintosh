# GA417 RTC 单因素 A/B 观察

本轮镜像已离线通过 ocvalidate 1.0.8、FAT、全部文件回读和临时副本回退验证；**尚未实际启动，也未证明能消除 POST 005**。

## 两组与回退

- **A：** Ventoy 原 `ISO/linux/HP-Tahoe-GA416-L3-6.img`，`DisableRtcChecksum=false`。
- **B：** 新 `ISO/linux/HP-Tahoe-GA417-RTC-CHECKSUM-ONLY.img`，唯一变量 `Kernel/Quirks/DisableRtcChecksum=true`。
- 两组均使用原 Metal，保持 GA416 L3=6、80EU/10SS、NOAUX、NOCCS3、PLANES2、R6/R5、Framebuffer 及完整图形组件。Metal 修复包另存，不在这轮安装。
- 回退由用户下次启动直接选 A；内部 EFI 不改。独立原配置 `config-GA416-ROLLBACK.plist` 也已保存；无需为了回退写内部 ESP。

## 每次由用户手动完成

1. 使用相同供电、启动路径和预先约定的短时空闲场景；记录所选镜像、真实日期和 UTC 时间、开始时 RTC，以及 BIOS 是否已显示 005。若初始 RTC 不可比较，标记本次不适于 A/B；不要暗中写 RTC 纠正样本。
2. 选 A 或 B 进入 macOS。记录 boot UUID、实际 config 来源、RTC/系统时间和有无联网校时；若出现卡死，不追加负载，由用户决定如何结束。不要把强制关机混为系统主动重启。
3. 用户结束 macOS 后，下一次 POST 立即记录 **005 是否出现及准确文字/照片**，照片若只发会话须标明。随后**直接启动 Linux**，避免中间 Windows/macOS 或重复诊断启动改变 RTC 状态。
4. 立即做一次只读采样，保存当前 boot ID、完整 `dmesg` 中早期 `rtc_cmos` / `setting system clock` 记录、`/sys/class/rtc/rtc0/{date,time,name,since_epoch}`、`timedatectl status`、本次 `systemd-timesyncd` 日志及采集 UTC 时间。早期内核时间才是联网校时前证据；采样时的正确系统时间不能代替它。
5. 采用相同初始 RTC 条件再比较另一组。按尝试顺序记录失败/未完成试次，保留原始日志；一次 B 未报错仅算一次观察，不是长期有效证明。RTC 试次结束后再单独考虑 Metal。

远程恢复连接后可由代理一次采样；用户无需手工输入长命令。采样不调用 `hwclock --systohc`、`timedatectl set-*` 或任何 RTC/NVRAM 写操作。若日志不可读，记录权限缺口，不以较晚的已校时数据填补。

## 记录模板

| 项目 | 值 |
|---|---|
| 试次 / A或B / IMG SHA256 | |
| 初始真实UTC / RTC / 供电 / 既有005 | |
| macOS boot UUID / 进入退出方式 / 空闲时长 | |
| 下一次 POST005 / 照片来源 | |
| 直接 Linux boot ID / 早期 rtc_cmos 原文 | |
| 当前RTC / 系统时间 / 网络校时记录 | |
| 是否可比较 / 意外操作 / 原件路径 | |

既有自然对照：macOS 后 Linux 早期 RTC 为 `2020-01-01T00:00:47 UTC`；Linux→OC诊断→Linux 为 `2026-10-25T13:26:58 UTC`。这是启动序列差异，未确定写入者；005 也不是 502 checksum 错误。用户已排除电池故障路线，继续调查软件/固件状态影响。RTC 与 Panic 的因果关联仍未证明。

镜像 SHA256：`22a6656cc3e5af03439a7ed1145063351e6c538bc5384adecb7ca263029f44cc`。
原 GA416 封存镜像 SHA256：`46588464684092a8d9374de2341f51e5b80e5632870bcdac981540d4b97955c7`。
