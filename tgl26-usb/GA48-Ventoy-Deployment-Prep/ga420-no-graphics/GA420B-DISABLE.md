# GA420B：无实验显示驱动的稳定性对照

**首次反馈：用户报告再次停在verbose，macOS SSH超时，尚未核验本次启动来源/Disable结果。** 见`SECOND-TRIAL.md`；当前不能计作有效稳定性对照。等待用户手动回NixOS取本次引导日志后再决定修订。

## 测试目的

用户明确：安装显示驱动修复前没有这些panic，即使显示卡顿；本轮要用**没有实验显示驱动运行、画面可以卡顿的基本显示**，观察相同工作负载下原pmap/链表等panic是否还出现。卡顿本身不是失败。先验证驱动停用，再记录稳定性，不能拿未到桌面的失败启动代替有效对照。

## 选择新镜像

用户手动从Ventoy选择 **`ISO/linux/HP-Tahoe-GA420B-NO-GRAPHICS-DISABLE.img`**，OpenCore中选已有macOS。到桌面后告诉代理，先核验加载状态并开始无过滤/无时长大小上限的全量日志。

## 为什么需要B版

首个GA420的原始日志`opencore-2026-10-26-162349.txt`已经证明标记`ga420nogfx=1`传入boot.efi，但两个TGL驱动与HookCase的`Exclude`全部返回`Unsupported`。该试次未成功实施预期的图形隔离，不能证明停用图形后仍有原内存panic。

B版只把三个Kernel Block策略从`Exclude`改为`Disable`并换标记为`ga420bnogfx=1`，相应注释更新。其他配置与文件相对GA420逐项不变；仍以GA419外围组合为对照基线。EFI不含NGreen/WEG，不注入TGL平台属性和图形修复参数。

固定OpenCore1.0.8源码`Library/OcAppleKernelLib/KextPatcher.c`的`PatcherBlockKext`明确处理`IsKernelCollection`与`KcFixupValue`，在kmod启动入口写入`mov eax,KMOD_RETURN_FAILURE; ret`。`PrelinkedContext.c`按Disable/Exclude选择对应路径。原始源码本地保存在`private/opencore-source/`。静态核对支持选择此策略，但具体三个驱动的补丁是否成功，必须看新引导日志的返回值与运行时状态。

## 有效对照条件

1. 新标记生效，三个Disable操作成功；
2. 完整kext/IORegistry确认没有运行中的TGL framebuffer/accelerator、HookCase、NGreen/WEG；没有IntelAccelerator/Metal设备；
3. 基本显示桌面与SSH可用。允许卡顿，不以流畅度评价稳定性；
4. 与GA419尽量保持同系统、外围、用户操作和日志负载；先观察20–30分钟并记录工作负载，再持续较长时间。短期不崩不能独立证明根因，重复同类panic也需要完整panic及有效停用证据。

系统端TGL/Metal文件和KC原件保留。Disable是启动期阻止kmod正常启动，不是卸载或从磁盘删除图形组件。本机目前只读采集、独立USB镜像交付，不通过改KC/根文件混入新的对照变量。

交付检查：`reports/BUILD-DISABLE.json`与`reports/USB-DELIVERY-DISABLE.json`，含ocvalidate1.0.8、全文件/整IMG和独立只读USB回验，以及内部ESP、原五IMG、VentoyEFI与Boot/Loader变量前后核验。尚未启动时这些仅是静态检查，不代表对照成立。
