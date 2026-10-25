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


def checked_pcm(chunk):
    """Validate the whole block before any stream state is advanced."""
    x = np.asarray(chunk)
    if x.ndim != 2 or x.shape[0] != 4 or not np.issubdtype(x.dtype, np.integer) or np.any(x < -2**23) or np.any(x >= 2**23):
        raise ValueError('four-channel integer S24 PCM')
    return x


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
        # Physical t emits source t-8; +/-8 delays require exactly [t-16,t].
        # Tags distinguish genuine stream boundaries from a missing ring row.
        self.samples = [[0, 0, 0, 0] for _ in range(17)]
        self._sample_times = [-1] * 17
        self.input_end = 0
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

    def _sample(self, ch, k):
        if k < 0 or k >= self.input_end:
            return 0
        slot = k % 17
        if self._sample_times[slot] != k:
            raise AssertionError('required sample was released or not yet received')
        return self.samples[slot][ch]

    def _beam(self, target, n):
        if n < 0:
            return 0
        if target is None:
            return self._sample(0, n)
        acc = 0
        sample = self._sample
        for ch, delay in enumerate(target):
            left, frac = divmod(n*Q-delay, Q)
            # Do not read zero-weight right sample: exact -8 needs no +9 lookahead.
            acc += sample(ch, left)*(Q-frac)
            if frac:
                acc += sample(ch, left+1)*frac
        return rne(acc, 4*Q)

    def _emit(self, include_trace=True):
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
            alpha = 0
            value = self._beam(self.current, n)
            beams = int(self.current is not None)
            if include_trace:
                endpoints = (self.current,)
        else:
            a, b, start = self.transition
            alpha = min(Q, rne((t-start)*Q, self.fade))
            value = rne(self._beam(a, n)*(Q-alpha) + self._beam(b, n)*alpha, Q)
            beams = int(a is not None) + int(b is not None and b != a)
            if include_trace:
                endpoints = (a, b)
        if beams > self.max_beams:
            self.max_beams = beams
        assert -(1 << 23) <= value < (1 << 23)
        trace = None
        if include_trace:
            trace = {'emit': t, 'endpoints': endpoints, 'alpha': alpha,
                     'desired': self.desired, 'expiry': self.expiry}
        self.time += 1
        return value, trace

    def push(self, chunk, final=False, *, trace=True):
        """Return (S24-in-int64 audio, traces); trace=False returns an empty list.

        The legacy default still includes every per-sample trace. Disabling it
        changes allocations only, never control timing or numerical output.
        """
        if self.closed:
            raise ValueError('closed stream')
        if type(trace) is not bool:
            raise ValueError('trace must be a bool')
        x = checked_pcm(chunk)
        count = x.shape[1]
        output = np.empty(count + (8 if final else 0), dtype=np.int64)
        traces = [None] * len(output) if trace else []
        for index in range(count):
            slot = self.time % 17
            row = self.samples[slot]
            row[0], row[1], row[2], row[3] = (int(x[0, index]), int(x[1, index]),
                                           int(x[2, index]), int(x[3, index]))
            self._sample_times[slot] = self.time
            self.input_end = self.time+1
            if self.max_history < 17:
                self.max_history = min(self.input_end, 17)
            output[index], item = self._emit(trace)
            if trace:
                traces[index] = item
        if final:
            self.input_end = self.time
            for index in range(count, count+8):
                output[index], item = self._emit(trace)
                if trace:
                    traces[index] = item
            self.closed = True
        return output, traces
