/* Small emergency report independent of the asynchronous game log and its locks.
   No game memory dump. Module-relative addresses are enough to symbolicate a stack. */
#ifdef _WIN32
#include <signal.h>
#include <stdint.h>
#include <wchar.h>
static HANDLE ocr_crash_file = INVALID_HANDLE_VALUE;
static volatile LONG ocr_crash_reporting;
static void ocr_crash_write(const char* text) {
    DWORD done;
    if (ocr_crash_file != INVALID_HANDLE_VALUE)
        WriteFile(ocr_crash_file, text, (DWORD)strlen(text), &done, NULL);
}
static void ocr_crash_number(const char* label, uint64_t value) {
    char line[160];
    size_t n = 0;
    while (*label && n < 120) line[n++] = *label++;
    line[n++] = '0'; line[n++] = 'x';
    for (int shift = 60; shift >= 0; shift -= 4) line[n++] = "0123456789abcdef"[(value >> shift) & 15];
    line[n++] = '\n'; line[n] = 0;
    ocr_crash_write(line);
}
static void ocr_crash_report(const char* reason, DWORD code, const CONTEXT* source) {
    if (InterlockedExchange(&ocr_crash_reporting, 1)) return;
    ocr_crash_write("FAILURE: "); ocr_crash_write(reason); ocr_crash_write("\n");
    ocr_crash_number("code=", code);
    ocr_crash_number("thread=", GetCurrentThreadId());
    if (source) {
        CONTEXT ctx = *source;
        ocr_crash_write("host stack (module + offset):\n");
        for (int i = 0; i < 24 && ctx.Rip; ++i) {
            HMODULE mod = NULL;
            char name[MAX_PATH] = "unknown";
            if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                    (LPCSTR)ctx.Rip, &mod)) GetModuleFileNameA(mod, name, MAX_PATH);
            name[MAX_PATH - 1] = 0;
            const char* base = strrchr(name, '\\');
            ocr_crash_write(base ? base + 1 : name);
            ocr_crash_number("+", ctx.Rip - (uint64_t)(uintptr_t)mod);
            DWORD64 image = 0;
            PRUNTIME_FUNCTION f = RtlLookupFunctionEntry(ctx.Rip, &image, NULL);
            if (!f) break; // do not probe possibly invalid stack memory for a leaf frame
            void* data;
            DWORD64 frame;
            const DWORD64 old_rip = ctx.Rip;
            RtlVirtualUnwind(UNW_FLAG_NHANDLER, image, ctx.Rip, f, &ctx, &data, &frame, NULL);
            if (ctx.Rip == old_rip) break;
        }
    }
    ocr_crash_write("END FAILURE\n");
    if (ocr_crash_file != INVALID_HANDLE_VALUE) FlushFileBuffers(ocr_crash_file);
    // Keep the first failure: a fault in the old handler must not overwrite it.
}
static void ocr_crash_abort(int sig) {
    CONTEXT ctx;
    RtlCaptureContext(&ctx);
    ocr_crash_report("CRT abort (SIGABRT)", (DWORD)sig, &ctx);
    // Return to abort(), which performs its normal termination. Never resume play.
}
static void ocr_crash_init(void) {
    wchar_t path[MAX_PATH];
    DWORD n = GetEnvironmentVariableW(L"OCR_CRASH_FILE", path, MAX_PATH);
    if (!n || n >= MAX_PATH) {
        n = GetModuleFileNameW(NULL, path, MAX_PATH);
        if (!n || n >= MAX_PATH - 64) return;
        while (n && path[n - 1] != L'\\' && path[n - 1] != L'/') --n;
        _snwprintf(path + n, MAX_PATH - n, L"ocarina_reborn_crash_%lu.txt", GetCurrentProcessId());
    }
    ocr_crash_file = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    ocr_crash_write("Ocarina Reborn emergency diagnostics v1\n");
    ocr_crash_number("pid=", GetCurrentProcessId());
    ocr_crash_write("A FAILURE section is written only when a fault is observed.\n");
    signal(SIGABRT, ocr_crash_abort);
}
#else
static void ocr_crash_init(void) {}
#define ocr_crash_report(reason, code, context) ((void)0)
#endif
