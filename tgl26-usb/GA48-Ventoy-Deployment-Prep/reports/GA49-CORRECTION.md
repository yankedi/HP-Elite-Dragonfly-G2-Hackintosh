# GA49 对 GA48 路径判断的纠正（2026-10-23）

**撤回 GA48 中“`/` sealed/read-only，因此 `/System/Library/Caches/xe.bundle` 无法安装、必须修改 SSV”的判断。**
当时未检查 firmlink，依据不足。这一错误也影响了旧部署/恢复脚本的预检，现已在本地修正，未在目标运行。

GA49 本轮目标实证：

- `/usr/share/firmlinks` 有 `/System/Library/Caches → System/Library/Caches`。
- 逻辑与Data实路径的设备号、inode都相同（16777231、20419）；df都为 `/dev/disk1s1`，挂载在Data卷。
- Data卷可写，Caches为root:wheel 0755、sunlnk，无restricted；root的只读access(W_OK)检查为yes。
- `sunlnk`不是`restricted`；不能由它推断不能在目录内创建xe.bundle。
- 根卷依然sealed/read-only，SIP/authenticated-root依然enabled。这不矛盾。
- **真正的路径权限阻塞**：`/Library/GPUBundles`带restricted，root access(W_OK)=no。
- W_OK不是实际写入/系统MAC/sandbox许可证明，本轮没有创建任何写探针、改变flags/权限或关闭保护。

因此仅就Caches路径而言，没有证据要求修改SSV或authenticated-root；原作者安装器本来也注释它是writable firmlink。
完整安装仍受GPUBundles权限、真实签名/信任、KC条件与插件依赖约束，不能反向推断root可任意写Data路径。

本轮获单独批准的staging原生结果、精确KDK资源、安装前提和九问，见 `../ga49/reports/RESULTS.md`。
旧 `reports/ARTIFACTS.json` 及其文档hash是GA48封存时的历史收据，不重写它来掩盖本次纠错；
GA49提供新的证据收据。所有IMG字节保持不变。
