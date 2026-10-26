#include "../candidate/kern_capture36.hpp"
#include <atomic>
#include <array>
#include <cassert>
#include <chrono>
#include <cstring>
#include <iostream>
#include <thread>
#include <vector>

struct Record { uint32_t index,version; uint64_t payload[16]; };
struct Policy {
    static bool valid(const Record &r,uint32_t index) noexcept { return r.version==3 && r.index==index; }
};
using Pipe=Capture36::Pipeline<Record,3,Policy>;
using Capture36::Submit; using Capture36::Drain; using Capture36::WriteResult;
Record record(uint32_t index) { Record r{};r.index=index;r.version=3;for(auto &v:r.payload)v=0x12340000+index;return r; }
struct Sink {
    std::atomic<unsigned> active{0},maxActive{0},calls{0};
    std::atomic<bool> block{false},entered{false},release{false};
    int error=0;bool shortWrite=false;
    Pipe *pipe=nullptr;bool nested=false,closeInside=false;
    std::vector<unsigned char> bytes;
    static WriteResult write(void *p,const void *data,size_t size) noexcept {
        auto &s=*static_cast<Sink *>(p);
        unsigned a=++s.active, m=s.maxActive.load();
        while(a>m && !s.maxActive.compare_exchange_weak(m,a)){}
        ++s.calls;s.entered=true;
        if(s.block) while(!s.release)std::this_thread::yield();
        const auto *r=static_cast<const Record *>(data);
        for(size_t i=0;i<size/sizeof(Record);++i){assert(Policy::valid(r[i],i));for(auto v:r[i].payload)assert(v==0x12340000+i);}
        s.bytes.assign(static_cast<const unsigned char *>(data),static_cast<const unsigned char *>(data)+size);
        if(s.nested) {s.nested=false;auto r2=record(1);assert(s.pipe->publish(r2,true)==Submit::Accepted);assert(s.pipe->drain(write,p)==Drain::Busy);}
        if(s.closeInside)s.pipe->close();
        --s.active;
        return {s.error, s.shortWrite?size-1:size};
    }
};
struct Fixture { Record slots[3]{},snapshot[3]{};Pipe pipe{slots,snapshot};Sink sink;Fixture(){sink.pipe=&pipe;} };
void normal() {
    Fixture f; auto r=record(0);
    assert(f.pipe.drain(Sink::write,&f.sink)==Drain::Idle);
    assert(f.pipe.publish(r,false)==Submit::Incomplete);assert(f.pipe.published()==0);
    auto bad=r;bad.version=2;assert(f.pipe.publish(bad,true)==Submit::Invalid);
    bad=r;bad.index=1;assert(f.pipe.publish(bad,true)==Submit::Invalid);
    assert(f.pipe.publish(r,true)==Submit::Accepted);
    r.payload[0]=0; // caller scratch no longer backs the immutable published record
    assert(f.pipe.drain(Sink::write,&f.sink)==Drain::Written);
    assert(f.pipe.written()==1 && f.sink.calls==1 && f.sink.maxActive==1);
    assert(f.pipe.drain(Sink::write,&f.sink)==Drain::Idle);
    assert(f.sink.calls==1); // no duplicate prefix
    for(unsigned i=1;i<3;++i){r=record(i);assert(f.pipe.publish(r,true)==Submit::Accepted);assert(f.pipe.drain(Sink::write,&f.sink)==Drain::Written);}
    r=record(3);assert(f.pipe.publish(r,true)==Submit::Full);assert(f.pipe.written()==3);
    f.pipe.close();assert(f.pipe.quiescent());assert(f.pipe.publish(r,true)==Submit::Stopped);
}
void failure(int error,bool partial,bool missing=false) {
    Fixture f;auto r=record(0);assert(f.pipe.publish(r,true)==Submit::Accepted);
    f.sink.error=error;f.sink.shortWrite=partial;
    assert(f.pipe.drain(missing?nullptr:Sink::write,&f.sink)==Drain::Failed);
    assert(f.pipe.failed() && f.pipe.written()==0 && f.pipe.attempts()==(missing?0U:1U));
    const int expected=missing?Capture36::MissingWriter:error?error:Capture36::ShortWrite;
    assert(f.pipe.error()==expected);
    f.sink.error=0;f.sink.shortWrite=false;
    for(unsigned i=0;i<16;++i)assert(f.pipe.drain(Sink::write,&f.sink)==Drain::Failed);
    r=record(1);assert(f.pipe.publish(r,true)==Submit::Failed);assert(f.pipe.error()==expected);
    f.pipe.close();assert(f.pipe.quiescent());
}
void contenders(unsigned count) {
    Fixture f;auto r=record(0);assert(f.pipe.publish(r,true)==Submit::Accepted);f.sink.block=true;
    std::thread owner([&]{assert(f.pipe.drain(Sink::write,&f.sink)==Drain::Written);});
    while(!f.sink.entered)std::this_thread::yield();
    std::vector<std::thread> losers;
    for(unsigned i=1;i<count;++i)losers.emplace_back([&]{assert(f.pipe.drain(Sink::write,&f.sink)==Drain::Busy);});
    for(auto &t:losers)t.join();
    f.sink.release=true;owner.join();
    assert(f.sink.calls==1 && f.sink.maxActive==1 && f.pipe.written()==1);
}
void pendingHandoff() {
    Fixture f;auto r=record(0);assert(f.pipe.publish(r,true)==Submit::Accepted);
    f.sink.nested=true;
    assert(f.pipe.drain(Sink::write,&f.sink)==Drain::Written);
    assert(f.pipe.written()==2 && f.sink.calls==2 && !f.pipe.pending());
    assert(f.pipe.drain(Sink::write,&f.sink)==Drain::Idle);
}
void cancellationAndDestroy() {
    {Fixture f;auto r=record(0);assert(f.pipe.publish(r,true)==Submit::Accepted);
     f.pipe.close();assert(f.pipe.quiescent());assert(f.pipe.drain(Sink::write,&f.sink)==Drain::Stopped);assert(f.sink.calls==0);assert(f.pipe.published()==1 && f.pipe.written()==0);}
    auto f=new Fixture;auto r=record(0);assert(f->pipe.publish(r,true)==Submit::Accepted);f->sink.block=true;
    std::thread worker([&]{assert(f->pipe.drain(Sink::write,&f->sink)==Drain::Stopped);});
    while(!f->sink.entered)std::this_thread::yield();
    f->pipe.close();assert(!f->pipe.quiescent());assert(f->pipe.drain(Sink::write,&f->sink)==Drain::Stopped);
    f->sink.release=true;worker.join();assert(f->pipe.quiescent());delete f;
    // Joining the only worker fences the external callback; quiescent alone doesn't.
}
void stopInsideWriter() {
    Fixture f;auto r=record(0);assert(f.pipe.publish(r,true)==Submit::Accepted);f.sink.closeInside=true;
    assert(f.pipe.drain(Sink::write,&f.sink)==Drain::Stopped);assert(f.pipe.quiescent());assert(f.pipe.written()==1);
}
struct ReentrantPolicy {
    static void (*inside)();
    static bool valid(const Record &r,uint32_t index) noexcept {if(inside){auto fn=inside;inside=nullptr;fn();}return Policy::valid(r,index);}
};
void (*ReentrantPolicy::inside)()=nullptr;
using ReentrantPipe=Capture36::Pipeline<Record,3,ReentrantPolicy>;
ReentrantPipe *reentrant=nullptr;
void reenter(){auto r=record(0);assert(reentrant->publish(r,true)==Submit::Busy);}
void producerReentry(){Record a[3]{},b[3]{};ReentrantPipe p(a,b);reentrant=&p;ReentrantPolicy::inside=reenter;auto r=record(0);assert(p.publish(r,true)==Submit::Accepted);assert(p.published()==1);}
std::atomic<bool> producerEntered{false},producerRelease{false};
void holdProducer(){producerEntered=true;while(!producerRelease)std::this_thread::yield();}
void competingProducers(){
    Record a[3]{},b[3]{};ReentrantPipe p(a,b);
    producerEntered=false;producerRelease=false;ReentrantPolicy::inside=holdProducer;
    std::thread owner([&]{auto r=record(0);assert(p.publish(r,true)==Submit::Accepted);});
    while(!producerEntered)std::this_thread::yield();
    std::vector<std::thread> losers;
    for(unsigned i=0;i<15;++i)losers.emplace_back([&]{auto r=record(0);assert(p.publish(r,true)==Submit::Busy);});
    for(auto &t:losers)t.join();
    producerRelease=true;owner.join();assert(p.published()==1);
}
void closeProducer(){reentrant->close();assert(!reentrant->quiescent());}
Capture36::WriteResult failWriter(void *,const void *,size_t) noexcept {return {5,0};}
void failDuringPublication(){assert(reentrant->drain(failWriter,nullptr)==Drain::Failed);}
void publicationTerminalRaces(){
    {Record a[3]{},b[3]{};ReentrantPipe p(a,b);reentrant=&p;ReentrantPolicy::inside=closeProducer;
     auto r=record(0);assert(p.publish(r,true)==Submit::RetainedStopped);assert(p.published()==1);assert(p.quiescent());}
    {Record a[3]{},b[3]{};ReentrantPipe p(a,b);reentrant=&p;auto r=record(0);assert(p.publish(r,true)==Submit::Accepted);
     ReentrantPolicy::inside=failDuringPublication;r=record(1);assert(p.publish(r,true)==Submit::RetainedFailed);
     assert(p.published()==2 && p.written()==0 && p.error()==5);assert(p.drain(failWriter,nullptr)==Drain::Failed);}
}
void invalidBuffers(){Record a[4]{};Pipe null(nullptr,a),alias(a,a),overlap(a,a+1);auto r=record(0);assert(null.publish(r,true)==Submit::Invalid);assert(alias.publish(r,true)==Submit::Invalid);assert(overlap.publish(r,true)==Submit::Invalid);}
void retryReasons(){
    struct RetryRecord { uint32_t attemptReasons[8];uint64_t payload; } r{};
    for(uint32_t attempt=1;attempt<=8;++attempt){
        Capture36::beginAttempt(r,attempt);
        for(uint32_t i=0;i<attempt-1;++i)assert(r.attemptReasons[i]==i+10);
        r.attemptReasons[attempt-1]=attempt+9;r.payload=123;
    }
    Capture36::beginAttempt(r,1);
    for(auto reason:r.attemptReasons)assert(reason==0);
    assert(r.payload==0);
}
void stress() {
    // 3 immutable records, one publisher and 16 coalescing callback contenders.
    // Each run's final explicit notification models a reliable executor fence.
    for(unsigned run=0;run<120;++run){
        Fixture f;std::atomic<bool> go{false},done{false};std::vector<std::thread> threads;
        for(unsigned i=0;i<16;++i)threads.emplace_back([&]{while(!go)std::this_thread::yield();while(!done)f.pipe.drain(Sink::write,&f.sink);});
        go=true;
        for(unsigned i=0;i<3;++i){auto r=record(i);assert(f.pipe.publish(r,true)==Submit::Accepted);std::this_thread::yield();}
        done=true;for(auto &t:threads)t.join();
        f.pipe.drain(Sink::write,&f.sink);
        assert(f.pipe.written()==3 && f.pipe.published()==3 && f.sink.maxActive==1 && f.pipe.attempts()<=3);
        assert(f.sink.bytes.size()==3*sizeof(Record));
    }
}
int main(){normal();failure(13,false);failure(5,false);failure(0,true);failure(Capture36::TimedOut,false);failure(0,false,true);contenders(2);contenders(16);pendingHandoff();cancellationAndDestroy();stopInsideWriter();producerReentry();competingProducers();publicationTerminalRaces();invalidBuffers();retryReasons();stress();std::cout<<"PASS ownership, immutable publication, 2/16 contenders, failure terminal, pending handoff, cancellation fence, reentry, 16 producers, terminal races, retry reasons, 120x16 stress\n";}
