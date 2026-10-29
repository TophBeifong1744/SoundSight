/* Optional bounded diagnostics. No changes to tensor arithmetic or ORT options. */
#include <unistd.h>
static int detail_enabled;
static double detail[12];
/* frame preparation, FFT, power, mel projection/log, FIR+stream bookkeeping,
 * VAD Run, embedding Run, embedding output copy, VAD calls, embedding calls,
 * mel frames, stream blocks. Nested in legacy perf[]; never sum both. */
typedef struct { OrtSession *session; const char *role; unsigned calls,limit; int active;
    double start_mono; char prefix[4096]; } TraceSession;
static TraceSession traces[2];
static unsigned trace_count;
static void trace_setup(OrtSessionOptions *options,const char *role) {
    const char *dir=getenv("SS_ORT_PROFILE_DIR");
    if(!dir || !*dir)return;
    if(trace_count>=2)die("PROFILE_SESSION_BOUND");
    TraceSession *t=&traces[trace_count];
    t->role=role;t->limit=!strcmp(role,"vad")?512:32;
    if(snprintf(t->prefix,sizeof(t->prefix),"%s/%s-%ld",dir,role,(long)getpid())>=(int)sizeof(t->prefix))die("PROFILE_PATH_BOUND");
    ok(api->EnableProfiling(options,t->prefix));t->start_mono=seconds();t->active=1;
}
static void trace_created(OrtSession *session) {
    const char *dir=getenv("SS_ORT_PROFILE_DIR");
    if(dir && *dir)traces[trace_count++].session=session;
}
static void trace_end(TraceSession *t) {
    if(!t->active)return;
    OrtAllocator *a=NULL;char *name=NULL;
    ok(api->GetAllocatorWithDefaultOptions(&a));
    ok(api->SessionEndProfiling(t->session,a,&name));
    /* Paths may contain quotes; store the basename in a separate text file. */
    char path[4120];snprintf(path,sizeof(path),"%s.trace-path.txt",t->prefix);
    FILE *f=fopen(path,"w");if(!f)die("PROFILE_PATH_WRITE");
    if(fprintf(f,"%s\n",name)<0 || fclose(f))die("PROFILE_PATH_WRITE");
    a->Free(a,name);t->active=0;
}
static void trace_before_run(OrtSession *session) {
    for(unsigned i=0;i<trace_count;i++)if(traces[i].session==session) {
        TraceSession *t=&traces[i];
        /* Bound retained ORT events even if a diagnostic caller runs too long. */
        if(t->calls==t->limit)trace_end(t);
        t->calls++;break;
    }
}
static void trace_finish(void) {
    for(unsigned i=0;i<trace_count;i++) {
        TraceSession *t=&traces[i];trace_end(t);
        char path[4120];snprintf(path,sizeof(path),"%s.meta.json",t->prefix);
        FILE *f=fopen(path,"w");if(!f)die("PROFILE_META_WRITE");
        if(fprintf(f,"{\"role\":\"%s\",\"pid\":%ld,\"calls\":%u,\"limit\":%u,\"truncated\":%s,\"session_create_monotonic_seconds\":%.9f,\"clock_alignment\":\"approximate_before_CreateSession\",\"graceful_close\":true}\n",
            t->role,(long)getpid(),t->calls,t->limit,t->calls>t->limit?"true":"false",t->start_mono)<0 || fclose(f))die("PROFILE_META_WRITE");
    }
}
