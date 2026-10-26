# i915 Linux x86_64 UAPI 显式 CPU 模型

`layout_probe.c` 直接包含固定 Mesa26.2.3 的 `include/drm-uapi/{drm.h,i915_drm.h}`，**只打印布局，不调用 ioctl**。`build/uapi-layout-v2/abi.json` 是实际 C 编译结果，Python model 按其精确请求号、size/offset 解码，不以手写近似取代 UAPI。

## 可运行范围

- BO 按4KiB取整的 CPU backing store、配额、会话内 handle 创建/关闭、边界、stale handle、锁。
- Context/VM **模拟标识**；对象中明确 `CPU_MODEL_ONLY` / `gpu_va_available=false`。
- 同步对象只模拟 CPU 显式 signal/reset 和立即检查 wait；不支持阻塞/未来工作依赖。未 signal、失败 submission 都不能产生完成。timeline 接口未实现。
- `UserArena` 仅允许已注册 synthetic address 的 copyin/out，永远不是主机虚拟指针。未知指针、溢出、不对齐、先释放指针都拒绝。
- `driver_name=GA40_MOCK_ONLY`；`require_real_anv_device` 必须 `ENODEV`，不注册 render node、不改 NMDRM 名称。
- GETPARAM、QUERY、MMAP_OFFSET、EXECBUFFER2 明确 `ENOTSUP`；未知请求（包括其他平台编码）`ENOTTY`；不存在真实 mmap、GPU地址、执行或Fence完成。

Linux/Darwin 的 `_IOW` 与 `_IOR` 方向位互换，而 `_IOWR` 两个位都置1，因此对应小结构的双向请求号可相同。不能将这种相同推广到单向请求；例如 GEM_CLOSE 的 Linux `0x40086409` 与 Darwin `0x80086409` 不同。本模型仅接受记录的 Linux 编码；实际 Darwin NMDRM 需要独立 wire ABI/转换合同。

## 实际验证

```sh
python3 -B tools/build_uapi.py
python3 -B -m unittest discover -s drm/tests -v
```

初轮 `logs/uapi-model-tests-015` 保留失败：测试 helper 和 ABI pack 的参数名 `name` 与 VERSION 字段冲突；断言使用旧32B sync wait，与本版本增加 deadline 字段的40B结构不一致。修前源码在 `reference/repairs/uapi-initial/`，修复改参数名、实录 deadline offset32并拒绝未模型化 hints。新构建 `logs/uapi-build-v2-016`、12项测试 `logs/uapi-model-tests-v2-017` 均 exit0，含8线程128次对象创建/回读/释放。旧输出不覆盖。

独立G3随后发现 VERSION 非零copy长度/null指针假成功（F1），原反例在 `audit/drm-safety/`，真实修前源/diff在 `reference/repairs/drm-safety-001/`。修复后name/date/desc均要求合法copyout指针，零长度查询仍允许；同时正确按__s64解码wait的timeout字段。`logs/uapi-model-audit-fixed-029` 共14项通过；`audit/drm-safety/recheck-001/` 独立69控制+14测试及旧成功/新EFAULT对照确认F1/F2关闭，0open。

本模型主动要求同步handle数组4B对齐和精确结构长度，比真实Linux x86 copyin路径更严格；这些EINVAL只验证研究模型的边界，不能证明真实内核在相同输入下的errno。wait是立即CPU状态检查，不实现Linux阻塞/绝对时间合同。设备关闭要求调用者停止并发使用会话，已关闭对象不再有效。

模型限制属于已公布的拒绝边界，不用于启动 ANV。后续实际内核合同见 `drm/I915-UAPI-MATRIX.md` 和 `drm/NMDRM-AUDIT.md`，硬件批准始终NO。
