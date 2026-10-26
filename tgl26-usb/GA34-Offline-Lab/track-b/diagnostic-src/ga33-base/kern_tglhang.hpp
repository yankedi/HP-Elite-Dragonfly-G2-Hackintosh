//
//  kern_tglhang.hpp
//  WhateverGreen (GA3.1 experimental branch)
//
//  Pure logic for the read-only GPU hang capture, shared by the kext and the offline
//  unit tests.
//
//  GA3.1 physical-memory safety policy (replaces GA3's [1 MiB, stolenBase) ∪ [4 GiB,
//  _max_mem) range whitelist, which could not prove safety):
//
//    * A physical read is approved only when the platform classifier says the 4 KiB
//      page(s) it touches are kernel-managed usable RAM. In the kext this classifier is
//      the kernel's own pmap_valid_page() (built from the EFI memory map by
//      i386_vm_init; the kernel uses it in KDP/hibernation to gate physical access).
//      Reserved, MMIO, TSEG/SMRAM, graphics stolen and firmware-protected memory are
//      not part of that map and are therefore refused by construction.
//    * Extra refusal fences (never approvals): the first MiB, the graphics stolen range
//      from GGC/DSMBASE, TOLUD, and the firmware block below TOLUD reported by the host
//      bridge (BDSM/BGSM/TSEGMB). These can only remove pages from the approved set.
//    * _max_mem is used only as an upper sanity bound, never as an approval.
//    * If the classifier is unavailable or its probe fails, no physical read happens at
//      all and the attempt is recorded as MemoryMapUnverified.
//    * Every read is checked per 4 KiB page with overflow and length checks. The same
//      checks apply to GPU page-table entry reads, not just to the final data pages.
//
#ifndef kern_tglhang_hpp
#define kern_tglhang_hpp

#include <stdint.h>
#include <stddef.h>

