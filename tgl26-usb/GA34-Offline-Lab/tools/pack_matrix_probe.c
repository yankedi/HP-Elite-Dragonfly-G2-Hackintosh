/* Keep independent pack checks live in optimized Release test executables. */
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "../reference/track-a/pack-proof.c"
