// Exact isolated core compiled as x86_64 Mach-O, not a loadable kext.
#include "../candidate/kern_capture36.hpp"
struct Record36 { uint32_t index,version; uint64_t payload; };
struct Policy36 { static bool valid(const Record36 &r,uint32_t n) noexcept {return r.index==n && r.version==3;} };
using Pipe36=Capture36::Pipeline<Record36,3,Policy36>;
extern "C" uint32_t capture36_publish(Pipe36 *p,const Record36 *r) {return static_cast<uint32_t>(p->publish(*r,true));}
extern "C" uint32_t capture36_drain(Pipe36 *p,Capture36::Write write,void *ctx) {return static_cast<uint32_t>(p->drain(write,ctx));}
extern "C" void capture36_close(Pipe36 *p) {p->close();}
extern "C" bool capture36_quiescent(Pipe36 *p) {return p->quiescent();}
