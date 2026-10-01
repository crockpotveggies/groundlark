/* SPDX-License-Identifier: MIT
 * TI ADS122C04 SBAS751B, Sensirion SHT4x, Bosch BMP388 and PMS5003 v2.3.
 * Raw transport bytes and factory trim are preserved; no gas calibration here.
 */
#include "platform.h"
#include <string.h>
static uint8_t mux, adc_counter, trim[21], pm_work[32], pm_frame[32], pm_n;
static bool adc_seen, pm_new, powered, climate_pending;
static uint64_t pm_time, adc_time, climate_due;
static bool command(uint8_t addr,uint8_t cmd,uint8_t *r,size_t n) { return sk_i2c(addr,&cmd,1,r,n); }
static bool write_reg(uint8_t addr,uint8_t reg,uint8_t value) { uint8_t w[]={reg,value};return sk_i2c(addr,w,2,NULL,0); }
static bool adc_reg(uint8_t reg,uint8_t expected) {
    uint8_t r[2];return command(0x40,(uint8_t)(0x20|(reg<<2)),r,2) && (r[0]^r[1])==255 && (r[0] & (reg==2?127:255))==expected;
}
static bool start_adc(uint8_t channel) {
    uint8_t value=(uint8_t)(((8+channel)<<4)|1);
    return write_reg(0x40,0x40,value) && adc_reg(0,value) && command(0x40,8,NULL,0);
}
void sk_power(bool enabled) {
    powered=enabled;sk_clamp(true);sk_rails(enabled);pm_n=0;pm_new=false;adc_seen=false;
    climate_pending=false;
}
uint8_t sk_configure(void) {
    uint8_t enabled=0,r[21];mux=0;adc_seen=false;
    bool adc=command(0x40,6,NULL,0);sk_delay(2);
    if(!powered)return 0;
    for(unsigned i=0;i<4 && adc;i++) adc=command(0x40,(uint8_t)(0x20|(i<<2)),r,1) && r[0]==0;
    adc=adc && write_reg(0x40,0x40,0x81) && write_reg(0x40,0x44,SK_ADC_CONFIG1) && write_reg(0x40,0x4c,0) && write_reg(0x40,0x48,0x50);
    adc=adc && adc_reg(0,0x81) && adc_reg(1,SK_ADC_CONFIG1) && adc_reg(2,0x50) && adc_reg(3,0);
    if(adc && start_adc(0))enabled|=15;
    /* Rails/reference have already had 150 ms to rise. Cell settling continues
     * for 60 s as MISSING; this duration is a prototype policy to qualify. */
    sk_clamp(false);
    if(command(0x44,0x89,NULL,0)) {
        sk_delay(2);
        if(!powered)return 0;
        if(sk_i2c(0x44,NULL,0,r,6) && sk_crc8(r,2)==r[2] && sk_crc8(r+3,2)==r[5])enabled|=32;
    }
    if(write_reg(0x76,0x7e,0xb6)) {
        sk_delay(3);
        if(!powered)return 0;
        bool ok=command(0x76,0,r,1) && r[0]==0x50 && command(0x76,0x31,trim,21);
        ok=ok && write_reg(0x76,0x1c,0x0b) && write_reg(0x76,0x1d,0x06) && write_reg(0x76,0x1b,0x33);
        ok=ok && command(0x76,0x1b,r,3) && r[0]==0x33 && r[1]==0x0b && r[2]==0x06;
        if(ok && command(0x76,2,r,1) && !(r[0]&7)) enabled|=64;
    }
    if(sk_pm_supply_ok())enabled|=16; /* UART configured at 9600 8N1; readiness is frame-based. */
    return enabled;
}
void sk_uart_error(void) { pm_n=0;pm_new=false; }
void sk_uart_input(uint8_t byte) {
    if(pm_n==0 && byte!=0x42)return;
    if(pm_n==1 && byte!=0x4d) { pm_n=byte==0x42?1:0;return; }
    pm_work[pm_n++]=byte;
    if(pm_n==4 && (pm_work[2]!=0 || pm_work[3]!=28)) { pm_n=0;return; }
    if(pm_n==32) {
        if(sk_pms_valid(pm_work)) { memcpy(pm_frame,pm_work,32);pm_new=true;pm_time=sk_clock(); }
        else pm_new=false;
        pm_n=0;
    }
}
uint8_t sk_read(uint8_t sid,sk_raw *raw) {
    if(sid<14) {
        if(sid!=10+mux)return 2;
        uint8_t d[8],r[2];uint8_t result=4;
        if(command(0x40,0x28,r,2) && (r[0]^r[1])==255) {
            if(!(r[0]&128))result=2;
            else if(command(0x40,0x10,d,8)) {
                bool ok=true;for(unsigned i=0;i<4;i++)if((d[i]^d[i+4])!=255)ok=false;
                if(ok) {
                    raw->counter=d[0];uint32_t v=(uint32_t)d[1]<<16|(uint32_t)d[2]<<8|d[3];
                    raw->counts=(v&0x800000)?(int32_t)(v|0xff000000u):(int32_t)v;
                    result=(raw->counts==8388607 || raw->counts==-8388608)?3:1;
                    if(adc_seen && ((uint8_t)(d[0]-adc_counter)!=1 || sk_clock()-adc_time>=10000))result=2;
                    adc_counter=d[0];adc_time=sk_clock();adc_seen=true;
                }
            }
        }
        mux=(mux+1)%4;if(!start_adc(mux))result=4;
        return result;
    }
    if(sid==14) {
        if(!sk_pm_supply_ok()) { pm_new=false;return 4; }
        if(!pm_new || sk_clock()-pm_time>1500)return 2;
        pm_new=false;memcpy(raw->data,pm_frame,32);return pm_frame[29]?4:1;
    }
    if(sid==15) {
        if(!powered)return 2;
        if(!climate_pending) {
            if(!command(0x44,0xfd,NULL,0))return 4;
            climate_due=sk_clock()+10;climate_pending=true;return 0;
        }
        if(sk_clock()<climate_due)return 0;
        climate_pending=false;
        if(sk_clock()-climate_due>=1000)return 2;
        if(!sk_i2c(0x44,NULL,0,raw->data,6) || sk_crc8(raw->data,2)!=raw->data[2] || sk_crc8(raw->data+3,2)!=raw->data[5])return 4;
        return 1;
    }
    uint8_t status;
    if(!command(0x76,3,&status,1))return 4;
    if((status&0x60)!=0x60)return 2;
    if(!command(0x76,4,raw->data,6))return 4;
    memcpy(raw->trim,trim,21);return 1;
}
