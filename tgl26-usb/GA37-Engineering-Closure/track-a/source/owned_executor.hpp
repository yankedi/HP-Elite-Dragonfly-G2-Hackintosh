// SPDX-License-Identifier: MIT
// Hosted ownership adapter over the unchanged GA36 Pipeline. No XNU/MMIO API.
#ifndef GA37_OWNED_EXECUTOR_HPP
#define GA37_OWNED_EXECUTOR_HPP
#include "kern_capture36.hpp"
#include <array>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <memory>
#include <mutex>
#include <utility>

namespace Capture37 {
enum class Context { Thread, Interrupt };
enum class Phase { Running, ClosingDrain, ClosingCancel, Closed };
enum class Shutdown { Drain, CancelQueued };
enum class Admission { Accepted, Busy, Incomplete, Invalid, Full, Stopped, Failed, SequenceExhausted, InterruptRejected };
enum class Executed { Written, Idle, Busy, Retry, Failed, Cancelled, Consumed, InterruptRejected };

template<class Record,uint32_t Capacity,class Policy> class Session {
    using Pipeline=Capture36::Pipeline<Record,Capacity,Policy>;
    using Gate=std::recursive_mutex; // defined same-thread try-admission for Policy reentry
    struct Control {
        // All queue/active/lifecycle counters are under gate. Pipeline atomics
        // protect the record prefix against drain running outside gate.
        Gate gate;
        std::condition_variable_any changed;
        std::array<Record,Capacity> slots{},snapshot{};
        Pipeline pipeline{slots.data(),snapshot.data()};
        // Backend lifetime travels with the control, never a naked captured self.
        const std::shared_ptr<void> backend;
        const Capture36::Write writer;
        Phase phase=Phase::Running;
        uint64_t nextTicket=0,queued=0,active=0,publishing=0,cancelled=0,completed=0;
        Control(std::shared_ptr<void> b,Capture36::Write w,uint64_t first)
            : backend(std::move(b)),writer(w),nextTicket(first) {}
        void finishIfIdle() {
            if(phase!=Phase::Running && phase!=Phase::Closed && queued==0 && active==0 && publishing==0) {
                pipeline.close();phase=Phase::Closed;
            }
            changed.notify_all();
        }
        void stop(Shutdown mode) {
            std::lock_guard<Gate> lock(gate);
            if(phase==Phase::Running) phase=mode==Shutdown::Drain?Phase::ClosingDrain:Phase::ClosingCancel;
            else if(phase==Phase::ClosingDrain && mode==Shutdown::CancelQueued) phase=Phase::ClosingCancel;
            finishIfIdle();
        }
    };
public:
    struct Info {
        Phase phase;
        uint64_t queued,active,publishing,cancelled,completed,nextTicket;
        uint32_t published,written;
        int error;
        bool allPublishedWritten() const noexcept {return published==written && error==0;}
    };
    class Ticket {
        friend class Session;
        std::shared_ptr<Control> state_;
        uint64_t id_=0;
        Ticket(std::shared_ptr<Control> s,uint64_t id) noexcept:state_(std::move(s)),id_(id) {}
        void cancel() noexcept {
            auto s=std::move(state_);
            if(!s)return;
            std::lock_guard<Gate> lock(s->gate);
            --s->queued;++s->cancelled;s->finishIfIdle();
        }
    public:
        Ticket() noexcept=default;
        Ticket(const Ticket &)=delete;
        Ticket &operator=(const Ticket &)=delete;
        Ticket(Ticket &&other) noexcept:state_(std::move(other.state_)),id_(other.id_) {}
        Ticket &operator=(Ticket &&other) noexcept {
            if(this!=&other){cancel();state_=std::move(other.state_);id_=other.id_;}return *this;
        }
        ~Ticket(){cancel();}
        explicit operator bool() const noexcept {return bool(state_);}
        uint64_t id() const noexcept {return id_;}
        Executed run(Context context=Context::Thread) {
            if(context==Context::Interrupt)return Executed::InterruptRejected;
            auto s=std::move(state_);
            if(!s)return Executed::Consumed;
            {
                std::lock_guard<Gate> lock(s->gate);
                --s->queued;
                if(s->phase==Phase::ClosingCancel || s->phase==Phase::Closed) {
                    ++s->cancelled;s->finishIfIdle();return Executed::Cancelled;
                }
                ++s->active;
            }
            // Write callback must return normally. A timeout never authorizes
            // force-free, pthread cancellation, longjmp or unloading active code.
            const auto result=s->pipeline.drain(s->writer,s->backend.get());
            {
                std::lock_guard<Gate> lock(s->gate);
                --s->active;
                // Core's bounded lease refusal is not close. Return the owned
                // notification intact so a scheduler cannot silently lose it.
                if(result==Capture36::Drain::Stopped && s->phase!=Phase::ClosingCancel) {
                    ++s->queued;state_=s;s->changed.notify_all();return Executed::Retry;
                }
                ++s->completed;s->finishIfIdle();
            }
            switch(result) {
                case Capture36::Drain::Written:return Executed::Written;
                case Capture36::Drain::Idle:return Executed::Idle;
                case Capture36::Drain::Busy:return Executed::Busy;
                case Capture36::Drain::Failed:return Executed::Failed;
                case Capture36::Drain::Stopped:return Executed::Cancelled;
            }
            return Executed::Failed;
        }
    };
    struct Submission {Admission result;Ticket ticket;};
    class Client {
        friend class Session;
        std::shared_ptr<Control> state_;
        explicit Client(std::shared_ptr<Control> s) noexcept:state_(std::move(s)) {}
        static Admission map(Capture36::Submit r) noexcept {
            switch(r) {
                case Capture36::Submit::Accepted:return Admission::Accepted;
                case Capture36::Submit::Busy:return Admission::Busy;
                case Capture36::Submit::Incomplete:return Admission::Incomplete;
                case Capture36::Submit::Invalid:return Admission::Invalid;
                case Capture36::Submit::Full:return Admission::Full;
                case Capture36::Submit::Failed:case Capture36::Submit::RetainedFailed:return Admission::Failed;
                // With the adapter gate Running and held, no shutdown can
                // close this core. Stopped here is its bounded lease refusal.
                case Capture36::Submit::Stopped:return Admission::Busy;
                case Capture36::Submit::RetainedStopped:return Admission::Stopped;
            }
            return Admission::Invalid;
        }
    public:
        Submission submit(const Record &r,bool complete=true,Context context=Context::Thread) const {
            if(context==Context::Interrupt)return {Admission::InterruptRejected,{}};
            auto s=state_; // caller must own a live Client value during this call
            std::unique_lock<Gate> lock(s->gate,std::try_to_lock);
            if(!lock.owns_lock())return {Admission::Busy,{}};
            if(s->phase!=Phase::Running)return {Admission::Stopped,{}};
            if(s->nextTicket==UINT64_MAX)return {Admission::SequenceExhausted,{}};
            ++s->publishing;
            auto result=s->pipeline.publish(r,complete);
            --s->publishing;
            if(result!=Capture36::Submit::Accepted){s->finishIfIdle();return {map(result),{}};}
            const auto id=s->nextTicket++;++s->queued;
            return {Admission::Accepted,Ticket{s,id}};
        }
        // Explicit recovery notification after a caller deliberately cancelled a
        // ticket; it does not re-publish/alter slots or reset a failed writer.
        Submission notify(Context context=Context::Thread) const {
            if(context==Context::Interrupt)return {Admission::InterruptRejected,{}};
            auto s=state_;std::lock_guard<Gate> lock(s->gate);
            if(s->phase!=Phase::Running)return {Admission::Stopped,{}};
            if(s->pipeline.failed())return {Admission::Failed,{}};
            if(!s->pipeline.pending())return {Admission::Incomplete,{}};
            if(s->nextTicket==UINT64_MAX)return {Admission::SequenceExhausted,{}};
            const auto id=s->nextTicket++;++s->queued;return {Admission::Accepted,Ticket{s,id}};
        }
        void requestShutdown(Shutdown mode) const {state_->stop(mode);}
        bool waitClosed(std::chrono::milliseconds budget) const {
            auto s=state_;std::unique_lock<Gate> lock(s->gate);
            return s->changed.wait_for(lock,budget,[&]{return s->phase==Phase::Closed;});
        }
        Info info() const {
            auto s=state_;std::lock_guard<Gate> lock(s->gate);
            return {s->phase,s->queued,s->active,s->publishing,s->cancelled,s->completed,s->nextTicket,s->pipeline.published(),s->pipeline.written(),s->pipeline.error()};
        }
        std::weak_ptr<void> lifetimeProbe() const noexcept {return state_;}
    };
private:
    std::shared_ptr<Control> state_;
public:
    // firstTicket permits deterministic exhaustion tests; no reset or wrap API.
    Session(std::shared_ptr<void> backend,Capture36::Write writer,uint64_t firstTicket=0)
        :state_(std::make_shared<Control>(std::move(backend),writer,firstTicket)) {}
    Session(const Session &)=delete;
    Session &operator=(const Session &)=delete;
    Session(Session &&)=delete;
    Session &operator=(Session &&)=delete;
    ~Session(){state_->stop(Shutdown::CancelQueued);} // nonblocking, no raw free
    Client client() const noexcept {return Client{state_};}
};
} // namespace Capture37
#endif
