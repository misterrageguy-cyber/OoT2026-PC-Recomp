#define OCR_AMIIBO_TEST 1
#include "ocr_amiibo.c"

static uint64_t call(void (*fn)(Ctx *), uint64_t a, uint64_t b, uint64_t d) {
    Ctx ctx = {0}; ctx.x[0] = a; ctx.x[1] = b; ctx.x[2] = d; fn(&ctx); return ctx.x[0];
}
#define CALL(name,a,b,d) call(imp__ZN2nn3nfp##name,a,b,d)
static uint8_t tag[540];
static void write_tag(void) {
    FILE *f = fopen(nfp_path, "wb"); assert(f);
    assert(fwrite(tag, 1, sizeof tag, f) == sizeof tag); assert(fclose(f) == 0);
}
int main(void) {
    const uint8_t head[] = {4,0x11,0x22,0xbf,0x33,0x44,0x55,0x66,0x44,0x48,0x0f,0xe0,0xf1,0x10,0xff,0xee};
    const uint8_t model[] = {0xf1,0xf2,3,4,0xf5,0xf6,7,2};
    memcpy(tag, head, sizeof head); memcpy(tag + 0x54, model, sizeof model);
    assert(ocr_amiibo_valid(tag, sizeof tag));
    for (size_t n = 0; n < 532; ++n) assert(!ocr_amiibo_valid(tag, n));
    assert(!ocr_amiibo_valid(tag, 539));
    assert(CALL(14GetDeviceStateERKNS0_12DeviceHandleE, 64, 0, 0) == NFP_UNAVAILABLE);
    assert(CALL(10InitializeEv, 0, 0, 0) == 0);
    remove(nfp_path);
    assert(CALL(11ListDevicesEPNS0_12DeviceHandleEPii, 64, 80, 1) == 0);
    assert(*(uint64_t *)(guest + 64) == 1 && *(int *)(guest + 80) == 1);
    assert(CALL(11ListDevicesEPNS0_12DeviceHandleEPii, 0, 80, 0) == 0 && *(int *)(guest+80) == 0);
    assert(CALL(11ListDevicesEPNS0_12DeviceHandleEPii, 64, 80, (uint64_t)-1) != 0);
    assert(CALL(19AttachActivateEventEPNS_2os15SystemEventTypeERKNS0_12DeviceHandleE, 512, 64, 0) == 0);
    assert(CALL(21AttachDeactivateEventEPNS_2os15SystemEventTypeERKNS0_12DeviceHandleE, 768, 64, 0) == 0);
    assert(CALL(14StartDetectionERKNS0_12DeviceHandleE, 64, 0, 0) == 0);
    assert(CALL(14GetDeviceStateERKNS0_12DeviceHandleE, 64, 0, 0) == NFP_SEARCH);
    write_tag(); nfp_poll();
    assert(nfp_state == NFP_FOUND && events[512] == 1);
    assert(CALL(14StartDetectionERKNS0_12DeviceHandleE, 64, 0, 0) != 0);
    assert(CALL(10GetTagInfoEPNS0_7TagInfoERKNS0_12DeviceHandleE, 128, 64, 0) == 0);
    assert(memcmp(guest + 128, head, 8) == 0 && guest[138] == 8);
    assert(guest[160] == 1 && guest[164] == 2);
    assert(CALL(12GetModelInfoEPNS0_9ModelInfoERKNS0_12DeviceHandleE, 256, 64, 0) != 0);
    assert(CALL(5MountERKNS0_12DeviceHandleENS0_9ModelTypeENS0_11MountTargetE, 64, 0, 1) == 0);
    memset(guest + 256, 0xcc, 65);
    assert(CALL(12GetModelInfoEPNS0_9ModelInfoERKNS0_12DeviceHandleE, 256, 64, 0) == 0);
    const uint8_t sdk_model[] = {0xf2,0xf1,3,7,0xf6,0xf5,4};
    assert(memcmp(guest+256, sdk_model, 7) == 0);
    for (int i = 7; i < 64; ++i) assert(guest[256+i] == 0);
    assert(guest[320] == 0xcc); /* exact buffer size */
    assert(CALL(12GetModelInfoEPNS0_9ModelInfoERKNS0_12DeviceHandleE, 4090, 64, 0) != 0);
    assert(CALL(18SetApplicationAreaERKNS0_12DeviceHandleEPKvm, 64, 128, 8) != 0);
    assert(CALL(5FlushERKNS0_12DeviceHandleE, 64, 0, 0) != 0);
    uint8_t check[572]; size_t size = 0;
    assert(ocr_amiibo_read(nfp_path, check, &size) && size == sizeof tag && memcmp(tag, check, size) == 0);
    /* A different selection does not mutate a mounted tag under the game's feet. */
    tag[0x56] = 9; write_tag(); nfp_poll();
    assert(nfp_state == NFP_REMOVED && events[768] == 1);
    assert(CALL(12GetModelInfoEPNS0_9ModelInfoERKNS0_12DeviceHandleE, 256, 64, 0) != 0);
    assert(CALL(13StopDetectionERKNS0_12DeviceHandleE, 64, 0, 0) == 0);
    assert(CALL(14StartDetectionERKNS0_12DeviceHandleE, 64, 0, 0) == 0 && nfp_state == NFP_FOUND);
    assert(events[512] == 2);
    remove(nfp_path); nfp_poll(); assert(nfp_state == NFP_REMOVED && events[768] == 2);
    assert(CALL(8FinalizeEv, 0, 0, 0) == 0);
    assert(CALL(14GetDeviceStateERKNS0_12DeviceHandleE, 64, 0, 0) == NFP_UNAVAILABLE);
    assert(CALL(10InitializeEv, 0, 0, 0) == 0 && nfp_state == NFP_IDLE);
    assert(!nfp_activate && !nfp_deactivate);
    puts("amiibo lifecycle, tag replacement, buffers and read-only checks passed");
    return 0;
}
