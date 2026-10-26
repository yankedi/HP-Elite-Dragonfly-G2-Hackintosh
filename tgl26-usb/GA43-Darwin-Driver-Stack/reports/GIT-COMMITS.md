# GA43 本地提交台账

分支 `ga43/darwin-toolchain-and-i915`，无 remote / push。
GA42 历史台账原内容保存在 `GA42-GIT-COMMITS.md`；GA43为独立仓库。
本台账每阶段增补已完成提交，当前记录所在提交由后续记录/最终回执补充，避免自引用。

| 完整 SHA | 分类 | 单元 | 验证 | 范围 |
|---|---|---|---|---|
| `a60352c660897ec6b97fbcb2d729e435508e0c1b` | baseline | 封存GA42 git archive继承 | `inherit-seal-002` 四组 sha256sum exit0；diffcheck | 来源验证，非新驱动验证 |
| `9939e3b0d3d9cf918d830276ad5cdb59387362e0` | tests_build | 五步真实Darwin探针、旧LLD适配和系统输入分界 | `darwin-probes-002` 对象/检查PASS、严格链接FAIL、诊断dylib exit0 | 无系统库/SDK/ANV成功 |
| `538c6ffeba7e5f0bf4cf132e9b117172312ac0f8` | tests_build | 真SDK/严格链接gate、隔离下载缓存、cross链接器和pkgconfig | `anv-prerequisite-gate-001`/`anv-kernel-sdk-rejection-001` exit2按预期拒绝；语法PASS | 完整ANV仍BLOCKED |
| `1153591fd1c97e62c75eca1d3d688d23b8ccbc84` | driver | VM/context host规划、官方VM destroy、真实GEM lease/quota及client清理 | `vm-tests-001` PASS3、`vm-darwin-compile-001`、`vm-upstream-source-001` | 无硬件PPGTT/context/submit |
| `2ba885eddde55208b8668f655606a4af6acdef89` | driver | 标准GEM mmap-offset到真实map backend、认证task/cookie寿命 | `mmap-build-002`/`mmap-tests-002` PASS3、`mmap-darwin-compile-001` PASS3对象 | 无BSD fd pager/runtime |
| `1f43ffdafbf16989233f6e33f5b62e2de64efc9b` | tests_build | 原生九单元真实-r组合链接、模块种类/符号输入分界 | `native-relocatable-ga43-001`和inspect exit0；模块尝试exit1旧LLD不识别-kext | MH_OBJECT组合不是kext |
| `be618d1a8eb5bd26a313454ebc59e94d2fe43d40` | driver | 原Linuxclose/exec转BSD，组合测试采用标准宏及mmapcookie | `drm-wire-build-002`、`drm-wire-tests-001` PASS2 | CPU syscall注入，非nativefd运行 |
| `587e78882b2dfe19d1b6d60d86771d8c89718766` | audit_docs | NullMoth/ANV实际调用追踪、单来源shader真实失败 | validator exit0；compiler SIGSEGV-11/gdb定位 | 无Gen12新输出 |
| `32bdad696734f720336ab43b77691662d957a312` | tests_build | GA43 seal入口绑定实际kernel-kit和历史receipt/index | bash syntax PASS；最终create/verify另记 | 不改历史seal |
| `33f20995437d1e8cf28a7c9e5b81125c8ccb3c3a` | driver | 审查F5 alternate close后继续revoke；VM测试遵守gate | `review-close-tests-001` PASS2 ASanUBSan | 原生调度/runtime未测 |
| `f8b5911787d58c64dc1f3c00bf55ec79dd29f863` | tests_build | F1：5 ABI单元同编译、4继承对象/SDK/source/layout/seal强制验来源 | gatePASS/stalepath拒绝；`native-relocatable-reviewed-001` PASS | 模块-kext仍FAIL |
| `ff4b139072a2742979c21f280a593645a09e4b05` | tests_build | F2/F3：真实Mach-O输出/import/LLVM合同、ANV内fresh probe gate | `darwin-probes-003`严格false；全exit0零输出负测拒绝；Undef诊断dylib拒绝 | 正向完整SDK仍缺 |
| `a519e823baa5f0a6d8fdbef033279f25bd3a88e9` | driver | 实际VM/GEM request保活、busy-unbind、首负错/取消/释放，无成功signal | `request-error-tests-001` PASS2、native VM compile PASS | 无GPU fence/submit |
| `5dcca72c5c0cab73dcdc22a724059df9de8a704f` | audit_docs | 保留原始独立审查/澄清、许可矩阵及33项需求映射/七问 | diffcheck；来源/各证据明确分级 | 未自称最终封存/完整PASS |
| `a0e7f953e132aa5208cbde414d75ccef398da9ce` | driver | R2 post-detach统一admission，16孤儿VM不变量witness和count防御 | `review-admission-tests-001` PASS2、native2单元PASS | 已获准的并发操作可完成；无GPU动作 |
| `21d05baf6da66f0ee0100dd3091204d58d8a1ebf` | tests_build | G1-G3工具身份/lazy依赖/精确rpath，拒优化Python，ANV TU输出合同 | 新004仍false；lazy/rpath/O负测PASS；独立CLOSURE无剩余scope缺陷 | 正向SDK分支后来由新输入实跑 |
| `da74f8426fcaa9b364bb5f5d9a35d543822e9e44` | audit_docs | 新本地GA45SDK/GA46linker发现，严格五组全部PASS；独立closure保留 | `darwin-new-inputs-001` stricttrue，`anv-new-inputs-001`真实Meson初试 | 非ANV/runtime成功 |
| `b7b585dcca75fca0cb59c30f15a6dea931964f94` | tests_build | 真实SDK版本/platform_version，C/C++/ObjC cross链接绑定，已有工具PATH | `anv-new-inputs-003` builtin/atomic/systemlink PASS，首错dl_iterate_phdr | 无ANV产物 |
| `4f591cc25cdf1f85889ada0d670e094f3ddae8d4` | driver/anv | 保留官方Apple LC_UUID identity，替换ELF-only Meson要求 | `anv-darwin-build-id-001` fuzz0/nativeUUID link PASS；下一依赖libdrm | 未改官方compiler |
| `d56e01fefaa91d841b2d7dc7ffdaba70dd407140` | driver/libdrm | Darwin feature宏/ioctl头修复，严格链接真实libdrm子集dylib | `libdrm-darwin-cross-002` PASS；2受影响CPU sanitizer PASS | 非完整libdrm或nativefd运行 |
| `4e0f0b4532f91987fc31a6f036aa6002b00599fa` | tests_build | 系统同来源CLC哈希固定、实际Meson/Ninja管理生成头和Darwin全量build | configurePASS/CLC8+blorp SPIRV生成；brw_eu真MachO PASS；build首错imageguard | 非最终ICD |
| `2f0b0c5fcd859916b769b079ce702da14ad149e7` | driver/anv | Darwin image modifier布局/初始化/查询guard一致 | fuzz0/全部per-hw image单元PASS，下一errorfutex | 未谎报KMS/不删Graphics |
| `13ea6e7c35fce2d2679c4449419dfa3d249c7c9f` | driver/anv | 公开Darwin address wait/wake，绝对超时转换和错误语义 | `anv-address-wait-link-001`严格7imports PASS；build到ICD最后link | host同步，native运行未验，不是GPU fence |
| `45906feb4c88c0e3a3d988ce458032393b7d5f4a` | driver/libdrm | 标准syncobj ioctl封送，无CPU fence/能力宣告 | `libdrm-syncobj-tests-001`3ASanUBSan PASS；真实crossdylib PASS | 内核syncobj尚无实现，保留负错 |
| `320a44187eafb1c9a852295cde861b35b7433e47` | driver/anv | 真正macOS WSI的Foundation/CoreGraphics依赖 | fresh7patch fuzz0/1077项编译和ICD JSON PASS；最后弱符号link失败保留 | 不是Vulkan初始化 |
| `c33e24bb4539c481584c14718676d964014be458` | driver/transport | 真正IOConnect用户API和共享kernel/user wire，显式connection非fd | 11imports/5exports严格linkPASS、2ASanUBSan PASS、kextlinkPASS | native运行及fd/pager/ANV接入未验 |
| `df4b62856698c447a91a12566783c09563a850af` | tests_build | 真实kext封装和固定hash目标KC nlist比较 | `native-package-001`PASS；355中354有external name，发现cxa_atexit | 名字匹配不等于目标KPI/C++ABI |
| `fee2e07aede67c8e442b5364c3d27f693d832356` | tests_build | LLVM后端保留kernel析构，拒用户atexit依赖 | 真-kext/354目标KC名字PASS；析构relocation仍在，oldnegativePASS | 非KC/load验收 |
| `3b1b471c4f118fa0bf625340ea115e08cb6888d7` | tests_build | 已有签名验证精确KDK本地提取/pbzx和真实KPI合同 | exactbuildPASS；354names有provider、1仅private新发现 | 所有Apple输入忽略，无新下载 |
| `950d9ac28cc4bc432c318a3eb5dab1a93d9241ac` | driver/xnu | 使用精确KDK提供的已声明Mach thread_call_allocate | 真-kextPASS；354imports全属于已声明KPI/IOPCI | 不新增private依赖；非C++ABI/load验收 |
| `80f33071e2b69f94d50b8c4846b4062d3681ce4c` | driver/anv | 独立审查N2修Apple wait正数归零，保留N1/N3原发现 | `review-n2-wait-contract-001`ASanUBSan fault注入PASS | 不是os_sync原生运行 |
