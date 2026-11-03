"""SoundSight 800x480 touch UI. Default screen selftest, no motion commands."""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import time

from backend import Backend


def screen_rotation(root, override=None):
    """Keep panel mounting separate from acoustic/servo coordinate settings."""
    value = 180
    path = Path(root)/'screen-orientation.local.json'
    if override is None and path.exists():
        if path.stat().st_size > 4096:
            raise ValueError('Screen orientation file too large')
        config = json.loads(path.read_text('utf-8'))
        if not isinstance(config, dict) or 'rotation' not in config:
            raise ValueError('Expected screen orientation rotation=0 or 180')
        value = config['rotation']
    elif override is not None:
        value = override
    if type(value) is not int or value not in (0, 180):
        raise ValueError('Screen rotation must be 0 or 180')
    return value


def rotate_frame(frame, rotation):
    # Pillow transpose is an exact pixel permutation: no resize/interpolation.
    if rotation == 0:
        return frame
    if rotation != 180:
        raise ValueError('Screen rotation must be 0 or 180')
    from PIL import Image
    return frame.transpose(getattr(Image, 'Transpose', Image).ROTATE_180)


def rotate_touch(points, rotation):
    # Touch.poll has already applied physical calibration. Invert the displayed
    # pixel mapping here; None (no update) and [] (release) must stay distinct.
    if rotation not in (0, 180):
        raise ValueError('Screen rotation must be 0 or 180')
    if points is None:
        return None
    if any(not (0 <= x < 800 and 0 <= y < 480) for x, y in points):
        raise ValueError('Touch coordinate outside 800x480 screen')
    return [(799-x, 479-y) for x, y in points] if rotation == 180 else points


