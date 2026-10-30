"""Experimental delayed speaker permission; no cryptography and no hardware IO.

Permission age starts at inference completion, never at message reception.
Audio/voice epochs revoke old decisions; an in-flight inference is not permission.
"""
import json
import math
from pathlib import Path
import time

CONFIG_NAME = 'speaker-follow.local.json'
DEFAULT_TTL = 3.0


def settings(threshold=None, ttl=DEFAULT_TTL):
    if threshold is not None and (type(threshold) not in (int, float) or
            not math.isfinite(threshold) or not -1 <= threshold <= 1):
        raise ValueError('Speaker threshold must be a finite cosine score in [-1,1] or null')
    if type(ttl) not in (int, float) or not math.isfinite(ttl) or not .1 <= ttl <= 30:
        raise ValueError('Speaker permit seconds must be 0.1..30')
    return dict(schema=1, threshold=threshold, permit_seconds=float(ttl),
                policy='delayed_permission_v1', recognition_qualified=False)


def load_settings(root):
    path = Path(root)/CONFIG_NAME
    if not path.exists():
        return settings()  # Absence is deliberately NOT the trial 0.65 threshold.
    value = json.loads(path.read_text(encoding='utf-8'))
    if set(value) != set(settings()) or value['schema'] != 1 or value['policy'] != 'delayed_permission_v1' or value['recognition_qualified'] is not False:
        raise ValueError('Unknown speaker-follow configuration')
    return settings(value['threshold'], value['permit_seconds'])


class SpeakerPermission:
    """Only the capture owner updates this state and submits servo commands."""
    def __init__(self, config, clock=time.monotonic):
        self.config = settings(config['threshold'], config['permit_seconds'])
        self.clock = clock
        self.epoch = None
        self.voice_epoch = -1
        self.voice_active = False
        self.voice_at = None
        self.score = self.result = None
        self.expires_at = 0.
        self.last_completed = -1.
        self.quiet_until_sample16 = 0
        self.reason = 'UNCONFIGURED' if self.config['threshold'] is None else 'WAITING_FOR_SPEECH'
        self.revocations = self.results = 0

    def start(self, epoch):
        if type(epoch) is not int or not 1 <= epoch <= 0xffffffff or self.epoch is not None:
            raise ValueError('One nonzero audio epoch per permission session')
        self.epoch = epoch

    def revoke(self, reason):
        if self.expires_at:
            self.revocations += 1
        self.expires_at = 0.
        self.reason = reason

    def quiet(self, sample_end16):
        """Volume silence also prevents an older in-flight result re-enabling motion."""
        self.quiet_until_sample16 = max(self.quiet_until_sample16, sample_end16)
        self.revoke('LOW_VOLUME')

    def event(self, message):
        now = self.clock()
        if message.get('epoch') != self.epoch or self.epoch is None:
            self.revoke('WRONG_AUDIO_SESSION')
            return
        kind = message.get('kind')
        ve = message.get('voice_epoch')
        if type(ve) is not int or ve < 0:
            raise ValueError('Invalid voice epoch')
        if kind == 'voice':
            at = message['at']
            if type(at) not in (int, float) or not math.isfinite(at) or at > now or now-at > .5:
                self.revoke('STALE_FRONTEND')
                return
            if ve < self.voice_epoch or self.voice_at is not None and at < self.voice_at:
                self.revoke('OUT_OF_ORDER_VOICE')
                return
            if ve != self.voice_epoch or not message['active']:
                self.revoke('NEW_SPEECH' if message['active'] else 'SILENCE')
            self.voice_epoch, self.voice_active, self.voice_at = ve, bool(message['active']), at
        elif kind == 'result':
            self.results += 1
            self.result = dict(message)
            self.score = message.get('score')
            completed = message['completed_at']
            if type(completed) not in (int, float) or not math.isfinite(completed) or completed > now or completed <= self.last_completed:
                self.revoke('INVALID_RESULT_TIME')
                return
            self.last_completed = completed
            if (ve != self.voice_epoch or not self.voice_active or
                    self.voice_at is None or now-self.voice_at > .5):
                self.revoke('OLD_OR_SILENT_SPEECH')
            elif message.get('start_sample16', -1) < self.quiet_until_sample16:
                self.revoke('RESULT_PRECEDES_QUIET')
            elif not message.get('usable'):
                self.revoke(str(message.get('reason', 'UNUSABLE_RESULT')).upper())
            elif self.config['threshold'] is None:
                self.revoke('UNCONFIGURED')
            elif type(self.score) not in (int, float) or not math.isfinite(self.score) or not -1 <= self.score <= 1:
                self.revoke('INVALID_SCORE')
            elif self.score < self.config['threshold']:
                self.revoke('SPEAKER_REJECTED')
            elif now >= completed+self.config['permit_seconds']:
                self.revoke('EXPIRED')
            else:
                self.expires_at = completed+self.config['permit_seconds']
                self.reason = 'TRIAL_SPEAKER_PASS'
        else:
            raise ValueError('Unknown speaker event')

    def allowed(self):
        now = self.clock()
        if self.voice_at is not None and now-self.voice_at > .5:
            self.revoke('FRONTEND_LOST')
        if self.expires_at and now >= self.expires_at:
            self.revoke('EXPIRED')
        return bool(self.expires_at and self.voice_active and self.config['threshold'] is not None)

    def snapshot(self):
        permit = self.allowed()
        return dict(permit=permit, reason=self.reason, score=self.score,
                    threshold=self.config['threshold'], permit_seconds=self.config['permit_seconds'],
                    remaining_seconds=max(0., self.expires_at-self.clock()), epoch=self.epoch,
                    voice_epoch=self.voice_epoch, results=self.results, revocations=self.revocations,
                    latest_result=self.result, recognition_qualified=False,
                    meaning='Recent target score permits CURRENT sound direction; not same-person association')
