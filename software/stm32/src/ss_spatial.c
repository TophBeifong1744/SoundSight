#include "ss_spatial.h"
#include "fpga_link_internal.h"
#include <string.h>
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
#if SS_ENABLE_MOTION_WRITES != 0
#error Three-dimensional diagnostic build must keep motion writes disabled
#endif
ss_status_t ss_spatial_poll(ss_link_t *l,const doa3d_config_t *cfg,
                           doa_frame_input_t *f,doa_dispatch_output_t *o)
{
    doa_frame_input_t input;
    doa_dispatch_output_t result;
    ss_status_t s;
    uint32_t start;
    if(f!=NULL) memset(f,0,sizeof(*f));
    if(o!=NULL) memset(o,0,sizeof(*o));
    if(l==NULL || cfg==NULL || f==NULL || o==NULL ||
       l->bus.now_ms==NULL || l->bus.transfer==NULL) return SS_ARGUMENT;
    start=l->bus.now_ms(l->bus.user);
    s=ss_link_acquire_at(l,start,&input);
    if(s!=SS_OK) return s; /* acquisition already isolates transport errors */
    l->solver_status=doa_dispatch_solve(&input,NULL,cfg,&result);
    if(l->solver_status!=DOA_OK) return ss_link_fail(l,SS_SOLVER_ERROR);
    /* Finish uses acquisition's original start, including solver execution. */
    s=ss_link_finish_at(l,start,SS_CONSUME);
    if(s!=SS_OK) return s;
    *f=input; *o=result;
    return SS_OK;
}
#endif
