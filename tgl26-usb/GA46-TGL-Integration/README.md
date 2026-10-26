# GA4.6 — Apple TGL Native Driver Integration

HP Elite Dragonfly G2 / i5-1135G7 / Iris Xe `8086:9A49` /
macOS Tahoe `26.6.2 / 25G83` / x86_64。

**已解决真实 `MH_KEXT_BUNDLE` 链接；完整功能集成仍未达成。**
离线工程已交付，状态：`KEXT_LINKED`、`USERSPACE_DYLIB_LINKED`、
`RUNTIME_SYMBOL_UNVERIFIED`、`ABI_UNVERIFIED`、`DEPLOYMENT_BLOCKED`、`GPU_NOT_TESTED`。
当前 Compiler Adapter 和 libxedrv 为明确拒绝未知 ABI 的隔离版本，不能部署为
可工作的 Metal 驱动。详见 [完整中文报告](FINAL-REPORT.md)。

## 真实证据

- 隔离构建 LLVM PR [#204805](https://github.com/llvm/llvm-project/pull/204805)，
  pinned head `d575e43643f7c90a1a2728352a24867d7105d9e9`。
- 合法 kext fixture、完整 NootedGreen 真链接，外部/本地重定位及模块生命周期
  节检查；上游 kext/objcopy 两项回归通过。
- 最终 native-only kext：1606 个重定位、392 个 undefined；全部有名称级
  provider 候选，其中 362 个 kernel 名称仍未确认为目标公开 KPI。
- 同 image LLVM C API 的真实 bitcode 解析/序列化，8 线程 1600 次 roundtrip，
  ASan/UBSan 检查通过；不是 Apple LLVM3902 降版实现。
- 18 项 donor patch 计划，仅应用 3 项链接/路径编辑到私有副本，独立差异/
  反向 SHA 验证与重复 staging 一致；实际检测到原 CodeDirectory 页哈希失配。

## 入口与交付

```sh
make check CHECK_OUT=logs/check-UNIQUE_ID
```

此入口只运行宿主 CPU 测试和交叉构建；不运行生成的 Darwin 文件。
已执行并通过：`logs/check-final-001.log`。

- [构建状态](reports/BUILD-STATUS.md)
- [编译器 ABI](reports/COMPILER-ABI-RESULT.md) / [依赖图](reports/COMPILER-DEPENDENCIES.json)
- [Metal ABI 与待授权探针](reports/METAL-ABI-RESULT.md)
- [原生入口审核](reports/NATIVE-BRANCH-REVIEW.md)
- [donor staging](reports/DONOR-STAGING-REVIEW.md)
- [五类签名加载判断](reports/SIGNING-GA46.md)
- [产物哈希封存](reports/ARTIFACT-SEAL.json) / [本地提交](reports/GIT-COMMITS.md)

私有产物：`staging/final-001/`。这是一套离线证据/隔离构建，非安装包。
GA45 原始报告移至 `reports/history-ga45/`，其历史相对路径仍指 GA45；
基线 `971c2a1` 的原仓库保持只读。公开来源锁定沿用继承清单。
SDK、Apple donor、工具链大产物和日志均 Git 忽略；未 push。
本阶段未安装/加载/修改目标驱动，未执行目标新程序或 GPU 工作，等待单独运行授权。
