# Tahoe 安装停顿：公开案例核对

日期：2026-10-17。用户要求先联网查相同问题，再报告发现。

## 当前结论

检索到安装倒计时长期不动／安装循环的相似案例，**没有找到同时匹配
Elite Dragonfly G2、当前 Tahoe、并行解包最后记录99%的已解决案例**。
倒计时数值相近不等于故障原因相同。

本机实际证据见 `.local/install-prep/hp-install-stall-postreboot-20261017/`：
`restore.log` 在 Cryptex100%和签名对象验证后进入并行解包，最后99%；
`ia.log` 最后21分钟，无阶段完成／明确致命错误。没有停顿当时的进程采样和内核日志。

## 已读案例与适用边界

| 来源 | 实际报告／结果 | 与本机的关系 |
| --- | --- | --- |
| [EliteMacx86：Sonoma/Ventura剩18分钟，SOLVED](https://elitemacx86.com/threads/sonoma-and-ventura-installation-stuck-freeze-at-about-18-minutes-remaning.1557/) | 2023-12，HP Victus AMD、Crucial P3，Recovery安装；楼主第7帖称USB映射后解决，管理员第8帖确认关闭 | 有真实用户解决回报，但平台／系统／阶段不同。本机RHUB已恢复Recovery USB，不能据此认定安装阶段USB也完全正常，亦不能直接搬用其映射 |
| [Olarila：重启后苹果进度条29分钟循环](https://olarila.com/topic/30951-cant-get-past-the-%E2%80%9Cabout-29-minutes-remaining%E2%80%9D/) | 2022-11，Intel Comet Lake笔记本、Samsung MZVLQ512HALU；`-igfxvesa`无效，管理员怀疑NVMe，楼主同意但无更换后成功回报 | 接力阶段外观相近，实际为重启循环；是Samsung而非本机Micron，不能标成已证实的硬盘修复 |
| [EliteMacx86：Monterey剩18分钟](https://elitemacx86.com/threads/mac-os-monterey-freezing-at-18-mins-remaining.1847/)及[第二页](https://elitemacx86.com/threads/mac-os-monterey-freezing-at-18-mins-remaining.1847/page-2) | 2024-06，HP AMD／Kioxia，NVMeFix、配置调整和过夜等待未解决；另一个用户第15帖报告自己另一台Xeon因坏ECC内存停在15/16分钟，移除坏条后成功 | 原楼主未解决；旁人内存案例有BIOS内存告警，不是本机内存损坏证据 |
| [AMD OS X：Sequoia剩12分钟](https://forum.amd-osx.com/threads/installer-freeze-at-12-minutes-remaining.6279/) | 2025-12，7950X3D平台；移除其他磁盘未解决，多项配置调整后反而更早重启，没有成功回报 | CPU／平台不同，无直接可套用结论 |

以上论坛正文已通过webfetch实际读取。部分站点阻止本地HTML归档，公开摘记是转述，
不是原始页面归档；具体归档状态见下方sources.json。
Reddit检索摘要还出现12分钟停顿／等待后继续等报告，但正文403，未采作已验证解决办法。

## SSD型号核对与NVMeFix

- 本机库存实测型号：`MTFDHBA512QFD-1AX1AABHA`。
- [Micron官方同基础料号目录](https://www.micron.com/products/obsolete/obsolete-2210-ssd/part-catalog/part-detail/mtfdhba512qfd-1ax15abyy)
  将MTFDHBA512QFD归在**2210**产品线；目录后缀不是本机OEM后缀。
  [Notebookcheck具体基础型号检索页](https://www.notebookcheck.net/Micron-2210-MTFDHBA512QFD-SSD-Benchmarks.539951.0.html)
  同样标2210（此页仅检索摘要可读，本地正文403）。
- [Dortania存储限制](https://dortania.github.io/OpenCore-Install-Guide/macos-limits.html#storage-support)
  点名的是**2200S**、PM981和PM991；不能把2200S结论套到2210。
  此轮未找到2210同型号、同解包阶段的已证实不兼容／修复报告。
- [NVMeFix上游README](https://github.com/acidanthera/NVMeFix)明确支持至macOS26，
  但某些功能（如超时panic修复）在较新系统上可能不可用。
  [Changelog](https://raw.githubusercontent.com/acidanthera/NVMeFix/master/Changelog.md)
  的1.1.3增加macOS26常量。支持版本不等于能修复本机停顿。
- 本地读取实测RHUB配置：`Kernel.Add`没有NVMeFix；`SecureBootModel=Disabled`，
  boot-args已经有`-igfxvesa`。内置部署配置与该基线摘要相同。
  [Tahoe指南](https://dortania.github.io/OpenCore-Install-Guide/extras/tahoe.html#ota-updates)
  的SecureBootModel建议针对OTA；本机已Disabled，不构成新的可变实验。

## 下一步判断

用户先报告选择Recovery的Reinstall并推断联网取得26.7.1，实际日志确为26.7.1／25G241。
随后明确纠正：**我们应该离线安装给定版本。** 目标回到此前已准备的离线26.6.2／25G83；
即使在线Reinstall能解释26.7.1来源，它也不满足当前指定目标。已重新计算本地离线HFS
SHA并与manifest一致；Lexar上次完整回读收据相同。当前HP没插USB（最新NixOS lsblk），
p7仍保留XID226时的未完成26.7.1暂存，无完成证据。

1. 下一轮使用Lexar中的只读26.6.2 HFS映像及其中App，不能点Recovery图形界面的网络Reinstall。
   镜像上次USB全文件回读通过，但此次未重新插入／回读；用户需在现场Recovery启动前插回。
2. 清理当前部分26.7.1状态可能需要`startosinstall --eraseinstall`。已保存的26.6.2
   `startosinstall --usage`说明它清除安装目标APFS volumes，`--preservecontainer`保留容器内其他卷；
   对当前卷组的影响仍需逐项核实。执行前必须取得用户对清除部分安装的明确授权。
3. 获准后用户物理进入Recovery，挂载verified HFS并启动指定26.6.2 App的startosinstall；
   完成后以日志／SystemVersion核验build25G83。实时停顿诊断仍有用，但不取代指定版本。
4. 若指定离线版本也复现停顿，再依据当时进程／内核／I/O证据评估单变量候选。

针对上次26.7.1的日志，解包输入确实是内置APFS暂存包，USB不是那一stage的直接输入；
但用户现在要求**重新用离线26.6.2**，所以物理Recovery启动与HFS app来源都要用Lexar。
当前NixOS保持在线；本次研究未改动HP、USB、EFI、NVRAM、固件或分区，没有执行重装或VM。

网页归档／摘要清单：
`.local/install-prep/hp-install-stall-postreboot-20261017/web-research/sources.json`，
SHA-256 `6b2aba5f180107b18af5d14150945cc0d3d0540a516ebfa1119aabda09ebcd3c`。

## 首次设置的 Apple Account 转圈与鼠标无响应（2026-10-17）

用户照片（原件只在会话中）显示 macOS Setup Assistant 的 **Sign In to Your Apple Account** 页面，
有旋转指示器和 Continue；用户报告刚进入此页鼠标指针不动。停留时长、键盘响应与现场网络状态未知。

- [Apple Tahoe 26 Setup Accounts](https://support.apple.com/guide/macbook-pro/set-up-your-accounts-apd1c52f9d30/2026/mac/26)：
  如果首次设置时未登录 Apple Account，完成后可在 System Settings 登录。账号登录不是完成macOS基础设置的必要条件。
- [Apple：Setup 时键盘或鼠标无法连接](https://support.apple.com/en-us/108797)：
  可使用有线USB设备；第三方设备若有接收器也可直接插入。建议试 Recovery 中曾验证工作的外接USB鼠标，直插USB-A，不经Hub。
- [Tahoe 26.4 Setup wizard automation issue](https://github.com/cirruslabs/macos-image-templates/issues/342)：
  社区报告 Apple Account 页的次要按钮在26.4会打开菜单，含“Sign in Later in Settings”；UI文字/控件布局随build可能不同，非Apple支持文档，也不是本机实测。
- [OpenCore-ISO Tahoe Setup Assistant freeze](https://github.com/LongQT-sea/OpenCore-ISO/issues/37)：
  一个QEMU/无dGPU Tahoe案例在设置最后界面出现转圈、系统仍可ping、GUI无响应；维护者建议重启并推测缺GPU加速。**平台和步骤不同，不足以证明本机同因。**
- [Apple强制关机方法](https://support.apple.com/en-us/102586)是一般无响应Mac的操作说明；未专门保证此Hackintosh Setup Assistant步骤重启后的状态。另有旧苹果笔记本在Setup转圈案例建议可等待约30分钟，但年代很早、现象不同。

**当前判断／建议：**图中仍是首次设置界面，不是安装进度条；到达此页说明OS已启动到setup流程。刚进入时的旋转单独不能判定系统死机。先等几分钟，并试一次Tab看焦点是否移动；可用键盘时寻找“Set Up Later”或“Sign in Later in Settings”来跳过账号，完成桌面初始化后再登录。也可接回Recovery中已验证的有线USB鼠标。如果界面持续多分钟无响应，强制关机通常不会擦除已经装好的OS，但可能回到Setup Assistant并需重走未完成步骤；这不是已验证的绝对保证。当前没有建议再次安装、擦除、改NVRAM或改EFI。

联网来源通过Exa搜索／抓取和DeepSeek V4.1 Flash只读交叉审查；完整链接、差异与证据边界记录于本历史研究文档。原项目中的事件级编排记录未复制到公开副本。模型审查没有访问HP或改动项目文件。

## 最新更正：接受许可后白屏、仅鼠标可移动

用户说明当前重启后先接受软件许可，随后白屏但鼠标指针可移动；键盘响应和停留时间未知。这是Setup Assistant的另一个页面，与上一张Apple Account spinner照片分开记录。

- 最近似的公开案例是[OpCore-Simplify issue #463](https://github.com/lzhoang2801/OpCore-Simplify/issues/463)：Tahoe清洁安装后黑屏、鼠标可动，维护者/楼主后来归因为缺图形加速，楼主称修改图形设置后解决；环境是不同台式机，不是这台HP，不能直接照搬配置。[Issue #561](https://github.com/lzhoang2801/OpCore-Simplify/issues/561)和[Olarila白屏光标案例](https://olarila.com/topic/42814-macos-tahoe-hackintosh-it-stops-at-a-white-screen-with-the-cursor-activated/)也报告相似症状。
- 本机使用`-igfxvesa`，Metal/图形加速尚未验证，所以WindowServer/GUI合成问题是**有根据的假设，不是确诊**。不应据此马上改EFI或重装。
- [2026-06 Setup Assistant快捷键报告](https://settings.blog/en/accessing-terminal-and-system-settings-in-setup-assistant/)给出Control+Option+Command+T打开Terminal、Control+Option+Command+C打开Console。HP键盘可试`Ctrl+Alt+Win+T`（Win约为Command、Alt约为Option），但这是管理员博客的通用当前版本报告，未在本机Tahoe验证；白屏若不绘制新窗口，可能看不到Terminal。运行用户为非特权`_mbsetupuser`。
- [Apple Remote Login说明](https://support.apple.com/guide/mac-help/allow-a-remote-computer-to-access-your-mac-mchlp1066/mac)是在System Settings→General→Sharing中启用SSH。Setup Assistant尚未建立普通管理员账户，**当前不能可靠开启SSH或用hpdiag Recovery启动器来远控已安装系统**；完成本地用户设置并开启Remote Login后，才可能SSH连接。
- 因为已经到安装后的Setup Assistant、不是Apple logo安装写盘阶段，强制关机的主要风险是Setup流程未提交并重回某一步；OS通常不需重装，但没有Apple对本Hackintosh此画面的恢复保证。先等一会儿并试Terminal快捷键/外接有线USB输入；如长时间无响应，重启是物理恢复选项，不是远程命令。

来源/推断边界和当时的用户报告见本历史研究文档；最新项目状态见[公开续接入口](continuation.md)。
