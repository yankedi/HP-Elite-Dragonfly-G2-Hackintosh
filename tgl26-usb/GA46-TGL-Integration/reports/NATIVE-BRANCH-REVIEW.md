# GA46 原生入口二次复核

GA45仅在局部wrapper检查nativeTgl，仍有可达的其他分支：

1. NGreen::processPatcher在识别PCI前默认安装cs_validate_page hook。
2. IOAF2路径仍会装pool hooks，且单独-ngreenxefix检查可绕过Gen11 xeFixEnabled。
3. Gen11默认V99/V193等实验逻辑，不只ForceWake/HANGCHECK一条路径。
4. -ngreenicl可重新注册ICL fallback，forceprops和configRead override可重引入
   伪装；CPU-only native判断未显式要求family6。
5. 原始patch-mtl17.py无视原生排除清单，直接应用compression/fastclear/RPL L3
   全表并ad-hoc重签；build-shader-compiler默认全量LLVM C++ re-export。

本轮实际native构建定义GA46_NATIVE_ONLY=1：

- init仅注册TGL两种历史bundle ID；不注册genx/ICL或DYLD页hook。
- NGreen kext回调仅分派精确8086:9A49+family6/TGL+无ICL伪装的Gen11入口；
  未知身份直接拒绝，绝不落入旧RPL分支。
- Gen11入口只识别TGL二进制；不装IOAF、ForceWake、MMIO、scheduler、memory、
  context、Display13或submit hooks。V40/V221与全部legacy实现仍保留历史源码，
  但native构建的入口不会到达它们，boot flags不能覆盖这一编译期边界。
- XE-FMT常量BGRA不是所有surface的语义证明；PLANES2+0x98和VALD flags也未经
  25G83确认。因此它们本轮**离线staging-only**，不以实验开关默认授权执行。
  WEG coexist标志下拒绝native分派；未证明实际多kext加载顺序下的互斥，保持
  DEPLOYMENT_BLOCKED，不宣称一个boot flag就能解决所有WEG/Lilu互斥问题。
- legacy prop seeding/PCI config覆写关闭，真正PCI身份与Tiger Lake profile保留。
- 旧全量构建/patch入口已替换为隔离native构建入口，或明确拒绝不成立的compiler
  组合。无自动codesign、安装或安全策略修改。

**这使当前NootedGreen成为真实链接的原生审计/隔离构建，不是已完成GPU移植。**
解除字段隔离需要真正25G83 ABI证据，解除compiler隔离需要真实3902/provider或
已验证序列化协议。这不是“加一个开关即可运行”。
