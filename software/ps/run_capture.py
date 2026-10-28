'PS capture using an already loaded overlay. No bitstream download or PS reset.'
import argparse
import contextlib
import json
import os
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

from ps_client import Client, Solver, STATUS


def address_from_hwh(path, instance='ps_link'):
    """从实际HWH取地址；校验模块种类，避免误操作其它MMIO设备。"""
    tree=ET.parse(path)
    modules=[m for m in tree.iter('MODULE') if m.get('INSTANCE')==instance
             and m.get('MODTYPE')=='bd_ps_link']
    if len(modules)!=1:
        raise ValueError('HWH has no unique bd_ps_link instance: '+instance)
    ranges={(int(m.get('BASEVALUE'),0),int(m.get('HIGHVALUE'),0))
            for m in tree.iter('MEMRANGE') if m.get('INSTANCE')==instance
            and m.get('SLAVEBUSINTERFACE')=='S_AXI' and m.get('MEMTYPE')=='REGISTER'}
    if len(ranges)!=1:raise ValueError('HWH has no unique S_AXI register address range')
    base,high=ranges.pop();size=high-base+1
    if size!=4096 or base%4096:raise ValueError('This interface requires an aligned 4-KiB address range')
    return base,size


def require_legacy_motion_hwh(path, instance='ps_link'):
    """Keep old un-gated automatic motion off the new dual-axis platform.

    This is a metadata-only check, before worker startup or MMIO. Older HWH
    files predate DUAL_AXIS_ENABLE, so absent means the legacy single axis.
    Manual calibration does not use this automatic-follow guard.
    """
    modules = [m for m in ET.parse(path).iter('MODULE')
               if m.get('INSTANCE') == instance and m.get('MODTYPE') == 'bd_ps_link']
    if len(modules) != 1:
        raise ValueError('HWH has no unique bd_ps_link instance: '+instance)
    params = {p.get('NAME'): p.get('VALUE') for p in modules[0].iter('PARAMETER')}
    if int(params.get('DUAL_AXIS_ENABLE', '0'), 0) != 0:
        raise ValueError('Dual-axis hardware requires soundsight-3d.sh speaker --axes; legacy automatic motion is disabled')


@contextlib.contextmanager
def single_owner(path):
    """Linux进程互斥；防止两个本程序同时消费同一套双槽。"""
    import fcntl
    # 锁文件不是任务凭证；程序退出即释放，绝不保存硬件会话状态。
    with open(path,'a',encoding='utf-8') as handle:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another PS capture process still owns the device') from None
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)


def durable_sink(handle):
    """fsync成功后才允许调用方消费硬件槽；不能保证存储介质自身永不掉电丢失。"""
    def save(record):
        handle.write(json.dumps(record,ensure_ascii=False)+'\n')
        handle.flush();os.fsync(handle.fileno())
    return save


def capture(client,sink,mode,count,drain_existing=False,config=None,
            watchdog_ticks=None,clear_faults=0,stats=None):
    """出错或Ctrl+C均先请求停用；存储失败的锁帧由Client保留。"""
    if watchdog_ticks is not None and (mode!='real' or drain_existing or config is None):
        raise ValueError('Motion requires new real frames and mechanical calibration')
    def one(allow_fault=False):
        began=time.monotonic_ns()
        if allow_fault:record=client.record_one(sink,allow_fault=True)
        elif watchdog_ticks is not None:record=client.record_one(sink,config,motion=True)
        else:record=client.record_one(sink)
        if stats is not None:
            elapsed=time.monotonic_ns()-began
            stats['consumed']=stats.get('consumed',0)+1
            stats['max_service_ns']=max(stats.get('max_service_ns',0),elapsed)
        return record
    client.identify()
    try:
        if drain_existing:
            client.disable()
            saved=0
            while client.read(STATUS)&3:
                one(allow_fault=True);saved+=1
            return saved
        kwargs={'clear_faults':clear_faults} if clear_faults else {}
        client.start(bist={'bist-reject':0,'bist-pass':1,'real':None}[mode],**kwargs)
        if watchdog_ticks is not None:client.arm(watchdog_ticks)
        for _ in range(count):one()
        return count
    finally:
        # disable不消费/清槽；错误留在硬件，后续可用--drain-existing保存。
        # 不能让清理异常盖住原存储错误；两者都打印，原异常继续上抛。
        original=sys.exc_info()[0]
        try:client.disable()
        except Exception as exc:
            if original is None:raise
            print('Disable/drain also failed; preserve state: '+str(exc),file=sys.stderr)


