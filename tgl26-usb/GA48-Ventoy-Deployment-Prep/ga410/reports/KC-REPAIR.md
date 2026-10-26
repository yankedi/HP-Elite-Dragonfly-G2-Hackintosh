# GA4.10：AuxKC链接及离线安装修复完成

用户在首次KC失败后明确要求“继续修复kc注册”。本次是新的、有具体修正依据的尝试，不是失败后无人值守重复注册。
旧goal保持closed/unmet，未擅自恢复或新建goal；旧收据不覆盖。本次按新用户请求执行KC修复。

## 实际结果

**`KC_REGISTERED`：离线AuxKC已由原生kmutil成功生成，核验后安装到目标系统路径。**
此状态的范围是实际链接及落盘，不包含第三方kext批准、签名受信任或运行时加载成功。
`POLICY_APPLIED=false`、`INSTALL_READY=false`；当前仍在25G83 Recovery，CSR原始值0，未触发任何重启、关机或GPU执行。

- `kmutil create --new aux`：**rc0**；仅执行了一次修正后的构建。
- 新AuxKC：7,077,888字节，SHA256 **`38f58293b7636dc7867168e670bb51a66958b10b54de515148a5e0d796543da5`**。
- UUID：`604F5C97-83A1-FBB1-B9FD-9EFD343C47F5`。
- 在线目的：`/Library/KernelCollections/AuxiliaryKernelExtensions.kc`。
  当前离线实际文件：`/Volumes/TARGET_DATA_VOLUME/Library/KernelCollections/AuxiliaryKernelExtensions.kc`。
- 发布脚本rc0，保持原root:wheel、0744及restricted标志；同目录原子rename，不原地截断原KC。
- 发布后的原生`kmutil inspect --show-extension-info --show-kext-uuids`再次rc0，读取的是**实际安装文件**，列出全部六项：

| 条目 | 版本 | 状态 |
| --- | --- | --- |
| org.smichaud.HookCase | 8.0.1 | 新增，真实Mach-O条目 |
| com.xxxxx.driver.AppleIntelTGLGraphics | 16.0.2 | 新增，真实Mach-O条目 |
| com.xxxxx.driver.AppleIntelTGLGraphicsFramebuffer | 16.0.0 | 新增，真实Mach-O条目 |
| com.highpoint-tech.kext.HighPointIOP | 4.4.5 | 原条目保留，Mach-O UUID与旧KC一致 |
| com.highpoint-tech.kext.HighPointRR | 4.22.1 | 原条目保留，Mach-O UUID与旧KC一致 |
| com.apple.driver.AppleMobileDevice | 4.0 | 原codeless条目保留 |

## 具体修正

1. 首次`install --update-all`会触发Boot/System KC重建。本次改为`create --new aux`，显式使用已有Boot/System作为链接输入，输出到Data工作目录的新候选；不改SSV。
2. 带`--volume-root`时，KC路径按卷内路径传入：`/System/Library/KernelCollections/...`。实测把完整`/Volumes/...`用于`libraries`会出现重复卷根路径，导致找不到输入KC。
3. `--repository`使用实际目标目录，以原生命令发现结果为依据，不假定所有路径选项归一化行为相同。`inspect`不支持`--volume-root`，因此使用其支持的绝对KC路径。
4. 加入目标L/E、StagedExtensions及Library/Apple/System/Library/Extensions仓库；`--explicit-only`明确选择三项新kext及三项旧条目，保留旧驱动而不引入其他KDK扩展。
5. 原生`libraries`读取正确集合后rc0；`print-diagnostics`对三项依赖均显示`Dependencies: OK`。实际native builder完成绑定并生成可核验的五个可执行fileset条目。
   未修改功能源码、ABI、依赖Plist或签名候选，未制造符号stub。

精确命令（完整实际展开记录还保留在目标工作目录和SSH原始日志）：