class UI:
    def __init__(self, backend, product=False):
        self.backend = backend
        self.page, self.mode, self.axes = 'HOME', 'SOUND', 'off'
        self.message, self.touch_text = '', 'Touch the four corners; coordinates appear here'
        self.buttons, self.dirty, self.down = [], True, False
        self.user_index, self.setting_index = 0, 0
        self.draft = dict(backend.cache)
        self.last_generation = -1
        self.touch_count = 0
        self.exit_requested = False
        self.last_live_refresh = 0.
        self.product = product
        self.modal = None
        self.enroll_seconds = 5
        self.enroll_name = None
        self.delete_target = None
        self.delete_token = None
        self.shutdown_pending = False
        self.shutdown_checked = False
        self.touch_failed = False
        self.startup_block = ''
        self.last_state = backend.state
        if product:
            try:
                from product import load_preferences
                self.mode = load_preferences(backend.root)
            except (ValueError, OSError) as exc:
                backend.fault('Saved screen settings: '+str(exc))

    @property
    def poweroff_ready(self):
        b = self.backend
        return (self.shutdown_pending and self.shutdown_checked and not b.busy and
                b.stop_verified and b.operation == 'verify-stop' and
                b.idle_state(b.device_state))

    def action(self, action):
        b = self.backend
        self.message = ''
        try:
            if action == 'STOP':
                self.modal = None
                self.shutdown_pending = False
                b.stop()
                self.axes = 'off'
            elif action == 'POWER':
                if not self.product or not b.control:
                    raise RuntimeError('Power control requires product mode')
                self.modal = 'POWER'
            elif action == 'CANCEL':
                self.modal = None
            elif self.modal == 'DELETE' and action == 'DELETE_CONFIRM':
                b.delete_user(self.delete_target, self.delete_token)
                self.modal = None
                self.axes = 'off'
                self.message = 'Deleting '+self.delete_target+'; wait for completion'
            elif self.modal == 'RECOVER' and action == 'RECOVER_CONFIRM':
                b.recover_capture()
                self.modal = None
                self.axes = 'off'
            elif self.modal == 'POWER' and action == 'POWER_CONFIRM':
                self.modal = None
                self.axes = 'off'
                if b.demo:
                    self.message = 'DEMO: no power action'
                else:
                    self.shutdown_pending, self.shutdown_checked = True, False
                    b.stop()
                    self.message = 'Stopping before shutdown. Keep power connected.'
            elif self.modal == 'ENROLL' and action in ('RECORD', 'SHORTER', 'LONGER'):
                if action == 'RECORD':
                    b.enroll(self.enroll_name, self.enroll_seconds)
                    self.modal = None
                    self.axes, self.page = 'off', 'HOME'
                else:
                    self.enroll_seconds = max(2, min(10, self.enroll_seconds + (1 if action == 'LONGER' else -1)))
            elif self.modal or self.shutdown_pending:
                self.message = 'Confirm or cancel the dialog first'
            elif action == 'EXIT':
                b.stop()
                self.exit_requested = True
                self.axes = 'off'
            elif action.startswith('PAGE:'):
                self.page = action[5:]
            elif b.busy:
                self.message = 'Wait for confirmed STOP before changing mode/settings'
            elif action == 'START':
                b.start(self.mode, self.axes)
            elif action == 'MODE':
                b.clear_live()
                self.mode = 'SPEAKER' if self.mode == 'SOUND' else 'SOUND'
                self.axes = 'off'
                if self.product and not b.demo:
                    from product import save_mode
                    save_mode(b.root, self.mode)
            elif action == 'AXES':
                choices = ['off', 'horizontal', 'vertical', 'both'] if b.motion and b.control else ['off']
                self.axes = choices[(choices.index(self.axes)+1) % len(choices)]
            elif action == 'ACK':
                if self.startup_block:
                    raise RuntimeError('Startup failed: '+self.startup_block)
                if self.touch_failed:
                    raise RuntimeError('Touch unavailable; wait for touch recovery first')
                if (b.session_failed or not b.stop_verified) and not b.external_fault:
                    self.modal = 'RECOVER'
                else:
                    b.acknowledge()
                self.axes = 'off'
                self.draft = dict(b.cache)
            elif action == 'STATUS':
                b.command('status')
            elif action == 'USER_NEXT':
                self.user_index = (self.user_index+1) % len(b.cache['profiles'])
            elif action == 'USER_SELECT':
                b.command('speaker-select', b.cache['profiles'][self.user_index])
                self.axes = 'off'
                self.message = 'Selection clears threshold. Run score-only before setting a new gate.'
            elif action == 'USER_VERIFY':
                b.command('speaker-list')
            elif action == 'ENROLL':
                if not b.control:
                    raise RuntimeError('Enrollment requires control mode')
                self.enroll_name = b.next_user()
                self.modal = 'ENROLL'
                self.axes = 'off'
            elif action == 'USER_DELETE':
                target = b.cache['profiles'][self.user_index]
                info = b.deletion_preview(target)
                self.delete_target, self.delete_token = target, info['token']
                self.modal = 'DELETE'
                self.axes = 'off'
            elif action == 'FIELD':
                self.setting_index = (self.setting_index+1) % 5
            elif action in ('PLUS', 'MINUS'):
                key = ['level', 'window', 'minimum', 'threshold', 'ttl'][self.setting_index]
                step, low, high = dict(level=(500, 1, 16777215), window=(1, 1, 100),
                                       minimum=(1, 1, 100), threshold=(.05, -1, 1), ttl=(.5, .1, 30))[key]
                value = self.draft[key]
                if value is None:
                    value = 0.
                self.draft[key] = max(low, min(high, round(value + step*(1 if action == 'PLUS' else -1), 4)))
            elif action == 'APPLY':
                key = ['level', 'window', 'minimum', 'threshold', 'ttl'][self.setting_index]
                if key == 'level':
                    b.command('level', self.draft['level'])
                elif key in ('window', 'minimum'):
                    b.command('filter', self.draft['window'], self.draft['minimum'])
                elif key == 'ttl':
                    b.command('speaker-config', '--ttl', self.draft['ttl'])
                elif self.draft['threshold'] is not None:
                    b.command('speaker-config', self.draft['threshold'])
                else:
                    raise ValueError('Use +/- to choose an explicit trial threshold')
            elif action == 'DISABLE':
                b.command('speaker-config', '--disable')
                self.axes = 'off'
        except Exception as exc:
            self.message = str(exc)
        self.dirty = True

    def touch(self, points):
        if points is None:
            return
        if not points:
            self.down = False
            return
        x, y = points[0]
        self.touch_count += 1
        self.touch_text = 'Touch x=%d y=%d contacts=%d reports=%d' % (x, y, len(points), self.touch_count)
        # 一次按压只触发一次；不自动重复 START/轴选择/配置保存。
        if not self.down and len(points) == 1:
            for rect, action in reversed(self.buttons):
                if rect[0] <= x < rect[2] and rect[1] <= y < rect[3]:
                    self.action(action)
                    break
        self.down = True
        self.dirty = True

    def tick(self):
        self.backend.tick()
        if self.shutdown_pending and not self.backend.busy and not self.shutdown_checked:
            self.backend._verify_stop()
            self.shutdown_checked = True
        if self.product and not self.backend.demo and self.last_state != self.backend.state:
            from product import update_journal
            stage = 'READY' if self.backend.state == 'IDLE' else self.backend.state
            update_journal(self.backend.root, stage, runtime_operation=self.backend.operation,
                           stop_verified=self.backend.stop_verified,
                           error=self.backend.note if self.backend.state == 'ERROR' else None)
            self.last_state = self.backend.state
        now = time.monotonic()
        if self.backend.busy and now - self.last_live_refresh >= .5:
            self.last_live_refresh = now
            self.dirty = True
        if self.last_generation != self.backend.generation:
            if self.backend.state in ('IDLE', 'ERROR'):
                self.axes = 'off'
                self.draft = dict(self.backend.cache)
                if self.backend.last_enrolled in self.backend.cache['profiles']:
                    self.user_index = self.backend.cache['profiles'].index(self.backend.last_enrolled)
            self.last_generation = self.backend.generation
            self.dirty = True

    def render(self):
        from PIL import Image, ImageDraw, ImageFont
        im = Image.new('RGB', (800, 480), '#0b1423')
        draw = ImageDraw.Draw(im)
        try:
            normal = ImageFont.truetype('DejaVuSans.ttf', 17)
            large = ImageFont.truetype('DejaVuSans.ttf', 28)
        except OSError:
            try:
                normal, large = ImageFont.load_default(size=17), ImageFont.load_default(size=28)
            except TypeError:
                normal = large = None

        def text(x, y, value, color='#e6edf7', big=False, limit=88):
            value = str(value).encode('ascii', errors='replace').decode()[:limit]
            font = large if big else normal
            if font:
                # PYNQ ships older Pillow without textbbox; keep clipping active
                # with its textsize API instead of requiring a board upgrade.
                def right_edge(value):
                    bbox = getattr(draw, 'textbbox', None)
                    if callable(bbox):
                        return bbox((0, 0), value, font=font)[2]
                    return draw.textsize(value, font=font)[0]
                while value and right_edge(value) > 780-x:
                    value = value[:-1]
                draw.text((x, y), value, fill=color, font=font)
            else:
                # 无额外字体时放大 Pillow 自带位图字体，不分发 Windows 字体。
                small = Image.new('RGBA', (max(1, len(value))*7, 13), (0, 0, 0, 0))
                ImageDraw.Draw(small).text((0, 0), value, fill=color, font=ImageFont.load_default())
                enlarged = small.resize((small.width*2, 26), Image.NEAREST)
                im.paste(enlarged, (x, y), enlarged)

        def button(rect, label, action, color='#21354f'):
            draw.rectangle(rect, fill=color)
            text(rect[0]+12, rect[1]+12, label, limit=32)
            self.buttons.append((rect, action))

        b, c = self.backend, self.backend.cache
        self.buttons = []
        text(20, 12, 'SOUNDSIGHT', '#53d8cc', big=True)
        text(260, 20, 'DEMO / NO HARDWARE' if b.demo else ('CONTROL / TAP START' if b.control else 'SCREEN + TOUCH SELFTEST'))
        text(20, 56, '%s  |  %s  |  SELECTED AXES %s' % (self.mode, b.state, self.axes.upper()), '#f5cd75')
        for n, page in enumerate(('HOME', 'USERS', 'SETTINGS', 'DIAGNOSTICS')):
            button((20+n*195, 91, 200+n*195, 139), page, 'PAGE:'+page,
                   '#236b75' if self.page == page else '#21354f')
        if self.page == 'HOME':
            text(24, 157, 'Voice enrollment' if b.operation == 'ENROLL' and b.busy else
                 'Acoustic follow' if self.mode == 'SOUND' else 'Speaker gate / score_ttl_v2', big=True)
            live = b.live()
            if live.get('stale'):
                text(24, 199, 'Direction: waiting / no recent runtime report', '#a7bdd5')
                text(24, 226, 'Motion: not confirmed by a recent report', '#a7bdd5')
            else:
                az, el = live.get('azimuth'), live.get('elevation')
                direction = 'Az: %s   El: %s deg' % (
                    '--' if az is None else '%.1f' % az, '--' if el is None else '%.1f' % el)
                if az is None and el is None:
                    direction = 'No angle: %s  W=%s V=%s/%s' % (
                        live.get('angle_reason', 'WAITING'), live.get('window', '-'),
                        live.get('valid', '-'), live.get('minimum', '-'))
                else:
                    direction += '   RX age: %.1fs' % live['report_age']
                text(24, 199, direction, '#53d8cc')
                text(24, 226, 'Level: %s   Motion: %s' % (live.get('level', '-'), live.get('motion', '-')), limit=72)
            if self.mode == 'SPEAKER':
                permit = live.get('permit')
                score = live.get('score')
                text(24, 253, 'Last score: %s  Permit: %s  TTL left: %s' % (
                    '--' if score is None else '%.3f' % score,
                    'UNKNOWN' if permit is None else 'YES' if permit else 'NO',
                    '--' if live.get('stale') else '%.1fs' % live.get('remain', 0.)), '#f5cd75')
                text(24, 278, 'User: %s  Gate: %s  Score age: %s' % (c['target'] or '(none)', c['threshold'],
                    '--' if live.get('score_age') is None else '%.1fs' % live['score_age']))
            else:
                text(24, 253, 'Identity gate OFF / follows current sound', '#f5cd75')
                text(24, 278, 'Level gate: %s   filter: %s / %s' % (c['level'], c['minimum'], c['window']))
            button((24, 309, 244, 359), 'Change mode', 'MODE')
            button((260, 309, 755, 359), 'Select axes: '+self.axes, 'AXES')
            text(24, 364, b.note, '#a7bdd5', limit=78)
            if b.operation == 'ENROLL' and b.busy:
                draw.rectangle((20, 192, 780, 305), fill='#183447')
                text(24, 205, b.note, '#f5cd75', limit=68)
                text(24, 249, 'Recording / processing with axes OFF. STOP cancels.')
        elif self.page == 'USERS':
            self.user_index %= len(c['profiles'])
            text(24, 160, 'Current: '+str(c['target'] or '(none)'), big=True)
            text(24, 205, 'Candidate: '+c['profiles'][self.user_index])
            text(24, 236, 'Local names only. SELECT runs original profile validation.')
            text(24, 264, 'Selecting a user clears the old threshold.', '#f5cd75')
            button((20, 288, 200, 332), 'Next user', 'USER_NEXT')
            button((215, 288, 395, 332), 'SELECT', 'USER_SELECT')
            button((410, 288, 590, 332), 'Validate', 'USER_VERIFY')
            button((605, 288, 785, 332), 'NEW voice', 'ENROLL')
            button((20, 340, 395, 384), 'DELETE candidate', 'USER_DELETE', '#6a3945')
        elif self.page == 'SETTINGS':
            key = ['level', 'window', 'minimum', 'threshold', 'ttl'][self.setting_index]
            text(24, 157, 'Edit: %s = %s' % (key, self.draft[key]), big=True)
            text(24, 201, 'Saved: %s | applies only to next session' % c[key])
            text(24, 230, 'Trial threshold is not qualified recognition.', '#f5cd75')
            button((24, 266, 226, 318), 'Next field', 'FIELD')
            button((242, 266, 325, 318), '-', 'MINUS')
            button((341, 266, 424, 318), '+', 'PLUS')
            button((440, 266, 755, 318), 'APPLY current field', 'APPLY')
            button((24, 330, 330, 382), 'DISABLE speaker gate', 'DISABLE')
        else:
            text(24, 151, self.touch_text, '#53d8cc')
            text(24, 181, 'Actual CLI output (bounded, unparsed):', '#a7bdd5')
            for n, line in enumerate(list(b.lines)[-4:]):
                text(24, 208+n*25, line, limit=78)
            button((24, 325, 250, 377), 'Read status', 'STATUS')
            button((266, 325, 575, 377), 'Recover capture' if (b.session_failed or not b.stop_verified) and not b.external_fault
                   else 'Recheck / reload', 'ACK')
            button((591, 325, 778, 377), 'SHUT DOWN' if self.product else 'EXIT panel',
                   'POWER' if self.product else 'EXIT', '#6a3945')
        if self.modal:
            draw.rectangle((10, 145, 790, 388), fill='#183447', outline='#53d8cc')
            self.buttons = []
            if self.modal == 'DELETE':
                text(30, 162, 'Delete this user?', big=True)
                text(30, 205, 'USER: '+str(self.delete_target))
                text(30, 236, 'Voice profile only. Cannot undo. Logs are kept.')
                text(30, 267, 'If active: target and threshold will be cleared.')
                button((30, 320, 350, 380), 'CANCEL', 'CANCEL')
                button((400, 320, 760, 380), 'CONFIRM DELETE', 'DELETE_CONFIRM', '#9a3545')
            elif self.modal == 'RECOVER':
                text(30, 165, 'Recover stopped audio capture?', big=True)
                text(30, 210, 'Save diagnostics and old direction frames first.')
                text(30, 240, 'Discard queued audio; keep axes OFF. No auto START.')
                button((30, 315, 350, 374), 'CANCEL', 'CANCEL')
                button((400, 315, 760, 374), 'CONFIRM recovery', 'RECOVER_CONFIRM')
            elif self.modal == 'POWER':
                text(30, 165, 'Shut down SoundSight?', big=True)
                text(30, 220, 'Runtime and display DMA must stop before poweroff.')
                text(30, 250, 'Keep power connected until Linux has shut down.')
                button((30, 315, 350, 374), 'CANCEL', 'CANCEL')
                button((400, 315, 760, 374), 'CONFIRM shutdown', 'POWER_CONFIRM', '#9a3545')
            else:
                text(30, 162, 'New voice: '+str(self.enroll_name), big=True)
                text(30, 205, 'Only this person speaks. Wait for SPEAK NOW.')
                text(30, 237, 'Duration: %d seconds; existing users are preserved.' % self.enroll_seconds)
                button((30, 276, 160, 323), '- 1 sec', 'SHORTER')
                button((180, 276, 310, 323), '+ 1 sec', 'LONGER')
                button((30, 334, 350, 383), 'CANCEL', 'CANCEL')
                button((400, 334, 760, 383), 'RECORD new voice', 'RECORD', '#235748')
        # STOP 固定位置覆盖所有页面，配置状态不影响其可达性。
        draw.rectangle((0, 390, 800, 480), fill='#101f32')
        text(20, 394, self.message or b.note, '#f5cd75', limit=76)
        button((20, 426, 255, 478), 'START selected mode' if b.control else 'SELFTEST / axes OFF',
               'START', '#235748')
        button((275, 426, 780, 478), 'STOP / AXES OFF', 'STOP', '#9a3545')
        self.dirty = False
        return im


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument('--demo', action='store_true', help='Offline PNG; no hardware or subprocesses')
    p.add_argument('--demo-window', action='store_true', help='Offline interactive Tk window')
    p.add_argument('--screenshot', type=Path, default=Path('screen-preview.png'))
    p.add_argument('--page', choices=['HOME', 'USERS', 'SETTINGS', 'DIAGNOSTICS'], default='HOME')
    p.add_argument('--mode', choices=['SOUND', 'SPEAKER'], default='SOUND')
    p.add_argument('--control', action='store_true', help='Enable existing CLI via explicit touch START')
    p.add_argument('--enable-motion', action='store_true', help='Allow explicit axis selection; boot still OFF')
    p.add_argument('--frames', type=int, default=0, help='0 until STOP; otherwise session frame bound 1..100000')
    p.add_argument('--seconds', type=float, default=0., help='Screen lifetime; 0 until EXIT panel or Ctrl+C')
    p.add_argument('--swap-xy', action='store_true')
    p.add_argument('--invert-x', action='store_true')
    p.add_argument('--invert-y', action='store_true')
    p.add_argument('--rotation', type=int, choices=(0, 180), default=None,
                   help='Display and touch together; local setting or default 180')
    p.add_argument('--product', action='store_true', help='Saved mode, enrollment and confirmed shutdown')
    p.add_argument('--owner-fd', type=int, help=argparse.SUPPRESS)
    p.add_argument('--startup-error', default='', help=argparse.SUPPRESS)
    return p


