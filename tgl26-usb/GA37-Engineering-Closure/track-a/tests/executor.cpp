#include "../source/owned_executor.hpp"
#include <atomic>
#include <cassert>
#include <cstring>
#include <functional>
#include <iostream>
#include <thread>
#include <vector>
using namespace Capture37;
using namespace std::chrono_literals;
struct Record {uint32_t index,version;uint64_t values[8];};
struct Policy {
    static std::function<void()> inside;
    static bool valid(const Record &r,uint32_t n) noexcept {
        if(inside){auto fn=std::move(inside);inside=nullptr;fn();}
        return r.version==3 && r.index==n;
    }
};
std::function<void()> Policy::inside;
using Owned=Session<Record,96,Policy>;
Record rec(uint32_t n){Record r{};r.index=n;r.version=3;for(auto &v:r.values)v=0x37110000+n;return r;}
struct Sink {
    std::atomic<bool> hold{false},entered{false},release{false};
    std::atomic<unsigned> calls{0},live{0},maxLive{0};
    std::atomic<int> error{0};
    std::vector<Record> last;
    std::function<void()> once;
    static Capture36::WriteResult write(void *ctx,const void *data,size_t size) noexcept {
        auto &s=*static_cast<Sink *>(ctx);unsigned now=++s.live,m=s.maxLive;
        while(now>m && !s.maxLive.compare_exchange_weak(m,now)){}
        ++s.calls;s.entered=true;
        if(s.hold)while(!s.release)std::this_thread::yield();
        assert(size%sizeof(Record)==0);auto r=static_cast<const Record *>(data);size_t n=size/sizeof(Record);
        for(size_t i=0;i<n;++i){assert(r[i].index==i && r[i].version==3);for(auto v:r[i].values)assert(v==0x37110000+i);}
        s.last.assign(r,r+n);
        if(s.once){auto f=std::move(s.once);s.once=nullptr;f();}
        --s.live;return {s.error.load(),size};
    }
};
void normalAndRepeat(){
    auto sink=std::make_shared<Sink>();Owned owner(sink,Sink::write);auto c=owner.client();
    auto a=c.submit(rec(0));assert(a.result==Admission::Accepted);assert(a.ticket.id()==0);
    assert(a.ticket.run(Context::Interrupt)==Executed::InterruptRejected);assert(c.info().queued==1);
    assert(a.ticket.run()==Executed::Written);assert(a.ticket.run()==Executed::Consumed);
    auto b=c.submit(rec(1));assert(b.result==Admission::Accepted);assert(b.ticket.run()==Executed::Written);
    assert(sink->calls==2 && sink->last.size()==2 && c.info().allPublishedWritten());
    auto rejected=c.submit(rec(2),true,Context::Interrupt);assert(rejected.result==Admission::InterruptRejected);
    c.requestShutdown(Shutdown::Drain);assert(c.waitClosed(10ms));assert(c.submit(rec(2)).result==Admission::Stopped);
}
void queuedOwnership(){
    std::weak_ptr<void> weak;
    Owned::Ticket queued;
    {
        auto sink=std::make_shared<Sink>();auto owner=std::make_unique<Owned>(sink,Sink::write);auto c=owner->client();weak=c.lifetimeProbe();
        auto work=c.submit(rec(0));queued=std::move(work.ticket);owner.reset();
        assert(!weak.expired());assert(!c.waitClosed(1ms));assert(c.info().phase==Phase::ClosingCancel);
    }
    assert(!weak.expired());assert(queued.run()==Executed::Cancelled);assert(weak.expired());
    {auto sink=std::make_shared<Sink>();Owned owner(sink,Sink::write);auto c=owner.client();
     auto work=c.submit(rec(0));c.requestShutdown(Shutdown::CancelQueued);assert(!c.waitClosed(1ms));
     work.ticket={};assert(c.waitClosed(10ms));assert(c.info().cancelled==1 && c.info().published==1 && c.info().written==0);}
}
void activeCloseTimeout(){
    auto sink=std::make_shared<Sink>();sink->hold=true;
    auto owner=std::make_unique<Owned>(sink,Sink::write);auto c=owner->client();auto weak=c.lifetimeProbe();
    auto sub=c.submit(rec(0));
    std::thread worker([ticket=std::move(sub.ticket)]()mutable{assert(ticket.run()==Executed::Written);});
    while(!sink->entered)std::this_thread::yield();
    c.requestShutdown(Shutdown::CancelQueued);assert(!c.waitClosed(1ms));assert(c.info().active==1);owner.reset();assert(!weak.expired());
    sink->release=true;worker.join();assert(c.waitClosed(10ms));assert(c.info().allPublishedWritten());
}
void captureReentryAndWriterFailure(){
    auto sink=std::make_shared<Sink>();Owned owner(sink,Sink::write);auto c=owner.client();
    Policy::inside=[&]{assert(c.submit(rec(0)).result==Admission::Busy);};
    auto a=c.submit(rec(0));assert(a.result==Admission::Accepted);
    sink->error=Capture36::TimedOut;assert(a.ticket.run()==Executed::Failed);
    auto info=c.info();assert(info.error==Capture36::TimedOut && info.written==0 && info.published==1);
    assert(c.submit(rec(1)).result==Admission::Failed);assert(c.notify().result==Admission::Failed);assert(sink->calls==1);
    c.requestShutdown(Shutdown::Drain);assert(c.waitClosed(10ms));assert(!c.info().allPublishedWritten());
}
void reentrantPublicationDuringWrite(){
    auto sink=std::make_shared<Sink>();Owned owner(sink,Sink::write);auto c=owner.client();Owned::Ticket next;
    sink->once=[&]{auto sub=c.submit(rec(1));assert(sub.result==Admission::Accepted);next=std::move(sub.ticket);assert(next.run()==Executed::Busy);};
    auto first=c.submit(rec(0));assert(first.ticket.run()==Executed::Written);
    assert(c.info().written==2 && sink->calls==2 && c.info().active==0 && c.info().queued==0);
}
void explicitCancellationRecovery(){
    auto sink=std::make_shared<Sink>();Owned owner(sink,Sink::write);auto c=owner.client();
    {auto a=c.submit(rec(0));assert(a.result==Admission::Accepted);} // queued notification cancelled, bytes retained
    assert(c.info().cancelled==1 && c.info().written==0);
    auto recovered=c.notify();assert(recovered.result==Admission::Accepted);assert(recovered.ticket.run()==Executed::Written);
    assert(c.info().allPublishedWritten());
}
void closeInsidePolicy(){
    for(auto mode:{Shutdown::Drain,Shutdown::CancelQueued}){
        auto sink=std::make_shared<Sink>();Owned owner(sink,Sink::write);auto c=owner.client();
        Policy::inside=[&]{c.requestShutdown(mode);auto info=c.info();assert(info.publishing==1 && info.phase!=Phase::Closed);};
        auto sub=c.submit(rec(0));assert(sub.result==Admission::Accepted);
        auto result=sub.ticket.run();assert(result==(mode==Shutdown::Drain?Executed::Written:Executed::Cancelled));
        assert(c.waitClosed(10ms) && c.info().publishing==0);
    }
}
void exhaustionAndReset(){
    auto sink=std::make_shared<Sink>();Owned owner(sink,Sink::write,UINT64_MAX-1);auto c=owner.client();
    auto a=c.submit(rec(0));assert(a.result==Admission::Accepted && a.ticket.id()==UINT64_MAX-1);
    assert(a.ticket.run()==Executed::Written);
    assert(c.submit(rec(1)).result==Admission::SequenceExhausted);assert(c.info().nextTicket==UINT64_MAX && c.info().published==1);
    c.requestShutdown(Shutdown::Drain);assert(c.waitClosed(10ms));
    // A new boot/reset requires a distinct owner, never resetting counters/storage in the old object.
    Owned newGeneration(sink,Sink::write);auto newer=newGeneration.client();auto b=newer.submit(rec(0));assert(b.ticket.id()==0);assert(b.ticket.run()==Executed::Written);
}
void contention(unsigned count){
    auto sink=std::make_shared<Sink>();Owned owner(sink,Sink::write);auto c=owner.client();
    std::atomic<bool> go{false};std::vector<Owned::Ticket> tickets(count);std::vector<std::thread> producers;
    for(unsigned i=0;i<count;++i)producers.emplace_back([&,i,client=c]{
        while(!go)std::this_thread::yield();
        for(;;){auto sub=client.submit(rec(i));if(sub.result==Admission::Accepted){tickets[i]=std::move(sub.ticket);break;}
            assert(sub.result==Admission::Invalid || sub.result==Admission::Busy);std::this_thread::yield();}
    });
    go=true;for(auto &t:producers)t.join();assert(c.info().published==count && c.info().queued==count);
    std::vector<std::thread> workers;
    for(auto &ticket:tickets)workers.emplace_back([work=std::move(ticket)]()mutable{
        auto r=Executed::Retry;
        for(unsigned attempt=0;attempt<100000 && r==Executed::Retry;++attempt)r=work.run();
        assert(r==Executed::Written || r==Executed::Idle || r==Executed::Busy);
    });
    c.requestShutdown(Shutdown::Drain);for(auto &w:workers)w.join();assert(c.waitClosed(100ms));
    assert(c.info().allPublishedWritten() && sink->last.size()==count && sink->maxLive==1 && sink->calls==1);
}
void shutdownRace(unsigned count){
    for(unsigned round=0;round<12;++round){
        auto sink=std::make_shared<Sink>();Owned owner(sink,Sink::write);auto c=owner.client();
        std::atomic<bool> go{false};std::vector<std::thread> threads;
        for(unsigned i=0;i<count;++i)threads.emplace_back([&,client=c]{
            while(!go)std::this_thread::yield();
            auto sub=client.submit(rec(0));
            if(sub.result==Admission::Accepted){auto r=sub.ticket.run();assert(r==Executed::Written || r==Executed::Cancelled);}
            else assert(sub.result==Admission::Busy || sub.result==Admission::Stopped || sub.result==Admission::Invalid);
        });
        go=true;c.requestShutdown(Shutdown::CancelQueued);for(auto &t:threads)t.join();
        assert(c.waitClosed(100ms));auto info=c.info();assert(info.queued==0 && info.active==0 && info.published<=1);
        assert(c.submit(rec(0)).result==Admission::Stopped);
    }
}
int main(){normalAndRepeat();queuedOwnership();activeCloseTimeout();captureReentryAndWriterFailure();reentrantPublicationDuringWrite();explicitCancellationRecovery();closeInsidePolicy();exhaustionAndReset();for(auto n:{1U,2U,16U,64U}){contention(n);shutdownRace(n);}std::cout<<"OWNED_EXECUTOR_PASS threads=1,2,16,64 actual_core=GA36 queued_ownership active_close timeout_no_free reentry failure-terminal saturation interrupt-deny mock-reset publishing-close-fence\n";}
