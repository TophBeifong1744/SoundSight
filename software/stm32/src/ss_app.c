#include "ss_app.h"
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
#include "ss_spatial.h"
#endif
#include <string.h>
static int valid(const ss_app_t *a) { return a!=NULL && a->initialized!=0U; }
static uint32_t now(const ss_app_t *a) { return a->runtime.link.bus.now_ms(a->runtime.link.bus.user); }
static int config_ok(const ss_app_config_t *c)
{ return c!=NULL && c->max_frames>=1U && c->max_frames<=4096U &&
    c->duration_ms>=1U && c->duration_ms<=60000U && c->print_every>=1U && c->print_every<=4096U; }
ss_status_t ss_app_parse_config(const char *text,ss_app_config_t *out)
{
    uint32_t v[3]; unsigned int i;
    if(text==NULL || out==NULL) return SS_ARGUMENT;
    memset(out,0,sizeof(*out));
    for(i=0U;i<3U;++i) {
        uint32_t n=0U; unsigned int digits=0U;
        while(*text==' ') ++text;
        while(*text>='0' && *text<='9') {
            uint32_t d=(uint32_t)(*text-'0');
            if(n>(UINT32_MAX-d)/10U || ++digits>10U) return SS_ARGUMENT;
            n=n*10U+d; ++text;
        }
        if(digits==0U || (*text!=' ' && *text!='\0')) return SS_ARGUMENT;
        v[i]=n;
    }
    while(*text==' ') ++text;
    if(*text!='\0') return SS_ARGUMENT;
    { ss_app_config_t c; c.max_frames=v[0]; c.duration_ms=v[1]; c.print_every=v[2];
      if(!config_ok(&c)) return SS_ARGUMENT;
      *out=c; }
    return SS_OK;
}
ss_status_t ss_app_init(ss_app_t *a,const ss_bus_t *bus)
{
    const ss_runtime_config_t rt={1U,1000U,500U};
    const ss_motion_config_t motion={{1U,23040,1,-23040,23040,0U,180U,180U},6144000U,80U,0U};
    ss_status_t s;
    if(a==NULL) return SS_ARGUMENT;
    memset(a,0,sizeof(*a));
    s=ss_runtime_init(&a->runtime,bus,&rt); if(s!=SS_OK) return s;
    s=ss_motion_init(&a->motion,&a->runtime.link,&motion); if(s!=SS_OK) return s;
    a->config.max_frames=8U; a->config.duration_ms=2000U; a->config.print_every=4U;
    a->initialized=1U; return SS_OK;
}
ss_status_t ss_app_configure(ss_app_t *a,const ss_app_config_t *c)
{
    if(!valid(a) || !config_ok(c)) return SS_ARGUMENT;
    if(a->active!=0U) return SS_BUSY;
    a->config=*c; return SS_OK;
}
ss_status_t ss_app_start(ss_app_t *a)
{
    ss_status_t s;
    if(!valid(a)) return SS_ARGUMENT;
    if(a->active!=0U || a->motion.state==SS_MOTION_ARMED) return SS_BUSY;
    s=ss_runtime_start(&a->runtime,SS_RUN_REAL); if(s!=SS_OK) return s;
    a->frames=0U; a->rejected=0U; a->queued=0U; a->drop_count=0U; a->max_step_ms=0U;
    a->last_status=SS_OK; a->active=1U; a->fresh=0U; a->user_stopped=0U; a->started_ms=now(a);
    return SS_OK;
}
static ss_status_t stop_run(ss_app_t *a)
{
    ss_status_t s=SS_OK;
    a->fresh=0U;
    if(a->motion.state==SS_MOTION_ARMED) s=ss_motion_disarm(&a->motion);
    if(s!=SS_OK) a->last_status=s;
    /* STOP is still requested after a failed disarm; no further frames run. */
    return ss_runtime_stop(&a->runtime);
}
ss_status_t ss_app_stop(ss_app_t *a)
{
    if(!valid(a)) return SS_ARGUMENT;
    a->user_stopped=1U;
    if(a->active==0U) a->active=1U; /* allow explicit STOP even after fault */
    return stop_run(a);
}
ss_status_t ss_app_arm(ss_app_t *a)
{
    if(!valid(a)) return SS_ARGUMENT;
    if(a->active==0U || a->runtime.state!=SS_RT_RUNNING) return SS_BUSY;
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
    return SS_ARGUMENT; /* 3D is diagnostic-only, including horizontal motion */
#else
    return ss_motion_arm(&a->motion);
#endif
}
ss_status_t ss_app_recover(ss_app_t *a)
{
    ss_status_t s;
    if(!valid(a)) return SS_ARGUMENT;
    if(a->active!=0U) return SS_BUSY;
    a->fresh=0U;
    s=ss_motion_recover(&a->motion);
    if(s!=SS_OK) { a->last_status=s; return s; }
    if(a->runtime.state==SS_RT_FAULT || a->runtime.state==SS_RT_STOPPED) {
        s=ss_runtime_recover(&a->runtime);
        if(s==SS_OK && ss_runtime_step(&a->runtime)==SS_RT_ERROR) s=a->runtime.last_error;
    }
    a->last_status=s; return s;
}
ss_status_t ss_app_ack_stop(ss_app_t *a)
{
    ss_status_t s;
    if(!valid(a)) return SS_ARGUMENT;
    if(a->active!=0U || a->motion.state==SS_MOTION_ARMED) return SS_BUSY;
    /* Explicit command may unblock transport diagnostics while leaving faults. */
    s=ss_recover(&a->runtime.link);
    if(s==SS_OK) s=ss_disable(&a->runtime.link);
    if(s==SS_OK) s=ss_acknowledge_stop(&a->runtime.link);
    if(s==SS_OK) s=ss_app_recover(a);
    a->last_status=s; return s;
}
ss_status_t ss_app_discard(ss_app_t *a)
{
    ss_status_t s;
    if(!valid(a)) return SS_ARGUMENT;
    if(a->active!=0U || a->motion.state==SS_MOTION_ARMED) return SS_BUSY;
    a->fresh=0U;
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
    memset(&a->result,0,sizeof(a->result));
    s=ss_spatial_poll(&a->runtime.link,&a->runtime.spatial_config,&a->frame,&a->spatial_result);
#else
    s=ss_poll_solve(&a->runtime.link,NULL,&a->frame,&a->result);
#endif
    a->last_status=s; a->fresh=(uint8_t)(s==SS_OK);
    return s;
}
ss_app_event_t ss_app_step(ss_app_t *a)
{
    ss_runtime_event_t event=SS_RT_NONE; ss_status_t s=SS_OK;
    uint32_t t,elapsed;
#if SS_DOA_PROFILE == SS_DOA_PLANAR
    int used_motion=0;
#endif
    if(!valid(a)) return SS_APP_ERROR;
    a->fresh=0U;
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
    memset(&a->spatial_result,0,sizeof(a->spatial_result));
#endif
    if(a->active==0U) return SS_APP_NONE;
    t=now(a);
    if((a->runtime.state==SS_RT_RUNNING || a->runtime.state==SS_RT_STARTING || a->runtime.state==SS_RT_PROBING) &&
       (a->frames>=a->config.max_frames || t-a->started_ms>=a->config.duration_ms)) (void)stop_run(a);
#if SS_DOA_PROFILE == SS_DOA_PLANAR
    if(a->runtime.state==SS_RT_RUNNING && a->motion.state==SS_MOTION_ARMED) {
        used_motion=1;
        s=ss_motion_poll(&a->motion,&a->frame,&a->result);
        if(s==SS_OK) event=a->result.direction_valid!=0U ? SS_RT_FRAME_VALID : SS_RT_FRAME_REJECTED;
        else if(s!=SS_NO_FRAME) {
            (void)ss_runtime_step(&a->runtime); /* quarantined link: no acquire */
            event=SS_RT_ERROR;
        }
    } else
#endif
    {
        event=ss_runtime_step(&a->runtime);
        if(event==SS_RT_ERROR) s=a->runtime.last_error;
        if(event==SS_RT_FRAME_VALID || event==SS_RT_FRAME_REJECTED) {
            a->frame=a->runtime.frame; a->result=a->runtime.result;
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
            a->spatial_result=a->runtime.spatial_result;
#endif
        }
    }
    if(event==SS_RT_FRAME_VALID || event==SS_RT_FRAME_REJECTED) {
        ++a->frames; if(event==SS_RT_FRAME_REJECTED) ++a->rejected;
        if((a->runtime.link.snapshot_status & SNAP_STATUS_QUEUED)!=0U) ++a->queued;
        s=ss_read_register(&a->runtime.link,REG_DROP_COUNT,&a->drop_count);
        if(s!=SS_OK) { (void)ss_runtime_step(&a->runtime); event=SS_RT_ERROR; }
        else a->fresh=1U;
#if SS_DOA_PROFILE == SS_DOA_PLANAR
        if(used_motion && a->motion.outcome==SS_MOTION_REJECTED) {
            (void)stop_run(a); if(event!=SS_RT_ERROR) a->fresh=1U;
        }
#endif
    }
    elapsed=now(a)-t; if(elapsed>a->max_step_ms) a->max_step_ms=elapsed;
    if(event==SS_RT_ERROR || a->runtime.state==SS_RT_FAULT) {
        if(s==SS_OK) s=a->runtime.last_error;
        a->last_status=s; a->active=0U; a->fresh=0U;
        memset(&a->frame,0,sizeof(a->frame)); memset(&a->result,0,sizeof(a->result));
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
        memset(&a->spatial_result,0,sizeof(a->spatial_result));
#endif
        return SS_APP_ERROR;
    }
    if(a->runtime.state==SS_RT_STOPPED) {
        a->active=0U; return SS_APP_ENDED;
    }
    return a->fresh!=0U ? SS_APP_FRAME : SS_APP_NONE;
}
