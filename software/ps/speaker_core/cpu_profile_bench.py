"""Opt-in Linux CPU diagnosis using frozen opt1 binaries; no hardware access.

Process CPU sums all threads (including runtime spinning). schedstat runqueue
wait is a separate sum, NOT wall minus CPU and NOT time blocked on a worker.
"""
import argparse
import array
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time

from pipeline_bench import Backend, unit
from stream_bench import reset


def proc_stat(text):
    fields = text[text.rindex(')')+2:].split()
    return {'ticks': int(fields[11])+int(fields[12]),
            'start': int(fields[19]), 'nice': int(fields[16])}


def snapshot(pid, proc=Path('/proc')):
    base = proc/str(pid)
    state = proc_stat((base/'stat').read_text())
    state['threads'] = {}
    for task in (base/'task').iterdir():
        try:
            stat = proc_stat((task/'stat').read_text())
            try:
                values = [int(x) for x in (task/'schedstat').read_text().split()]
                sched = values[:3] if len(values) >= 3 else None
            except (OSError, ValueError):
                sched = None
            state['threads'][task.name] = dict(stat, sched=sched,
                affinity=sorted(os.sched_getaffinity(int(task.name))))
        except FileNotFoundError:
            continue
    return state


def difference(before, after, wall, hz):
    if before['start'] != after['start'] or after['ticks'] < before['ticks']:
        raise RuntimeError('PROCESS_COUNTER_CHANGED')
    stable = set(before['threads']) == set(after['threads'])
    rows = []
    for tid in sorted(set(before['threads']) & set(after['threads'])):
        a, b = before['threads'][tid], after['threads'][tid]
        if a['start'] != b['start']:
            stable = False
            continue
        row = dict(tid=tid, cpu_seconds=(b['ticks']-a['ticks'])/hz,
                   nice=b['nice'], affinity=b['affinity'], runqueue_wait_seconds=None,
                   scheduled_seconds=None, timeslices=None)
        if a['sched'] is not None and b['sched'] is not None:
            delta = [y-x for x,y in zip(a['sched'], b['sched'])]
            if min(delta) < 0:
                raise RuntimeError('SCHEDSTAT_COUNTER_REGRESSED')
            row.update(scheduled_seconds=delta[0]/1e9,
                       runqueue_wait_seconds=delta[1]/1e9, timeslices=delta[2])
        rows.append(row)
    cpu = (after['ticks']-before['ticks'])/hz
    complete = stable and bool(rows) and all(r['runqueue_wait_seconds'] is not None for r in rows)
    return dict(wall_seconds=wall, process_cpu_seconds=cpu,
                average_busy_cores=cpu/wall, clock_tick_seconds=1/hz,
                stable_threads=stable, threads=rows,
                thread_runqueue_wait_sum_seconds=sum(r['runqueue_wait_seconds'] for r in rows) if complete else None,
                schedstat_readable=complete,
                interpretation='CPU includes runtime spin; thread waits may overlap; zero waits may mean disabled kernel accounting; never subtract CPU sum from wall')