def demo_window(ui, rotation=0):
    import tkinter as tk
    from PIL import ImageTk
    window = tk.Tk()
    window.title('SoundSight S3 - OFFLINE DEMO')
    window.resizable(False, False)
    label = tk.Label(window)
    label.pack()
    label.bind('<ButtonPress-1>', lambda event: ui.touch(rotate_touch([(event.x, event.y)], rotation)))
    label.bind('<ButtonRelease-1>', lambda event: ui.touch([]))

    def update():
        ui.tick()
        if ui.dirty:
            photo = ImageTk.PhotoImage(rotate_frame(ui.render(), rotation))
            label.configure(image=photo)
            label.image = photo
        if ui.exit_requested:
            window.destroy()
            return
        window.after(200, update)
    update()
    window.mainloop()


def main(argv=None):
    args = parser().parse_args(argv)
    import math
    if not 0 <= args.frames <= 100000 or not math.isfinite(args.seconds) or args.seconds < 0:
        raise ValueError('Use frames 0..100000 and finite seconds >= 0')
    if args.enable_motion and not args.control:
        raise ValueError('--enable-motion requires --control')
    rotation = screen_rotation(args.root, args.rotation)
    print('SCREEN_ROTATION=%d TOUCH_ROTATION=%d' % (rotation, rotation), flush=True)
    try:
        import PIL
        import numpy
    except ImportError as exc:
        print('DEPENDENCY_MISSING: %s. No downloads or hardware access performed.' % exc, file=sys.stderr)
        return 2
    print('%s transport=PS_I2C0_EMIO_LINUX Python=%s Pillow=%s numpy=%s' %
          ('SCREEN_PRODUCT_P1' if args.product else 'SCREEN_S3',
           sys.version.split()[0], PIL.__version__, numpy.__version__))
    offline = args.demo or args.demo_window
    backend = Backend(args.root, args.control, args.enable_motion, demo=offline, frames=args.frames)
    ui = UI(backend, product=args.product)
    ui.page = args.page
    if not args.product:
        ui.mode = args.mode
    if args.startup_error:
        ui.startup_block = args.startup_error
        backend.fault('Startup failed: '+args.startup_error)
    if offline:
        rotate_frame(ui.render(), rotation).save(args.screenshot)
        print('OFFLINE_SCREENSHOT='+str(args.screenshot.resolve())+' HARDWARE_ACTIONS=0')
        if args.demo_window:
            demo_window(ui, rotation)
        return 0
    if os.name != 'posix':
        raise RuntimeError('Hardware screen requires Linux/PYNQ; use --demo on PC')
    if args.product:
        from product import verify_product
        verify_product(args.root)
    import fcntl
    from hardware import open_overlay, ScreenGPIO, Touch, Display, wait_until
    from linux_i2c import LinuxI2C
    # 单独的屏幕所有者锁允许原运行时拥有采集锁；禁止第二个 UI 使用 DMA。
    owner_path = '/tmp/soundsight-screen-owner.lock'
    if args.owner_fd is not None:
        if not args.product:
            raise ValueError('Inherited owner requires product mode')
        owner = os.fdopen(args.owner_fd, 'a')
        held, actual = os.fstat(owner.fileno()), os.stat(owner_path)
        if (held.st_dev, held.st_ino) != (actual.st_dev, actual.st_ino):
            raise ValueError('Wrong inherited screen owner')
        os.set_inheritable(owner.fileno(), False)
    else:
        owner = open(owner_path, 'a')
    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    display, gpio, bus = None, None, None
    quit_requested = [False]

    def request_exit(signum, frame):
        quit_requested[0] = True
        backend.stop()
    signal.signal(signal.SIGINT, request_exit)
    signal.signal(signal.SIGTERM, request_exit)
    result = 0
    power_accepted = False
    try:
        overlay, mmio, allocate, np = open_overlay(args.root)
        gpio = ScreenGPIO(mmio(0x41200000, 0x1000), touch_owned=False)
        display = Display(mmio(0x43000000, 0x1000), gpio, allocate, np)
        display.start(allocate)
        # 视频输出锁定依赖有效 AXI 视频流，必须先启动 VDMA 再等待锁定。
        wait_until(gpio.locked, 1., 'Screen video output timing lock not asserted')
        ui.message = 'Starting touch controller. Axes are OFF.'
        display.present(rotate_frame(ui.render(), rotation))
        gpio.backlight(True)
        if args.product:
            from product import update_journal
            update_journal(args.root, 'DISPLAY_LIT')
        touch = None
        touch_attempts, next_touch_retry = 0, 0.
        def touch_error(exc):
            ui.touch_failed = True
            ui.axes, ui.down = 'off', True
            ui.message = 'Touch fault; STOP requested. Recovery needs Recheck.'
            backend.fault('Touch: '+str(exc))
            ui.dirty = True
            print('PRODUCT_TOUCH_FAULT='+str(exc), flush=True)
            if args.product:
                from product import update_journal
                update_journal(args.root, 'TOUCH_FAULT', error=str(exc)[:400])
        started, last_render, last_health = time.monotonic(), time.monotonic(), 0.
        while not quit_requested[0] and not ui.exit_requested:
            now = time.monotonic()
            if args.seconds and now-started >= args.seconds:
                break
            ui.tick()
            if touch is None and touch_attempts < 3 and now >= next_touch_retry and not backend.busy:
                touch_attempts += 1
                try:
                    # Kernel ownership precedes all touch reset/probe operations.
                    bus = LinuxI2C()
                    candidate = Touch(bus, gpio, args.swap_xy, args.invert_x, args.invert_y)
                    controller = candidate.probe()
                    touch = candidate
                    ui.touch_failed = False
                    ui.message = ('Touch recovered. Tap Recheck; axes remain OFF.' if touch_attempts > 1
                                  else args.startup_error)
                    print('TOUCH='+controller, flush=True)
                    print('SCREEN_READY=1 CURRENT_FRAME_ACK=%d AXES=off CONTROL=%d' %
                          (display.active, int(args.control)), flush=True)
                    if args.product:
                        from product import update_journal, fingerprints
                        update_journal(args.root, 'READY' if backend.state == 'IDLE' else 'FAULT_IDLE',
                                       settings_at_ready=fingerprints(args.root), axes='off')
                    ui.dirty = True
                except (OSError, ValueError, RuntimeError) as exc:
                    if bus:
                        bus.close(); bus = None
                    touch_error(exc)
                    next_touch_retry = now+2.
            if touch is not None:
                try:
                    ui.touch(rotate_touch(touch.poll(), rotation))
                except (OSError, ValueError, RuntimeError) as exc:
                    touch = None
                    if bus:
                        bus.close(); bus = None
                    touch_error(exc)
                    next_touch_retry = now+2.
            if now-last_health >= .1:
                display.health()
                last_health = now
            interval = .5 if backend.busy else .2
            if ui.dirty and now-last_render >= interval:
                display.present(rotate_frame(ui.render(), rotation))
                last_render = time.monotonic()
            if ui.poweroff_ready:
                ui.message = 'Shutting down. Keep power connected.'
                display.present(rotate_frame(ui.render(), rotation))
                if not display.close():
                    raise RuntimeError('Display DMA STOP unconfirmed; shutdown blocked')
                try:
                    from product import poweroff
                    poweroff(args.root)
                    power_accepted = True
                    break
                except Exception as exc:
                    ui.shutdown_pending = False
                    ui.message = str(exc)
                    backend.fault('Shutdown failed: '+str(exc))
                    display = Display(mmio(0x43000000, 0x1000), gpio, allocate, np)
                    display.start(allocate)
                    wait_until(gpio.locked, 1., 'Screen timing lock after shutdown rejection')
                    display.present(rotate_frame(ui.render(), rotation)); gpio.backlight(True)
            time.sleep(.02)
    except Exception as exc:
        result = 1
        if args.product:
            from product import update_journal
            update_journal(args.root, 'ERROR', error=str(exc)[:400])
        print('SCREEN_STOP: %s: %s' % (type(exc).__name__, exc), file=sys.stderr, flush=True)
    finally:
        # 异常或退出先撤销运行时动作，等待真实退出；绝不静默强杀后重启。
        backend.stop()
        if gpio:
            try:
                gpio.backlight(False)
            except Exception as exc:
                print('BACKLIGHT_OFF_UNCONFIRMED: '+str(exc), file=sys.stderr, flush=True)
        last_report = 0.
        while backend.busy:
            backend.tick()
            if time.monotonic()-last_report > 5:
                print('EXIT_PENDING: '+backend.note, flush=True)
                last_report = time.monotonic()
            time.sleep(.05)
        if not power_accepted and (backend.session_failed or not backend.stop_verified):
            result = 1
        if display:
            while not display.close():
                print('DMA_STOP_UNCONFIRMED: retaining buffers, backlight OFF; do not reprogram/kill', flush=True)
                time.sleep(1)
        if bus:
            bus.close()
        fcntl.flock(owner, fcntl.LOCK_UN)
        owner.close()
        if args.product and not power_accepted:
            from product import update_journal
            update_journal(args.root, 'PANEL_STOPPED' if result == 0 else 'ERROR_STOPPED',
                           stop_verified=backend.stop_verified, exit_code=result)
    return result


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('SCREEN_ERROR: %s: %s' % (type(exc).__name__, exc), file=sys.stderr)
        raise SystemExit(1)
