/* Private CPU replay extension. No hardware access. 32ms blocks, causal FIR,
 * one continuous Silero state, and one computation per 25ms mel frame. */
static struct {
    float history[61],audio_frame[400],state[256],vad_input[576];
    unsigned pos,decimation,frame_fill;
} stream_state;

static void stream_reset(void) { memset(&stream_state,0,sizeof(stream_state)); }

static float *stream_step(const float *x,const float *tables,OrtSession *vad,uint32_t *count) {
    /* [audio_count=512, mel_frames, probability, audio[512], raw_mel[frames*80]] */
    double begin=seconds();
    double mel_before=perf[2];
    static float out[3+512+4*80];
    unsigned a=0,frames=0;
    for(unsigned i=0;i<1536;i++) {
        stream_state.history[stream_state.pos]=x[i];
        if(stream_state.decimation==0) {
            float y=0;
            for(unsigned k=0;k<61;k++)y+=stream_state.history[(stream_state.pos+61-k)%61]*tables[k];
            out[3+a]=y;stream_state.vad_input[64+a]=y;a++;
            stream_state.audio_frame[stream_state.frame_fill++]=y;
            if(stream_state.frame_fill==400) {
                mel_frame(stream_state.audio_frame,tables,out+3+512+frames*80);frames++;
                memmove(stream_state.audio_frame,stream_state.audio_frame+160,240*4);
                stream_state.frame_fill=240;
            }
        }
        stream_state.pos=(stream_state.pos+1)%61;
        stream_state.decimation=(stream_state.decimation+1)%3;
    }
    if(a!=512 || frames>4)die("STREAM_INTERNAL_SHAPE");
    if(detail_enabled){detail[4]+=seconds()-begin-(perf[2]-mel_before);detail[11]++;}
    vad_step(vad,stream_state.state,stream_state.vad_input,out+2);
    out[0]=512;out[1]=(float)frames;*count=3+512+frames*80;
    perf[1]+=seconds()-begin;perf[6]++;return out;
}
