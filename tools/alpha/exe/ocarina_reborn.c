/* OcarinaReborn.exe: starts the alpha launcher, python\pythonw.exe -I launcher\launcher.py, in this exe's folder.
   No console window. Build: llvm-windres ocarina_reborn.rc -O coff -o rc.o; clang -O2 -municode -mwindows ocarina_reborn.c rc.o */
#include <windows.h>
#include <wchar.h>

#define CHARS (MAX_PATH * 2)

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command_line, int show)
{
    wchar_t folder[CHARS], python[CHARS], command[CHARS * 2 + 64];
    STARTUPINFOW si = { sizeof si };
    PROCESS_INFORMATION pi;
    DWORD n = GetModuleFileNameW(NULL, folder, CHARS);
    (void)instance; (void)previous; (void)command_line; (void)show;
    if (n == 0 || n >= CHARS) return 1;
    while (n > 0 && folder[n - 1] != L'\\') n--;
    folder[n > 0 ? n - 1 : 0] = 0;
    swprintf(python, CHARS, L"%ls\\python\\pythonw.exe", folder);
    swprintf(command, CHARS * 2 + 64, L"\"%ls\" -I \"%ls\\launcher\\launcher.py\"", python, folder);
    if (GetFileAttributesW(python) == INVALID_FILE_ATTRIBUTES ||
        !CreateProcessW(python, command, NULL, NULL, FALSE, 0, NULL, folder, &si, &pi)) {
        MessageBoxW(NULL, L"Ocarina Reborn is incomplete. Please reinstall it.", L"Ocarina Reborn", MB_OK | MB_ICONERROR);
        return 1;
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return 0;
}
