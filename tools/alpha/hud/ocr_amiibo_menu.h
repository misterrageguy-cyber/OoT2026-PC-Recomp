// Nonblocking native picker: the render thread never waits for the file dialog.
#pragma once
#include <atomic>
#include <mutex>
#include <string>
#include <thread>
#include <cerrno>
#include "../../host/ocr_amiibo_file.h"
#ifdef _WIN32
#include <commdlg.h>
#endif

namespace ocr_amiibo_menu {
inline std::atomic<bool> busy{false};
inline std::mutex status_lock;
inline std::string status;
inline void say(const char *text) { std::lock_guard<std::mutex> guard(status_lock); status = text; }
inline std::string message() { std::lock_guard<std::mutex> guard(status_lock); return status; }

inline void choose(HWND owner) {
    if (busy.exchange(true)) return;
#ifdef _WIN32
    try { std::thread([owner]() {
        struct Done { ~Done() { busy = false; } } done;
        HMODULE lib = LoadLibraryW(L"comdlg32.dll");
        auto picker = lib ? (BOOL(WINAPI *)(LPOPENFILENAMEW))GetProcAddress(lib, "GetOpenFileNameW") : nullptr;
        if (!picker) { if (lib) FreeLibrary(lib); say("File picker unavailable."); return; }
        wchar_t file[32768] = L"";
        OPENFILENAMEW dialog{};
        dialog.lStructSize = sizeof dialog; dialog.hwndOwner = owner;
        dialog.lpstrFile = file; dialog.nMaxFile = 32768;
        dialog.lpstrFilter = L"amiibo (*.bin)\0*.bin\0\0";
        dialog.lpstrTitle = L"Ocarina Reborn - Select your amiibo .bin";
        dialog.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR | OFN_DONTADDTORECENT;
        BOOL chosen = picker(&dialog);
        FreeLibrary(lib);
        if (!chosen) return;
        FILE *source = _wfopen(file, L"rb");
        if (!source) { say("Could not read that file."); return; }
        uint8_t data[OCR_AMIIBO_MAX + 1];
        size_t n = fread(data, 1, sizeof data, source);
        bool valid = !ferror(source) && ocr_amiibo_valid(data, n);
        fclose(source);
        if (!valid) { say("Invalid raw amiibo .bin. Expected 532, 540 or 572 bytes."); return; }
        char path[4096]; wchar_t target[4096], temp[4096];
        if (!ocr_amiibo_path(path, sizeof path) ||
            !MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, target, 4096)) {
            say("Game folder path is too long or invalid."); return;
        }
        int count = swprintf(temp, 4096, L"%ls.%lu.%llu.tmp", target, GetCurrentProcessId(), GetTickCount64());
        if (count < 0 || count >= 4096) { say("Game folder path is too long."); return; }
        HANDLE out = CreateFileW(temp, GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (out == INVALID_HANDLE_VALUE) { say("Could not save the selected amiibo in the game folder."); return; }
        DWORD written = 0;
        bool ok = WriteFile(out, data, (DWORD)n, &written, nullptr) && written == n && FlushFileBuffers(out);
        CloseHandle(out);
        if (ok) ok = MoveFileExW(temp, target, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
        if (!ok) { DeleteFileW(temp); say("Could not save the selected amiibo. Previous selection kept."); return; }
        say("Ready. Close F1 and use the game's amiibo scan. Reward limits still apply.");
    }).detach(); } catch (...) { busy = false; say("Could not open the amiibo file picker."); }
#else
    (void)owner; busy = false; say("Select an amiibo .bin in the launcher.");
#endif
}
inline void clear() {
    if (busy.exchange(true)) return;
    char path[4096];
    if (!ocr_amiibo_path(path, sizeof path)) say("Game folder path is invalid.");
    else if (remove(path) == 0 || errno == ENOENT) say("Amiibo removed.");
    else say("Could not remove the selected amiibo.");
    busy = false;
}
} // namespace ocr_amiibo_menu
