"""无STM32版PS客户程序。ip为已加载overlay中的MMIO对象；本文件不加载/下载位流。

软件单一所有者运行，不允许两个进程同时操作快照。默认仅求解/记录，不请求运动。
主方案PL+STM32+PS不得使用此客户端消费快照。
"""
import ctypes as C
import json
import time
import sys
from pathlib import Path

MAGIC, SYS, SEQ, FEATURE, PEAK, ENERGY, ANGLE, SELECT = 0,4,8,12,16,20,24,28
LEFT, RIGHT, SECOND, BIST, STATUS, SNAP, ACT, WDT, FAULT, DROP, ABI = 32,36,40,44,52,56,88,96,100,104,108

class Solver:
    def __init__(self, library):
        self.lib=C.CDLL(str(Path(library).resolve()))
        self.call=self.lib.ss_solve_words
        self.call.argtypes=[C.c_uint32,C.c_uint32,C.POINTER(C.c_uint32),C.POINTER(C.c_int32),C.POINTER(C.c_int32)]
        self.call.restype=C.c_int
    def solve(self, frame, config=None):
        if len(frame['words'])!=30:raise ValueError('需要完整六对，每对五个字')
        if config is not None and len(config)!=7:raise ValueError('机械配置需要七个参数')
        words=(C.c_uint32*30)(*frame['words']);out=(C.c_int32*12)()
        cfg=(C.c_int32*7)(*config) if config is not None else None
        rc=self.call(frame['sequence'],frame['status'],words,cfg,out)
        keys=['api_status','direction_valid','reason','angle_q8','ux_q20','uy_q20','valid_pairs','servo_deg','servo_cmd_valid','map_status','first_error','bad_pair']
        result=dict(zip(keys,out));result['bridge_status']=rc
        return result

