// SPDX-License-Identifier: MIT
// GA36 CPU/freestanding publication core. No XNU scheduling, GPU or file APIs.
#ifndef KERN_CAPTURE36_HPP
#define KERN_CAPTURE36_HPP
#include <stddef.h>
#include <stdint.h>

namespace Capture36 {
// Preserve only prior reason slots across an exclusively owned retry. Attempt1
// starts a new record. This is payload bookkeeping, NOT capture serialization.
template<class Record> inline void beginAttempt(Record &r,uint32_t attempt) noexcept {
    static_assert(__is_trivially_copyable(Record), "byte-cleared diagnostic record");
    uint32_t reasons[sizeof(r.attemptReasons)/sizeof(r.attemptReasons[0])]{};
    if(attempt>1) for(size_t i=0;i<sizeof(reasons)/sizeof(reasons[0]);++i) reasons[i]=r.attemptReasons[i];
    auto bytes=reinterpret_cast<unsigned char *>(&r);
    for(size_t i=0;i<sizeof(r);++i) bytes[i]=0;
    if(attempt>1) for(size_t i=0;i<sizeof(reasons)/sizeof(reasons[0]);++i) r.attemptReasons[i]=reasons[i];
}
enum class Submit : uint32_t { Accepted, Busy, Incomplete, Invalid, Full, Stopped, Failed, RetainedStopped, RetainedFailed };
enum class Drain : uint32_t { Idle, Busy, Written, Failed, Stopped };
struct WriteResult { int error; size_t transferred; };
using Write = WriteResult (*)(void *, const void *, size_t) noexcept;
constexpr int ShortWrite = -3601;
constexpr int MissingWriter = -3602;
constexpr int TimedOut = -3603; // backend must RETURN; this cannot interrupt a blocked I/O

template<class Record, uint32_t Capacity, class Policy> class Pipeline {
    static_assert(Capacity > 0 && Capacity < 1024, "bounded capacity");
    static_assert(__is_trivially_copyable(Record), "wire record must be trivially copyable");
    static_assert(__atomic_always_lock_free(4, nullptr), "lock-free 32-bit atomics required");
    static_assert(sizeof(Record) <= SIZE_MAX / Capacity, "size overflow");
    static constexpr uint32_t Running=1, Pending=2, Failed=4, Stopping=8, Closed=0x80000000U;
    Record *const slots_;
    Record *const snapshot_;
    const bool configured_;
    uint32_t life_=0, producer_=0, word_=0, published_=0, written_=0, attempts_=0;
    int error_=0;
    static uint32_t load(const uint32_t &v) noexcept { return __atomic_load_n(&v, __ATOMIC_ACQUIRE); }
    bool enter() noexcept {
        uint32_t v=load(life_);
        // No unbounded spinning in capture: contention is an explicit refusal.
        for (uint32_t n=0; n<32; ++n) {
            if ((v&Closed) || (v&~Closed)==Closed-1) return false;
            if (__atomic_compare_exchange_n(&life_, &v, v+1, false, __ATOMIC_ACQUIRE, __ATOMIC_RELAXED)) return true;
        }
        return false;
    }
    struct Lease {
        Pipeline &p; bool valid;
        explicit Lease(Pipeline &q) noexcept : p(q), valid(q.enter()) {}
        ~Lease() { if (valid) __atomic_fetch_sub(&p.life_,1,__ATOMIC_RELEASE); }
    };
    struct Producer {
        Pipeline &p; bool valid;
        explicit Producer(Pipeline &q) noexcept : p(q),valid(false) {
            uint32_t zero=0;
            valid=__atomic_compare_exchange_n(&p.producer_,&zero,1,false,__ATOMIC_ACQUIRE,__ATOMIC_RELAXED);
        }
        ~Producer() { if(valid) __atomic_store_n(&p.producer_,0,__ATOMIC_RELEASE); }
    };
    struct Writer {
        Pipeline &p; bool owned=true;
        explicit Writer(Pipeline &q) noexcept : p(q) {}
        ~Writer() { if(owned) __atomic_fetch_and(&p.word_,~Running,__ATOMIC_RELEASE); }
    };
    static void copy(Record *to,const Record *from,uint32_t count) noexcept {
        auto d=reinterpret_cast<unsigned char *>(to);
        auto s=reinterpret_cast<const unsigned char *>(from);
        for(size_t i=0;i<sizeof(Record)*count;++i) d[i]=s[i];
    }
    static bool validBuffers(Record *a,Record *b) noexcept {
        if(!a || !b) return false;
        const uintptr_t x=reinterpret_cast<uintptr_t>(a), y=reinterpret_cast<uintptr_t>(b);
        const size_t bytes=sizeof(Record)*Capacity;
        return x<=UINTPTR_MAX-bytes && y<=UINTPTR_MAX-bytes && (x+bytes<=y || y+bytes<=x);
    }
    Drain fail(int e) noexcept {
        int zero=0;
        __atomic_compare_exchange_n(&error_,&zero,e,false,__ATOMIC_RELEASE,__ATOMIC_RELAXED);
        __atomic_fetch_or(&word_,Failed,__ATOMIC_RELEASE);
        return Drain::Failed; // Writer guard releases owner on every return
    }
public:
    // Buffers must remain alive until close + callback fencing + quiescent.
    // Construction happens before sharing. No reset/reinitialize API and no ABA reuse.
    Pipeline(Record *slots,Record *snapshot) noexcept
        : slots_(slots),snapshot_(snapshot),configured_(validBuffers(slots,snapshot)) {}
    Pipeline(const Pipeline &)=delete;
    Pipeline &operator=(const Pipeline &)=delete;
    uint32_t published() const noexcept { return load(published_); }
    uint32_t written() const noexcept { return load(written_); }
    uint32_t attempts() const noexcept { return load(attempts_); }
    int error() const noexcept { return __atomic_load_n(&error_,__ATOMIC_ACQUIRE); }
    bool pending() const noexcept { return (load(word_)&Pending)!=0; }
    bool failed() const noexcept { return (load(word_)&Failed)!=0; }

    Submit publish(const Record &record,bool complete) noexcept {
        if(!complete) return Submit::Incomplete;
        Lease lease(*this);
        if(!lease.valid) return Submit::Stopped;
        Producer producer(*this);
        if(!producer.valid) return Submit::Busy;
        uint32_t flags=load(word_);
        if(flags&Stopping) return Submit::Stopped;
        if(flags&Failed) return Submit::Failed;
        const uint32_t count=load(published_);
        if(!configured_ || !Policy::valid(record,count)) return Submit::Invalid;
        if(count==Capacity) return Submit::Full;
        // Caller owns stable input for this call only. Copy, then release-publish.
        copy(slots_+count,&record,1);
        __atomic_store_n(&published_,count+1,__ATOMIC_RELEASE);
        const uint32_t before=__atomic_fetch_or(&word_,Pending,__ATOMIC_ACQ_REL);
        if(before&Stopping) return Submit::RetainedStopped;
        if(before&Failed) return Submit::RetainedFailed;
        return Submit::Accepted; // caller must arrange a worker notification
    }

    Drain drain(Write callback,void *context) noexcept {
        Lease lease(*this);
        if(!lease.valid) return Drain::Stopped;
        uint32_t flags=load(word_);
        bool owner=false;
        for(uint32_t n=0;n<Capacity+4;++n) {
            if(flags&Stopping) return Drain::Stopped;
            if(flags&Failed) return Drain::Failed;
            if(flags&Running) return Drain::Busy;
            if(!(flags&Pending)) return Drain::Idle;
            if(__atomic_compare_exchange_n(&word_,&flags,flags|Running,false,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)) {
                owner=true; break;
            }
        }
        if(!owner) return Drain::Busy;
        Writer writer(*this);
        if(!callback) return fail(MissingWriter);
        bool any=false;
        // Each cycle clears Pending, observes immutable published prefix, then
        // CAS-releases ownership only if no publisher signalled meanwhile.
        for(uint32_t cycle=0;cycle<Capacity+2;++cycle) {
            const uint32_t prior=__atomic_fetch_and(&word_,~Pending,__ATOMIC_ACQ_REL);
            if(prior&Stopping) return Drain::Stopped;
            const uint32_t target=load(published_);
            if(target>load(written_)) {
                copy(snapshot_,slots_,target);
                __atomic_fetch_add(&attempts_,1,__ATOMIC_RELAXED);
                const WriteResult result=callback(context,snapshot_,sizeof(Record)*target);
                if(result.error) return fail(result.error);
                if(result.transferred!=sizeof(Record)*target) return fail(ShortWrite);
                __atomic_store_n(&written_,target,__ATOMIC_RELEASE);
                any=true;
            }
            uint32_t expected=Running;
            if(__atomic_compare_exchange_n(&word_,&expected,0,false,__ATOMIC_RELEASE,__ATOMIC_RELAXED)) {
                writer.owned=false;
                return any?Drain::Written:Drain::Idle;
            }
            if(expected&Stopping) return Drain::Stopped;
        }
        // Bounded yield: Pending remains set, so the executor must re-notify.
        __atomic_fetch_or(&word_,Pending,__ATOMIC_RELEASE);
        return any?Drain::Written:Drain::Busy;
    }

    void close() noexcept {
        __atomic_fetch_or(&life_,Closed,__ATOMIC_ACQ_REL);
        __atomic_fetch_or(&word_,Stopping,__ATOMIC_RELEASE);
    }
    bool quiescent() const noexcept {
        return load(life_)==Closed && load(producer_)==0 && !(load(word_)&Running);
    }
    // quiescent does NOT fence an external queued callback holding a raw pointer.
    // Scheduler must cancel/wait + prevent new entry before freeing this object.
};
} // namespace Capture36
#endif
