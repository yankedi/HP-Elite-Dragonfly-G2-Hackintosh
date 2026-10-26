//
//  test_tglhang.cpp — offline unit tests for the GA3.1 hang capture core.
//
//  Build:  nix-shell -p gcc --run 'g++ -std=c++17 -O2 -Wall -Wextra -Werror -o test_tglhang test_tglhang.cpp'
//  Run:    ./test_tglhang
//
//  The fake world models:
//    * a platform classifier (a set of "valid" 4 KiB pages, standing in for pmap_valid_page),
//    * the extra refusal fences (stolen, TOLUD, firmware block, maxMem),
//    * physical memory contents.
//  Any read attempt outside the approved set is counted as a violation and fails the run.
//
#include "../kern_tglhang.hpp"

#include <cstdio>
#include <cstring>
#include <map>
#include <set>
#include <vector>

using namespace TglHang;

static int failures = 0;
static int tests = 0;

#define CHECK(cond) do { \
	if (!(cond)) { std::printf("FAIL %s:%d  %s\n", __func__, __LINE__, #cond); failures++; } \
} while (0)

#define CHECK_EQ(a, b) do { \
	auto va = (a); auto vb = (b); \
	if (!(va == vb)) { std::printf("FAIL %s:%d  %s == %s (%llu != %llu)\n", __func__, __LINE__, #a, #b, \
		(unsigned long long)va, (unsigned long long)vb); failures++; } \
} while (0)

// ---------------------------------------------------------------------------
// Fake platform
// ---------------------------------------------------------------------------
struct Platform {
	std::set<uint64_t> validPages;                  // fake pmap_valid_page page set
	std::map<uint64_t, std::vector<uint8_t>> pages; // fake physical memory
	Fences fences {};
	bool classifierReady = true;
	uint32_t probe0 = 1;                            // pmap_valid_page(0) -> false (encoded 0)
	uint32_t probe1 = 1;                            // informational

	uint64_t nextPhys = 0x20000000;
	uint64_t reads = 0;
	uint64_t violations = 0;
	mutable std::set<uint64_t> classified;  // pages the classifier was asked about
	mutable std::set<uint64_t> readTargets; // pages the harness actually copied from

	bool pageValid(uint64_t page) const { return validPages.count(page) != 0; }

	bool allow(uint64_t address, uint64_t length) const {
		if (!classifierReady || !probe0)
			return false;
		if (!fencesAllow(fences, address, length))
			return false;
		uint64_t end = address + length;
		for (uint64_t page = address & ~(PageSize - 1); page < end; page += PageSize) {
			classified.insert(page);
			if (!pageValid(page))
				return false;
		}
		return true;
	}

	uint64_t alloc(uint8_t fill = 0) {
		uint64_t p = nextPhys;
		pages[p] = std::vector<uint8_t>(4096, fill);
		validPages.insert(p);
		nextPhys += 4096;
		return p;
	}

	uint64_t allocAt(uint64_t phys, uint8_t fill = 0) {
		pages[phys] = std::vector<uint8_t>(4096, fill);
		validPages.insert(phys);
		return phys;
	}

	void invalidate(uint64_t phys) { validPages.erase(phys & ~0xFFFULL); }

	void poke(uint64_t phys, uint64_t off, const void *src, size_t len) {
		if ((phys & 0xFFF) + off + len > 4096) { std::printf("poke overflow\n"); failures++; return; }
		auto it = pages.find(phys & ~0xFFFULL);
		if (it == pages.end()) { std::printf("poke: no page %llx\n", (unsigned long long)phys); failures++; return; }
		std::memcpy(it->second.data() + (phys & 0xFFF) + off, src, len);
	}

	void pokeSpan(uint64_t phys, uint64_t off, const void *src, size_t len) {
		auto s = static_cast<const uint8_t *>(src);
		uint64_t at = (phys & ~0xFFFULL) + off;
		while (len > 0) {
			auto it = pages.find(at & ~0xFFFULL);
			if (it == pages.end()) { std::printf("pokeSpan: no page %llx\n", (unsigned long long)at); failures++; return; }
			size_t room = 4096 - (at & 0xFFF);
			size_t chunk = len < room ? len : room;
			std::memcpy(it->second.data() + (at & 0xFFF), s, chunk);
			s += chunk; at += chunk; len -= chunk;
		}
	}

	void setEntry(uint64_t tablePhys, uint32_t index, uint64_t value) {
		poke(tablePhys, uint64_t(index) * 8, &value, 8);
	}
};

static bool harnessAllow(void *ctx, uint64_t address, uint64_t length) {
	return static_cast<Platform *>(ctx)->allow(address, length);
}