class Client:
    def __init__(self, ip, solver):
        self.ip=ip;self.solver=solver;self.last_consumed=None
    def read(self, address):return int(self.ip.read(address)) & 0xffffffff
    def write(self, address, value):self.ip.write(address,int(value))
    def identify(self):
        if self.read(MAGIC)!=0x5a5a2026 or self.read(ABI)!=0x00010000:
            raise RuntimeError('硬件ID/ABI不匹配')
    def stop(self):
        # 即使后续读取/排空失败，第一步已经要求硬件停止新增并撤动作许可。
        self.write(ACT,2)
    def disable(self, timeout=0.25):
        self.stop();mode=self.read(SYS)&2
        self.write(SYS,8|mode)
        deadline=time.monotonic()+timeout
        while self.read(STATUS)&0x8000:
            if time.monotonic()>deadline:raise TimeoutError('仍在排空；保留记录，不自动复位')
            time.sleep(.001)
    def start(self, bist=None, clear_faults=0):
        if type(clear_faults) is not int or not 0<=clear_faults<=0xfff:
            raise ValueError('清错掩码必须在0..0xfff内')
        self.identify();before=self.read(FAULT);self.disable()
        # 已保存结果由调用者先处理，绝不为了启动偷偷消费。
        if self.read(STATUS)&3:raise RuntimeError('先处理已有快照，再启动新会话')
        # 只自动清本次STOP新增的取消位；历史故障须由操作者显式选择。
        if before&~clear_faults:
            raise RuntimeError('启动前有历史故障0x%x；处理原因和旧槽后显式指定清错掩码'%before)
        self.write(SYS,8);self.write(FAULT,(before&clear_faults)|0x40)
        if self.read(FAULT):raise RuntimeError('故障原因未消失')
        if bist is not None:
            if bist not in (0,1):raise ValueError('BIST只能0或1')
            self.write(BIST,bist);self.write(SYS,11)
        else:self.write(SYS,9)
    def acquire(self, timeout=0.25):
        deadline=time.monotonic()+timeout
        while True:
            status=self.read(STATUS)
            if status&3:break
            if self.read(FAULT):raise RuntimeError('设备报错；查看FAULT并保留现场')
            if time.monotonic()>deadline:raise TimeoutError('没有完整快照')
            time.sleep(.001)
        self.write(SNAP,1);status=self.read(STATUS);seq=self.read(SEQ)
        if not status&1 or not seq:raise RuntimeError('未锁住完整帧')
        if seq==self.last_consumed:raise RuntimeError('帧序号重复；先核对是否发生冷复位')
        words=[]
        for pair in range(6):
            self.write(SELECT,pair)
            words.extend(self.read(a) for a in (FEATURE,PEAK,LEFT,RIGHT,SECOND))
            if (words[-5]>>8)&7!=pair:raise RuntimeError('pair回显错误，保留锁帧')
        # 队列允许新帧到来，比较仅使用被锁帧的稳定字段，不比较实时IRQ/queued。
        after=self.read(STATUS)
        if self.read(SEQ)!=seq or not after&1 or (after^status)&0xff100018:
            raise RuntimeError('读取期间锁帧变化')
        return dict(sequence=seq,status=status,words=words,energy=self.read(ENERGY),fault=self.read(FAULT),drops=self.read(DROP))
    def consume(self, frame):
        if not self.read(STATUS)&1 or self.read(SEQ)!=frame['sequence']:
            raise RuntimeError('当前锁帧与待消费记录不一致')
        self.write(SNAP,4);self.last_consumed=frame['sequence']
    def record_one(self, sink, config=None, motion=False, allow_fault=False):
        """sink必须把记录保存成功才返回；失败时保留硬件槽并请求STOP。"""
        try:
            began=time.monotonic_ns();frame=self.acquire();acquired=time.monotonic_ns()
            if frame['fault'] and not allow_fault:
                raise RuntimeError('锁帧时发现故障0x%x；STOP并保帧，使用排空模式保存'%frame['fault'])
            result=self.solver.solve(frame,config)
            record=dict(frame=frame,result=result,motion_requested=motion,
                        timing_ns={'acquire':acquired-began,'solve':time.monotonic_ns()-acquired})
            sink(record)
            if result['bridge_status']!=0:raise RuntimeError('C桥报错；已保存输入，保留锁帧')
            if motion and result['bridge_status']==0 and result['direction_valid'] and result['servo_cmd_valid']:
                self.command(frame,result)
                # 这里只确认COMMIT后未读到故障；没有机械位置反馈。
                sink(dict(frame={'sequence':frame['sequence']},
                          action='commit_no_fault_observed',mechanical_arrival='UNVERIFIED'))
            if not allow_fault and self.read(FAULT):raise RuntimeError('保存期间设备新增故障；STOP并保帧')
            self.consume(frame)
            return record
        except BaseException:
            try:self.stop()
            except Exception as exc:print('STOP也失败：'+str(exc),file=sys.stderr)
            raise
    def arm(self, watchdog_ticks):
        if not 1<=watchdog_ticks<=0xffffffff:raise ValueError('看门狗必须非零且在32位内')
        if not self.read(STATUS)&0x80000:raise RuntimeError('硬件执行器参数未绑定')
        if self.read(SYS)!=9 or self.read(FAULT):raise RuntimeError('需无故障真实模式')
        self.write(ACT,4);self.write(WDT,watchdog_ticks);self.write(ACT,1)
        if not self.read(ACT)&1:raise RuntimeError('硬件未授予运动许可')
    def command(self, frame, result):
        # 必须在消费前调用；求解成功不自动意味着允许动作。
        status=self.read(STATUS)
        if result['bridge_status'] or not result['direction_valid'] or not result['servo_cmd_valid'] or frame['status']&8:
            raise RuntimeError('没有合法的真实帧舵机命令')
        if not status&1 or self.read(SEQ)!=frame['sequence'] or not self.read(ACT)&1 or self.read(FAULT):
            raise RuntimeError('锁帧/许可/故障条件不满足')
        self.write(ANGLE,0x40000|result['servo_deg']);self.write(ACT,8)
        if self.read(FAULT):raise RuntimeError('动作未被硬件正常接收；查看故障')

def jsonl_sink(file):
    """每条写入后flush；需要落盘耐久性时由应用在flush后执行os.fsync。"""
    def save(record):
        file.write(json.dumps(record,ensure_ascii=False)+'\n');file.flush()
    return save
