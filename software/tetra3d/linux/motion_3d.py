"""PS dual-axis v1 client and fixed-array geometric mapping.

No actuation on import/construction. Callers hold the existing PS owner lock.
A mode change always revokes the old command; no automatic re-arm after expiry.
"""
import math
import time
from ps_client import MAGIC, ABI, SYS, STATUS, FAULT, SEQ, ACT
from filter_3d import angles, unit

CAP, COMMAND, STATE, TARGET = 0xa0, 0xa4, 0xa8, 0xac
H_LIMITS, V_LIMITS, AXES, FRAME = 0xb0, 0xb4, 0xb8, 0xbc
LAST_TARGET, LAST_FRAME = 0xc0, 0xc4
CAPABILITY = 0x44554101
MASKS = dict(off=0, horizontal=1, vertical=2, both=3)


def calibration(value, maximum):
    keys = ('front_deg', 'direction', 'min_deg', 'max_deg')
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('Calibration requires front_deg direction min_deg max_deg')
    if any(type(value[k]) is not int for k in keys):
        raise ValueError('Calibration values must be integers')
    if value['direction'] not in (-1, 1) or not 0 <= value['min_deg'] <= value['front_deg'] <= value['max_deg'] <= maximum:
        raise ValueError('Calibration direction/range invalid for %d degree servo' % maximum)
    return dict(value)


def selected_calibration(config, mask):
    if type(mask) is not int or mask not in (1, 2, 3):
        raise ValueError('Select horizontal, vertical or both explicitly')
    return {name: calibration(config[name], maximum) for bit, name, maximum in
            ((1, 'horizontal', 360), (2, 'vertical', 220)) if mask & bit}


def pointing_geometry(value):
    defaults = dict(pivot_x_cm=0., pivot_y_cm=0., pivot_z_cm=0., source_range_cm=None)
    if not isinstance(value, dict) or set(value)-set(defaults):
        raise ValueError('Unknown pointing geometry field')
    defaults.update(value)
    for key, v in defaults.items():
        if key == 'source_range_cm' and v is None:
            continue
        if type(v) not in (float, int) or not math.isfinite(v):
            raise ValueError('Pointing geometry must contain finite centimetres')
        if key == 'source_range_cm' and v <= 0:
            raise ValueError('Known source range must be positive')
    return defaults


def mapped_targets(output, config, mask):
    cfg = selected_calibration(config, mask)
    if not output.get('valid'):
        return None, 'NO_VALID_DIRECTION'
    direction = output
    geom = pointing_geometry(config.get('pointing', {}))
    if geom['source_range_cm'] is not None:
        distance = geom['source_range_cm']
        try:
            vector = unit(output['vector'])
            delta = [distance*v-geom[k] for v, k in zip(vector, ('pivot_x_cm', 'pivot_y_cm', 'pivot_z_cm'))]
            if math.sqrt(sum(v*v for v in delta)) <= 1e-12*max(distance, 1.):
                return None, 'POINTING_DIRECTION_UNDEFINED'
            direction = angles(delta)
        except (ValueError, TypeError):
            return None, 'POINTING_DIRECTION_UNDEFINED'
    targets = dict(horizontal=0, vertical=0)
    for name, field in (('horizontal', 'azimuth'), ('vertical', 'elevation')):
        if name not in cfg:
            continue
        if not direction.get(field+'_valid') or direction.get(field+'_deg') is None:
            return None, 'AXIS_UNOBSERVABLE'
        c = cfg[name]
        target = c['front_deg'] + c['direction']*direction[field+'_deg']
        if not math.isfinite(target) or not c['min_deg'] <= target <= c['max_deg']:
            return None, 'OUTSIDE_MECHANICAL_RANGE'
        targets[name] = round(target)
    return targets, None


