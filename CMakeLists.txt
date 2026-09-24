cmake_minimum_required(VERSION 3.26)
project(pysciencemode LANGUAGES C)

# Builds the `sciencemode._sciencemode` cffi extension (API mode) on top of a
# static build of HASOMED's ScienceMode4 C library (git submodule).
# Driven by scikit-build-core (see pyproject.toml); `pip install .` is enough.

set(SMPT_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/extern/ScienceMode4_c_library")
set(SMPT_LIB "${SMPT_ROOT}/ScienceMode_Library")
if(NOT EXISTS "${SMPT_LIB}/src/general/smpt_client.c")
  message(FATAL_ERROR
    "ScienceMode4 C library sources not found in ${SMPT_ROOT}.\n"
    "Run: git submodule update --init --recursive")
endif()

# SKBUILD_SABI_COMPONENT is "Development.SABIModule" when scikit-build-core
# builds an abi3 wheel (wheel.py-api in pyproject.toml), empty otherwise
# (e.g. free-threaded CPython, which has no stable ABI).
find_package(Python REQUIRED COMPONENTS Interpreter Development.Module ${SKBUILD_SABI_COMPONENT})

# --- Static ScienceMode4 library (general + low-level + mid-level) ----------
# We define our own target instead of add_subdirectory() so that the upstream
# test executable and install() rules do not end up in the wheel. The dyscom
# level is not built: its client API is disabled upstream on macOS and it is
# not used by pysciencemode.
file(GLOB SMPT_SOURCES CONFIGURE_DEPENDS
  "${SMPT_LIB}/src/general/*.c"
  "${SMPT_LIB}/src/general/packet/*.c"
  "${SMPT_LIB}/src/general/packet_input_buffer/*.c"
  "${SMPT_LIB}/src/general/packet_output_buffer/*.c"
  # Each OS-specific file is fully guarded by #ifdef _WIN32 / __linux__ /
  # __APPLE__, so compiling all of them is correct on every platform.
  "${SMPT_LIB}/src/general/serial_port/*.c"
  "${SMPT_LIB}/src/low-level/*.c"
  "${SMPT_LIB}/src/mid-level/*.c"
)
add_library(smpt STATIC ${SMPT_SOURCES})
set_target_properties(smpt PROPERTIES
  C_STANDARD 99
  POSITION_INDEPENDENT_CODE ON)
target_include_directories(smpt PUBLIC
  "${SMPT_LIB}/include"
  "${SMPT_LIB}/include/general"
  "${SMPT_LIB}/include/general/packet"
  "${SMPT_LIB}/include/general/packet_input_buffer"
  "${SMPT_LIB}/include/general/packet_output_buffer"
  "${SMPT_LIB}/include/general/serial_port"
  "${SMPT_LIB}/include/low-level"
  "${SMPT_LIB}/include/mid-level")
target_compile_definitions(smpt PUBLIC SMPT_LOW_LEVEL SMPT_MID_LEVEL)
if(MSVC)
  target_compile_definitions(smpt PUBLIC _CRT_SECURE_NO_WARNINGS)
endif()
if(UNIX)
  target_link_libraries(smpt PUBLIC m)
endif()

# --- cffi extension ---------------------------------------------------------
set(FFI_BUILDER "${CMAKE_CURRENT_SOURCE_DIR}/tools/cffi/build_ffi.py")
set(FFI_CDEF "${CMAKE_CURRENT_SOURCE_DIR}/tools/cffi/smpt_cdef.h")
set(FFI_C "${CMAKE_CURRENT_BINARY_DIR}/_sciencemode.c")
add_custom_command(
  OUTPUT "${FFI_C}"
  COMMAND "${Python_EXECUTABLE}" "${FFI_BUILDER}" "${FFI_C}"
  DEPENDS "${FFI_BUILDER}" "${FFI_CDEF}"
  COMMENT "Generating cffi C source for sciencemode._sciencemode"
  VERBATIM)

# cffi's generated code targets the CPython limited API by default, so we build
# a single abi3 extension (one wheel per platform for all CPython >= 3.10).
if(SKBUILD_SABI_VERSION)
  python_add_library(_sciencemode MODULE WITH_SOABI USE_SABI ${SKBUILD_SABI_VERSION} "${FFI_C}")
else()
  python_add_library(_sciencemode MODULE WITH_SOABI "${FFI_C}")
  # Otherwise cffi would still define Py_LIMITED_API (and, with MSVC, try to
  # link python3.lib) while we link against the version-specific library.
  target_compile_definitions(_sciencemode PRIVATE _CFFI_NO_LIMITED_API)
endif()
target_link_libraries(_sciencemode PRIVATE smpt)

install(TARGETS _sciencemode LIBRARY DESTINATION sciencemode)
# The licenses of the bundled C library (MPL-2.0 OR LGPL-3.0-or-later) are
# shipped in the wheel's .dist-info/licenses via `license-files` (pyproject).