namespace TglHang {

constexpr uint32_t MaxBatchPages  = 8;    // 32 KiB of batch
constexpr uint32_t MaxKernelPages = 2;    // 8 KiB per shader kernel
constexpr uint32_t KernelCount    = 2;    // 3DSTATE_VS and 3DSTATE_PS
constexpr uint32_t MaxRecords     = 3;    // recorded hangs per boot
constexpr uint32_t MaxPageReads   = 16;   // 8 batch + 4 kernel + slack
constexpr uint32_t MaxTableReads  = 128;  // 4 per translation, generous slack
constexpr uint64_t MaxReadBytes   = 96 * 1024;

constexpr uint64_t PageSize  = 4096;
constexpr uint64_t LowStart  = 0x100000ULL;      // the first MiB is never read
constexpr uint64_t HighStart = 0x100000000ULL;   // 4 GiB
constexpr uint64_t MaxPhysical = 1ULL << 44;     // 16 TiB: ppnum_t is 32-bit, (addr >> 12) must fit

/**
 *  GA3.3: record version, capture stages and per-attempt diagnostics. The diagnostics only observe
 *  what the existing gates decided; no gate is relaxed.
 */
constexpr uint32_t RecordVersion = 3; // GA3.3

constexpr uint32_t StageNone       = 0;
constexpr uint32_t StageClassifier = 1; // classifier gates (ready + probe)
constexpr uint32_t StageExclusions = 2; // stolen/TOLUD/TSEG exclusion gate
constexpr uint32_t StageRegisters  = 3; // BB_ADDR/PDP0 sanity
constexpr uint32_t StageBatch      = 4; // batch page translation/reads
constexpr uint32_t StageScan       = 5; // batch command scan
constexpr uint32_t StageKernel     = 6; // shader kernel translation/reads
constexpr uint32_t StageDone       = 7; // complete record

struct Diag {
	uint32_t version {RecordVersion};
	uint32_t size {0};            // sizeof(HangRecord) as built
	uint32_t stage {StageNone};   // last stage entered
	uint32_t failReason {0};      // Reason at the first refusal
	uint32_t failLevel {0xFF};    // page-table level of the first refusal (3..0, 0xFF none)
	uint32_t pmapChecked {0};     // pmap_valid_page() calls
	uint32_t pmapAccepted {0};    //   ... returning true
	uint32_t pmapRejected {0};    //   ... returning false
	uint32_t fenceRejected {0};   // ranges refused by the extra fences
	uint32_t readAttempts {0};    // physical reads attempted after all gates
	uint32_t readSuccesses {0};   //   ... that returned data
	uint32_t batchBytes {0};      // captured payload bytes
	uint32_t vsBytes {0};
	uint32_t psBytes {0};
	uint32_t bridgeDiag {0};      // bit0 read ok, bit1..4 which regs validated, bits8..15 bridgeState
	uint64_t failGpuVA {0};       // GPU VA being translated at the first refusal
	uint64_t failPhys {0};        // physical address involved in the first refusal
	uint64_t failTable {0};       // page table that contained the refused entry (0 if n/a)
};

/**
 *  GA3.2: classification-resolution diagnostics, packed into HangRecord::resolveDiag (the field
 *  was padding and stayed zero in GA3.1). The kernel log is not readable for a previous boot on
 *  this machine, so the record itself must carry the outcome of the symbol resolution.
 *    bit 0     _max_mem resolved
 *    bit 1     _pmap_valid_page resolved
 *    bit 2     pmap probe accepted (pmap_valid_page(0) == false)
 *    bit 3     _uio_free resolved
 *    bits 16-23  last KernelPatcher error code observed while resolving
 */
constexpr uint32_t ResolveMaxMem    = 1U << 0;
constexpr uint32_t ResolvePmap      = 1U << 1;
constexpr uint32_t ResolveProbeOk   = 1U << 2;
constexpr uint32_t ResolveUioFree   = 1U << 3;
constexpr uint32_t ResolveErrorShift = 16;

inline uint32_t packResolveDiag(bool maxMem, bool pmap, bool probeOk, bool uioFree, uint32_t lastError) {
	return (maxMem ? ResolveMaxMem : 0) | (pmap ? ResolvePmap : 0) | (probeOk ? ResolveProbeOk : 0) |
	    (uioFree ? ResolveUioFree : 0) | ((lastError & 0xFFU) << ResolveErrorShift);
}

/**
 *  Why a capture attempt did not produce a complete record
 */
enum Reason : uint32_t {
	Ok = 0,
	RegsInvalid,          // engine registers do not look like a hung Gen12 engine
	StolenUnknown,        // (recorded only) stolen registers unusable; classifier still governs
	AddrOutside,          // candidate outside the fences
	LimitHit,             // a page/table/byte limit stopped the capture
	NotMapped,            // the GPU page-table entry is not present (nothing to read)
	ReadFailed,           // a physical read failed
	Pml4Invalid,          // PDP0 does not look like a page-table base
	NoBatch,              // not even the batch page could be read
	ScanIncomplete,       // batch captured but STATE_BASE_ADDRESS / VS / PS were not found
	Disabled,             // feature off or not armed
	MemoryMapUnverified,  // the platform classifier is missing or failed its probe
	UnsafePhysicalRange,  // a candidate page failed the page classifier/fences
	WakesUnusable,        // only unusable SafeForceWake windows were seen
};

/**
 *  Extra refusal fences from the hang-time registers and the host bridge. Every fence
 *  is optional; a missing fence just means the classifier alone decides that range.
 */
struct Fences {
	bool haveStolen {false};
	uint64_t stolenBase {0};
	uint64_t stolenSize {0};
	bool haveLowTop {false};      // TOLUD: top of low usable DRAM
	uint64_t lowTop {0};
	bool haveTseg {false};        // TSEGMB validated: SMRAM exclusion proven
	uint64_t tsegBase {0};
	bool haveFirmwareFloor {false}; // lowest of BDSM/BGSM/TSEGMB seen below TOLUD
	uint64_t firmwareFloor {0};
	bool haveMaxMem {false};
	uint64_t maxMem {0};
};

/**
 *  Fence-only part of the policy (the classifier is applied by the caller per page).
 *  Returns false when the range must not be read.
 */
inline bool fencesAllow(const Fences &f, uint64_t address, uint64_t length) {
	if (length == 0 || length > PageSize)
		return false;
	uint64_t end = address + length;
	if (end < address)                 // integer overflow
		return false;
	if (end > HighStart && address < HighStart)
		return false;                  // a single read may not cross the 4 GiB boundary
	if (end > MaxPhysical)
		return false;                  // page number must never be truncated to 32 bits
	if (address < LowStart)
		return false;
	if (f.haveMaxMem && end > f.maxMem)
		return false;
	if (f.haveStolen && address < f.stolenBase + f.stolenSize && end > f.stolenBase)
		return false;
	if (address < HighStart) {
		if (f.haveLowTop && end > f.lowTop)
			return false;              // at/above TOLUD below 4 GiB is not DRAM
		if (f.haveTseg && address < f.lowTop && end > f.tsegBase)
			return false;              // SMRAM/TSEG block below TOLUD
		if (f.haveFirmwareFloor && address < f.lowTop && end > f.firmwareFloor)
			return false;              // firmware/graphics/SMRAM block below TOLUD
	}
	return true;
}

/**
 *  Convert a physical address into the kernel's 32-bit page number (ppnum_t). Alignment and the
 *  16 TiB ceiling are checked before the shift; when the page number would not fit into 32 bits
 *  the function returns false and pmap_valid_page() must not be called at all. The value is never
 *  truncated.
 */
inline bool toPpnum(uint64_t address, uint32_t &ppn) {
	if ((address & (PageSize - 1)) != 0)
		return false;
	if (address >= MaxPhysical)
		return false;
	uint64_t number = address >> 12;
	if (number > 0xFFFFFFFFULL)
		return false;
	ppn = static_cast<uint32_t>(number);
	return true;
}

/**
 *  Deprecated range container kept only so records can describe the derived fences.
 */
struct Range { uint64_t start, end; };

/**
 *  Reads a physical range into dst. The caller guarantees the range is approved; the
 *  kext implementation re-checks the classifier before the actual read.
 */
using ReadFn = bool (*)(void *context, uint64_t physical, void *dst, uint64_t length);

/**
 *  Approves a physical byte range. The kext supplies the platform classifier plus the
 *  fences; the tests supply a fake classifier over a simulated page map.
 */
using AllowFn = bool (*)(void *context, uint64_t address, uint64_t length);

struct Reader {
	void *context {nullptr};
	ReadFn read {nullptr};
	AllowFn allow {nullptr};
	void *allowContext {nullptr};
	Reason reason {Ok};
	uint32_t pageReads {0};
	uint32_t tableReads {0};
	uint64_t bytes {0};
	bool tableEntry {false}; // set by translate() for page-table entries
	// GA3.3 diagnostics
	uint32_t stage {StageNone};
	uint32_t level {0xFF};
	uint64_t gpuVA {0};
	uint64_t lastPhys {0};
	uint64_t lastTable {0};
	uint32_t readAttempts {0};
	uint32_t readSuccesses {0};
	bool failSeen {false};
	uint32_t failStage {StageNone};
	uint32_t failReason {0};
	uint32_t failLevel {0xFF};
	uint64_t failGpuVA {0};
	uint64_t failPhys {0};
	uint64_t failTable {0};

