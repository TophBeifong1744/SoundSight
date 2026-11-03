"""P1 product boot, durable stage records and shutdown. No work on import."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

REVISION = 'SCREEN_PRODUCT_P1'
SERVICE = 'soundsight-product.service'
CONFIGS = ('settings.local.json', 'speaker-follow.local.json',
           'speaker-target.local.json', 'servo3d.local.json', 'horizontal.local.json',
           'screen.local.json', 'screen-orientation.local.json')


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.product-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=True, indent=2, allow_nan=False)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        if os.name == 'posix':
            fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def fingerprints(root):
    root = Path(root)
    paths = [root/n for n in CONFIGS]
    paths += sorted((root/'speaker-profiles').glob('*/profile.json'))
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.is_file()}


def load_preferences(root):
    p = Path(root)/'screen.local.json'
    if not p.exists():
        return 'SOUND'
    if p.stat().st_size > 4096:
        raise ValueError('Screen preference file too large')
    value = json.loads(p.read_text('utf-8'))
    if not isinstance(value, dict) or value.get('mode') not in ('SOUND', 'SPEAKER'):
        raise ValueError('Invalid saved screen mode')
    return value['mode']


def save_mode(root, mode):
    if mode not in ('SOUND', 'SPEAKER'):
        raise ValueError('Invalid mode')
    atomic_json(Path(root)/'screen.local.json', dict(schema=1, mode=mode))


class Journal:
    def __init__(self, root, boot_id=None):
        self.root = Path(root)
        self.path = self.root/'logs/product/latest.json'
        boot_id = boot_id or Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        old = None
        journal_error = None
        if self.path.is_file():
            try:
                old = json.loads(self.path.read_text('utf-8'))
                if not isinstance(old, dict):
                    raise ValueError('Not a journal object')
            except (ValueError, OSError) as exc:
                journal_error = str(exc)
                # A damaged diagnostic record must not overwrite settings or
                # prevent a new boot; preserve the damaged bytes for inspection.
                self.path.replace(self.path.with_name('damaged-%d.json' % time.time_ns()))
        self.value = dict(revision=REVISION, boot_id=boot_id, events=[], stage='BOOT',
                          axes='off', automatic_motion=False,
                          boot_started_monotonic=time.monotonic())
        if journal_error:
            self.value['previous_journal_error'] = journal_error
        if old:
            atomic_json(self.path.parent/'previous.json', old)
            self.value['previous_boot_id'] = old.get('boot_id')
            self.value['previous_stage'] = old.get('stage')
            self.value['new_boot'] = old.get('boot_id') != boot_id
            if old.get('settings_at_shutdown') is not None:
                self.value['settings_preserved'] = old['settings_at_shutdown'] == fingerprints(self.root)
        self.stage('BOOT')

    def stage(self, stage, **details):
        self.value.update(stage=stage, **details)
        self.value['events'].append(dict(stage=stage, monotonic=time.monotonic()))
        self.value['events'] = self.value['events'][-32:]
        atomic_json(self.path, self.value)
        print('PRODUCT_STAGE='+stage, flush=True)


def update_journal(root, stage, **details):
    path = Path(root)/'logs/product/latest.json'
    value = json.loads(path.read_text('utf-8')) if path.is_file() else dict(revision=REVISION, events=[])
    value.update(stage=stage, **details)
    if stage in ('DISPLAY_LIT', 'READY'):
        now = time.monotonic()
        timings = value.setdefault('startup_timing', {})
        # Keep first startup measurements even after later READY/STOP transitions.
        timings.setdefault(stage.lower()+'_uptime_seconds', now)
        if 'boot_started_monotonic' in value:
            timings.setdefault(stage.lower()+'_since_service_seconds', now-value['boot_started_monotonic'])
    value.setdefault('events', []).append(dict(stage=stage, monotonic=time.monotonic()))
    value['events'] = value['events'][-32:]
    atomic_json(path, value)
    print('PRODUCT_STAGE='+stage, flush=True)


def run_stage(argv, root, cancelled, timeout=240):
    """Bound startup; interrupt and wait for cleanup, never kill a live owner."""
    proc = subprocess.Popen(argv, cwd=str(root), start_new_session=True,
                            env=dict(os.environ, PYTHONUNBUFFERED='1'))
    start, interrupted = time.monotonic(), False
    while proc.poll() is None:
        if not interrupted and (cancelled[0] or time.monotonic()-start > timeout):
            interrupted = True
            try:
                os.killpg(proc.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
            print('PRODUCT_STARTUP_INTERRUPTED: waiting for owner exit', flush=True)
        time.sleep(.1)
    if interrupted or proc.returncode:
        raise RuntimeError('Startup command failed/interrupted: '+str(proc.returncode))


def verify_product(root):
    root = Path(root)
    value = json.loads((root/'PRODUCT-INSTALL.json').read_text('utf-8'))
    if value.get('revision') != REVISION or not value.get('files'):
        raise ValueError('P1 installation receipt required')
    from pathlib import PurePosixPath
    for name, expected in value['files'].items():
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
            raise ValueError('Invalid P1 receipt path')
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != expected:
            raise ValueError('P1 installed file differs: '+name)


def boot(root):
    import fcntl
    root = Path(root).resolve()
    owner = open('/tmp/soundsight-screen-owner.lock', 'a')
    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    journal = Journal(root)
    try:
        verify_product(root)
    except Exception as exc:
        journal.stage('INSTALL_ERROR', error=str(exc))
        owner.close()
        return 1
    cancelled = [False]
    def stop(signum, frame):
        cancelled[0] = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    error = None
    try:
        from hardware import verify_install, open_overlay
        verify_install(root)  # Check receipt and previous-boot gate before prepare.
        journal.stage('PREPARING')
        run_stage(['sh', str(root/'soundsight-3d.sh'), 'prepare', '--quick'], root, cancelled)
        if cancelled[0]:
            raise RuntimeError('Startup cancelled')
        journal.stage('TOUCH_SETUP')
        # Already hold screen owner. Calling the existing CLI here would try to
        # reacquire that lock, so call its checked core in this same process.
        open_overlay(root)
        from screen_i2c_prepare import apply_overlay
        apply_overlay(root)
        journal.stage('PANEL_STARTING')
    except Exception as exc:
        error = str(exc)
        journal.stage('STARTUP_ERROR', error=error)
    if cancelled[0]:
        owner.close()
        return 1
    # Carry the exclusive screen ownership across exec: no boot/GUI race.
    os.set_inheritable(owner.fileno(), True)
    argv = [sys.executable, '-B', str(root/'software/screen/ui.py'),
            '--root', str(root), '--control', '--enable-motion', '--product',
            '--owner-fd', str(owner.fileno())]
    if error:
        argv += ['--startup-error', error[:400]]
    try:
        os.execv(sys.executable, argv)
    finally:
        owner.close()  # Only reached if exec itself failed.


def poweroff(root, runner=subprocess.run):
    # Caller has already confirmed runtime idle and released display DMA.
    update_journal(root, 'SHUTDOWN_REQUESTED', settings_at_shutdown=fingerprints(root))
    if hasattr(os, 'sync'):
        os.sync()
    result = runner(['systemctl', 'poweroff', '--no-block'], capture_output=True,
                    text=True, timeout=10)
    if result.returncode:
        update_journal(root, 'SHUTDOWN_FAILED', error=result.stderr[-400:])
        raise RuntimeError('Shutdown rejected: '+result.stderr[-160:])


def report(root):
    root = Path(root)
    path = root/'logs/product/latest.json'
    value = json.loads(path.read_text('utf-8')) if path.is_file() else {'stage': 'NOT_STARTED'}
    boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    result = dict(current_boot_id=boot_id, same_boot=value.get('boot_id') == boot_id,
                  record=value, current_settings=fingerprints(root), hardware_actions=0)
    for action in ('is-enabled', 'is-active'):
        r = subprocess.run(['systemctl', action, SERVICE], capture_output=True, text=True, timeout=10)
        result[action] = r.stdout.strip()
    print(json.dumps(result, indent=2))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['boot', 'check', 'export'])
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    a = p.parse_args()
    if a.action == 'boot':
        return boot(a.root)
    value = report(a.root)
    if a.action == 'export':
        import zipfile
        out = a.root/'logs/product-check.zip'
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('check.json', json.dumps(value, indent=2))
            for path in (a.root/'logs/product').glob('*.json'):
                z.write(path, path.name)
            r = subprocess.run(['journalctl', '-u', SERVICE, '-b', '--no-pager', '-n', '250'],
                               capture_output=True, text=True, timeout=10)
            z.writestr('service.log', r.stdout)
        print('OUTPUT='+str(out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
