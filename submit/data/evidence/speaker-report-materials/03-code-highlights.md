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

## B补充：S07起的候选与三维源码

S01～S06仍属于A原v3来源。以下各片段分别绑定自己的文件哈希、行号、候选或公开提交；不把优化模型说成原创CAM++/Silero。B声纹完整运行包仍为私下交接，本目录只公开可审阅片段。三维完整源码链接固定提交，不能冒充A当前main已采用全部优化。

<a id="s07"></a>

### S07 RX4全通道字节符号校验

每包仍检查完整头和2048个S24扩展值，减少Python整数展开。E12的95.71%仅属于纯内存校验；MMIO/调度不在这项测量内。

候选：`RX4 ZIP 0b648d4a0853d1b9444ef46e4ed51dd5ae3b9fce93cf22d56b1ac50f02824615`；原路径 `software/ps/pcm_capture.py` 第74–89行。

```python
def decode_packet(data, epoch, sequence):
    if len(data) != PACKET_BYTES:
        raise ValueError('Incorrect DMA packet length: %d' % len(data))
    magic, fmt, session, seq, low, high, count_flags, size = struct.unpack_from('<8I', data)
    start = low | (high << 32)
    flags = count_flags >> 16
    if (magic, fmt, session, seq, start, count_flags & 65535, size) != (
            0x43505353, 0x00200001, epoch, sequence, sequence * SAMPLES, SAMPLES, 8192):
        raise ValueError('Packet header/session/sequence/sample continuity mismatch')
    if flags & ~1:
        raise ValueError('Unknown packet flags')
    # Reject malformed S24 sign extension rather than silently truncating it.
    if bytes(data[34::4]).translate(S24_SIGN_BYTES) != bytes(data[35::4]):
        raise ValueError('PCM is not sign-extended S24')
    return dict(epoch=session, block_seq=seq, sample_start=start,
                sample_count=SAMPLES, clipped=bool(flags & 1))
```

<a id="s08"></a>

### S08 CP1固定常量右矩阵布局

55个非gate的1×1投影改Transpose/MatMul；另52个CAM gate采用tile8。权重值保留，98帧专用；E15为整个CP1候选收益，不能分摊到单条改动。

候选：`CP1模型 5012f8f3afd594943d37384524a8b596b1fc860c5f371058b783c396411396ac`；原路径 `tools/packed_cam_model.py` 第113–145行。

```python
        _require(len(node.output) == 1 and len(node.input) in (2, 3), 'projection arity')
        _require({a.name: helper.get_attribute_value(a) for a in node.attribute} == POINT_ATTRIBUTES,
                 'projection convolution attributes')
        _require(node.input[1] in tensors, 'projection weight initializer missing')
        weight = numpy_helper.to_array(tensors[node.input[1]])
        _require(weight.dtype == np.float32 and weight.ndim == 3 and weight.shape[2] == 1,
                 'projection weight type/shape')
        _require(np.isfinite(weight).all(), 'projection nonfinite weight')
        transpose_name = node.name+'/PG1_WT'
        ntc, mm, added = [node.name+'/PG1_'+s for s in ('input_NTC', 'mm', 'bias')]
        for name in (transpose_name, ntc, mm, added):
            _require(name not in all_tensor_names, 'new tensor collision: '+name)
            all_tensor_names.add(name)
        transpose = np.ascontiguousarray(weight[:, :, 0].T)
        _require(np.array_equal(transpose.T.view(np.uint32), weight[:, :, 0].view(np.uint32)),
                 'transposed weight bits changed')
        graph.initializer.append(numpy_helper.from_array(transpose, transpose_name))
        output_nodes.extend([
            helper.make_node('Transpose', [node.input[0]], [ntc], name=node.name+'/PG1_transpose_in', perm=[0, 2, 1]),
            helper.make_node('MatMul', [ntc, transpose_name], [mm], name=node.name+'/PG1_matmul'),
        ])
        last = mm
        if len(node.input) == 3:
            _require(node.input[2] in tensors, 'projection bias initializer missing')
            bias = numpy_helper.to_array(tensors[node.input[2]])
            _require(bias.dtype == np.float32 and bias.shape == (weight.shape[0],)
                     and np.isfinite(bias).all(), 'projection bias type/shape/values')
            output_nodes.append(helper.make_node('Add', [mm, node.input[2]], [added], name=node.name+'/PG1_add'))
            last = added
        output_nodes.append(helper.make_node('Transpose', [last], list(node.output),
                                            name=node.name+'/PG1_transpose_out', perm=[0, 2, 1]))
        replaced_weights.add(node.input[1])
        changed.append(dict(node=node.name, original_weight=node.input[1],
```

