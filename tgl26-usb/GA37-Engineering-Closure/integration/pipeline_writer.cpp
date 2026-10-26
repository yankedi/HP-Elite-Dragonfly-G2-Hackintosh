// Actual GA36 byte-prefix Pipeline -> owned GA37 executor -> transactional writer.
// Input is read-only historical THAG; no GPU data is modified or regenerated.
#include "../track-a/source/owned_executor.hpp"
#include "snapshot_writer.hpp"
#include <array>
#include <cassert>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <memory>
#include <vector>
namespace fs=std::filesystem;
using namespace std::chrono_literals;
constexpr size_t RecordSize=0xc2a0;
struct Record {std::array<uint8_t,RecordSize> bytes;};
static_assert(sizeof(Record)==RecordSize,"wire bytes only");
uint32_t le32(const uint8_t *p){return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);}
struct Policy {static bool valid(const Record &r,uint32_t n)noexcept{return le32(r.bytes.data())==0x47414854 && le32(r.bytes.data()+4)==n;}};
using Owned=Capture37::Session<Record,3,Policy>;
constexpr Capture36::Write actualCallback=&ga37::SnapshotWriter::callback_adapter<Capture36::WriteResult>;
std::vector<uint8_t> read(const fs::path &path){std::ifstream f(path,std::ios::binary);assert(f);return {std::istreambuf_iterator<char>(f),{}};}
std::vector<fs::path> revisions(const fs::path &parent){std::vector<fs::path> out;for(const auto &e:fs::directory_iterator(parent/"revisions"))if(e.path().extension()==".snap")out.push_back(e.path());return out;}
int main(int argc,char **argv){
    assert(argc==3);auto bytes=read(argv[1]);assert(bytes.size()==RecordSize*2);
    ga37::recordwire::Snapshot decoded;assert(ga37::recordwire::parse(bytes.data(),bytes.size(),decoded));assert(decoded.version==2 && decoded.records.size()==2);
    Record a{},b{};std::memcpy(a.bytes.data(),bytes.data(),RecordSize);std::memcpy(b.bytes.data(),bytes.data()+RecordSize,RecordSize);
    const fs::path root=argv[2];fs::create_directories(root/"success");fs::create_directories(root/"failure");
    for(auto directory:{root/"success",root/"failure"})fs::permissions(directory,fs::perms::owner_all,fs::perm_options::replace);
    ga37::WriterOptions options;options.parent_directory=(root/"success").string();
    auto writer=std::make_shared<ga37::SnapshotWriter>(options);
    {
        Owned owner(writer,actualCallback);auto client=owner.client();
        auto first=client.submit(a);assert(first.result==Capture37::Admission::Accepted);assert(first.ticket.run()==Capture37::Executed::Written);
        assert(writer->last_commit().success());assert(client.info().written==1);
        auto second=client.submit(b);assert(second.result==Capture37::Admission::Accepted);assert(second.ticket.run()==Capture37::Executed::Written);
        auto receipt=writer->last_commit();assert(receipt.success() && receipt.sequence==2);
        assert(client.info().allPublishedWritten());assert(revisions(root/"success").size()==2);
        assert(client.notify().result==Capture37::Admission::Incomplete);
        auto again=actualCallback(writer.get(),bytes.data(),bytes.size());assert(again.error==0 && again.transferred==bytes.size());assert(revisions(root/"success").size()==2);
        client.requestShutdown(Capture37::Shutdown::Drain);assert(client.waitClosed(100ms));
    }
    // Fresh writer/process-state recovery of a full prefix is idempotent.
    {ga37::SnapshotWriter recovered(options);auto result=actualCallback(&recovered,bytes.data(),bytes.size());assert(result.error==0);assert(recovered.last_commit().sequence==2);}
    // Establish durable old evidence, then inject a returned write failure while
    // the actual Pipeline retains the longer immutable prefix in Failed state.
    options.parent_directory=(root/"failure").string();
    {ga37::SnapshotWriter initial(options);auto result=actualCallback(&initial,a.bytes.data(),a.bytes.size());assert(result.error==0);}
    auto oldfiles=revisions(root/"failure");assert(oldfiles.size()==1);auto old=read(oldfiles[0]);
    options.fault.fail_stage=ga37::FaultStage::Write;auto failing=std::make_shared<ga37::SnapshotWriter>(options);
    {
        Owned owner(failing,actualCallback);auto client=owner.client();
        auto first=client.submit(a);assert(first.ticket.run()==Capture37::Executed::Written); // identical durable prefix is reused
        auto second=client.submit(b);auto secondResult=second.ticket.run();
        if(secondResult!=Capture37::Executed::Failed){auto d=client.info();std::cerr<<"failure-case submit="<<unsigned(second.result)<<" execute="<<unsigned(secondResult)<<" coreerr="<<d.error<<" writererr="<<unsigned(failing->last_commit().error)<<" count="<<d.published<<" written="<<d.written<<"\n";}
        assert(secondResult==Capture37::Executed::Failed);
        auto info=client.info();assert(info.published==2 && info.written==1 && info.error!=0);
        assert(client.notify().result==Capture37::Admission::Failed);
        assert(read(oldfiles[0])==old && revisions(root/"failure").size()==1);
        client.requestShutdown(Capture37::Shutdown::Drain);assert(client.waitClosed(100ms));assert(!client.info().allPublishedWritten());
    }
    bool finalFound=false;for(auto p:revisions(root/"success")){auto stored=read(p);if(stored==bytes)finalFound=true;}
    assert(finalFound);std::cout<<"INTEGRATION_PASS actual_GA36_core owned_executor exact_nominal_ABI THAG2 immutable_full_prefix durable_recovery duplicate_idempotent failure_terminal old_evidence_preserved\n";
}
