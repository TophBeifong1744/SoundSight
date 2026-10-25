#include "doa_solver_3d.h"
#include <math.h>
#include <string.h>
static const unsigned int pa[6]={0U,0U,0U,1U,1U,2U};
static const unsigned int pb[6]={1U,2U,3U,2U,3U,3U};
/* Existing PL peak centres; neighbour storage is -9..9. */
static const double scan[6]={6.0,8.0,6.0,6.0,8.0,6.0};
static int finite_range(double v,double lo,double hi) { return v>=lo && v<=hi; }
static int64_t rne(int64_t n,int64_t den)
{
    int64_t a,q,rem;
    if(den<=0)return 0;
    a=n<0?-n:n;q=a/den;rem=a%den;
    if(rem*INT64_C(2)>den || (rem*INT64_C(2)==den && q%INT64_C(2)!=0))++q;
    return n<0?-q:q;
}
static int32_t q8(double degrees)
{
    double a=fabs(degrees)*256.0,base=floor(a),frac=a-base;
    int32_t n=(int32_t)base;
    if(frac>0.5 || (frac==0.5 && n%2!=0))++n;
    return degrees<0.0?-n:n;
}
void doa3d_default_config(doa3d_config_t *c)
{
    double a=40.0,h=a*sqrt(2.0/3.0),x=a/sqrt(3.0);
    if(c==NULL)return;
    memset(c,0,sizeof(*c));
    c->mic_mm[0][0]=(float)x;c->mic_mm[0][2]=(float)(-h/4.0);
    c->mic_mm[1][0]=(float)(-x/2.0);c->mic_mm[1][1]=20.0f;c->mic_mm[1][2]=(float)(-h/4.0);
    c->mic_mm[2][0]=(float)(-x/2.0);c->mic_mm[2][1]=-20.0f;c->mic_mm[2][2]=(float)(-h/4.0);
    c->mic_mm[3][2]=(float)(3.0*h/4.0);
    c->sample_rate_hz=48000.0f;c->sound_speed_m_s=343.0f;
    /* Research defaults, not measured acoustic acceptance limits. */
    c->max_normal_condition=100.0f;c->max_residual_rms_samples=0.5f;
    c->norm_min=0.85f;c->norm_max=1.15f;c->tau_slack_samples=0.125f;
    c->min_pairs=4U;
}
/* 3x3 symmetric inverse. Inputs bounded by configuration checks.
 * infinity norm condition is for normal matrix, not the microphone matrix. */
