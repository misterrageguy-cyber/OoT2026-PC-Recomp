/* Ocarina Reborn: one virtual read-only amiibo reader, selected in Launcher/F1.
   Public ABI/state layout: switchbrew/libnx nx/include/switch/services/nfc.h.
   The original UID stays stable; the game keeps its own reward/cooldown rules.
   Encrypted application/owner data is never reported as successfully read. */
#include "hos.h"
#include "ocr_amiibo_file.h"
#include <windows.h>

enum { NFP_IDLE, NFP_SEARCH, NFP_FOUND, NFP_REMOVED, NFP_MOUNTED, NFP_UNAVAILABLE };
enum { NFP_OK = 0, NFP_BAD_ARGUMENT = (65 << 9) | 115,
       NFP_BAD_STATE = (73 << 9) | 115, NFP_NO_APP = (128 << 9) | 115,
       NFP_NOT_REGISTERED = (120 << 9) | 115 };
static SRWLOCK nfp_lock = SRWLOCK_INIT;
static int nfp_initialized, nfp_state = NFP_UNAVAILABLE, nfp_thread_started;
static uint64_t nfp_activate, nfp_deactivate;
static uint8_t nfp_tag[OCR_AMIIBO_MAX];
static size_t nfp_tag_size;
static char nfp_path[4096];

static void *nfp_buffer(uint64_t a, size_t n) {
    return a && hos_mem_region(a, n) ? hos_guest_range(a, n) : NULL;
}
static int nfp_device(uint64_t a) {
    uint64_t *p = nfp_buffer(a, 8);
    return nfp_initialized && p && *p == 1;
}
static int nfp_tag_ready(void) { return nfp_state == NFP_FOUND || nfp_state == NFP_MOUNTED; }
/* Caller holds nfp_lock. No user tag paths or serial numbers go into logs. */
static void nfp_poll(void) {
    if (!nfp_initialized || (nfp_state != NFP_SEARCH && !nfp_tag_ready())) return;
    uint8_t data[OCR_AMIIBO_MAX];
    size_t n = 0;
    int found = ocr_amiibo_read(nfp_path, data, &n);
    if (nfp_state == NFP_SEARCH && found) {
        memcpy(nfp_tag, data, n); nfp_tag_size = n; nfp_state = NFP_FOUND;
        if (nfp_activate) hos_system_event_signal(nfp_activate);
        hos_log("amiibo: selected tag detected (read-only)");
    } else if (nfp_tag_ready() && (!found || n != nfp_tag_size || memcmp(data, nfp_tag, n))) {
        nfp_state = NFP_REMOVED;
        if (nfp_deactivate) hos_system_event_signal(nfp_deactivate);
        hos_log("amiibo: tag removed or replaced; waiting for the game's next scan");
    }
}
#ifndef OCR_AMIIBO_TEST
static DWORD WINAPI nfp_worker(void *unused) {
    (void)unused;
    for (;;) {
        Sleep(100);
        AcquireSRWLockExclusive(&nfp_lock);
        nfp_poll();
        ReleaseSRWLockExclusive(&nfp_lock);
    }
    return 0;
}
#endif
#define NFP_LOCK() AcquireSRWLockExclusive(&nfp_lock)
#define NFP_RETURN(v) do { uint64_t result_ = (v); ReleaseSRWLockExclusive(&nfp_lock); RET(result_); return; } while (0)

