"""Single subprocess owner; all runtime operations use existing argument-list CLI."""
from collections import deque
import json
import os
import math
import re
from pathlib import Path
import signal
import subprocess
import time


def read_json(path, default):
    if not path.exists():
        return default
    if path.stat().st_size > 65536:
        raise ValueError('Oversized local configuration: ' + path.name)
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('Expected configuration object: ' + path.name)
    return value


class Backend:
    def __init__(self, root, control=False, motion=False, demo=False, frames=0):
        self.root = Path(root).resolve()
        self.control, self.motion, self.demo, self.frames = control, motion, demo, frames
        self.proc, self.pgid, self.pending = None, None, b''
        self.state, self.note, self.operation = 'IDLE', 'Axes OFF. Tap START explicitly.', ''
        if not control:
            self.note = 'Screen/touch selftest. Runtime START and configuration are disabled.'
        self.lines = deque(maxlen=16)
        self.started = self.stopping = 0.
        self.generation = 0
        self.cache = {}
        self.telemetry, self.received_at = {}, None
        self.device_state = None
        self.status_rows = []
        self.last_runtime_code = None
        self.stop_verified = True
        self.session_failed = False
        self.reload()

    @property
    def busy(self):
        return self.proc is not None

    def reload(self):
        # 仅读小型本地配置，不读取或导出模型、嵌入向量、个人录音。
        root = self.root
        settings = read_json(root/'settings.local.json', {})
        gate = read_json(root/'speaker-follow.local.json', {})
        selected = read_json(root/'speaker-target.local.json', {})
        profiles = ['P01']
        for path in sorted((root/'speaker-profiles').glob('*/profile.json')):
            name = 'P02' if path.parent.name == 'P02-v1' else path.parent.name
            if len(profiles) < 128 and name not in profiles:
                profiles.append(name)
        self.cache = dict(level=settings.get('min_level', 7000),
                          window=settings.get('window_frames', 20),
                          minimum=settings.get('min_valid', 12),
                          threshold=gate.get('threshold'), ttl=gate.get('permit_seconds', 3.),
                          target=selected.get('target_id'), profiles=profiles,
                          calibration=read_json(root/'servo3d.local.json', {}))

    def _launch(self, arguments, operation):
        if self.busy or self.state != 'IDLE':
            raise RuntimeError('Wait for confirmed STOP/exit before another operation')
        if not self.control:
            raise RuntimeError('Screen selftest: runtime commands disabled; use --control')
        if self.demo:
            self.note = 'DEMO only: ' + ' '.join(arguments)
            self.generation += 1
            return
        if os.name != 'posix':
            raise RuntimeError('Runtime control requires Linux process groups')
        if not (self.root/'soundsight-3d.sh').is_file():
            raise FileNotFoundError('Install screen into the existing SoundSight runtime root')
        # shell=False; signal the runtime group. Detached inference is closed by the runtime.
        self.proc = subprocess.Popen(['sh', str(self.root/'soundsight-3d.sh')] + list(arguments),
                                     cwd=str(self.root), stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     start_new_session=True, bufsize=0)
        self.pgid = self.proc.pid
        os.set_blocking(self.proc.stdout.fileno(), False)
        self.state = 'STARTING' if operation in ('SOUND', 'SPEAKER') else 'RUNNING'
        self.operation = operation
        self.status_rows = []
        if operation in ('SOUND', 'SPEAKER'):
            self.clear_live()
            self.stop_verified = False
            self.last_runtime_code = None
        self.note = 'Starting ' + operation
        self.started, self.pending = time.monotonic(), b''
        self.generation += 1
        print('PANEL_COMMAND=' + json.dumps(dict(operation=operation, arguments=list(arguments))), flush=True)

    def start(self, mode, axes):
        if self.session_failed:
            raise RuntimeError('Previous session failed; inspect saved runtime log before restarting panel')
        if not self.stop_verified:
            raise RuntimeError('STOP not verified; use Read status and inspect diagnostics')
        if mode not in ('SOUND', 'SPEAKER') or axes not in ('off', 'horizontal', 'vertical', 'both'):
            raise ValueError('Invalid mode or axis selection')
        if axes != 'off' and not self.motion:
            raise RuntimeError('Motion requires --enable-motion and explicit axis selection')
        args = ['follow-sound' if mode == 'SOUND' else 'speaker', '--axes', axes,
                '--frames', str(self.frames)]
        if mode == 'SPEAKER':
            args += ['--seconds', '0']
        self._launch(args, mode)

    def command(self, name, *values):
        # 配置写入交给原 CLI 校验及原子保存；切换用户沿用清除门限规则。
        if name not in ('speaker-select', 'speaker-list', 'speaker-config', 'level', 'filter', 'status'):
            raise ValueError('Unsupported screen command')
        self._launch([name] + [str(v) for v in values], name)

    def stop(self):
        if not self.busy:
            return
        if self.operation == 'verify-stop':
            return
        if self.state != 'STOPPING':
            self.clear_live()
            self.state, self.stopping = 'STOPPING', time.monotonic()
            self.note = 'STOP requested; waiting for process group exit'
            self.generation += 1
            try:
                os.killpg(self.pgid, signal.SIGINT)
            except ProcessLookupError:
                pass

    def _group_alive(self):
        try:
            os.killpg(self.pgid, 0)
            return True
        except ProcessLookupError:
            return False

    def tick(self):
        if not self.proc:
            return
        # 每轮最多读取 32 KiB，长行截断，避免日志洪流饿死 STOP/触摸循环。
        for _ in range(8):
            try:
                chunk = os.read(self.proc.stdout.fileno(), 4096)
            except BlockingIOError:
                break
            if not chunk:
                break
            self.pending += chunk
            while b'\n' in self.pending:
                line, self.pending = self.pending.split(b'\n', 1)
                self.accept_line(line.decode('utf-8', errors='replace'))
            if len(self.pending) > 8192:
                self.pending = self.pending[-800:]
        code = self.proc.poll()
        if code is not None:
            if self._group_alive():
                self.stop()
            else:
                self.proc.stdout.close()
                self.proc, self.pgid = None, None
                if self.pending:
                    self.accept_line(self.pending.decode('utf-8', errors='replace'))
                    self.pending = b''
                operation = self.operation
                self.reload()
                if operation in ('SOUND', 'SPEAKER'):
                    self.clear_live()
                    self.last_runtime_code = code
                    self.session_failed = code != 0
                    self._verify_stop()
                elif operation == 'verify-stop':
                    valid = code == 0 and len(self.status_rows) == 1 and self.idle_state(self.status_rows[0])
                    self.stop_verified = valid
                    self.state = 'IDLE' if valid and not self.session_failed else 'ERROR'
                    self.note = ('STOP verified. Select axes before next START.' if self.state == 'IDLE' else
                                 'Session failed; inspect runtime log.' if valid else
                                 'STOP NOT VERIFIED. Inspect status; restart blocked.')
                    print('PANEL_STOP_CHECK=' + json.dumps(dict(verified=valid,
                          runtime_code=self.last_runtime_code, status_code=code,
                          device=self.device_state)), flush=True)
                else:
                    self.state = 'IDLE' if code == 0 else 'ERROR'
                    self.note = 'Command finished; return code %s' % code
                self.generation += 1
                return
        # 配置/status 超时同样只发 SIGINT，不强杀或自动重新启动动作。
        if self.operation not in ('SOUND', 'SPEAKER') and time.monotonic()-self.started > 15:
            if self.operation == 'verify-stop':
                if self.state != 'STOPPING':
                    self.state, self.stopping = 'STOPPING', time.monotonic()
                    try:
                        os.killpg(self.pgid, signal.SIGINT)
                    except ProcessLookupError:
                        pass
            else:
                self.stop()
        if self.state == 'STOPPING' and time.monotonic()-self.stopping > 5:
            message = 'STOP UNCONFIRMED. No restart. Inspect terminal/hardware.'
            if self.note != message:
                self.note = message
                self.generation += 1

    def clear_live(self):
        self.telemetry, self.received_at = {}, None

    @staticmethod
    def idle_state(value):
        keys = ('status', 'fault', 'drops', 'sys', 'actuator', 'dual_axis')
        if not isinstance(value, dict) or any(type(value.get(k)) is not int or
                not 0 <= value[k] <= 0xffffffff for k in keys):
            return False
        return not (value['status'] & (3 | 0x8000) or value['sys'] & 1 or
                    value['actuator'] & 1 or value['dual_axis'] & 0x19 or value['fault'] & ~0x40)

    def _verify_stop(self):
        self.state = 'IDLE'
        self._launch(['status'], 'verify-stop')
        self.state = 'VERIFYING'
        self.note = 'Checking device STOP; restart blocked until readback'

    def accept_line(self, line):
        # Parse bounded complete lines before clipping diagnostics. Never parse LAST_GROUP as current.
        self.lines.append(line[:800])
        self.generation += 1
        if line.startswith('DEVICE_STATE='):
            try:
                value = json.loads(line.split('=', 1)[1])
            except (ValueError, TypeError):
                value = None
            self.status_rows.append(value)
            self.status_rows = self.status_rows[:2]  # duplicate evidence is rejected
            self.device_state = value
        if line.startswith(('STOP:', 'THREE_D_STOPPED', 'SPEAKER_3D_STOPPED', 'SPEAKER_3D_READY')):
            print('PANEL_RUNTIME=' + line[:1500], flush=True)
        if not line.startswith(('FRAME=', 'NO_OUTPUT:')):
            return
        self.clear_live()
        if len(line) > 4096:
            return
        current = line.split(';', 1)[0]
        tokens = dict(re.findall(r'(?:^|\s)([A-Z_]+)=([^\s;]+)', current))
        def number(value):
            try:
                result = float(value)
                return result if math.isfinite(result) else None
            except (TypeError, ValueError):
                return None
        t = dict(frame=tokens.get('FRAME', '-'), level=tokens.get('LEVEL', '-'),
                 motion=tokens.get('MOTION', 'WAITING'), angle_reason='NO_CURRENT_DIRECTION',
                 azimuth=None, elevation=None, score=None, permit=None, remain=0., score_age=None)
        if 'NO_OUTPUT:' in current:
            reasons = current.split('NO_OUTPUT:', 1)[1].strip().split()
            t['angle_reason'] = reasons[0] if reasons else 'NO_CURRENT_DIRECTION'
        else:
            t['azimuth'] = number(tokens.get('AZIMUTH'))
            t['elevation'] = number(tokens.get('ELEVATION'))
            t['angle_reason'] = 'CURRENT' if t['azimuth'] is not None or t['elevation'] is not None else 'UNOBSERVABLE'
        if self.operation == 'SPEAKER':
            fields = dict(re.findall(r'(?:^|\s)([A-Z_]+)=([^\s;]+)', line))
            if fields.get('POLICY') == 'score_ttl_v2':
                t['score'] = number(fields.get('SPEAKER_SCORE'))
                t['score_age'] = number(fields.get('SCORE_AGE', '').rstrip('s'))
                t['remain'] = max(0., number(fields.get('REMAIN', '').rstrip('s')) or 0.)
                if fields.get('PERMIT') in ('0', '1'):
                    t['permit'] = fields['PERMIT'] == '1' and t['remain'] > 0
                t['permit_reason'] = fields.get('PERMIT_REASON', 'UNKNOWN')
        self.telemetry, self.received_at = t, time.monotonic()
        if self.state == 'STARTING':
            self.state = 'RUNNING'
            self.note = 'Receiving runtime reports; STOP ends this session'

    def live(self):
        t = dict(self.telemetry)
        age = None if self.received_at is None else max(0., time.monotonic() - self.received_at)
        if age is None or age > 2. or self.state not in ('STARTING', 'RUNNING'):
            return dict(stale=True, report_age=age)
        t.update(stale=False, report_age=age)
        t['remain'] = max(0., t.get('remain', 0.) - age)
        if t.get('permit') and t['remain'] <= 0:
            t['permit'] = False
        if t.get('score_age') is not None:
            t['score_age'] += age
        return t

    def acknowledge(self):
        if not self.busy:
            self.reload()
            self.clear_live()
            if self.session_failed or not self.stop_verified:
                self._verify_stop()
            else:
                self.state = 'IDLE'
                self.note = 'Idle. Next START is explicit; axes must be reselected.'
            self.generation += 1
