"""无STM32版的目标PS运行入口；只连接已经加载的设计，不下载bit、不复位PS。

默认只做拒绝BIST和记录，不授予运动许可。真实模式也仅解算和记录。
用户先完成DDR/MIO/PYNQ环境，加载与传入HWH配套的bit，再运行本程序。
"""
import argparse
import contextlib
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from ps_client import Client, Solver, STATUS


def address_from_hwh(path, instance='ps_link'):
    """从实际HWH取地址；校验模块种类，避免误操作其它MMIO设备。"""
    tree=ET.parse(path)
    modules=[m for m in tree.iter('MODULE') if m.get('INSTANCE')==instance
             and m.get('MODTYPE')=='bd_ps_link']
    if len(modules)!=1:
        raise ValueError('HWH中没有唯一的bd_ps_link实例：'+instance)
    ranges={(int(m.get('BASEVALUE'),0),int(m.get('HIGHVALUE'),0))
            for m in tree.iter('MEMRANGE') if m.get('INSTANCE')==instance
            and m.get('SLAVEBUSINTERFACE')=='S_AXI' and m.get('MEMTYPE')=='REGISTER'}
    if len(ranges)!=1:raise ValueError('HWH没有唯一的S_AXI寄存器地址段')
    base,high=ranges.pop();size=high-base+1
    if size!=4096 or base%4096:raise ValueError('本接口要求对齐的4KiB地址段')
    return base,size


@contextlib.contextmanager
def single_owner(path):
    """Linux进程互斥；防止两个本程序同时消费同一套双槽。"""
    import fcntl
    # 锁文件不是任务凭证；程序退出即释放，绝不保存硬件会话状态。
    with open(path,'a',encoding='utf-8') as handle:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('另一PS取数程序仍持有控制权') from None
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)


def durable_sink(handle):
    """fsync成功后才允许调用方消费硬件槽；不能保证存储介质自身永不掉电丢失。"""
    def save(record):
        handle.write(json.dumps(record,ensure_ascii=False)+'\n')
        handle.flush();os.fsync(handle.fileno())
    return save


def capture(client,sink,mode,count,drain_existing=False):
    """出错或Ctrl+C均先请求停用；存储失败的锁帧由Client保留。"""
    client.identify()
    try:
        if drain_existing:
            client.disable()
            saved=0
            while client.read(STATUS)&3:
                client.record_one(sink);saved+=1
            return saved
        client.start(bist={'bist-reject':0,'bist-pass':1,'real':None}[mode])
        for _ in range(count):client.record_one(sink)
        return count
    finally:
        # disable不消费/清槽；错误留在硬件，后续可用--drain-existing保存。
        # 不能让清理异常盖住原存储错误；两者都打印，原异常继续上抛。
        original=sys.exc_info()[0]
        try:client.disable()
        except Exception as exc:
            if original is None:raise
            print('停用/排空也失败，保留现场：'+str(exc),file=sys.stderr)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hwh',type=Path,required=True,help='当前已加载bit配套的实际HWH')
    parser.add_argument('--ip',default='ps_link',help='HWH中的Module Reference实例名')
    parser.add_argument('--library',type=Path,default=Path(__file__).with_name('libss_solver.so'))
    parser.add_argument('--output',type=Path,required=True,help='追加写入JSONL；保存成功才消费')
    parser.add_argument('--mode',choices=['bist-reject','bist-pass','real'],default='bist-reject')
    parser.add_argument('--frames',type=int,default=1)
    parser.add_argument('--drain-existing',action='store_true',help='停用后只保存已有帧，不启动新采集')
    parser.add_argument('--lock-file',default='/tmp/soundsight-ps-owner.lock')
    args=parser.parse_args(argv)
    if args.frames<1:parser.error('--frames至少为1')
    if not args.drain_existing and args.mode!='real' and args.frames!=1:
        parser.error('一轮BIST只生成一帧；--frames必须为1')
    base,size=address_from_hwh(args.hwh,args.ip)
    solver=Solver(args.library)  # ARM库不匹配会在访问硬件前报错。
    with single_owner(args.lock_file):
        from pynq import MMIO
        client=Client(MMIO(base,size),solver)
        with args.output.open('a',encoding='utf-8') as handle:
            saved=capture(client,durable_sink(handle),args.mode,args.frames,args.drain_existing)
    print('已保存帧数：',saved,'；未使能运动。')
    return 0


if __name__=='__main__':raise SystemExit(main())
