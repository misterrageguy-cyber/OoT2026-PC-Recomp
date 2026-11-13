#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstdio>

constexpr int VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU = 1;
constexpr uint64_t MB = 1ull << 20;
struct { struct { int deviceType; } props; } dev;
struct { int vram_mb; } opts;
int manual_gb;
int ocr_texture_budget_gb() { return manual_gb; }
bool preset_caps_memory() { return true; }
void logf(const char*, ...) {}
/* HELPER */
uint64_t actual(int gb, bool integrated, uint64_t own, bool known, uint64_t allowed, int preset_mb = 0) {
    manual_gb = gb;
    dev.props.deviceType = integrated ? 1 : 2;
    opts.vram_mb = preset_mb;
    /* SELECTION */
    return budget;
}
void check(const char* name, uint64_t got, uint64_t expected) {
    if (got != expected) {
        fprintf(stderr, "%s: got %llu MB, expected %llu MB\n", name,
                (unsigned long long)(got / MB), (unsigned long long)(expected / MB));
        exit(9);
    }
}
void vram_env(const char* value) {
#ifdef _WIN32
    _putenv_s("RX_VK_VRAM_MB", value);
#else
    if (*value) setenv("RX_VK_VRAM_MB", value, 1); else unsetenv("RX_VK_VRAM_MB");
#endif
}
int main() {
    vram_env("");
    check("tester manual 4 GB on 10.7 GB UMA", actual(4, true, 2048 * MB, true, 4863 * MB), 2048 * MB);
    check("16 GB selection cannot defeat smaller UMA cap", actual(16, true, 1536 * MB, true, 4863 * MB), 1536 * MB);
    check("small explicit cache still wins", actual(2, true, 3584 * MB, true, 8192 * MB), 2048 * MB);
    check("dedicated manual option retained", actual(4, false, 2048 * MB, true, 8192 * MB), 4096 * MB);
    check("dedicated driver clamp retained", actual(4, false, 2048 * MB, true, 4096 * MB), 3072 * MB);
    check("auto retains engine UMA budget", actual(0, true, 2048 * MB, true, 4863 * MB), 2048 * MB);
    check("engine preset retains UMA budget", actual(0, true, 2048 * MB, true, 4863 * MB, 4800), 2048 * MB);
    check("unknown driver still retains UMA budget", actual(4, true, 2048 * MB, false, 0), 2048 * MB);
    vram_env("1500");
    check("explicit developer environment wins", actual(16, true, 1500 * MB, true, 4863 * MB, 4800), 1500 * MB);
    puts("texture budget protections passed");
}
