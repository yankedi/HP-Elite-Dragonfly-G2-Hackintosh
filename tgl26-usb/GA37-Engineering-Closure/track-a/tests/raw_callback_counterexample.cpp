// Negative test: actual GA36 core with the missing external lifetime owner.
// Only executed under ASan in a child; a detected UAF is the expected counterexample.
#include "../source/kern_capture36.hpp"
struct R{unsigned index;};struct P{static bool valid(const R &,unsigned)noexcept{return true;}};
struct OldAdapter {R a[3]{},b[3]{};Capture36::Pipeline<R,3,P> pipeline{a,b};};
int main(){auto owner=new OldAdapter;auto raw=&owner->pipeline;owner->pipeline.close();if(!owner->pipeline.quiescent())return 3;delete owner;return static_cast<int>(raw->drain(nullptr,nullptr));}
