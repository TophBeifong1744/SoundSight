"""PS-only volume extension: real mean absolute PCM level, no speech detection.

Raw solver results remain audit data. Only direction_output is the gated
application result. This client forbids motion, including through legacy calls.
"""
from ps_client import Client, MAGIC, ABI, STATUS

LEVEL_ABI = 0x00010001
LEVEL_CAP = 1 << 17
LEVEL_VALID = 1 << 5


def gate_record(record, threshold):
    """Return a separate application verdict; never relabel frozen S1 reasons.

    None measures only: there is no calibrated threshold and hence no real
    direction permission. Below threshold does not STOP acquisition or lose
    records. Cancelled/faulted/invalid measurements fail closed.
    """
    if 'frame' not in record or 'result' not in record:
        return record
    if threshold is not None and (type(threshold) is not int or not 1 <= threshold <= 0xffffff):
        raise ValueError('音量门限须为1..16777215的整数采样计数')
    frame, solver = record['frame'], record['result']
    status = frame['status']
    measured = bool(status & LEVEL_VALID) and bool(status & LEVEL_CAP) and not bool(status & 8)
    level = frame['energy'] if measured else None
    valid = False
    if frame['fault'] or status & (1 << 20):
        reason = 'fault_or_cancelled'
    elif status & 8:
        # BIST's synthetic 100000 is not real acoustic level or a calibration point.
        reason = 'bist_no_acoustic_output'
    elif not measured or type(level) is not int or not 0 <= level <= 0xffffff:
        reason = 'level_unavailable'
    elif threshold is None:
        reason = 'measurement_only'
    elif level < threshold:
        reason = 'below_volume_threshold'
    elif solver['bridge_status'] or solver['api_status'] or not solver['direction_valid']:
        reason = 'solver_rejected'
    else:
        reason, valid = 'valid', True
    return dict(record,
                volume=dict(level_counts=level, threshold_counts=threshold,
                            unit='mean_abs_dc_removed_pcm', measured=measured),
                direction_output=dict(valid=valid, angle_q8=solver['angle_q8'] if valid else None,
                                      reason=reason))


class VolumeClient(Client):
    def __init__(self, ip, solver, threshold=None):
        super().__init__(ip, solver)
        self.threshold = threshold

    def identify(self):
        # Reject old bitstreams before any write; zero in the old ENERGY field
        # must never be silently interpreted as silence.
        if self.read(MAGIC) != 0x5a5a2026 or self.read(ABI) != LEVEL_ABI:
            raise RuntimeError('需要PL+PS音量扩展ABI 0x00010001；旧bit不能测量真实音量')
        if not self.read(STATUS) & LEVEL_CAP:
            raise RuntimeError('硬件没有真实音量能力标志')

    def record_one(self, sink, config=None, motion=False, allow_fault=False):
        if motion:
            raise ValueError('音量扩展当前仅测量/记录，不驱动舵机')
        def gated_sink(record):
            sink(gate_record(record, self.threshold))
        raw = super().record_one(gated_sink, config, False, allow_fault)
        return gate_record(raw, self.threshold)

    def arm(self, watchdog_ticks):
        raise ValueError('音量扩展当前不授予动作许可')

    def command(self, frame, result):
        raise ValueError('音量扩展当前不提交舵机动作')
