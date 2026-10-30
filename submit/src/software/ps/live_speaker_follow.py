"""Continuous CP1/VF1 scoring for the explicitly delayed permission experiment.

Shares native PCM/frontend and original enrollment with LiveSpeaker. Does not
change the legacy two-second source-age policy in the diagnostic entry.
"""
from collections import deque
import math
import queue
import threading

from live_speaker import LiveSpeaker
from pipeline_bench import unit
from stream_bench import MAX_FRONT_LAG
from speaker_permission import POLICY
from speaker_statistics import SpeakerStatistics


class LatestEvents:
    """Bounded mailboxes for voice, latest attempt and latest numeric score.

    A dedicated passing-result slot survives later low scores or skipped jobs.
    Threads never perform socket/console writes; storage stays constant.
    """
    def __init__(self, threshold=None):
        self.threshold = threshold
        self.passing_result = None
        self.lock = threading.Lock()
        self.voice = self.result = None
        self.scored_result = None

    def publish(self, event):
        with self.lock:
            if event['kind'] == 'voice':
                self.voice = event
            else:
                self.result = event
                score = event.get('score')
                if type(score) in (int, float) and math.isfinite(score) and -1 <= score <= 1:
                    self.scored_result = event
                    if event.get('usable') and self.threshold is not None and score >= self.threshold:
                        self.passing_result = event

    def take(self):
        with self.lock:
            result = self.result
            if result is not None and self.scored_result is not None:
                # Keep the latest diagnostic score even after a skipped attempt.
                result = dict(result, display_result=dict(self.scored_result))
            values = [self.voice] if self.voice is not None else []
            if self.passing_result is not None and self.passing_result is not self.result:
                values.append(self.passing_result)
            if result is not None:
                values.append(result)
            self.passing_result = None
            self.voice = self.result = None
            self.scored_result = None
        return values


class FollowSpeaker(LiveSpeaker):
    def __init__(self, *args, event_sink, collect_statistics=False, statistics_threshold=None, **kwargs):
        self.statistics = SpeakerStatistics(statistics_threshold) if collect_statistics else None
        self.event_sink = event_sink
        self.completed_rows = deque(maxlen=32)
        self.completed_count = 0
        super().__init__(*args, **kwargs)

    def _front(self):
        samples = bytearray()
        speech_start = None
        previous_voice = -1
        try:
            while not self.start_event.wait(.05):
                if self.stop.is_set():
                    return
            while not self.stop.is_set():
                try:
                    data = self.input.get(timeout=.05)
                except queue.Empty:
                    if self.input_done.is_set():
                        break
                    continue
                if self.packet_taken is not None:
                    self.packet_taken()
                samples.extend(data[32:])
                if len(samples) < 1536*16:
                    continue
                begin = self.clock()
                if begin-self.origin-(self.cache.samples+512)/16000 > MAX_FRONT_LAG:
                    raise RuntimeError('SPEAKER_FRONTEND_OVERRUN')
                self.cache.push(self.front.run_pcm32(samples))
                samples.clear()
                self.front_blocks += 1
                self.front_seconds += self.clock()-begin
                lag = self.clock()-self.origin-self.cache.samples/16000
                self.max_lag = max(self.max_lag, lag)
                if lag > MAX_FRONT_LAG:
                    raise RuntimeError('SPEAKER_FRONTEND_OVERRUN')
                self.mail.update_voice(self.cache)
                if self.cache.voice_epoch != previous_voice:
                    previous_voice = self.cache.voice_epoch
                    speech_start = self.cache.samples-512 if self.cache.active else None
                self.event_sink(dict(kind='voice', epoch=self.epoch, voice_epoch=self.cache.voice_epoch,
                                     active=self.cache.active, at=self.clock(), end_sample16=self.cache.samples))
                # Start with the first VAD-qualified sound, not capture start.
                # Then replace the sole pending window every frontend block;
                # no accumulated inference backlog and no waiting for a batch.
                if speech_start is not None and self.cache.samples//160*160-speech_start >= 16000:
                    job = self.cache.snapshot(1.)
                    job['epoch'] = self.epoch
                    self.mail.put(job)
            self.partial_samples = len(samples)//16
            if samples and not self.stop.is_set():
                self.front.check_pcm32_tail(samples)
            if not self.stop.is_set():
                self.mail.finish()
        except BaseException as exc:
            self.fail(repr(exc))

    def _infer(self):
        try:
            while not self.stop.is_set():
                job = self.mail.take()
                if job is None:
                    break
                began = self.clock()
                age = began-self.origin-job['end_sample16']/16000
                row = {k: v for k, v in job.items() if k != 'features'}
                row.update(kind='result', score=None, usable=False, reason='insufficient_speech',
                           target_id=self.config.get('target_id', 'P01'), model_selection='cp1_vf1',
                           profile_score_only=self.config.get('score_only', False), recognition_qualified=False,
                           start_age_seconds=age)
                if job['coverage'] >= .5 and job['active']:
                    if (job['frames'] != 98 or len(job['features']) != 7840 or
                            not all(math.isfinite(x) for x in job['features'])):
                        raise ValueError('CP1 requires 98x80 finite native features')
                    vector = unit(self.embed.run('J', job['features']))
                    row['score'] = max(-1., min(1., sum(x*y for x, y in zip(vector, self.config['template']))))
                    with self.mail.cv:
                        row['usable'] = bool(not self.mail.error and not self.stop.is_set())
                    row['reason'] = 'scored' if row['usable'] else 'capture_failed'
                row.update(completed_at=self.clock(), compute_seconds=self.clock()-began,
                           source_age_seconds=self.clock()-self.origin-job['end_sample16']/16000)
                if self.statistics is not None:
                    self.statistics.observe(row['score'], row['compute_seconds'])
                self.completed_count += 1
                self.completed_rows.append(row)
                self.event_sink(row)  # Bounded IPC; no per-result stdout blocking.
        except BaseException as exc:
            self.fail(repr(exc))

    def finish(self, capture_pass):
        if not capture_pass:
            self.fail('CAPTURE_FAILED_IDENTITIES_INVALID')
        self.input_done.set()
        for thread in self.threads:
            thread.join(timeout=30)
        if any(t.is_alive() for t in self.threads):
            self.fail('SPEAKER_WORKER_SHUTDOWN_TIMEOUT')
        if capture_pass and not self.error and self.front_blocks*1536+self.partial_samples != self.accepted*512:
            self.fail('SPEAKER_INPUT_ACCOUNTING')
        self.stop.set()
        return dict(status='FAIL' if self.error else 'PASS', error=self.error, input_packets=self.accepted,
                    generated=self.mail.generated, replaced=self.mail.replaced, consumed=self.completed_count,
                    results=list(self.completed_rows), retained_result_limit=32, max_front_lag_seconds=self.max_lag,
                    statistics=self.statistics.snapshot() if self.statistics is not None else dict(enabled=False),
                    policy=POLICY, current_identity='insufficient', reason='session_ended',
                    recognition_qualified=False, model_selection='cp1_vf1')
