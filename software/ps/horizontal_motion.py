"""Horizontal motion on fresh real frames; existing register ABI is unchanged.

Calibration lives on PYNQ. No movement is enabled merely by importing this
module or loading the actuator-capable bitstream. The caller explicitly selects
motion and supplies mechanical limits. Vertical commands are never generated.
"""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from ps_client import Client, ACT, STATUS, FAULT
from volume_gate import VolumeClient

CLOCK_HZ = 61440000
WATCHDOG_TICKS = 46080000  # 750 ms: same host-loss budget as the normal runtime.


def validate_geometry(config):
    """Fixed array origin: +X is DOA 0 deg, +Y is DOA +90 deg; units cm.

    Range is horizontal distance from the array, supplied by the user. It is
    never inferred from volume. None keeps direction-only (far-field) aiming.
    """
    if not isinstance(config, dict):
        raise ValueError('Geometry must be an object')
    names = ('pivot_x_cm', 'pivot_y_cm', 'source_range_cm')
    if set(config) - set(names):
        raise ValueError('Unknown geometry field')
    result = dict(pivot_x_cm=0.0, pivot_y_cm=0.0, source_range_cm=None)
    result.update(config)
    for key, value in result.items():
        if key == 'source_range_cm' and value is None:
            continue
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Geometry values must be finite numbers in cm')
        if key == 'source_range_cm' and value <= 0:
            raise ValueError('Source range must be positive or null')
    return result


def validate_calibration(config):
    """Servo angles are integer degrees; optional geometry is in centimetres."""
    names = ('front_deg', 'direction', 'min_deg', 'max_deg')
    if any(type(config.get(n)) is not int for n in names):
        raise ValueError('Calibration requires integer front_deg, direction, min_deg, max_deg')
    if config['direction'] not in (-1, 1):
        raise ValueError('direction must be +1 or -1')
    if not 0 <= config['min_deg'] <= config['front_deg'] <= config['max_deg'] <= 360:
        raise ValueError('Require 0 <= min_deg <= front_deg <= max_deg <= 360')
    result = {n: config[n] for n in names}
    if 'geometry' in config:
        result['geometry'] = validate_geometry(config['geometry'])
    return result


def load_calibration(path):
    return validate_calibration(json.loads(Path(path).read_text(encoding='utf-8')))


def mapped_target(q8, config):
    """Return (servo angle, rejection reason), without modifying raw DOA.

    In finite-range mode the source is R*(cos(theta),sin(theta)) at the
    array origin. Subtract the pivot position before computing its bearing.
    The pointed component's mounting yaw is included in front_deg calibration.
    This model assumes its pointing axis passes through the horizontal pivot.
    """
    if type(q8) is not int or not -180*256 <= q8 < 180*256:
        return None, 'INVALID_SOURCE_ANGLE'
    angle = q8 / 256
    geometry = config.get('geometry', {})
    distance = geometry.get('source_range_cm')
    x, y = geometry.get('pivot_x_cm', 0), geometry.get('pivot_y_cm', 0)
    if distance is not None and (x != 0 or y != 0):
        radians = math.radians(angle)
        dx, dy = distance*math.cos(radians)-x, distance*math.sin(radians)-y
        # At the pivot the bearing is undefined. The tiny relative tolerance
        # only absorbs trig roundoff; it is not a physical clearance limit.
        if (not math.isfinite(dx) or not math.isfinite(dy) or
                math.hypot(dx, dy) <= 1e-12*max(distance, abs(x), abs(y), 1.0)):
            return None, 'GEOMETRY_TARGET_UNDEFINED'
        angle = (math.degrees(math.atan2(dy, dx)) + 180) % 360 - 180
    target = config['front_deg'] + config['direction']*angle
    if not config['min_deg'] <= target <= config['max_deg']:
        return None, 'OUTSIDE_MECHANICAL_RANGE'
    # Python integer round uses nearest/even, as required by the S1 mapping.
    return round(target), None


def map_angle(q8, config):
    return mapped_target(q8, config)[0]


def check_hwh(path, ip='ps_link', *, automatic_motion=True):
    # Shared prepare/status/manual checks validate the electrical configuration
    # only; old automatic-follow callers must also reject a dual-axis design.
    if automatic_motion:
        from run_capture import require_legacy_motion_hwh
        require_legacy_motion_hwh(path, ip)
    modules = [m for m in ET.parse(path).iter('MODULE')
               if m.get('INSTANCE') == ip and m.get('MODTYPE') == 'bd_ps_link']
    if len(modules) != 1:
        raise ValueError('Expected one bd_ps_link in HWH')
    params = {p.get('NAME'): p.get('VALUE') for p in modules[0].iter('PARAMETER')}
    expected = dict(ACTUATOR_BOUND=1, LEVEL_ENABLE=1, CLK_FREQ_HZ=CLOCK_HZ,
                    SERVO_MAX=360, MECHANICAL_MIN=0, MECHANICAL_MAX=360)
    for key, value in expected.items():
        if int(params.get(key, '-1'), 0) != value:
            raise ValueError('Horizontal HWH requires %s=%s' % (key, value))