static int inverse(double g[3][3],double inv[3][3],double *condition)
{
    double a=g[0][0],b=g[0][1],c=g[0][2],d=g[1][1],e=g[1][2],f=g[2][2];
    double det=a*(d*f-e*e)-b*(b*f-c*e)+c*(b*e-c*d);
    double scale=fmax(a,fmax(d,f)),gn=0.0,in=0.0;
    unsigned int i,j;
    if(!(scale>0.0) || !(det>1e-10*scale*scale*scale))return 0;
    inv[0][0]=(d*f-e*e)/det;inv[0][1]=(c*e-b*f)/det;inv[0][2]=(b*e-c*d)/det;
    inv[1][0]=inv[0][1];inv[1][1]=(a*f-c*c)/det;inv[1][2]=(b*c-a*e)/det;
    inv[2][0]=inv[0][2];inv[2][1]=inv[1][2];inv[2][2]=(a*d-b*b)/det;
    for(i=0;i<3U;++i){double gs=0.0,is=0.0;for(j=0;j<3U;++j){gs+=fabs(g[i][j]);is+=fabs(inv[i][j]);}gn=fmax(gn,gs);in=fmax(in,is);}
    *condition=gn*in;return 1;
}
static int s25(int32_t x) {return x>=DOA_S25_MIN && x<=DOA_S25_MAX;}
static int stage_error(uint32_t x) {return x==FPGA_STAGE_NUMERIC || x==FPGA_STAGE_PROTOCOL;}
static doa_status_t prepare_geometry(const doa3d_config_t *cfg,
                                     double rows[6][3],double bound[6])
{
    unsigned int i,j;
    if(cfg==NULL)return DOA_BAD_ARGUMENT;
    /* Current producer is fixed 48 kHz, bin7..85. A new rate needs alignment. */
    if(cfg->sample_rate_hz!=48000.0f || !finite_range(cfg->sound_speed_m_s,300.0,380.0) ||
       !finite_range(cfg->max_normal_condition,1.0,10000.0) ||
       !finite_range(cfg->max_residual_rms_samples,0.0,2.0) ||
       !finite_range(cfg->norm_min,(double)0.01f,1.0) || !finite_range(cfg->norm_max,1.0,2.0) ||
       !finite_range(cfg->tau_slack_samples,0.0,0.5) || cfg->min_pairs<4U || cfg->min_pairs>6U || cfg->coordinates_measured>1U)return DOA_BAD_ARGUMENT;
    for(i=0;i<4U;++i)for(j=0;j<3U;++j)if(!finite_range(cfg->mic_mm[i][j],-1000.0,1000.0))return DOA_BAD_ARGUMENT;
    for(i=0;i<6U;++i){
        double length2=0.0;
        for(j=0;j<3U;++j){
            rows[i][j]=((double)cfg->mic_mm[pb[i]][j]-(double)cfg->mic_mm[pa[i]][j])*(double)cfg->sample_rate_hz/(1000.0*(double)cfg->sound_speed_m_s);
            length2+=rows[i][j]*rows[i][j];
        }
        bound[i]=sqrt(length2);
        if(!(bound[i]>0.01) || bound[i]>scan[i])return DOA_BAD_ARGUMENT;
    }
    return DOA_OK;
}
void doa3d_default_options(doa3d_options_t *o)
{
    if(o==NULL)return;
    memset(o,0,sizeof(*o));o->version=DOA3D_OPTIONS_VERSION;
    o->quality_weight_floor=0.25f;
}
doa_status_t doa3d_prepare(const doa3d_config_t *cfg,const doa3d_options_t *options,
                         doa3d_prepared_t *p)
{
    unsigned int mask,i,j,k;
    doa3d_options_t o;
    if(p==NULL)return DOA_BAD_ARGUMENT;
    memset(p,0,sizeof(*p));
    doa3d_default_options(&o);if(options!=NULL)o=*options;
    if(o.version!=DOA3D_OPTIONS_VERSION || o.quality_weighting>1U ||
       !finite_range(o.quality_weight_floor,0.05,1.0))return DOA_BAD_ARGUMENT;
    for(i=0;i<4U;++i)if(!finite_range(o.channel_delay_samples[i],-1.0,1.0))return DOA_BAD_ARGUMENT;
    if(prepare_geometry(cfg,p->rows,p->bound)!=DOA_OK)return DOA_BAD_ARGUMENT;
    p->config=*cfg;p->options=o;
    for(mask=0;mask<64U;++mask){
        double g[3][3]={{0}};
        for(i=0;i<6U;++i)if((mask&(1U<<i))!=0U)
            for(j=0;j<3U;++j)for(k=0;k<3U;++k)g[j][k]+=p->rows[i][j]*p->rows[i][k];
        p->invertible_by_mask[mask]=(uint8_t)inverse(g,p->inverse_by_mask[mask],&p->condition_by_mask[mask]);
    }
    p->ready=DOA3D_OPTIONS_VERSION;return DOA_OK;
}
static doa_status_t solve_internal(const doa_frame_input_t *frame,const doa3d_config_t *cfg,
                                   const doa3d_prepared_t *prepared,doa3d_output_t *o)
{
    double rows[6][3],bound[6],g[3][3]={{0}},inv[3][3],rhs[3]={0},u[3]={0};
    double condition,norm,res=0.0,horizontal,az,el,tau[6]={0};
    unsigned int i,j,k;int cancel=0,error=0;
    if(o==NULL)return DOA_BAD_ARGUMENT;
    memset(o,0,sizeof(*o));o->reason=DOA3D_SOURCE;o->bad_pair_index=DOA_NO_BAD_PAIR;
    for(i=0;i<6U;++i)o->pair[i].reason=DOA_PAIR_NOT_EVALUATED;
    if(frame==NULL || cfg==NULL)return DOA_BAD_ARGUMENT;
    o->frame_id=frame->frame_id;o->first_error_code=(uint8_t)SNAP_STATUS_GET_FIRST_ERROR(frame->flags);
    if((frame->flags&~DOA_FRAME_FLAGS_MASK)!=0U)return DOA_INPUT_FLAGS;
    if((frame->flags&SNAP_STATUS_FRAME_CANCELLED)!=0U){o->reason=DOA3D_CANCELLED;return DOA_OK;}
    if((frame->flags&SNAP_STATUS_ALL_TERMINAL)==0U)return DOA_INCOMPLETE_FRAME;
    for(i=0;i<6U;++i){
        const doa_pair_input_t *p=&frame->pair[i];
        uint32_t ph=FEATURE_0_GET_PHAT_STAGE(p->flags),ip=FEATURE_0_GET_IFFT_STAGE(p->flags);
        if(!s25(p->peak)||!s25(p->r_minus)||!s25(p->r_plus)||!s25(p->second_peak)||p->lag< -32||p->lag>31||p->mask_count>79U){o->bad_pair_index=(uint8_t)i;return DOA_INPUT_RANGE;}
        if((p->flags&~DOA_PAIR_FLAGS_MASK)!=0U || ph>FPGA_STAGE_SKIPPED || ip>FPGA_STAGE_SKIPPED || ph==0U || ip==0U){o->bad_pair_index=(uint8_t)i;return DOA_INPUT_FLAGS;}
        if((p->flags&FEATURE_0_CANCELLED)!=0U || ph==FPGA_STAGE_CANCELLED || ip==FPGA_STAGE_CANCELLED)cancel=1;
        if((p->flags&FEATURE_0_NUMERIC_ERROR)!=0U || stage_error(ph)||stage_error(ip))error=1;
    }
    if(cancel){o->reason=DOA3D_CANCELLED;return DOA_OK;}
    if(error || o->first_error_code!=0U)return DOA_OK;
    if((frame->flags&SNAP_STATUS_BIST)!=0U){o->reason=DOA3D_LEGACY_BIST;return DOA_OK;}
    o->reason=DOA3D_CONFIG;
    if(prepared!=NULL){memcpy(rows,prepared->rows,sizeof(rows));memcpy(bound,prepared->bound,sizeof(bound));}
    else if(prepare_geometry(cfg,rows,bound)!=DOA_OK)return DOA_BAD_ARGUMENT;
    o->coordinates_measured=cfg->coordinates_measured;
    for(i=0;i<6U;++i){
        const doa_pair_input_t *p=&frame->pair[i];doa_pair_result_t *q=&o->pair[i];
        int64_t den,num,delta,mag;double weight=1.0;
        q->reason=DOA_PAIR_MASK;if(p->mask_count<12U)continue;
        q->reason=DOA_PAIR_STAGE;
        if((p->flags&FEATURE_0_RAW_PEAK_VALID)==0U || (p->flags&FEATURE_0_IFFT_QUALIFIED)==0U || FEATURE_0_GET_PHAT_STAGE(p->flags)!=FPGA_STAGE_OK || FEATURE_0_GET_IFFT_STAGE(p->flags)!=FPGA_STAGE_OK)continue;
        den=(int64_t)p->r_minus-INT64_C(2)*p->peak+p->r_plus;
        num=((int64_t)p->r_minus-p->r_plus)*INT64_C(2048);
        if(den<0){den=-den;num=-num;}delta=rne(num,den);
        if(delta>2048)delta=2048;
        if(delta< -2048)delta=-2048;
        q->delta_q12=(int32_t)delta;q->tau_q12=p->lag*INT32_C(4096)+q->delta_q12;
        mag=p->peak<0?-(int64_t)p->peak:p->peak;if(mag==0)mag=1;
        num=((int64_t)p->peak-((p->flags&FEATURE_0_SECOND_VALID)!=0U?p->second_peak:0))*INT64_C(32768);
        q->margin_q15=rne(num,mag);q->reason=DOA_PAIR_TAU;
        tau[i]=(double)q->tau_q12/4096.0;
        if(prepared!=NULL)tau[i]-=(double)prepared->options.channel_delay_samples[pa[i]]-
                                  (double)prepared->options.channel_delay_samples[pb[i]];
        if(fabs(tau[i])>bound[i]+cfg->tau_slack_samples || fabs((double)p->lag)>scan[i])continue;
        if(prepared!=NULL && prepared->options.quality_weighting!=0U)
            weight=fmax((double)prepared->options.quality_weight_floor,fmin(1.0,(double)q->margin_q15/32768.0));
        q->qualified=1U;q->reason=DOA_PAIR_OK;++o->valid_pair_count;o->valid_pair_mask=(uint8_t)(o->valid_pair_mask|(uint8_t)(1U<<i));
        for(j=0;j<3U;++j){
            rhs[j]+=rows[i][j]*tau[i]*weight;
            if(prepared==NULL || prepared->options.quality_weighting!=0U)
                for(k=0;k<3U;++k)g[j][k]+=rows[i][j]*rows[i][k]*weight;
        }
    }
    o->reason=DOA3D_PAIRS;if(o->valid_pair_count<cfg->min_pairs)return DOA_OK;
    o->reason=DOA3D_SINGULAR;
    if(prepared!=NULL && prepared->options.quality_weighting==0U){
        if(prepared->invertible_by_mask[o->valid_pair_mask]==0U)return DOA_OK;
        memcpy(inv,prepared->inverse_by_mask[o->valid_pair_mask],sizeof(inv));
        condition=prepared->condition_by_mask[o->valid_pair_mask];
    }else if(!inverse(g,inv,&condition))return DOA_OK;
    o->normal_condition=(float)condition;o->reason=DOA3D_CONDITION;
    if(!(condition<=cfg->max_normal_condition))return DOA_OK;
    for(j=0;j<3U;++j)for(k=0;k<3U;++k)u[j]+=inv[j][k]*rhs[k];
    for(i=0;i<6U;++i)if(o->pair[i].qualified!=0U){double predicted=0.0,diff;for(j=0;j<3U;++j)predicted+=rows[i][j]*u[j];diff=predicted-tau[i];res+=diff*diff;}
    o->ux=(float)u[0];o->uy=(float)u[1];o->uz=(float)u[2];
    norm=sqrt(u[0]*u[0]+u[1]*u[1]+u[2]*u[2]);o->norm=(float)norm;
    o->residual_rms_samples=(float)sqrt(res/o->valid_pair_count);
    o->reason=DOA3D_RESIDUAL;if(!(o->residual_rms_samples<=cfg->max_residual_rms_samples))return DOA_OK;
    o->reason=DOA3D_NORM;if(!(norm>=cfg->norm_min && norm<=cfg->norm_max))return DOA_OK;
    horizontal=sqrt(u[0]*u[0]+u[1]*u[1]);el=atan2(u[2],horizontal)*57.2957795130823208768;
    o->elevation_deg=(float)el;o->elevation_q8=q8(el);o->elevation_valid=1U;
    /* Near a pole azimuth is unobservable; never publish arbitrary 0 as valid. */
    if(horizontal>norm*1e-4){az=atan2(u[1],u[0])*57.2957795130823208768;if(az>=180.0)az-=360.0;o->azimuth_deg=(float)az;o->azimuth_q8=q8(az);if(o->azimuth_q8>=46080)o->azimuth_q8-=92160;o->azimuth_valid=1U;}
    o->reason=DOA3D_VALID;o->direction_valid=1U;return DOA_OK;
}

doa_status_t doa3d_solve(const doa_frame_input_t *frame,const doa3d_config_t *cfg,doa3d_output_t *o)
{
    return solve_internal(frame,cfg,NULL,o);
}
doa_status_t doa3d_solve_prepared(const doa_frame_input_t *frame,const doa3d_prepared_t *p,doa3d_output_t *o)
{
    if(p==NULL || p->ready!=DOA3D_OPTIONS_VERSION)return solve_internal(frame,NULL,NULL,o);
    return solve_internal(frame,&p->config,p,o);
}
