# GA43 继承基线

GA43 分支：`ga43/darwin-toolchain-and-i915`。独立 Git，无 remote。
通过 `git archive` 继承 GA42 已提交源码，保留 GA42 文件内容；继承的
FINAL-REPORT、报告及台账均为历史结果，不是 GA43 成功声明。

- 来源 HEAD：`ebc63b2bf254cc867b544ad7232ed7860580cb3f`，源树 clean。
- GA42 receipt SHA256：`fe3534a314a9cbab7442f8d02db1438f4192183e56fc33ce23496f75709f34af`。
- GA42 seal SHA256：`4d5545d57ca56656acb4e34562a0c531794c43c59a085846ee4233660a3bf90f`。
- `logs/inherit-seal-002/`：sha256sum 实际校验 manifest、本地文件、kernel-kit
  和历史 seals，exit 0。`inherit-seal-001` 工作目录有误，子检查失败被最后命令
  的 exit 0 掩盖，原输出保留；不能用该次总 exit 判断 seal 成功。
- 规定的 GA42 `reports/NEXT-STEPS.md` 不存在；依赖链实际在 FINAL-REPORT E 节。
- 九个原有对象位于只读 GA42 `artifacts/native-final-001/`，不重新生成基线对象。
- GA42 `reports/OFFLINE-EXCEPTION.md` 和 `logs/anv-040-meson-linux-parse/`
  中未授权下载历史保留；本轮无追认、无自动下载。

固定输入：Mesa `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`；
Linux `7d0a66e4bb9081d75c82ec4957c50034cb0ea449`；
NullMoth `47f818b11cef59acb480210afdf9065fdd44e356`。

工具链初查发现本地 Android build-tools 缓存中的 LLD 含 Darwin flavor。
`logs/cached-lld-001/` 的 `--version` 参数被该旧版忽略；尚未证明动态库链接。
下一步执行无系统依赖的 Mach-O 链接探针，再分开验证 SDK/libSystem/libc++。

离线、历史树只读、无目标机/安全策略/EFI/GPU 操作。所有真实 GPU 状态 NOT_TESTED。