def qualified(frame, result):
    """Mirror public raw eligibility before COMMIT; hardware remains authoritative."""
    status = frame['status']
    if (frame['fault'] or not status & 16 or status & (8 | (1 << 20))
            or status >> 24 or result['bridge_status'] or result['api_status']
            or not result['direction_valid']):
        return False
    count = 0
    for i in range(6):
        w = frame['words'][5*i]
        if (w >> 24 == 0x11 and w & (1 << 11) and w & (1 << 13)
                and not w & ((1 << 15) | (1 << 14)) and (w >> 16) & 127 >= 12):
            count += 1
    return count >= 3


class HorizontalClient(VolumeClient):
    """Only this explicit runtime may turn filtered angles into actuator commits.

    A completed good window establishes a target. Subsequent fresh, loud,
    individually valid frames may refresh that SAME target during collection,
    including inside the 3-degree deadband. An isolated rejected sample cannot
    refresh the watchdog; low volume/gap or failed window revokes the output.
    Resuming follow after revoke needs a new good window.
    Manual calibration uses a fixed bounded angle, but still requires a fresh
    loud qualified real frame. It cannot bypass BIST/fault/ownership protection.
    """
    def __init__(self, ip, solver, threshold, calibration, manual_angle=None,
                 window_frames=20, min_valid=12):
        super().__init__(ip, solver, threshold, True, window_frames, min_valid)
        self.calibration = validate_calibration(calibration)
        if manual_angle is not None and (type(manual_angle) is not int or
                not calibration['min_deg'] <= manual_angle <= calibration['max_deg']):
            raise ValueError('Manual angle is outside the configured mechanical range')
        self.manual_angle = manual_angle
        self.target = None
        self.motion_stopped = False
        self.commits = 0
        self.stop_requested = lambda: False

    def identify(self):
        super().identify()
        if not self.read(STATUS) & (1 << 19):
            raise RuntimeError('Horizontal-capable bitstream is required')

    def revoke(self):
        # REVOKE drops PWM permission without stopping microphone acquisition.
        if self.read(ACT) & 1:
            self.write(ACT, 4)
        self.target = None

    def stop_direction_output(self):
        self.motion_stopped = True
        self.revoke()
        super().stop_direction_output()

    def apply_motion(self, record):
        frame, result = record['frame'], record['result']
        output, detail = record['direction_output'], record['angle_filter']
        action = dict(requested=True, committed=False, servo_deg=None,
                      reason='WAITING_FOR_WINDOW', mechanical_arrival='UNVERIFIED')
        record['motion'] = action
        record['motion_requested'] = True
        fresh = qualified(frame, result) and record['frame_direction']['valid']
        if self.motion_stopped or self.stop_requested() or detail.get('reset_reason'):
            self.revoke()
            action['reason'] = 'REVOKED_INVALID_OR_STOPPED'
            return
        if not fresh:
            # No new command on a rejected sample. While collecting, preserve
            # the last accepted target only under the existing hardware lease.
            # An ineligible window-ending sample cannot establish a new target.
            if detail['complete'] or self.manual_angle is not None:
                self.revoke()
            action['reason'] = 'NO_FRESH_QUALIFIED_COMMAND'
            return
        if self.manual_angle is not None:
            self.target = self.manual_angle
        elif output['valid']:
            self.target, reason = mapped_target(output['angle_q8'], self.calibration)
            if self.target is None:
                self.revoke()
                action['reason'] = reason
                return
        elif detail['complete']:
            self.revoke()
            action['reason'] = 'REVOKED_WINDOW_REJECTED'
            return
        if self.target is None:
            return
        # A revoke may be draining the previous high pulse. Never block frame
        # consumption while waiting and never submit a command during drain.
        if self.read(STATUS) & (1 << 15):
            action['reason'] = 'WAITING_FOR_PWM_DRAIN'
            return
        if self.read(FAULT):
            raise RuntimeError('Device fault before horizontal COMMIT')
        if not self.read(ACT) & 1:
            Client.arm(self, WATCHDOG_TICKS)
        if self.stop_requested():
            self.revoke()
            action['reason'] = 'REVOKED_USER_STOP'
            return
        # Use the public current-frame command path, substituting only the
        # explicitly mapped application target, never editing the raw result.
        command = dict(result, servo_deg=self.target, servo_cmd_valid=1)
        Client.command(self, frame, command)
        self.commits += 1
        action.update(committed=True, servo_deg=self.target, reason='COMMIT_NO_FAULT_OBSERVED')

    def record_one(self, sink, config=None, motion=False, allow_fault=False):
        def act_then_accept(record):
            self.apply_motion(record)
            sink(record)
        # The base Client catches errors, requests STOP and retains the locked
        # frame; command always precedes CONSUME. No SD I/O in this callback.
        return super().record_one(act_then_accept, config, False, allow_fault)