def argument_parser():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hwh',type=Path,required=True,help='Actual HWH matching the currently loaded bitstream')
    parser.add_argument('--ip',default='ps_link',help='Module Reference instance name in HWH')
    parser.add_argument('--library',type=Path,default=Path(__file__).with_name('libss_solver.so'))
    parser.add_argument('--output',type=Path,required=True,help='Append JSONL; consume only after successful save')
    parser.add_argument('--mode',choices=['bist-reject','bist-pass','real'],default='bist-reject')
    parser.add_argument('--frames',type=int,default=1)
    parser.add_argument('--drain-existing',action='store_true',help='Disable and save existing frames only; do not start capture')
    parser.add_argument('--lock-file',default='/tmp/soundsight-ps-owner.lock')
    parser.add_argument('--clear-faults',type=lambda v:int(v,0),default=0,
                        help='Clear only explicitly selected historical faults; resolve causes and old slots first')
    parser.add_argument('--horizontal-motion',action='store_true',help='Explicitly enable horizontal motion supported by this ABI')
    parser.add_argument('--servo-config',type=Path,help='Measured calibration config[7] JSON array; no default')
    parser.add_argument('--watchdog-ticks',type=lambda v:int(v,0),help='Agreed watchdog ticks at 61.44 MHz; no default')
    return parser


def validate_servo_config(config):
    """仅检查现有C合同的配置范围；角度映射及舍入仍由唯一C算法计算。"""
    if not isinstance(config,list) or len(config)!=7 or any(type(v) is not int or not -2**31<=v<2**31 for v in config):
        raise ValueError('Mechanical calibration must contain seven int32 values')
    offset,direction,lo,hi,mechanical_lo,mechanical_hi,servo_max=config
    if not (-8388608<=offset<=8388607 and direction in (-1,1)
            and -46080<=lo<=hi<46080 and 0<=mechanical_lo<=mechanical_hi<=servo_max<=511
            and servo_max>=1):
        raise ValueError('Mechanical calibration is outside the C contract range')
    return config


def prepare_args(args,parser):
    if args.frames<1:parser.error('--frames must be at least 1')
    if not args.drain_existing and args.mode!='real' and args.frames!=1:
        parser.error('BIST generates one frame per run; --frames must be 1')
    if not 0<=args.clear_faults<=0xfff:parser.error('--clear-faults must be in 0..0xfff')
    config=None
    if args.horizontal_motion:
        if args.mode!='real' or args.drain_existing:parser.error('Motion is only allowed for new real frames')
        if args.servo_config is None or args.watchdog_ticks is None:
            parser.error('Motion requires --servo-config and --watchdog-ticks')
        if not 1<=args.watchdog_ticks<=0xffffffff:parser.error('Watchdog must be a nonzero 32-bit value')
        try:config=validate_servo_config(json.loads(args.servo_config.read_text(encoding='utf-8')))
        except ValueError as exc:parser.error(str(exc))
        require_legacy_motion_hwh(args.hwh, args.ip)
    elif args.servo_config is not None or args.watchdog_ticks is not None:
        parser.error('Motion parameters require explicit --horizontal-motion')
    return config


def main(argv=None):
    parser=argument_parser();args=parser.parse_args(argv);config=prepare_args(args,parser)
    base,size=address_from_hwh(args.hwh,args.ip)
    solver=Solver(args.library)  # ARM库不匹配会在访问硬件前报错。
    with single_owner(args.lock_file):
        from pynq import MMIO
        client=Client(MMIO(base,size),solver)
        with args.output.open('a',encoding='utf-8') as handle:
            saved=capture(client,durable_sink(handle),args.mode,args.frames,args.drain_existing,
                          config,args.watchdog_ticks,args.clear_faults)
    print('SAVED_FRAMES=',saved,'HORIZONTAL_MOTION=',args.horizontal_motion)
    return 0


if __name__=='__main__':raise SystemExit(main())
