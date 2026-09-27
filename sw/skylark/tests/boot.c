/* SPDX-License-Identifier: GPL-3.0-only -- power-cut journal fixture. */
#include "boot.h"
#include <assert.h>
#include <setjmp.h>
#include <string.h>
static uint32_t pages[1024];
static int cut,steps;
static jmp_buf power_loss;
static void step(void) { if(cut && ++steps==cut)longjmp(power_loss,1); }
static void erase(unsigned page) {
    /* Interrupt the erase at every word too; the other page must survive. */
    for(unsigned i=0;i<512;i++) { pages[page*512+i]=0xffffffff;step(); }
}
static void program(unsigned word,uint32_t value) {
    pages[word]&=value|0xffff0000;step();
    pages[word]&=value|0x0000ffff;step();
}
int main(void) {
    memset(pages,255,sizeof pages);
    for(unsigned i=1;i<=800;i++)assert(sk_boot_next(pages,erase,program)==i);
    uint32_t saved[1024];memset(pages,255,sizeof pages);
    for(unsigned i=1;i<=256;i++)assert(sk_boot_next(pages,erase,program)==i);
    memcpy(saved,pages,sizeof pages);
    for(int fault=1;fault<=516;fault++) {
        memcpy(pages,saved,sizeof pages);steps=0;cut=fault;
        if(!setjmp(power_loss))sk_boot_next(pages,erase,program);
        cut=0;uint32_t next=sk_boot_next(pages,erase,program);
        assert(next==257 || next==258);assert(sk_boot_next(pages,erase,program)>next);
    }
    memset(pages,255,sizeof pages);pages[0]=0xfffffffe;pages[1]=1;
    assert(sk_boot_next(pages,erase,program)==0);
    return 0;
}
