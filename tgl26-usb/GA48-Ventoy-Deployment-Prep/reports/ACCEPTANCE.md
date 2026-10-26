# GA48 需求 → 实物/命令证据审计

> 本页记录GA48时点验收，不是GA49当前安装就绪证明。GA49撤回Caches必改SSV推断并补做原生包预检，见 [纠错](GA49-CORRECTION.md)。

本阶段验收对象是新介质和部署准备，不包含被明确禁止的目标部署/启动/Metal实验。
下表的“待授权”是真实阻塞，不使用静态通过替代运行成功。

| 原要求 | 具体证据/交付 | 结论 |
|---|---|---|
| GA47实际目录、Git提交、不得覆盖历史 | verify-package固定a9ae966、UPSTREAM_BASE；Git clean；所有解包输出在GA48/private | 完成 |
| 归档存在、83,106,926字节/79.3MiB、指定SHA | PACKAGE.json与实际重算51aaff… | 完成 |
| 246文件/链接、31Mach-O | 每项对manifest核对，另验证归档根收据；PACKAGE.json | 完成 |
| NG/HookCase MH_KEXT_BUNDLE；真实dylib | PACKAGE.json解析filetype11/6，最终audit再次断言 | 完成 |
| Lilu/NG/HookCase版本与依赖 | PACKAGE-CHECK.md、PACKAGE.json、DEPENDENCIES.json；1.7.2/1.0.0/8.0.1 | 静态范围完成；原生注册待授权 |
| donor16.0.32补丁、资源、布局 | 10项MTL+12项旧plugin、6资源精确比较，五个必需目录实存 | 完成 |
| 原作者shader路径，不换GA46隔离版 | git功能diff仅kern_gen11；SerializedBitcode/WithOptions导出及重导出检查、TGLLP | 完成；真实request/reply实测仍待授权 |
| LLVM3802/3902明确保留问题 | PACKAGE依赖清单、TARGET/DEPLOYMENT/FIRST-BOOT报告 | 完成标记，运行依赖未解决 |
| 当前真实EFI与旧副本只读比较 | 原始300MiB分区读取、本轮41OC文件比较、ESP-COMPARISON.json | 完成；原分区前后SHA一致 |
| HP自己的EFI，保留ACPI/USB/输入/网络/音频/SMBIOS/扫描 | current OC与VESA、旧基线相同；builder逐section断言、精确delta仅四路径 | 完成 |
| 真9A49、无8A5A、native平台、Lilu后NG、WEG禁用、HookCase系统侧 | IMAGE.json/CONFIG-DIFF/DEPLOYMENT完整布局 | 完成 |
| 无DellRPL/ADLP/GA32b参数 | bootargs167字节断言及报告 | 完成 |
| Kernel/Block及ICL审查、依赖顺序与失败行为 | Block=[]；读取stock ICL personality无9A49，当前未加载；CONFIG-DIFF/DEPENDENCIES | 完成 |
| PLANES2+0x98风险及分项开关 | 默认noplanesfix、两候选；阐明无FMT独立反向开关、VALD不被关闭 | 完成；不假定运行安全 |
| 真实新IMG、沿用既有Ventoy/FAT方法 | out/HP-Tahoe-TGL-GA48.img；原1MiB/MBR结构保留、OpenCore固定1.0.8 | 完成 |
| 真实NG/已审计Lilu/HP kext；所有Enabled路径 | 85 EFI文件，13 Enabled kext项、ACPI/Drivers/Tools路径核验 | 完成 |
| 匹配ocvalidate、bootargs | 主配置+3候选+VESA均rc0；bootargs167+NUL1字节 | 完成 |
| 分区/FAT/独立重挂载逐文件回读/关键SHA | sfdisk、两份fsck -n rc0、只读loop挂载99文件回读；MEDIA.json | 完成 |
| 本地先生成、U盘真实挂载/空间/目标名空再新增、同步哈希 | /dev/sdb1 exFAT、exclusive create、fsync/sync、最终SHA0facaf…相同 | 完成 |
| 禁止覆盖三份原IMG/内部EFI/默认项 | PROTECTED-BEFORE与MEDIA后哈希一致、ESP-COMPARISON前后相同，无默认项写命令 | 完成 |
| 独立VESA、7MB排错、原Ventoy可选、不用GA32b | 原VESA含igfxvesa且无NG、FAT/OC/Enabled全通过；VESA-RECOVERY | 静态完成，本轮未重新物理启动 |
| 系统端恢复清单和程序，只生成审查不执行 | deployment-review/recovery-review/recovery-kc-review；逐路径恢复与KC分阶段、bash -n | 完成准备；实际恢复待授权 |
| macOS原生codesign/kext依赖/KC不改状态检查 | 实际codesign true rc0、stock ICL rc1、kmutil inspect rc0、providers/kpi/plist读取 | 完成只读证据；包原生签名待staging授权 |
| 如需复制先精确范围，不任意远端写 | TARGET-PREFLIGHT指定Users/Shared新staging、原tar校验/解包/native只读命令与清理范围 | 完成请求说明，未复制 |
| 上游SIP/SecureBoot/签名逐项分类、CSR0+AMFI不误称足够 | SECURITY矩阵、当前CSR0/SIP enabled、GA48无AMFI arg、保留hook风险说明 | 完成；加载条件仍阻塞 |
| 可审查部署顺序10项、每步逆向、注册失败立即停 | DEPLOYMENT顺序0–10、精确目录、review脚本传播rc、VESA-RECOVERY | 完成准备；未实际注册 |
| 首启9A49/NG/TGL后再MetalDevice/Shader/GPU | FIRST-BOOT逐层清单，所有实验另批 | 完成准备，未执行 |
| 本地逐单元commit、不push、不改历史 | GA48独立git提交；无配置remote；GA47固定HEAD clean，历史只读引用 | 完成 |
| 最终四问、制作验证后停止 | RESULTS.md四项回答、ARTIFACTS.json真实收据 | 完成介质/准备交付，不宣布加速可用 |

最后核验命令 `python3 tools/audit-delivery.py` 只读校验本地与USB已有文件和既存证据，
不重新构建、不覆盖IMG、不连接目标执行部署，也不运行上述审查脚本。