```sh
/usr/bin/kmutil create --new aux \
  --volume-root "/Volumes/TARGET_SYSTEM_VOLUME" \
  --kdk "/Volumes/TARGET_DATA_VOLUME/Library/Developer/KDKs/KDK_26.6.2_25G83.kdk" \
  --variant-suffix release --arch x86_64 --verbose \
  --boot-path /System/Library/KernelCollections/BootKernelExtensions.kc \
  --system-path /System/Library/KernelCollections/SystemKernelExtensions.kc \
  --auxiliary-path /Users/Shared/GA410-work-20261023-0820/kc-repair-aux-20261023/AuxiliaryKernelExtensions.kc \
  --repository "/Volumes/TARGET_SYSTEM_VOLUME/Library/Extensions" \
  --repository "/Volumes/TARGET_SYSTEM_VOLUME/Library/StagedExtensions/Library/Extensions" \
  --repository "/Volumes/TARGET_SYSTEM_VOLUME/Library/Apple/System/Library/Extensions" \
  --explicit-only \
  --bundle-identifier org.smichaud.HookCase \
  --bundle-identifier com.xxxxx.driver.AppleIntelTGLGraphics \
  --bundle-identifier com.xxxxx.driver.AppleIntelTGLGraphicsFramebuffer \
  --bundle-identifier com.highpoint-tech.kext.HighPointIOP \
  --bundle-identifier com.highpoint-tech.kext.HighPointRR \
  --bundle-identifier com.apple.driver.AppleMobileDevice
```

## 真实链接与发布核验

`verify-auxkc-repair.py`独立读取完整SSH回传的Mach-O文件，核对x86_64/MH_FILESET、五个内嵌Mach-O UUID/有效地址、六项prelink元数据、在线bundle路径及三项旧条目版本/可执行UUID。
三个新UUID分别与已安装kext一致；并确认新AuxKC绑定：

- Boot UUID：`REDACTED-SESSION-ID`。
- System UUID：`REDACTED-SESSION-ID`。

发布前16项KC基线SHA256全部通过；发布后16项期望清单仅AuxKC的一行hash发生变化，其他15项（包括全部原System KC/Preboot KC文件）仍与备份一致。
未调用针对当前Recovery卷的无参`kcditto`，未手工在Preboot创建AuxKC或替换Boot/System；目标为x86_64，其已有AuxKC路径就在Data的Library/KernelCollections。
11项组件的204文件SHA256再次全部通过。
原HighPoint条目的prelink来源路径由StagedExtensions改为其相同UUID的已安装L/E路径，此差异已明确记录。

## 签名及加载策略仍需真实验证

`print-diagnostics`对三项ad-hoc kext仍报告`Authenticating extension failed: Bad code signature`，即便整体命令rc0也不能忽略。
本次构建保留native `create`的默认本地认证模式（目标help默认`--no-authentication`），**未使用`-z`/`--no-authorization`**，未伪造Apple签名或写批准数据库。
原生构建成功不是这些kext已经获得运行时认证许可的证据。此认证问题未通过新签名或策略启动得到解决，故不能标`INSTALL_READY`。
后续必须在明确匹配的引导策略下验证实际许可/加载；CSR3独立镜像尚未启动，TGL首启配置尚未完成匹配。
构建/读取仍出现Recovery默认KextExcludeList未找到的warning；目标ExcludeList实际存在并被find发现，未篡改或移除。
候选的KCGEN诊断还保留了其他候选来源的arm64e/无可执行文件discard信息；独立prelink及实际安装文件原生inspect均确认全部六项目标确实在KC中，不靠总体rc0推断。

## 保持开机与恢复路径

- 最后SSH确认root/25G83、CSR raw0、authenticated-root enabled；完整NVRAM字典与修复前一致。
- 没有重启/关机/加载驱动，没有改内部EFI或原IMG；机器保持Recovery开机与2222 SSH。
- **现在系统AuxKC已有TGL条目。旧VESA EFI仍可访问不等于系统栈已恢复为原状态，不能再直接沿用“维护镜像回系统后再安装”的旧指引。**
  后续引导需先核实匹配的策略与恢复安排，不把任何镜像标作已就绪的加速首启。
- 全部原恢复归档和USB恢复工具保留；若要恢复原VESA系统状态，使用既有Recovery全栈恢复流程撤销11项组件并恢复原AuxKC，校验后再决定引导。
- 快速、仅AuxKC恢复副本：目标`/Users/Shared/GA410-work-20261023-0820/kc-repair-aux-20261023/publication/previous-AuxiliaryKernelExtensions.kc`。
  SHA256仍为`5d6170588133eae3fe1d4f0024f67960f0ce6aeb6d2f3266e9865d96ddfa8fcd`，已原生metadata-preserving复制；NixOS也有完整回读。
  单独恢复此文件不代表已撤销11项系统组件；不在运行中的系统替换其KC。

## 记录

本次工具提交`8e1c63a`、`845bc8b`，本地保存、不push。
机器可读收据见`KC-REPAIR-STATE.json`；原始命令/rc/stdout/stderr在忽略的`ga410/private/commands/`。
构建工作目录额外保留命令、stdout、stderr、returncode及候选；publication下有旧AuxKC和发布后完整KC校验清单。
