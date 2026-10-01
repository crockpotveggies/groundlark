/* SPDX-License-Identifier: MIT */
#ifndef SKYLARK_H
#define SKYLARK_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define SK_CHANNELS 7
#define SK_FRAME_MAX 272
#define SK_QUEUE 8
#define SK_GAS_SLOT_MS 8
#define SK_ADC_CONFIG1 0x82
typedef struct { int32_t counts; uint8_t counter, data[32], trim[21]; } sk_raw;
/* Board hooks: bounded operations; read returns pending=0, valid=1, missing=2,
 * saturated=3, fault=4. Invalid frames must never be returned as valid. */
void sk_power(bool enabled); /* Must clamp before cutting analog power. */
uint8_t sk_configure(void); /* Successfully configured channel bitmask. */
uint8_t sk_read(uint8_t sensor, sk_raw *raw);
typedef struct {
    char device[33]; uint64_t boot, started, ready, next[SK_CHANNELS];
    uint64_t sequence[SK_CHANNELS], dropped, gas_due;
    uint8_t gas_slot;
    uint32_t revision; uint8_t faults[SK_CHANNELS], enabled, announce, pending;
    bool powered, connected, initialized;
    uint8_t frames[SK_QUEUE][SK_FRAME_MAX]; uint16_t lengths[SK_QUEUE];
    uint8_t head, count;
} sk_state;
void sk_init(sk_state *s, const char *device, uint64_t boot);
void sk_supply(sk_state *s, bool available, uint64_t ms);
void sk_connection(sk_state *s, bool ready, uint64_t ms);
void sk_tick(sk_state *s, uint64_t ms);
const uint8_t *sk_tx(sk_state *s, uint16_t *length);
void sk_tx_done(sk_state *s);
uint8_t sk_crc8(const uint8_t *data, size_t length);
bool sk_pms_valid(const uint8_t data[32]);
#endif
