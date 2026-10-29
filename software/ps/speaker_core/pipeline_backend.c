/* File-only CPU backend. Shares the existing ORT configuration and checked IO.
 * Binary pipe protocol is private to pipeline_bench.py; no hardware interfaces. */
#define main original_core_probe_main
#include "core_bench.c"
#undef main
#include <float.h>
#ifndef SS_MIN_CHUNK_SAMPLES
#define SS_MIN_CHUNK_SAMPLES 24000
#endif

static void die(const char *s) { fprintf(stderr,"PIPE_ERROR=%s\n",s); exit(2); }
static void ok(OrtStatus *s) { if (!checked(s)) exit(2); }
static void rd(void *p,size_t n) { if(fread(p,1,n,stdin)!=n) die("TRUNCATED_REQUEST"); }
static void wr(const void *p,size_t n) { if(fwrite(p,1,n,stdout)!=n) die("OUTPUT_FAILED"); }
static OrtEnv *penv;
static OrtMemoryInfo *mem;
/* Wall times include scheduling. frontend includes mel and VAD: do not add them. */
static double perf[8]; /* decode, frontend, mel, vad, cmn, embed, blocks, embeddings */
#include "detail_profile.h"
static unsigned mel_lo[80],mel_hi[80];
static void mel_init(const float *tables) {
    for(unsigned m=0;m<80;m++) {
        unsigned lo=0,hi=257;
        while(lo<hi && tables[461+m*257+lo]==0)lo++;
        while(hi>lo && tables[461+m*257+hi-1]==0)hi--;
        mel_lo[m]=lo;mel_hi[m]=hi;
    }
}
static OrtSession *make_session(const char *path,int threads,const char *role) {
    OrtSessionOptions *o=NULL; OrtSession *s=NULL;
    ok(api->CreateSessionOptions(&o));
    /* Official Silero graph contains unused initializers; keep errors visible. */
    ok(api->SetSessionLogSeverityLevel(o,ORT_LOGGING_LEVEL_ERROR));
    ok(api->SetIntraOpNumThreads(o,threads)); ok(api->SetInterOpNumThreads(o,1));
    ok(api->SetSessionExecutionMode(o,ORT_SEQUENTIAL));
    ok(api->DisableCpuMemArena(o)); ok(api->DisableMemPattern(o));
    ok(api->AddSessionConfigEntry(o,"session.intra_op.allow_spinning","0"));
    ok(api->SetSessionGraphOptimizationLevel(o,ORT_ENABLE_ALL));
    trace_setup(o,role);
    ok(api->CreateSession(penv,path,o,&s));trace_created(s); api->ReleaseSessionOptions(o); return s;
}
static OrtValue *tensor(void *p,size_t bytes,const int64_t *dims,size_t nd,ONNXTensorElementDataType kind) {
    OrtValue *v=NULL; ok(api->CreateTensorWithDataAsOrtValue(mem,p,bytes,dims,nd,kind,&v)); return v;
}
static void copy_output(OrtValue *v,float *dst,size_t expected) {
    OrtTensorTypeAndShapeInfo *sh=NULL; size_t n; ONNXTensorElementDataType kind;
    ok(api->GetTensorTypeAndShape(v,&sh)); ok(api->GetTensorShapeElementCount(sh,&n));
    ok(api->GetTensorElementType(sh,&kind)); api->ReleaseTensorTypeAndShapeInfo(sh);
    if(n!=expected || kind!=ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT) die("BAD_OUTPUT_SHAPE");
    float *p=NULL; ok(api->GetTensorMutableData(v,(void**)&p));
    for(size_t i=0;i<n;i++) if(!isfinite(p[i])) die("NONFINITE_OUTPUT");
    memcpy(dst,p,n*4);
}
static void fft(double *re,double *im) {
    for(int i=1,j=0;i<512;i++) {
        int b=256; for(;j&b;b>>=1) j^=b; j^=b;
        if(i<j) { double t=re[i];re[i]=re[j];re[j]=t; }
    }
    for(int len=2;len<=512;len*=2) {
        double a=-6.2831853071795864769/len,cr=cos(a),ci=sin(a);
        for(int b=0;b<512;b+=len) {
            double r=1,v=0;
            for(int j=0;j<len/2;j++) {
                int p=b+j,q=p+len/2;
                double tr=r*re[q]-v*im[q],ti=r*im[q]+v*re[q];
                re[q]=re[p]-tr;im[q]=im[p]-ti;re[p]+=tr;im[p]+=ti;
                double nr=r*cr-v*ci; v=r*ci+v*cr;r=nr;
            }
        }
    }
}
static void vad_step(OrtSession *vad,float *state,float *input,float *prob) {
    double begin=seconds();
    int64_t sr=16000; const int64_t id[]={1,576},sd[]={2,1,128};
    const char *inames[]={"input","state","sr"},*onames[]={"output","stateN"};
    OrtValue *ins[]={tensor(input,576*4,id,2,ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT),
        tensor(state,256*4,sd,3,ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT),
        tensor(&sr,8,NULL,0,ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64)},*outs[2]={NULL,NULL};
    trace_before_run(vad);double run_begin=detail_enabled?seconds():0;
    ok(api->Run(vad,NULL,inames,(const OrtValue*const*)ins,3,onames,2,outs));
    if(detail_enabled){detail[5]+=seconds()-run_begin;detail[8]++;}
    copy_output(outs[0],prob,1);copy_output(outs[1],state,256);
    if(*prob<0 || *prob>1)die("INVALID_PROBABILITY");
    for(int j=0;j<3;j++)api->ReleaseValue(ins[j]);
    for(int j=0;j<2;j++)api->ReleaseValue(outs[j]);
    memmove(input,input+512,64*4);
    perf[3]+=seconds()-begin;
}
static void mel_frame(const float *x,const float *tables,float *out) {
    double begin=seconds();
    double re[512]={0},im[512]={0};float centered[400];double mean=0;
    double mark=detail_enabled?seconds():0;
    for(int j=0;j<400;j++)mean+=x[j];
    for(int j=0;j<400;j++)centered[j]=x[j]-(float)(mean/400);
    for(int j=0;j<400;j++)re[j]=(centered[j]-.97f*centered[j?j-1:0])*tables[61+j];
    if(detail_enabled){detail[0]+=seconds()-mark;mark=seconds();}
    fft(re,im);
    if(detail_enabled){detail[1]+=seconds()-mark;mark=seconds();}
    double power[257];
    for(int k=0;k<257;k++)power[k]=re[k]*re[k]+im[k]*im[k];
    if(detail_enabled){detail[2]+=seconds()-mark;mark=seconds();}
    for(int m=0;m<80;m++) {
        double sum=0;
        /* Preserve increasing-bin accumulation and precision; omit zero weights. */
        for(unsigned k=mel_lo[m];k<mel_hi[m];k++) {
            float weight=tables[461+m*257+k];if(weight!=0)sum+=power[k]*weight;
        }
        out[m]=logf(fmaxf((float)sum,FLT_EPSILON));
    }
    if(detail_enabled){detail[3]+=seconds()-mark;detail[10]++;}
    perf[2]+=seconds()-begin;
}
static void cmn(float *x,int frames) {
    double begin=seconds();
    for(int m=0;m<80;m++){double mean=0;for(int f=0;f<frames;f++)mean+=x[f*80+m];mean/=frames;for(int f=0;f<frames;f++)x[f*80+m]-=(float)mean;}
    perf[4]+=seconds()-begin;
}
#ifdef SS_STREAMING
#include "stream_frontend.h"
#endif
int main(int argc,char **argv) {
    long threads;
    int front_only=0,embed_only=0;
#ifdef SS_STREAMING
    if(argc==6) {
        front_only=!strcmp(argv[5],"front");embed_only=!strcmp(argv[5],"embed");
        if(!front_only && !embed_only)die("ROLE");
    } else
#endif
    if(argc!=5)die("ARGS_MODEL_VAD_TABLES_THREADS");
    if(!number(argv[4],1,2,&threads))die("THREADS");
    const uint32_t endian=1;
    if(*(const unsigned char*)&endian!=1 || sizeof(float)!=4) die("ENDIAN");
    float *tables=read_floats(argv[3],61+400+80*257); if(!tables) die("TABLES");
    mel_init(tables);
    api=OrtGetApiBase()->GetApi(ORT_API_VERSION); if(!api) die("ORT_API");
    detail_enabled=getenv("SS_SPEAKER_DETAIL_PROFILE") && !strcmp(getenv("SS_SPEAKER_DETAIL_PROFILE"),"1");
    double start=seconds();
    ok(api->CreateEnv(ORT_LOGGING_LEVEL_WARNING,"SoundSightPipeline",&penv));
    ok(api->CreateCpuMemoryInfo(OrtArenaAllocator,OrtMemTypeDefault,&mem));
    OrtSession *embed=front_only?NULL:make_session(argv[1],(int)threads,"embedding"); double e=seconds();
    OrtSession *vad=embed_only?NULL:make_session(argv[2],1,"vad"); double v=seconds();
    printf("{\"embedding_load_seconds\":%.6f,\"vad_load_seconds\":%.6f,\"ort\":\"%s\",\"live_opt_revision\":1}\n",e-start,v-e,OrtGetApiBase()->GetVersionString()); fflush(stdout);
#ifdef SS_STREAMING
    float live_input[198*80];
#endif
    for(;;) {
        int cmd=fgetc(stdin); if(cmd=='Q') break; if(cmd==EOF) die("MISSING_QUIT");
#ifdef SS_STREAMING
        if(cmd=='Z') { stream_reset();uint32_t ack=1;wr(&ack,4);fflush(stdout);continue; }
#endif
        if(cmd=='R') { struct rusage u; if(getrusage(RUSAGE_SELF,&u)) die("RSS"); double mb=u.ru_maxrss/1024.;wr(&mb,8);fflush(stdout);continue; }
        if(cmd=='T') { wr(perf,sizeof(perf));fflush(stdout);continue; }
        if(cmd=='U') { wr(detail,sizeof(detail));fflush(stdout);continue; }
        uint32_t n; rd(&n,4);
        if(n==0 || n>2880000) die("INPUT_BOUND");
#ifdef SS_STREAMING
        if(cmd=='B'||cmd=='C') {
            if(!vad || (cmd=='B' ? n!=1536 : (n!=512 && n!=1024)))die("PCM32_BLOCK_OR_ROLE");
            /* 3 x 512 frames, four interleaved signed S24-in-S32 channels.
               Same per-512-frame mic0 clipping check as the old Python path. */
            int32_t raw[1536*4];rd(raw,(size_t)n*16);double begin=seconds();
            for(unsigned block=0;block<n/512;block++) {
                unsigned clipped=0;
                for(unsigned j=0;j<512;j++) {
                    unsigned i=block*512+j;int32_t value=raw[i*4];
                    if(value < -8388608 || value > 8388607)die("PCM24_SIGN_EXTENSION");
                    live_input[i]=(float)value/8388608.f;
                    if(fabs((double)live_input[i])>=.999)clipped++;
                }
                if((double)clipped/512>.01)die("EXCESSIVE_CLIPPING");
            }
            perf[0]+=seconds()-begin;uint32_t count=0;
            if(cmd=='C') { wr(&count,4);fflush(stdout);continue; }
            float *out=stream_step(live_input,tables,vad,&count);
            wr(&count,4);wr(out,(size_t)count*4);fflush(stdout);continue;
        }
#endif
        if(cmd=='D') {
            /* PCM24 little-endian, four interleaved channels, fixed mic0.
               Keep values bit-identical to the prior Python conversion. */
            unsigned char *raw=malloc((size_t)n*12);
            float *decoded=malloc((size_t)n*4);
            if(!raw || !decoded)die("ALLOC");
            rd(raw,(size_t)n*12);uint32_t clipped=0;
            for(uint32_t i=0;i<n;i++) {
                const unsigned char *p=raw+(size_t)i*12;
                int32_t value=(int32_t)p[0] | ((int32_t)p[1]<<8) | ((int32_t)p[2]<<16);
                if(value & 0x800000)value-=0x1000000;
                decoded[i]=(float)value/8388608.f;
                if(fabs((double)decoded[i])>=.999)clipped++;
            }
            if((double)clipped/n>.01)die("EXCESSIVE_CLIPPING");
            wr(&n,4);wr(decoded,(size_t)n*4);fflush(stdout);free(raw);free(decoded);continue;
        }
        int own_x=1,own_y=1;
        float *x=NULL;
#ifdef SS_STREAMING
        if((cmd=='S'||cmd=='N'||cmd=='J'||cmd=='E') && n<=198*80) { x=live_input;own_x=0; }
#endif
        if(own_x)x=malloc((size_t)n*4);
        if(!x) die("ALLOC");
        rd(x,(size_t)n*4);
        for(uint32_t i=0;i<n;i++) if(!isfinite(x[i])) die("NONFINITE_INPUT");
        float *y=NULL; uint32_t count=0;
#ifdef SS_STREAMING
        if(cmd=='S') {
            if(!vad || n!=1536)die("STREAM_BLOCK_OR_ROLE");
            y=stream_step(x,tables,vad,&count);
            own_y=0;
        } else if(cmd=='N') {
            if(n%80 || n/80<98 || n/80>198)die("STREAM_CMN_BOUND");
            y=x;own_y=0;count=n;cmn(y,n/80);
        } else
#endif
        if(cmd=='P') {
            double mean=0; for(uint32_t i=0;i<n;i++)mean+=x[i]; mean/=n;
            double rms=0; for(uint32_t i=0;i<n;i++){x[i]-=(float)mean;rms+=(double)x[i]*x[i];}
            if(sqrt(rms/n)<1e-5) { count=0; }
            else {
                count=(n+2)/3; y=calloc(count,4);if(!y)die("ALLOC");
                /* scipy resample_poly(up=1,down=3): 61-tap Kaiser FIR,
                   zero extension and removal of its 30-input-sample delay. */
                for(uint32_t i=0;i<count;i++) {
                    float sum=0;
                    for(int k=0;k<61;k++){int j=(int)(3*i)+30-k;if(j>=0 && j<(int)n)sum+=x[j]*tables[k];}
                    y[i]=sum;
                }
            }
        } else if(cmd=='V') {
            if(n>960000 || !vad)die("VAD_BOUND_OR_ROLE");
            count=(n+511)/512;y=calloc(count,4);if(!y)die("ALLOC");
            float state[256]={0},input[576]={0};
            for(uint32_t b=0;b<count;b++) {
                memset(input+64,0,512*4);uint32_t size=n-b*512;if(size>512)size=512;
                memcpy(input+64,x+b*512,size*4);
                vad_step(vad,state,input,y+b);
            }
        } else if(cmd=='F') {
            if(n<SS_MIN_CHUNK_SAMPLES || n>64000)die("CHUNK_BOUND");
            int frames=1+((int)n-400)/160;
            count=(uint32_t)frames*80;y=calloc(count,4);if(!y)die("ALLOC");
            for(int f=0;f<frames;f++)mel_frame(x+f*160,tables,y+f*80);
            cmn(y,frames);
        } else if(cmd=='E'
#ifdef SS_STREAMING
                  ||cmd=='J'
#endif
        ) {
            if(!embed || n%80 || n/80<(1+(SS_MIN_CHUNK_SAMPLES-400)/160) || n/80>398)die("FEATURE_BOUND");
#ifdef SS_STREAMING
            if(cmd=='J') {
                if(n/80<98 || n/80>198)die("STREAM_CMN_BOUND");
                cmn(x,n/80);
            }
#endif
            count=192;y=calloc(count,4);if(!y)die("ALLOC");const int64_t dims[]={1,n/80,80};
            OrtValue *in=tensor(x,(size_t)n*4,dims,3,ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT),*out=NULL;
            const char *ins[]={"features"},*outs[]={"embedding"};
            double begin=seconds();
            trace_before_run(embed);double run_begin=detail_enabled?seconds():0;
            ok(api->Run(embed,NULL,ins,(const OrtValue*const*)&in,1,outs,1,&out));
            if(detail_enabled){detail[6]+=seconds()-run_begin;detail[9]++;run_begin=seconds();}
            copy_output(out,y,192);
            if(detail_enabled)detail[7]+=seconds()-run_begin;
            perf[5]+=seconds()-begin;perf[7]++;
            api->ReleaseValue(in);api->ReleaseValue(out);
        } else die("UNKNOWN_COMMAND");
        wr(&count,4);if(count)wr(y,(size_t)count*4);fflush(stdout);
        if(own_y)free(y);
        if(own_x)free(x);
    }
    trace_finish();
    if(vad)api->ReleaseSession(vad);
    if(embed)api->ReleaseSession(embed);
    api->ReleaseMemoryInfo(mem);api->ReleaseEnv(penv);free(tables);return 0;
}
