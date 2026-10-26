# R4：原作者NOCCS3用于真实Tiger Lake/Tahoe

下一次Ventoy入口：**`ISO/linux/HP-Tahoe-TGL-GA410-R4-CCS.img`**。
OpenCore选**已安装Tahoe 26.6.2 / 25G83系统**。镜像完整交付结果见`TGL-R4.json`。
机器保持Recovery开机，下一次物理启动由用户执行。

## R3实测

- 花屏照片显示规律绿紫方块、苹果标志和进度条；普通系统22端口超时/无路由，不能据此断言单纯显示故障。
- 已通过Recovery SSH取回新panic：失败session为`D456F9B2-FBC6-4668-9518-DFBCA33F2A50`，约64.180秒后，SecurityAgent触发`resolve_ccs+0xc7`写页故障。
- 采集器`kmutil showloaded`中的NG UUID为`4C4C4403-5555-3144-A1D3-3BEC9ADF5FE8`，精确匹配R3；FB、accelerator和HookCase亦已加载。
- 原始accelerator的`resolve_ccs`入口是`0x8cb2a`，`0x8cbf1`指令为`mov %eax,-0x14(%rsi)`；RSI=`0xffffffa069593244`减0x14恰好CR2=`0xffffffa069593230`。
- 调用链为`enableRenderCompressionWithAccelTask → IGAccelResource::submitCCSResolve → IntelAccelerator::submitCCSResolve → resolve_ccs`。
- 本次没有复现前两轮的port pure-virtual和scratch+0xd000 panic；没有捕获到HP-R3日志，不能声称已运行态测量确认分配结果。
- 采集器20个命令中19项rc0；`kernel-log`为143（watchdog终止），不计为成功。IORegistry早期accelerator输出为空，不能借rc0冒称全栈工作。
- 花屏原因仍未定位；新panic也不证明其为唯一原因。Metal功能尚未验证。

## R4源码变化和边界

原作者的XE-NOCCS3注释明确记录同一Tahoe IOAccelCommandBufferPool2写故障，并以`xor eax,eax; ret`跳过`IntelAccelerator::submitCCSResolve`。
原find/replace数组、应用代码保持原样，只把这一项从RPL专用拓扑块移出：原RPL分支继续使用，真实TGL仅Tahoe启用。
实物24字节模式唯一命中`submitCCSResolve`入口`0x2c84c`。

这是复用上游的**启动兼容绕过**，并未实现/验证CCS resolve本身；不能将其描述为修复了完整压缩转换语义。
保留原压缩/AUX enable路径、R2 f13b、R3 scratch分配对齐和完整组件。没有把整个TGL变成RPL，也没有同时启用其他RPL拓扑、POSH、HiZ或NOAUX补丁。
功能delta见`NG-R4-upstream-noccs3-tahoe.patch`，构建依据见`NG-R4-BUILD.json`。

## 交付和下次观察

独立源码副本/构建/原生实验重签；配置、221字节boot-args及系统KC沿用前轮实验。
实际codesign strict/deep、ocvalidate、完整EFI回读、原生完整文件清单和整镜像SHA256结果见`TGL-R4.json`。

R3证据和失败marker留存，采集器重新待命；新增30次、间隔2秒、总时限75秒的只读dmesg采样（16MiB输出上限），便于崩溃前保存后续NG日志，无GPU工作负载。

本次用户进入的是BaseSystem.dmg只读HFS恢复环境，diskutil的VolumeName为空。
旧恢复wrapper仅允许名字`macOS Base System`而在读取数据前拒绝；新独立`restore-firstboot-recovery-r3.sh`允许在`--collect/--verify`下使用有CDIS目录、BusProtocol=Disk Image且WritableVolume=false的Recovery。
`--restore`仍保留原先更严格入口条件。实际按UUID定位目标并取证成功，未执行恢复。

启动R4后先看显示/登录及普通SSH，随后读取加载状态和新采集输出。若再停住，先保持开机尝试SSH；需Recovery时选择CSR0镜像→`HPRECOVERY (dmg)`，联网执行`sh /Volumes/系统/hpdiag/s`。
完整本轮证据同步至Ventoy `GA410-R4-20261023/`及目标Data工作目录。