<a id="s09"></a>

### S09 VF1展开固定条件分支

展开7个由16k/形状确定的If，保留被选路径的浮点算术和循环状态。E16分别给PC VAD与ARM整体前端结果。

候选：`VF1模型 2f9baaee7df0ff223225b6fcb176ad0ae33542c7ae83015d7f87351c5c32d84c`；原路径 `tools/vad_fixed_model.py` 第35–67行。

```python
def _flatten_selected(graph):
    """Copy selected lexical branches and prune only unreachable definitions."""
    _require(not graph.sparse_initializer,'sparse weights unsupported')
    nodes=[];initializers=[];seen=set();selected=[];copied=[]

    def flatten(g):
        if g is not graph:
            _require(not g.input and not g.sparse_initializer,'selected branch must use lexical inputs')
        for t in g.initializer:initializers.append(copy.deepcopy(t))
        for node in g.node:
            if node.op_type=='If':
                _require(node.name in BRANCHES and node.name not in seen,'unexpected or duplicate If '+node.name)
                _require(node.domain in ('','ai.onnx') and len(node.input)==1,'If operator contract')
                seen.add(node.name)
                attrs={a.name:a for a in node.attribute}
                _require(len(node.attribute)==2 and set(attrs)=={'then_branch','else_branch'},'If branch attributes')
                chosen=attrs[BRANCHES[node.name]]
                _require(chosen.type==onnx.AttributeProto.GRAPH,'If branch type')
                branch=chosen.g
                _require(len(branch.output)==len(node.output),'branch output arity')
                selected.append(dict(node=node.name,branch=BRANCHES[node.name],condition=node.input[0]))
                branch_index=len(selected)
                flatten(branch)
                for idx,(source,target) in enumerate(zip(branch.output,node.output)):
                    _require(source.name!=target,'branch output alias must be explicit')
                    nodes.append(helper.make_node('Identity',[source.name],[target],
                                                  name='VF1_bridge_%d_%d'%(branch_index,idx)))
            else:
                _require(not any(a.type in (onnx.AttributeProto.GRAPH,onnx.AttributeProto.GRAPHS)
                                 for a in node.attribute),'unhandled nested graph '+node.name)
                nodes.append(copy.deepcopy(node));copied.append(node.SerializeToString())
    flatten(graph)
    _require(seen==set(BRANCHES),'expected exactly seven flattened branches')
```

<a id="s10"></a>

### S10 固定VAD的调用边界

sr输入仍在ABI中，但图内不再按sr分支；调用层必须保证16kHz，不能当通用8k模型。

候选：`同S09`；原路径 `tools/vad_fixed_model.py` 第135–141行。

```python
def validate_runtime_inputs(audio,state,sr):
    """Reference wrapper contract. Existing native vad_step hardcodes sr=16000."""
    if type(sr) is not int or sr!=FIXED_SR:raise ValueError('VF1_ONLY_16000')
    if not isinstance(audio,np.ndarray) or not isinstance(state,np.ndarray):raise ValueError('VF1_ARRAYS_REQUIRED')
    if audio.dtype!=np.float32 or audio.shape!=INPUT_SHAPE or state.dtype!=np.float32 or state.shape!=STATE_SHAPE:
        raise ValueError('VF1_SHAPE_OR_TYPE')
    if not np.isfinite(audio).all() or not np.isfinite(state).all():raise ValueError('VF1_NONFINITE')
```

<a id="s11"></a>

### S11 三维可选加权与残差证据

