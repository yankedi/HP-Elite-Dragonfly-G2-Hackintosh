/* GA4.5: header-free x86_64 Mach-O dylib link probe.
 * It intentionally has no libc/Foundation dependency so it can be linked
 * without an Apple SDK.  It does not touch IOKit, Metal, or a GPU.
 */
__attribute__((visibility("default"))) int xe_abi_probe_version(void) {
  return 0x4501;
}
__attribute__((visibility("default"))) int xe_abi_probe_layout(unsigned long long a, unsigned long long b) {
  return (int)(a == 0x338 && b == 0x30);
}
