/* SPDX-License-Identifier: GPL-3.0-only
 * Shared by the STM32 image and native fault-injection tests. No heap/RTOS.
 * A bounded, write-only v1 protobuf encoder; wire compatibility is verified by
 * decoding actual C output with the repository's independent Protobuf runtime.
 */
#include "platform.h"
#include <string.h>
typedef struct { uint8_t data[256]; size_t n; bool failed; } buf;
static void byte(buf *b, uint8_t v) { if(b->n < sizeof b->data) b->data[b->n++]=v; else b->failed=true; }
static void var(buf *b, uint64_t v) { while(v>127) { byte(b,(uint8_t)v|128);v>>=7; } byte(b,(uint8_t)v); }
static void num(buf *b, uint8_t field, uint64_t v) { var(b,(uint32_t)field<<3);var(b,v); }
static void bytes(buf *b, uint8_t field, const void *p, size_t n) {
    var(b,((uint32_t)field<<3)|2);var(b,n);
    const uint8_t *a=p;for(size_t i=0;i<n;i++) byte(b,a[i]);
}
static void sub(buf *b,uint8_t field,const buf *v) { bytes(b,field,v->data,v->n); b->failed|=v->failed; }
static bool enqueue(sk_state *s, uint8_t field, const buf *body) {
    if(s->count==SK_QUEUE || body->failed) return false;
    buf b={0};num(&b,1,1);bytes(&b,2,s->device,strlen(s->device));
    byte(&b,25);for(unsigned i=0;i<8;i++) byte(&b,(uint8_t)(s->boot>>(8*i)));
    sub(&b,field,body);
    uint32_t crc=~0u;
    for(size_t i=0;i<b.n;i++) { crc^=b.data[i];for(unsigned j=0;j<8;j++) crc=(crc>>1)^(0xedb88320u & (0u-(crc&1))); }
    crc=~crc;for(unsigned i=0;i<4;i++) byte(&b,(uint8_t)(crc>>(8*i)));
    if(b.failed) return false;
    unsigned slot=(s->head+s->count)%SK_QUEUE;uint8_t *out=s->frames[slot];
    size_t n=1,start=0;uint8_t code=1;
    /* Discard a host's partial frame left by a prior CDC/DTR session. */
    if(field==10) { out[0]=0;start=1;n=2; }
    for(size_t i=0;i<b.n;i++) {
        if(!b.data[i]) { out[start]=code;start=n++;code=1; }
        else { out[n++]=b.data[i];if(++code==255) { out[start]=code;start=n++;code=1; } }
    }
    out[start]=code;out[n++]=0;s->lengths[slot]=(uint16_t)n;s->count++;return true;
}
uint8_t sk_crc8(const uint8_t *data,size_t length) {
    uint8_t crc=255;for(size_t i=0;i<length;i++) { crc^=data[i];for(unsigned j=0;j<8;j++) crc=(uint8_t)((crc<<1)^((crc&128)?0x31:0)); }return crc;
}
bool sk_pms_valid(const uint8_t d[32]) {
    if(d[0]!=0x42 || d[1]!=0x4d || d[2]!=0 || d[3]!=28) return false;
    unsigned sum=0;for(unsigned i=0;i<30;i++) sum+=d[i];return sum==((unsigned)d[30]<<8|d[31]);
}
void sk_init(sk_state *s,const char *id,uint64_t boot) {
    memset(s,0,sizeof *s);size_t n=strlen(id);if(n>32)n=32;
    memcpy(s->device,id,n);s->boot=boot;sk_power(false);
}
void sk_connection(sk_state *s,bool ready,uint64_t ms) {
    (void)ms;
    ready=ready && s->powered;
    if(ready==s->connected) return;
    s->connected=ready;s->count=0;s->head=0;s->announce=0;
    if(ready && s->initialized) { s->revision++;s->announce=1;s->pending|=0x80; }
}
/* USB configuration authorizes power; DTR only controls the data session.
 * A suspended/reset/unconfigured bus must still remove sensor power. */
