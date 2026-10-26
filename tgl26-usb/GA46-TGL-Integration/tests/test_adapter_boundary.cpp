#include <cassert>
#include <csignal>
#include <cstdint>
#include <cstddef>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>
extern "C" void *MTLCompilerCreate(void *);
extern "C" long MTLCompilerBuildRequestWithSerializedBitcode(void *,void *,void *,uint32_t,const char *,size_t,void *,void *,void *,void *,void *,void *,void *);
extern "C" void MTLCompilerDelete(void *);
extern "C" void MTLCompilerReleaseReply(void *);
int main() {
    rlimit r{0,0};assert(setrlimit(RLIMIT_CORE,&r)==0);
    struct sigaction before{},after{};
    assert(sigaction(SIGSEGV,nullptr,&before)==0);
    assert(MTLCompilerCreate(reinterpret_cast<void *>(1))==nullptr);
    assert(sigaction(SIGSEGV,nullptr,&after)==0 && before.sa_handler==after.sa_handler);
    for(int i=0;i<3;i++) {
        pid_t p=fork();assert(p>=0);
        if(!p) {
            // A caller with invalid request/reply pointers must fail-stop
            // before reading/writing them, not crash later inside libigc.
            void *bad=reinterpret_cast<void *>(1);
            if(i==0) MTLCompilerBuildRequestWithSerializedBitcode(bad,bad,bad,0,(const char *)bad,16,bad,bad,bad,bad,bad,bad,bad);
            if(i==1) MTLCompilerDelete(bad);
            if(i==2) MTLCompilerReleaseReply(bad);
            _exit(99);
        }
        int status=0;assert(waitpid(p,&status,0)==p);
        assert(WIFSIGNALED(status) && WTERMSIG(status)==SIGABRT);
    }
}
