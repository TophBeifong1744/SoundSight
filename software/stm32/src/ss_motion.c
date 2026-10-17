#include "ss_motion.h"
#include "fpga_link_internal.h"
#include <string.h>

static int valid(const ss_motion_t *m) { return m != NULL && m->initialized != 0U; }
static uint32_t now(const ss_motion_t *m) { return m->link->bus.now_ms(m->link->bus.user); }
static void report_clear(ss_motion_t *m)
{
    m->outcome=SS_MOTION_NONE; m->report_frame=0U; m->report_target=0U;
    m->commit_attempted=0U; m->commit_transfer_completed=0U; m->consume_completed=0U;
}
static ss_status_t error(ss_motion_t *m, ss_status_t s)
{
    m->state=SS_MOTION_FAULT;
    if (m->first_error==SS_OK) m->first_error=s;
    m->last_error=s;
    m->outcome=m->commit_attempted!=0U ? SS_MOTION_UNCERTAIN : SS_MOTION_ERROR;
    /* S2 already tried one revoke on transport error: never retry it here. */
    if (m->link->recovery_required==0U) (void)ss_link_fail(m->link,s);
    return s;
}
#define TRY(call) do { ss_status_t v_=(call); if(v_!=SS_OK) return v_; } while(0)
static ss_status_t faults(ss_motion_t *m, uint32_t t)
{
    TRY(ss_link_read_at(m->link,t,REG_FAULT_STATUS,&m->link->faults));
    if ((m->link->faults & ~FAULT_DEFINED_MASK)!=0U) return SS_WIRE_FORMAT;
    return m->link->faults==0U ? SS_OK : SS_DEVICE_FAULT;
}
static ss_status_t real_mode(ss_motion_t *m,uint32_t t)
{
    uint32_t v;
    TRY(ss_link_read_at(m->link,t,REG_SYS_CTRL,&v));
    return v==(SYS_CTRL_ENABLE|SYS_CTRL_LITE_DEBUG_MODE) ? SS_OK : SS_DEVICE_FAULT;
}
static ss_status_t permit(ss_motion_t *m,uint32_t t,uint32_t expected)
{
    uint32_t v;
    TRY(ss_link_read_at(m->link,t,REG_ACT_CTRL,&v));
    return v==expected ? SS_OK : SS_DEVICE_FAULT;
}
static ss_status_t snapshot(ss_motion_t *m,uint32_t t,int require_lock)
{
    uint32_t s, id;
    uint32_t required=SNAP_STATUS_PROFILE_SUPPORTED|SNAP_STATUS_ACTUATOR_BOUND;
    TRY(ss_link_read_at(m->link,t,REG_SNAP_STATUS,&s));
    if ((s & ~SNAP_STATUS_DEFINED_MASK)!=0U) return SS_WIRE_FORMAT;
    if ((s & required)!=required || (s & (SNAP_STATUS_DRAINING|SNAP_STATUS_GAP))!=0U)
        return SS_DEVICE_FAULT;
    if (require_lock!=0) {
        required|=SNAP_STATUS_LOCKED|SNAP_STATUS_ALL_TERMINAL|SNAP_STATUS_MOTION_PERMIT;
        if ((s & required)!=required || (s & (SNAP_STATUS_BIST|SNAP_STATUS_ENERGY_VALID|
            SNAP_STATUS_REAL_ENERGY_CAP|SNAP_STATUS_FRAME_CANCELLED|SNAP_STATUS_FIRST_ERROR_MASK))!=0U)
            return SS_DEVICE_FAULT;
        TRY(ss_link_read_at(m->link,t,REG_FRAME_CNT,&id));
        if (id!=m->report_frame || m->link->locked==0U || m->link->locked_id!=id)
            return SS_STALE_FRAME;
    }
    return SS_OK;
}
static ss_status_t revoke(ss_motion_t *m,uint32_t t)
{
    uint32_t v;
    TRY(ss_link_motion_write_at(m->link,t,REG_ACT_CTRL,ACT_CTRL_REVOKE));
    TRY(permit(m,t,0U));
    TRY(ss_link_motion_write_at(m->link,t,REG_WATCHDOG_TICKS,0U));
    TRY(ss_link_read_at(m->link,t,REG_WATCHDOG_TICKS,&v));
    return v==0U ? SS_OK : SS_DEVICE_FAULT;
}
int ss_motion_build_enabled(void) { return SS_ENABLE_MOTION_WRITES; }
ss_status_t ss_motion_init(ss_motion_t *m,ss_link_t *l,const ss_motion_config_t *config)
{
    doa_servo_result_t mapped;
    ss_motion_config_t c;
    if (m==NULL || l==NULL || config==NULL) return SS_ARGUMENT;
    c=*config; memset(m,0,sizeof(*m));
    if (l->bus.now_ms==NULL || l->bus.transfer==NULL ||
        l->bus.transfer_timeout_ms==0U || l->bus.transfer_timeout_ms>=UINT32_C(0x80000000) ||
        l->bus.operation_timeout_ms==0U || l->bus.operation_timeout_ms>=UINT32_C(0x80000000) ||
        c.allow_submission>1U ||
        c.watchdog_ticks==0U || c.max_frame_hold_ms==0U ||
        c.max_frame_hold_ms>=UINT32_C(0x80000000)) return SS_ARGUMENT;
    (void)doa_map_angle_q8(0,&c.servo,&mapped);
    if (mapped.config_legal==0U || c.servo.servo_max>511U) return SS_ARGUMENT;
    m->link=l; m->config=c; m->initialized=1U;
    return SS_OK;
}
static ss_status_t arm_inner(ss_motion_t *m,uint32_t t)
{
    uint32_t v;
    if(m->link->locked!=0U) return SS_BUSY;
    TRY(real_mode(m,t)); TRY(faults(m,t)); TRY(snapshot(m,t,0));
    TRY(revoke(m,t));
    TRY(ss_link_motion_write_at(m->link,t,REG_WATCHDOG_TICKS,m->config.watchdog_ticks));
    TRY(ss_link_read_at(m->link,t,REG_WATCHDOG_TICKS,&v));
    if(v!=m->config.watchdog_ticks) return SS_DEVICE_FAULT;
    TRY(ss_link_motion_write_at(m->link,t,REG_ACT_CTRL,ACT_CTRL_PERMIT));
    TRY(permit(m,t,ACT_CTRL_PERMIT)); TRY(faults(m,t));
    return SS_OK;
}
ss_status_t ss_motion_arm(ss_motion_t *m)
{
    ss_status_t s;
    if(!valid(m)) return SS_ARGUMENT;
    if(m->state==SS_MOTION_FAULT || m->link->recovery_required!=0U) return SS_RECOVERY_REQUIRED;
    if(m->state!=SS_MOTION_DISARMED) return SS_BUSY;
    report_clear(m);
    if(ss_motion_build_enabled()==0 || m->config.allow_submission==0U) {
        m->outcome=SS_MOTION_GATE_CLOSED; return SS_ARGUMENT;
    }
    s=arm_inner(m,now(m));
    if(s!=SS_OK) return error(m,s);
    m->state=SS_MOTION_ARMED; m->stop_attempted=0U;
    return SS_OK;
}
ss_status_t ss_motion_disarm(ss_motion_t *m)
{
    ss_status_t s;
    if(!valid(m)) return SS_ARGUMENT;
    /* An existing quarantine is only cleared by explicit recover. */
    if(m->state==SS_MOTION_FAULT || m->link->recovery_required!=0U) return SS_RECOVERY_REQUIRED;
    m->state=SS_MOTION_DISARMED;
    s=revoke(m,now(m));
    return s==SS_OK ? SS_OK : error(m,s);
}
ss_status_t ss_motion_stop(ss_motion_t *m)
{
    ss_status_t s;
    if(!valid(m)) return SS_ARGUMENT;
    if(m->stop_attempted!=0U) return m->stop_result;
    m->stop_attempted=1U; m->state=SS_MOTION_DISARMED;
    s=ss_stop(m->link); m->stop_result=s;
    if(s!=SS_OK) return error(m,s);
    if(m->link->recovery_required!=0U) m->state=SS_MOTION_FAULT;
    return SS_OK;
}
ss_status_t ss_motion_recover(ss_motion_t *m)
{
    ss_status_t s;
    if(!valid(m)) return SS_ARGUMENT;
    m->state=SS_MOTION_DISARMED;
    s=ss_recover(m->link);
    if(s==SS_OK && m->link->faults!=0U) s=SS_DEVICE_FAULT;
    if(s!=SS_OK) return error(m,s);
    m->stop_attempted=0U;
    return SS_OK; /* report and attempted-frame fence intentionally survive */
}
static ss_status_t poll_inner(ss_motion_t *m,uint32_t t,doa_frame_input_t *f,doa_solve_output_t *r)
{
    uint32_t v,word,elapsed;
    TRY(real_mode(m,t)); TRY(faults(m,t)); TRY(permit(m,t,ACT_CTRL_PERMIT));
    TRY(ss_link_acquire_at(m->link,t,f));
    m->report_frame=f->frame_id;
    if(m->have_attempted!=0U && f->frame_id<=m->last_attempted_frame) return SS_STALE_FRAME;
    m->link->solver_status=doa_solve(f,&m->config.servo,r);
    if(m->link->solver_status!=DOA_OK) return SS_SOLVER_ERROR;
    if(r->servo_cmd_valid==0U) {
        m->state=SS_MOTION_DISARMED;
        TRY(revoke(m,t));
        TRY(ss_link_finish_at(m->link,t,SS_CONSUME));
        m->consume_completed=1U; m->outcome=SS_MOTION_REJECTED;
        return SS_OK;
    }
    m->report_target=r->horizontal_servo_deg;
    TRY(snapshot(m,t,1)); TRY(real_mode(m,t)); TRY(faults(m,t));
    TRY(permit(m,t,ACT_CTRL_PERMIT));
    TRY(ss_link_read_at(m->link,t,REG_WATCHDOG_TICKS,&v));
    if(v!=m->config.watchdog_ticks) return SS_DEVICE_FAULT;
    word=ACTUATOR_HORIZONTAL_VALID | (uint32_t)r->horizontal_servo_deg;
    TRY(ss_link_motion_write_at(m->link,t,REG_ACTUATOR_CMD,word));
    TRY(ss_link_read_at(m->link,t,REG_ACTUATOR_CMD,&v));
    if(v!=word) return SS_DEVICE_FAULT;
    TRY(snapshot(m,t,1)); TRY(faults(m,t)); TRY(permit(m,t,ACT_CTRL_PERMIT));
    elapsed=now(m)-t;
    /* Reserve a full transfer timeout before attempting COMMIT. The frozen
     * frame has no capture timestamp: this bounds host hold time only. */
    if(elapsed>=m->config.max_frame_hold_ms ||
       m->link->bus.transfer_timeout_ms>=m->config.max_frame_hold_ms-elapsed ||
       elapsed>=m->link->bus.operation_timeout_ms ||
       m->link->bus.transfer_timeout_ms>=m->link->bus.operation_timeout_ms-elapsed)
        return SS_TIMEOUT;
    m->last_attempted_frame=f->frame_id; m->have_attempted=1U; m->commit_attempted=1U;
    TRY(ss_link_motion_write_at(m->link,t,REG_ACT_CTRL,ACT_CTRL_COMMIT));
    m->commit_transfer_completed=1U;
    TRY(faults(m,t)); TRY(permit(m,t,ACT_CTRL_PERMIT));
    TRY(ss_link_finish_at(m->link,t,SS_CONSUME));
    m->consume_completed=1U; m->outcome=SS_MOTION_SUBMITTED_UNCONFIRMED;
    return SS_OK;
}
ss_status_t ss_motion_poll(ss_motion_t *m,doa_frame_input_t *f,doa_solve_output_t *r)
{
    ss_status_t s;
    doa_frame_input_t frame;
    doa_solve_output_t result;
    if(f!=NULL) memset(f,0,sizeof(*f));
    if(r!=NULL) memset(r,0,sizeof(*r));
    if(!valid(m) || f==NULL || r==NULL) return SS_ARGUMENT;
    if(m->state==SS_MOTION_FAULT || m->link->recovery_required!=0U) return SS_RECOVERY_REQUIRED;
    if(m->state!=SS_MOTION_ARMED) return SS_BUSY;
    report_clear(m);
    memset(&frame,0,sizeof(frame)); memset(&result,0,sizeof(result));
    s=poll_inner(m,now(m),&frame,&result);
    if(s==SS_NO_FRAME) { m->outcome=SS_MOTION_EMPTY; return s; }
    if(s!=SS_OK) return error(m,s);
    *f=frame; *r=result;
    return SS_OK;
}
