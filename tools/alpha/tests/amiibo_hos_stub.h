/* Only the HLE test boundary. The amiibo implementation is compiled unchanged. */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <assert.h>
typedef struct { uint64_t x[32]; } Ctx;
#define HLE(sym) void imp_##sym(Ctx *c)
#define ARG(n) (c->x[n])
#define RET(v) (c->x[0] = (uint64_t)(v))
static unsigned char guest[4096];
static int hos_mem_region(uint64_t a, uint64_t n) { return a && a < sizeof guest && n <= sizeof guest - a; }
static void *hos_guest_range(uint64_t a, uint64_t n) { return hos_mem_region(a, n) ? guest + a : NULL; }
static unsigned events[4096];
static void hos_system_event_init(uint64_t a, int clear) { (void)clear; events[a] = 0; }
static void hos_system_event_signal(uint64_t a) { assert(a < sizeof guest); ++events[a]; }
static void hos_log(const char *fmt, ...) { (void)fmt; }
