/* SPDX-License-Identifier: MIT */
#include "boot.h"
#ifndef BOOT_PAGE_WORDS
#define BOOT_PAGE_WORDS 512
#endif
uint32_t sk_boot_next(const volatile uint32_t *pages,
                     void (*erase)(unsigned),void (*program)(unsigned,uint32_t)) {
    uint32_t best=0;unsigned active=0;
    for(unsigned page=0;page<2;page++)for(unsigned n=0;n<BOOT_PAGE_WORDS/2;n++) {
        const volatile uint32_t *r=pages+page*BOOT_PAGE_WORDS+n*2;
        if(r[0] && r[0]!=0xffffffff && (r[0]^r[1])==0xffffffff && r[0]>best) { best=r[0];active=page; }
    }
    if(best>=0xfffffffe)return 0;
    unsigned slot=0;for(;slot<BOOT_PAGE_WORDS/2;slot++) {
        const volatile uint32_t *r=pages+active*BOOT_PAGE_WORDS+slot*2;
        if(r[0]==0xffffffff && r[1]==0xffffffff)break;
    }
    if(slot==BOOT_PAGE_WORDS/2) { active^=1;slot=0;erase(active); }
    unsigned word=active*BOOT_PAGE_WORDS+slot*2;uint32_t value=best+1;
    program(word,value);program(word+1,~value);
    if(pages[word]!=value || pages[word+1]!=~value)return 0;
    return value;
}
