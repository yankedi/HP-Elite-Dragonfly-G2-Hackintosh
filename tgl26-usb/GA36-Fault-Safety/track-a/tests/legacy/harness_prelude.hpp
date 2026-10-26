// GA36 Track A legacy-writer harness prelude.
//
// This file is NOT XNU. Every vfs/vnode/uio/thread primitive below is a fake with
// deterministic fault injection. OSCompareAndSwap is modelled as a real atomic
// compare-exchange (true = the caller acquired ownership), but it is not the macOS
// kernel implementation. The extracted hangThread() runs as an ordinary pthread,
// not as a ThreadCall callback.
#ifndef GA36_TRACKA_HARNESS_PRELUDE_HPP
#define GA36_TRACKA_HARNESS_PRELUDE_HPP

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <thread>
#include <vector>

using vfs_context_t = void *;
using vnode_t = void *;
using user_addr_t = uintptr_t;
using thread_call_param_t = void *;

// Small errno subset used by the extracted source. Some libc headers already
// define these as macros; undefine them before providing the fake values.
#undef EIO
#undef ENOMEM
#undef EACCES
#undef EINVAL
#undef ENOTEMPTY
constexpr int EIO = 5;
constexpr int ENOMEM = 12;
constexpr int EACCES = 13;
constexpr int EINVAL = 22;
constexpr int ENOTEMPTY = 66;

// Open/close/lookup/uio flag subset; only distinctness matters to the mocks.
constexpr int O_WRONLY = 0x0001;
constexpr int O_CREAT = 0x0200;
constexpr int O_TRUNC = 0x0400;
constexpr int O_NOFOLLOW = 0x0100;
constexpr int FWRITE = 0x2000;
constexpr int VNODE_LOOKUP_NOFOLLOW = 0x0001;
constexpr int UIO_SYSSPACE = 0;
constexpr int UIO_WRITE = 1;
constexpr int IO_SYNC = 1;
constexpr int FWASWRITTEN = 0x0001;
constexpr int MAXPATHLEN_FAKE = 1024;

struct MockUio {
	size_t resid {0};
	size_t added {0};
	const void *data {nullptr};
};
using uio_t = MockUio *;

enum class Fault {
	Ok,
	VfsNull,
	OpenFail,
	OpenNullVp,
	UioCreateFail,
	AddiovFail,
	WriteError,
	ShortWrite,
	CloseError,
};

struct Backend {
	Fault fault {Fault::Ok};

	std::atomic<int> vfsCreate {0};
	std::atomic<int> vfsRele {0};
	std::atomic<int> openCall {0};
	std::atomic<int> openAcquired {0}; // open returned 0 AND produced a non-null vnode
	std::atomic<int> closeCall {0};
	std::atomic<int> uioCreateCall {0};
	std::atomic<int> uioCreate {0};
	std::atomic<int> uioFreeCall {0};
	std::atomic<int> addiovCall {0};
	std::atomic<int> writeCall {0};
	std::atomic<int> writeBytes {0};
	std::atomic<int> casCalls {0};
	std::atomic<int> casSuccess {0};
	std::atomic<int> casFail {0};
	std::atomic<int> activeWrites {0};
	std::atomic<int> maxActiveWrites {0};
	std::atomic<uint64_t> lastData {0};

	std::mutex gateMutex;
	std::condition_variable gateCv;
	int arrived {0};
	bool gateWriters {false};
	int gateWriterTarget {0};
	bool gateCas {false};
	int gateCasTarget {0};

	void reset(Fault f = Fault::Ok) {
		fault = f;
		vfsCreate = 0;
		vfsRele = 0;
		openCall = 0;
		openAcquired = 0;
		closeCall = 0;
		uioCreateCall = 0;
		uioCreate = 0;
		uioFreeCall = 0;
		addiovCall = 0;
		writeCall = 0;
		writeBytes = 0;
		casCalls = 0;
		casSuccess = 0;
		casFail = 0;
		activeWrites = 0;
		maxActiveWrites = 0;
		lastData = 0;
		{
			std::lock_guard<std::mutex> lock(gateMutex);
			arrived = 0;
			gateWriters = false;
			gateWriterTarget = 0;
			gateCas = false;
			gateCasTarget = 0;
		}
		gateCv.notify_all();
	}
};

inline Backend g_be;

