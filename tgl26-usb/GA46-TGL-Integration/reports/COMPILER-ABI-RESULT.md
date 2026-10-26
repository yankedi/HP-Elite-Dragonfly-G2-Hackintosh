# Compiler Adapter / LLVM Bridge：GA46 工程结果

## 已确认的真实问题

GA45的三项假设不成立：捕获SIGSEGV并longjmp后无法恢复LLVM锁、堆和C++对象；
将当前Module直接交给LLVM3902调用者没有对象布局保证；普通C API写出的当前
bitcode不等价于Apple私有`getSerializedModule(...,3902)`降版格式。
两组常数比较/函数序言特征不证明函数签名、sret ABI、返回对象所有权或唯一身份。

真实donor与25G83插件反汇编保存在`logs/*-plugin-disassembly-001.txt`。
donor Create@0x2030分配0x120对象，SetHelper@0x20d6写+0x10；ReleaseReply@0x20e0
读取**compiler对象**+0x110执行delete[]、+0x108执行free，不是任意reply指针。
新Create@0x225f同样分配0x120，ReleaseReply@0x22f0也使用这两个字段；
不能据此推导所有其他成员相容。
donor WithOptions@0x2128保存r8为Module、r9为另一参数；25G83新入口@0x2338
保存r8/r9并按input首字段0/2/3分支；之后传`r9d`为长度，说明原适配器的
`size_t`长度声明也未经逐字段确认。donor family==0x4e2分支选择TGL runtime。
Options/metadata/resource binding/同步完成与reply存活期不能由寄存器平移推出。

## 源码实际修复

- 删除进程signal handlers、altstack/longjmp及崩溃后继续执行。
- 删除伪造helper/provider vtable、raw_string_ostream空析构、Twine固定内存
  布局转换和私有函数扫描，不再以这些符号伪装解决LLVM ABI。
- adapter的Create明确返回null（没有创建编译器）；未知请求/foreign delete
  或reply路径失败即停，**不写未知栈指针、不猜错误码、不伪造reply**。
- bridge仅提供项目自有诊断字节ABI；不能作为旧LLVM的drop-in替代品。
  历史legacy exports移除，所以donor会正确拒绝缺失导入，不能误称兼容。
- `compiler/owned-bitcode.hpp`精确install name、RTLD_LOCAL、逐C API同image
  `dladdr`核验；每请求独立context，输入copy、输出copy，销毁顺序
  output-buffer→module→input-buffer→message→context。不接受外来Module*。
- 新两个dylib严格链接，不用`-undefined dynamic_lookup`；adapter命名修为
  `libMTLIGCCompilerPlugin.dylib`，Old仅供Apple donor，避免历史命名碰撞。

当前状态是**安全隔离、ABI_UNVERIFIED**，不是功能完备编译器。

## 实际CPU回归

`logs/compiler-owned-001.log`：真实LLVM21读取Clang生成bitcode，1600次8线程
roundtrip，ASan/UBSan及leak检查通过；截断payload经真正LLVM parse错误路径
返回，非法magic/超限/缺失provider拒绝。llvm-dis验证实际函数保留。
这验证新ownership/序列化实现，不验证Apple bitcode3902或目标Metal ABI。
官方LLVM文档仅保证新reader读取旧bitcode，**不保证旧reader读取新bitcode**；
官方`BitReader.cpp`确认eager parse不接管输入buffer。本轮也查询了Context7。

## 依赖证据

机器图 `reports/COMPILER-DEPENDENCIES.json` 从真实Mach-O导入、export trie、
library ordinals生成，包含旧/新adapter、bridge、donor plugin/libigc、
25G83 plugin/libigc、GPUCompiler32023以及实际MTLCompiler四导出证据。
保留全部imports，区分LINK_RESOLVED / RUNTIME_RESOLUTION_REQUIRED /
SYMBOL_ABSENT / ABI_MISMATCH。未知shared-cache exports用null，绝不作不存在。
新bridge诊断C API的可用性仍需精确install name dlopen+同image符号探针。
旧plugin需要的LLVM3902 C++实现仍是**不可替代真实阻塞**；没有离线合法
3902 provider或经过验证的字节/IPC降版边界，不能恢复旧plugin编译。
