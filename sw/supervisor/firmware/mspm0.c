/* SPDX-License-Identifier: MIT
 * DAQHAT-01 MSPM0L1106TRHBR. GPIO mapping follows the independent pin fixture.
 * Target build evidence does not qualify ADC accuracy, shutdown timing or power.
 */
#include "power.h"
#ifndef POLICY_HEADER
#define POLICY_HEADER "policy.h"
#endif
#include POLICY_HEADER
#include <ti/driverlib/dl_gpio.h>
#include <ti/driverlib/dl_adc12.h>
#include <ti/driverlib/dl_vref.h>
#include <ti/driverlib/dl_wwdt.h>
static volatile uint32_t ticks;
void systick(void){ticks++;}
static void trap(void){for(;;){} /* watchdog resets; external RUN pulldown keeps reset safe */}
extern uint32_t _stack,_sidata,_sdata,_edata,_sbss,_ebss;
void start(void);
__attribute__((section(".vectors"),used)) const uintptr_t vectors[48]={
    [0]=(uintptr_t)&_stack,[1]=(uintptr_t)start,[2]=(uintptr_t)trap,[3]=(uintptr_t)trap,
    [11]=(uintptr_t)trap,[14]=(uintptr_t)trap,[15]=(uintptr_t)systick
};
static void outputs(const power_state *s) {
    if(s->request)DL_GPIO_setPins(GPIOA,DL_GPIO_PIN_4);else DL_GPIO_clearPins(GPIOA,DL_GPIO_PIN_4);
    if(s->run)DL_GPIO_setPins(GPIOA,DL_GPIO_PIN_3);else DL_GPIO_clearPins(GPIOA,DL_GPIO_PIN_3);
}
static bool measure(uint32_t *mv) {
    DL_ADC12_clearInterruptStatus(ADC0,DL_ADC12_INTERRUPT_MEM0_RESULT_LOADED);
    DL_ADC12_startConversion(ADC0);
    uint32_t began=ticks;
    while(!DL_ADC12_getRawInterruptStatus(ADC0,DL_ADC12_INTERRUPT_MEM0_RESULT_LOADED))
        if(ticks-began>=10)return false;
    uint32_t code=DL_ADC12_getMemResult(ADC0,DL_ADC12_MEM_IDX_0);
    if(code==0 || code>=4095)return false;
    /* R135/R136 = 1M/150k; nominal 2.5 V reference. Calibration pending. */
    *mv=(uint32_t)(((uint64_t)code*2500*115+30712)/(4095*15));
    return true;
}
int main(void) {
    DL_GPIO_reset(GPIOA);DL_GPIO_enablePower(GPIOA);
    DL_ADC12_reset(ADC0);DL_ADC12_enablePower(ADC0);
    DL_VREF_reset(VREF);DL_VREF_enablePower(VREF);
    for(volatile unsigned i=0;i<1000;i++){}
    DL_GPIO_clearPins(GPIOA,DL_GPIO_PIN_3|DL_GPIO_PIN_4);
    DL_GPIO_initDigitalOutput(IOMUX_PINCM4);DL_GPIO_initDigitalOutput(IOMUX_PINCM5);
    DL_GPIO_enableOutput(GPIOA,DL_GPIO_PIN_3|DL_GPIO_PIN_4);
    DL_GPIO_initDigitalInput(IOMUX_PINCM6); /* PA5 ACK_N, external pull-up */
    /* PA27/ADC0.0 stays analog; SWD pins stay in reset mux state. */
    const DL_VREF_ClockConfig vc={DL_VREF_CLOCK_BUSCLK,DL_VREF_CLOCK_DIVIDE_1};
    const DL_VREF_Config vr={DL_VREF_ENABLE_ENABLE,DL_VREF_BUFCONFIG_OUTPUT_2_5V,
                            DL_VREF_SHMODE_DISABLE,DL_VREF_SH_MIN,DL_VREF_HOLD_MIN};
    DL_VREF_setClockConfig(VREF,&vc);DL_VREF_configReference(VREF,&vr);
    const DL_ADC12_ClockConfig ac={.clockSel=DL_ADC12_CLOCK_SYSOSC,
        .divideRatio=DL_ADC12_CLOCK_DIVIDE_8,.freqRange=DL_ADC12_CLOCK_FREQ_RANGE_24_TO_32};
    DL_ADC12_setClockConfig(ADC0,&ac);
    DL_ADC12_initSingleSample(ADC0,DL_ADC12_REPEAT_MODE_DISABLED,DL_ADC12_SAMPLING_SOURCE_AUTO,
        DL_ADC12_TRIG_SRC_SOFTWARE,DL_ADC12_SAMP_CONV_RES_12_BIT,DL_ADC12_SAMP_CONV_DATA_FORMAT_UNSIGNED);
    DL_ADC12_configConversionMem(ADC0,DL_ADC12_MEM_IDX_0,DL_ADC12_INPUT_CHAN_0,
        DL_ADC12_REFERENCE_VOLTAGE_INTREF,DL_ADC12_SAMPLE_TIMER_SOURCE_SCOMP0,
        DL_ADC12_AVERAGING_MODE_DISABLED,DL_ADC12_BURN_OUT_SOURCE_DISABLED,
        DL_ADC12_TRIGGER_MODE_AUTO_NEXT,DL_ADC12_WINDOWS_COMP_MODE_DISABLED);
    DL_ADC12_setSampleTime0(ADC0,500);DL_ADC12_enableConversions(ADC0);
    SysTick_Config(32000); /* reset SYSOSC = 32 MHz; 1 ms */
    DL_WWDT_initWatchdogMode(WWDT0,DL_WWDT_CLOCK_DIVIDE_1,DL_WWDT_TIMER_PERIOD_15_BITS,
        DL_WWDT_RUN_IN_SLEEP,DL_WWDT_WINDOW_PERIOD_0,DL_WWDT_WINDOW_PERIOD_0);
    power_state state;power_init(&state,&board_policy,0);outputs(&state);
    uint32_t previous=ticks;uint64_t elapsed=0;
    for(;;) {
        uint32_t now=ticks;elapsed+=(uint32_t)(now-previous);previous=now;
        uint32_t mv=0;bool valid=elapsed>=20 && measure(&mv);
        bool halted=!DL_GPIO_readPins(GPIOA,DL_GPIO_PIN_5);
        power_tick(&state,elapsed,valid,mv,halted);outputs(&state);
        DL_WWDT_restart(WWDT0);
        uint32_t wait=ticks;while(ticks-wait<10)__WFI();
    }
}
void start(void) {
    uint32_t *src=&_sidata;for(uint32_t *dst=&_sdata;dst<&_edata;) *dst++=*src++;
    for(uint32_t *dst=&_sbss;dst<&_ebss;) *dst++=0;
    main();trap();
}
