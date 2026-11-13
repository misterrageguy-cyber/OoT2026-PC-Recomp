#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "../hud/ocr_crash.h"
static LONG WINAPI test_crash(EXCEPTION_POINTERS* p) {
    ocr_crash_report("unhandled exception", p->ExceptionRecord->ExceptionCode, p->ContextRecord);
    return EXCEPTION_EXECUTE_HANDLER;
}
int main(int argc, char** argv) {
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    ocr_crash_init();
    SetUnhandledExceptionFilter(test_crash);
    if (argc > 1 && !strcmp(argv[1], "abort")) abort();
    if (argc > 1 && !strcmp(argv[1], "exception")) RaiseException(0xc0000005, 0, 0, NULL);
    return 0;
}
