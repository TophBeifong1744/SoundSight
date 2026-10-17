#include "ss_runtime.h"
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
#include "ss_spatial.h"
#endif
#include <string.h>

static int valid(const ss_runtime_t *r) { return r != NULL && r->initialized != 0U; }
static int interval(uint32_t v) { return v != 0U && v < UINT32_C(0x80000000); }
static uint32_t now(const ss_runtime_t *r) { return r->link.bus.now_ms(r->link.bus.user); }
static void increment(uint32_t *v) { if (*v != UINT32_MAX) ++*v; }
static void clear_result(ss_runtime_t *r)
{
    r->fresh_result = 0U;
    memset(&r->frame, 0, sizeof(r->frame));
    memset(&r->result, 0, sizeof(r->result));
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
    memset(&r->spatial_result,0,sizeof(r->spatial_result));
#endif
}
static void transition(ss_runtime_t *r, ss_runtime_state_t state)
{ r->state = state; r->state_since_ms = now(r); r->poll_pending = 1U; }
static ss_runtime_event_t fault(ss_runtime_t *r, ss_status_t error)
{
    clear_result(r);
    if (r->first_error == SS_OK) r->first_error = error;
    r->last_error = error;
    r->producer_idle_observed = 0U;
    increment(&r->errors);
    transition(r, SS_RT_FAULT);
    return SS_RT_ERROR;
}
static int poll_due(ss_runtime_t *r)
{
    uint32_t t = now(r);
    if (r->poll_pending == 0U && t - r->last_poll_ms < r->config.poll_interval_ms)
        return 0;
    r->poll_pending = 0U;
    return 1;
}
static ss_status_t read_faults(ss_runtime_t *r)
{
    ss_status_t s = ss_read_register(&r->link, REG_FAULT_STATUS, &r->link.faults);
    if (s != SS_OK) return s;
    if ((r->link.faults & ~FAULT_DEFINED_MASK) != 0U) return SS_WIRE_FORMAT;
    return r->link.faults == 0U ? SS_OK : SS_DEVICE_FAULT;
}
ss_status_t ss_runtime_init(ss_runtime_t *r, const ss_bus_t *bus,
                            const ss_runtime_config_t *config)
{
    ss_bus_t b;
    ss_runtime_config_t c;
    ss_status_t s;
    if (r == NULL || bus == NULL || config == NULL) return SS_ARGUMENT;
    b = *bus; c = *config;
    memset(r, 0, sizeof(*r));
    if (!interval(c.poll_interval_ms) || !interval(c.start_timeout_ms) ||
        !interval(c.drain_timeout_ms)) return SS_ARGUMENT;
    s = ss_init(&r->link, &b);
    if (s != SS_OK) return s;
    r->config = c; r->initialized = 1U;
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
    doa3d_default_config(&r->spatial_config);
#endif
    transition(r, SS_RT_IDLE);
    return SS_OK;
}
ss_status_t ss_runtime_start(ss_runtime_t *r, ss_run_t mode)
{
    if (!valid(r)) return SS_ARGUMENT;
    clear_result(r);
    if (mode != SS_RUN_REAL && mode != SS_RUN_BIST_REJECT && mode != SS_RUN_BIST_PASS)
        return SS_ARGUMENT;
    if (r->state != SS_RT_IDLE && r->state != SS_RT_STOPPED) return SS_BUSY;
    if (r->link.recovery_required != 0U) return SS_RECOVERY_REQUIRED;
    r->mode = mode; r->resume_allowed = 0U;
    r->stop_attempted = 0U; r->stop_sent = 0U; r->producer_idle_observed = 0U;
    transition(r, SS_RT_PROBING);
    return SS_OK;
}
ss_status_t ss_runtime_stop(ss_runtime_t *r)
{
    if (!valid(r)) return SS_ARGUMENT;
    clear_result(r); r->resume_allowed = 0U;
    if (r->state == SS_RT_STOPPING || r->state == SS_RT_DRAINING ||
        r->state == SS_RT_STOPPED || r->stop_attempted != 0U) return SS_OK;
    r->producer_idle_observed = 0U;
    transition(r, SS_RT_STOPPING);
    return SS_OK;
}
ss_status_t ss_runtime_recover(ss_runtime_t *r)
{
    if (!valid(r)) return SS_ARGUMENT;
    clear_result(r);
    if (r->state != SS_RT_FAULT && r->state != SS_RT_STOPPED) return SS_BUSY;
    r->producer_idle_observed = 0U;
    transition(r, SS_RT_RECOVERING);
    return SS_OK;
}
ss_status_t ss_runtime_resume(ss_runtime_t *r)
{
    if (!valid(r)) return SS_ARGUMENT;
    clear_result(r);
    if (r->state != SS_RT_IDLE || r->resume_allowed == 0U) return SS_BUSY;
    if (r->link.recovery_required != 0U) return SS_RECOVERY_REQUIRED;
    transition(r, SS_RT_RESUMING);
    return SS_OK;
}
ss_runtime_event_t ss_runtime_step(ss_runtime_t *r)
{
    ss_status_t s;
    uint32_t ctrl, snap, expected, bist;
    if (!valid(r)) return SS_RT_ERROR;
    clear_result(r);
    switch (r->state) {
    case SS_RT_IDLE: case SS_RT_STOPPED: case SS_RT_FAULT:
        return SS_RT_NONE;
    case SS_RT_PROBING:
        if (now(r) - r->state_since_ms >= r->config.start_timeout_ms)
            return fault(r, SS_TIMEOUT);
        s = ss_probe(&r->link);
        if (s != SS_OK) return fault(r, s);
        if (now(r) - r->state_since_ms >= r->config.start_timeout_ms)
            return fault(r, SS_TIMEOUT);
        /* Keep the original startup deadline across probing and BUSY waits. */
        r->state = SS_RT_STARTING; r->poll_pending = 1U;
        return SS_RT_STATE_CHANGED;
    case SS_RT_STARTING:
        if (now(r) - r->state_since_ms >= r->config.start_timeout_ms)
            return fault(r, SS_TIMEOUT);
        if (!poll_due(r)) return SS_RT_NONE;
        s = ss_start(&r->link, r->mode); r->last_poll_ms = now(r);
        if (s != SS_OK && s != SS_BUSY) return fault(r, s);
        if (now(r) - r->state_since_ms >= r->config.start_timeout_ms)
            return fault(r, SS_TIMEOUT);
        if (s == SS_BUSY) return SS_RT_NONE;
        r->resume_allowed = 1U;
        transition(r, SS_RT_RUNNING);
        return SS_RT_STATE_CHANGED;
    case SS_RT_RUNNING:
        /* An app-side statistics read can quarantine the link within the same
         * millisecond. Fault must take precedence over polling throttling. */
        if (r->link.recovery_required != 0U)
            return fault(r,r->link.last_error!=SS_OK?r->link.last_error:SS_RECOVERY_REQUIRED);
        if (!poll_due(r)) return SS_RT_NONE;
        s = read_faults(r);
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
        if (s == SS_OK) s = ss_spatial_poll(&r->link,&r->spatial_config,&r->frame,&r->spatial_result);
#else
        if (s == SS_OK) s = ss_poll_solve(&r->link, NULL, &r->frame, &r->result);
#endif
        r->last_poll_ms = now(r);
        if (s == SS_NO_FRAME) { increment(&r->empty_polls); return SS_RT_NONE; }
        if (s != SS_OK) return fault(r, s);
        increment(&r->frames); r->fresh_result = 1U;
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
        if (r->spatial_result.direction_valid != 0U) return SS_RT_FRAME_VALID;
#else
        if (r->result.direction_valid != 0U) return SS_RT_FRAME_VALID;
#endif
        increment(&r->rejected_frames);
        return SS_RT_FRAME_REJECTED;
    case SS_RT_STOPPING:
        r->stop_attempted = 1U;
        if (r->link.identity_verified == 0U) {
            if (r->link.recovery_required != 0U) return fault(r, SS_RECOVERY_REQUIRED);
            transition(r, SS_RT_STOPPED); /* Host only; no write to unknown target. */
            return SS_RT_STATE_CHANGED;
        }
        s = ss_stop(&r->link);
        if (s != SS_OK) return fault(r, s);
        r->stop_sent = 1U;
        if (r->link.recovery_required != 0U) return fault(r, SS_RECOVERY_REQUIRED);
        s = ss_disable(&r->link);
        if (s != SS_OK) return fault(r, s);
        r->state = SS_RT_DRAINING; r->poll_pending = 1U;
        return SS_RT_STATE_CHANGED;
    case SS_RT_DRAINING:
        if (now(r) - r->state_since_ms >= r->config.drain_timeout_ms)
            return fault(r, SS_TIMEOUT);
        if (!poll_due(r)) return SS_RT_NONE;
        s = ss_read_register(&r->link, REG_SYS_CTRL, &ctrl);
        if (s != SS_OK) return fault(r, s);
        s = ss_read_register(&r->link, REG_SNAP_STATUS, &snap);
        r->last_poll_ms = now(r);
        if (s != SS_OK) return fault(r, s);
        if ((ctrl & ~SYS_CTRL_WRITE_MASK) != 0U ||
            (ctrl & SYS_CTRL_LITE_DEBUG_MODE) == 0U ||
            (snap & ~SNAP_STATUS_DEFINED_MASK) != 0U ||
            (snap & SNAP_STATUS_PROFILE_SUPPORTED) == 0U)
            return fault(r, SS_WIRE_FORMAT);
        if (now(r) - r->state_since_ms >= r->config.drain_timeout_ms)
            return fault(r, SS_TIMEOUT);
        if ((ctrl & SYS_CTRL_ENABLE) != 0U || (snap & SNAP_STATUS_DRAINING) != 0U)
            return SS_RT_NONE;
        r->producer_idle_observed = 1U;
        transition(r, SS_RT_STOPPED);
        return SS_RT_STATE_CHANGED;
    case SS_RT_RECOVERING:
        s = ss_recover(&r->link);
        if (s != SS_OK) return fault(r, s);
        if (r->link.faults != 0U) return fault(r, SS_DEVICE_FAULT);
        increment(&r->recoveries);
        transition(r, SS_RT_IDLE); /* No implicit restart or consumption. */
        return SS_RT_STATE_CHANGED;
    case SS_RT_RESUMING:
        s = read_faults(r);
        if (s != SS_OK) return fault(r, s);
        s = ss_read_register(&r->link, REG_SYS_CTRL, &ctrl);
        if (s != SS_OK) return fault(r, s);
        expected = SYS_CTRL_ENABLE | SYS_CTRL_LITE_DEBUG_MODE |
            (r->mode == SS_RUN_REAL ? UINT32_C(0) : SYS_CTRL_BIST_MODE);
        if (ctrl != expected) return fault(r, SS_DEVICE_FAULT);
        if (r->mode != SS_RUN_REAL) {
            s = ss_read_register(&r->link, REG_BIST_SELECT, &bist);
            if (s != SS_OK) return fault(r, s);
            if (bist != (r->mode == SS_RUN_BIST_PASS ? BIST_SELECT_PASS : BIST_SELECT_REJECT))
                return fault(r, SS_DEVICE_FAULT);
        }
        transition(r, SS_RT_RUNNING);
        return SS_RT_STATE_CHANGED;
    default:
        return fault(r, SS_ARGUMENT);
    }
}
