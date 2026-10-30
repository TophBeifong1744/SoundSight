"""Offline paired background/front-speech analysis; no hardware or parameter writes."""
from pathlib import Path
import collections,hashlib,io,json,subprocess,sys,wave,zipfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'software/ps'),str(ROOT/'tools')]
from ps_client import Solver
from volume_gate import gate_record
from angle_filter import OnlineAngleFilter,circular_mean,difference
from tool_config import gcc_executable
build=ROOT/'simulation/work/pcm-front-replay';build.mkdir(parents=True,exist_ok=True)
cmd=[str(gcc_executable()),'-std=c99','-O2','-Wall','-Wextra','-Werror','-shared',
     '-I'+str(ROOT/'software/common'),'-I'+str(ROOT/'software/common/s1'),
     str(ROOT/'software/common/s1/doa_solver.c'),str(ROOT/'software/ps/ss_solver_bridge.c'),'-lm','-o',str(build/'solver.dll')]
p=subprocess.run(cmd,capture_output=True)
(HERE/'compile.log').write_bytes(p.stdout+p.stderr)
(HERE/'compile-command.json').write_text(json.dumps(cmd,indent=2))
assert p.returncode==0,p.stderr
solver=Solver(build/'solver.dll')
source=HERE/'input/soundsight_pcm_front_background.zip'

