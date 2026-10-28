"""Independent, bounded horizontal calibration. Never starts audio acquisition.

The hardware has a fixed 750 ms lease, renewed only by an explicit COMMIT.
No fabricated frame, snapshot consume, solver result or acoustic flag is used.
"""
import math
import time
from horizontal_motion import validate_calibration
from ps_client import MAGIC, ABI, SYS, STATUS, FAULT

CAP, CONTROL, ANGLE, LIMITS = 0x70, 0x74, 0x78, 0x7c
CAPABILITY = 0x4d534301


def validate_request(calibration, angle, seconds):
    config = validate_calibration(calibration)
    if type(angle) is not int or not config['min_deg'] <= angle <= config['max_deg']:
        raise ValueError('Manual angle is outside the configured mechanical range')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not .1 <= seconds <= 60:
        raise ValueError('Calibration duration must be 0.1..60 seconds')
    return config


def calibrate(ip, calibration, angle, seconds=5.0, clock=time.monotonic, sleep=time.sleep):
    """Caller holds the same owner lock as capture. Returns after PWM drain.

    All checks before the first write are read-only. A lost process leaves the
    independent hardware watchdog in charge; it cannot auto-arm on recovery.
    """
    config = validate_request(calibration, angle, seconds)
    read = lambda a: int(ip.read(a)) & 0xffffffff
    if read(MAGIC) != 0x5a5a2026 or read(ABI) != 0x10001:
        raise RuntimeError('Hardware ID/volume ABI mismatch')
    status = read(STATUS)
    if status & (3 << 18) != (3 << 18):
        raise RuntimeError('New manual-calibration bitstream required; no writes made')
    if read(CAP) != CAPABILITY:
        raise RuntimeError('Unsupported manual-calibration interface; no writes made')
    if read(SYS) != 8 or status & (3 | 0x8000) or read(CONTROL) & 3:
        raise RuntimeError('Stop capture and drain existing records/PWM before calibration')
    fault = read(FAULT)
    if fault & ~0x40:
        raise RuntimeError('Existing device fault 0x%x; inspect before calibration' % fault)
    count = 0
    try:
        if fault: ip.write(FAULT, 0x40)  # Only the known completed STOP marker.
        if read(FAULT): raise RuntimeError('Fault cause remains present')
        ip.write(LIMITS, config['min_deg'] | (config['max_deg'] << 16))
        ip.write(ANGLE, angle)
        ip.write(CONTROL, 1)
        if read(FAULT) or not read(CONTROL) & 1:
            raise RuntimeError('Manual ARM rejected')
        deadline = clock() + seconds
        while clock() < deadline:
            # Do not re-arm after a watchdog expiry, even if software resumes.
            if read(FAULT) or not read(CONTROL) & 1:
                raise RuntimeError('Manual permission lost/fault; no automatic restart')
            ip.write(CONTROL, 2)
            count += 1
            if read(FAULT): raise RuntimeError('Manual COMMIT rejected')
            sleep(min(.1, max(0.0, deadline-clock())))
    finally:
        ip.write(CONTROL, 0)
        until = clock() + .1
        while read(CONTROL) & 3:
            if clock() >= until:
                raise RuntimeError('Manual STOP drain timeout; preserve device state')
            sleep(.001)
    return dict(target_deg=angle, commits=count, seconds=seconds,
                audio_started=False, mechanical_arrival='UNVERIFIED', stopped=True)