void sk_supply(sk_state *s,bool available,uint64_t ms) {
    if(available==s->powered)return;
    s->powered=available;
    if(!available)sk_connection(s,false,ms);
    s->initialized=false;s->enabled=0;s->pending=0;
    sk_power(available);s->started=ms;s->ready=ms+150;
    memset(s->faults,0,sizeof s->faults);
}
static bool handshake(sk_state *s) {
    buf b={0};
    if(s->announce==1) {
        num(&b,1,3);bytes(&b,2,"skylark-0.1.1",13);
        uint8_t ids[]={10,11,12,13,14,15,16};bytes(&b,3,ids,sizeof ids);
        if(!enqueue(s,10,&b))return false;
        s->announce=2;
    } else {
        num(&b,1,s->revision);
        for(unsigned i=0;i<SK_CHANNELS;i++) {
            buf c={0};num(&c,1,i+10);num(&c,2,(s->enabled>>i)&1);
            num(&c,3,(s->enabled&(1u<<i))?(i<4?4*SK_GAS_SLOT_MS*1000000:1000000000):0);sub(&b,2,&c);
        }
        if(!enqueue(s,11,&b))return false;
        s->announce=0;
    }return true;
}
static void sample(sk_state *s,unsigned i,uint64_t ms,uint8_t quality,const sk_raw *raw) {
    buf r={0},t={0},a={0},b={0};num(&a,1,s->sequence[i]++);
    num(&t,1,2);num(&t,2,ms*1000000);sub(&a,2,&t);num(&a,3,quality);
    if(quality!=2) {
        if(i<4) { num(&r,1,((uint32_t)raw->counts<<1) ^ (0u-(raw->counts<0)));num(&r,2,raw->counter);sub(&a,16,&r); }
        else { bytes(&r,1,raw->data,i==4?32:6);if(i==6)bytes(&r,2,raw->trim,21);sub(&a,(uint8_t)(i+13),&r); }
    }
    num(&b,1,i+10);num(&b,2,s->revision);sub(&b,3,&a);
    /* Physical conversion loss is unknown. Never emit an invented zero. */
    if(!enqueue(s,12,&b))s->dropped++;
}
void sk_tick(sk_state *s,uint64_t ms) {
    if(!s->powered || !s->boot || ms<s->ready)return;
    if(!s->initialized) {
        s->enabled=sk_configure();
        if(!s->powered) { sk_power(false);return; }
        s->initialized=true;
        if(s->connected) { s->revision++;s->announce=1; }
        s->pending=0x80;
        ms=sk_clock();s->gas_slot=0;s->gas_due=ms+SK_GAS_SLOT_MS;
        for(unsigned i=0;i<SK_CHANNELS;i++)s->next[i]=ms+(i<4?SK_GAS_SLOT_MS*(i+1):1000);
    }
    while(s->announce)if(!handshake(s))return;
    if(s->connected && s->pending && s->count<SK_QUEUE) {
        buf b={0};unsigned i=0;while(!(s->pending&(1u<<i)))i++;
        const char *text=i==7?"Configured; warmup and unavailable conversions are missing":"Sensor I/O failed; three errors latch until USB power reset";
        num(&b,1,i==7?0:i+10);num(&b,2,i==7?1:3);bytes(&b,4,text,strlen(text));
        if(enqueue(s,13,&b))s->pending&=(uint8_t)~(1u<<i);
    }
    for(unsigned i=0;i<SK_CHANNELS;i++) {
        ms=sk_clock();
        if(!(s->enabled&(1u<<i)) || ms<s->next[i])continue;
        /* One shared converter: a late loop must never catch up by restarting
         * several single shots back-to-back. Preserve channel order and allow
         * a complete conversion after each mux change. */
        if(i<4 && (i!=s->gas_slot || ms<s->gas_due))continue;
        uint64_t period=i<4?4*SK_GAS_SLOT_MS:1000;
        sk_raw raw={0};uint8_t q=s->faults[i]>=3?2:sk_read((uint8_t)(i+10),&raw);
        if(q==0)continue; /* Nonblocking conversion; keep original deadline. */
        s->sequence[i]+=(ms-s->next[i])/period;s->next[i]=ms+period;
        if(i<4) { s->gas_slot=(i+1)%4;s->gas_due=sk_clock()+SK_GAS_SLOT_MS; }
        if(!s->powered)return;
        if(q==4) {
            if(s->faults[i]<3)s->faults[i]++;
            s->pending|=(uint8_t)(1u<<i);q=2;
            /* A failed multiplexed ADC is one device, not four independent
             * converters. Stop all four channels together to preserve order. */
            if(i<4 && s->faults[i]==3)for(unsigned j=0;j<4;j++)s->faults[j]=3;
        }
        else if(q!=2)s->faults[i]=0;
        if((i<4 && ms-s->started<60000) || (i==4 && ms-s->started<30000))q=2;
        if(s->connected)sample(s,i,ms,q,&raw);
        else s->sequence[i]++;
    }
}
const uint8_t *sk_tx(sk_state *s,uint16_t *length) { if(!s->count)return NULL;*length=s->lengths[s->head];return s->frames[s->head]; }
void sk_tx_done(sk_state *s) { if(s->count) { s->head=(s->head+1)%SK_QUEUE;s->count--; } }
