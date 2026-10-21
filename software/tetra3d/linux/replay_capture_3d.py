"""离线回放裸frame或已有采集JSONL，输出三维结果；不导入PYNQ或操作MMIO。

python software/tetra3d/linux/replay_capture_3d.py --help
输出新JSONL及终端方向；数据来源/几何未由此工具变成实测。
"""
import argparse
from pathlib import Path
from runtime_3d import SolverAdapter3D,durable_sink_3d,replay
from solver_3d import Solver3D,read_json


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,default=Path(__file__).with_name('libss_solver_3d.so'))
    parser.add_argument('--geometry',type=Path,required=True)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    solver=SolverAdapter3D(Solver3D(args.library,read_json(args.geometry.read_text(encoding='utf-8'))))
    with args.input.open(encoding='utf-8') as source,args.output.open('x',encoding='utf-8') as sink:
        count=replay(source,durable_sink_3d(sink),solver)
    print('CAPTURE_REPLAY_3D_COMPLETE frames=%d motion=DISABLED'%count)
    return 0


if __name__=='__main__':raise SystemExit(main())
