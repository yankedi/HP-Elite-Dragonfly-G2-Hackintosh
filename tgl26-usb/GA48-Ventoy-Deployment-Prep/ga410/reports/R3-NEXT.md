# R3：Blit3D scratch分配页对齐实验

> R3实测更新：出现新的SecurityAgent CCS resolve写页故障并花屏。当前入口见[R4说明](R4-NEXT.md)，本文件保留R3交付时点。

下一次Ventoy入口：**`ISO/linux/HP-Tahoe-TGL-GA410-R3-BLIT-ALIGN.img`**。
进入OpenCore后选**已安装Tahoe 26.6.2 / 25G83**。
交付与完整SHA256以`TGL-R3.json`为准；当前机器保持Recovery开机，物理启动由用户执行。

## R2已确认的进展和故障

Recovery SSH已连接，Recovery session为`46BCE917-C18A-46DB-830C-E96E056E3C8E`。
新panic和采集输出对应失败系统session`AD062E14-6E9D-4BE0-BF74-9B46F46DBA24`。
panic中的NG UUID与R2交付产物精确一致，且含`-allow3d -disablegfxfirmware`。

- R2没有再出现上一轮`probePortState+0x207` pure-virtual panic；已经进入WindowServer的`IOAccelCommandQueue::process_command_buffer`。
- 新故障发生在开机约55.579秒：`IGHardwareBlit3DContext::initialize+0x4c`返回点内的scratch初始化写故障。
- `RBX=0xffffff8035b2f000`，`CR2=0xffffff8035b3c000`，差为`0xD000`；写入长度`RDX=0x44`，页故障错误码2。
- 原始accelerator实物的`initialize`位于`0x7d8b8`，调用scratch helper的指令为`0x7d8ff`，返回地址`0x7d904`，恰好`+0x4c`。
- helper在`0x319f6`计算`base+0xd000`，随后复制`0x44`字节，与寄存器精确匹配。后面还会继续写sampler/blend尾部。
- 原作者现有V69替代路径默认跳过scratch，XE-BLITSCRATCH2会生成临时缓冲区再只复制前`0xD000`字节；这两条路径均有已知功能缺口。真实TGL分支直接调用原始初始化，所以本机仍撞到这个故障。
- 本次首次采集到内核实际CSR为`0x203`，authenticated-root仍启用。完整证据索引见`R2-PANIC.json`。

## R3的具体修改

保留R2的f13b；只在现有`IGHardwareExtendedContextinitWithOptions` wrapper中增加分配参数修正：

1. 限定真实TGL、Darwin25/Tahoe、参数指针为已解析的Blit3D静态params，且size字段精确等于`0xD240`。
2. 对该`0x38`字节params作每次调用独立的栈副本，只将`+0x10`的scratch分配大小改成`0xE000`。
3. 传给原始initWithOptions，继续完整的Apple scratch shader/state初始化；返回值照旧，并新增分配前/返回后日志。

反汇编依据：静态构造器将`0xb0c40`处的64位`0xD240`写入Blit3D params `+0x10`；原始ExtendedContext在`0x7cf59`读取此字段，传入`IGSharedMappedBuffer::withOptions`。
两层原始初始化消费字段且不保存params指针，记录最后一个字段位于`+0x30`。每次调用副本不修改共享静态常量。

**这是针对实测页边界故障的分配修正实验。CPU映射为何缺少尾页尚未从运行态量出，页对齐能否消除故障仍待实机验证。**
NG实物中`0xD240`条件、`0xE000`大小和新增日志已检查，见`R3-BINARY-CHECK.json`。
完整source delta见`NG-R3-align-blit-scratch.patch`；独立27个源文件中仍只有`kern_gen11.cpp`改变。

## 下一次验证

新镜像原生重签、strict/deep、同版ocvalidate、EFI回读、完整文件和整镜像SHA256检查以实际`TGL-R3.json`为准。
原始NG/驱动及旧镜像保留；新签名NG另存Data工作目录`ng-r3/`。
安装组件、AuxKC、HP配置和221字节启动参数沿用R2实验；NG由EFI加载。

采集器的R2失败marker已归档，输出原样留存；取消原先15秒等待，优先取accelerator/FB/PCI状态，避免再次崩溃时只抓到早期启动。
下次观察显示/登录/SSH，随后读取`HP-R3:`日志和IORegistry。未完成任何Metal设备、shader或GPU计算验证。
若黑屏，保持开机并告知代理先试普通系统SSH；需要恢复取证时仍用CSR0 Recovery镜像，联网执行`sh /Volumes/系统/hpdiag/s`。

证据、补丁、构建工具和交付收据同步至Ventoy `GA410-R3-20261023/`及目标Data工作目录。
