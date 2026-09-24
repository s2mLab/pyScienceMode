/* Minimal libc stand-in used only by generate_cdef.py so that pycparser can
 * parse the ScienceMode4 headers without platform/compiler-specific system
 * headers. Declarations coming from this directory are never emitted in the
 * cdef (cffi already knows these types). */
#ifndef FAKE_LIBC_TYPES_H
#define FAKE_LIBC_TYPES_H
typedef signed char int8_t;
typedef unsigned char uint8_t;
typedef short int16_t;
typedef unsigned short uint16_t;
typedef int int32_t;
typedef unsigned int uint32_t;
typedef long long int64_t;
typedef unsigned long long uint64_t;
typedef unsigned long size_t;
typedef long time_t;
typedef struct _fake_FILE FILE;
typedef _Bool bool;
#define true 1
#define false 0
#define NULL 0
#endif
