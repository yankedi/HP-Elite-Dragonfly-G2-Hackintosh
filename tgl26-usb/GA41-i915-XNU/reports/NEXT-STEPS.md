# 下一工程建议与硬件授权条件

本文件是建议，不是自动继续命令；本轮不部署、不加载kext、不运行真实batch。

## 唯一推荐的下一切片

先取得合法完整Darwin用户SDK和目标Tahoe25G83 KDK/IOKit链接环境，
把已有native Mach-O可编译源码接入**真实per-open/client生命周期**和
受控设备query契约。继续复用本轮Create/Publish seam，不另建CPU mock。

1. 用户态shim目标编译、libc/IOKit链接和独立进程加载；完整ANV平台依赖真实修复，
   不把Linux.so改扩展名。公开kernel header kit不能替代用户SDK。
2. GPU资源唯一所有权、NMDRM fd/IOPCIDevice/accelerator BDF身份绑定、device removal，
   真实query值来源与长度/copyin/out失败；缺这些不宣称i915。
3. 原生GEM map/close/taskDied/fd duplicate真实语义和卸载保活，
   cdev自动copyout回滚问题明确解决；MapOffset/mmap pager或经过审核的等价transport。
   只有真实kernel CPU页生命周期过关后才进入DMA/PPGTT。
4. 官方TGL GGTT/PPGTT/context/RCS/exec、DMA/cache；
   syncobj/dma-buf sync_file/fence/completion/IRQ/reset一起构成首次执行合同。
5. NMXGPU/Accelerator缺失来源/实现补全，以及插件port→PCI→ICD一致性，
   然后才申请短小Compute Fence＋CPU读回试验。

## 何时申请什么授权

**现在不是GPU batch实验就绪。**
未来只申请真实设备Query或CPU GEM测试时，应先具备目标编译/链接产物、
来源许可、资源唯一所有权、卸载/失效句柄/失败释放/越界/copyin/out完整负例，
且准确说明会加载什么和是否影响现有显示驱动；这仍需新的明确批准。

申请第一次GPU Compute前，额外要求：

- ANV与native transport可链接、导出/版本一致，真实i915 query非静态填值；
  初始化硬探针（含PRIME/syncobj/timeline）符合被声明能力。
- 每个BO已证明实际DMA/地址空间/缓存语义、pin/ref与VM关闭一致；
  不存在把host虚拟地址当GPU地址的路径。
- context隔离、engine唯一资源所有权、提交事务和有界batch范围清楚。
- 完成/fault/timeout/reset不能死等；设备丢失时fence以错误结束，资源按引用顺序清理，
  恢复路径已隔离测试/静态核验；保留原显示/SSH的回退方案。
- 小型可复现Compute输入/expected CPU readback、退出条件和采证命令事先固定，
  然后请求用户单独批准具体一次硬件操作。

WindowServer/IOSurface/eDP/scanout/显示电源整合必须在Compute正确后作为独立目标。
