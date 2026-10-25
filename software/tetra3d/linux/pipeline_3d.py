"""Integrated, hardware-free 3D processing with explicit source-sample timing.

One object owns one contiguous session. Feature sequence numbers are NEVER PCM
timestamps. Pass capture_sample and now_sample from the same PCM source clock.
An invalid time, reordered feature, or bad PCM block latches the session failed;
create a new instance rather than continuing with potentially stale steering.
NumPy is imported only when DAS is explicitly enabled.
"""
import copy
from dataclasses import asdict
import math
from pathlib import Path
import sys

if __package__:
    from .solver_3d import Solver3D, _options
    from .spatial_runtime import (DirectionFilter3D, DirectionFilterConfig,
                                  DualAxisTracker, DualAxisConfig)
else:
    from solver_3d import Solver3D, _options
    from spatial_runtime import (DirectionFilter3D, DirectionFilterConfig,
                                 DualAxisTracker, DualAxisConfig)


def _mapping(value, name, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(name + ': expected dictionary with known fields')
    return copy.deepcopy(value)


def _four(values, name, low, high, lower_open=False):
    if not isinstance(values, (list, tuple)) or len(values) != 4:
        raise ValueError(name + ': four numbers required')
    answer = []
    for value in values:
        if type(value) not in (int, float):
            raise ValueError(name + ': finite numbers required')
        try:
            value = float(value)
        except OverflowError as exc:
            raise ValueError(name + ': finite numbers required') from exc
        if not math.isfinite(value) or value > high or value < low or (lower_open and value == low):
            raise ValueError(name + ': value outside permitted range')
        answer.append(value)
    return answer


def normalize_pipeline_config(config=None):
    """Validate plain JSON configuration without importing NumPy or a C library.

    Delay correction has one owner: calibration.channel_delay_samples. Supplying
    solver_options.channel_delay_samples is rejected even when values match.
    axes=None disables setpoint simulation; a fully specified axes object opts
    into software simulation, never PWM/MMIO or an actuator command.
    """
    cfg = _mapping({} if config is None else config, 'pipeline config',
                   ('schema', 'solver_options', 'calibration', 'calibration_source',
                    'direction_filter', 'das', 'axes'))
    if type(cfg.get('schema', 1)) is not int or cfg.get('schema', 1) != 1:
        raise ValueError('pipeline schema must be 1')
    options = cfg.get('solver_options', {})
    if not isinstance(options, dict) or 'channel_delay_samples' in options:
        raise ValueError('channel delays belong only in calibration')
    options = _options(options)
    options.pop('channel_delay_samples')
    calibration = _mapping(cfg.get('calibration', {'schema': 1}), 'calibration',
                           ('schema', 'channel_delay_samples', 'channel_gain'))
    if type(calibration.get('schema')) is not int or calibration['schema'] != 1:
        raise ValueError('calibration schema must be 1')
    calibration['channel_delay_samples'] = _four(
        calibration.get('channel_delay_samples', [0]*4), 'channel_delay_samples', -1., 1.)
    calibration['channel_gain'] = _four(
        calibration.get('channel_gain', [1]*4), 'channel_gain', 0., 8., True)
    source = cfg.get('calibration_source', 'UNCALIBRATED')
    if not isinstance(source, str) or not source.strip():
        raise ValueError('calibration_source must be a nonempty string')
    direction = cfg.get('direction_filter', {})
    if not isinstance(direction, dict):
        raise ValueError('direction_filter must be a dictionary')
    try:
        direction = asdict(DirectionFilterConfig(**direction))
    except TypeError as exc:
        raise ValueError('unknown direction_filter configuration') from exc
    das = _mapping(cfg.get('das', {}), 'das', ('enabled', 'fade_samples'))
    das = dict(enabled=das.get('enabled', False), fade_samples=das.get('fade_samples', 480))
    if type(das['enabled']) is not bool or type(das['fade_samples']) is not int or das['fade_samples'] < 1:
        raise ValueError('DAS needs boolean enabled and positive integer fade_samples')
    axes = cfg.get('axes')
    if axes is not None:
        fields = ('config', 'initial_yaw_deg', 'initial_pitch_deg', 'initial_time_s')
        axes = _mapping(axes, 'axes', fields)
        if set(axes) != set(fields) or not isinstance(axes['config'], dict):
            raise ValueError('axes requires config and explicit initial pose/time')
        try:
            axis_config = DualAxisConfig(**axes['config'])
            DualAxisTracker(axis_config, **{k: axes[k] for k in fields[1:]})
        except TypeError as exc:
            raise ValueError('unknown/missing axes configuration') from exc
        axes['config'] = asdict(axis_config)
    return dict(schema=1, solver_options=options, calibration=calibration,
                calibration_source=source, direction_filter=direction, das=das, axes=axes)


def solver_options_from_config(config=None):
    """Return effective solver options with the shared channel-delay calibration."""
    cfg = normalize_pipeline_config(config)
    options = copy.deepcopy(cfg['solver_options'])
    options['channel_delay_samples'] = list(cfg['calibration']['channel_delay_samples'])
    return options


def _sample(value, name):
    # Bound source time to retain substantially better than one-sample precision
    # when converting to float seconds. At 48 kHz this permits 185 years.
    if type(value) is not int or not 0 <= value < (1 << 48):
        raise ValueError(name + ' must be an integer in [0,2**48)')
    return value


class TetraPipeline:
    """Solver -> spherical tracker -> optional DAS / software axis setpoints.

    now_sample is nondecreasing. Capture samples and feature sequences strictly
    increase (poll at the same boundary is harmless). With DAS, process_frame and
    poll must occur exactly at next_sample: push historical PCM before applying
    a newly available feature. push_pcm performs at most one beam control at its
    boundary and the core enforces expiry inside the block. final=True closes
    the pipeline after emitting the eight-sample latency tail.
    """
    def __init__(self, library, geometry, config=None, *, session_id='session-0', target_id='unidentified'):
        if any(not isinstance(v, str) or not v.strip() for v in (session_id, target_id)):
            raise ValueError('nonempty session_id and target_id required')
        self._config = normalize_pipeline_config(config)
        self._session_id, self._target_id = session_id, target_id
        self._closed = self._faulted = False
        self._failure = None
        self._now = self._capture = self._sequence = None
        self._direction = None
        self._beam = self._axes = None
        self._filter_config = DirectionFilterConfig(**self._config['direction_filter'])
        self._filter = DirectionFilter3D(self._filter_config)
        self._solver = Solver3D(library, geometry, options=solver_options_from_config(self._config))
        try:
            rate = self._solver.geometry['sample_rate_hz']
            if type(rate) not in (int, float) or not math.isfinite(rate) or rate <= 0 or rate != int(rate):
                raise ValueError('positive integer source PCM sample rate required')
            self._sample_rate_hz = int(rate)
            if self._config['das']['enabled']:
                if __package__:
                    from ..das.das_3d import TetraDAS
                else:
                    # Support the existing direct linux-directory import style.
                    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                    try:
                        from das.das_3d import TetraDAS
                    finally:
                        sys.path.pop(0)
                self._beam = TetraDAS(self._solver.geometry,
                                      fade_samples=self._config['das']['fade_samples'],
                                      calibration=self._config['calibration'])
            if self._config['axes'] is not None:
                axes = self._config['axes']
                self._axes = DualAxisTracker(DualAxisConfig(**axes['config']),
                    **{key: axes[key] for key in ('initial_yaw_deg', 'initial_pitch_deg', 'initial_time_s')})
        except BaseException:
            self._solver.close()
            self._closed = True
            raise

    @property
    def closed(self):
        return self._closed

    @property
    def session_id(self):
        return self._session_id

    @property
    def target_id(self):
        return self._target_id

    @property
    def sample_rate_hz(self):
        return self._sample_rate_hz

    @property
    def faulted(self):
        return self._faulted

    @property
    def next_sample(self):
        return self._beam.next_sample if self._beam is not None else None

    def metadata(self):
        return copy.deepcopy(dict(schema=1, profile='TETRA40_3D',
            session_id=self.session_id, target_id=self.target_id,
            sample_rate_hz=self.sample_rate_hz, geometry=self._solver.geometry,
            solver_options=self._solver.options, config=self._config,
            timebase='SOURCE_PCM_SAMPLE_INDEX', axes_mode='SOFTWARE_ONLY',
            motion_requested=False, closed=self._closed, faulted=self._faulted,
            failure=self._failure))

    def _open(self):
        if self._faulted:
            raise RuntimeError('pipeline session faulted; create a new instance: ' + self._failure)
        if self._closed:
            raise RuntimeError('pipeline is closed')

    def _latch(self, exc):
        self._faulted = True
        self._failure = str(exc)
        self._direction = None
        self.close()

    def _time(self, now_sample):
        now = _sample(now_sample, 'now_sample')
        if self._now is not None and now < self._now:
            raise ValueError('source clock reversed; create a new session')
        if self._beam is not None and now != self.next_sample:
            raise ValueError('feature/control time must equal next PCM sample')
        return now

    def _axis(self, direction, now):
        if self._axes is None:
            return dict(command_valid=False, yaw_deg=None, pitch_deg=None,
                        reason='disabled', software_only=True)
        result = self._axes.update(direction, now_s=now/self.sample_rate_hz, enable=True)
        result['software_only'] = True
        return result

    def process_frame(self, frame, *, capture_sample, now_sample):
        self._open()
        try:
            now = self._time(now_sample)
            capture = _sample(capture_sample, 'capture_sample')
            if capture > now or (self._capture is not None and capture <= self._capture):
                raise ValueError('capture time future, duplicate, or out of order')
            if not isinstance(frame, dict):
                raise ValueError('frame must be a dictionary')
            sequence = frame.get('sequence')
            if type(sequence) is not int or not 0 <= sequence <= 0xffffffff:
                raise ValueError('frame sequence must be uint32')
            if self._sequence is not None and sequence <= self._sequence:
                raise ValueError('duplicate/reordered frame; restart session before sequence wrap')
            fault = frame.get('fault', 0)
            if type(fault) is not int or not 0 <= fault <= 0xffffffff:
                raise ValueError('frame fault must be uint32')
            for key in ('stopped', 'drain'):
                if key in frame and type(frame[key]) is not bool:
                    raise ValueError(key + ' must be boolean')
            result = self._solver.solve(frame)
            flags = frame['status']
            unsafe = (fault != 0 or bool(flags & (8 | 0x8000 | 0x100000 | 0xff000000))
                      or frame.get('stopped', False) or frame.get('drain', False)
                      or result['bridge_status'] != 0 or result['api_status'] != 0
                      or result['reason'] in (5, 6, 7, 8))
            stale = now/self.sample_rate_hz-capture/self.sample_rate_hz > self._filter_config.max_age_s
            if unsafe or stale:
                # Discard HOLD as well as candidates; never carry a real target
                # across BIST, stop/drain, cancelled data or a source fault.
                # A stale frame must not reject once and then revive the old
                # target on the next poll/push boundary.
                self._filter = DirectionFilter3D(self._filter_config)
                filter_input = {'direction_valid': 0}
            else:
                filter_input = result
            direction = self._filter.update(filter_input,
                timestamp_s=capture/self.sample_rate_hz, now_s=now/self.sample_rate_hz,
                sequence=sequence, session_id=self.session_id,
                target_id=self.target_id)['filtered_direction']
            if unsafe:
                direction['reason'] = 'source_fault_bist_or_stop'
            self._direction = direction
            self._now, self._capture, self._sequence = now, capture, sequence
            return copy.deepcopy(dict(frame=frame, result=result,
                filtered_direction=direction, axis_setpoint=self._axis(direction, now),
                motion_requested=False, timing=dict(capture_sample=capture,
                    now_sample=now, sample_rate_hz=self.sample_rate_hz)))
        except Exception as exc:
            self._latch(exc)
            raise

    def poll(self, *, now_sample):
        self._open()
        try:
            now = self._time(now_sample)
            direction = self._filter.poll(now_s=now/self.sample_rate_hz)
            self._direction, self._now = direction, now
            return copy.deepcopy(dict(filtered_direction=direction,
                axis_setpoint=self._axis(direction, now), motion_requested=False,
                timing=dict(now_sample=now, sample_rate_hz=self.sample_rate_hz)))
        except Exception as exc:
            self._latch(exc)
            raise

    def push_pcm(self, pcm, *, start_sample, final=False):
        self._open()
        try:
            if self._beam is None:
                raise ValueError('DAS is not enabled in this pipeline')
            if type(final) is not bool:
                raise ValueError('final must be boolean')
            start = self._time(start_sample)
            # Whole-block preflight before submitting any control or consuming
            # samples. TetraDAS repeats this defensive check for direct callers.
            checked = self._beam.calibration.apply_pcm(pcm)
            if checked.shape[1] == 0 and not final:
                raise ValueError('empty PCM block requires final=True')
            _sample(start + checked.shape[1] + (8 if final else 0), 'PCM end')
            direction = self._filter.poll(now_s=start/self.sample_rate_hz)
            self._direction = direction
            # valid_until is exclusive. Rounding down then subtracting one is
            # conservative by at most one sample, never prolongs the target.
            expiry = (math.floor(direction['valid_until_s'] * self.sample_rate_hz)-1
                      if direction['valid'] else -1)
            if direction['valid'] and expiry >= start:
                self._beam.steer(direction['vector'], valid_through=expiry)
            else:
                self._beam.fallback()
            output = self._beam.push(pcm, start_sample=start, final=final)
            self._now = self.next_sample
            if final:
                self.close()
            return output
        except Exception as exc:
            self._latch(exc)
            raise

    def close(self):
        self._solver.close()
        self._closed = True

    def __enter__(self):
        self._open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
