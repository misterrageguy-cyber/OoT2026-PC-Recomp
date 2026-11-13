// Ocarina Reborn: bounded, allocation-free measurements of actual game-frame intervals.
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>

namespace ocr {
struct FrameWindow {
    // More than five seconds at the engine's highest supported 240 FPS cap.
    std::array<double, 2048> samples{};
    size_t size = 0;
    uint64_t frames = 0, over50 = 0, over100 = 0;
    double sum_ms = 0, worst_ms = 0;
    bool menu_seen = false;

    void add(double ms, bool menu_open = false) {
        if (!std::isfinite(ms) || ms <= 0) return;
        if (size < samples.size()) samples[size++] = ms;
        ++frames;
        sum_ms += ms;
        worst_ms = std::max(worst_ms, ms);
        over50 += ms > 50.0;
        over100 += ms > 100.0;
        menu_seen = menu_seen || menu_open;
    }
    bool complete() const { return frames == size; }
    double percentile(double fraction) const {
        if (!size || !complete()) return 0; // Never report truncated samples as a full-window percentile.
        auto ordered = samples;
        const size_t rank = std::max<size_t>(1, (size_t)std::ceil(std::clamp(fraction, 0.0, 1.0) * size));
        std::nth_element(ordered.begin(), ordered.begin() + rank - 1, ordered.begin() + size);
        return ordered[rank - 1];
    }
    void clear() {
        size = 0; frames = over50 = over100 = 0;
        sum_ms = worst_ms = 0; menu_seen = false;
    }
};
} // namespace ocr
