/* SPDX-License-Identifier: GPL-3.0-only
 * Inject delayed/stuck hardware and coincident flags into production drivers.
 * Bit numbers come from RM0091, independent of driver-local constants.
 */
#include "peripherals.h"
#include <assert.h>
#include <string.h>
static uint32_t regs[6];
static uint64_t ticks,cal_end;
static bool stuck_cal,stuck_ready,stuck_conversion,overrun;
static unsigned berr_clears,starts;
uint64_t sk_clock(void) { return ticks++; }
void sk_delay(uint32_t ms) { ticks+=ms; }
uint32_t sk_register_read(sk_register r) {
    if(r==SK_ADC_CR && (regs[r]&(1u<<31)) && !stuck_cal) {
        regs[r]&=~(1u<<31);cal_end=ticks;
    }
    uint32_t v=regs[r];
    if(r==SK_ADC_DR)regs[SK_ADC_ISR]&=~4u;
    return v;
}
void sk_register_write(sk_register r,uint32_t value) {
    if(r==SK_I2C_ICR) { regs[SK_I2C_ISR]&=~value;if(value&256)berr_clears++;return; }
    if(r==SK_ADC_ISR) { regs[r]&=~value;return; }
    if(r==SK_ADC_CR) {
        regs[r]=value;
        if(value&16) { regs[r]&=~20u;return; }
        if(value&2) { regs[r]&=~3u;regs[SK_ADC_ISR]&=~1u;return; }
        if((value&1) && !stuck_ready) {
            assert(ticks>=cal_end+2); /* Reject the former immediate ADEN. */
            regs[SK_ADC_ISR]|=1;
        }
        if(value&4) {
            starts++;
            if(!stuck_conversion) {
                regs[r]&=~4u;regs[SK_ADC_ISR]|=4|(overrun?16:0);
                regs[SK_ADC_DR]=regs[SK_ADC_CHSELR]==1?2900:1500;
            }
        }
        return;
    }
    regs[r]=value;
}
static void reset(void) {
    memset(regs,0,sizeof regs);ticks=10;cal_end=0;
    stuck_cal=stuck_ready=stuck_conversion=overrun=false;starts=0;
}
int main(void) {
    reset();assert(sk_adc_initialize());
    assert(sk_adc_sample(0)==2900 && sk_adc_sample(17)==1500);
    assert(sk_adc_disable());assert(sk_adc_sample(0)==0);
    assert(sk_adc_enable());assert(sk_adc_sample(17)==1500);
    reset();stuck_cal=true;assert(!sk_adc_initialize());assert(ticks<20);
    assert(sk_adc_sample(0)==0 && starts==0);
    reset();stuck_ready=true;assert(!sk_adc_initialize());assert(ticks<25);
    reset();assert(sk_adc_initialize());stuck_conversion=true;
    assert(sk_adc_sample(0)==0);assert(ticks<30);
    /* A timed-out result arriving late cannot satisfy the VREF channel. */
    regs[SK_ADC_ISR]|=4;regs[SK_ADC_DR]=2900;stuck_conversion=false;
    assert(sk_adc_sample(17)==0 && starts==1);
    assert(sk_adc_enable());assert(sk_adc_sample(17)==1500);
    overrun=true;assert(sk_adc_sample(0)==0);
    reset();regs[SK_I2C_ISR]=256|2;
    assert(sk_i2c_wait_flag(2,100));assert(berr_clears==1);
    regs[SK_I2C_ISR]=16|32;assert(!sk_i2c_wait_flag(32,100));
    regs[SK_I2C_ISR]=512|2;assert(!sk_i2c_wait_flag(2,100));
    regs[SK_I2C_ISR]=32;assert(!sk_i2c_wait_flag(4,100));
    regs[SK_I2C_ISR]=0;assert(!sk_i2c_wait_flag(4,ticks+5));assert(ticks<25);
    return 0;
}
