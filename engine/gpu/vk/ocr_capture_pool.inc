// Ocarina Reborn: bounded, serial refill of scene-loading capture buffers.
// Included inside vk_memory.cpp's namespace, after cap_prewarm_on().
std::atomic<int> cap_prewarm_busy{0};
uint32_t cap_prewarm_pending = 0; // cap_free_mu, one bit per size class
constexpr uint64_t ocr_cap_classes[] = {32, 64, 128, 192, 256};
void cap_exit_note() {
    std::lock_guard lk(cap_free_mu);
    cap_shutting_down = true;
    cap_prewarm_pending = 0;
}
int cap_prewarm_index(uint64_t size) {
    for (int i = 0; i < 5; ++i) if (size <= (ocr_cap_classes[i] << 20)) return i;
    return -1;
}
bool ocr_cap_room(uint64_t bytes) {
    MEMORYSTATUSEX ms{};
    ms.dwLength = sizeof(ms);
    // Speculative allocations must leave headroom for the game, OS and RAM guard.
    if (!GlobalMemoryStatusEx(&ms)) return false;
    const char* e = getenv("OCR_RAM_RESERVE_MB");
    const uint64_t reserve = (uint64_t)std::max(1024, e ? atoi(e) : 1024) << 20;
    return ms.ullAvailPhys > reserve + bytes && ms.ullAvailPageFile > reserve + bytes;
}
void ocr_cap_worker() {
    for (;;) {
        uint64_t bytes = 0;
        {
            std::lock_guard lk(cap_free_mu);
            while (cap_prewarm_pending && !cap_shutting_down.load()) {
                const int index = __builtin_ctz(cap_prewarm_pending);
                cap_prewarm_pending &= ~(1u << index);
                const uint64_t want = ocr_cap_classes[index] << 20;
                bool have = false;
                for (const auto& f : cap_free) if (f.size == want) have = true;
                // Rejected work is not requeued in a busy loop. A later capture may retry.
                if (!have && cap_free.size() < 12 && cap_free_bytes + want <= cap_spare_max() && ocr_cap_room(want)) {
                    bytes = want;
                    break;
                }
            }
            if (!bytes) { cap_prewarm_busy = 0; return; }
        }
        VkBuffer b = VK_NULL_HANDLE;
        VmaAllocation a = nullptr;
        void* m = nullptr;
        const auto start = std::chrono::steady_clock::now();
        // No pool lock while the driver allocates/commits memory.
        const bool ok = create_buffer_cached(bytes, VK_BUFFER_USAGE_TRANSFER_SRC_BIT, b, a, &m, !env_on("RX_VK_CAP_BLOCKS"));
        if (cap_shutting_down.load()) return; // device/list may already be going; process owns the remaining allocation
        if (ok && m) {
            static std::atomic<int> told{0};
            if (told++ < 20) logf("[OcarinaReborn/LOAD] capture spare %llu MB ready in %.1f ms (background refill)",
                (unsigned long long)(bytes >> 20), std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count());
            cap_buf_free(b, a, m, bytes, true);
        } else if (b) destroy_buffer(b, a);
    }
}
// Called with cap_free_mu held. Requests survive the worker's concurrency limit.
void cap_prewarm_class(uint64_t size) {
    if (!cap_prewarm_on() || cap_shutting_down.load() || size < (32ull << 20)) return;
    const int index = cap_prewarm_index(size);
    if (index < 0 || (ocr_cap_classes[index] << 20) > cap_spare_max()) return;
    cap_prewarm_pending |= 1u << index;
    if (cap_prewarm_busy.load()) return;
    static const bool exit_hook = std::atexit(cap_exit_note) == 0;
    (void)exit_hook;
    cap_prewarm_busy = 1;
    try { std::thread(ocr_cap_worker).detach(); }
    catch (...) { cap_prewarm_busy = 0; cap_prewarm_pending = 0; }
}
bool cap_buf_get(uint64_t need, VkBuffer& buffer, VmaAllocation& alloc, void*& map, uint64_t& size) {
    const uint64_t target = cap_buf_size(need);
    std::unique_lock lk(cap_free_mu);
    static bool first = true;
    if (first) {
        first = false;
        for (uint64_t mb : {32, 64, 128, 192}) cap_prewarm_class(mb << 20);
    }
    size_t best = cap_free.size();
    for (size_t i = 0; i < cap_free.size(); ++i)
        // A 2 MB frame must not eat a 128 MB spare prepared for a scene load.
        if (cap_free[i].size >= need && cap_free[i].size <= target &&
            (best == cap_free.size() || cap_free[i].size < cap_free[best].size)) best = i;
    if (best < cap_free.size()) {
        buffer = cap_free[best].buffer; alloc = cap_free[best].alloc;
        map = cap_free[best].map; size = cap_free[best].size;
        cap_free_bytes -= size;
        cap_free.erase(cap_free.begin() + (ptrdiff_t)best);
        cap_prewarm_class(target);
        return map != nullptr;
    }
    cap_prewarm_class(target);
    lk.unlock();
    size = target;
    map = nullptr;
    const auto start = std::chrono::steady_clock::now();
    const bool ok = create_buffer_cached(size, VK_BUFFER_USAGE_TRANSFER_SRC_BIT, buffer, alloc, &map,
                                         size >= (16ull << 20) && !env_on("RX_VK_CAP_BLOCKS")) && map;
    const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();
    if (ms >= 10.0) logf("[OcarinaReborn/LOAD] capture pool miss: %llu MB, %.1f ms on submitting thread",
                         (unsigned long long)(size >> 20), ms);
    return ok;
}