static bool harnessRead(void *ctx, uint64_t physical, void *dst, uint64_t length) {
	auto p = static_cast<Platform *>(ctx);
	p->reads++;
	if (!p->allow(physical, length)) { p->violations++; return false; }
	p->readTargets.insert(physical & ~0xFFFULL);
	if ((physical & 0xFFF) + length > 4096)
		return false;
	auto it = p->pages.find(physical & ~0xFFFULL);
	if (it == p->pages.end())
		return false;
	std::memcpy(dst, it->second.data() + (physical & 0xFFF), length);
	return true;
}

// ---------------------------------------------------------------------------
// Page table helpers
// ---------------------------------------------------------------------------
static const uint64_t AddrMask = 0x000FFFFFFFFFF000ULL;

static uint64_t tableFor(Platform &p, uint64_t pml4, uint64_t va, int level, bool create) {
	uint64_t table = pml4;
	for (int l = 3; l > level; l--) {
		uint64_t entry = 0;
		uint64_t slot = (va >> (12 + 9 * l)) & 0x1FF;
		auto it = p.pages.find(table);
		if (it != p.pages.end())
			std::memcpy(&entry, it->second.data() + slot * 8, 8);
		if (!(entry & 1)) {
			if (!create)
				return 0;
			uint64_t next = p.alloc();
			entry = next | 0x3;
			p.setEntry(table, uint32_t(slot), entry);
		}
		table = entry & AddrMask;
	}
	return table;
}

static void map4K(Platform &p, uint64_t pml4, uint64_t va, uint64_t phys) {
	uint64_t pt = tableFor(p, pml4, va, 0, true);
	p.setEntry(pt, uint32_t((va >> 12) & 0x1FF), (phys & AddrMask) | 0x3);
}

static void map2M(Platform &p, uint64_t pml4, uint64_t va, uint64_t phys) {
	uint64_t pd = tableFor(p, pml4, va, 1, true);
	p.setEntry(pd, uint32_t((va >> 21) & 0x1FF), (phys & AddrMask & ~0x1FFFFFULL) | 0x80 | 0x3);
}

// Large-page mapping is exercised in test_large_page_target.
static void test_large_page_target();



// ---------------------------------------------------------------------------
// Constants used by the scenarios
// ---------------------------------------------------------------------------
static const uint64_t BB_VA   = 0x40B75ED8ULL;
static const uint64_t BATCH   = BB_VA & ~0xFFFULL;
static const uint64_t BSTART  = BATCH - 7 * 4096;
static const uint64_t IBASE   = 0x80000000ULL;
static const uint64_t VS_OFF  = 0x1000;
static const uint64_t PS_OFF  = 0x2000;
static const uint32_t GGC_128MB = 4U << 8;

static const uint64_t STOLEN_BASE = 0xC0000000ULL;   // 128 MiB stolen
static const uint64_t TOLUD       = 0xC8000000ULL;
static const uint64_t TSEGMB      = 0xB0000000ULL;   // TSEG below stolen (problem A)
static const uint64_t BDSM        = 0xBC000000ULL;
static const uint64_t BGSM        = 0xBE000000ULL;

static void standardFences(Fences &f) {
	deriveFences(uint32_t(TOLUD), uint32_t(TSEGMB), uint32_t(BDSM), uint32_t(BGSM),
	    true, STOLEN_BASE, 128ULL << 20, true, 16ULL << 30, f);
}

static CaptureInput makeInput(uint64_t pml4, bool classifierReady = true) {
	CaptureInput in {};
	in.regs[0] = uint32_t(BB_VA);
	in.regs[1] = uint32_t(BB_VA >> 32) & 0xFFFF;
	in.regs[2] = uint32_t(pml4);
	in.regs[3] = uint32_t(pml4 >> 32);
	in.ggc = GGC_128MB;
	in.dsmBase = STOLEN_BASE;
	in.maxMem = 16ULL << 30;
	in.haveMaxMem = true;
	in.tolud = uint32_t(TOLUD);
	in.tsegmb = uint32_t(TSEGMB);
	in.bdsm = uint32_t(BDSM);
	in.bgsm = uint32_t(BGSM);
	in.bridgeValid = true;
	standardFences(in.fences);
	in.requireExclusions = true;
	in.classifierReady = classifierReady;
	in.classifierProbeOk = 1; // pmap_valid_page(0) reported page 0 invalid
	in.classifierProbe1 = 1;
	return in;
}

