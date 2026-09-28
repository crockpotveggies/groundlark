/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef SK_PERIPHERALS_H
#define SK_PERIPHERALS_H
#include <stdbool.h>
#include <stdint.h>
/* Small MMIO seam: the same bounded driver runs on hardware and fault fixtures. */
typedef enum { SK_ADC_CR, SK_ADC_ISR, SK_ADC_CHSELR, SK_ADC_DR,
               SK_I2C_ISR, SK_I2C_ICR } sk_register;
uint32_t sk_register_read(sk_register reg);
void sk_register_write(sk_register reg,uint32_t value);
bool sk_adc_initialize(void);
bool sk_adc_enable(void);
bool sk_adc_disable(void);
unsigned sk_adc_sample(unsigned channel);
bool sk_i2c_wait_flag(uint32_t flag,uint64_t end);
#endif