def check_package(root):
    manifest = json.loads((root/'profile-assets.json').read_text())
    for name, digest in manifest['sha256'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('INVALID_ASSET_PATH')
        if hashlib.sha256((root/path).read_bytes()).hexdigest() != digest:
            raise ValueError('PROFILE_ASSET_HASH: '+name)
    return manifest


class PacedFront:
    """One block in flight, never queue a file's worth of stale work."""
    def __init__(self, backend, raw, max_lag=.5):
        if not raw or len(raw) % (1536*16):
            raise ValueError('FRONTEND_INPUT_LENGTH')
        self.backend, self.raw, self.max_lag = backend, raw, max_lag
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.error = None
        self.blocks = self.cycles = 0
        self.max_lag_seconds = 0.
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        try:
            reset(self.backend)
            origin = time.monotonic()
            size = 1536*16
            while not self.stop.is_set():
                for pos in range(0, len(self.raw), size):
                    release = origin+(self.blocks+1)*.032
                    if self.stop.wait(max(0., release-time.monotonic())):
                        return
                    if time.monotonic()-release > self.max_lag:
                        raise RuntimeError('PROFILE_FRONTEND_OVERRUN_NO_CATCHUP')
                    self.backend.run_pcm32(self.raw[pos:pos+size])
                    self.blocks += 1
                    self.max_lag_seconds = max(self.max_lag_seconds,time.monotonic()-release)
                    if self.max_lag_seconds > self.max_lag:
                        raise RuntimeError('PROFILE_FRONTEND_OVERRUN_NO_CATCHUP')
                    if self.blocks >= 3:
                        self.ready.set()
                self.cycles += 1
                reset(self.backend)
        except BaseException as exc:
            self.error = repr(exc)
        finally:
            self.ready.set()

    def start(self):
        self.thread.start()
        if not self.ready.wait(10):
            raise RuntimeError('PROFILE_FRONTEND_START_TIMEOUT')
        self.check()

    def check(self):
        if self.error:
            raise RuntimeError(self.error)

    def close(self):
        self.stop.set()
        self.thread.join(5)
        if self.thread.is_alive():
            self.backend.close(force=True)
            self.thread.join(5)
            raise RuntimeError('PROFILE_FRONTEND_STOP_TIMEOUT')
        self.check()


def bench(root, output, executable=None, repeats=2):
    manifest = check_package(root)
    cfg = json.loads((root/'profile-cases.json').read_text())
    original = set(os.sched_getaffinity(0))
    cpus = sorted(original)[:2]
    if len(cpus) != 2:
        raise RuntimeError('PROFILE_REQUIRES_TWO_CPUS')
    taskset, nice = shutil.which('taskset'), shutil.which('nice')
    if not taskset or not nice:
        raise RuntimeError('PROFILE_REQUIRES_TASKSET_NICE')
    hz = os.sysconf('SC_CLK_TCK')
    data = (root/'profile/epoch26.pcm32').read_bytes()
    jobs = []
    for case in cfg['windows']:
        features = array.array('f')
        features.frombytes((root/case['features']).read_bytes())
        if len(features) != 98*80:
            raise ValueError('PROFILE_WINDOW_SHAPE')
        jobs.append((case,features))
    front = embed = producer = None
    result = dict(status='RUNNING',scope='OFFLINE_PACED_FRONTEND_NOT_DMA_CAPTURE',
                  hardware_access=False,motion_commands=0,recognition_qualified=False,
                  source=manifest['source'],policy=dict(driver_cpu=cpus[1],frontend_cpu=cpus[1],
                  embedding_cpus=cpus,embedding_threads=2,embedding_nice_increment=10),
                  repeats=repeats,runs=[],frontend_runs=[],
                  boundary='J IPC+CMN+embedding only; CPU counters bracket call; vector normalization and scoring outside stopwatch',
                  order=['isolated_before','paced_frontend','isolated_after'])
    try:
        os.sched_setaffinity(0,{cpus[1]})
        front = Backend(root,role='front',executable=executable,prefix=[taskset,'-c',str(cpus[1])])
        embed = Backend(root,role='embed',executable=executable,
                        prefix=[taskset,'-c',','.join(map(str,cpus)),nice,'-n','10'])
        if min(front.loads.get('live_opt_revision',0),embed.loads.get('live_opt_revision',0)) != 1:
            raise ValueError('OPT1_BACKEND_REQUIRED')
        result['loads'] = {'front':front.loads,'embed':embed.loads}
        result['kernel'] = os.uname().release
        try:
            result['kernel_schedstats'] = Path('/proc/sys/kernel/sched_schedstats').read_text().strip()
        except OSError:
            result['kernel_schedstats'] = 'UNKNOWN'
        for mode in result['order']:
            if mode == 'paced_frontend':
                producer = PacedFront(front,data)
                producer.start()
            else:
                # Do not leave an idle spinning ORT frontend in the isolated run.
                time.sleep(.3)
            for repeat in range(repeats):
                for case,features in jobs:
                    if producer:
                        producer.check()
                    before = snapshot(embed.p.pid)
                    front_before = snapshot(front.p.pid)
                    start = time.monotonic()
                    vector = embed.run('J',features)
                    wall = time.monotonic()-start
                    after = snapshot(embed.p.pid)
                    front_after = snapshot(front.p.pid)
                    score = sum(a*b for a,b in zip(unit(vector),cfg['template']))
                    if abs(score-case['reference_score']) > .002:
                        raise RuntimeError('PROFILE_SCORE_MISMATCH')
                    row = dict(mode=mode,repeat=repeat+1,window=case['id'],score=score,
                               reference_pass=True,first_call=len(result['runs'])==0,
                               counters=difference(before,after,wall,hz),
                               frontend_cpu_seconds=(front_after['ticks']-front_before['ticks'])/hz)
                    result['runs'].append(row)
                    print('PROFILE_RESULT='+json.dumps(row),flush=True)
                    if producer:
                        producer.check()
            if producer:
                producer.close()
                result['frontend_runs'].append(dict(blocks=producer.blocks,cycles=producer.cycles,
                    max_lag_seconds=producer.max_lag_seconds,pending_capacity=0))
                producer = None
        result['status'] = 'PASS'
    except BaseException as exc:
        result.update(status='FAIL',error=repr(exc))
        raise
    finally:
        try:
            if producer:
                try:
                    producer.close()
                except BaseException as exc:
                    result.update(status='FAIL',cleanup_error=repr(exc))
            for backend in (embed,front):
                if backend:
                    backend.close(force=True)
        finally:
            os.sched_setaffinity(0,original)
            with output.open('x') as f:
                json.dump(result,f,indent=2,allow_nan=False)
    if result['status'] != 'PASS':
        raise RuntimeError('PROFILE_CLEANUP_FAILED')
    print('CPU_PROFILE=PASS LIVE_CAPTURE=0 MOTION_COMMANDS=0',flush=True)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action',choices=['check','bench'])
    p.add_argument('--output')
    args = p.parse_args()
    root = Path(__file__).resolve().parent
    if sys.byteorder != 'little' or array.array('f').itemsize != 4:
        raise RuntimeError('PROFILE_REQUIRES_LE_FLOAT32')
    check_package(root)
    print('PROFILE_PACKAGE_OK=1 NO_HARDWARE_ACCESS=1',flush=True)
    if args.action == 'bench':
        if not args.output or Path(args.output).exists():
            raise ValueError('NEW_OUTPUT_REQUIRED')
        bench(root,Path(args.output))


if __name__ == '__main__':
    main()
