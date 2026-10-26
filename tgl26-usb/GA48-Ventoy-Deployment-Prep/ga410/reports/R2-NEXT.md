# R2：针对probePortState panic的下一次实机启动

> R2实测更新：已发生新的Blit3D写页故障，当前入口见[R3说明](R3-NEXT.md)。本文件保留R2交付时点，勿再次选择R2。

用户已明确授权直接修改并逐个解决阻塞；本轮在独立NG实验副本中启用了原作者现有f13b补丁。

## 唯一下一次实验入口

Ventoy选择 **`ISO/linux/HP-Tahoe-TGL-GA410-R2-F13B.img`**，OpenCore中选择**已安装Tahoe 26.6.2 / 25G83**。
不要选择旧TGL或已HOLD的R1。完整交付SHA256和验证结果见`TGL-R2.json`。

## 改了什么

- 独立副本`ga410/private/ng-r2/source/`相对GA47的27个源文件，仅一行不同：取消原有`f13b/r13b`应用行的注释。
- 原find/replace数组没有重写；全套NG功能、用户态驱动、原驱动布局均保留。
- 补丁精确针对本次panic的`AppleIntelPort::probePortState+0x207`虚调用，依据见`FIRSTBOOT-PANIC.json`。
- 使用原GA47离线编译/链接配方重建NG，然后在当前真实Recovery中原生ad-hoc重签、strict/deep校验。
- 新镜像沿用R1的221字节参数，补齐`-allow3d -disablegfxfirmware`；CSR Add0x203、AMFI及HP配置保持原实验值。
- NG通过EFI加载，因此无需为这项修改重建/发布AuxKC。完整204项组件、22项备份和当前KC仍由原生恢复预检核对。

## 验证边界

已完成的编译/原生结构签名/镜像检查以实际`TGL-R2.json`为准。
ad-hoc结构验证不是Apple签名信任；这轮也没有实际启动R2，不能宣称panic已在硬件上消除或Metal成功。
原GA47源码和旧IMG留存，新签名NG另存目标Data工作目录`ng-r2/`，新镜像为独立文件。
机器保持Recovery开机，没有自动重启/关机或Reset NVRAM。

## 首次重试观察

- 先观察是否越过原画面并进入登录/桌面。SSH起来后由代理读取实际boot-args/CSR、加载kext、IORegistry及采集记录。
- collector已重新待命，原失败输出和marker保留；结果仍在`/Users/Shared/GA410-firstboot/`。
- 未安排Metal、shader或GPU工作负载，不以“进入桌面”直接宣称全栈完成。
- 若再次停住，拍下最后画面；先由代理尝试SSH。需要Recovery时仍选`HP-Tahoe-Recovery-GA410-CSR0.img → HPRECOVERY (dmg)`，联网后`sh /Volumes/系统/hpdiag/s`。
- Recovery原始NVRAM panic继续保留，不清空它；按boot-args、UUID和崩溃点区分新旧记录。

## 本轮工程记录

源补丁：`ga410/patches/NG-R2-enable-upstream-f13b.patch`。
构建工具：`build-ng-r2.py`；原生签名和交付工具：`deliver-ng-r2.py`。
构建日志及实际生成diff留在`ga410/private/`；命令rc/stdout/stderr留在`ga410/private/commands/`。
初次编译与链接已经成功，但构建后“原仓库必须clean”检查因Python导入生成的`__pycache__`而拒绝收据。
该字节码被移到独立工作目录保留，禁用后续写bytecode，并对同一个已编译产物完成检查；未改动原GA47文件，也没有借此重新改变功能或吞错。
交付脚本启动前另修正一个Python字符串连接语法错误，该次没有发生远端操作。

说明、补丁、实际收据和操作证据同步至Ventoy `GA410-R2-20261023/`及目标Data工作目录同名子目录，最终清单原生SHA256校验。
