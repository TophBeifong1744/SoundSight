"""Experimental delayed speaker permission; no cryptography and no hardware IO.

Permission age starts at inference completion, never at message reception.
Speech pauses do not revoke a pass. Only a new passing result refreshes its TTL.
Audio-session identity, invalid data and explicit STOP remain fail-closed.
"""
import json
import math
from pathlib import Path
import time

CONFIG_NAME = 'speaker-follow.local.json'
DEFAULT_TTL = 3.0
POLICY = 'score_ttl_v2'


def settings(threshold=None, ttl=DEFAULT_TTL):
    if threshold is not None and (type(threshold) not in (int, float) or
            not math.isfinite(threshold) or not -1 <= threshold <= 1):
        raise ValueError('Speaker threshold must be a finite cosine score in [-1,1] or null')
    if type(ttl) not in (int, float) or not math.isfinite(ttl) or not .1 <= ttl <= 30:
        raise ValueError('Speaker permit seconds must be 0.1..30')
    return dict(schema=1, threshold=threshold, permit_seconds=float(ttl),
                policy=POLICY, recognition_qualified=False)


def load_settings(root):
    path = Path(root)/CONFIG_NAME
    if not path.exists():
        return settings()  # Absence is deliberately NOT the trial 0.65 threshold.
    value = json.loads(path.read_text(encoding='utf-8'))
    if set(value) != set(settings()) or value['schema'] != 1 or value['policy'] not in ('delayed_permission_v1', POLICY) or value['recognition_qualified'] is not False:
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
        self.display_result = None
        self.expires_at = 0.
        self.last_completed = -1.
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
        """Volume affects direction/motion separately, never the speaker TTL."""
        pass

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
            # Diagnostic only: silence, pauses and segment changes cannot shorten
            # an already granted score TTL. Worker/capture failures still STOP.
            self.voice_epoch = ve
            self.voice_active = bool(message['active'])
            self.voice_at = message['at']
        elif kind == 'result':
            self.results += 1
            self.result = dict(message)
            self._remember_score(message.get('display_result', message), now)
            self.score = message.get('score')
            completed = message['completed_at']
            if type(completed) not in (int, float) or not math.isfinite(completed) or completed > now or completed <= self.last_completed:
                self.revoke('INVALID_RESULT_TIME')
                return
            self.last_completed = completed
            if not message.get('usable'):
                # No score (e.g. insufficient speech) is not a new passing result.
                # It neither extends nor cancels the previous permit.
                if not self.allowed():
                    self.reason = str(message.get('reason', 'UNUSABLE_RESULT')).upper()
            elif self.config['threshold'] is None:
                self.revoke('UNCONFIGURED')
            elif type(self.score) not in (int, float) or not math.isfinite(self.score) or not -1 <= self.score <= 1:
                self.revoke('INVALID_SCORE')
            elif self.score < self.config['threshold']:
                if not self.allowed():
                    self.reason = 'SPEAKER_REJECTED'
            elif now >= completed+self.config['permit_seconds']:
                self.revoke('EXPIRED')
            else:
                self.expires_at = completed+self.config['permit_seconds']
                self.reason = 'TRIAL_SPEAKER_PASS'
        else:
            raise ValueError('Unknown speaker event')

    def _remember_score(self, result, now):
        """Retain a diagnostic score without granting or extending permission."""
        if not isinstance(result, dict):
            return
        score, completed = result.get('score'), result.get('completed_at')
        if (result.get('epoch') != self.epoch or result.get('kind') != 'result' or
                type(score) not in (int, float) or not math.isfinite(score) or not -1 <= score <= 1 or
                type(completed) not in (int, float) or not math.isfinite(completed) or not 0 <= completed <= now):
            return
        if self.display_result is not None and completed <= self.display_result['completed_at']:
            return
        self.display_result = dict(score=score, completed_at=completed,
                                   usable=bool(result.get('usable')),
                                   reason=str(result.get('reason', 'UNKNOWN')).upper())

    def allowed(self):
        now = self.clock()
        if self.expires_at and now >= self.expires_at:
            self.revoke('EXPIRED')
        return bool(self.expires_at and self.config['threshold'] is not None)

    def snapshot(self):
        permit = self.allowed()
        return dict(policy=POLICY, permit=permit, reason=self.reason, score=self.score,
                    display_score=None if self.display_result is None else self.display_result['score'],
                    display_score_age_seconds=None if self.display_result is None else max(0., self.clock()-self.display_result['completed_at']),
                    display_result=self.display_result,
                    threshold=self.config['threshold'], permit_seconds=self.config['permit_seconds'],
                    remaining_seconds=max(0., self.expires_at-self.clock()), epoch=self.epoch,
                    voice_epoch=self.voice_epoch, results=self.results, revocations=self.revocations,
                    latest_result=self.result, recognition_qualified=False,
                    meaning='Recent target score permits CURRENT sound direction; not same-person association')
