/* Ocarina Reborn: private clothing overlay, prepared before the game reads RomFS.
 * Original does no work and never changes the player's files. The offline helper
 * publishes a complete cache atomically; an error leaves the ordinary mod stack.
 * Settings are the same keys saved by the launcher and the F1 Gameplay rows.
 */
#include "hos.h"
#include "hos_paths.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#ifdef _WIN32
#include <windows.h>

int hos_mods_export_tunic_sources(const char *path);
int hos_mods_add_tunic(const char *path);

void ocr_tunic_init(const char *romfs) {
    char root[1024], ini[1200], cache[1200], map[1300], ready[1300], log[1300];
    if (!hos_game_path_a(root, sizeof root)) return;
    char *end = strrchr(root, '\\');
    if (!end) end = strrchr(root, '/');
    if (!end) return;
    *end = 0;
    snprintf(ini, sizeof ini, "%s\\ocarina_reborn_options.ini", root);
    FILE *f = fopen(ini, "r");
    int on = 0, rgb[3] = {80, 160, 75};
    if (!f) return;
    char line[512], key[80], value[80];
    while (fgets(line, sizeof line, f)) {
        if (sscanf(line, "%79[^=]=%79s", key, value) != 2) continue;
        char *tail;
        long n = strtol(value, &tail, 10);
        if (tail == value || *tail) continue;
        if (!strcmp(key, "custom_tunic_color")) on = n > 0;
        for (int i = 0; i < 3; ++i)
            if (!strcmp(key, i == 0 ? "tunic_red" : i == 1 ? "tunic_green" : "tunic_blue"))
                rgb[i] = n < 0 ? 0 : n > 255 ? 255 : (int)n;
    }
    fclose(f);
    if (!on) { hos_log("tunic: Original (no overlay)"); return; }
    snprintf(cache, sizeof cache, "%s\\.ocarina_reborn_tunic_cache", root);
    if (!CreateDirectoryA(cache, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) {
        hos_log("tunic: cache not writable; original clothing kept"); return;
    }
    const unsigned long pid = GetCurrentProcessId();
    snprintf(map, sizeof map, "%s\\mods-%lu.tsv", cache, pid);
    snprintf(ready, sizeof ready, "%s\\ready-%lu.txt", cache, pid);
    snprintf(log, sizeof log, "%s\\helper-%lu.log", cache, pid);
    if (!hos_mods_export_tunic_sources(map)) {
        hos_log("tunic: could not record mod sources; original clothing kept"); return;
    }
    DeleteFileA(ready);
    char python[1400], command[8192];
    snprintf(python, sizeof python, "%s\\.ocarina_reborn_tunic_tools\\python\\python.exe", root);
    int count = snprintf(command, sizeof command,
        "\"%s\" -I \"%s\\.ocarina_reborn_tunic_tools\\tunic_assets.py\" --romfs \"%s\" "
        "--cache \"%s\" --mods-map \"%s\" --ready \"%s\" --rgb %d %d %d",
        python, root, romfs ? romfs : "romfs", cache, map, ready, rgb[0], rgb[1], rgb[2]);
    wchar_t wpython[1400], wcommand[8192];
    if (count < 0 || count >= sizeof command ||
        !MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, python, -1, wpython, 1400) ||
        !MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, command, -1, wcommand, 8192)) goto done;
    SECURITY_ATTRIBUTES sa = {sizeof sa, NULL, TRUE};
    HANDLE output = CreateFileA(log, GENERIC_WRITE, FILE_SHARE_READ, &sa, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    HANDLE input = CreateFileA("NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, NULL);
    HANDLE job = CreateJobObjectW(NULL, NULL);
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    STARTUPINFOW si = {0};
    si.cb = sizeof si; si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdInput = input; si.hStdOutput = si.hStdError = output;
    PROCESS_INFORMATION pi = {0};
    DWORD result = 1;
    if (output != INVALID_HANDLE_VALUE && input != INVALID_HANDLE_VALUE && job &&
        SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof limits) &&
        CreateProcessW(wpython, wcommand, NULL, NULL, TRUE, CREATE_NO_WINDOW | CREATE_SUSPENDED,
                       NULL, NULL, &si, &pi)) {
        if (AssignProcessToJobObject(job, pi.hProcess)) {
            hos_log("tunic: preparing #%02X%02X%02X (offline)", rgb[0], rgb[1], rgb[2]);
            ResumeThread(pi.hThread);
            if (WaitForSingleObject(pi.hProcess, 120000) == WAIT_OBJECT_0)
                GetExitCodeProcess(pi.hProcess, &result);
        } else TerminateProcess(pi.hProcess, 1);
        CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    }
    if (job) CloseHandle(job);
    if (output != INVALID_HANDLE_VALUE) CloseHandle(output);
    if (input != INVALID_HANDLE_VALUE) CloseHandle(input);
    if (result == 0 && (f = fopen(ready, "r")) != NULL) {
        char token[66] = {0}, overlay[1400];
        size_t n = fread(token, 1, sizeof token - 1, f); fclose(f);
        int valid = n == 32;
        for (size_t i = 0; i < n; i++) if (!isxdigit((unsigned char)token[i])) valid = 0;
        if (valid) {
            snprintf(overlay, sizeof overlay, "%s\\%s", cache, token);
            hos_log("tunic: #%02X%02X%02X ready, %d private RomFS entries", rgb[0], rgb[1], rgb[2],
                    hos_mods_add_tunic(overlay));
        }
    } else hos_log("tunic: helper failed or timed out; original clothing kept; see %s", log);
done:
    DeleteFileA(map); DeleteFileA(ready);
}
#else
void ocr_tunic_init(const char *romfs) { (void)romfs; }
#endif
