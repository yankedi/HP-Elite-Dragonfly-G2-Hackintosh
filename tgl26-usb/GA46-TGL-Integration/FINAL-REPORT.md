# GA4.6 — Apple TGL 原生驱动链接、ABI 与集成：最终报告

日期：2026-10-23。目标：HP Elite Dragonfly G2，i5-1135G7，Iris Xe
`8086:9A49`，macOS Tahoe `26.6.2 / 25G83`，x86_64。

## 一、结论

**真实 kext 链接障碍已解决；本轮离线工程已交付，完整功能集成未达成。**

实际生成 `NootedGreen.kext/Contents/MacOS/NootedGreen`，没有修改 Mach-O
filetype 伪造 kext，没有伪造 OSSymbol/IOService/内核运行时实现。Compiler 和
Metal 复核确认现有实现缺少不可跳过的私有 ABI 证明；本轮修复了生命周期与
伪恢复问题，并隔离未知调用，**没有实现可工作的旧编译器请求转换或 Metal
descriptor 适配**。不能将严格链接、测试通过或主动拒绝未知调用称为功能完成。

| 验收状态 | 本轮判定 | 精确范围 |
|---|---|---|
| `KEXT_FILETYPE_VALID` | 达到 | x86_64、MH_KEXT_BUNDLE=0xB |
| `KEXT_RELOCATIONS_VALID` | 达到 | 实际1606个外部/本地重定位通过静态检查 |
| `KERNEL_SYMBOLS_AUDITED` | 达到，有限制 | 392个名称均有候选provider；不等于公开KPI/对象ABI通过 |
| `KEXT_LINKED` | 达到 | 真kext与Info.plist已封存，未签名/加载 |
| `USERSPACE_DYLIB_LINKED` | 达到 | 3dylib严格two-level链接；当前为隔离/诊断版本 |
| `RUNTIME_SYMBOL_UNVERIFIED` | 保留 | target shared-cache libLLVM导出未现场核验 |
| `ABI_UNVERIFIED` | 保留 | kernel/Lilu C++、compiler私有协议、Metal完整schema |
| `DEPLOYMENT_BLOCKED` | 保留 | 修改Apple组件及Apple host接受自建库无已证明路径 |
| `GPU_NOT_TESTED` | 保留 | 未执行目标新探针、kext加载或GPU工作 |

未取得 `KEXT_LOADED`、`KEXT_RUNNING`、`METAL_DEVICE_READY` 或 `GPU_SUBMIT_PASS`。

## 二、继承与工程边界

GA45原仓库维持 `971c2a1de82e1570307f34d85d5989a118a71831`，工作树干净。
GA46由其Git archive创建独立仓库，分支 `ga46/tgl-integration`；继承记录
`reports/INHERITANCE.json`。GA40–GA45未写入，无push，无Apple SDK或二进制
进入提交。GA45原报告保存在本仓库 `reports/history-ga45/`，历史结论不冒充
GA46结果。技术路线仍为Apple TGL16.0.32 + NootedGreen + libxedrv +
Compiler Adapter/LLVM Bridge；未恢复Mesa/i915-XNU或ICL指令转译。

没有修改EFI/IMG/NVRAM/BIOS/SIP/SSV/AMFI/Secure Boot，没有安装/加载kext，
没有替换目标GPU bundle、重启、MMIO/Batch/Shader执行。source/result IMG为null。
本轮CPU测试仅运行NixOS宿主ELF测试程序；交叉构建的Darwin文件没有执行。

## 三、P0：真正解决 kext 链接

### 3.1 上游与工具链

