// Ocarina Reborn: opt-in mip trimming, restricted to large, coarse ASTC 2D arrays.
// Reuses the engine's existing skip-aware allocation, upload and view paths.
#pragma once
#include <algorithm>
#include <cstdint>

namespace ocr {
inline uint32_t texture_skip(int mode, bool astc, bool array_2d, bool target, bool sparse,
                             unsigned samples, unsigned block_w, unsigned block_h,
                             uint32_t width, uint32_t height, uint32_t layers, uint32_t levels,
                             uint32_t existing_skip, uint64_t decoded_bytes) {
    if ((mode != 1 && mode != 2) || !astc || !array_2d || target || sparse || samples > 1 ||
        block_w < 6 || block_h < 6 || layers < 2 || levels < 2 || levels > 32 ||
        existing_skip >= levels || decoded_bytes < (32ull << 20)) return existing_skip;
    const uint32_t limit = mode == 1 ? 1024 : 512;
    uint32_t skip = existing_skip;
    // Keep at least one stored level. Never trim uncompressed render targets, UI atlases,
    // cubemaps or the finer ASTC formats used by small/detail textures.
    while (skip + 1 < levels && (std::max(width, height) >> skip) > limit) ++skip;
    return skip;
}
} // namespace ocr
