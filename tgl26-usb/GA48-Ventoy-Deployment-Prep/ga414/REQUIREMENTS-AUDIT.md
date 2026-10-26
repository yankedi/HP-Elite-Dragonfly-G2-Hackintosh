# GA414 需求—证据核对表

本次验收的是作者 NOAUX 单因素实验和核心 R8 结果；桌面修复与长期稳定性没有被替换为构建／像素成功。

| 要求／门槛 | 实际证据／状态 |
|---|---|
| R6唯一基线、仅ga414、完整源码diff | `R6-SOURCE-INVENTORY.json`、`SOURCE-AND-DONOR.json`、`patches/GA414-NOAUX-vs-R6.patch`；27文件仅kern_gen11.cpp变化 |
| 原const数组与18字节pattern，仅75 0b→90 90 | source审计、`GUARD-TESTS.json`真实constructor 18-byte/count1；实际donor全文件唯一 |
| native精确HP/9A49/CPU/subsystem/25G83、保留非native、once/count/error、-ngreenccs | 完整diff、22项guard；`RUNTIME-BOOT.json`真实gate1/first1/pre1:0/post0:1，bootargs无禁用参数 |
| 不扩大RPL大分支、不NOTCF/BLIT16/RCPOLICY、无R7/整套xefix | 非NOAUX源码逐字比对、其余26文件hash相同；真实启动参数 |
| 保留R2/R3/R5/R6/NOCCS3/XE-FMT/整个系统栈 | source审计、`BUILD.json`、`DELIVERY.json`系统栈/KC前后hash；运行NOCCS3、80EU10SS、R6pool日志 |
| native NODEPTH保持R6未启用并报告作者建议差异 | BUILD/FINAL-REPORT明确说明，未增加第二功能变量 |
| 真实kext/MachO/符号/UUID/功能段 | `BUILD.json`、private真实build/native-signed产物；UUID4C4C44E9...72E6 |
| 原生ad-hoc strict/deep codesign，签名功能段/UUID不变 | `NATIVE-SIGNATURE.json`与真实SSH收据；native image-mounted再次strict/deep验证 |
| 实际25G83 16.0.32 donor，不硬套25G241偏移 | SOURCE-AND-DONOR：短版16.0.32/bundle16.0.2，SHA14e21de5...71393，函数0x73fc2/pattern0x73fc6，离线只变2字节 |
| KC依赖不变/既有系统栈 | plist完全相同、无新增undefinedimport、系统栈/AuxKChash不变；legacy pseudo-library缺枚举明确记录，不冒充新resolver验证 |
| 从封存正确R6新建独立IMG、不覆盖四旧镜像 | `IMAGE-LOCAL.json`、`DELIVERY.json`旧镜像前后hash；本地封存IMG SHA1f973605...1401bd |
| OC1.0.8 ocvalidate/Enabled路径依赖顺序版本 | IMAGE-LOCAL/DELIVERY；校验rc0、匹配固定OC包；外部Apple provider及继承legacy consumer明确记录 |
| FAT/分区/只读/逐文件/全图/sync复核 | DELIVERY-AUDIT验证62记录/100文件；仅NG executable变化，FAT -n rc0，MBR相同；native readonly回读及sync后二次hash相同 |
| 指定Ventoy ISO/linux目录，新文件 | 同盘USB接HP，用`/Volumes/TARGET_VOLUME/ISO/linux/`，卷UUID固定；Linux预期挂载路径如实说明 |
| 不改内部EFI/默认引导/驱动/AuxKC/安全配置 | 配方及全部真实命令收据，无安装/重启/切引导；仅隔离tmp与新USB文件写入 |
| 用户在场手动启动，新UUID/HP/25G83/组件 | 用户“好了”确认后实际SSH；`RUNTIME-BOOT.json`及identity，session463849A7...1A35 |
| NOCCS3+NOAUX实际命中、80EU10SS、panic/WS/SSH/reset门槛 | runtime dmesg和health pre/post/delayed；无本boot新诊断；空unified查询不当命中证据 |
| 一次GA412 legacy原用例/同shader/顺序/pitch/lifecycle/getBytes/tracer | 相同原二进制hash、独占once ledger+remote claim；`R8-RESULT.json`单CB；未重编或重签probe |
| input/gpu/cpu/expected独立、CB真实status/error/时序 | private/r8-legacy-capture 9文件、result/command/probe日志；CBstatus4无error，GPU先冻结再getBytes；原verifier检查inode/尺寸/时序 |
| 全图三组diff/hash、独立expected、PASS严格条件/GPU回归 | 原verifierrc0+第二种packed比较：三组0错；full/activehash齐全；无copy回归 |
| timeout/reset/hang停止、不重试 | 本次无这些故障；实际一次GPU命令，未循环；前置unsignedprobe检查停止发生在once claim之前，不计GPU重试 |
| R8 PASS后才检查桌面/日志，无压力测试 | desktop命令均晚于唯一R8完成；Dock/Finder/WS+IOAccelerator+现有WS日志；一次screenshot尝试失败，原回执保留 |
| 截图与实际屏幕、图层/图标图片 | 实屏用户明确仍花屏；SSH screenshot失败，无法独立做视觉定位/同屏比较；未宣称截图正常或scanout已定位 |
| 新RCS/PIPE_CONTROL+0x7e4/gpuRestart改善 | 当前dmesg/fault query无相应记录、诊断无本boot新增；短窗口，改善/长期消除UNVERIFIED |
| PASS但仍花屏分开处理 | `PIXEL_PASS + DESKTOP_ARTIFACTS_REMAIN`；后续独立IOSurface/Blit/合成/scanout边界，未制作下一轮镜像 |
| R8 FAIL分支、直接AUX/dirty/locked backing | 本次PASS，FAIL分支不适用；逐资源kernel AUX/CCS/dirty仍NOT_OBSERVED，用户态raw不冒充内核状态 |
| 无叠加/NOCCS3返回修改/清dirty/自造resolve/ABIhook/PIPE_CONTROL修改 | 本轮运行只复用原probe/tracer和只读检查，无新驱动功能变化 |
| 镜像/hash/diff/kext/全部验证/运行/像素/恢复/本地commit | BUILD/FINAL-REPORT、各reports、private原件、BOOT-HANDOFF；构建9e9b9f5，运行证据后续本地commit；未push |
| 状态分层 | 交付时BOOT_NOT_TESTED保留；本次更新IMAGE_BUILT/NOAUX_RUNTIME_CONFIRMED/PIXEL_PASS/DESKTOP_ARTIFACTS_REMAIN/STABILITY_UNVERIFIED |

证据复核命令（离线，无GPU提交）：

```bash
python3 ga414/tools/audit-source-and-donor.py
python3 ga414/tools/audit-delivery.py
python3 ga414/tools/summarize-runtime.py
python3 ga414/tools/audit-runtime.py
```

运行入口 `run-r8-once.py` 已有本轮独占记录，**不是**复核命令；不能为重复得到PASS再次执行GPU。
