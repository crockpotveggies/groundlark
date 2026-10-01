/* SPDX-License-Identifier: MIT */
#include "head.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint64_t now;static bool power;static unsigned mode;static uint8_t registers[256];
static uint64_t climate_ready;
static bh_state *current;
uint64_t bh_clock(void){return now;}
void bh_delay(uint32_t ms){now+=ms;if(mode==6&&power)bh_supply(current,false,now);}
void bh_power(bool enabled){power=enabled;}
bool bh_i2c(uint8_t addr,const uint8_t *w,size_t wn,uint8_t *r,size_t rn){
    assert(power);
    if(mode==1&&now>500)return false;
    if(addr==0x20){
        if(wn>1){memcpy(registers+w[0],w+1,wn-1);return true;}
        assert(wn==1);
        if(w[0]==0x34){r[0]=0x80;return true;}
        if(w[0]==0x24){const uint8_t v[]={0xff,0xff,0xfe,0,0,0,0x7f,0xff,0xfe};assert(rn==9);memcpy(r,v,9);return true;}
        memcpy(r,registers+w[0],rn);return true;
    }
    assert(addr==0x44);
    if(wn){assert(wn==1&&(w[0]==0xfd||w[0]==0x94));if(w[0]==0xfd)climate_ready=now+9;return true;}
    assert(rn==6&&now>=climate_ready);
    const uint8_t v[]={0x66,0x66,0x93,0x80,0,0xa2};memcpy(r,v,6);if(mode==2)r[2]^=1;return true;
}
static void drain(bh_state *s){uint16_t length;const uint8_t *p;while((p=bh_tx(s,&length))){assert(length<=BH_FRAME_MAX);fwrite(p,1,length,stdout);bh_tx_done(s);}}
int main(int argc,char **argv){
    mode=argc>1?(unsigned)atoi(argv[1]):0;
    bh_state s;current=&s;bh_init(&s,"native-burrowlark",1);assert(!power);bh_supply(&s,true,now);bh_connection(&s,true);
    for(;now<5000;now++){
        if(mode==3&&now==1500)bh_connection(&s,false);
        if(mode==3&&now==2500)bh_connection(&s,true);
        if(mode==4&&now==1500){bh_supply(&s,false,now);assert(!power);}
        if(mode==4&&now==2500){bh_supply(&s,true,now);bh_connection(&s,true);}
        bh_tick(&s,now);if(mode!=5||now<1000||now>2000)drain(&s);
    }drain(&s);if(mode==6)assert(!s.initialized&&!s.count&&!power);
    bh_supply(&s,false,now);assert(!power);return 0;
}
