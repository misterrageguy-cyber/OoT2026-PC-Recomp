/* (Ocarina Reborn, diagnostics) which UI layouts the game looks up, and from where.

   f_8100dde0 is the UI manager's find-by-name: x0 the manager, w1 the layout's name as a Murmur3 hash. Each new pair of
   (name hash, caller) is logged once with the time since the start, so a pickup's layout shows up as a new line the moment
   it first appears. Bounded: at most 4096 pairs, then silent. tools/alpha/hud/ocr_uidiag.py hooks it. */
#include "hos.h"
#include <windows.h>
#include <stdbool.h>

static struct { uint32_t hash; uint64_t lr; } seen[4096];
static volatile LONG n_seen;
static SRWLOCK lock = SRWLOCK_INIT;

void ocr_uidiag(Ctx *c) {
    const uint32_t hash = (uint32_t)c->x[1];
    const uint64_t lr = c->x[30];
    static uint64_t t0;
    if (!t0) t0 = GetTickCount64();
    AcquireSRWLockShared(&lock);
    const LONG n = n_seen;
    for (LONG i = 0; i < n; i++)
        if (seen[i].hash == hash && seen[i].lr == lr) { ReleaseSRWLockShared(&lock); return; }
    ReleaseSRWLockShared(&lock);
    AcquireSRWLockExclusive(&lock);
    if (n_seen < (LONG)(sizeof seen / sizeof seen[0])) {
        for (LONG i = n; i < n_seen; i++)
            if (seen[i].hash == hash && seen[i].lr == lr) { ReleaseSRWLockExclusive(&lock); return; }
        seen[n_seen].hash = hash, seen[n_seen].lr = lr, n_seen++;
        hos_log("[OcarinaReborn/UIDIAG] t=%.1fs layout %08x from %#llx", (GetTickCount64() - t0) / 1000.0, hash,
                (unsigned long long)lr);
    }
    ReleaseSRWLockExclusive(&lock);
}

/* (and each site that names a counter layout: logged on its first run and again whenever it runs after a second or more of
   quiet, with how often it ran meanwhile. A per-frame site shows once; a pickup's shows at the moment of the pickup) */
static const char *const site_names[] = {"NumDisplayMiniGame_00", "NumDisplay_00", "PlayerStatus_00", "SimpleInfo_00"};
static struct { unsigned long long pc; uint64_t last; LONG runs; } sites[128];
static volatile LONG n_sites, site_lines;
static SRWLOCK site_lock = SRWLOCK_INIT;

void ocr_uidiag_site(unsigned long long pc, int name) {
    static uint64_t t0;
    const uint64_t now = GetTickCount64();
    if (!t0) t0 = now;
    AcquireSRWLockExclusive(&site_lock);
    LONG i = 0;
    while (i < n_sites && sites[i].pc != pc) i++;
    if (i == n_sites) {
        if (n_sites >= (LONG)(sizeof sites / sizeof sites[0])) { ReleaseSRWLockExclusive(&site_lock); return; }
        sites[n_sites].pc = pc, sites[n_sites].last = 0, sites[n_sites].runs = 0, n_sites++;
    }
    const bool quiet = !sites[i].last || now - sites[i].last >= 1000;
    const LONG runs = ++sites[i].runs;
    sites[i].last = now;
    if (quiet && site_lines < 4000) {
        site_lines++;
        sites[i].runs = 0;
        hos_log("[OcarinaReborn/UIDIAG] t=%.1fs site %#llx %s (ran %ld times since its last line)", (now - t0) / 1000.0, pc,
                name >= 0 && name < 4 ? site_names[name] : "?", (long)runs - 1);
    }
    ReleaseSRWLockExclusive(&site_lock);
}

/* (and calls with their arguments: x0, x1, x2 and the caller, once per new (place, caller, x1) and again after a second of
   quiet: f_80fac430 (the HUD's NumDisplay on or off), f_8340e350 (a layout's open or close)) */
static struct { unsigned long long pc, lr, a1; uint64_t last; } calls[512];
static volatile LONG n_calls;
static SRWLOCK call_lock = SRWLOCK_INIT;

void ocr_uidiag_call(Ctx *c, unsigned long long pc) {
    static uint64_t t0;
    const uint64_t now = GetTickCount64();
    if (!t0) t0 = now;
    const unsigned long long lr = c->x[30], a1 = c->x[1] & 0xffffffffull;
    AcquireSRWLockExclusive(&call_lock);
    LONG i = 0;
    while (i < n_calls && !(calls[i].pc == pc && calls[i].lr == lr && calls[i].a1 == a1)) i++;
    if (i == n_calls) {
        if (n_calls >= (LONG)(sizeof calls / sizeof calls[0])) { ReleaseSRWLockExclusive(&call_lock); return; }
        calls[n_calls].pc = pc, calls[n_calls].lr = lr, calls[n_calls].a1 = a1, calls[n_calls].last = 0, n_calls++;
    }
    const bool quiet = !calls[i].last || now - calls[i].last >= 1000;
    calls[i].last = now;
    if (quiet && site_lines < 4000) {
        site_lines++;
        hos_log("[OcarinaReborn/UIDIAG] t=%.1fs call %#llx x0=%#llx x1=%#llx x2=%#llx from %#llx", (now - t0) / 1000.0, pc,
                (unsigned long long)c->x[0], a1, (unsigned long long)c->x[2] & 0xffffffffull, lr);
    }
    ReleaseSRWLockExclusive(&call_lock);
}
