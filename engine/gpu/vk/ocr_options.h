// (Ocarina Reborn) The graphics rows Ocarina Reborn adds to the F1 menu's Graphics tab, as the renderer reads them: the options
// file beside the game (the menu saves every row there by its name), or an RX_VK_* switch of the same meaning, which wins.
// Each is read once, at its first use: the rows say "Applies after a restart", and the menu asks for one when they change.
#pragma once
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <algorithm>

#include "vk_paths.h"

namespace mkwvk {

/// key's value in the options file, or env_name's when that is set, or otherwise
inline int ocr_option(const char* env_name, const char* key, int otherwise) {
    if (env_name)
        if (const char* e = getenv(env_name)) return atoi(e);
    char exe[MAX_PATH];
    const DWORD n = game_module_path(exe, MAX_PATH);
    std::string ini(exe, n);
    ini = ini.substr(0, ini.find_last_of("\\/") + 1) + "ocarina_reborn_options.ini";
    const size_t klen = strlen(key);
    int v = otherwise;
    if (FILE* f = fopen(ini.c_str(), "r")) {
        char line[128];
        while (fgets(line, sizeof line, f))
            if (!strncmp(line, key, klen) && line[klen] == '=') {
                v = atoi(line + klen + 1);
                break;
            }
        fclose(f);
    }
    return v;
}

/// Anisotropic filtering: the row's choice (Off, 2x, 4x, 8x, 16x) as the most samples; RX_VK_ANISO the number itself
inline int ocr_anisotropy() {
    if (const char* e = getenv("RX_VK_ANISO")) return atoi(e);
    static const int most[] = {0, 2, 4, 8, 16};
    const int i = ocr_option(nullptr, "anisotropic_filtering", 0);
    return most[i < 0 ? 0 : i > 4 ? 4 : i];
}

/// Texture detail: added to every sampler's level-of-detail bias (Standard 0, High -0.5, Ultra -1: the finer mip levels
/// further away)
inline float ocr_texture_bias() {
    static const float bias[] = {0.0f, -0.5f, -1.0f};
    static const float b = [] {
        const int i = ocr_option(nullptr, "texture_detail", 1);   // (default High)
        return bias[i < 0 ? 0 : i > 2 ? 2 : i];
    }();
    return b;
}

/// Texture memory: the most the texture cache may hold, in GB (0: Auto, the renderer's own budget). The renderer keeps it
/// under three quarters of what the driver allows, so a value past the card's memory is clamped there
inline int ocr_texture_budget_gb() {
    static const int gb[] = {0, 2, 4, 6, 8, 12, 16};
    static const int v = [] {
        const int i = ocr_option(nullptr, "texture_memory", 0);
        return gb[i < 0 ? 0 : i > 6 ? 6 : i];
    }();
    return v;
}

/// Shader cache: off when the row says so (or RX_VK_NO_PROGRAM_CACHE is set): every program compiled again each start
inline bool ocr_program_cache_off() {
    static const bool off = getenv("RX_VK_NO_PROGRAM_CACHE") != nullptr || ocr_option(nullptr, "shader_cache", 1) == 0;
    return off;
}

/// Shader threads: the compile workers, auto_n when the row is Auto; never more than the CPU's threads less one
inline unsigned ocr_shader_workers(unsigned auto_n) {
    static const unsigned want[] = {0, 2, 4, 6, 8};
    static const unsigned n = [] {
        const int i = ocr_option(nullptr, "shader_threads", 0);
        return want[i < 0 ? 0 : i > 4 ? 4 : i];
    }();
    if (!n) return auto_n;
    const unsigned cpus = std::thread::hardware_concurrency();
    return std::max(1u, std::min(n, cpus > 1 ? cpus - 1 : 1u));
}

} // namespace mkwvk
