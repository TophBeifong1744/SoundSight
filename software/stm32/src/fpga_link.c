#include "fpga_link.h"
#include "fpga_link_internal.h"
#include <string.h>

static int configured(const ss_link_t *l)
{
    return l != NULL && l->bus.transfer != NULL && l->bus.now_ms != NULL &&
        l->bus.transfer_timeout_ms != 0U && l->bus.operation_timeout_ms != 0U;
}
static int known_address(uint32_t a)
{
    switch (a) {
    case REG_MAGIC_ID: case REG_SYS_CTRL: case REG_FRAME_CNT:
    case REG_FEATURE_0: case REG_FEATURE_1: case REG_SIGNAL_ENG:
    case REG_ACTUATOR_CMD: case REG_FEATURE_SELECT: case REG_R_MINUS:
    case REG_R_PLUS: case REG_R_SECOND: case REG_BIST_SELECT:
    case REG_SNAP_STATUS: case REG_SNAP_CMD: case REG_ACT_CTRL:
    case REG_WATCHDOG_TICKS: case REG_FAULT_STATUS: case REG_DROP_COUNT:
    case REG_ABI_VERSION: return 1;
    default: return 0;
    }
}
static ss_status_t transaction(ss_link_t *l, uint32_t start, uint32_t a,
                               int write, uint32_t *v)
{
    uint8_t tx[5] = {0}, rx[5] = {0};
    uint32_t elapsed = l->bus.now_ms(l->bus.user) - start;
    uint32_t timeout, transfer_start;
    ss_bus_status_t s;
    if (elapsed >= l->bus.operation_timeout_ms) return SS_TIMEOUT;
    timeout = l->bus.operation_timeout_ms - elapsed;
    if (timeout > l->bus.transfer_timeout_ms) timeout = l->bus.transfer_timeout_ms;
    tx[0] = (uint8_t)(a | (write != 0 ? FPGA_ABI_WRITE_BIT : UINT32_C(0)));
    if (write != 0) {
        tx[1] = (uint8_t)(*v >> 24); tx[2] = (uint8_t)(*v >> 16);
        tx[3] = (uint8_t)(*v >> 8); tx[4] = (uint8_t)*v;
    }
    transfer_start = l->bus.now_ms(l->bus.user);
    s = l->bus.transfer(l->bus.user, tx, rx, timeout);
    if (s == SS_BUS_TIMEOUT) return SS_TIMEOUT;
    if (s != SS_BUS_OK) return SS_IO_ERROR;
    if (l->bus.now_ms(l->bus.user) - transfer_start >= timeout ||
        l->bus.now_ms(l->bus.user) - start >= l->bus.operation_timeout_ms)
        return SS_TIMEOUT;
    if (write == 0) *v = ((uint32_t)rx[1] << 24) | ((uint32_t)rx[2] << 16) |
                        ((uint32_t)rx[3] << 8) | (uint32_t)rx[4];
    return SS_OK;
}
static ss_status_t rd(ss_link_t *l, uint32_t t, uint32_t a, uint32_t *v)
{ return transaction(l, t, a, 0, v); }
static ss_status_t wr(ss_link_t *l, uint32_t t, uint32_t a, uint32_t v)
{ return transaction(l, t, a, 1, &v); }

/* Separate bounded best-effort revoke, with no retry. Never claim a timeout
 * proves motion stopped; physical safety still depends on PL/watchdog. */
