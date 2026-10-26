// CPU-only real LLVM bitcode regression input; never submitted to a GPU.
int ga46_add(int a, int b) { return a + b; }
static int state;
int ga46_accumulate(int n) { state += n; return state; }