可选权重影响求解；仍对全部合格对计算未加权残差并检查，不把坏对证据隐藏。默认权重关闭。E17/E18为PC证据。

候选：`dfe9975168bae92af34b9c25891c3678bc5d1dc6`；原路径 `software/tetra3d/core/doa_solver_3d.c` 第154–177行。 [完整源码](https://github.com/TophBeifong1744/SoundSight/blob/dfe9975168bae92af34b9c25891c3678bc5d1dc6/software/tetra3d/core/doa_solver_3d.c#L154)。

```c
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
```

<a id="s12"></a>

### S12 DAS环缓冲与分数延时

17槽覆盖所需历史；四通道线性插值、等权叠加和最近偶数舍入保留。关闭无用trace的PC收益见E18，不是ARM实时结论。

候选：`dfe9975168bae92af34b9c25891c3678bc5d1dc6`；原路径 `software/tetra3d/das/dynamic_das.py` 第89–110行。 [完整源码](https://github.com/TophBeifong1744/SoundSight/blob/dfe9975168bae92af34b9c25891c3678bc5d1dc6/software/tetra3d/das/dynamic_das.py#L89)。

```python
    def _sample(self, ch, k):
        if k < 0 or k >= self.input_end:
            return 0
        slot = k % 17
        if self._sample_times[slot] != k:
            raise AssertionError('required sample was released or not yet received')
        return self.samples[slot][ch]

    def _beam(self, target, n):
        if n < 0:
            return 0
        if target is None:
            return self._sample(0, n)
        acc = 0
        sample = self._sample
        for ch, delay in enumerate(target):
            left, frac = divmod(n*Q-delay, Q)
            # Do not read zero-weight right sample: exact -8 needs no +9 lookahead.
            acc += sample(ch, left)*(Q-frac)
            if frac:
                acc += sample(ch, left+1)*frac
        return rne(acc, 4*Q)
```

<a id="s13"></a>

### S13 三维模块接合和时基失效

统一求解/空间滤波/可选DAS与纯软件轴；过旧新帧清除旧滤波状态，防止后续poll复活旧目标。不是PYNQ在线运行入口，也不实现人物识别。

候选：`dfe9975168bae92af34b9c25891c3678bc5d1dc6`；原路径 `software/tetra3d/linux/pipeline_3d.py` 第251–278行。 [完整源码](https://github.com/TophBeifong1744/SoundSight/blob/dfe9975168bae92af34b9c25891c3678bc5d1dc6/software/tetra3d/linux/pipeline_3d.py#L251)。

```python
            result = self._solver.solve(frame)
            flags = frame['status']
            unsafe = (fault != 0 or bool(flags & (8 | 0x8000 | 0x100000 | 0xff000000))
                      or frame.get('stopped', False) or frame.get('drain', False)
                      or result['bridge_status'] != 0 or result['api_status'] != 0
                      or result['reason'] in (5, 6, 7, 8))
            stale = now/self.sample_rate_hz-capture/self.sample_rate_hz > self._filter_config.max_age_s
            if unsafe or stale:
                # Discard HOLD as well as candidates; never carry a real target
                # across BIST, stop/drain, cancelled data or a source fault.
                # A stale frame must not reject once and then revive the old
                # target on the next poll/push boundary.
                self._filter = DirectionFilter3D(self._filter_config)
                filter_input = {'direction_valid': 0}
            else:
                filter_input = result
            direction = self._filter.update(filter_input,
                timestamp_s=capture/self.sample_rate_hz, now_s=now/self.sample_rate_hz,
                sequence=sequence, session_id=self.session_id,
                target_id=self.target_id)['filtered_direction']
            if unsafe:
                direction['reason'] = 'source_fault_bist_or_stop'
            self._direction = direction
            self._now, self._capture, self._sequence = now, capture, sequence
            return copy.deepcopy(dict(frame=frame, result=result,
                filtered_direction=direction, axis_setpoint=self._axis(direction, now),
                motion_requested=False, timing=dict(capture_sample=capture,
                    now_sample=now, sample_rate_hz=self.sample_rate_hz)))
```
