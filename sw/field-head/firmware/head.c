/* SPDX-License-Identifier: MIT
 * Burrowlark fixed 10 Hz RM3100 / 1 Hz SHT45 profile. No heap or RTOS.
 * PNI RM3100 breakout manual r08; Sensirion SHT4x high-precision command.
 */
#include "head.h"
#include <string.h>
typedef struct { uint8_t d[192];unsigned n;bool bad; } buf;
static void byte(buf *b,uint8_t v) { if(b->n<sizeof b->d)b->d[b->n++]=v;else b->bad=true; }
static void var(buf *b,uint64_t v) { while(v>127){byte(b,(uint8_t)v|128);v>>=7;}byte(b,(uint8_t)v); }
static void num(buf *b,unsigned f,uint64_t v) { var(b,f<<3);var(b,v); }
static void bytes(buf *b,unsigned f,const void *data,unsigned n) { var(b,(f<<3)|2);var(b,n);const uint8_t *p=data;for(unsigned i=0;i<n;i++)byte(b,p[i]); }
static void sub(buf *b,unsigned f,const buf *v) { bytes(b,f,v->d,v->n);b->bad|=v->bad; }
static bool enqueue(bh_state *s,unsigned field,const buf *body) {
    if(s->count==BH_QUEUE){if(field==12)s->overflow=true;return false;}
    if(body->bad || !s->connected || !s->boot)return false;
    buf b={0};num(&b,1,1);bytes(&b,2,s->device,(unsigned)strlen(s->device));
    byte(&b,25);for(unsigned i=0;i<8;i++)byte(&b,(uint8_t)(s->boot>>(i*8)));sub(&b,field,body);
    uint32_t crc=~0u;for(unsigned i=0;i<b.n;i++){crc^=b.d[i];for(unsigned j=0;j<8;j++)crc=(crc>>1)^(0xedb88320u&(0u-(crc&1)));}
    crc=~crc;for(unsigned i=0;i<4;i++)byte(&b,(uint8_t)(crc>>(i*8)));if(b.bad)return false;
    unsigned slot=(s->head+s->count)%BH_QUEUE;uint8_t *out=s->frames[slot];unsigned n=1,start=0;uint8_t code=1;
    if(field==10){out[0]=0;start=1;n=2;}
    for(unsigned i=0;i<b.n;i++) {
        if(!b.d[i]){out[start]=code;start=n++;code=1;}
        else{out[n++]=b.d[i];if(++code==255){out[start]=code;start=n++;code=1;}}
    }
    out[start]=code;out[n++]=0;s->lengths[slot]=(uint16_t)n;s->count++;return true;
}
static uint8_t crc8(const uint8_t *p){uint8_t c=255;for(unsigned i=0;i<2;i++){c^=p[i];for(unsigned j=0;j<8;j++)c=(uint8_t)((c<<1)^((c&128)?0x31:0));}return c;}
static bool reg(uint8_t r,uint8_t *data,unsigned n){return bh_i2c(0x20,&r,1,data,n);}
static bool write_reg(uint8_t r,uint8_t v){uint8_t d[]={r,v};return bh_i2c(0x20,d,2,0,0);}
static uint8_t configure(void){
    uint8_t enabled=0,data[6],cycles[]={4,0,200,0,200,0,200},stop=0x94;
    if(write_reg(1,0) && bh_i2c(0x20,cycles,7,0,0) && reg(4,data,6) && !memcmp(data,cycles+1,6) &&
       write_reg(0x0b,0x96) && reg(0x0b,data,1) && data[0]==0x96 && write_reg(1,0x79)) enabled|=1;
    if(bh_i2c(0x44,&stop,1,0,0)) {bh_delay(1);enabled|=2;}
    return enabled;
}
void bh_init(bh_state *s,const char *device,uint64_t boot){memset(s,0,sizeof *s);size_t n=strlen(device);if(!n||n>32)return;memcpy(s->device,device,n);s->boot=boot;bh_power(false);}
void bh_supply(bh_state *s,bool enabled,uint64_t ms){
    if(enabled==s->powered)return;
    s->power_generation++;
    s->powered=enabled;s->initialized=false;s->enabled=0;s->ready=ms+20;
    memset(s->failures,0,sizeof s->failures);
    if(!enabled)bh_connection(s,false);
    bh_power(enabled);
}
void bh_connection(bh_state *s,bool connected){
    connected=connected&&s->powered&&s->boot;
    if(connected==s->connected)return;
    s->connected=connected;s->count=s->head=0;s->announce=0;
    if(connected&&s->initialized){if(s->revision==UINT32_MAX){s->boot=0;return;}s->revision++;s->announce=1;}
}
static bool handshake(bh_state *s){
    buf b={0};
    if(s->announce==1){num(&b,1,2);bytes(&b,2,"burrowlark-0.1.0",15);uint8_t ids[]={7,17};bytes(&b,3,ids,2);if(!enqueue(s,10,&b))return false;s->announce=2;}
    else{
        num(&b,1,s->revision);
        for(unsigned i=0;i<2;i++){buf c={0};num(&c,1,i?17:7);num(&c,2,(s->enabled>>i)&1);num(&c,3,(s->enabled&(1u<<i))?(i?1000000000:100000000):0);
            if(!i){num(&c,8,200);num(&c,9,200);num(&c,10,200);}sub(&b,2,&c);}
        if(!enqueue(s,11,&b))return false;s->announce=0;
    }return true;
}
static void status(bh_state *s,unsigned sensor,const char *detail){buf b={0};num(&b,1,sensor);num(&b,2,3);bytes(&b,4,detail,(unsigned)strlen(detail));enqueue(s,13,&b);}
static unsigned read_sensor(unsigned index,uint8_t *raw){
    if(!index){uint8_t status;
        if(!reg(0x34,&status,1))return 2;
        if(!(status&0x80))return 0;
        return reg(0x24,raw,9)?1:2;
    }
    uint8_t command=0xfd;
    if(!bh_i2c(0x44,&command,1,0,0))return 2;
    bh_delay(9);
    if(!bh_i2c(0x44,0,0,raw,6)||crc8(raw)!=raw[2]||crc8(raw+3)!=raw[5])return 2;
    return 1;
}
static void sample(bh_state *s,unsigned index,uint64_t ms,unsigned quality,const uint8_t *raw){
    buf batch={0},sample={0},stamp={0};num(&batch,1,index?17:7);num(&batch,2,s->revision);
    num(&sample,1,s->sequence[index]);num(&stamp,1,2);num(&stamp,2,ms*1000000);sub(&sample,2,&stamp);num(&sample,3,quality);
    if(quality==1||quality==3){buf payload={0};
        if(index)bytes(&payload,1,raw,6);
        else{buf xyz={0};for(unsigned i=0;i<3;i++){uint32_t u=(uint32_t)raw[3*i]<<16|(uint32_t)raw[3*i+1]<<8|raw[3*i+2];int32_t v=(int32_t)(u&0x800000?u|0xff000000:u);num(&xyz,i+1,((uint32_t)v<<1)^(uint32_t)(v>>31));}sub(&payload,1,&xyz);}
        sub(&sample,index?18:12,&payload);
    }
    sub(&batch,3,&sample);enqueue(s,12,&batch); /* dropped_before absent: physical loss unknown */
}
void bh_tick(bh_state *s,uint64_t ms){
    if(!s->powered||!s->boot)return;
    uint32_t generation=s->power_generation;
    if(!s->initialized){if(ms<s->ready)return;uint8_t enabled=configure();
        if(!s->powered||generation!=s->power_generation)return;
        s->enabled=enabled;s->initialized=true;s->next[0]=s->next[1]=bh_clock();
        if(s->revision==UINT32_MAX){s->boot=0;return;}s->revision++;if(s->connected)s->announce=1;}
    while(s->announce){if(!handshake(s))return;}
    if(s->overflow && s->count<BH_QUEUE && s->connected) {
        buf b={0};num(&b,1,0);num(&b,2,4);bytes(&b,4,"USB sample queue overflow",25);
        if(enqueue(s,13,&b))s->overflow=false;
    }
    for(unsigned i=0;i<2;i++){
        uint64_t now=bh_clock(),period=i?1000:100;
        if(!(s->enabled&(1u<<i))||now<s->next[i])continue;
        uint64_t skipped=(now-s->next[i])/period;
        if(s->sequence[i]>UINT64_MAX-skipped-1){s->boot=0;return;}
        s->sequence[i]+=skipped;s->next[i]=now+period;
        uint8_t raw[9]={0};unsigned quality=s->failures[i]>=3?2:read_sensor(i,raw);
        if(!s->powered||generation!=s->power_generation)return;
        if(quality==2&&s->failures[i]<3){s->failures[i]++;status(s,i?17:7,"sensor read failed");}
        if(quality==1){s->failures[i]=0;if(!i)for(unsigned j=0;j<3;j++)if((raw[j*3]==0x80&&!raw[j*3+1]&&!raw[j*3+2])||(raw[j*3]==0x7f&&raw[j*3+1]==255&&raw[j*3+2]==255))quality=3;}
        sample(s,i,bh_clock(),quality?quality:2,raw);s->sequence[i]++;
    }
}
const uint8_t *bh_tx(bh_state *s,uint16_t *length){if(!s->count)return 0;*length=s->lengths[s->head];return s->frames[s->head];}
void bh_tx_done(bh_state *s){if(s->count){s->head=(s->head+1)%BH_QUEUE;s->count--;}}