HLE(_ZN2nn3nfp10InitializeEv) {
    NFP_LOCK();
    if (!ocr_amiibo_path(nfp_path, sizeof nfp_path)) NFP_RETURN(NFP_BAD_ARGUMENT);
    if (!nfp_thread_started) {
#ifndef OCR_AMIIBO_TEST
        HANDLE worker = CreateThread(NULL, 0, nfp_worker, NULL, 0, NULL);
        if (!worker) NFP_RETURN(NFP_BAD_STATE);
        CloseHandle(worker);
#endif
        nfp_thread_started = 1;
    }
    if (!nfp_initialized) {
        nfp_initialized = 1; nfp_state = NFP_IDLE;
        hos_log("amiibo: virtual reader ready; select your .bin in Launcher or F1 > Gameplay");
    }
    NFP_RETURN(NFP_OK);
}
HLE(_ZN2nn3nfp8FinalizeEv) {
    NFP_LOCK();
    nfp_initialized = 0; nfp_state = NFP_UNAVAILABLE;
    nfp_activate = nfp_deactivate = 0; nfp_tag_size = 0;
    memset(nfp_tag, 0, sizeof nfp_tag);
    NFP_RETURN(NFP_OK);
}
HLE(_ZN2nn3nfp8GetStateEv) { NFP_LOCK(); NFP_RETURN(nfp_initialized); }
HLE(_ZN2nn3nfp11ListDevicesEPNS0_12DeviceHandleEPii) {
    NFP_LOCK();
    int32_t *count = nfp_buffer(ARG(1), 4);
    int32_t capacity = (int32_t)ARG(2);
    uint64_t *handles = capacity > 0 ? nfp_buffer(ARG(0), 8) : NULL;
    if (!count || capacity < 0 || (capacity > 0 && !handles)) NFP_RETURN(NFP_BAD_ARGUMENT);
    *count = 0;
    if (!nfp_initialized) NFP_RETURN(NFP_BAD_STATE);
    if (capacity > 0) { *count = 1; *handles = 1; }
    NFP_RETURN(NFP_OK);
}
HLE(_ZN2nn3nfp14GetDeviceStateERKNS0_12DeviceHandleE) {
    NFP_LOCK();
    if (!nfp_device(ARG(0))) NFP_RETURN(NFP_UNAVAILABLE);
    nfp_poll();
    NFP_RETURN(nfp_state);
}
HLE(_ZN2nn3nfp9GetNpadIdEPjRKNS0_12DeviceHandleE) {
    NFP_LOCK();
    uint32_t *out = nfp_buffer(ARG(0), 4);
    if (!out || !nfp_device(ARG(1))) NFP_RETURN(NFP_BAD_ARGUMENT);
    *out = 0; /* player one, also for keyboard input */
    NFP_RETURN(NFP_OK);
}
HLE(_ZN2nn3nfp14StartDetectionERKNS0_12DeviceHandleE) {
    NFP_LOCK();
    if (!nfp_device(ARG(0))) NFP_RETURN(NFP_BAD_ARGUMENT);
    if (nfp_state != NFP_IDLE && nfp_state != NFP_REMOVED) NFP_RETURN(NFP_BAD_STATE);
    nfp_state = NFP_SEARCH; nfp_tag_size = 0;
    nfp_poll();
    NFP_RETURN(NFP_OK);
}
HLE(_ZN2nn3nfp13StopDetectionERKNS0_12DeviceHandleE) {
    NFP_LOCK();
    if (!nfp_device(ARG(0))) NFP_RETURN(NFP_BAD_ARGUMENT);
    if (nfp_tag_ready() && nfp_deactivate) hos_system_event_signal(nfp_deactivate);
    nfp_state = NFP_IDLE; nfp_tag_size = 0;
    NFP_RETURN(NFP_OK);
}
HLE(_ZN2nn3nfp5MountERKNS0_12DeviceHandleENS0_9ModelTypeENS0_11MountTargetE) {
    NFP_LOCK();
    if (!nfp_device(ARG(0)) || ARG(1) != 0 || ARG(2) < 1 || ARG(2) > 3) NFP_RETURN(NFP_BAD_ARGUMENT);
    if (nfp_state != NFP_FOUND) NFP_RETURN(NFP_BAD_STATE);
    nfp_state = NFP_MOUNTED;
    NFP_RETURN(NFP_OK);
}
HLE(_ZN2nn3nfp7UnmountERKNS0_12DeviceHandleE) {
    NFP_LOCK();
    if (!nfp_device(ARG(0)) || nfp_state != NFP_MOUNTED) NFP_RETURN(NFP_BAD_STATE);
    nfp_state = NFP_FOUND;
    NFP_RETURN(NFP_OK);
}
HLE(_ZN2nn3nfp10GetTagInfoEPNS0_7TagInfoERKNS0_12DeviceHandleE) {
    NFP_LOCK();
    uint8_t *out = nfp_buffer(ARG(0), 0x58);
    if (!out || !nfp_device(ARG(1))) NFP_RETURN(NFP_BAD_ARGUMENT);
    if (!nfp_tag_ready()) NFP_RETURN(NFP_BAD_STATE);
    memset(out, 0, 0x58);
    /* SDK tag identity includes the first cascade's BCC byte (8 bytes). */
    memcpy(out, nfp_tag, 8); out[10] = 8;
    out[0x20] = 1; out[0x24] = 2; /* Type A / Type 2 */
    NFP_RETURN(NFP_OK);
}
HLE(_ZN2nn3nfp12GetModelInfoEPNS0_9ModelInfoERKNS0_12DeviceHandleE) {
    NFP_LOCK();
    uint8_t *out = nfp_buffer(ARG(0), 0x40);
    if (!out || !nfp_device(ARG(1))) NFP_RETURN(NFP_BAD_ARGUMENT);
    if (nfp_state != NFP_MOUNTED) NFP_RETURN(NFP_BAD_STATE);
    const uint8_t *id = nfp_tag + 0x54;
    memset(out, 0, 0x40);
    out[0] = id[1]; out[1] = id[0]; out[2] = id[2]; out[3] = id[6];
    out[4] = id[5]; out[5] = id[4]; out[6] = id[3];
    hos_log("amiibo: model identity read by game");
    NFP_RETURN(NFP_OK);
}
HLE(_ZN2nn3nfp13GetCommonInfoEPNS0_10CommonInfoERKNS0_12DeviceHandleE) {
    NFP_LOCK();
    if (!nfp_device(ARG(1)) || nfp_state != NFP_MOUNTED) NFP_RETURN(NFP_BAD_STATE);
    /* This is in the encrypted RAM area; do not invent successful output. */
    NFP_RETURN(NFP_NO_APP);
}
HLE(_ZN2nn3nfp15GetRegisterInfoEPNS0_12RegisterInfoERKNS0_12DeviceHandleE) {
    NFP_LOCK();
    if (!nfp_device(ARG(1)) || nfp_state != NFP_MOUNTED) NFP_RETURN(NFP_BAD_STATE);
    NFP_RETURN(NFP_NOT_REGISTERED);
}
HLE(_ZN2nn3nfp19OpenApplicationAreaERKNS0_12DeviceHandleEj) { RET(NFP_NO_APP); }
HLE(_ZN2nn3nfp18GetApplicationAreaEPvPmRKNS0_12DeviceHandleEm) { RET(NFP_NO_APP); }
HLE(_ZN2nn3nfp18SetApplicationAreaERKNS0_12DeviceHandleEPKvm) { RET(NFP_NO_APP); }
HLE(_ZN2nn3nfp23RecreateApplicationAreaERKNS0_12DeviceHandleERKNS0_25ApplicationAreaCreateInfoE) { RET(NFP_NO_APP); }
HLE(_ZN2nn3nfp21CreateApplicationAreaERKNS0_12DeviceHandleERKNS0_25ApplicationAreaCreateInfoE) { RET(NFP_NO_APP); }
HLE(_ZN2nn3nfp5FlushERKNS0_12DeviceHandleE) { RET(NFP_NO_APP); }
/* System applets cannot modify this read-only reader. Never claim a repair,
   registration or erase succeeded while leaving its output uninitialized. */
