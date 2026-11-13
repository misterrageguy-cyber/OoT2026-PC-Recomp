// Ocarina Reborn: game-frame timings, sampled before frame interpolation, in five-second windows.
// CPU is renderer submission time, not total CPU time. GPU queries may complete a few frames later.
struct OcrPerfCounters {
    int64_t draws = 0, skipped = 0, dispatches = 0, pipelines = 0, translated = 0, failed = 0;
    int64_t uploads = 0, upload_bytes = 0, not_ready = 0, waits = 0, gpu = 0, cpu = 0;
    double wait_ms = 0;
};
OcrPerfCounters ocr_perf_counters() {
    OcrPerfCounters c;
    int64_t astc = 0;
    draw_stats(&c.draws, &c.skipped, &c.dispatches, &c.pipelines);
    shader_stats(&c.translated, &c.failed);
    texture_stats(&c.uploads, &astc, &c.upload_bytes);
    draw_stats3(&c.not_ready, &c.waits, &c.wait_ms);
    c.gpu = st_gpu_ns; c.cpu = prof_ns[PROF_SUBMIT];
    return c;
}
void ocr_perf_tick() {
    using clk = std::chrono::steady_clock;
    static auto last = clk::now();
    static auto begin = last;
    static bool primed = false;
    static ocr::FrameWindow window;
    static OcrPerfCounters before;
    const auto now = clk::now();
    const double ms = std::chrono::duration<double, std::milli>(now - last).count();
    last = now;
    if (!primed) {
        // Exclude initialization and shader precompile from the first measurement.
        primed = true; begin = now; before = ocr_perf_counters();
        return;
    }
    window.add(ms, menu_is_open());
    const double seconds = std::chrono::duration<double>(now - begin).count();
    if (seconds < 5.0 || !window.frames) return;
    const auto after = ocr_perf_counters();
    const double f = 1.0 / window.frames;
    const double cpu = std::max<int64_t>(0, after.cpu - before.cpu) * f / 1e6;
    const double gpu = std::max<int64_t>(0, after.gpu - before.gpu) * f / 1e6;
    uint64_t used = 0, budget = 0;
    const bool vram = vram_usage(&used, &budget);
    ::mkwvk::ocr_ov_cpu.store((float)cpu, std::memory_order_relaxed);
    ::mkwvk::ocr_ov_gpu.store((float)gpu, std::memory_order_relaxed);
    ::mkwvk::ocr_ov_vram.store(vram ? (float)(used / 1073741824.0) : 0, std::memory_order_relaxed);
    ::mkwvk::ocr_ov_budget.store(vram ? (float)(budget / 1073741824.0) : 0, std::memory_order_relaxed);
    // Keep the original prefix readable by older launchers. The versioned tail adds
    // exact nearest-rank window percentiles, uncapped hitch counts and sampling context.
    logf("[perf] fps %.1f | frame %.1f ms avg, %.1f ms worst | CPU (renderer) %.1f ms | GPU %.1f ms | VRAM %s%.2f / %.2f GB | "
         "textures %zu (%llu MB) | draws %.0f (%.1f skipped, %.1f not ready) | dispatches %.0f | uploads %.2f MB | "
         "new pipelines %lld, waits %.2f (%.1f ms) | programs translated %lld, failed %lld (all: %lld) | "
         "stats2 seconds %.3f frames %llu p95 %.2f p99 %.2f over50 %llu over100 %llu menu %d complete %d fg %d",
         window.frames / seconds, window.sum_ms * f, window.worst_ms, cpu, gpu,
         vram ? "" : "? ", used / 1073741824.0, budget / 1073741824.0,
         texture_count(), (unsigned long long)(texture_bytes() >> 20),
         (after.draws - before.draws) * f, (after.skipped - before.skipped) * f,
         (after.not_ready - before.not_ready) * f, (after.dispatches - before.dispatches) * f,
         (after.upload_bytes - before.upload_bytes) * f / 1048576.0,
         (long long)(after.pipelines - before.pipelines), (after.waits - before.waits) * f,
         (after.wait_ms - before.wait_ms) * f, (long long)(after.translated - before.translated),
         (long long)(after.failed - before.failed), (long long)after.failed,
         seconds, (unsigned long long)window.frames, window.percentile(.95), window.percentile(.99),
         (unsigned long long)window.over50, (unsigned long long)window.over100,
         window.menu_seen ? 1 : 0, window.complete() ? 1 : 0, opts.framegen);
    if (window.over100)
        logf("[Performance Warning] %llu game frames over 100 ms in %.1f s (worst %.1f ms)",
             (unsigned long long)window.over100, seconds, window.worst_ms);
    before = after; begin = now; window.clear();
}