class DualAxis:
    def __init__(self, ip):
        self.ip = ip

    def read(self, address):
        return int(self.ip.read(address)) & 0xffffffff

    def identify(self):
        if self.read(MAGIC) != 0x5a5a2026 or self.read(ABI) != 0x10001:
            raise RuntimeError('PL ID/volume ABI mismatch; no writes')
        if self.read(CAP) != CAPABILITY:
            raise RuntimeError('Dual-axis bitstream required; no writes')

    def configure(self, config, mask):
        cfg = selected_calibration(config, mask)
        if self.read(STATE) & 0x19:
            raise RuntimeError('Revoke and finish PWM drain before changing calibration')
        if self.read(FAULT):
            raise RuntimeError('Inspect device faults before configuration')
        limits = {}
        for name, address in (('horizontal', H_LIMITS), ('vertical', V_LIMITS)):
            c = cfg.get(name, dict(min_deg=0, max_deg=0))
            limits[name] = c['min_deg'] | c['max_deg'] << 16
            self.ip.write(address, limits[name])
        self.ip.write(AXES, mask)
        self.ip.write(COMMAND, 4)
        if self.read(FAULT) or (self.read(STATE) >> 8) & 3 != mask:
            raise RuntimeError('Dual-axis configuration rejected')
        if self.read(0xcc) != limits['horizontal'] or self.read(0xd0) != limits['vertical']:
            raise RuntimeError('Applied limits differ from requested limits')

    def arm(self, follow, permit_check=None):
        if self.read(STATE) & 0x19 or self.read(FAULT):
            raise RuntimeError('Dual-axis ARM requires inactive, drained, fault-free device')
        if permit_check is not None and not permit_check():
            self.revoke()
            return False
        self.ip.write(COMMAND, 2 if follow else 1)
        state = self.read(STATE)
        if self.read(FAULT) or not state & 1 or bool(state & 2) != bool(follow):
            raise RuntimeError('Dual-axis ARM rejected')
        return True

    def commit(self, targets, sequence=None, permit_check=None):
        state = self.read(STATE)
        if not state & 1 or state & 0x18 or self.read(FAULT):
            raise RuntimeError('Motion permit expired/revoked; no automatic restart')
        follow = bool(state & 2)
        if follow != (sequence is not None):
            raise ValueError('Follow requires a current frame; manual must not use one')
        h, v = targets['horizontal'], targets['vertical']
        if type(h) is not int or type(v) is not int or not 0 <= h <= 360 or not 0 <= v <= 220:
            raise ValueError('Target outside electrical angle domain')
        packed = h | v << 16
        # Both shadows belong to one commit. Hardware validates full sequence and both limits.
        self.ip.write(TARGET, packed)
        if follow:
            if type(sequence) is not int or not 1 <= sequence <= 0xffffffff:
                raise ValueError('Expected nonzero uint32 frame sequence')
            if not self.read(STATUS) & 1 or self.read(SEQ) != sequence:
                raise RuntimeError('Current locked frame changed before dual-axis COMMIT')
            self.ip.write(FRAME, sequence)
        # Re-check immediately before the committing MMIO write. A permission
        # can expire or be revoked while ARM/shadow registers are being serviced.
        if permit_check is not None and not permit_check():
            self.revoke()
            return False
        self.ip.write(COMMAND, 3)
        if self.read(FAULT) or self.read(LAST_TARGET) != packed or not self.read(STATE) & 4:
            raise RuntimeError('Dual-axis COMMIT rejected')
        if follow and self.read(LAST_FRAME) != sequence:
            raise RuntimeError('Dual-axis frame acknowledgement mismatch')
        return True

    def revoke(self):
        self.ip.write(COMMAND, 0)

    def wait_drained(self, clock=time.monotonic, sleep=time.sleep):
        end = clock() + .1
        while self.read(STATE) & 0x19:
            if clock() >= end:
                raise TimeoutError('Dual-axis drain not confirmed')
            sleep(.001)


def manual(ip, config, targets, seconds=3., clock=time.monotonic, sleep=time.sleep):
    if not isinstance(targets, dict) or not targets or set(targets)-{'horizontal', 'vertical'}:
        raise ValueError('Specify at least one axis')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not .1 <= seconds <= 60:
        raise ValueError('Manual duration must be 0.1..60 seconds')
    mask = (1 if 'horizontal' in targets else 0) | (2 if 'vertical' in targets else 0)
    cfg = selected_calibration(config, mask)
    for name, value in targets.items():
        if type(value) is not int or not cfg[name]['min_deg'] <= value <= cfg[name]['max_deg']:
            raise ValueError('Manual target outside calibrated limits')
    axes = DualAxis(ip)
    axes.identify()
    if axes.read(SYS) != 8 or axes.read(STATUS) & (3 | 0x8000) or axes.read(STATE) & 0x19:
        raise RuntimeError('Stop acquisition and drain old frames/PWM before manual calibration')
    fault = axes.read(FAULT)
    if fault & ~0x40:
        raise RuntimeError('Existing hardware fault; inspect before calibration')
    count = 0
    try:
        if fault:
            ip.write(FAULT, 0x40)
        axes.configure(config, mask)
        axes.arm(False)
        packed = dict(horizontal=0, vertical=0)
        packed.update(targets)
        deadline = clock() + seconds
        while clock() < deadline:
            axes.commit(packed)
            count += 1
            sleep(.1)
    finally:
        try:
            axes.revoke()
            axes.wait_drained(clock, sleep)
        except BaseException:
            # Even a failed extension access must attempt the independent
            # legacy stop paths. Do not report mechanical arrival/stop on error.
            try:
                ip.write(ACT, 2)
            finally:
                ip.write(SYS, 8)
            raise
    return dict(commits=count, axes=mask, targets=targets, audio_started=False,
                mechanical_arrival='UNVERIFIED', stop_confirmed=True)
