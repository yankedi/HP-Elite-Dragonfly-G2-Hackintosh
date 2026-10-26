#!/usr/bin/env python3
"""Host-only tests of actual source helpers and real LookupPatchPlus constructors."""
import re
from common import *


def main():
    out = WORK / 'guard-tests'; out.mkdir()
    text = (WORK / 'source/src/NootedGreen/kern_gen11.cpp').read_text()
    start = text.index('static size_t hpGa414PatternCount(')
    end = text.index('// ==== 6 kextInfos:', start)
    helpers = text[start:end]
    arrays = '\n'.join(re.search(r'static const uint8_t ' + name + r'\[\] = \{[^}]+\};', text).group(0)
                       for name in ('f_noaux', 'r_noaux'))
    header = out / 'Headers/kern_patcher.hpp'; header.parent.mkdir()
    header.write_text('''#pragma once
#include <cstdint>
#include <cstddef>
using UInt8 = uint8_t;
using mach_vm_address_t = uint64_t;
struct KernelPatcher {
 struct KextInfo {};
 struct SolveRequest { template<class T> SolveRequest(const char*, T&) {} };
 struct RouteRequest { template<class... T> RouteRequest(const char*, T...) {} };
 struct LookupPatch { KextInfo *kext; const UInt8 *find; const UInt8 *replace; size_t size; size_t count; };
};
''')
    source = out / 'guards.cpp'
    actual_header = WORK / 'source/src/NootedGreen/kern_patcherplus.hpp'
    source.write_text('''#include <cstring>
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include "''' + str(actual_header) + '''"
''' + helpers + arrays + '''
static int cases = 0;
static void need(bool condition) { cases++; if (!condition) { fprintf(stderr,"case %d failed\\n",cases); exit(1); } }
int main() {
 need(hpGa414NoAuxIdentity(true,0x8c,0x8086,0x9a49,0x103c,0x8716,true,"25G83"));
 need(!hpGa414NoAuxIdentity(false,0x8c,0x8086,0x9a49,0x103c,0x8716,true,"25G83"));
 need(!hpGa414NoAuxIdentity(true,0x8d,0x8086,0x9a49,0x103c,0x8716,true,"25G83"));
 need(!hpGa414NoAuxIdentity(true,0xba,0x8086,0x9a49,0x103c,0x8716,true,"25G83"));
 need(!hpGa414NoAuxIdentity(true,0x8c,0x1234,0x9a49,0x103c,0x8716,true,"25G83"));
 need(!hpGa414NoAuxIdentity(true,0x8c,0x8086,0x9a40,0x103c,0x8716,true,"25G83"));
 need(!hpGa414NoAuxIdentity(true,0x8c,0x8086,0x9a49,0x1028,0x8716,true,"25G83"));
 need(!hpGa414NoAuxIdentity(true,0x8c,0x8086,0x9a49,0x103c,0x0000,true,"25G83"));
 need(!hpGa414NoAuxIdentity(true,0x8c,0x8086,0x9a49,0x103c,0x8716,false,"25G83"));
 need(!hpGa414NoAuxIdentity(true,0x8c,0x8086,0x9a49,0x103c,0x8716,true,"25G241"));
 need(!hpGa414NoAuxIdentity(true,0x8c,0x8086,0x9a49,0x103c,0x8716,true,"25G83x"));
 need(!hpGa414NoAuxIdentity(true,0x8c,0x8086,0x9a49,0x103c,0x8716,true,nullptr));
 need(hpGa414PatternCount(nullptr,100,f_noaux,sizeof(f_noaux))==0);
 need(hpGa414PatternCount(f_noaux,sizeof(f_noaux)-1,f_noaux,sizeof(f_noaux))==0);
 need(hpGa414PatternCount(f_noaux,sizeof(f_noaux),f_noaux,sizeof(f_noaux))==1);
 need(hpGa414PatternCount(f_noaux,sizeof(f_noaux),r_noaux,sizeof(r_noaux))==0);
 uint8_t two[2*sizeof(f_noaux)]; memcpy(two,f_noaux,sizeof(f_noaux)); memcpy(two+sizeof(f_noaux),f_noaux,sizeof(f_noaux));
 need(hpGa414PatternCount(two,sizeof(two),f_noaux,sizeof(f_noaux))==2);
 uint8_t atEnd[sizeof(f_noaux)+1] = {}; memcpy(atEnd+1,f_noaux,sizeof(f_noaux));
 need(hpGa414PatternCount(atEnd,sizeof(atEnd),f_noaux,sizeof(f_noaux))==1);
 memcpy(atEnd+1,r_noaux,sizeof(r_noaux));
 need(hpGa414PatternCount(atEnd,sizeof(atEnd),f_noaux,sizeof(f_noaux))==0);
 need(hpGa414PatternCount(atEnd,sizeof(atEnd),r_noaux,sizeof(r_noaux))==1);
 KernelPatcher::KextInfo active;
 LookupPatchPlus const patchNoAux[] = {{&active, f_noaux, r_noaux, sizeof(f_noaux), 1}};
 need(patchNoAux[0].find==f_noaux && patchNoAux[0].replace==r_noaux && patchNoAux[0].size==18 && patchNoAux[0].count==1);
 need(patchNoAux[0].findMask==nullptr && patchNoAux[0].replaceMask==nullptr && patchNoAux[0].skip==0);
 printf("SOURCE_GUARDS_PASS cases=%d constructor=unmasked-18-byte-count1\\n",cases);
}
''')
    compiler = ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined', '-I' + str(out), str(source), '-o', str(out / 'guards')]
    build_output = run(compiler)
    output = run([out / 'guards'])
    require('SOURCE_GUARDS_PASS cases=22' in output, 'guard case count/result')
    save(REPORTS / 'GUARD-TESTS.json', {'status': 'CPU_ONLY_SOURCE_GUARDS_PASS', 'cases': 22, 'output': output,
         'compiler_argv': compiler, 'compiler_output': build_output,
         'source_helpers': record(WORK / 'source/src/NootedGreen/kern_gen11.cpp'),
         'real_constructor_header': record(actual_header), 'test_harness': record(source),
         'scope': 'Actual helpers and actual LookupPatchPlus constructors; stub kernel type declarations only, not a simulated GPU/patcher execution.',
         'GPU_commands_submitted': False})
    print(output)


if __name__ == '__main__':
    main()
