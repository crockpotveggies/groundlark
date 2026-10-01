/* SPDX-License-Identifier: MIT */
#ifndef SK_BOOT_H
#define SK_BOOT_H
#include <stdint.h>
uint32_t sk_boot_next(const volatile uint32_t *pages,
                     void (*erase)(unsigned page),
                     void (*program)(unsigned word, uint32_t value));
#endif
