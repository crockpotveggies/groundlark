/* SPDX-License-Identifier: MIT */
#ifndef SK_PLATFORM_H
#define SK_PLATFORM_H
#include "skylark.h"
bool sk_i2c(uint8_t address,const uint8_t *write,size_t wn,uint8_t *read,size_t rn);
void sk_delay(uint32_t ms);
uint64_t sk_clock(void);
void sk_clamp(bool hold);
void sk_rails(bool enabled);
bool sk_pm_supply_ok(void);
void sk_uart_input(uint8_t byte);
void sk_uart_error(void);
#endif
