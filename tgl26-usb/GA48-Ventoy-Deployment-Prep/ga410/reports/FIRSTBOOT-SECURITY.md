# GA4.10 首启实验策略：选择依据与边界

## 已有证据

1. 本机native诊断对三个kext报告`Bad code signature`；它们是本机重签的ad-hoc实验副本，不具备正常Apple/Developer ID kext信任身份。
2. 对离线目标KextPolicy及其WAL进行只读SSH复制后，NixOS SQLite查询这三个Bundle ID，批准记录为零。没有编辑目标批准数据库。
3. 固定GA47/JulioNectar基准的`docs/METAL.md:19–27`及`docs/CATALOG.md`记载：这套ad-hoc用户态Metal/编译器栈涉及AMFI library validation，作者方案使用`amfi_get_out_of_my_way=1`。
   这是相同实现的上游依据，不是HP已完成动态Metal加载的证据。
4. 当前真实Recovery允许离线写入，因此系统组件和AuxKC已完成；当前raw CSR0不等于下次安装系统会允许这些组件加载。

## 本次准备的实验配置

从上游`0xA13`去除没有本机必要性证据的`0x10 AppleInternal`和`0x800 unauthenticated-root`，采用其与本次安装有关的子集**`0x203`**：

| 位 | 作用 | 本次依据 |
| --- | --- | --- |
| 0x1 | 允许不受信任kext | 三项kext只有ad-hoc身份，原生认证拒绝 |
| 0x2 | 放宽filesystem保护 | 保留已授权原布局的GPUBundles等受保护Data路径维护能力 |
| 0x200 | 允许未批准kext | 三项无正常信任身份且目标批准数据库没有记录；首次实验不依赖启动后再点批准 |

此掩码是**有依据的实验配置，不是已在HP证明的最小充分值**。
准备`amfi_get_out_of_my_way=1`以匹配原作者完整用户态栈的加载方案；它会全局放宽AMFI，范围超过单个GPU插件。
上游NG已有`_cs_validate_page` hook也保留，不能宣称此实验没有代码校验策略放宽。
保留authenticated-root/SSV、OC SecureBootModel原值Disabled，不修改其他SIP位，不引入新的绕过kext。

## 如何生效与如何撤销

- 新实验镜像NVRAM Add为`03020000`，Delete明确包含CSR及boot-args；不会依赖旧CSR3镜像是否留下变量。
- WriteFlash=false维持既有设置；volatile注入必须按每个引导镜像自包含处理。Delete依然可能影响原持久变量。
- 只有用户真正使用新镜像启动后，才能检查实际CSR/boot-args及加载情况。**当前POLICY_APPLIED仍false**。
- 独立Recovery CSR0镜像显式Delete/Add原CSR0及VESA参数，随后按恢复工具撤销目标组件和KC；不Reset NVRAM，不自动执行失败过的原生CSR写入。
- 没有给当前Recovery强行写CSR或AMFI；本轮完整NVRAM前后字典会在最终校验中比较。

## 状态用语

PREBOOT_PREP_COMPLETE / READY_FOR_USER_FIRST_TEST_BOOT指所有启动前操作已落地。
它们不等于已完成策略应用、正常签名信任、驱动加载、显示、Metal或Shader/GPU功能验收。
原生`create`的默认本地`--no-authentication`构建模式也不能作为受信任加载证据；本次没有使用`-z`/`--no-authorization`。
五条LLVM3802/3902旧强依赖保留；若实际加载器报缺失依赖必须记录并处理，本次不谎称已验证这部分运行链。
