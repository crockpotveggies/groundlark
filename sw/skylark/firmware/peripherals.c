/* SPDX-License-Identifier: GPL-3.0-only
 * STM32F072 RM0091 register bits; ES0223 Rev 6 sections 2.4.3 and 2.11.8.
 */
#include "platform.h"
#include "peripherals.h"
enum { ADEN=1u, ADDIS=2u, ADSTART=4u, ADSTP=16u,
       ADRDY=1u, EOC=4u, EOS=8u, OVR=16u,
       NACKF=16u, STOPF=32u, BERR=256u, ARLO=512u };
#define ADCAL (1u<<31)
static bool adc_ready;
static void set_cr(uint32_t bits) {
    sk_register_write(SK_ADC_CR,sk_register_read(SK_ADC_CR)|bits);
}
static bool wait_register(sk_register reg,uint32_t mask,bool set) {
    uint64_t end=sk_clock()+2;
    while(((sk_register_read(reg)&mask)!=0)!=set)
        if(sk_clock()>=end)return false;
    return true;
}
bool sk_adc_enable(void) {
    adc_ready=false;
    if(sk_register_read(SK_ADC_CR)&(ADCAL|ADSTART|ADSTP|ADDIS))return false;
    sk_register_write(SK_ADC_ISR,ADRDY);
    set_cr(ADEN);
    adc_ready=wait_register(SK_ADC_ISR,ADRDY,true);
    return adc_ready;
}
bool sk_adc_initialize(void) {
    adc_ready=false;
    set_cr(ADCAL);
    if(!wait_register(SK_ADC_CR,ADCAL,false))return false;
    /* ES0223: allow >=4 ADC clocks after calibration. Two ms ticks guarantee
     * at least 1 ms even when called just before SysTick; USB is not up yet. */
    sk_delay(2);
    return sk_adc_enable();
}
bool sk_adc_disable(void) {
    adc_ready=false;
    if(sk_register_read(SK_ADC_CR)&ADSTART) {
        set_cr(ADSTP);
        if(!wait_register(SK_ADC_CR,ADSTART|ADSTP,false))return false;
    }
    if(sk_register_read(SK_ADC_CR)&ADEN)set_cr(ADDIS);
    return wait_register(SK_ADC_CR,ADEN|ADDIS,false);
}
unsigned sk_adc_sample(unsigned channel) {
    if(!adc_ready || channel>18 || (sk_register_read(SK_ADC_CR)&(ADSTART|ADSTP|ADDIS|ADCAL)))return 0;
    sk_register_write(SK_ADC_ISR,EOC|EOS|OVR);
    sk_register_write(SK_ADC_CHSELR,1u<<channel);
    set_cr(ADSTART);
    if(!wait_register(SK_ADC_ISR,EOC,true) || (sk_register_read(SK_ADC_ISR)&OVR)) {
        /* A late conversion must not be mistaken for the next channel. Latch
         * the monitor unavailable until suspend/resume or reset re-enables it. */
        (void)sk_adc_disable();return 0;
    }
    return sk_register_read(SK_ADC_DR);
}
bool sk_i2c_wait_flag(uint32_t flag,uint64_t end) {
    for(;;) {
        uint32_t status=sk_register_read(SK_I2C_ISR);
        /* ES0223: BERR alone does not abort a master transfer. Clear it and
         * keep checking NACK/arbitration/STOP and the bounded deadline. */
        if(status&BERR)sk_register_write(SK_I2C_ICR,BERR);
        if(status&(NACKF|ARLO))return false;
        if(status&flag)return true;
        if((status&STOPF) || sk_clock()>=end)return false;
    }
}
