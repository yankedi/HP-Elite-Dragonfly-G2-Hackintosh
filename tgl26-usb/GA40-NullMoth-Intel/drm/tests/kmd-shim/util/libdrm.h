/* Deliberate CPU test dependency, NOT libdrm and NOT a device transport. */
#ifndef GA40_KMD_TEST_LIBDRM
#define GA40_KMD_TEST_LIBDRM
typedef struct { char *name; } drmVersion;
typedef drmVersion *drmVersionPtr;
drmVersionPtr drmGetVersion(int fd);
void drmFreeVersion(drmVersionPtr version);
#endif
