/* SPDX-License-Identifier: MIT */
#include "power.h"
#include <assert.h>
static const power_policy policy={true,11000,12500,1000,1000,10000,30000};
int main(void) {
    power_state s;power_policy disabled={0};
    power_init(&s,&disabled,0);
    for(unsigned i=0;i<604800;i++)power_tick(&s,(uint64_t)i*1000,true,14000,false);
    assert(!s.run && !s.request);
    power_policy bad=policy;bad.restart_mv=11200;power_init(&s,&bad,0);
    assert(s.mode==POWER_LATCHED && !s.run);
    power_init(&s,&policy,0);
    power_tick(&s,30000,true,14000,true);power_tick(&s,40000,true,14000,true);
    assert(!s.run); /* stale halt acknowledgement cannot start the Pi */
    power_tick(&s,40001,true,14000,false);power_tick(&s,41001,true,14000,false);assert(s.run);
    power_tick(&s,42000,true,10500,false);power_tick(&s,42999,true,14000,false);assert(!s.request);
    power_tick(&s,43000,true,10500,false);power_tick(&s,44000,true,10500,false);assert(s.request&&s.run);
    power_tick(&s,44100,true,14000,true);assert(!s.request&&!s.run);
    power_tick(&s,74100,false,14000,false);power_tick(&s,90000,false,14000,false);assert(!s.run);
    uint64_t t=100000;
    for(unsigned i=0;i<3;i++) {
        power_tick(&s,t,true,14000,false);power_tick(&s,t+1000,true,14000,false);assert(s.run);
        power_tick(&s,t+1001,false,0,false);assert(s.request&&s.run);
        power_tick(&s,t+11001,false,0,false);assert(!s.run);t+=50000;
    }
    assert(s.mode==POWER_LATCHED);
    power_tick(&s,t+604800000,true,14000,false);assert(!s.run);
    power_init(&s,&policy,0);power_tick(&s,30000,true,14000,false);
    power_tick(&s,31000,true,14000,false);assert(s.run);
    power_tick(&s,1,true,14000,false);assert(s.mode==POWER_LATCHED&&!s.run);
    return 0;
}