def inspect(z,folder,expected_blocks):
    result=json.loads(z.read(folder+'/result.json'))
    binary=z.read(folder+'/packets.bin');wav_bytes=z.read(folder+'/four_mic.wav')
    assert len(binary) % 8224 == 0
    n = len(binary)//8224
    assert n == result['requested_blocks'] == len(result['packets']) == expected_blocks
    blocks = np.frombuffer(binary, dtype='<i4').reshape(n, 2056)
    headers = blocks[:, :8].view('<u4')
    assert np.all(headers[:, 0] == 0x43505353)
    assert np.all(headers[:, 1] == 0x00200001)
    assert np.all(headers[:, 2] == result['epoch'])
    assert np.array_equal(headers[:, 3], np.arange(n))
    assert np.array_equal(headers[:, 4], np.arange(n)*512)
    assert np.all(headers[:, 5] == 0)
    assert np.all((headers[:, 6] & 65535) == 512)
    assert np.all((headers[:, 6] >> 16) <= 1)
    assert np.all(headers[:, 7] == 8192)
    pcm = blocks[:, 8:].reshape(-1, 4).copy()
    assert pcm.min() >= -8388608 and pcm.max() <= 8388607
    with wave.open(io.BytesIO(wav_bytes), 'rb') as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (4,3,48000,len(pcm))
        raw = np.frombuffer(w.readframes(w.getnframes()), np.uint8).reshape(-1,3).astype(np.int32)
        decoded = raw[:,0] | (raw[:,1]<<8) | (raw[:,2]<<16)
        decoded = ((decoded ^ 0x800000)-0x800000).reshape(-1,4)
        assert np.array_equal(pcm, decoded)
    assert result['result'] == 'PASS' and result['error'] is None and not result['cleanup_errors']
    assert result['dma_halted'] and not result['motion'] and result['final_ps']['drops']==0
    frames = result['frames']
    assert len(frames) == (len(pcm)-1024)//512+1
    for i,f in enumerate(frames):
        m=f['audio']
        assert f['fault']==0 and f['drops']==0
        assert m['valid'] and m['covered_by_recording']
        assert (m['epoch'],m['sample_start'],m['sample_count']) == (result['epoch'],i*512,1024)
        assert m['source_window']==frames[0]['audio']['source_window']+i
        assert f['sequence']==frames[0]['sequence']+i
    expected=json.loads((ROOT/'document/evidence/ps-cdc-control-fix-20261024/board-package/hardware-review.json').read_text())
    assert all(result['hardware'][key+'_sha256']==expected['hardware'][key]['sha256'] for key in ('bit','hwh','xsa'))
    x=pcm.astype(float);x-=x.mean(axis=0)
    power=np.mean(x*x,axis=0);rms=np.sqrt(power)
    rms100=np.sqrt(np.mean(x[:len(x)//4800*4800].reshape(-1,4800,4)**2,axis=1))
    hann=np.hanning(4096);freq=np.fft.rfftfreq(4096,1/48000)
    windows=np.lib.stride_tricks.sliding_window_view(x,4096,axis=0)[::2048]
    psd=(np.abs(np.fft.rfft(windows*hann,axis=-1))**2).mean(axis=0)*2/(48000*(hann*hann).sum())
    filtered=OnlineAngleFilter();replay=[]
    for frame in frames:
        sol=solver.solve(frame);assert sol['bridge_status']==0
        gate=gate_record(dict(frame=frame,result=sol),7000)
        rec=filtered.apply(gate)
        replay.append(dict(sequence=frame['sequence'],time_s=frame['audio']['sample_start']/48000,
                           energy=frame['energy'],solver=sol,gate=gate['direction_output'],
                           filter=rec['angle_filter'],output=rec['direction_output']))
    levels=np.array([f['energy'] for f in frames]);valid=[s for s in replay if s['solver']['direction_valid']]
    gated=[s for s in replay if s['gate']['valid']];outputs=[s for s in replay if s['output']['valid']]
    angles=[s['solver']['angle_q8']/256 for s in gated];center=circular_mean(angles)
    strong=[s for s in replay if s['energy']>=7000]
    summary=dict(epoch=result['epoch'],packets=n,samples_per_channel=len(pcm),seconds=len(pcm)/48000,
        continuity='PASS',wav_matches_packets=True,hardware_matches=True,frames=len(frames),
        final_ps=result['final_ps'],final_audio=result['final_audio_before_dma_reset'],
        clipped_packets=int(np.count_nonzero(headers[:,6]>>16)),
        full_scale_samples=int(np.count_nonzero((pcm==-8388608)|(pcm==8388607))),
        pcm_ac_rms=rms.tolist(),pcm_mean_abs=np.abs(pcm.astype(float)).mean(axis=0).tolist(),
        pcm_peak_percent_full_scale=(np.abs(pcm.astype(float)).max(axis=0)/8388608*100).tolist(),
        dc_mean=pcm.astype(float).mean(axis=0).tolist(),
        identical_channel_pairs=[(a,b) for a in range(4) for b in range(a+1,4) if np.array_equal(pcm[:,a],pcm[:,b])],
        level_min_p10_p50_p90_p99_max=np.percentile(levels,[0,10,50,90,99,100]).tolist(),
        level_ge_7000=int((levels>=7000).sum()),solver_valid=len(valid),
        solver_reasons=dict(collections.Counter(s['solver']['reason'] for s in replay)),
        solver_reasons_above_gate=dict(collections.Counter(s['solver']['reason'] for s in strong)),
        valid_above_gate=len(gated),gated_angle_circular_mean_deg=center,
        gated_angle_offset_from_mean_p10_p50_p90=np.percentile([difference(a,center) for a in angles],[10,50,90]).tolist() if angles else [],
        filtered_complete_windows=sum(s['filter']['complete'] for s in replay),
        filtered_accepted_windows=len(outputs),filtered_angles=[s['output']['angle_deg'] for s in outputs],
        filtered_reasons=dict(collections.Counter(s['output']['reason'] for s in replay)),
        strongest_frequency_hz=[float(freq[1+np.argmax(row[1:])]) for row in psd],
        power_fraction_below_300Hz=(psd[:,freq<300].sum(axis=1)/psd.sum(axis=1)).tolist())
    return dict(summary=summary,replay=replay,rms100=rms100,psd=psd,freq=freq,power=power)

with zipfile.ZipFile(source) as z:
    assert z.testzip() is None
    background=inspect(z,'pcm-20211118-083010-763369',256)
    speech=inspect(z,'pcm-20211118-083126-118712',1024)
comparison=10*np.log10(speech['power']/background['power'])
report=dict(scope='User-provided recordings; no live board actions or product changes',
    input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    recording_labels='Assigned from user commands: epoch4 quiet background; epoch5 fixed approximate front at requested ~1m, continuous speech',
    filter_assumption=dict(level=7000,window=20,min_valid=12,radius_deg=10,consensus='2/3',deadband_deg=3,
        note='Offline default diagnostic only; actual saved user settings and mechanical front calibration were not supplied'),
    background=background['summary'],speech=speech['summary'],
    speech_to_background_total_power_db=comparison.tolist(),
    caveat='Power contrast is not a calibrated speech-only SNR. No measured reference angle or subjective listening.',
    source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [ROOT/'software/common/s1/doa_solver.c',ROOT/'software/common/s1/doa_solver.h',
         ROOT/'software/common/fpga_stm32_abi_frozen.h',ROOT/'software/ps/ss_solver_bridge.c',
         ROOT/'software/ps/volume_gate.py',ROOT/'software/ps/angle_filter.py']})
with zipfile.ZipFile(ROOT/'release/output/soundsight_pynq_pcm_cdc.zip') as delivered:
    for name,digest in report['source_hashes'].items():
        payload=delivered.read('SoundSight_PYNQ_PCM_CDC/'+name.replace('\\','/'))
        assert hashlib.sha256(payload).hexdigest()==digest,name
report['replay_sources_match_delivered_package']=True
angles=report['speech']['filtered_angles']
report['speech'].update(filtered_mean_deg=float(np.mean(angles)) if angles else None,
    filtered_std_deg=float(np.std(angles)) if angles else None,
    filtered_range_deg=[min(angles),max(angles)] if angles else [])
(HERE/'analysis.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
for label,data in [('background',background),('speech',speech)]:
    (HERE/(label+'-replay.json')).write_text(json.dumps(data['replay'],indent=2)+'\n',encoding='utf-8')
fig,axes=plt.subplots(2,2,figsize=(13,8),constrained_layout=True)
for ax,(label,data) in zip(axes[0],[('Background',background),('Front speech',speech)]):
    for c in range(4):ax.plot((np.arange(len(data['rms100']))+.5)*.1,20*np.log10(data['rms100'][:,c]/8388608),label='Mic '+str(c))
    ax.set(title=label+': 100 ms RMS',xlabel='Time (s)',ylabel='dBFS',ylim=(-70,-38));ax.grid(alpha=.3);ax.legend(ncol=2)
ax=axes[1,0]
for label,data in [('Background',background),('Front speech',speech)]:ax.plot(data['freq'],10*np.log10(np.maximum(data['psd'].mean(axis=0)/8388608**2,1e-20)),label=label)
ax.set(title='Average four-channel PSD',xlabel='Frequency (Hz)',ylabel='dBFS/Hz',xlim=(0,5000));ax.legend();ax.grid(alpha=.3)
ax=axes[1,1];replay=speech['replay']
for valid,color,label in [(True,'green','Raw valid + level >= 7000'),(False,'gray','Raw valid below level gate')]:
    items=[s for s in replay if s['solver']['direction_valid'] and (s['energy']>=7000)==valid]
    ax.scatter([s['time_s'] for s in items],[s['solver']['angle_q8']/256 for s in items],s=7,color=color,label=label)
items=[s for s in replay if s['output']['valid']]
ax.scatter([s['time_s'] for s in items],[s['output']['angle_deg'] for s in items],marker='x',s=50,color='red',label='Default filtered output')
ax.set(title='Front speech: offline direction replay',xlabel='Time (s)',ylabel='Raw array angle (degrees)',ylim=(-180,180));ax.legend(fontsize=8);ax.grid(alpha=.3)
fig.savefig(HERE/'background-front-comparison.png',dpi=150);plt.close(fig)
print(json.dumps(report,indent=2))