通过认证GitHub核验[LLVM PR204805](https://github.com/llvm/llvm-project/pull/204805)
为open/draft/unmerged、1提交、24文件；4条bot评论，无返回的人类review线程。
观测head `d575e43643f7c90a1a2728352a24867d7105d9e9`，base
`762316e293d1db4f495bdbb545c31d588a1a2d62`。完整patch与测试已审阅；未假设
NixOS LLVM21.1.8含补丁。完整pinned公开源码在隔离目录实际构建LLD和检查工具，
不全局安装。Release/assertions/X86、6并行编译/1链接，构建日志保存。

| 身份 | SHA256 |
|---|---|
| PR patch | `0465346e1210f2d3889a08348da1a37c2eb9bf8896b500f6af73b3aafbbf3b6c` |
| LLVM source archive | `5cb8413f1ccf12050982606e58e0a7f96985dc512dd61475f10d5d040e3b8b50` |
| 最终ld64.lld | `f1b7547756dc64555c580dd8e30d1437a71a9c4c7bab7a13e496f9df95180661` |

tarball首次CMake错误提取父仓库Git revision，已关闭该展示功能重新构建；
来源以commit/source SHA为准。缓存cctools因缺libBlocksRuntime/libdispatch
不能运行，未计成功。PR仅支持x86_64，不把arm64e/chained-fixup算入本轮能力。
本轮构建LLD而非补丁Clang；编译用宿主Clang并显式传内核选项，直接调用新LLD。

### 3.2 合法fixture与真实故障修复

fixture含真实IOMalloc/IOFree、kmod_info、全局构造/析构，不以空系统函数补符号。
定位 `__cxa_atexit` 来自LLVM后端全局析构降级：仅前端
`-fno-use-cxa-atexit`不足，加入
`-mllvm -disable-atexit-based-global-dtor-lowering`才保留kernel析构节。
与Xcode项目核对模块名/start/stop/C++17/静态链接/异步unwind设置，使用真实
SDK libkmod.a跳板。netdbg从cstdarg改为内核stdarg.h并实际编译，不用Linux
libc++头，不伪造缺失libcc_kext.a。SDK26.5仍不是精确25G83 KDK。

fixture检查PASS。上游 `lld/test/MachO/kext.s` 与
`llvm-objcopy/MachO/kext-relocations.test` **2/2 PASS**：外/本地重定位、
错误SIGNED/chained-fixup/arm64拒绝、strip/remove-section索引重建。
先前缺count/strip的失败日志保留，不与最终PASS混计。

### 3.3 完整NootedGreen及符号分类

先实际链接全源码候选（1815重定位/397imports）；随后复核遗留分支，建立
最终native-only入口，重新构建14对象，最终**1606重定位/392imports**。
检查header/segments/sections/symtab/dysymtab/`__LINKEDIT`、外部/本地索引与
addend、初始化/终止节、模块入口、Lilu依赖、Info.plist展开；拒绝用户态dyld
命令/TLV/atexit导入。与来源明确Lilu及两个Apple donor kext结构对照。

PR的-kext语义保留undefined，`-undefined error`也不等于kernel provider
验收；因此另设逐名称provider gate。最终分类如下：

- **A公开KPI：未证。** 362名称存在同build25G83 Recovery KC的kernel符号表，
  但没有目标公开KPI allowlist，机器图category为null、candidate_category=A。
- **B原生kext：1名称级provider。** IOPCIDevice::metaClass在IOPCIFamily。
- **C Lilu：29真实导出。** 只读附带Lilu1.7.2；对象布局仍未证。
- **D误入用户态ABI：未在当前名称审计发现。** 不把stack protector名称单独
  当污染证据；真实Lilu也导入其kernel provider。
- **E缺失/不支持：当前名称没有完全找不到provider者；** 这不排除未知的
  公开性、私有ABI限制或目标KC拒绝。未把未知硬归为A或宣称E风险为零。

`KERNEL_SYMBOLS_AUDITED`表示做过审计并公开上述限制，不是
`KERNEL_ABI_VERIFIED`。Recovery KC不等于目标boot KC，C++mangling一致不证明
IOService/OSSymbol vtable及Lilu成员布局。最新机器记录
`reports/KERNEL-SYMBOL-PROVIDERS.json`纠正了初始日志用A表示kernel名称候选的
宽泛分组；历史日志不改写。

## 四、Compiler Adapter / LLVM Bridge

### 4.1 真实依赖图与调用证据

从9个真实Mach-O及既有MTLCompiler导出证据生成
`reports/COMPILER-DEPENDENCIES.json`：全部导入、库ordinal、预期/实际provider、
mangling、版本、加载顺序及失败行为；动态C API也列入。
图中统计6090个`RUNTIME_RESOLUTION_REQUIRED`、41个`ABI_MISMATCH`、
2个`LINK_RESOLVED`、8个`SYMBOL_ABSENT`。包含GA45历史节点，不是说新3dylib
有6090个未解析符号。LINK_RESOLVED仅精确导出和编码绑定证据，不是目标运行。
Shared-cache libLLVM无离线export表的字段标null，未把文件不存在推导成
install name无法dlopen。MTLCompiler373.7/current32024、GPUCompiler32023
与donor3902不是同一版本；旧入口与新入口分别在各plugin，不在framework的
实际四项导出中，未再通过特征字节猜测私有函数地址。

两份实际反汇编证实Create分配0x120对象，ReleaseReply以compiler对象为参数，
读取+0x110/delete[]与+0x108/free。原adapter不能把任意reply指针传进去。
新入口r8/r9与旧Module参数的位置关系不证明Options/input/metadata/resource
binding、同步完成、reply生命周期或错误码契约；新路径还使用r9d长度，原先
size_t声明并未逐字段确立。完整偏移/路径记录见COMPILER-ABI-RESULT。

### 4.2 已完成的源码工程

- 移除进程signal/longjmp崩溃后继续、伪helper/provider vtable、假ostream
  析构、固定Twine内存布局与函数特征扫描，不再伪造ABI兼容。
- adapter Create不调用未知donor，返回null；外国实例删除、reply和未知请求
  失败即停，不写未知栈指针，不猜返回码，不伪造编译成功。
- bridge移除旧C++ shim导出，只暴露项目自有字节诊断ABI。明确不再是donor的
  drop-in LLVM替代品；缺失旧ABI让loader拒绝，比伪函数可链接更诚实。
- 同image LLVM C API、精确install name/RTLD_LOCAL/dladdr同owner检查；每请求
  新context，输入/输出copy，按output→module→input→message→context清理。
  不接受外来Module*，不混用3902与32023对象。
- 3dylib严格two-level系统依赖链接，不用`-undefined dynamic_lookup`。
  新自建adapter命名正常plugin，Old留作Apple donor，消除历史命名冲突。

**未完成：SerializedBitcode→WithOptions的功能转换、Apple bitcode3902降版、
真实3902 C++ provider、ICB helper及完整请求/reply协议。** 当前隔离路径不是
这些功能的替代实现。

### 4.3 非Mock的CPU回归

用Clang生成含函数/全局状态的真实bitcode，通过宿主LLVM21解析/序列化；
8线程1600次roundtrip、ASan/UBSan/leak检查通过，llvm-dis确认函数保留。
截断payload进入真实LLVM错误路径；非法magic/超限/缺provider拒绝。另以真实
adapter源码验证Create为null、3个未知ABI入口SIGABRT且未改变SIGSEGV handler。
不是空Mock，也不证明Apple compiler可编译TGL shader。
官方LLVM仅保证新reader读取旧bitcode，不保证旧reader读取新bitcode；
普通roundtrip绝不等同Apple私有3902降版接口。

## 五、Metal373.7/libxedrv及探针

审查发现旧libxedrv的固定偏移、TLS循环buffer返回指针、全局lazy初始化、
hash-map不释放与heap重分配、signal中非安全日志、重入和生命周期问题。
本轮移除这些未经证明的RPL/私有ABI转换，保留历史源码于baseline。
新版本只在实际donor实现、已核验签名的方法上拒绝device init；一次性安装、
继承方法用class_addMethod，不原地修改framework父类。类/加载次序不满足时
明确失败即停。它是隔离构建，不能注入WindowServer当可用驱动。

共享CPU preflight读取真实class/ivar encoding、size/alignment/offset，
NSGetSizeAndAlignment确认storage extent；先核验selector，再在新建descriptor
上检查inline地址及公开sample/vertex property与候选字段对照。C边界测试有
负例；目标Objective-C行为尚未执行。即便探针全部吻合，也不自动批准LogicOp
27→32、附件bitfields/enum或完整private ownership schema。

待单独批准的CPU观察命令与行为在`reports/METAL-ABI-RESULT.md`：

```sh
./metal-abi-probe
./compiler-runtime-probe
```

前者只新建CPU descriptors/查询元数据与其自有字段；不创建设备或GPU工作。
后者默认精确system install names的RTLD_NOLOAD/dlsym/dladdr，不加载donor。
额外`--open-system-images`会dlopen Apple系统image并可能运行initializers，
故其行为和授权单列；本轮均**未执行**。这些观察不解除ABI或部署限制。

## 六、原生分支与18项donor staging

发现局部门控仍可被其他分支绕过：识别PCI前的cs_validate_page hook、IOAF
pool/xefix路径、Gen11其他实验分支、ICL注册/forceprops/configRead覆写。
实际构建定义GA46_NATIVE_ONLY=1：family6/TGL/8086:9A49且无ICL伪装才分派，
只注册TGL，不走IOAF/RPL/ICL/代码签名页分支；ForceWake/HANGCHECK/V40/V221
等旧实现不可由boot flag绕回。WEG coexist标志下拒绝，未宣称已证明多kext
实际互斥。FMT常量BGRA、PLANES2+0x98、VALD flags语义未证，均staging-only。
最终NootedGreen由此是可审计native-only构建，**尚非完整兼容驱动**。

保留9A49/TGL/Display12身份与Apple原生compression/AUX/scheduler/memory/
context/提交代码。18项计划含原SHA/原字节/唯一条件/替换/后SHA/逆向/审核：

- 仅实际应用MTL header ncmds/sizeofcmds、LC_LOAD_DYLIB、plugin path三项到
  GA46私有副本；filetype不改，Mach-O完整重解析。
- 其余15项原字节不变；包括FMT/PLANES2/VALD及compression/AUX/clear/RPL L3
  相关绕过。短字节/padding以全文件SHA+固定offset限定，不虚报全局唯一。
- 第二实现独立计算实际改变offset集合、无重叠/排除项不变并反向还原全文件
  SHA；重复staging生成相同计划与SHA。是独立实现二次复核，不冒充独立人员
  或另一Agent的运行语义审查。
- 原MTL1286个CodeDirectory/SHA256页哈希匹配；修改副本**0/1/162页失配**。
  未验证CMS证书链，不重签，不因LC_CODE_SIGNATURE存在而称原签名仍有效。

`PrivateFrameworks/../Caches`路径只保留为离线实验，不证明sandbox规范化后
接受；当前副本无可执行的整套安装布局。详见DONOR-STAGING-REVIEW/PATCH-PLAN。

## 七、五类签名与加载可行性

1. **自建NootedGreen：** 格式正确还需目标ABI/KPI/Lilu、有效kext签名身份、
   公证/批准/KC流程；普通Developer ID Application不等于kext-enabled身份。
2. **未修改Apple donor：** 字节不变最多保留原签名条件，仍未证明跨版驱动
   匹配、依赖和目标加载许可；原CodeDirectory匹配不是证书信任验证。
3. **修改Apple私有驱动：** 原code pages实测失配；普通开发者重签不能恢复
   Apple身份或私有权限，无约束内合法加载路径实证。
4. **自建dylib：** Team ID不是Apple；@rpath/绝对路径、host library validation
   与sandbox分别约束。能链接不证明Apple host接受。
5. **WindowServer/MTLCompilerService整套接受：** host entitlement不能由插件
   自授，公证也不是Apple授权私有驱动。五项不能由购买一张证书统一解决。

已查询Apple一手资料，链接和平台区别见`reports/SIGNING-GA46.md`。macOS11
后的KC/AuxKC流程不能由filetype绕过；不把Apple silicon Reduced Security/
1TR/LocalPolicy原样套用Intel HP，也不因不是Apple silicon就假定签名失效。

**在不改变既定安全约束、且没有Apple允许的修改组件/host加载路径证明时，
部署分支保持终止于DEPLOYMENT_BLOCKED。** 它不是仅缺一次运行授权；CPU
探针只能缩小证据缺口，不能给予Apple host接受组件的能力。

## 八、封存、提交与验证入口

私有产物根：`staging/final-001/`；逐文件SHA在
`reports/ARTIFACT-SEAL.json`与私有MANIFEST，当前摘要在
`staging/manifests/components.json`。封存包含94个文件/链接记录，不含SDK。
sealed source_commit是已提交的构建源码版本，最后报告提交另见Git台账。

最终kext SHA256：

```text
0d920d5a42c1dac2364cd01cdb60c740c301562855d99a552d9e27310160a2b8
```

实际已执行 `make check CHECK_OUT=logs/check-final-001`，exit0。
日志包含所有必要CPU回归、真实构建、独立donor验证与上游测试；没有重复运行
目标程序。最后仅修正审计分类、构建入口指向及文档/清单，不改变封存二进制；
针对这些更改另做脚本语法、manifest/hash、provider重审计与Git差异检查。
单元提交及最后交付HEAD见`reports/GIT-COMMITS.md`与`git log -1`，无remote/push。

## 九、离第一次 Apple TGL Metal Compute 还差什么

以下每一项都不可用本轮链接或CPU测试代替：

1. **目标KC和C++ABI：** 取得公开KPI/允许符号集，核验IOService/OSSymbol/
   Lilu布局、实际KC解析与加载生命周期；名称匹配尚不足。
2. **真实编译器边界：** 取得兼容LLVM3902实现，或完成并验证Apple所需字节
   降版/隔离协议；确认input/options/TGLLP/metadata/resource bindings、helper
   和reply所有权/错误/同步契约。不能恢复旧C++对象跨版本转发。
3. **Metal373.7完整schema：** 合法取得runtime观察并验证field/bitfield/enum/
   生命周期；实现真正转换和重入/并发策略，取代当前主动拒绝。
4. **约束内加载路径：** 修改Apple组件、自建库及Apple host接受度必须分别
   有实证；目前没有，不可把Developer ID或公证视为自动解决方案。
5. **用户明确授权后的分阶段目标验证：** CPU观察、再部署/加载、最后真实
   Metal Compute分别授权和验收；尚未开始，且前四项不能被授权本身解决。

因此，本轮最重要的实质进展是**真kext链接与后端析构问题已解决，并将若干
原先隐藏的跨版本ABI/危险分支转为有证据的明确阻塞**。完整原生GPU加速仍为
UNMET，不能以“安全拒绝”冒充适配完成。

**本阶段到此停止，等待下一阶段明确授权与上述缺口的实际证据。**