// OSCompareAndSwap mock: a genuine atomic CAS, success is true. This is deliberately
// the correct primitive; the baseline bug is the inverted use, not the CAS itself.
inline int MockCompareAndSwap(uint32_t oldValue, uint32_t newValue, volatile uint32_t *slot) {
	uint32_t expected = oldValue;
	uint32_t *plainSlot = const_cast<uint32_t *>(slot);
	const bool success = __atomic_compare_exchange_n(
	    plainSlot, &expected, newValue, false,
	    __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
	g_be.casCalls.fetch_add(1);
	if (success)
		g_be.casSuccess.fetch_add(1);
	else
		g_be.casFail.fetch_add(1);
	g_be.gateCv.notify_all();
	return success ? 1 : 0;
}
#define OSCompareAndSwap(a, b, c) MockCompareAndSwap((a), (b), (c))

inline vfs_context_t mock_vfs_context_create(vfs_context_t) {
	g_be.vfsCreate.fetch_add(1);
	if (g_be.fault == Fault::VfsNull)
		return nullptr;
	return reinterpret_cast<vfs_context_t>(uintptr_t(0x1000));
}

inline int mock_vnode_open(const char *, int, int, int, vnode_t *vpp, vfs_context_t) {
	g_be.openCall.fetch_add(1);
	if (g_be.fault == Fault::OpenFail) {
		if (vpp)
			*vpp = nullptr;
		return EACCES;
	}
	if (g_be.fault == Fault::OpenNullVp) {
		if (vpp)
			*vpp = nullptr;
		return 0; // looks successful but hands back no vnode
	}
	if (vpp)
		*vpp = reinterpret_cast<vnode_t>(uintptr_t(0x2000));
	g_be.openAcquired.fetch_add(1);
	return 0;
}

inline uio_t mock_uio_create(int, long long, int, int) {
	g_be.uioCreateCall.fetch_add(1);
	if (g_be.fault == Fault::UioCreateFail)
		return nullptr;
	g_be.uioCreate.fetch_add(1);
	return new MockUio();
}

inline int mock_uio_addiov(uio_t uio, user_addr_t address, size_t length) {
	if (g_be.fault == Fault::AddiovFail)
		return EINVAL;
	if (!uio)
		return EINVAL;
	uio->data = reinterpret_cast<const void *>(address);
	uio->resid = length;
	uio->added = length;
	g_be.addiovCall.fetch_add(1);
	g_be.lastData.store(reinterpret_cast<uint64_t>(address));
	return 0;
}

inline size_t mock_uio_resid(uio_t uio) {
	return uio ? uio->resid : 0;
}

inline int mock_vnop_write(vnode_t, uio_t uio, int, vfs_context_t) {
	g_be.writeCall.fetch_add(1);
	if (uio) {
		g_be.writeBytes.fetch_add(static_cast<int>(uio->added));
		g_be.lastData.store(reinterpret_cast<uint64_t>(uio->data));
	}
	const int now = g_be.activeWrites.fetch_add(1) + 1;
	int previousMax = g_be.maxActiveWrites.load();
	while (now > previousMax &&
	    !g_be.maxActiveWrites.compare_exchange_weak(previousMax, now)) {
	}
	{
		std::unique_lock<std::mutex> lock(g_be.gateMutex);
		g_be.arrived++;
		g_be.gateCv.notify_all();
		if (g_be.gateWriters) {
			g_be.gateCv.wait_for(lock, std::chrono::seconds(10), [] {
				return g_be.arrived >= g_be.gateWriterTarget;
			});
		} else if (g_be.gateCas) {
			g_be.gateCv.wait_for(lock, std::chrono::seconds(10), [] {
				return g_be.casCalls.load() >= g_be.gateCasTarget;
			});
		}
	}
	int result = 0;
	if (g_be.fault == Fault::WriteError) {
		result = EIO;
	} else if (g_be.fault == Fault::ShortWrite) {
		if (uio)
			uio->resid = 1; // caller must report EIO, never completion
		result = 0;
	} else if (uio) {
		uio->resid = 0;
	}
	g_be.activeWrites.fetch_sub(1);
	g_be.gateCv.notify_all();
	return result;
}

inline void mock_uio_free(void *pointer) {
	g_be.uioFreeCall.fetch_add(1);
	delete static_cast<MockUio *>(pointer);
}

inline int mock_vnode_close(vnode_t, int, vfs_context_t) {
	g_be.closeCall.fetch_add(1);
	if (g_be.fault == Fault::CloseError)
		return ENOTEMPTY; // vnode reference is still released by the real vnode_close
	return 0;
}

inline void mock_vfs_context_rele(vfs_context_t) {
	g_be.vfsRele.fetch_add(1);
}

inline void *lilu_os_memcpy(void *destination, const void *source, size_t length) {
	return std::memcpy(destination, source, length);
}

inline void bzero(void *destination, size_t length) {
	std::memset(destination, 0, length);
}

#ifndef SYSLOG
#define SYSLOG(...) do { } while (0)
#endif

#define vfs_context_create(ctx) mock_vfs_context_create(ctx)
#define vfs_context_rele(ctx) mock_vfs_context_rele(ctx)
#define vnode_open(path, flags, mode, lookup, vpp, ctx) \
	mock_vnode_open((path), (flags), (mode), (lookup), (vpp), (ctx))
#define vnode_close(vp, flags, ctx) mock_vnode_close((vp), (flags), (ctx))
#define uio_create(a, b, c, d) mock_uio_create((a), (b), (c), (d))
#define uio_addiov(u, a, l) mock_uio_addiov((u), (a), (l))
#define uio_resid(u) mock_uio_resid(u)
#define VNOP_WRITE(vp, u, f, c) mock_vnop_write((vp), (u), (f), (c))
#define CAST_USER_ADDR_T(p) reinterpret_cast<user_addr_t>(p)

// Minimal fake of only the members read/written by the extracted functions. The
// nested HangRecord is intentionally NOT the real wire record.
namespace IGFX {

struct TigerLakeRegisterMap {
	struct HangRecord {
		static constexpr uint32_t Magic = 0x47414854;
		static constexpr uint32_t MaxRecords = 3;
		uint32_t magic {Magic};
		uint32_t index {0};
		uint32_t ms {0};
		uint32_t attempts {0};
		uint32_t wakeDomain {0};
		uint32_t attemptReasons[8] {};
		uint32_t regs[16] {};
		uint64_t payload[8] {};
	};

	HangRecord *hangRec {nullptr};
	uint8_t *hangWriteBuf {nullptr};
	volatile uint32_t hangCount {0};
	volatile int hangWriteError {0};
	volatile uint32_t hangWriting {0};
	void (*uioFree)(void *) {nullptr};

	int hangWriteRecords(const void *data, size_t length);
	void hangThread(thread_call_param_t param0, thread_call_param_t);
};

} // namespace IGFX

#endif
