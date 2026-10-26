# GA416 U盘旧引导清理完成

2026-10-25，按用户“删除除了gpu正常的以外的引导……保留新的引导和安装引导”的新指示，在HP NixOS上核对挂载的Ventoy数据分区后执行。

## 保留的macOS镜像

均位于U盘`ISO/linux/`：

| 文件 | 用途 |
|---|---|
| `HP-Tahoe-GA416-L3-6.img` | GPU桌面及一次R8已验证的现用版本 |
| `HP-Tahoe-GA416-OCDBG-BASELINE.img` | 新制独立OC DEBUG内存诊断版本，尚未启动 |
| `HP-Tahoe-Recovery-GA410-CSR0.img` | 既有实际使用的安装/恢复入口 |

已删除其余 **30份旧HP-Tahoe实验镜像**，合计 **40296775680字节（40.30GB／37.53GiB）**。删除前保存明确文件清单、大小、mtime及用户授权；执行前重新核对机器、boot ID、exFAT挂载路径和每个目标。

删除后核对HP-Tahoe镜像仅余上述三份，三份文件的完整SHA256均与删除前一致。其他Linux/Windows安装ISO的路径、大小、mtime保持不变。硬盘EFI没有修改。U盘可用空间约66.05GiB。

原始授权/计划/回执：`private/usb-cleanup/`。
逐文件删除及保留校验记录：[USB-CLEANUP.json](reports/USB-CLEANUP.json)。

后续诊断操作见[Linux结果与OC诊断镜像](GA416-LINUX-MEMORY-RESULT.md)。
