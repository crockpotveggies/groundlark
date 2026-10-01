/* SPDX-License-Identifier: MIT */
#ifndef GROUNDLARK_HEAD_H
#define GROUNDLARK_HEAD_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define BH_QUEUE 4
#define BH_FRAME_MAX 224
typedef struct {
    char device[33]; uint64_t boot, next[2], sequence[2], ready;
    uint32_t revision, power_generation; unsigned head,count,announce;
    bool powered,connected,initialized,overflow; uint8_t enabled,failures[2];
    uint8_t frames[BH_QUEUE][BH_FRAME_MAX];uint16_t lengths[BH_QUEUE];
} bh_state;
uint64_t bh_clock(void);
void bh_delay(uint32_t ms);
bool bh_i2c(uint8_t address,const uint8_t *write,size_t wn,uint8_t *read,size_t rn);
void bh_power(bool enabled);
void bh_init(bh_state *state,const char *device,uint64_t boot);
void bh_supply(bh_state *state,bool enabled,uint64_t ms);
void bh_connection(bh_state *state,bool connected);
void bh_tick(bh_state *state,uint64_t ms);
const uint8_t *bh_tx(bh_state *state,uint16_t *length);
void bh_tx_done(bh_state *state);
#endif