static ss_status_t fail(ss_link_t *l, ss_status_t s)
{
    l->last_error = s;
    l->recovery_required = 1U;
    l->revoke_result = l->identity_verified != 0U ?
        wr(l, l->bus.now_ms(l->bus.user), REG_ACT_CTRL, ACT_CTRL_REVOKE) : SS_NOT_PROBED;
    return s;
}
static ss_status_t ready(const ss_link_t *l)
{
    if (!configured(l)) return SS_ARGUMENT;
    if (l->recovery_required != 0U) return SS_RECOVERY_REQUIRED;
    return l->probed != 0U ? SS_OK : SS_NOT_PROBED;
}
static ss_status_t status_read(ss_link_t *l, uint32_t t, uint32_t *s)
{
    ss_status_t r = rd(l, t, REG_SNAP_STATUS, s);
    if (r != SS_OK) return r;
    l->snapshot_status = *s;
    return (*s & ~SNAP_STATUS_DEFINED_MASK) == 0U ? SS_OK : SS_WIRE_FORMAT;
}
#define TRY_LOCAL(call) do { ss_status_t step = (call); if (step != SS_OK) return step; } while (0)
static ss_status_t probe_inner(ss_link_t *l, uint32_t t)
{
    uint32_t v;
    l->probed = 0U;
    l->identity_verified = 0U;
    TRY_LOCAL(rd(l, t, REG_MAGIC_ID, &v));
    if (v != FPGA_ABI_MAGIC_VALUE) return SS_IDENTITY;
    TRY_LOCAL(rd(l, t, REG_ABI_VERSION, &v));
    if (v != FPGA_ABI_VERSION_VALUE) return SS_IDENTITY;
    l->identity_verified = 1U;
    TRY_LOCAL(wr(l, t, REG_ACT_CTRL, ACT_CTRL_REVOKE));
    TRY_LOCAL(wr(l, t, REG_WATCHDOG_TICKS, 0U));
    TRY_LOCAL(rd(l, t, REG_ACT_CTRL, &v));
    if (v != 0U) return SS_DEVICE_FAULT;
    TRY_LOCAL(rd(l, t, REG_WATCHDOG_TICKS, &v));
    if (v != 0U) return SS_DEVICE_FAULT;
    l->probed = 1U;
    return SS_OK;
}
ss_status_t ss_init(ss_link_t *l, const ss_bus_t *bus)
{
    ss_bus_t copy;
    if (l == NULL || bus == NULL) return SS_ARGUMENT;
    copy = *bus;
    memset(l, 0, sizeof(*l));
    if (copy.transfer == NULL || copy.now_ms == NULL ||
        copy.transfer_timeout_ms == 0U || copy.transfer_timeout_ms >= UINT32_C(0x80000000) ||
        copy.operation_timeout_ms == 0U || copy.operation_timeout_ms >= UINT32_C(0x80000000))
        return SS_ARGUMENT;
    l->bus = copy;
    return SS_OK;
}
ss_status_t ss_probe(ss_link_t *l)
{
    ss_status_t s;
    if (!configured(l)) return SS_ARGUMENT;
    if (l->recovery_required != 0U) return SS_RECOVERY_REQUIRED;
    if (l->locked != 0U) return SS_BUSY;
    s = probe_inner(l, l->bus.now_ms(l->bus.user));
    /* Do not issue writes to an unrecognised device. */
    if (s == SS_IDENTITY) { l->last_error = s; l->recovery_required = 1U; return s; }
    return s == SS_OK ? SS_OK : fail(l, s);
}
ss_status_t ss_read_register(ss_link_t *l, uint32_t a, uint32_t *v)
{
    ss_status_t s;
    if (v == NULL) return SS_ARGUMENT;
    *v = 0U;
    s = ready(l); if (s != SS_OK) return s;
    if (!known_address(a)) return SS_BAD_REGISTER;
    s = rd(l, l->bus.now_ms(l->bus.user), a, v);
    if (s != SS_OK) { *v = 0U; return fail(l, s); }
    return SS_OK;
}
static ss_status_t start_inner(ss_link_t *l, uint32_t t, ss_run_t mode)
{
    uint32_t ctrl, status, v, desired;
    TRY_LOCAL(rd(l, t, REG_SYS_CTRL, &ctrl));
    if ((ctrl & ~SYS_CTRL_WRITE_MASK) != 0U || (ctrl & SYS_CTRL_LITE_DEBUG_MODE) == 0U)
        return SS_WIRE_FORMAT;
    TRY_LOCAL(wr(l, t, REG_SYS_CTRL, ctrl & ~SYS_CTRL_ENABLE));
    TRY_LOCAL(rd(l, t, REG_SYS_CTRL, &v));
    if (v != (ctrl & ~SYS_CTRL_ENABLE)) return SS_DEVICE_FAULT;
    TRY_LOCAL(status_read(l, t, &status));
    if ((status & (SNAP_STATUS_LOCKED | SNAP_STATUS_QUEUED | SNAP_STATUS_DRAINING)) != 0U)
        return SS_BUSY;
    if ((status & SNAP_STATUS_PROFILE_SUPPORTED) == 0U) return SS_WIRE_FORMAT;
    TRY_LOCAL(rd(l, t, REG_FAULT_STATUS, &l->faults));
    if (l->faults != 0U) return SS_DEVICE_FAULT;
    TRY_LOCAL(wr(l, t, REG_ACT_CTRL, ACT_CTRL_REVOKE));
    TRY_LOCAL(wr(l, t, REG_WATCHDOG_TICKS, 0U));
    if (mode != SS_RUN_REAL) {
        desired = mode == SS_RUN_BIST_PASS ? BIST_SELECT_PASS : BIST_SELECT_REJECT;
        TRY_LOCAL(wr(l, t, REG_BIST_SELECT, desired));
        TRY_LOCAL(rd(l, t, REG_BIST_SELECT, &v));
        if (v != desired) return SS_DEVICE_FAULT;
    }
    desired = SYS_CTRL_LITE_DEBUG_MODE | (mode == SS_RUN_REAL ? UINT32_C(0) : SYS_CTRL_BIST_MODE);
    TRY_LOCAL(wr(l, t, REG_SYS_CTRL, desired));
    TRY_LOCAL(rd(l, t, REG_SYS_CTRL, &v));
    if (v != desired) return SS_DEVICE_FAULT;
    desired |= SYS_CTRL_ENABLE;
    TRY_LOCAL(wr(l, t, REG_SYS_CTRL, desired));
    TRY_LOCAL(rd(l, t, REG_SYS_CTRL, &v));
    return v == desired ? SS_OK : SS_DEVICE_FAULT;
}
ss_status_t ss_start(ss_link_t *l, ss_run_t mode)
{
    ss_status_t s = ready(l);
    if (s != SS_OK) return s;
    if (mode != SS_RUN_REAL && mode != SS_RUN_BIST_REJECT && mode != SS_RUN_BIST_PASS)
        return SS_ARGUMENT;
    if (l->locked != 0U) return SS_BUSY;
    s = start_inner(l, l->bus.now_ms(l->bus.user), mode);
    return s == SS_OK || s == SS_BUSY ? s : fail(l, s);
}
ss_status_t ss_stop(ss_link_t *l)
{
    ss_status_t s;
    if (!configured(l)) return SS_ARGUMENT;
    if (l->identity_verified == 0U) return SS_NOT_PROBED;
    /* Allowed during recovery, but does not clear the recovery requirement. */
    s = wr(l, l->bus.now_ms(l->bus.user), REG_ACT_CTRL, ACT_CTRL_STOP);
    if (s != SS_OK) return fail(l, s);
    return SS_OK; /* Transport completed; not a measurement of physical PWM. */
}
static ss_status_t acquire_inner(ss_link_t *l, uint32_t t, doa_frame_input_t *f)
{
    uint32_t status, w, raw_mask = 0U;
    unsigned int i, j;
    const uint32_t addresses[4] = { REG_FEATURE_1, REG_R_MINUS, REG_R_PLUS, REG_R_SECOND };
    if (l->locked != 0U) return SS_BUSY;
    TRY_LOCAL(wr(l, t, REG_SNAP_CMD, SNAP_CMD_ACQUIRE));
    TRY_LOCAL(status_read(l, t, &status));
    if ((status & SNAP_STATUS_PROFILE_SUPPORTED) == 0U) return SS_WIRE_FORMAT;
    if ((status & SNAP_STATUS_LOCKED) == 0U) return SS_NO_FRAME;
    l->locked = 1U;
    if ((status & (SNAP_STATUS_ALL_TERMINAL | SNAP_STATUS_PROFILE_SUPPORTED)) !=
        (SNAP_STATUS_ALL_TERMINAL | SNAP_STATUS_PROFILE_SUPPORTED)) return SS_WIRE_FORMAT;
    if ((status & SNAP_STATUS_BIST) == 0U &&
        (status & (SNAP_STATUS_ENERGY_VALID | SNAP_STATUS_REAL_ENERGY_CAP)) != 0U)
        return SS_WIRE_FORMAT;
    TRY_LOCAL(rd(l, t, REG_FRAME_CNT, &f->frame_id));
    l->locked_id = f->frame_id;
    if (f->frame_id == 0U || (l->have_consumed != 0U && f->frame_id <= l->last_consumed_id))
        return SS_STALE_FRAME;
    f->flags = SNAP_STATUS_GET_FRAME_FLAGS(status);
    for (i = 0; i < DOA_PAIR_COUNT; ++i) {
        doa_pair_input_t *p = &f->pair[i];
        int32_t values[4];
        TRY_LOCAL(wr(l, t, REG_FEATURE_SELECT, (uint32_t)i));
        TRY_LOCAL(rd(l, t, REG_FEATURE_0, &w));
        if ((w & ~FEATURE_0_DEFINED_MASK) != 0U || FEATURE_0_GET_PAIR(w) != i ||
            FEATURE_0_GET_PHAT_STAGE(w) == FPGA_STAGE_PENDING ||
            FEATURE_0_GET_PHAT_STAGE(w) > FPGA_STAGE_SKIPPED ||
            FEATURE_0_GET_IFFT_STAGE(w) == FPGA_STAGE_PENDING ||
            FEATURE_0_GET_IFFT_STAGE(w) > FPGA_STAGE_SKIPPED) return SS_WIRE_FORMAT;
        p->lag = FEATURE_0_GET_LAG(w);
        if (p->lag < -32 || p->lag > 31 || FEATURE_0_GET_MASK_COUNT(w) > 79U)
            return SS_WIRE_FORMAT;
        p->mask_count = (uint8_t)FEATURE_0_GET_MASK_COUNT(w);
        p->flags = FEATURE_0_GET_FLAGS(w);
        if ((w & FEATURE_0_RAW_PEAK_VALID) != 0U) raw_mask |= UINT32_C(1) << i;
        for (j = 0; j < 4U; ++j) {
            TRY_LOCAL(rd(l, t, addresses[j], &w));
            values[j] = fpga_abi_word_to_s32(w);
            if (values[j] < FPGA_ABI_S25_MIN || values[j] > FPGA_ABI_S25_MAX)
                return SS_WIRE_FORMAT;
        }
        p->peak = values[0]; p->r_minus = values[1];
        p->r_plus = values[2]; p->second_peak = values[3];
    }
    if (raw_mask != ((status & SNAP_STATUS_VALID_PAIRS_MASK) >> SNAP_STATUS_VALID_PAIRS_SHIFT))
        return SS_WIRE_FORMAT;
    return SS_OK;
}
ss_status_t ss_acquire_frame(ss_link_t *l, doa_frame_input_t *f)
{
    return ss_link_acquire_at(l, configured(l) ? l->bus.now_ms(l->bus.user) : 0U, f);
}
ss_status_t ss_link_acquire_at(ss_link_t *l, uint32_t t, doa_frame_input_t *f)
{
    ss_status_t s;
    doa_frame_input_t tmp;
    if (f == NULL) return SS_ARGUMENT;
    memset(f, 0, sizeof(*f)); memset(&tmp, 0, sizeof(tmp));
    s = ready(l); if (s != SS_OK) return s;
    s = acquire_inner(l, t, &tmp);
    if (s == SS_OK) { *f = tmp; return SS_OK; }
    return s == SS_NO_FRAME || s == SS_BUSY ? s : fail(l, s);
}
static ss_status_t finish_inner(ss_link_t *l, uint32_t t, ss_finish_t how)
{
    TRY_LOCAL(wr(l, t, REG_SNAP_CMD, how == SS_CONSUME ? SNAP_CMD_CONSUME : SNAP_CMD_RELEASE));
    if (how == SS_CONSUME) {
        l->last_consumed_id = l->locked_id;
        l->have_consumed = 1U;
    }
    l->locked = 0U; l->locked_id = 0U;
    return SS_OK;
}
ss_status_t ss_finish_frame(ss_link_t *l, ss_finish_t how)
{
    return ss_link_finish_at(l, configured(l) ? l->bus.now_ms(l->bus.user) : 0U, how);
}
ss_status_t ss_link_finish_at(ss_link_t *l, uint32_t t, ss_finish_t how)
{
    ss_status_t s = ready(l);
    if (s != SS_OK) return s;
    if ((how != SS_CONSUME && how != SS_RELEASE) || l->locked == 0U) return SS_ARGUMENT;
    s = finish_inner(l, t, how);
    return s == SS_OK ? s : fail(l, s);
}
ss_status_t ss_poll_solve(ss_link_t *l, const doa_servo_config_t *servo,
                          doa_frame_input_t *f, doa_solve_output_t *r)
{
    doa_frame_input_t tmp;
    doa_solve_output_t solved;
    ss_status_t s;
    uint32_t t;
    if (f != NULL) memset(f, 0, sizeof(*f));
    if (r != NULL) memset(r, 0, sizeof(*r));
    if (f == NULL || r == NULL) return SS_ARGUMENT;
    s = ready(l); if (s != SS_OK) return s;
    memset(&tmp, 0, sizeof(tmp));
    t = l->bus.now_ms(l->bus.user);
    s = acquire_inner(l, t, &tmp);
    if (s == SS_NO_FRAME || s == SS_BUSY) return s;
    if (s != SS_OK) return fail(l, s);
    l->solver_status = doa_solve(&tmp, servo, &solved);
    if (l->solver_status != DOA_OK) return fail(l, SS_SOLVER_ERROR);
    s = finish_inner(l, t, SS_CONSUME);
    if (s != SS_OK) return fail(l, s);
    *f = tmp; *r = solved;
    return SS_OK;
}
static ss_status_t recover_inner(ss_link_t *l, uint32_t t)
{
    uint32_t status;
    TRY_LOCAL(probe_inner(l, t));
    TRY_LOCAL(status_read(l, t, &status));
    if ((status & SNAP_STATUS_LOCKED) != 0U) {
        TRY_LOCAL(wr(l, t, REG_SNAP_CMD, SNAP_CMD_RELEASE));
        TRY_LOCAL(status_read(l, t, &status));
        if ((status & SNAP_STATUS_LOCKED) != 0U) return SS_DEVICE_FAULT;
    }
    TRY_LOCAL(rd(l, t, REG_FAULT_STATUS, &l->faults));
    if ((l->faults & ~FAULT_DEFINED_MASK) != 0U) return SS_WIRE_FORMAT;
    l->locked = 0U; l->locked_id = 0U;
    /* Sticky device faults remain observable; diagnostic reads are permitted,
     * but ss_start refuses to enable while any fault remains. */
    l->recovery_required = 0U; l->last_error = SS_OK;
    return SS_OK;
}
ss_status_t ss_recover(ss_link_t *l)
{
    ss_status_t s;
    if (!configured(l)) return SS_ARGUMENT;
    s = recover_inner(l, l->bus.now_ms(l->bus.user));
    if (s == SS_IDENTITY) { l->last_error = s; l->recovery_required = 1U; return s; }
    return s == SS_OK ? s : fail(l, s);
}

