"""Unfrozen serialized-retarget streaming candidate; S24 PCM, Q12 delays/weights.

Three banks: mono plus at most two beam endpoints. During a fade only the
latest requested target is pending. It starts after the current fade ends.
This bounded policy intentionally differs from immediate arbitrary retargeting.
"""
from numbers import Integral
import numpy as np

Q = 4096


def integer(value):
    return isinstance(value, Integral) and not isinstance(value, (bool, np.bool_))


def rne(n, d):
    q, r = divmod(n, d)
    return q + int(2*r > d or (2*r == d and q % 2))


def checked_target(value):
    if value is None:
        return None
    if len(value) != 4 or any(not integer(v) or abs(v) > 8*Q for v in value):
        raise ValueError('four Q12 integer delays within +/-8 samples')
    return tuple(map(int, value))


class DynamicDAS:
    """push consumes physical sample time; returned samples start at emit=0.

    Source sample n is emitted at n+8. A control received at physical t first
    affects that emission time, never earlier. Caller splits input at controls.
    EOF returns the final 8 delayed samples with genuine out-of-record zeros.
    Control handling precedes TTL (> valid_through) at the same clock.
    """
    def __init__(self, fade_samples=480):
        if not integer(fade_samples) or fade_samples < 1:
            raise ValueError('positive integer fade')
        self.fade = int(fade_samples)
        self.time = 0
        self.closed = False
        self.samples = {}  # ring keyed by absolute input sample, at most 17 rows
        self.current = None
        self.transition = None  # (from, to, first emit)
        self.desired = None
        self.expiry = None
        self.control_at = None
        self.events = []
        self.max_history = 0
        self.max_beams = 0
        self.saturations = 0

    def control(self, *, state, delays=None, valid_through=None):
        if self.closed:
            raise ValueError('closed stream')
        if self.control_at == self.time:
            raise ValueError('one control per physical sample')
        if state not in ('LOCKED', 'HOLD', 'SEARCH', 'STOP'):
            raise ValueError('unsupported state')
        if state == 'LOCKED':
            target = checked_target(delays)
            if target is None or not integer(valid_through) or valid_through < self.time:
                raise ValueError('fresh beam needs unexpired integer TTL')
            self.desired, self.expiry = target, int(valid_through)
        elif state == 'HOLD':
            if delays is not None or valid_through is not None:
                raise ValueError('HOLD cannot replace beam or refresh TTL')
        else:
            if delays is not None or valid_through is not None:
                raise ValueError('fallback has no beam or TTL')
            self.desired, self.expiry = None, None
        self.control_at = self.time
        self.events.append({'emit': self.time, 'kind': state})

    def _beam(self, target, n):
        def sample(ch, k):
            if k < 0 or k >= self.input_end:
                return 0
            if k not in self.samples:
                raise AssertionError('required sample was released or not yet received')
            return self.samples[k][ch]
        if n < 0:
            return 0
        if target is None:
            return sample(0, n)
        acc = 0
        for ch, delay in enumerate(target):
            left, frac = divmod(n*Q-delay, Q)
            # Do not read zero-weight right sample: exact -8 needs no +9 lookahead.
            acc += sample(ch, left)*(Q-frac)
            if frac:
                acc += sample(ch, left+1)*frac
        return rne(acc, 4*Q)

    def _emit(self):
        t = self.time
        if self.expiry is not None and t > self.expiry:
            self.desired, self.expiry = None, None
            self.events.append({'emit': t, 'kind': 'TTL_EXPIRED'})
        if self.transition is not None and t-self.transition[2] >= self.fade:
            self.current = self.transition[1]
            self.transition = None
        if self.transition is None and self.desired != self.current:
            self.transition = (self.current, self.desired, t)
            self.events.append({'emit': t, 'kind': 'FADE_START',
                                'from': self.current, 'to': self.desired})
        n = t-8
        if self.transition is None:
            endpoints = (self.current,)
            alpha = 0
            value = self._beam(self.current, n)
        else:
            a, b, start = self.transition
            alpha = min(Q, rne((t-start)*Q, self.fade))
            endpoints = (a, b)
            value = rne(self._beam(a, n)*(Q-alpha) + self._beam(b, n)*alpha, Q)
        self.max_beams = max(self.max_beams, len(set(x for x in endpoints if x is not None)))
        assert -(1 << 23) <= value < (1 << 23)
        trace = {'emit': t, 'endpoints': endpoints, 'alpha': alpha,
                 'desired': self.desired, 'expiry': self.expiry}
        self.time += 1
        # next emission needs at earliest (t+1)-8-8 = t-15
        for key in list(self.samples):
            if key < self.time-16:
                del self.samples[key]
        return value, trace

    def push(self, chunk, final=False):
        if self.closed:
            raise ValueError('closed stream')
        x = np.asarray(chunk)
        if x.ndim != 2 or x.shape[0] != 4 or not np.issubdtype(x.dtype, np.integer) or np.any(x < -2**23) or np.any(x >= 2**23):
            raise ValueError('four-channel integer S24 PCM')
        output, traces = [], []
        for row in x.T:
            self.samples[self.time] = tuple(map(int, row))
            self.input_end = self.time+1
            self.max_history = max(self.max_history, len(self.samples))
            y, trace = self._emit()
            output.append(y); traces.append(trace)
        if final:
            self.input_end = self.time
            for _ in range(8):
                y, trace = self._emit()
                output.append(y); traces.append(trace)
            self.closed = True
        return np.asarray(output, dtype=np.int64), traces