// A complete happy-path setup: 8 batch pages + SBA/VS/PS + 2 kernels.
static void buildHappyPath(Platform &p, uint64_t pml4, std::vector<uint64_t> &batchPhys) {
	for (int i = 0; i < 8; i++)
		batchPhys.push_back(p.alloc());
	for (int i = 0; i < 8; i++)
		map4K(p, pml4, BSTART + i * 4096, batchPhys[i]);
	uint32_t sba[22] = {};
	sba[0] = 0x61010014;
	sba[10] = uint32_t(IBASE);
	sba[11] = uint32_t(IBASE >> 32);
	p.poke(batchPhys[0], 100 * 4, sba, sizeof(sba));

	uint32_t vs[12] = {};
	vs[0] = 0x78100007;
	vs[1] = uint32_t(VS_OFF) & ~0x3FU;
	p.pokeSpan(batchPhys[0], 1022 * 4, vs, sizeof(vs)); // spans into the next batch page

	uint32_t ps[12] = {};
	ps[0] = 0x7820000B;
	ps[1] = uint32_t(PS_OFF);
	p.poke(batchPhys[2], 32, ps, sizeof(ps));

	uint64_t vsPhys0 = p.alloc(0x90), vsPhys1 = p.alloc(0x91), psPhys0 = p.alloc(0x92);
	map4K(p, pml4, IBASE + VS_OFF, vsPhys0);
	map4K(p, pml4, IBASE + VS_OFF + 4096, vsPhys1);
	map4K(p, pml4, IBASE + PS_OFF, psPhys0);
}

