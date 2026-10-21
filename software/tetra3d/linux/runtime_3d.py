"""C的三维应用适配；复用已验证的快照/STOP，三维路径仅计算和记录。"""
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'software/ps'))
from run_smp import InterruptibleClient
from volume_gate import VolumeClient,LEVEL_CAP,LEVEL_VALID


class SolverAdapter3D:
    """满足旧Client的调用签名，数值计算仍只调用B的Solver3D一次。"""
    def __init__(self,solver):self.solver=solver
    @property
    def geometry(self):return self.solver.geometry
    def solve(self,frame,config=None):
        if config is not None:raise ValueError('3D direction entry does not accept motion configuration')
        result=self.solver.solve(frame)
        if result['servo_cmd_valid']!=0:raise RuntimeError('3D direction solver unexpectedly enabled motion')
        return result


class Client3D(InterruptibleClient):
    """CPU1唯一硬件所有者；连直接调用arm/command也拒绝，STOP仍可正常执行。"""
    def __init__(self,ip,solver,cancel,measure_level=False):
        super().__init__(ip,solver,cancel);self.measure_level=measure_level
    def identify(self):
        # 明确选择配套ABI；借用主线只读身份检查，不调用二维角度门限函数。
        if self.measure_level:VolumeClient.identify(self)
        else:super().identify()
    def arm(self,*args,**kwargs):raise RuntimeError('3D direction-only: arm is disabled')
    def command(self,*args,**kwargs):raise RuntimeError('3D direction-only: command is disabled')
    def record_one(self,sink,config=None,motion=False,allow_fault=False):
        if config is not None or motion:raise ValueError('3D direction-only: motion is disabled')
        def save(record):
            record=dict(record,profile='TETRA40_3D',geometry=self.solver.geometry,motion='DISABLED',
                        direction_output=dict(valid=False,reason='raw_solver_only'))
            if self.measure_level:
                status=record['frame']['status']
                measured=bool(status&LEVEL_CAP and status&LEVEL_VALID and not status&8)
                record['volume']=dict(measured=measured,
                    level_counts=record['frame']['energy'] if measured else None,
                    threshold_counts=None,unit='mean_abs_dc_removed_pcm')
            sink(record)
        return super().record_one(save,allow_fault=allow_fault)


def display_3d(record):
    """只有本次有效角度才显示数值；不能把极点或失败默认0度当成测量。"""
    if 'result' not in record:return
    result=record['result'];sequence=record['frame']['sequence']
    if result['bridge_status']:
        print('3D frame=%d API_ERROR=%d'%(sequence,result['bridge_status']),flush=True)
        return
    if not result['direction_valid']:
        print('3D frame=%d REJECTED reason=%d'%(sequence,result['reason']),flush=True)
        return
    az='%.6f deg'%result['azimuth_deg'] if result['azimuth_valid'] else 'UNOBSERVABLE'
    el='%.6f deg'%result['elevation_deg'] if result['elevation_valid'] else 'INVALID'
    geometry=record['geometry']
    print('RAW_SOLVER_3D frame=%d az=%s el=%s geometry=%s/%s fault=0x%x motion=DISABLED'%(
        sequence,az,el,geometry['provenance'],geometry['source_id'],record['frame'].get('fault',0)),flush=True)


def durable_sink_3d(handle,display=display_3d):
    """CPU0严格JSON落盘后显示；任一步失败均不发ACK，不消费失败帧。"""
    def save(record):
        handle.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
        handle.flush();os.fsync(handle.fileno())
        if display is not None:display(record)
    return save


def frame_from_record(record):
    """支持B的裸frame及C的采集日志；显式跳过会话/动作记录，不猜缺字帧。"""
    if not isinstance(record,dict):raise ValueError('expected a frame or capture record')
    if 'frame' in record:
        frame=record['frame']
        if isinstance(frame,dict) and set(frame)=={'sequence'} and 'action' in record:return None
    elif record.get('event') in ('startup','finished','failed'):
        return None
    else:frame=record
    if not isinstance(frame,dict) or not {'sequence','status','words'}<=set(frame):
        raise ValueError('frame requires sequence/status/words')
    return frame


def replay(source,sink,solver):
    """离线原始帧/现有日志回放；错误原文落盘后停止，正常算法拒绝继续。"""
    from solver_3d import read_json
    count=0
    for number,line in enumerate(source,1):
        try:
            frame=frame_from_record(read_json(line))
            if frame is None:continue
            began=time.perf_counter_ns();result=solver.solve(frame)
            elapsed=time.perf_counter_ns()-began
        except (ValueError,KeyError,TypeError) as exc:
            sink(dict(event='input_error',input_line=number,error=str(exc),raw_line=line.rstrip('\r\n')))
            raise
        sink(dict(frame=frame,result=result,geometry=solver.geometry,profile='TETRA40_3D',
                  replay=True,geometry_binding='EXPLICIT_RECOMPUTE',input_line=number,
                  call_ns=elapsed,motion='DISABLED'))
        count+=1
        if result['bridge_status']:raise RuntimeError('3D API error saved; stopped at input line %d'%number)
    if not count:raise ValueError('no complete frames; no validation performed')
    return count