	/** Record the first refusal with its context; later refusals cannot happen (capture stops). */
	void markFail(Reason why, uint64_t phys, uint64_t table) {
		if (!failSeen) {
			failSeen = true;
			failStage = stage;
			failReason = static_cast<uint32_t>(why);
			failLevel = level;
			failGpuVA = gpuVA;
			failPhys = phys;
			failTable = table;
		}
	}

	/**
	 *  Bounded, classifier-verified physical read. This is the only way bytes enter a
	 *  capture: there is no path that reads without calling allow() first.
	 */
	bool fetch(uint64_t physical, void *dst, uint64_t length) {
		lastPhys = physical;
		if (!read || !allow)
			return fail(MemoryMapUnverified);
		if (length == 0 || length > PageSize)
			return fail(LimitHit);
		if (physical + length < physical)
			return fail(UnsafePhysicalRange);
		if (!allow(allowContext, physical, length))
			return fail(UnsafePhysicalRange);
		if (bytes + length > MaxReadBytes)
			return fail(LimitHit);
		if (tableEntry) {
			if (tableReads + 1 > MaxTableReads)
				return fail(LimitHit);
			tableReads++;
		} else {
			if (pageReads + 1 > MaxPageReads)
				return fail(LimitHit);
			pageReads++;
		}
		readAttempts++;
		if (!read(context, physical, dst, length))
			return fail(ReadFailed);
		readSuccesses++;
		bytes += length;
		return true;
	}

