# Donor16.0.32 私有staging及二次审核

已实际运行`tools/stage-donor.py staging/donor-native-001`，并在最终make check
生成第二个独立输出，18项计划、前后/反向SHA完全一致。源只读GA45 donor未写入。
全部原字节、偏移、唯一条件、替换字节、安全判断和每文件SHA在
`reports/DONOR-PATCH-PLAN.json`，Apple文件仅在Git忽略的staging。

## 实际应用的3项（仅离线实验副本）

- MTL header ncmds/sizeofcmds：增加1个LC_LOAD_DYLIB，不改变filetype。
- 原始header padding中写入libxedrv绝对install path；111个替换字节加原有
  尾部NUL覆盖112字节command，完整Mach-O重解析通过。
- MTL compiler plugin path重定向到继承的xe.bundle候选路径。

此副本不是安装布局：目标绝对路径、@rpath、host许可、compiler ABI和真实
libLLVM3902提供者未成立，状态PRIVATE_OFFLINE_STAGED_NOT_DEPLOYABLE。
`PrivateFrameworks/../Caches`路径并不证明sandbox规范化后会接受该插件。

## 其余15项

保持原始字节。FMT/PLANES2/VALD因25G83语义未确认保持staging-only；
NOCCS3/NODEPTH/NOAUX、compression/fastclear/RPL L3和clear/VS绕过均不应用。
未更改PCI9A49、Tiger Lake profile、Display12、原生compression/AUX或Apple
scheduler/memory/context/提交逻辑。旧全表patch工具已从本轮构建入口退出。

## 独立验证的范围

`tools/verify-donor-stage.py`不导入writer或原配置，独立计算每一个实际变化
offset集合、确认排除项未变、检查无重叠，并反向恢复三个完整原文件SHA。
`logs/check-final-001.log`记录两个实际staging输出均通过。
这是同一工程Agent进行的独立实现/二次审核，**不是另一位人员或独立Agent
对Metal运行语义的背书**。它证明字节事务，不证明runtime安全或可部署。

## 签名的真实离线证据

新增CodeDirectory页哈希审计：原donor MTL的1286个SHA256/4096B code pages
全部匹配其存储CodeDirectory；修改副本第**0、1、162页**不再匹配。
`reports/DONOR-SIGNATURE-PAGES.json`为实测输出。未验证CMS证书链或信任根，
未重签；绝不把原LC_CODE_SIGNATURE仍存在当作修改后签名有效。

## 原生源码复核结论

详见`NATIVE-BRANCH-REVIEW.md`：局部默认关闭并不足够，其他入口曾可达
旧IOAF/RPL/DYLD行为；最终native-only dispatcher隔离这些路径。尚未获得的
目标ABI/KC/host政策证据均不能靠字节匹配、boot flag或签名证书替代。