ss_status_t ss_link_fail(ss_link_t *l, ss_status_t s)
{ return fail(l, s); }

ss_status_t ss_link_read_at(ss_link_t *l, uint32_t t, uint32_t a, uint32_t *v)
{
    ss_status_t s;
    if (v == NULL) return SS_ARGUMENT;
    *v = 0U;
    s = ready(l); if (s != SS_OK) return s;
    if (!known_address(a)) return SS_BAD_REGISTER;
    s = rd(l, t, a, v);
    if (s != SS_OK) { *v = 0U; return fail(l, s); }
    return SS_OK;
}

ss_status_t ss_link_motion_write_at(ss_link_t *l, uint32_t t, uint32_t a, uint32_t v)
{
    ss_status_t s;
    int safe = (a == REG_ACT_CTRL && (v == ACT_CTRL_REVOKE || v == ACT_CTRL_STOP || v == 0U)) ||
               (a == REG_WATCHDOG_TICKS && v == 0U);
    if (!configured(l)) return SS_ARGUMENT;
    if (safe) {
        if (l->identity_verified == 0U) return SS_NOT_PROBED;
    } else {
        s = ready(l); if (s != SS_OK) return s;
#if SS_ENABLE_MOTION_WRITES == 0
        return SS_ARGUMENT;
#else
        if (a == REG_ACT_CTRL) {
            if (v != ACT_CTRL_PERMIT && v != ACT_CTRL_COMMIT) return SS_ARGUMENT;
        } else if (a == REG_ACTUATOR_CMD) {
            if ((v & ~(ACTUATOR_HORIZONTAL_MASK | ACTUATOR_HORIZONTAL_VALID)) != 0U ||
                (v & ACTUATOR_HORIZONTAL_VALID) == 0U) return SS_ARGUMENT;
        } else if (a != REG_WATCHDOG_TICKS) return SS_BAD_REGISTER;
#endif
    }
    s = wr(l, t, a, v);
    return s == SS_OK ? SS_OK : fail(l, s);
}
