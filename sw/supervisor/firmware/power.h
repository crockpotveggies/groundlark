/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef GL_POWER_H
#define GL_POWER_H
#include <stdint.h>
#include <stdbool.h>
typedef struct {
    bool enabled;
    uint32_t shutdown_mv, restart_mv, shutdown_confirm_ms, restart_confirm_ms;
    uint32_t shutdown_timeout_ms, minimum_off_ms;
} power_policy;
typedef enum {POWER_OFF, POWER_RUN, POWER_SHUTDOWN, POWER_LATCHED} power_mode;
typedef struct {
    power_policy policy;
    power_mode mode;
    uint64_t since, condition_since, previous;
    bool condition, run, request;
    unsigned timeouts;
} power_state;
bool power_valid(const power_policy *policy);
void power_init(power_state *state, const power_policy *policy, uint64_t ms);
void power_tick(power_state *state, uint64_t ms, bool valid, uint32_t mv, bool halted);
#endif
