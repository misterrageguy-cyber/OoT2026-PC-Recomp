#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
static SRWLOCK log_lock = SRWLOCK_INIT, log_write_lock = SRWLOCK_INIT;
static LONG log_async = 1;
static DWORD log_writer;
static HANDLE ready, proceed;
static int log_take_locked(char** batch) { (void)batch; return 0; }
static void log_write(char** batch, int n) { (void)batch; (void)n; }
static void log_drain_raw(void) {}
/* ACTUAL_FLUSH */
static DWORD WINAPI writer(void* ignored) {
    (void)ignored;
    AcquireSRWLockExclusive(&log_lock);
    SetEvent(ready);
    WaitForSingleObject(proceed, 2000);
    AcquireSRWLockExclusive(&log_write_lock);
    ReleaseSRWLockExclusive(&log_lock);
    ReleaseSRWLockExclusive(&log_write_lock);
    return 0;
}
static DWORD WINAPI flush(void* ignored) { (void)ignored; log_flush(); return 0; }
int main(void) {
    ready = CreateEvent(NULL, TRUE, FALSE, NULL);
    proceed = CreateEvent(NULL, TRUE, FALSE, NULL);
    HANDLE threads[2];
    threads[0] = CreateThread(NULL, 0, writer, NULL, 0, NULL);
    if (WaitForSingleObject(ready, 2000) != WAIT_OBJECT_0) return 8;
    threads[1] = CreateThread(NULL, 0, flush, NULL, 0, NULL);
    Sleep(100);
    SetEvent(proceed);
    if (WaitForMultipleObjects(2, threads, TRUE, 2000) != WAIT_OBJECT_0) {
        fputs("FAIL: writer and flush deadlocked\n", stderr);
        ExitProcess(9);
    }
    puts("PASS: concurrent log flush and writer completed");
    return 0;
}
