# ANV 到 macOS/8086:9A49 的实际阻塞

## 1. 分开看“能构建”与“能初始化设备”

实际构建命令、结果和本机最早缺失依赖见 `intel/ANV-BUILD-REPORT.md`；缺SDK、依赖或Meson平台条件的构建失败不能冒充运行时Intel设备错误。反过来，Linux编译通过也不证明Darwin能链接/加载或拥有内核后端。

下面的设备序列是固定Mesa26.2.3源码推导及CPU函数回放，**没有在macOS运行ANV或向设备发ioctl**。没有用户态libdrm/节点/PCI适配时，会在这些i915门禁之前失败。

## 2. 枚举/PCI门禁在最前面

`anv_physical_device_try_create` (`src/intel/vulkan/anv_physical_device.c:2816–2859`) 需要可打开的render node、可用render位、PCI总线及vendor8086。`intel_get_device_info_from_fd` (`src/intel/dev/intel_device_info.c:1913–1961`) 还需要 `drmGetDevice2` 提供真实PCI信息。标准Linux libdrm依赖的节点/PCI发现和Darwin devfs/IOKit不是自动兼容；无libdrm的Mesa fallback只会失败，不能靠拷贝头文件补齐。

因此 **节点/PCI/libdrm shim不存在时的最早阻塞是transport/enumeration**，而不是Shader、submit或IOSurface。

## 3. 即使存在枚举shim，NMDRM当前身份仍被拒绝

NMDRM `kexts/NMDRM/nmdrm.cpp:59,121–127` 返回driver name **`nmdrm`**。Mesa原样 `src/intel/dev/intel_kmd.c:31–52` 在非virtio路径仅认可 **`i915` / `xe`**，故返回 `INTEL_KMD_TYPE_INVALID`；`intel_device_info.c:1957–1961` 失败，ANV将它转成 `VK_ERROR_INCOMPATIBLE_DRIVER` (`anv_physical_device.c:2857–2859`)。

CPU执行证据：`drm/tests/kmd_identity.c` 编译原样Mesa `intel_kmd.c`，只用明确命名的测试stub替换版本查询和virtio判断。`logs/kmd-identity-build-fixed-030`、`logs/kmd-identity-run-031` 均exit0，7控制：nmdrm/GA40_MOCK_ONLY/unknown/NULL被拒，i915/xe/显式virtio分支分类正确。没有fd访问，也没有ANV初始化成功。

首个编译尝试027因C引号include优先引用原virtio头而失败；030明确通过原guard和 `-include` 测试stub隔离依赖，**没有修改原函数或源树**。该依赖stub不是Darwin/libdrm实现，不能拿正控制“i915”字符串证明设备可用。

## 4. 不可用“改名i915”绕过缺失合同

版本身份只是第一个拒绝点，不是移植实现。真实i915路径紧接着进入 `src/intel/dev/i915/intel_device_info.c:561`：

1. `GETPARAM(I915_PARAM_CS_TIMESTAMP_FREQUENCY)` (`:567–571`)；TGL版本≥10，查询失败即返回false。
2. revision/topology及可选hwconfig/memory-region信息，TGL拓扑不足无法继续 (`:574–596`)。
3. aperture/GTT与tiling能力，其中 `has_get_tiling` 需要真正的GEM对象；之后才继续mmap、userptr、context isolation等信息 (`:614–633`)。
4. 设备信息之后ANV自身还检查更多GETPARAM、PRIME/dma-buf、同步对象/timeline及其它初始化条件。

NMDRM没有任何这些i915命令case，默认返回 `ENOTTY`，非PRIME的generic GET_CAP返回 `EINVAL`。因此 **第一个实际i915专用内核缺口是可靠的GETPARAM/拓扑设备信息后端，后续第一个不能只靠只读查询补齐的关键基础是GEM对象/映射/所有权**。后续完整列表、结构体与调用路径见 `drm/I915-UAPI-MATRIX.md`。

不同函数属于不同初始化阶段；不能把稍后ANV参数阶段的HAS_WAIT_TIMEOUT写成整个device-info链最早query。也不能把 `has_context_isolation` 的最终检查误写为它一定在所有GEM/tiling探针之前执行。

## 5. 内核边界与私有资源边界

- **GEM/CPU映射**：MMAP_OFFSET只是offset token，还需要真正的cdev mmap、页所有权、长度/权限、缓存/销毁语义。模型backing store不是它。
- **GPU VM/Context/Submit**：PPGTT/GGTT、GPU VA、context隔离、驻留、命令引用、RCS执行均须真实内核行为；不可返回模拟成功给ANV。
- **Sync**：syncobj、可导入导出fd、Fence完成/失败/超时、IRQ/reset以及与BO释放的一致性必须真实实现。CPU显式signal不是GPU完成。
- **IOSurface/WindowServer**：NullMoth的NVK私有假fd资源导入/共享标记不能直接用于ANV；普通Vulkan Buffer或host-pointer import不自动建立IOSurface跨进程可见性。
- **显示**：NMIntelFB只是固件线性scanout接管参考，无法代替compute/render内核后端。它和真实i915必须有明确PCI/BAR/IRQ/电源资源所有权，避免与Apple现有Intel驱动冲突。

## 6. 本轮结论

首阻塞按条件准确分层：**本机构建依赖/SDK → Darwin transport及真实PCI枚举 → nmdrm身份拒绝 → i915 GETPARAM/拓扑 → GEM/映射/VM/context → submit/sync → IOSurface/WindowServer**。这些不是一个统一“需要适配i915”的口号。

本轮未把任何未实现ioctl改成成功，也没有把nmdrm改名。下一项工程唯一推荐为 `GA41-NEXT-STEPS.md` 的真实设备探测与GEM内存对象闭环；硬件批准仍NO。
