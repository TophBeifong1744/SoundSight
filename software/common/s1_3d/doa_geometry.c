#include "doa_geometry.h"
#include <math.h>
#include <string.h>
static int in_range(double v,double lo,double hi) { return v>=lo && v<=hi; }
void doa_geometry_nominal(doa_geometry_record_t *r)
{
    doa3d_config_t c; unsigned int i;
    if(r==NULL) return;
    memset(r,0,sizeof(*r)); doa3d_default_config(&c);
    r->schema=DOA_GEOMETRY_SCHEMA; r->revision=1U;
    r->provenance=DOA_GEOMETRY_NOMINAL;
    strcpy(r->source_id,"tetra40-nominal-v1");
    r->sample_rate_hz=c.sample_rate_hz; r->sound_speed_m_s=c.sound_speed_m_s;
    r->position_error_mm=-1.0f;
    for(i=0U;i<4U;++i) { r->mic[i].channel=(uint8_t)i; memcpy(r->mic[i].xyz_mm,c.mic_mm[i],sizeof(r->mic[i].xyz_mm)); }
}
/* Independent geometry preflight; same normal-matrix norm and rank tolerance
 * as solver, without constructing a fake frame or bypassing source checks. */
static int condition_of(double g[3][3],double *condition)
{
    double a=g[0][0],b=g[0][1],c=g[0][2],d=g[1][1],e=g[1][2],f=g[2][2];
    double det=a*(d*f-e*e)-b*(b*f-c*e)+c*(b*e-c*d);
    double scale=fmax(a,fmax(d,f)),inv[3][3],gn=0.0,in=0.0;
    unsigned int i,j;
    if(!(scale>0.0) || !(det>1e-10*scale*scale*scale)) return 0;
    inv[0][0]=(d*f-e*e)/det;inv[0][1]=(c*e-b*f)/det;inv[0][2]=(b*e-c*d)/det;
    inv[1][0]=inv[0][1];inv[1][1]=(a*f-c*c)/det;inv[1][2]=(b*c-a*e)/det;
    inv[2][0]=inv[0][2];inv[2][1]=inv[1][2];inv[2][2]=(a*d-b*b)/det;
    for(i=0U;i<3U;++i) {
        double gs=0.0,is=0.0;
        for(j=0U;j<3U;++j) { gs+=fabs(g[i][j]);is+=fabs(inv[i][j]); }
        gn=fmax(gn,gs);in=fmax(in,is);
    }
    *condition=gn*in;return 1;
}
static doa_geometry_status_t fail(doa_geometry_report_t *r,doa_geometry_status_t s)
{ if(r!=NULL) r->status=s; return s; }
doa_geometry_status_t doa_geometry_build(const doa_geometry_record_t *r,
                                        doa3d_config_t *out,doa_geometry_report_t *report)
{
    static const unsigned int a[6]={0U,0U,0U,1U,1U,2U},b[6]={1U,2U,3U,2U,3U,3U};
    static const double scan[6]={6,8,6,6,8,6};
    doa3d_config_t c; unsigned int i,j,k,seen=0U;
    double g[3][3]={{0}},condition,scale;
    if(out!=NULL) memset(out,0,sizeof(*out));
    if(report!=NULL) { memset(report,0,sizeof(*report));report->bad_pair=255U; }
    if(r==NULL || out==NULL || report==NULL) return fail(report,DOA_GEOMETRY_ARGUMENT);
    if(r->schema!=DOA_GEOMETRY_SCHEMA || r->revision==0U ||
       (r->provenance!=DOA_GEOMETRY_NOMINAL && r->provenance!=DOA_GEOMETRY_MEASURED && r->provenance!=DOA_GEOMETRY_SYNTHETIC))
        return fail(report,DOA_GEOMETRY_METADATA);
    for(i=0U;i<DOA_GEOMETRY_SOURCE_BYTES;++i) {
        unsigned char ch=(unsigned char)r->source_id[i];
        if(ch==0U) break;
        if(ch<33U || ch>126U) return fail(report,DOA_GEOMETRY_METADATA);
    }
    if(i==0U || i==DOA_GEOMETRY_SOURCE_BYTES) return fail(report,DOA_GEOMETRY_METADATA);
    if(r->sample_rate_hz!=48000.0f || !in_range(r->sound_speed_m_s,300,380) ||
       !(r->position_error_mm==-1.0f || in_range(r->position_error_mm,0,1000)) ||
       (r->provenance==DOA_GEOMETRY_MEASURED && !(r->position_error_mm>0.0f)))
        return fail(report,DOA_GEOMETRY_RANGE);
    doa3d_default_config(&c);
    c.sample_rate_hz=r->sample_rate_hz;c.sound_speed_m_s=r->sound_speed_m_s;
    c.coordinates_measured=(uint8_t)(r->provenance==DOA_GEOMETRY_MEASURED);
    for(i=0U;i<4U;++i) {
        unsigned int ch=r->mic[i].channel;
        if(ch>3U || (seen&(1U<<ch))!=0U) return fail(report,DOA_GEOMETRY_CHANNEL);
        seen|=1U<<ch;
        for(j=0U;j<3U;++j) {
            if(!in_range(r->mic[i].xyz_mm[j],-1000,1000)) return fail(report,DOA_GEOMETRY_RANGE);
            c.mic_mm[ch][j]=r->mic[i].xyz_mm[j];
        }
    }
    report->uncertainty_known=(uint8_t)(r->position_error_mm>=0.0f);
    scale=(double)c.sample_rate_hz/(1000.0*(double)c.sound_speed_m_s);
    for(i=0U;i<6U;++i) {
        double v[3],len=0.0,bound;
        for(j=0U;j<3U;++j) { v[j]=(double)c.mic_mm[b[i]][j]-c.mic_mm[a[i]][j];len+=v[j]*v[j]; }
        len=sqrt(len);bound=(len+(report->uncertainty_known?2.0*(double)r->position_error_mm:0.0))*scale;
        report->distance_mm[i]=(float)len;report->nominal_delay_samples[i]=(float)(len*scale);
        /* -1 explicitly denotes unavailable uncertainty-enlarged bound. */
        report->bounded_delay_samples[i]=report->uncertainty_known?(float)bound:-1.0f;
        if(!(len*scale>0.01) || bound>scan[i]) { report->bad_pair=(uint8_t)i;return fail(report,DOA_GEOMETRY_WINDOW); }
        for(j=0U;j<3U;++j)for(k=0U;k<3U;++k)g[j][k]+=v[j]*v[k]*scale*scale;
    }
    if(!condition_of(g,&condition)) return fail(report,DOA_GEOMETRY_SINGULAR);
    report->normal_condition=(float)condition;
    if(!(condition<=c.max_normal_condition)) return fail(report,DOA_GEOMETRY_CONDITION);
    *out=c;report->valid=1U;report->status=DOA_GEOMETRY_OK;return DOA_GEOMETRY_OK;
}
