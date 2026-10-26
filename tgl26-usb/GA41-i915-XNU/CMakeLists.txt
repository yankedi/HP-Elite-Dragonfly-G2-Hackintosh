cmake_minimum_required(VERSION 3.20)
project(GA41Foundation C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
option(GA41_SANITIZE "ASan and UBSan for isolated CPU tests" ON)
if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
  message(FATAL_ERROR "This target builds only the explicit Linux CPU test backend; native XNU adapter requires KDK and separate kernel build")
endif()
add_compile_options(-Wall -Wextra -Werror -Wpedantic)
if(GA41_SANITIZE)
  add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
  add_link_options(-fsanitize=address,undefined)
endif()
add_library(gx_gem STATIC i915-xnu/gem/gx_gem.c i915-xnu/drm/gx_ioctl.c)
target_include_directories(gx_gem PUBLIC i915-xnu/include sources/linux/include/uapi/drm)
# Linux headers_install removes __user (sparse annotation). Keep originals
# unchanged; erase annotation only at compilation boundary, not layout/types.
target_compile_definitions(gx_gem PUBLIC __user= "__packed=__attribute__((packed))")
add_library(abi_compile_linux OBJECT tests/abi_compile.c)
target_include_directories(abi_compile_linux PRIVATE sources/linux/include/uapi/drm)
target_compile_definitions(abi_compile_linux PRIVATE __user= "__packed=__attribute__((packed))")
find_package(Threads REQUIRED)
add_executable(gem_cpu_test tests/test_gem.c tests/gem_cpu_backend.c)
target_link_libraries(gem_cpu_test PRIVATE gx_gem Threads::Threads)
enable_testing()
add_test(NAME GEM_CPU_MEMFD_LIFECYCLE COMMAND gem_cpu_test)

add_subdirectory(libdrm-darwin)
add_executable(drm_gem_integration
  libdrm-darwin/tests/test_drm_darwin.c tests/gem_cpu_backend.c
  $<TARGET_OBJECTS:mesa-intel-kmd>)
target_compile_definitions(drm_gem_integration PRIVATE GA41_GEM_INTEGRATION=1)
target_include_directories(drm_gem_integration PRIVATE
  tests nmx libdrm-darwin/include
  "${MESA_ROOT}/src" "${MESA_ROOT}/include" "${MESA_ROOT}/src/intel/dev")
target_link_libraries(drm_gem_integration PRIVATE gx_gem drm-darwin nmx-identity Threads::Threads)
add_test(NAME DRM_GEM_CPU_SUBSET_INTEGRATION COMMAND drm_gem_integration)
