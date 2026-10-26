# HP RTC 提示照片：错误005已确认

2026-10-25，用户在准备切换NixOS的上下文中提供开机自检照片。图像来源为会话附件，未将其声称为已经另存的本地图片文件。

## 照片可见文字

> 开机自检错误
>
> 系统时间无效。这可能是因为电池供电不足所致。
> 请使用操作系统设置正确的时间和日期。如果仍然显示此消息，
> 您可能需要更换板载电池。
>
> 实时时钟电源丢失（005）
>
> ENTER - 重启系统

照片明确提供此前缺少的错误码与原文。该画面不是502/CMOS checksum提示；不能把005直接记为校验和错误或据此断定DisableRtcChecksum能解决。

## 官方对照

HP官方《Resolving diagnostic errors that are displayed during startup》：
<https://support.hp.com/in-en/document/ish_6904096-6904147-16>

“Real-Time Clock Power Loss (005)”说明系统时间无效、时间日期未设置；可能来自电池供电丢失，反复出现时可能需要更换CMOS/RTC电池。措辞为可能性，而不是对这台机器电池故障的实测确认。

## 证据边界与后续

后续用户明确要求排除电池故障路线，已进入NixOS；采集到内核早期`rtc_cmos`将系统时间设为`2020-01-01T00:00:47 UTC`，见`GA416-LINUX-MEMORY-RESULT.md`。后续以软件／固件状态影响为排查方向。

再后一次“Linux→OC内存诊断→Linux”启动，早期`rtc_cmos`读到正确的`2026-10-25T13:26:58 UTC`。这是新启动对照，不证明具体macOS写入者、POST005不存在或已修复；见[OC诊断实测结果](GA416-OC-MEMORY-DEBUG-RESULT.md)。

- 已确认固件实际报告RTC/时间无效，不能仅用UTC与本地时区差解释这张照片。
- 不能从照片独立证明发生了物理断电、RTC电池坏、macOS写坏RTC，或OpenCore与panic同因。
- 用户此前报告“每次macOS后再开机会出现”，可把软件/固件状态干扰列为候选，但仍需同供电条件下非macOS启动序列对照。
- 已有同boot由2020校到2026的日志与此现象一致；网络校时后的RTC读数不等于开机前原始状态。
- 下一步仍为用户手动经正常Linux入口进入NixOS后只读采集RTC、BIOS、EFI内存图。照片本身不代表已经进入NixOS。
- 未改BIOS设置、RTC、EFI/NVRAM，未执行任何远程重启或电池处置。
