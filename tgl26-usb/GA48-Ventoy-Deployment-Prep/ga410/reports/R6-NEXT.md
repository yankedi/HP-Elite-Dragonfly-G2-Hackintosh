# R6：复用上游命令池容量和对齐修复

## R5 实测结论

`R5-RUNTIME.json` 保存了本轮核对事实及私有原始文件哈希：

- session：`REDACTED-SESSION-ID`。
- 加载的 NG UUID：`4C4C4426-5555-3144-A1B3-CCD2D1B45BE1`，匹配 R5。
- `HP-R5` 内核日志和 Metal 客户端均验证 80EU、10 subslice、镜像1/10、
  5 个 dispatcher；R5 的拓扑修正实际生效，但桌面花屏仍存在。
- 23:46:03 的 `gpuRestart` 报告：RCS context63 卡死；最后 ring batch
  起点 `0x40007e40`，`ACTHD=0x40008004`，`IPEHR=0x40188001`，
  `EIR=ESR=1`。地址跨过4KB页边界；报告称页表看起来正常。
- 本次完整 dmesg 中 `XeNG POOL[1] init count=8 size=0x1000->0x1000`，
  后续多个 count8 / count256 的4KB池同样未扩大。
- 重启后的 WindowServer PID906 主线程阻塞在
  `WSInitialize → CoreDisplay → IOFramebufferOpen → IOServiceOpen`。
- 已知像素 no-copy 小探针 PID933 在23:47:28启动，比 hang 报告晚85秒。
  采样证明其停在 `MTLCreateSystemDefaultDevice → IOServiceOpen`；
  尚未提交测试 GPU 工作，未得到有效像素对比结果。已发送 TERM。

本次已成功 sudo 采集完整 dmesg 和 WindowServer sample，归档
`ga410/private/r5-live/root-capture.tar.gz`，SHA256：
`e517951a93242beebda2ddf2588ff18c98a6064ba6ee9522c43a2f787ab5ff1e`。
凭据不在报告、代码或证据归档中。

本轮29份原始文件和命令回执另行封存为
`ga410/private/R5-R6-local-evidence-20261024.tar.gz`，SHA256：
`ec52a310a3ec7f0c39e3fc22efd53f4727e5ec6df66883d8f2a960750ee8ac6c`。

## 命令池代码证据

1. TGL accelerator 在 `0x33c95..0x33caf` 允许一次预留至多64KB，随后调用
   `IOAccelCommandBufferPool2::getBufferPtrNoInc`。
2. 精确25G83 KDK 的该函数位于 `0x62bc`：使用池 `+0x1858` 当前指针和
   `+0x1850` 上限，空间不足时提交/切换buffer；新buffer不再拒绝超容量预留。
   这些字段与上游包装器一致。
3. 作者 `docs/HISTORY.md` §10.4 已记录同类跨4KB命令池故障，并提供
   XE-POOL 容量修复、POOLALIGN 64字节对齐修复。
4. 当前这两个包装器的生效条件都仅为 `-ngreenxefix`，当前配置没有该参数。
   直接添加它会连带开启许多其他实验路径，因此本次只修改这两个门控。

报告没有转储 ACTHD 处的实际 batch 内存，故不能把边界和错误码当成所有
花屏根因已经证明。这里是有运行态和静态证据支持的最小兼容修复候选。

## R6 源码与构建

从 R5 独立源码副本构建，保留此前全部修正。只改 `kern_green.cpp`：

- `wrapPoolInit` / `wrapPoolGetPtr` 的原 `-ngreenxefix` 门控增加真实 TGL
  且 Tahoe 条件，继续保留 `-ngreennopoolfix` 的关闭语义。
- 使用现有公开 `getIsRealTGL()`，不改变成员可见性或另做 CPU 检测。
- 容量算法保持上游原样：count≤16至少128KB，更多buffer的池至少16KB，
  原64KB池不变；对≥0x400 dword的预留保留原64字节padding算法。