HLE(_ZN2nn3nfp29StartNicknameAndOwnerSettingsEPNS0_12DeviceHandleEPbPNS0_12RegisterInfoERKNS0_24AmiiboSettingsStartParamERKNS0_7TagInfoERKS4_) { RET(NFP_NOT_REGISTERED); }
HLE(_ZN2nn3nfp29StartNicknameAndOwnerSettingsEPNS0_12DeviceHandleEPbPNS0_12RegisterInfoERKNS0_24AmiiboSettingsStartParamERKNS0_7TagInfoE) { RET(NFP_NOT_REGISTERED); }
HLE(_ZN2nn3nfp19StartGameDataEraserEPNS0_12DeviceHandleERKNS0_24AmiiboSettingsStartParamERKNS0_7TagInfoE) { RET(NFP_NO_APP); }
HLE(_ZN2nn3nfp13StartRestorerEPNS0_12DeviceHandleERKNS0_24AmiiboSettingsStartParamERKNS0_7TagInfoE) { RET(NFP_NO_APP); }

static void nfp_attach(Ctx *c, int kind) {
    NFP_LOCK();
    if (!nfp_initialized || !nfp_buffer(ARG(0), 0x40) || (kind < 2 && !nfp_device(ARG(1)))) NFP_RETURN(NFP_BAD_ARGUMENT);
    hos_system_event_init(ARG(0), kind == 2);
    if (kind == 0) { nfp_activate = ARG(0); if (nfp_tag_ready()) hos_system_event_signal(ARG(0)); }
    if (kind == 1) nfp_deactivate = ARG(0);
    NFP_RETURN(NFP_OK);
}
HLE(_ZN2nn3nfp19AttachActivateEventEPNS_2os15SystemEventTypeERKNS0_12DeviceHandleE) { nfp_attach(c, 0); }
HLE(_ZN2nn3nfp21AttachDeactivateEventEPNS_2os15SystemEventTypeERKNS0_12DeviceHandleE) { nfp_attach(c, 1); }
HLE(_ZN2nn3nfp29AttachAvailabilityChangeEventEPNS_2os15SystemEventTypeE) { nfp_attach(c, 2); }