	/**
	 *  Classifier-only check for a page that will be read later (large-page targets).
	 */
	bool allowed(uint64_t physical, uint64_t length) {
		if (!allow)
			return false;
		bool ok = allow(allowContext, physical, length);
		if (!ok)
			markFail(UnsafePhysicalRange, physical, lastTable);
		return ok;
	}

private:
	bool fail(Reason why) {
		markFail(why, lastPhys, lastTable);
		reason = why;
		return false;
	}
};

/**
 *  Gen12 GMS encoding: 0x01..0xEF are 32 MiB steps, 0xF0..0xFE are 4 MiB steps.
 *  0x00 and 0xFF are undefined.
 */
inline bool parseStolen(uint32_t ggc, uint64_t dsmBase, uint64_t &base, uint64_t &size) {
	if (ggc == 0 || ggc == 0xFFFFFFFFU)
		return false;
	uint32_t gms = (ggc >> 8) & 0xFF;
	if (gms == 0 || gms == 0xFF)
		return false;
	uint64_t sz = gms >= 0xF0 ? (uint64_t(gms) - 0xF0 + 1) * 4ULL * 1024 * 1024
	                          : uint64_t(gms) * 32ULL * 1024 * 1024;
	uint64_t b = dsmBase & ~0xFFFFFULL;
	if (b < 16ULL * 1024 * 1024)
		return false;
	if (b > 0xF0000000ULL)
		return false;
	if (sz < 4ULL * 1024 * 1024 || sz > 512ULL * 1024 * 1024)
		return false;
	if (b + sz > HighStart)
		return false;
	base = b;
	size = sz;
	return true;
}

/**
 *  Host bridge (BDF 00:00.0) register interpretation. All values are raw config reads.
 *  Only conservative, validated values become fences.
 */
inline void deriveFences(uint32_t toludReg, uint32_t tsegmbReg, uint32_t bdsmReg, uint32_t bgsmReg,
    bool haveStolen, uint64_t stolenBase, uint64_t stolenSize,
    bool haveMaxMem, uint64_t maxMem, Fences &out) {
	out = Fences {};
	if (haveStolen) {
		out.haveStolen = true;
		out.stolenBase = stolenBase;
		out.stolenSize = stolenSize;
	}
	if (haveMaxMem) {
		out.haveMaxMem = true;
		out.maxMem = maxMem & ~0xFFFULL;
	}
	// TOLUD: bits 31:20 are the top of low usable DRAM in 1 MiB units.
	uint64_t lowTop = uint64_t(toludReg) & 0xFFF00000ULL;
	bool lowTopOk = toludReg != 0 && toludReg != 0xFFFFFFFFU &&
	    lowTop >= 0x40000000ULL && lowTop <= 0xFFF00000ULL;
	if (lowTopOk) {
		out.haveLowTop = true;
		out.lowTop = lowTop;
	}
	// TSEGMB: bits 31:20 are the SMRAM/TSEG base in 1 MiB units. Validated strictly;
	// when it cannot be established the caller must fail closed (SMRAM exclusion unproven).
	uint64_t tseg = uint64_t(tsegmbReg) & 0xFFF00000ULL;
	bool tsegOk = tsegmbReg != 0 && tsegmbReg != 0xFFFFFFFFU &&
	    tseg >= 64ULL * 1024 * 1024 && (!lowTopOk || tseg < lowTop);
	if (tsegOk) {
		out.haveTseg = true;
		out.tsegBase = tseg;
	}
	// Firmware block below TOLUD: lowest plausible of BDSM/BGSM/TSEGMB, 1 MiB aligned.
	uint64_t floor = ~0ULL;
	bool floorOk = false;
	const uint32_t regs[3] = { bdsmReg, bgsmReg, tsegmbReg };
	for (uint32_t i = 0; i < 3; i++) {
		uint64_t base = uint64_t(regs[i]) & 0xFFF00000ULL;
		if (regs[i] == 0 || regs[i] == 0xFFFFFFFFU)
			continue;
		if (base < 64ULL * 1024 * 1024)
			continue;
		if (lowTopOk && base >= lowTop)
			continue;
		if (base < floor) {
			floor = base;
			floorOk = true;
		}
	}
	if (floorOk) {
		out.haveFirmwareFloor = true;
		out.firmwareFloor = floor;
	}
}

/**
 *  4-level GPU page-table walk (same entry layout as x86-64: bit 0 present, bit 7 large
 *  page at levels 2 and 1). Returns the 4 KiB physical page or 0 with reader.reason set.
 *  Table entries are read through the same classifier gate as data pages.
 */
inline uint64_t translate(Reader &reader, uint64_t pml4, uint64_t address) {
	constexpr uint64_t AddrMask = 0x000FFFFFFFFFF000ULL;
	uint64_t table = pml4 & AddrMask;
	for (int level = 3; level >= 0; level--) {
		uint64_t entry = 0;
		reader.tableEntry = true;
		reader.level = static_cast<uint32_t>(level);
		reader.gpuVA = address;
		reader.lastTable = table; // GA3.3: page that contains the entry being read
		bool ok = reader.fetch(table + ((address >> (12 + 9 * level)) & 0x1FF) * 8, &entry, sizeof(entry));
		reader.tableEntry = false;
		if (!ok)
			return 0;
		if (!(entry & 1)) {
			reader.reason = NotMapped;
			return 0;
		}
		if (level > 0 && level < 3 && (entry & 0x80)) {
			uint64_t mask = (1ULL << (12 + 9 * level)) - 1;
			uint64_t page = (entry & AddrMask & ~mask) | (address & mask & ~0xFFFULL);
			reader.lastPhys = page;
			if (!reader.allowed(page, PageSize)) {
				reader.reason = UnsafePhysicalRange;
				return 0;
			}
			return page;
		}
		table = entry & AddrMask;
	}
	reader.level = 0;
	reader.lastPhys = table;
	if (!reader.allowed(table, PageSize)) {
		reader.reason = UnsafePhysicalRange;
		return 0;
	}
	return table;
}

/**
 *  3D-state commands looked for in the batch (Gen12 encodings, same as the upstream
 *  reference implementation):
 *    STATE_BASE_ADDRESS 0x61010014, 3DSTATE_VS 0x78100007, 3DSTATE_PS 0x7820xxxx
 */
struct Scan {
	bool foundSba {false};
	bool foundVs {false};
	bool foundPs {false};
	uint64_t sbaAt {0};
	uint64_t instructionBase {0};
	uint64_t kernelOffset[KernelCount] {};
	uint64_t kernelAt[KernelCount] {};
	uint32_t sbaCmd[22] {};
	uint32_t kernelCmd[KernelCount][12] {};

