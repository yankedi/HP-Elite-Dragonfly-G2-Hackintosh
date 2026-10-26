# 源码身份、实际复用与移植边界

## 固定来源

- Linux **v6.18**，annotated tag `f7b88edb52c8dd01b7e576390d658ae6eef0e134`，
  peeled commit **`7d0a66e4bb9081d75c82ec4957c50034cb0ea449`**。
  来源 torvalds/linux；原始 codeload archive 完整保留，SHA256
  `2617efd103533b57613d16f144ceea575b1a6b890ce5e16201b1d254e2b7b33c`。
  只解出 `drivers/gpu/drm/`、`include/drm/`、`include/uapi/drm/`、
  LICENSES/COPYING/Makefile，共7728文件，逐文件hash见 `sources/linux-files.json`。
  这是固定官方源包的部分解出，不是已构建的Linux内核。
- Mesa26.2.3固定 `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`，
  NullMoth固定 `47f818b11cef59acb480210afdf9065fdd44e356`，均从GA40只读使用。
- XNU公开参考 `xnu-12377.121.6` / `ac9718fb1af618d5ce8678d0dc6e8a58f252216f`，
  **不是目标25G83的KDK**。IOBuffer/IOMemoryMap/IOLocks头与实现用于API语义核对；
  不能因参考头存在而声称目标ABI已验证。
- `logs/nullmoth-remote-001`：本轮查询官方HEAD/main仍为固定47f818b，
  没有发现该上游入口中一个更新、完整且可验证的NMXGPU实现。
  这只覆盖指定上游，不是对整个互联网“不存在任何实现”的断言。

## A/B选择：根据实际依赖而不是预设

`reference/linux-port-dependencies.json`记录7个真实源文件的直接include。

| 路径 | 实际依赖 | 对A/B的影响 |
|---|---|---|
| `i915_gem_create.c`498行 | DRM fourcc、display、lmem/region、PXP、i915_drv、extensions/trace | 不能把整个文件直接当OS无关函数库 |
| `i915_gem_shmem.c`669行 | Linux shmem_fs、pagevec、swap、uio、scatterlist | 页分配/回收强依赖Linux VM，XNU不能机械改名 |
| `drm_gem.c`1620行 | file/fs/mm/pagemap/dma-buf、GEM/VMA manager | A需要Linux文件、VM、DMA reservation等兼容层；远超过一个锁或malloc |
| `i915_gem_execbuffer.c`3645行 | dma-resv、sync_file、uaccess、GT/ring/context/PM/PXP | 提交不能由CPU页管理替代 |
| `gen8_ppgtt.c`1085行 | GEM对象、scatterlist、GT/GTT、vgpu | Gen12页表算法可逐步复用，但绑定/DMA/TLB必须原生承接 |
| `i915_request.c`2314行 | dma-fence链、irq_work、scheduler、engine/reset/breadcrumbs | A必须保留并移植真实调度/完成语义，不能立即signal |
| `drm_syncobj.c`1744行 | anon inode、eventfd、file、sync_file、uaccess | 标准fd共享/等待不是整数表可替代 |

选择**B式窄切片**开始：原样复用Create/Publish编排和UAPI，
在明确私有类型边界上接原生页/锁/映射；后续GT算法仍优先复用官方代码。
这不是“B已完成整个驱动”，也不排除后续某些DRM设施采取A式兼容。
本轮不引入旧世代display、OA perf、PXP、GuC、lmem等与最初CPU页闭环无关实现；
TGL未来的GGTT/Gen8+PPGTT、RCS、context、cache、completion/reset仍是必要工作。

## 真正编译进新Foundation的Linux函数

| 上游文件/函数 | 本地编译入口 | 修改 | 实际覆盖 |
|---|---|---|---|
| `i915/gem/i915_gem_create.c:72 i915_gem_publish` | `i915-xnu/gem/upstream_create.inc` | 函数体逐字不改 | handle持有引用后drop allocation引用，失败亦释放 |
| 同文件`:224 i915_gem_create_ioctl` | 同上 | 函数体逐字不改 | system region选择→create_user→publish编排 |
| `include/uapi/drm/drm.h` | `gx_gem.c/gx_ioctl.c` | 原始文件不改；编译边界抹去`__user`稀疏标注、正确定义`__packed`属性 | GEM_CLOSE结构/请求合同 |
| `include/uapi/drm/i915_drm.h` | 同上 | 同上 | GEM_CREATE布局及标准i915 UAPI定义 |

提取脚本 `tools/extract_i915_create.py`，逐函数hash见
`sources/i915-function-reuse.json`。**两个函数不是完整GEM实现**：
`__i915_gem_object_create_user`、handle表、refcount等hook是新写的窄系统接口层，
其私有小结构明确不与Linux完整drm_file/i915私有结构二进制兼容。
`drm_gem.c`等其余文件只作合同参考，未编译/移植进本轮库。

Mesa `src/intel/dev/intel_kmd.c`原样编译进CPU整合测试，
查询函数经新libdrm边界，nmdrm应被拒绝；完整ANV另行真实Linux构建。
没有重写Metal前端或BRW编译器。

## 许可证和私有交付

Linux整体发行GPL-2.0-only，但**本次提取的两个Intel函数原文件明确SPDX:MIT**；
不能把它们误称GPL函数，也不能由此把整棵Linux改授MIT。
完整源包各文件许可/双许可/例外分别保留，以对应文件声明为准。
UAPI保留原始版权/许可；用户态包含UAPI不等于许可整个内核实现。
新Foundation源码MIT，全文及Intel版权说明见 `sources/licenses/GA41-MIT.txt`。
NullMoth PolyForm Noncommercial边界仍在GA40原许可；本轮没有把其实现复制进新GEM库。
Mesa、libdrm、XNU/公开kernel header kit分别保留自己的许可/来源记录。
没有公开push、PR、上传、kext分发或许可证兼容性已解决的声明。
