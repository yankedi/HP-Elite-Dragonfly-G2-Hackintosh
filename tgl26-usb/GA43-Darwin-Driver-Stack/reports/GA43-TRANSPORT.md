# GA43 DRM mmap-offset / 原生资源整合

新增标准 `DRM_IOCTL_I915_GEM_MMAP_OFFSET` BSD wire `0xc0206464` 路由。
只接受真实CPU write-back backing，拒绝WC/GTT/FIXED和extensions。
每个live owner/handle获得稳定、不复用、有符号off_t范围内的byte cookie；
不是内核地址、DMA或GPU VA。相邻BO最大保留64MiB，不发生cookie范围重叠。

`GX_OFFSET_MAP` 是薄Darwin transport操作，消费标准cookie与长度/权限，
由现有IOUserClient `externalMethod` → `gx_client_ioctl` → `gx_map_offset`
→ 实际XNU `createMappingInTask` 后端处理。task仅取原认证owner；
cookie/handle/复制/映射/发布/回滚均在client gate内，底层解析与map在同一device锁内。
handle关闭撤销未来cookie使用，已有映射持有BO直到unmap/close/death；
copyout失败且rollback-unmap失败时仍由原reaper保活重试，task不会提前释放。

本单元交付的是**标准cookie生成加私有IOUserClient CPU-map操作**，后者消费cookie
并复用现有XNU资源后端；不是标准fd mmap支持。仍没有已验证BSD fd/d_mmap pager。
旧公开头的d_mmap签名不足，
不猜ABI，不伪造render字符设备身份。普通 `mmap(fd,...)` 及原生用户态IOConnect
libdrm接入仍需补齐并验证；当前完整DRM_TRANSPORT不是PASS。

`mmap-tests-002`：新cookie所有权/稳定性/不复用/跨owner拒绝、真实memfd别名读写、
handle关闭后map保活、出界拒绝、copyout及unmap双失败保活、close重试，及受影响
GEM/VM/client三ASanUBSan目标PASS。`mmap-build-001` 的__u64/uint64指针差异失败
已修为显式local值；`mmap-tests-001`运行的是上次构建旧二进制，不计入本单元验收。
`mmap-build-002`成功后才运行的002测试是本单元有效结果，全部原日志保留。
`mmap-darwin-compile-001`三个修改生产单元实际Mach-O编译PASS，非链接或runtime。

## libdrm原始Linux请求转换

本轮继续修复此前组合测试绕过的缺口：`drmIoctl`现在将原Linux GEM_CLOSE
`0x40086409`转换为BSD `0x80086409`，原Linux write-only EXECBUFFER2
`0x40406469`转换为BSD `0x80406469`。只精确匹配已知LP64合同，不猜未知方向位。
GEM_CREATE和MMAP_OFFSET的read/write编码相同，直接透传；nested pointer不重打包。
组合测试改用标准宏close与mmap-offset，再将cookie送入同一真实GEM映射路径；
验证exec被生产preflight拒绝（EINVAL），不会将未知/无硬件能力当成功。
`drm-wire-build-002`和`drm-wire-tests-001`两个相关ASan/UBSan目标PASS；
001构建因误写第二目标名exit2保留，002纠正后验收。不宣称真实fd/IOConnect接通。

独立审查F5已修复：可信替代teardown先关闭raw owner file后，client close把EBADF
当作已关file，继续mapping revoke，避免永久重试strand。新增witness覆盖unmap先失败
后恢复，task/BO保活直至成功；`review-close-tests-001`两相关ASanUBSan目标PASS。
F6文字已明确收紧为cookie生成＋私有CPU-map，native fd/pager/render/libdrm整链仍BLOCKED。

## 新本地SDK后的真实libdrm交叉链接

`libdrm-darwin-cross-001`暴露Darwin构建中的真实缺陷：POSIX feature宏隐藏F_GETPATH/
major/minor，且只include ioccom没有ioctl声明。改为Apple显式_DARWIN_C_SOURCE和
BSD sys/ioctl.h；未改CPU syscall替换、ioctl编码或生产身份。
`libdrm-darwin-cross-002`使用现有用户SDK、现代linker严格链接真实`libdrm.dylib`，
Mach-O/exports/全部28个imports ordinal→libSystem及依赖合同PASS。
SHA256 `365364984126663d18bd9590471e6ef1670025cacfde6b4f7bc89bd03aeaf547`。
`libdrm-darwin-host-tests-001`两个受影响ASanUBSan目标PASS。
这是可供ANV链接的真实libdrm子集，不是完整libdrm API，也不是native fd/runtime成功。
复现：`tools/with-local-darwin-inputs.sh`包裹`tools/build-darwin-libdrm.sh`，输出prefix全新。

## 标准 syncobj 用户态请求封送（不是内核 fence）

ANV实际最终链接报13个必要drmSyncobj入口缺失。新增独立`drm_syncobj.c`，按已有
公开drm.h封送create/destroy、fd import/export、wait/reset/signal、timeline
wait/signal/query及transfer；输出只在真实ioctl成功后发布，错误原样转负errno。
没有CPU syncobj表、预置成功或内核fence实现；现有内核不支持时仍返回其真实错误。
不新增syncobj能力宣告。全部syncobj request为标准IOWR，Darwin头直接使用BSD编码。

`libdrm-syncobj-build-001`因尚未重新configure找不到新目标，保留失败；configure001和
build002成功。`libdrm-syncobj-tests-001`三个相关ASan/UBSan目标PASS；新fault-injection
验证失败后handle/fd/first_signaled不发布、EOPNOTSUPP/ENOTTY/ETIMEDOUT传播和64位
pointer/point/timeout不截断，仅CPU封送测试。`libdrm-syncobj-cross-001`真实严格Darwin
dylib检查PASS，SHA256 `97a5330342d13d78e17abb536c8dc1bbadfa93f59a69ed88a94a08dd071a8da2`。

## 真正 IOConnect 用户端与共享 ABI

新增`drm-darwin-native.h`/`native_transport.c`使用真实IOKit用户API，匹配现有GX42Service，
IOServiceOpen绑定实际创建task，IOConnectCallScalarMethod向现有selector0传BSD request/
原用户地址，显式验证scalar errno；GX_OFFSET_MAP/UNMAP连接既有内核GEM/XNU后端。
统一`gx_user_abi.h`给用户和内核使用，原wire结构/offset/selector不变。
open/map只在成功后发布输出；close消费connection，失败的内核映射由现有reaper保活。
用户代码没有注入syscall、指定task、模拟内核或生成CPU backing。

`io-connect-native-link-001`：真实C交叉编译及严格dylib链接PASS，11 imports分别绑定
libSystem和IOKit，五个API导出合同PASS。`shared-uapi-tests-001`两个受影响ASanUBSan
目标PASS；`native-shared-uapi-link-001`五fresh加四seal对象重新编译/真实-kext链接PASS。
此接口明确以io_connect_t端口操作，**不是fd**，不能把它传给普通drmIoctl/mmap。
ANV仍走普通fd路径，BSD render node/pager与ANV连接尚未完成；原生调用/管理员策略/
IOServiceClose失败后的目标运行行为均NOT_TESTED。没有据静态链接声称整链成功。
