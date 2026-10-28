# 关键实现摘录（只供报告引用）

以下均从固定v3公开源码ZIP提取，不是当前上板源码。片段可能依赖未摘录的上下文，不可作为完整可运行模块。路径/行号指ZIP内部的原源码；包哈希与片段校验见[source-map.json](source-map.json)。

## S01 功率谱复用与稀疏Mel遍历

每帧FFT后只生成一次功率谱，按非零Mel区间累加。对应E05前端优化；不能把40.55%全部归因于这一条改动。

固定v3源码 `software/ps/speaker_core/pipeline_backend.c`，原第89–112行。

```c
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
```

## S02 连续前处理状态复用

FIR历史、VAD状态和400点音频帧跨块复用，只生成新增Mel帧；窗口滑动不重复从头计算。

固定v3源码 `software/ps/speaker_core/stream_frontend.h`，原第10–37行。

```c
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
```

## S03 收包回调与32包信用

采集侧只提交数据并限制未确认包数，不运行网络；连续性、epoch及背压出错立即失败。减少算法解释器对收包路径的影响，不证明所有溢出已消除。

固定v3源码 `software/ps/speaker_process.py`，原第83–94行。

```python
    def submit(self,data,meta):
        # Called by the sole DMA owner. No print, disk IO, Python threads or wait.
        self._drain()
        if self.error or self.result is not None or self.p.poll() is not None:
            raise RuntimeError(self.error or 'SPEAKER_WORKER_EXITED')
        if not self.started_once or len(data)!=PACKET_BYTES:raise ValueError('SPEAKER_IPC_INPUT')
        if meta['block_seq']!=self.sent or meta['sample_start']!=self.sent*512:raise ValueError('SPEAKER_PACKET_GAP')
        if self.epoch is None:self.epoch=meta['epoch']
        if meta['epoch']!=self.epoch:raise ValueError('SPEAKER_EPOCH_CHANGED')
        if self.sent-self.acked>=CREDITS:raise RuntimeError('SPEAKER_IPC_CREDIT_OVERFLOW_STOP')
        self._send(b'P'+data);self.sent+=1
        self.highwater=max(self.highwater,self.sent-self.acked)
```

## S04 只保留最新待算候选

这是v3历史调度规则，须结合调用方和常量理解；后续28日延迟许可属于另一个控制策略。替换声纹任务不等于丢弃PCM。

固定v3源码 `software/ps/speaker_core/stream_bench.py`，原第94–101行。

```python
    def put(self, job):
        with self.cv:
            if self.done:
                raise RuntimeError('PUBLISH_AFTER_FINISH')
            self.generated += 1
            self.replaced += self.pending is not None
            self.pending = job
            self.cv.notify()
```

## S05 旧候选与过期身份失效

这是v3历史调度规则，须结合调用方和常量理解；后续28日延迟许可属于另一个控制策略。替换声纹任务不等于丢弃PCM。

固定v3源码 `software/ps/speaker_core/stream_bench.py`，原第119–127行。

```python
    def validity(self, job, age):
        with self.cv:
            if self.error:
                return 'frontend_failed'
            if age > MAX_RESULT_AGE:
                return 'expired'
            if not self.active or self.voice_epoch != job['voice_epoch']:
                return 'speech_state_changed'
            return 'fresh'
```

## S06 逐次推理计时完整性

FPR-R1修复：不能只看全局Run数和是否存在节点；每次Run都要有节点，节点不能落在所有Run之外，交叉/截断不当完整结果。

固定v3源码 `software/ps/speaker_core/network_profile.py`，原第66–77行。

```python
    runs.sort(key=lambda r:r['start'])
    starts=[r['start'] for r in runs];coverage=[0]*len(runs);unassigned=0
    overlapping_runs=any(a['end']>b['start'] for a,b in zip(runs,runs[1:]))
    for n in nodes:
        index=bisect.bisect_right(starts,n['start'])-1
        if index>=0 and n['end']<=runs[index]['end']:coverage[index]+=1
        else:unassigned+=1
    expected=min(meta['calls'],meta['limit'])
    complete=(meta.get('graceful_close') is True and not meta.get('truncated') and
              len(runs)==expected and expected>0 and bool(nodes) and not crossing and
              all(coverage) and not unassigned and not overlapping_runs)
    status='NO_SAMPLES' if expected==0 and not nodes and not runs else 'COMPLETE' if complete else 'PARTIAL'
```
