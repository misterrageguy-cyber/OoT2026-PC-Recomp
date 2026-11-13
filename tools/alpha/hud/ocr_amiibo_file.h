/* Ocarina Reborn: public tag identity only, raw NTAG215 byte order.
   Layout reference: socram8888/amiitool amiibo.c, tag_to_internal; libnx nfc.h.
   No cryptographic keys, game data, tag decryption or write-back. */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include "hos_paths.h"

#define OCR_AMIIBO_FILE "ocarina_reborn_amiibo.bin"
#define OCR_AMIIBO_MAX 572

static inline int ocr_amiibo_valid(const uint8_t *p, size_t n) {
    if (n != 532 && n != 540 && n != 572) return 0;
    if (p[0] != 4 || p[3] != (0x88 ^ p[0] ^ p[1] ^ p[2]) ||
        p[8] != (p[4] ^ p[5] ^ p[6] ^ p[7]) || p[0x5b] != 2) return 0;
    /* amiibo's CC is F1 10 FF EE; E1 10 3E 00 is a generic NTAG215 CC. */
    if (memcmp(p + 12, "\xf1\x10\xff\xee", 4) && memcmp(p + 12, "\xe1\x10\x3e\x00", 4)) return 0;
    unsigned bits = 0;
    for (int i = 0x54; i < 0x5b; ++i) bits |= p[i];
    return bits != 0;
}

static inline int ocr_amiibo_path(char *out, size_t cap) {
    DWORD n = hos_game_path_a(out, (DWORD)cap);
    if (!n || n >= cap) return 0;
    while (n && out[n - 1] != '/' && out[n - 1] != '\\') --n;
    if (n + sizeof OCR_AMIIBO_FILE > cap) return 0;
    memcpy(out + n, OCR_AMIIBO_FILE, sizeof OCR_AMIIBO_FILE);
    return 1;
}

static inline int ocr_amiibo_read(const char *path, uint8_t *out, size_t *size) {
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    uint8_t bytes[OCR_AMIIBO_MAX + 1];
    size_t n = fread(bytes, 1, sizeof bytes, f);
    int ok = !ferror(f) && ocr_amiibo_valid(bytes, n);
    fclose(f);
    if (!ok) return 0;
    memcpy(out, bytes, n);
    *size = n;
    return 1;
}
