// GA415: bounded, read-only observations for the audited 25G83 TGL donor only.
// No allocation, FP arithmetic, resource writes, routing decision or return substitution.
#ifndef GA415_BLIT_OBSERVER_HPP
#define GA415_BLIT_OBSERVER_HPP

static bool gGa415ObsEnabled = false;
static mach_vm_address_t gGa415OrgSourceCopy = 0, gGa415OrgFastCopy = 0, gGa415Org3D = 0;
static volatile uint32_t gGa415ObsGeneral = 0, gGa415ObsUnaligned = 0, gGa415ObsProbe = 0;

static uint32_t ga415Obs32(const void *object, size_t offset) {
	uint32_t value;
	memcpy(&value, reinterpret_cast<const uint8_t *>(object) + offset, sizeof(value));
	return value;
}

static uint32_t ga415ObsClaim(volatile uint32_t *counter, uint32_t limit) {
	// Saturating budget with bounded contention; never wrap and resume logging.
	for (unsigned attempt = 0; attempt < 8; attempt++) {
		const uint32_t old = *counter;
		if (old >= limit) return 0;
		if (__sync_bool_compare_and_swap(counter, old, old + 1)) return old + 1;
	}
	return 0;
}

static void ga415ObsLog(const char *kind, const void *params, const void *rectVector) {
	if (!gGa415ObsEnabled || !params || !rectVector) return;
	const auto *p = reinterpret_cast<const uint8_t *>(params);
	const uint32_t sp = ga415Obs32(p, 0x08), dp = ga415Obs32(p, 0x50);
	const uint32_t sb = ga415Obs32(p, 0x00), so = ga415Obs32(p, 0x2c);
	const uint32_t db = ga415Obs32(p, 0x48), dO = ga415Obs32(p, 0x74);
	uint64_t count = 0;
	memcpy(&count, rectVector, sizeof(count));
	uint32_t rect[8] = {};
	if (count) {
		const void *data = nullptr;
		memcpy(&data, reinterpret_cast<const uint8_t *>(rectVector) + 0x10, sizeof(data));
		if (data) memcpy(rect, data, sizeof(rect));
	}
	// Reserve a separate budget for the known A/B/C geometry. Rect values are float bits;
	// do not evaluate floating point in a kernel hook. First pair has widths at +8/+24.
	const bool knownWidth = rect[2] == 0x44200000U || rect[2] == 0x44208000U ||
		rect[6] == 0x44200000U || rect[6] == 0x44208000U;
	const bool knownPitch = sp == 2560 || sp == 2568 || sp == 2576 || sp == 2624 ||
		dp == 2560 || dp == 2568 || dp == 2576 || dp == 2624;
	const bool unaligned = ((sp | dp | (sb + so) | (db + dO)) & 63U) != 0;
	const char *category = knownWidth && knownPitch ? "P" : unaligned ? "U" : "G";
	uint32_t n = category[0] == 'P' ? ga415ObsClaim(&gGa415ObsProbe, 96) :
		category[0] == 'U' ? ga415ObsClaim(&gGa415ObsUnaligned, 16) : ga415ObsClaim(&gGa415ObsGeneral, 16);
	if (!n) return;
	// tag is a lossy correlation token, not a raw pointer or unique resource ID.
	const uint32_t tag = static_cast<uint32_t>(reinterpret_cast<uintptr_t>(params) >> 4);
	IOLog("GA415OBS kind=%s cls=%s n=%u tag=%08x sp=%u dp=%u st=%u dt=%u sb=%08x so=%08x db=%08x do=%08x bpe=%u rs=%u f3=%u/%u aux=%u/%u rects=%llu r=%08x,%08x,%08x,%08x,%08x,%08x,%08x,%08x\n",
		kind, category, n, tag, sp, dp, p[0x0c], p[0x54], sb, so, db, dO,
		p[0xa0], (p[0xa2] >> 3U) & 3U, p[0x3c] & 1U, p[0x84] & 1U,
		ga415Obs32(p, 0x20) != 0 || ga415Obs32(p, 0x24) != 0,
		ga415Obs32(p, 0x68) != 0 || ga415Obs32(p, 0x6c) != 0, count,
		rect[0], rect[1], rect[2], rect[3], rect[4], rect[5], rect[6], rect[7]);
}

// Exact audited donor callers ignore these helpers' return registers. Tail-call
// the original once with identical arguments; no context/task/resource edits.
static void ga415ObsSourceCopy(void *ctx, void *params, void *rects, void *wa) {
	ga415ObsLog("COPY2D", params, rects);
	FunctionCast(ga415ObsSourceCopy, gGa415OrgSourceCopy)(ctx, params, rects, wa);
}

static void ga415ObsFastCopy(void *ctx, void *params, void *rects, void *wa) {
	ga415ObsLog("FAST2D", params, rects);
	FunctionCast(ga415ObsFastCopy, gGa415OrgFastCopy)(ctx, params, rects, wa);
}

static void ga415Obs3D(void *ctx, void *params, void *rects) {
	ga415ObsLog("COPY3D", params, rects);
	FunctionCast(ga415Obs3D, gGa415Org3D)(ctx, params, rects);
}

#endif
