/* SPDX-License-Identifier: GPL-3.0-only
 * Independent register/UART fixture. Links the production encoder and drivers.
 * stdout is the real binary USB stream; assertions and checks run on the host.
 */
#include "platform.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint64_t now;
static bool clamp=true,rails;
static uint8_t regs[4],counter,bmp[256];
static unsigned resets,reads,mode;
static sk_state *active;
static const uint8_t climate[]={0x66,0x66,0x93,0x80,0x00,0xa2};
void sk_delay(uint32_t ms) {
    now+=ms;
    if(mode==6 && now>=150 && now<160)sk_connection(active,false,now);
}
uint64_t sk_clock(void) { return now; }
void sk_clamp(bool hold) { assert(hold || rails);clamp=hold; }
void sk_rails(bool on) { assert(clamp);rails=on; }
bool sk_pm_supply_ok(void) { return rails; }
bool sk_i2c(uint8_t addr,const uint8_t *w,size_t wn,uint8_t *r,size_t rn) {
    assert(rails);assert(wn<=32 && rn<=32);
    uint8_t cmd=wn?w[0]:0;
    if(addr==0x40) {
        if(mode==5)return false;
        if(cmd==6) { memset(regs,0,4);counter=0;resets++;return true; }
        if(cmd>=0x40 && cmd<=0x4c) { assert(wn==2);regs[(cmd>>2)&3]=w[1];return true; }
        if(cmd>=0x20 && cmd<=0x2c) {
            unsigned i=(cmd>>2)&3;r[0]=regs[i]|(i==2?128:0);
            if(!regs[2])r[0]=regs[i];
            if(rn==2)r[1]=(uint8_t)~r[0];return true;
        }
        if(cmd==8) { assert(regs[0]>=0x81 && regs[0]<=0xb1);assert(regs[1]==2 && regs[2]==0x50 && regs[3]==0);counter++;return true; }
        if(cmd==0x10) {
            assert(rn==8);reads++;r[0]=counter;r[1]=0x40;r[2]=0x12;r[3]=(regs[0]>>4)-8;
            for(unsigned i=0;i<4;i++)r[i+4]=(uint8_t)~r[i];
            if(mode==1 && now>61000)r[7]^=1;
            if(mode==2 && now>61000 && now<61080) { r[0]-=2;r[4]=(uint8_t)~r[0]; }
            return true;
        }
        assert(0);
    }
    if(addr==0x44) {
        if(wn) { assert(cmd==0xfd || cmd==0x89);return true; }
        assert(rn==6);memcpy(r,climate,6);
        if(mode==1 && now>61000)r[2]^=1;
        return true;
    }
    if(addr==0x76) {
        if(wn==2) { bmp[cmd]=w[1];return true; }
        assert(wn==1);
        if(cmd==0) { r[0]=0x60;return true; }
        if(cmd==3) { r[0]=0x60;return true; }
        if(cmd==4) { const uint8_t d[]={0x80,0xe6,0xc5,0,0x80,0x70};memcpy(r,d,6);return true; }
        if(cmd==0x31) {
            const uint8_t trim[]={0,100,0,128,0,0,96,0,64,0,0,0,0,0,0,0,0,0,0,0,0};
            memcpy(r,trim,21);return true;
        }
        memcpy(r,bmp+cmd,rn);return true;
    }
    assert(0);return false;
}
static void particulate(void) {
    uint8_t d[32]={0x42,0x4d,0,28};d[12]=0;d[13]=37;d[28]=1;
    unsigned sum=0;for(unsigned i=0;i<30;i++)sum+=d[i];d[30]=sum>>8;d[31]=sum;
    if(mode==1 && now>61000)d[31]^=1;
    sk_uart_input(0xff);for(unsigned i=0;i<32;i++)sk_uart_input(d[i]);
}
int main(int argc,char **argv) {
    if(argc>1)mode=(unsigned)(argv[1][0]-'0');
    assert(sk_crc8(climate,2)==climate[2]);assert(sk_crc8(climate+3,2)==climate[5]);
    sk_state s;active=&s;sk_init(&s,"native-skylark",1);assert(clamp && !rails);
    sk_connection(&s,true,now);assert(clamp && rails);
    bool resumed=false;
    while(now<72000) {
        if(now%100==0)particulate();
        if(mode==4 && now>=65000 && !resumed) {
            sk_connection(&s,false,now);assert(clamp && !rails && !s.count);
            now+=100;sk_connection(&s,true,now);resumed=true;
        }
        if(mode==6 && now>=1000 && !resumed) { assert(!rails && clamp);sk_connection(&s,true,now);resumed=true; }
        sk_tick(&s,now);assert(s.count<=SK_QUEUE);
        if(!(mode==3 && now>61000 && now<63000)) {
            uint16_t n;const uint8_t *p;
            while((p=sk_tx(&s,&n))) { assert(n<=SK_FRAME_MAX);assert(fwrite(p,1,n,stdout)==n);sk_tx_done(&s); }
        }
        now++;
    }
    assert(resets==(mode==5?0:mode==4 || mode==6?2:1));
    if(mode!=5)assert(reads>100);
    if(mode==3)assert(s.dropped>0);
    sk_connection(&s,false,now);assert(clamp && !rails);
    return 0;
}
