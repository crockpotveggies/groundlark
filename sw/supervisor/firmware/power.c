/* SPDX-License-Identifier: GPL-3.0-only */
#include "power.h"
#include <string.h>
bool power_valid(const power_policy *p) {
    return !p->enabled || (p->shutdown_mv>=8500 && p->shutdown_mv<=17500 &&
        p->restart_mv>=p->shutdown_mv+500 && p->restart_mv<=18000 &&
        p->shutdown_confirm_ms>=1000 && p->shutdown_confirm_ms<=3600000 &&
        p->restart_confirm_ms>=1000 && p->restart_confirm_ms<=3600000 &&
        p->shutdown_timeout_ms>=10000 && p->shutdown_timeout_ms<=300000 &&
        p->minimum_off_ms>=30000 && p->minimum_off_ms<=86400000);
}
static void enter(power_state *s,power_mode mode,uint64_t ms) {
    s->mode=mode;s->since=ms;s->condition=false;
    s->run=mode==POWER_RUN || mode==POWER_SHUTDOWN;
    s->request=mode==POWER_SHUTDOWN;
}
void power_init(power_state *s,const power_policy *p,uint64_t ms) {
    memset(s,0,sizeof *s);s->policy=*p;s->previous=ms;
    enter(s,power_valid(p)?POWER_OFF:POWER_LATCHED,ms);
}
static bool confirmed(power_state *s,bool condition,uint64_t ms,uint32_t duration) {
    if(!condition){s->condition=false;return false;}
    if(!s->condition){s->condition=true;s->condition_since=ms;}
    return ms-s->condition_since>=duration;
}
void power_tick(power_state *s,uint64_t ms,bool valid,uint32_t mv,bool halted) {
    if(ms<s->previous){enter(s,POWER_LATCHED,ms);return;}
    s->previous=ms;
    if(!s->policy.enabled){enter(s,POWER_OFF,ms);return;}
    if(s->mode==POWER_OFF) {
        bool ready=valid && mv>=s->policy.restart_mv && mv<=18000 && !halted &&
                   ms-s->since>=s->policy.minimum_off_ms;
        if(confirmed(s,ready,ms,s->policy.restart_confirm_ms))enter(s,POWER_RUN,ms);
    } else if(s->mode==POWER_RUN) {
        if(halted)enter(s,POWER_OFF,ms);
        else if(!valid || mv<8000 || mv>18000 ||
                confirmed(s,mv<=s->policy.shutdown_mv,ms,s->policy.shutdown_confirm_ms))
            enter(s,POWER_SHUTDOWN,ms);
    } else if(s->mode==POWER_SHUTDOWN) {
        if(halted)enter(s,POWER_OFF,ms);
        else if(ms-s->since>=s->policy.shutdown_timeout_ms) {
            s->timeouts++;
            enter(s,s->timeouts>=3?POWER_LATCHED:POWER_OFF,ms);
        }
    }
}
