"""因果角度筛选：只处理已有记录，不访问硬件或提交动作。

与离线回放共享同一数学实现；窗口以帧数计，参数是实验值而非标定结论。
"""
import math
from statistics import mean

WINDOW = 20
MIN_VALID = 12
RADIUS_DEG = 10.0
CONSENSUS = 2 / 3
DEADBAND_DEG = 3.0


def validate_window(window_frames=WINDOW, min_valid=MIN_VALID):
    # 限制内存和圆周中心搜索规模；保持原有算法，只允许调整样本数量。
    if (type(window_frames) is not int or type(min_valid) is not int
            or not 1 <= min_valid <= window_frames <= 100):
        raise ValueError('Require 1 <= min_valid <= window_frames <= 100')
    return window_frames, min_valid


def difference(a, b):
    """Signed shortest angular displacement, in [-180, 180)."""
    return (a - b + 180) % 360 - 180


def circular_mean(angles):
    x = sum(math.cos(math.radians(a)) for a in angles)
    y = sum(math.sin(math.radians(a)) for a in angles)
    # Opposing directions have no meaningful mean, not a valid zero angle.
    if not angles or math.hypot(x, y) <= 1e-12 * len(angles):
        return None
    return difference(math.degrees(math.atan2(y, x)), 0)


def estimate(angles, min_valid=MIN_VALID, radius=RADIUS_DEG):
    """A circular L1 medoid locates the current window's majority direction.

    Keep samples within a fixed radius; require 12 retained samples AND at least
    two thirds of all valid samples. Parameters are experimental, not calibrated.
    The previous target is deliberately absent: genuine new directions can pass.
    """
    result = dict(valid_count=len(angles), arithmetic=None, circular_unfiltered=None,
                  center=None, inlier_count=0, filtered=None, decision='insufficient_valid')
    if len(angles) < min_valid:
        return result
    result['arithmetic'] = mean(angles)
    result['circular_unfiltered'] = circular_mean(angles)
    # Deterministic tie-break only; split populations are rejected by consensus.
    center = min(sorted(angles), key=lambda a: sum(abs(difference(b, a)) for b in angles))
    kept = [a for a in angles if abs(difference(a, center)) <= radius]
    result.update(center=center, inlier_count=len(kept))
    if len(kept) < min_valid or len(kept) / len(angles) < CONSENSUS:
        result['decision'] = 'insufficient_consensus'
        return result
    result['filtered'] = circular_mean(kept)
    result['decision'] = 'accepted' if result['filtered'] is not None else 'undefined_mean'
    return result


class OnlineAngleFilter:
    """可调非重叠窗口（默认20帧/至少12有效）；音量不足/故障/断序清空。

    输出只在完整且通过筛选的窗口末尾有效。死区内返回上次目标，
    updated=False；其余帧角度为None，不能把旧目标当作新的有效方向。
    求解拒绝帧计入窗口但不参与平均；低音量直接清窗，恢复后重新积累。
    """
    def __init__(self, window_frames=WINDOW, min_valid=MIN_VALID):
        self.window_frames, self.min_valid = validate_window(window_frames, min_valid)
        self.stopped = False
        self.reset()

    def reset(self):
        self.count = 0
        self.angles = []
        self.held = None
        self.last_sequence = None
        self.first_sequence = None

    def stop(self):
        self.reset()
        self.stopped = True

    def apply(self, record):
        if 'frame' not in record or 'result' not in record:
            return record
        gate = record['direction_output']
        sequence = record['frame']['sequence']
        output = dict(valid=False, angle_q8=None, angle_deg=None,
                      updated=False, reason='collecting_window')
        details = dict(window_size=self.window_frames, min_valid=self.min_valid,
                       radius_deg=RADIUS_DEG, min_consensus=CONSENSUS,
                       deadband_deg=DEADBAND_DEG, complete=False,
                       frame_count=0, valid_count=0, sequence_reset=False, reset_reason=None)
        # 即便排尾记录携带一个正常求解结果，也不能产生新目标。
        if self.stopped:
            output['reason'] = 'stopped_or_drain'
            details['reset_reason'] = 'stopped_or_drain'
        elif record['result']['api_status'] or record['result']['bridge_status']:
            self.reset()
            output['reason'] = 'solver_error'
            details['reset_reason'] = 'solver_error'
        elif not gate['valid'] and gate['reason'] != 'solver_rejected':
            self.reset()
            output['reason'] = gate['reason']
            details['reset_reason'] = gate['reason']
        else:
            if self.last_sequence is not None and sequence != self.last_sequence + 1:
                self.reset()
                details['sequence_reset'] = True
                details['reset_reason'] = 'sequence_gap'
            self.last_sequence = sequence
            if self.count == 0:
                self.first_sequence = sequence
            self.count += 1
            if gate['valid']:
                self.angles.append(gate['angle_q8'] / 256)
            details.update(frame_count=self.count, valid_count=len(self.angles),
                           first_sequence=self.first_sequence, last_sequence=sequence)
            if self.count == self.window_frames:
                result = estimate(self.angles, min_valid=self.min_valid)
                details.update(result, complete=True)
                candidate = result['filtered']
                if candidate is not None:
                    updated = self.held is None or abs(difference(candidate, self.held)) >= DEADBAND_DEG
                    if updated:
                        self.held = candidate
                    output.update(valid=True, angle_deg=self.held,
                                  angle_q8=round(self.held * 256), updated=updated,
                                  reason='target_updated' if updated else 'within_deadband')
                else:
                    output['reason'] = result['decision']
                self.count = 0
                self.angles = []
        # 分层保留：C原始result、单帧门限结果、最终多帧应用结果。
        return dict(record, frame_direction=gate, angle_filter=details,
                    direction_output=output)
