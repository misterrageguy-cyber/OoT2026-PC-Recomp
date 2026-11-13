#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdlib>
#include <mutex>
#include <thread>
#include <vector>
#include <cstdio>
#undef assert
#define assert(condition) do { if (!(condition)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #condition); std::_Exit(9); } } while (0)
using VkBuffer = uint64_t;
using VmaAllocation = void*;
constexpr VkBuffer VK_NULL_HANDLE = 0;
constexpr int VK_BUFFER_USAGE_TRANSFER_SRC_BIT = 1;
struct MEMORYSTATUSEX { unsigned dwLength; uint64_t ullAvailPhys, ullAvailPageFile; };
static std::atomic<uint64_t> available{8ull << 30};
int GlobalMemoryStatusEx(MEMORYSTATUSEX* m) { m->ullAvailPhys = m->ullAvailPageFile = available; return 1; }
bool env_on(const char*) { return false; }
void logf(const char*, ...) {}
struct FreeBuf { VkBuffer buffer; VmaAllocation alloc; void* map; uint64_t size; };
std::vector<FreeBuf> cap_free;
std::mutex cap_free_mu;
uint64_t cap_free_bytes = 0;
std::atomic<bool> cap_shutting_down{false};
std::atomic<bool> warming{true}, allocating{false};
std::atomic<int> delay_ms{2}, made{0};
uint64_t cap_spare_max() { return 512ull << 20; }
bool cap_prewarm_on() { return warming; }
void destroy_buffer(VkBuffer, VmaAllocation) {}
bool create_buffer_cached(uint64_t, int, VkBuffer& b, VmaAllocation& a, void** m, bool) {
    allocating = true;
    std::this_thread::sleep_for(std::chrono::milliseconds(delay_ms.load()));
    b = ++made; a = *m = reinterpret_cast<void*>(uintptr_t(b));
    allocating = false;
    return true;
}
void cap_buf_free(VkBuffer b, VmaAllocation a, void* m, uint64_t n, bool = false) {
    std::lock_guard lk(cap_free_mu);
    if (cap_free_bytes + n <= cap_spare_max() && cap_free.size() < 12) {
        cap_free.push_back({b, a, m, n}); cap_free_bytes += n;
    }
}
uint64_t cap_buf_size(uint64_t n) { uint64_t size = 2ull << 20; while (size < n) size *= 2; return size; }
#include "../hud/ocr_capture_pool.inc"
static void idle() {
    for (int i = 0; i < 5000 && cap_prewarm_busy; ++i) std::this_thread::sleep_for(std::chrono::milliseconds(1));
    assert(!cap_prewarm_busy);
}
int main() {
    VkBuffer b{}; VmaAllocation a{}; void* map{}; uint64_t size{};
    assert(cap_buf_get(1ull << 20, b, a, map, size));
    idle();
    // All queued initial classes, including the formerly skipped fourth class.
    assert(cap_free.size() == 4 && cap_free_bytes == (416ull << 20));
    const int before = made;
    assert(cap_buf_get(1ull << 20, b, a, map, size));
    assert(size == (2ull << 20) && cap_free_bytes == (416ull << 20));
    assert(cap_buf_get(30ull << 20, b, a, map, size));
    assert(size == (32ull << 20));
    idle();
    assert(cap_free_bytes == (416ull << 20) && made > before); // refill occurred
    available = 512ull << 20;
    assert(cap_buf_get(30ull << 20, b, a, map, size));
    idle();
    assert(cap_free_bytes == (384ull << 20)); // low-memory safety: no speculative refill
    warming = false;
    delay_ms = 80;
    std::thread request([&] { assert(cap_buf_get(4ull << 20, b, a, map, size)); });
    while (!allocating) std::this_thread::yield();
    assert(cap_free_mu.try_lock()); // a driver allocation cannot block pool returns
    cap_free_mu.unlock();
    request.join();
    puts("capture pool: queued fourth class, refill, size matching, memory guard and unlocked allocation passed");
}
