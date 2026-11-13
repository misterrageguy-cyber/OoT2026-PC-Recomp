#include "../hud/ocr_perf_metrics.h"
#include "../hud/ocr_texture_policy.h"
#include <cassert>
#include <limits>
#include <iostream>

int main() {
    ocr::FrameWindow f;
    assert(f.percentile(.99) == 0);
    for (int i = 1; i <= 100; ++i) f.add(i);
    assert(f.percentile(.95) == 95 && f.percentile(.99) == 99);
    assert(f.frames == 100 && f.over50 == 50 && f.over100 == 0 && f.worst_ms == 100);
    f.add(125, true);
    assert(f.over100 == 1 && f.menu_seen);
    f.add(0); f.add(-1); f.add(std::numeric_limits<double>::infinity());
    assert(f.frames == 101);
    f.clear();
    assert(!f.frames && !f.menu_seen && f.percentile(.99) == 0);
    for (int i = 0; i < 2049; ++i) f.add(16.0);
    assert(!f.complete() && f.percentile(.99) == 0 && f.frames == 2049);
    using ocr::texture_skip;
    const uint64_t bytes = 600ull << 20;
    assert(texture_skip(0, true, true, false, false, 1, 8, 8, 1365, 1365, 90, 10, 0, bytes) == 0);
    assert(texture_skip(1, true, true, false, false, 1, 8, 8, 1365, 1365, 90, 10, 0, bytes) == 1);
    assert(texture_skip(2, true, true, false, false, 1, 8, 8, 1365, 1365, 90, 10, 0, bytes) == 2);
    assert(texture_skip(2, true, true, false, false, 1, 8, 8, 1365, 1365, 90, 10, 3, bytes) == 3);
    assert(texture_skip(2, true, true, true, false, 1, 8, 8, 1365, 1365, 90, 10, 0, bytes) == 0);
    assert(texture_skip(2, false, true, false, false, 1, 8, 8, 1365, 1365, 90, 10, 0, bytes) == 0);
    assert(texture_skip(2, true, false, false, false, 1, 8, 8, 1365, 1365, 90, 10, 0, bytes) == 0);
    assert(texture_skip(2, true, true, false, true, 1, 8, 8, 1365, 1365, 90, 10, 0, bytes) == 0);
    assert(texture_skip(2, true, true, false, false, 4, 8, 8, 1365, 1365, 90, 10, 0, bytes) == 0);
    assert(texture_skip(2, true, true, false, false, 1, 4, 4, 1365, 1365, 90, 10, 0, bytes) == 0);
    assert(texture_skip(2, true, true, false, false, 1, 8, 8, 1365, 1365, 1, 10, 0, bytes) == 0);
    assert(texture_skip(2, true, true, false, false, 1, 8, 8, 1365, 1365, 90, 1, 0, bytes) == 0);
    assert(texture_skip(2, true, true, false, false, 1, 8, 8, 1365, 1365, 90, 10, 0, 4ull << 20) == 0);
    std::cout << "PASS: frame percentiles, hitches, overflow and texture-policy exclusions\n";
}