- 每个包装器首次运行新增 `HP-R6 ... enabled=1` 日志。

`NG-R6-BUILD.json` 记录编译产物和源码哈希。初次编译因直接访问私有
`isRealTGL` 被拒绝，改为现有公开accessor后编译通过，失败日志亦保留。

## 当前交付状态与下一步

**R6 已在 Recovery 完成原生签名和交付，等待用户物理启动验证。**

- 镜像：`/Volumes/TARGET_VOLUME/ISO/linux/HP-Tahoe-TGL-GA410-R6-POOL.img`。
- 整镜像 SHA256：`648714162de51060fe031b0d99f252e2332a0f308c24acefa7d97b50fa1f9677`。
- NG UUID：`4C4C44D0-5555-3144-A111-5710B37AE86F`。
- NG 签名后 SHA256：`5d0ce0238fc13d273748c61a020219a7d8dab6154fdd59c36e0ef9780164ea5f`。
- 原生 ad-hoc strict/deep 验证成功，全部文件型 sections 和 UUID 保持不变。
- ocvalidate 成功，配置字节与 R5 相同；本地EFI回读和原生全部100文件清单一致。
- 整镜像上传后与卸载后哈希一致，明确 umount、detach 和最终 sync 均成功。
- 原系统204文件及KC、22份备份校验通过。已校验采集器及LaunchDaemon哈希、
  shell语法和plist，并将旧marker改名保留；新首启marker已不存在、采集器待命。
- `TGL-R6.json` 是本轮完整交付回执。

用户启动步骤：手动重启，在 Ventoy 选择 `HP-Tahoe-TGL-GA410-R6-POOL.img`，
随后 OpenCore 选择已安装的 Tahoe 26.6.2 / 25G83 系统。开机联网后先核对
加载的NG UUID、80EU拓扑、`HP-R6 ... enabled=1` 和实际池大小，再递进验证。
容量修复生效的预期日志为 count8 `0x1000->0x20000`、count256
`0x1000->0x4000`；POOLALIGN仅在需要padding时输出，不要求每次都出现。
目前尚无R6运行结果，不能据交付成功宣称GPU hang或像素问题已解决。

## 交付过程中的差异与补充证据

最初正常SSH失联的失败回执仍保留。Recovery重连后，首次整镜像检查发现R5
实盘哈希变为 `90e0f7e98ea87d4a2dd83ef6741cab48d27367bb3ac1ccdb2c7aeb84be054946`，
配方按原哈希检查停止，尚未创建R6远端目录。下载实盘R5并逐文件比对证明：
原100文件全部一致、未删除文件，仅新增 `opencore-2020-01-01-000058.txt`。
逐字节比较共9892字节变化；差异报告在私有目录封存，摘要已写入交付报告。
R6仍由封存且原哈希正确的本地R5制作，交付前后实盘R5哈希相同。

配方新增显式 `--recovery` 和唯一 `--attempt` 回执前缀。成功执行为：
`python3 ga410/tools/deliver-ng-r6.py --recovery --attempt postboot-checked`。
原失败回执未覆盖。

Recovery额外取回R5最终崩溃记录，归档SHA256为
`86767caca2a0448b31302810212319b08d2abfad74b4395d5ccc944b9fb3eb6c`。
23:52:09 watchdog报告与同一R5 boot session一致，WindowServer初始化未完成；
内核锁持有者为 `IOGraphicsSystem` 线程1832，TGL UUID精确匹配。其栈包含
`IGScheduler::resumeCommandStreamer` 返回点 `0x56aad` 和
`IGAccelEventMachine::eventTimeout` 返回点 `0x1608c`，与GPU hang后的恢复阻塞
相符。`R5-POSTHANG-WATCHDOG.json` 保存结论和原始文件哈希，不把它当成
R6修复效果的证明。