	bool complete() const { return foundSba && foundVs && foundPs; }
};

inline void copyBytes(void *dst, const void *src, size_t length) {
	auto d = static_cast<uint8_t *>(dst);
	auto s = static_cast<const uint8_t *>(src);
	for (size_t i = 0; i < length; i++)
		d[i] = s[i];
}

inline void scanBatch(const uint32_t *words, uint32_t wordCount, uint64_t batchStart, uint64_t bbAddr, Scan &out) {
	uint32_t end = wordCount;
	if (bbAddr >= batchStart) {
		uint64_t upTo = (bbAddr - batchStart) / 4 + 1;
		if (upTo < end)
			end = static_cast<uint32_t>(upTo);
	} else {
		end = 0;
	}
	for (uint32_t i = 0; i + 22 <= end; i++) {
		uint32_t w = words[i];
		if (w == 0x61010014) {
			copyBytes(out.sbaCmd, &words[i], sizeof(out.sbaCmd));
			out.sbaAt = batchStart + static_cast<uint64_t>(i) * 4;
			out.instructionBase = ((static_cast<uint64_t>(words[i + 11]) << 32) | words[i + 10]) & ~0xFFFULL;
			out.foundSba = true;
		} else if (w == 0x78100007 || (w & 0xFFFFFF00U) == 0x78200000U) {
			int k = w == 0x78100007 ? 0 : 1;
			copyBytes(out.kernelCmd[k], &words[i], sizeof(out.kernelCmd[k]));
			out.kernelOffset[k] = ((static_cast<uint64_t>(words[i + 2]) << 32) | words[i + 1]) & ~0x3FULL;
			out.foundVs |= k == 0;
			out.foundPs |= k == 1;
		}
	}
	if (out.foundSba) {
		out.kernelAt[0] = out.instructionBase + out.kernelOffset[0];
		out.kernelAt[1] = out.instructionBase + out.kernelOffset[1];
	}
}

/**
 *  Everything the capture needs from the engine, read through MMIO while the driver's
 *  own forcewake is held, plus the classifier state supplied by the kernel glue.
 */
struct CaptureInput {
	uint32_t regs[16] {};
	uint32_t ggc {0};
	uint64_t dsmBase {0};
	uint64_t maxMem {0};
	bool haveMaxMem {false};
	uint32_t tolud {0};
	uint32_t tsegmb {0};
	uint32_t bdsm {0};
	uint32_t bgsm {0};
	bool bridgeValid {false};
	Fences fences {};               // derived by the caller from the registers above
	bool requireExclusions {false}; // fail closed unless stolen+TOLUD+TSEG are all proven
	// Platform classifier state:
	bool classifierReady {false};   // pmap_valid_page resolved and probed
	uint32_t classifierProbeOk {0}; // 1 = pmap_valid_page(0) correctly reported invalid
	uint32_t classifierProbe1 {0};  // raw pmap_valid_page(0x40000), informational
};

struct CaptureOutput {
	Reason result {RegsInvalid};
	Fences fences {};
	uint64_t ramTop {0};
	uint64_t bbAddr {0};
	uint64_t pml4 {0};
	uint64_t batchStart {0};
	uint64_t batchPhys[MaxBatchPages] {};
	uint32_t batchValid {0};   // bit per slot, slot 7 is the BB_ADDR page
	uint32_t batchPages {0};
	uint32_t tableReads {0};
	uint32_t pageReads {0};
	uint64_t readBytes {0};
	uint32_t classifierReady {0};
	uint32_t classifierProbeOk {0};
	uint32_t classifierProbe1 {0};
	uint32_t bridgeValid {0};
	uint32_t exclusionStolen {0};
	uint32_t exclusionLowTop {0};
	uint32_t exclusionTseg {0};
	uint32_t exclusionsVerified {0};
	uint32_t bridgeRegs[4] {};  // TOLUD, TSEGMB, BDSM, BGSM
	Scan scan {};
	uint64_t kernelPhys[KernelCount] {};
	uint32_t kernelPages[KernelCount] {};
	uint8_t batch[MaxBatchPages][PageSize] {};
	uint8_t kernel[KernelCount][MaxKernelPages][PageSize] {};
};

/**
 *  The bounded capture itself. Only reader.fetch() touches physical memory, and it
 *  always consults the classifier first.
 */
inline void capture(Reader &reader, const CaptureInput &in, CaptureOutput &out) {
	reader.stage = StageClassifier;
	// 0. The platform classifier must be present and self-consistent; without it no
	//    physical read is allowed at all (requirement: MemoryMapUnverified).
	out.classifierReady = in.classifierReady ? 1 : 0;
	out.classifierProbeOk = in.classifierProbeOk;
	out.classifierProbe1 = in.classifierProbe1;
	if (!in.classifierReady || !in.classifierProbeOk) {
		out.result = MemoryMapUnverified;
		return;
	}
	reader.stage = StageExclusions;
	out.exclusionStolen = in.fences.haveStolen ? 1 : 0;
	out.exclusionLowTop = in.fences.haveLowTop ? 1 : 0;
	out.exclusionTseg = in.fences.haveTseg ? 1 : 0;
	out.exclusionsVerified = (in.fences.haveStolen && in.fences.haveLowTop && in.fences.haveTseg) ? 1 : 0;
	if (in.requireExclusions && !out.exclusionsVerified) {
		// SMRAM/graphics-stolen exclusion cannot be proven: no physical read at all.
		out.result = UnsafePhysicalRange;
		return;
	}

	reader.stage = StageRegisters;
	// 1. Registers: BB_ADDR (0x2140/0x2168) and RCS PDP0 (0x2270/0x2274).
	uint32_t bbLo = in.regs[0], bbHi = in.regs[1], pdLo = in.regs[2], pdHi = in.regs[3];
	if (bbLo == 0xFFFFFFFFU || bbHi == 0xFFFFFFFFU || pdLo == 0xFFFFFFFFU || pdHi == 0xFFFFFFFFU) {
		out.result = RegsInvalid;
		return;
	}
	out.bbAddr = (static_cast<uint64_t>(bbHi & 0xFFFF) << 32) | bbLo;
	out.pml4 = (static_cast<uint64_t>(pdHi) << 32) | (pdLo & 0xFFFFF000U);
	if (out.bbAddr < LowStart || (out.pml4 & 0xFFF) != 0 || out.pml4 == 0) {
		out.result = Pml4Invalid;
		return;
	}

	// 2. Fences (never approvals), derived by the caller from the same registers.
	out.fences = in.fences;
	out.bridgeValid = in.bridgeValid ? 1 : 0;
	out.bridgeRegs[0] = in.tolud;
	out.bridgeRegs[1] = in.tsegmb;
	out.bridgeRegs[2] = in.bdsm;
	out.bridgeRegs[3] = in.bgsm;
	if (in.haveMaxMem)
		out.ramTop = in.maxMem;

	reader.stage = StageBatch;
	// 3. Batch pages: slot 7 holds the page BB_ADDR points into.
	out.batchStart = (out.bbAddr & ~(PageSize - 1)) - (MaxBatchPages - 1) * PageSize;
	for (uint32_t i = 0; i < MaxBatchPages; i++) {
		uint64_t gpu = out.batchStart + static_cast<uint64_t>(i) * PageSize;
		uint64_t phys = translate(reader, out.pml4, gpu);
		if (!phys) {
			if (reader.reason == NotMapped)
				continue; // nothing mapped here; slot stays zeroed
			out.result = reader.reason;
			return;
		}
		if (!reader.fetch(phys, out.batch[i], PageSize)) {
			out.result = reader.reason;
			return;
		}
		out.batchPhys[i] = phys;
		out.batchValid |= 1U << i;
		out.batchPages++;
	}
	if (out.batchPages == 0) {
		out.result = NoBatch;
		return;
	}

	reader.stage = StageScan;
	// 4. Decode the state commands from the captured pages.
	auto words = reinterpret_cast<const uint32_t *>(out.batch);
	scanBatch(words, MaxBatchPages * (PageSize / 4), out.batchStart, out.bbAddr, out.scan);
	if (!out.scan.complete()) {
		out.result = ScanIncomplete;
		return;
	}

	reader.stage = StageKernel;
	// 5. Shader kernels: two pages each, translated separately.
	for (uint32_t k = 0; k < KernelCount; k++) {
		uint64_t first = out.scan.kernelAt[k];
		if (first == 0)
			continue;
		for (uint32_t p = 0; p < MaxKernelPages; p++) {
			uint64_t gpu = (first & ~(PageSize - 1)) + static_cast<uint64_t>(p) * PageSize;
			uint64_t phys = translate(reader, out.pml4, gpu);
			if (!phys) {
				if (reader.reason == NotMapped)
					break;
				out.result = reader.reason;
				return;
			}
			if (!reader.fetch(phys, out.kernel[k][p], PageSize)) {
				out.result = reader.reason;
				return;
			}
			out.kernelPhys[k] = out.kernelPhys[k] ? out.kernelPhys[k] : phys;
			out.kernelPages[k]++;
		}
	}

	reader.stage = StageDone;
	out.result = Ok;
}

/**
 *  Copies the counters of the attempt into the output for the record
 */
inline void finishCounters(const Reader &reader, CaptureOutput &out) {
	out.tableReads = reader.tableReads;
	out.pageReads = reader.pageReads;
	out.readBytes = reader.bytes;
}

} // namespace TglHang

#endif
