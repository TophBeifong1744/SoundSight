"""独立三维无动作入口：同一Linux/PYNQ，CPU1取帧/调用C，CPU0保存/显示。

python software/tetra3d/linux/run_smp_3d.py --help
不加载bit、不复位PS；实际几何、PL通道和符号由现场先核对。
"""
import argparse
import multiprocessing as mp
import os
from pathlib import Path
import sys

from runtime_3d import Client3D,SolverAdapter3D,durable_sink_3d
from solver_3d import Solver3D,read_json
import run_smp as shared
from run_capture import address_from_hwh,single_owner


def argument_parser():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hwh',type=Path,required=True)
    parser.add_argument('--ip',default='ps_link')
    parser.add_argument('--library',type=Path,default=Path(__file__).with_name('libss_solver_3d.so'))
    parser.add_argument('--geometry',type=Path,required=True,help='显式四麦坐标/来源JSON，标称值不等于实测')
    parser.add_argument('--output',type=Path,required=True,help='新JSONL文件，拒绝覆盖/混合旧会话')
    parser.add_argument('--mode',choices=['real'],help='显式启用真实无动作采集；旧BIST仍用二维入口')
    parser.add_argument('--frames',type=int,default=1)
    parser.add_argument('--quiet',action='store_true',help='保留完整日志，关闭逐帧终端显示以减少服务耗时')
    parser.add_argument('--measure-level',action='store_true',help='显式选择音量ABI 0x10001，仅记录音量；不筛选三维方向')
    parser.add_argument('--drain-existing',action='store_true')
    parser.add_argument('--clear-faults',type=lambda value:int(value,0),default=0)
    parser.add_argument('--lock-file',default='/tmp/soundsight-ps-owner.lock',help='与二维入口共用同一所有者锁')
    parser.add_argument('--host-cpu',type=int,default=0)
    parser.add_argument('--worker-cpu',type=int,default=1)
    return parser


def prepare_args(args,parser):
    if args.frames<1:parser.error('--frames must be positive')
    if not 0<=args.clear_faults<=0xfff:parser.error('--clear-faults must be 0..0xfff')
    if args.drain_existing:
        if args.mode is not None or args.clear_faults:parser.error('drain mode does not start or clear faults')
    elif args.mode!='real':parser.error('choose --mode real or --drain-existing')
    # 只供复用既有capture；CLI不提供任何动作/看门狗配置。
    args.mode='real';args.watchdog_ticks=None
    return read_json(args.geometry.read_text(encoding='utf-8'))


def worker_main(connection,cancel,options,base,size,geometry):
    try:
        with shared.pinned(options.worker_cpu),single_owner(options.lock_file):
            solver=SolverAdapter3D(Solver3D(options.library,geometry))
            from pynq import MMIO
            client=Client3D(MMIO(base,size),solver,cancel,options.measure_level)
            client.identify()
            info=dict(worker_pid=os.getpid(),worker_cpu=options.worker_cpu,
                      worker_affinity=sorted(os.sched_getaffinity(0)),profile='TETRA40_3D',
                      geometry=solver.geometry,motion='DISABLED',measure_level=options.measure_level)
            shared.worker_session(connection,cancel,client,options,None,info)
    except BaseException as exc:
        try:connection.send(('error',dict(error=type(exc).__name__+': '+str(exc))))
        except (EOFError,OSError):pass
    finally:connection.close()


def main(argv=None):
    parser=argument_parser();args=parser.parse_args(argv);geometry=prepare_args(args,parser)
    shared.validate_cpus(args.host_cpu,args.worker_cpu)
    base,size=address_from_hwh(args.hwh,args.ip)
    context=mp.get_context('spawn');parent,child=context.Pipe();cancel=context.Event()
    worker=context.Process(target=worker_main,args=(child,cancel,args,base,size,geometry),name='soundsight-3d-solver')
    with args.output.open('x',encoding='utf-8') as handle:
        worker.start();child.close()
        try:
            with shared.pinned(args.host_cpu):
                info=dict(host_pid=os.getpid(),host_cpu=args.host_cpu,
                          host_affinity=sorted(os.sched_getaffinity(0)),profile='TETRA40_3D',motion='DISABLED')
                sink=durable_sink_3d(handle,display=None) if args.quiet else durable_sink_3d(handle)
                result=shared.collect(parent,worker,cancel,sink,info)
        finally:
            original=sys.exc_info()[0];parent.close()
            try:shared.finish_worker(worker,cancel)
            except Exception as exc:
                if original is None:raise
                print(str(exc),file=sys.stderr)
    print('CAPTURE_3D_COMPLETE frames=%d motion=DISABLED'%result['saved'])
    return 0


if __name__=='__main__':raise SystemExit(main())
