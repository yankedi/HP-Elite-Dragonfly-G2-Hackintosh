# GA4.10 本轮启动前实际操作记录

本轮依照用户“完成下次物理启动前所有操作、保留开机、把操作及SSH方式落盘”的指示执行。
命令原始证据在`ga410/private/commands/`，交付包中的`operation-evidence.tar.gz`保留本轮命令、实际rc/stdout/stderr和关键旁证。
历史安装和KC修复收据保留；本轮没有重新注册KC。

## 已完成操作

1. 通过已固定host key的Recovery root SSH2222确认25G83、Data/System/Preboot实际挂载和工作目录；16项KC清单再次通过。
2. 检查目标Remote Login override、user/admin/authorized_keys元数据；开发机普通公钥与目标匹配。
   从已认证Recovery读取目标普通系统host**公钥**并建立项目独立pin；没有读取/复制host私钥或客户端私钥。
3. 只读复制目标KextPolicy和WAL并查询，三项新Bundle ID没有批准记录。结合ad-hoc认证拒绝及固定上游Metal文档，确定实验CSR0x203及AMFI参数，依据写入`FIRSTBOOT-SECURITY.md`。
4. 从已签名独立staging导出Lilu/NG，完整匹配签名清单；原生strict/deep结构验证通过。
5. 从保留GA48制作两份独立镜像：TGL实验、CSR0独立Recovery。保留HP布局及完整驱动实现；三项系统kext仅由AuxKC提供，EFI只注入Lilu/NG。
6. 同版ocvalidate rc0；检查全部启用kext路径/架构/版本/依赖顺序、策略、设备属性；本地mtools回读完整EFI相等，前1MiB引导/分区表不变。
7. 交付USB后对完整镜像做原生SHA256、只读挂载、全文件原生SHA256清单与配置回读；Recovery BaseSystem/Chunklist保留原字节，卸载/分离成功。
8. 发现镜像根继承的FIRST-BOOT.txt仍写VESA，已只修改两份**新镜像**的该说明，原子替换后重新原生只读清单与完整哈希确认。之前候选哈希保留在收据中；以FINALPREP-DELIVERY.json最终值为准。
9. 安装一次性LaunchDaemon及受限输出/超时collector，原生bash语法和plutil检查通过；未在Recovery bootstrap，marker不存在，结果目录为空。未运行Metal/GPU测试。
10. 编写UUID定位的Recovery wrapper，复用原元数据保留恢复工具；在当前真实Recovery完成多次随修正必要的非破坏预检：备份22项、已装组件204项及KC清单全部通过。
11. 实际执行仅采集的`--collect`；归档当前KC、现有首启目录及历史panic/WindowServer报告，未把这些旧报告当作新驱动故障。
    最终pax版本rc0、stderr为空，11项归档/记录SHA256通过，native tar可读；离机独立抽取AuxKC后其SHA256匹配已发布新KC。
12. 最终SSH身份/boot session复核仍为当前Recovery；完整11变量NVRAM字典与KC修复后基线相同，CSR raw0，authenticated-root enabled。
13. 将说明、SSH连接方法、工具、状态、清单及原始操作证据交付NixOS工程、目标Data和Ventoy；实际交付校验另见HANDOFF-DELIVERY.json。

## 本轮出现并已处理的错误

- Recovery没有`sqlite3`。改为通过已认证SSH只读复制KextPolicy+WAL，在NixOS查询；初次只复制主库为空，随后使用独立新文件名复制完整pair后成功。目标数据库从未修改。
- 原runner拒绝覆盖已有本地下载文件，保留拒绝记录并换独立文件名，没有抹除现场。
- 最初只采集版本用`find -exec cp`向exFAT复制扩展属性，子命令报错但外层find rc0；**该次不能算完整成功**。
  修正为单次native pax，直接传播tar错误，并对归档生成/回读SHA256；重新实测成功。初始有误采集目录保留，最终成功路径在FIRSTBOOT-STATE.json记录。
- 初版嵌入启动说明过时，已更正新镜像并重新做完整验证；两次版本/哈希均保留，不把早期哈希当最终交付。

## 当前落点及未发生操作

- 当前准备完成状态是`PREBOOT_PREP_COMPLETE / READY_FOR_USER_FIRST_TEST_BOOT`。
- `POLICY_APPLIED=false`，运行时kext认证/批准/驱动加载及Metal未实测；不将AuxKC生成或ad-hoc结构验签当作正常可信加载。
- 当前SSH在线、机器开机，没有重启或关机，没有改内部EFI、默认启动项、原GA48/VESA镜像或Reset NVRAM。
- 原VESA在本轮开始与结束的实际SHA256均为`5f8c7b8257d16a7039daa42bc9e832b734f731dcc965045cde4e90aef1bbb7f9`；这仅证明本轮未修改，不能替代更早历史版本的其他哈希。
- 下一步只能由用户选择何时物理引导新镜像；首次按控制面取证→MetalDevice→ShaderCompile→小规模GPUCompute逐层推进。