static void runCapture(Platform &p, CaptureInput &in, CaptureOutput &out) {
	Reader reader {&p, harnessRead, harnessAllow, &p};
	capture(reader, in, out);
	finishCounters(reader, out);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
static void test_happy_path() {
	tests++;
	Platform p;
	Fences f {};
	standardFences(f);
	p.fences = f;
	uint64_t pml4 = p.alloc();
	std::vector<uint64_t> batchPhys;
	buildHappyPath(p, pml4, batchPhys);

	CaptureOutput out {};
	CaptureInput in = makeInput(pml4);
	Reader reader {&p, harnessRead, harnessAllow, &p};
	capture(reader, in, out);
	finishCounters(reader, out);

	CHECK_EQ(out.result, Ok);
	CHECK_EQ(out.batchPages, 8u);
	CHECK_EQ(out.batchValid, 0xFFu);
	CHECK(out.scan.complete());
	CHECK_EQ(out.scan.kernelAt[0], IBASE + VS_OFF);
	CHECK_EQ(out.scan.kernelAt[1], IBASE + PS_OFF);
	CHECK_EQ(out.kernelPages[0], 2u);
	CHECK_EQ(out.kernelPages[1], 1u);
	CHECK(out.readBytes <= MaxReadBytes);
	CHECK(out.pageReads <= MaxPageReads);
	CHECK(out.tableReads <= MaxTableReads);
	CHECK(p.violations == 0);
	CHECK_EQ(out.fences.haveStolen, true);
	CHECK_EQ(out.fences.haveLowTop, true);
	CHECK_EQ(out.fences.haveFirmwareFloor, true);
	CHECK_EQ(out.fences.firmwareFloor, TSEGMB);
}

static void test_classifier_unavailable_no_reads() {
	tests++;
	Platform p;
	Fences f {};
	standardFences(f);
	p.fences = f;
	uint64_t pml4 = p.alloc();
	CaptureOutput out {};
	CaptureInput in = makeInput(pml4, false);
	runCapture(p, in, out);
	CHECK_EQ(out.result, MemoryMapUnverified);
	CHECK_EQ(p.reads, 0ULL);
	CHECK_EQ(p.violations, 0ULL);
}

static void test_classifier_probe_failed_no_reads() {
	tests++;
	Platform p;
	uint64_t pml4 = p.alloc();
	CaptureOutput out {};
	CaptureInput in = makeInput(pml4);
	in.classifierProbeOk = 0; // pmap_valid_page(0) returned true -> refuse everything
	Fences f {};
	standardFences(f);
	p.fences = f;
	Reader reader {&p, harnessRead, harnessAllow, &p};
	capture(reader, in, out);
	CHECK_EQ(out.result, MemoryMapUnverified);
	CHECK_EQ(p.reads, 0ULL);
}

// Problem A: TSEG/SMRAM sits below the graphics stolen area; a PTE pointing there must
// be refused although GA3's [1 MiB, stolenBase) range would have allowed it.
static void test_pte_into_tseg_below_stolen_refused() {
	tests++;
	Platform p;
	Fences f {};
	standardFences(f);
	p.fences = f;
	uint64_t pml4 = p.alloc();
	std::vector<uint64_t> batchPhys;
	for (int i = 0; i < 8; i++) {
		uint64_t ph = p.alloc();
		batchPhys.push_back(ph);
	}
	// Slot 3 points into the TSEG range [TSEGMB, ...): page 0xB0000000.
	uint64_t tsegPage = TSEGMB + 0x400000;
	batchPhys[3] = tsegPage;
	// The classifier does not have this page (SMRAM is not usable RAM) but the page has
	// contents that *would* be readable; a violation is recorded if anyone tries.
	p.pages[tsegPage] = std::vector<uint8_t>(4096, 0x5A);
	for (int i = 0; i < 8; i++)
		map4K(p, pml4, BSTART + i * 4096, batchPhys[i]);

	CaptureOutput out {};
	CaptureInput in = makeInput(pml4);
	runCapture(p, in, out);
	CHECK_EQ(out.result, UnsafePhysicalRange);
	CHECK_EQ(p.violations, 0ULL);
	// The refused page must never have been read: at most the pages before it were captured.
	CHECK(out.batchPages <= 3u);
}

static void test_pte_into_reserved_hole_refused() {
	tests++;
	Platform p;
	Fences f {};
	standardFences(f);
	p.fences = f;
	uint64_t pml4 = p.alloc();
	std::vector<uint64_t> batchPhys;
	for (int i = 0; i < 8; i++)
		batchPhys.push_back(p.alloc());
	// A reserved hole inside [1 MiB, stolenBase): keep the page readable in the fake
	// world but mark it invalid for the classifier.
	uint64_t holePage = 0x40000000ULL;
	p.pages[holePage] = std::vector<uint8_t>(4096, 0x11);
	p.validPages.erase(holePage);
	batchPhys[5] = holePage;
	for (int i = 0; i < 8; i++)
		map4K(p, pml4, BSTART + i * 4096, batchPhys[i]);

	CaptureOutput out {};
	CaptureInput in = makeInput(pml4);
	runCapture(p, in, out);
	CHECK_EQ(out.result, UnsafePhysicalRange);
	CHECK_EQ(p.violations, 0ULL);
}

static void test_pte_above_ram_refused() {
	tests++;
	Platform p;
	Fences f {};
	standardFences(f);
	p.fences = f;
	uint64_t pml4 = p.alloc();
	std::vector<uint64_t> batchPhys;
	for (int i = 0; i < 8; i++)
		batchPhys.push_back(p.alloc());
	batchPhys[2] = 0x500000000ULL; // above 16 GiB: not in the classifier either
	for (int i = 0; i < 8; i++)
		map4K(p, pml4, BSTART + i * 4096, batchPhys[i]);

	CaptureOutput out {};
	CaptureInput in = makeInput(pml4);
	runCapture(p, in, out);
	CHECK_EQ(out.result, UnsafePhysicalRange);
	CHECK_EQ(p.violations, 0ULL);
}

static void test_cross_page_table_entry_read_refused() {
	tests++;
	Platform p;
	Fences f {};
	standardFences(f);
	p.fences = f;
	uint64_t pml4 = p.alloc();
	std::vector<uint64_t> batchPhys;
	for (int i = 0; i < 8; i++)
		batchPhys.push_back(p.alloc());
	for (int i = 0; i < 8; i++)
		map4K(p, pml4, BSTART + i * 4096, batchPhys[i]);

	// Make the *page-table* page holding the last entries invalid for the classifier:
	// the walk must refuse even though the data pages are fine.
	uint64_t pt = tableFor(p, pml4, BSTART, 0, true);
	p.validPages.erase(pt);

	CaptureOutput out {};
	CaptureInput in = makeInput(pml4);
	runCapture(p, in, out);
	CHECK_EQ(out.result, UnsafePhysicalRange);
	CHECK_EQ(p.violations, 0ULL);
}

static void test_stolen_fence_blocks_even_if_classifier_lies() {
	tests++;
	Platform p;
	Fences f {};
	standardFences(f);
	p.fences = f;
	uint64_t pml4 = p.alloc();
	std::vector<uint64_t> batchPhys;
	for (int i = 0; i < 8; i++)
		batchPhys.push_back(p.alloc());
	// Simulate a firmware bug: the stolen page is in the "valid" set.
	uint64_t stolenPage = STOLEN_BASE + 0x1000;
	p.pages[stolenPage] = std::vector<uint8_t>(4096, 0);
	p.validPages.insert(stolenPage);
	batchPhys[1] = stolenPage;
	for (int i = 0; i < 8; i++)
		map4K(p, pml4, BSTART + i * 4096, batchPhys[i]);

	CaptureOutput out {};
	CaptureInput in = makeInput(pml4);
	runCapture(p, in, out);
	CHECK_EQ(out.result, UnsafePhysicalRange);
	CHECK_EQ(p.violations, 0ULL);
}

static void test_tolud_fence_blocks_hole() {
	tests++;
	Platform p;
	Fences f {};
	standardFences(f);
	p.fences = f;
	uint64_t pml4 = p.alloc();
	std::vector<uint64_t> batchPhys;
	for (int i = 0; i < 8; i++)
		batchPhys.push_back(p.alloc());
	uint64_t mmio = 0xE0000000ULL; // between TOLUD and 4 GiB
	p.pages[mmio] = std::vector<uint8_t>(4096, 0);
	p.validPages.insert(mmio);
	batchPhys[6] = mmio;
	for (int i = 0; i < 8; i++)
		map4K(p, pml4, BSTART + i * 4096, batchPhys[i]);

	CaptureOutput out {};
	CaptureInput in = makeInput(pml4);
	runCapture(p, in, out);
	CHECK_EQ(out.result, UnsafePhysicalRange);
	CHECK_EQ(p.violations, 0ULL);
}

static void test_missing_earlier_pages_tolerated() {
	tests++;
	Platform p;
	Fences f {};
	standardFences(f);
	p.fences = f;
	uint64_t pml4 = p.alloc();
	uint64_t bbPhys = p.alloc(), earlierPhys = p.alloc();
	map4K(p, pml4, BATCH, bbPhys);
	map4K(p, pml4, BSTART + 3 * 4096, earlierPhys);
	uint32_t sba[22] = {0x61010014};
	sba[10] = uint32_t(IBASE);
	sba[11] = uint32_t(IBASE >> 32);
	p.poke(earlierPhys, 0, sba, sizeof(sba));
	uint32_t vs[12] = {0x78100007};
	vs[1] = uint32_t(VS_OFF);
	p.poke(earlierPhys, 96, vs, sizeof(vs));
	uint32_t ps[12] = {0x7820000B};
	ps[1] = uint32_t(PS_OFF);
	p.poke(earlierPhys, 160, ps, sizeof(ps));
	uint64_t vsPhys = p.alloc(), psPhys = p.alloc();
	map4K(p, pml4, IBASE + VS_OFF, vsPhys);
	map4K(p, pml4, IBASE + PS_OFF, psPhys);

	CaptureOutput out {};
	CaptureInput in = makeInput(pml4);
	runCapture(p, in, out);
	CHECK_EQ(out.result, Ok);
	CHECK_EQ(out.batchPages, 2u);
	CHECK(out.scan.complete());
	CHECK_EQ(out.scan.kernelAt[0], IBASE + VS_OFF);
	CHECK_EQ(out.kernelPages[0], 2u); // the PS page follows the VS page in VA order
	CHECK_EQ(p.violations, 0ULL);
}

static void test_command_after_bb_ignored() {
	tests++;
	Platform p;
	Fences f {};
	standardFences(f);
	p.fences = f;
	uint64_t pml4 = p.alloc();
	uint64_t bbPhys = p.alloc();
	map4K(p, pml4, BATCH, bbPhys);
	uint32_t ps[12] = {0x7820000B};
	ps[1] = uint32_t(PS_OFF);
	p.poke(bbPhys, 0xF00, ps, sizeof(ps));
	CaptureOutput out {};
	CaptureInput in = makeInput(pml4);
	runCapture(p, in, out);
	CHECK_EQ(out.result, ScanIncomplete);
	CHECK(!out.scan.foundPs);
}

static void test_large_page_target() {
	tests++;
	Platform p;
	Fences f {};
	standardFences(f);
	p.fences = f;
	uint64_t pml4 = p.alloc();
	// Batch through a 2 MiB page whose physical base is a valid page.
	uint64_t base2M = 0x30000000ULL;
	uint64_t off2M = BSTART & 0x1FFFFFULL;
	map2M(p, pml4, BSTART, base2M);
	for (int i = 0; i < 8; i++)
		p.allocAt(base2M + off2M + i * 4096);
	uint64_t cmdPage = base2M + off2M + 3 * 4096;
	uint32_t sba[22] = {0x61010014};
	sba[10] = uint32_t(IBASE);
	sba[11] = uint32_t(IBASE >> 32);
	p.poke(cmdPage, 0, sba, sizeof(sba));
	uint32_t vs[12] = {0x78100007};
	vs[1] = uint32_t(VS_OFF);
	p.poke(cmdPage, 96, vs, sizeof(vs));
	uint32_t ps[12] = {0x7820000B};
	ps[1] = uint32_t(PS_OFF);
	p.poke(cmdPage, 160, ps, sizeof(ps));
	// Kernels via a 2 MiB page too.
	uint64_t kbase2M = 0x34000000ULL;
	map2M(p, pml4, IBASE, kbase2M);
	for (uint64_t off = VS_OFF; off <= PS_OFF + 4096; off += 4096)
		p.allocAt(kbase2M + (IBASE & 0x1FFFFFULL) + off);

	CaptureOutput out {};
	CaptureInput in = makeInput(pml4);
	runCapture(p, in, out);
	CHECK_EQ(out.result, Ok);
	CHECK_EQ(out.batchPages, 8u);
	CHECK_EQ(p.violations, 0ULL);
}

// pmap_valid_page() takes a 32-bit ppnum_t: the conversion from a physical address must be
// checked (alignment, 16 TiB ceiling) and must never truncate a page number.
static void test_ppnum_conversion() {
	tests++;
	uint32_t ppn = 0xDEADBEEF;
	CHECK(!toPpnum(0x1234, ppn));                        // not page aligned
	CHECK(toPpnum(0x0, ppn)); CHECK_EQ(ppn, 0u);
	CHECK(toPpnum(PageSize, ppn)); CHECK_EQ(ppn, 1u);
	CHECK(toPpnum(MaxPhysical - PageSize, ppn));
	CHECK_EQ(ppn, 0xFFFFFFFFu);                           // largest representable page number
	CHECK(!toPpnum(MaxPhysical, ppn));                    // 16 TiB: does not fit into 32 bits
	CHECK(!toPpnum(MaxPhysical + PageSize, ppn));
	CHECK(!toPpnum(0xFFFFFFFFFFFFF000ULL, ppn));          // top of the 48-bit address space
	CHECK_EQ(ppn, 0xFFFFFFFFu);                           // a failed conversion leaves the output alone
}

// Forged page-table entries above 16 TiB must abort the capture before classification, even when
// (address >> 12) truncated to 32 bits would land on a valid page. Both the _max_mem fence and
// the 16 TiB ppnum_t limit itself are exercised.
static void test_forged_high_physical_addresses() {
	tests++;
	for (int variant = 0; variant < 2; variant++) {
		Platform p;
		Fences f {};
		standardFences(f);
		if (variant == 1)
			f.haveMaxMem = false; // only the 16 TiB ppnum_t limit applies
		p.fences = f;
		uint64_t pml4 = p.alloc();
		std::vector<uint64_t> batchPhys;
		buildHappyPath(p, pml4, batchPhys);
		uint64_t realPage = batchPhys[7];             // the page BB_ADDR points into
		uint64_t forged = (1ULL << 44) + realPage;    // (forged >> 12) truncates onto realPage
		map4K(p, pml4, BATCH, forged);                // remap the batch page to the forged address
		CaptureOutput out {};
		CaptureInput in = makeInput(pml4);
		runCapture(p, in, out);
		CHECK_EQ(out.result, UnsafePhysicalRange);
		CHECK_EQ(p.violations, 0ULL);
		CHECK_EQ(p.classified.count(realPage), 0u);   // no truncated page number was classified
		CHECK_EQ(p.readTargets.count(realPage), 0u);  // and the truncation target was never read
	}
}

// GA3.2: the classifier-resolution diagnostics that must appear in every record.
static void test_pack_resolve_diag() {
	tests++;
	CHECK_EQ(packResolveDiag(false, false, false, false, 0), 0u);
	CHECK_EQ(packResolveDiag(true, true, true, true, 0), 0x0Fu);
	CHECK_EQ(packResolveDiag(true, true, true, true, 0xAB), 0x00AB000Fu);
	CHECK_EQ(packResolveDiag(false, false, false, false, 0x1234), 0x00340000u); // low 8 bits only
	CHECK_EQ(packResolveDiag(true, false, false, true, 7), 0x00070009u);
	CHECK_EQ(packResolveDiag(false, true, true, false, 0x0F), 0x000F0006u);
}

static void test_limits() {
	tests++;
	Platform p;
	Fences f {};
	standardFences(f);
	p.fences = f;
	uint64_t base = p.alloc() & ~0xFFFULL;
	for (uint32_t i = 0; i < MaxPageReads + 1; i++)
		p.allocAt(base + i * 4096);
	{
		Reader reader {&p, harnessRead, harnessAllow, &p};
		uint8_t buf[4096];
		bool ok = true;
		for (uint32_t i = 0; i < MaxPageReads; i++)
			ok = reader.fetch(base + i * 4096, buf, 4096) && ok;
		CHECK(ok);
		CHECK_EQ(reader.pageReads, MaxPageReads);
		CHECK(!reader.fetch(base + MaxPageReads * 4096, buf, 4096));
		CHECK_EQ(reader.reason, LimitHit);
	}
	{
		Reader reader2 {&p, harnessRead, harnessAllow, &p};
		reader2.tableEntry = true;
		uint8_t buf[8];
		bool ok = true;
		for (uint32_t i = 0; i < MaxTableReads; i++)
			ok = reader2.fetch(base + i * 8, buf, 8) && ok;
		CHECK(ok);
		CHECK_EQ(reader2.tableReads, MaxTableReads);
		CHECK(!reader2.fetch(base, buf, 8));
		CHECK_EQ(reader2.reason, LimitHit);
	}
}

// The first capture must fail closed when the SMRAM/stolen exclusion cannot be proven.
static void test_exclusions_unverified_fail_closed() {
	tests++;
	// (a) host bridge unavailable: no TOLUD/TSEG fences
	{
		Platform p;
		uint64_t pml4 = p.alloc();
		CaptureOutput out {};
		CaptureInput in = makeInput(pml4);
		deriveFences(0, 0, 0, 0, true, STOLEN_BASE, 128ULL << 20, true, 16ULL << 30, in.fences);
		p.fences = in.fences;
		runCapture(p, in, out);
		CHECK_EQ(out.result, UnsafePhysicalRange);
		CHECK_EQ(p.reads, 0ULL);
		CHECK_EQ(p.violations, 0ULL);
		CHECK_EQ(out.exclusionsVerified, 0u);
	}
	// (b) stolen registers unusable (GGC garbage): no stolen fence
	{
		Platform p;
		uint64_t pml4 = p.alloc();
		CaptureOutput out {};
		CaptureInput in = makeInput(pml4);
		in.ggc = 0;
		standardFences(in.fences);
		// standardFences() builds fences with a valid stolen range; simulate the unverifiable case:
		deriveFences(uint32_t(TOLUD), uint32_t(TSEGMB), uint32_t(BDSM), uint32_t(BGSM),
		    false, 0, 0, true, 16ULL << 30, in.fences);
		p.fences = in.fences;
		runCapture(p, in, out);
		CHECK_EQ(out.result, UnsafePhysicalRange);
		CHECK_EQ(p.reads, 0ULL);
	}
	// (c) TSEGMB unreadable but TOLUD fine: SMRAM exclusion unproven
	{
		Platform p;
		uint64_t pml4 = p.alloc();
		CaptureOutput out {};
		CaptureInput in = makeInput(pml4);
		deriveFences(uint32_t(TOLUD), 0xFFFFFFFF, uint32_t(BDSM), uint32_t(BGSM),
		    true, STOLEN_BASE, 128ULL << 20, true, 16ULL << 30, in.fences);
		p.fences = in.fences;
		runCapture(p, in, out);
		CHECK_EQ(out.result, UnsafePhysicalRange);
		CHECK_EQ(p.reads, 0ULL);
	}
	// (d) all proven: capture proceeds
	{
		Platform p;
		Fences f {};
		standardFences(f);
		p.fences = f;
		uint64_t pml4 = p.alloc();
		std::vector<uint64_t> batchPhys;
		buildHappyPath(p, pml4, batchPhys);
		CaptureOutput out {};
		CaptureInput in = makeInput(pml4);
		runCapture(p, in, out);
		CHECK_EQ(out.result, Ok);
		CHECK_EQ(out.exclusionsVerified, 1u);
		CHECK_EQ(p.violations, 0ULL);
	}
}

static void test_fences_policy() {
	tests++;
	Fences f {};
	standardFences(f);
	CHECK(fencesAllow(f, 0x100000, 4096));                 // first usable MiB
	CHECK(!fencesAllow(f, 0x1000, 4096));                  // first MiB refused
	CHECK(!fencesAllow(f, 0xFFFFF, 8));                    // crosses 1 MiB boundary from below
	CHECK(fencesAllow(f, 0x40000000, 4096));               // inside low RAM
	CHECK(!fencesAllow(f, STOLEN_BASE, 4096));             // stolen base
	CHECK(!fencesAllow(f, STOLEN_BASE - 4096, 8192));      // overlaps stolen
	CHECK(!fencesAllow(f, TSEGMB, 4096));                  // SMRAM/TSEG base
	CHECK(!fencesAllow(f, TSEGMB + 0x100000, 4096));       // inside SMRAM
	CHECK(!fencesAllow(f, TSEGMB - 8, 16));                // crosses into SMRAM
	CHECK(!fencesAllow(f, BDSM, 4096));                    // firmware block
	CHECK(!fencesAllow(f, TOLUD, 4096));                   // at TOLUD
	CHECK(!fencesAllow(f, TOLUD - 8, 16));                 // crosses TOLUD
	CHECK(fencesAllow(f, HighStart + 0x1000, 4096));       // high RAM is not affected by TOLUD
	CHECK(!fencesAllow(f, 0xFFFFFFFFFFFFF000ULL, 0x2000)); // overflow
	CHECK(!fencesAllow(f, HighStart - 8, 16));             // crosses 4 GiB boundary
	CHECK(!fencesAllow(f, (16ULL << 30) - 8, 16));         // above maxMem
	CHECK(!fencesAllow(f, 0x2000, 8192));                  // length > one page
	CHECK(!fencesAllow(f, MaxPhysical - 4096, 4096));      // above maxMem here, and bounded anyway
	CHECK(!fencesAllow(f, MaxPhysical - 8, 16));           // crosses the 16 TiB ceiling
	{
		Fences none {};
		CHECK(fencesAllow(none, MaxPhysical - 4096, 4096)); // without other fences this is the only bound
		CHECK(!fencesAllow(none, MaxPhysical, 4096));       // at 16 TiB the page number would not fit
	}
}

static void test_derive_fences() {
	tests++;
	Fences f {};
	deriveFences(uint32_t(TOLUD), uint32_t(TSEGMB), uint32_t(BDSM), uint32_t(BGSM),
	    true, STOLEN_BASE, 128ULL << 20, true, 16ULL << 30, f);
	CHECK(f.haveLowTop); CHECK_EQ(f.lowTop, TOLUD);
	CHECK(f.haveTseg); CHECK_EQ(f.tsegBase, TSEGMB);
	CHECK(f.haveFirmwareFloor); CHECK_EQ(f.firmwareFloor, TSEGMB); // TSEGMB < BDSM < BGSM
	CHECK(f.haveStolen); CHECK_EQ(f.stolenBase, STOLEN_BASE);
	{
		Fences g {};
		deriveFences(0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, true, STOLEN_BASE, 128ULL << 20, false, 0, g);
		CHECK(!g.haveLowTop);
		CHECK(!g.haveFirmwareFloor);
		CHECK(g.haveStolen); // stolen from GGC/DSMBASE still applies
	}
	{
		Fences h {};
		deriveFences(uint32_t(TOLUD), 0, 0, 0, false, 0, 0, true, 16ULL << 30, h);
		CHECK(h.haveLowTop); CHECK(!h.haveTseg); CHECK(!h.haveFirmwareFloor); CHECK(!h.haveStolen);
	}
	{
		Fences t {};
		deriveFences(uint32_t(TOLUD), 0xFFFFFFFF, uint32_t(BDSM), uint32_t(BGSM), true, STOLEN_BASE, 128ULL << 20, true, 16ULL << 30, t);
		CHECK(t.haveLowTop); CHECK(!t.haveTseg); CHECK(t.haveFirmwareFloor); CHECK(t.haveStolen);
	}
	{
		Fences k {};
		deriveFences(0x1000, 0x1000, 0x1000, 0x1000, false, 0, 0, false, 0, k); // nonsense values
		CHECK(!k.haveLowTop);
		CHECK(!k.haveFirmwareFloor);
	}
}

static void test_parse_stolen_table() {
	tests++;
	uint64_t b = 0, s = 0;
	CHECK(parseStolen(4U << 8, STOLEN_BASE, b, s)); CHECK_EQ(b, STOLEN_BASE); CHECK_EQ(s, 128ULL << 20);
	CHECK(parseStolen(0xF0U << 8, 0x80000000ULL, b, s)); CHECK_EQ(s, 4ULL << 20);
	CHECK(!parseStolen(0xFFU << 8, 0x80000000ULL, b, s));
	CHECK(!parseStolen(0, 0x80000000ULL, b, s));
	CHECK(!parseStolen(4U << 8, 0x8000ULL, b, s));
	CHECK(!parseStolen(4U << 8, 0xF8000000ULL, b, s));
}

int main() {
	test_happy_path();
	test_classifier_unavailable_no_reads();
	test_classifier_probe_failed_no_reads();
	test_pte_into_tseg_below_stolen_refused();
	test_pte_into_reserved_hole_refused();
	test_pte_above_ram_refused();
	test_cross_page_table_entry_read_refused();
	test_stolen_fence_blocks_even_if_classifier_lies();
	test_tolud_fence_blocks_hole();
	test_pack_resolve_diag();
	test_forged_high_physical_addresses();
	test_ppnum_conversion();
	test_missing_earlier_pages_tolerated();
	test_large_page_target();
	test_command_after_bb_ignored();
	test_limits();
	test_exclusions_unverified_fail_closed();
	test_fences_policy();
	test_derive_fences();
	test_parse_stolen_table();

	std::printf("%d test groups, %d failures\n", tests, failures);
	return failures ? 1 : 0;
}
