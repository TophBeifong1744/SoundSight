"""Strict explicit research configuration and synthetic timing contracts."""
from numbers import Integral

PROFILE = "soundsight-fixed4-dual-domain-research-v1"
PAIRS = ("01", "02", "03", "12", "13", "23")
EXTERNAL = ("transport", "frame_domain", "binding") + tuple(
    f"{domain}_{node}_{ch}" for domain in ("gate", "doa")
    for node in ("fft", "fixed4") for ch in range(4)) + tuple(f"ifft_{pair}" for pair in PAIRS)


def integer(value, label, lo=0, hi=None):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < lo or (hi is not None and value > hi):
        raise ValueError("CONFIG_INCOMPLETE_OR_INVALID: " + label)
    return int(value)


def required(obj, key, parent="config"):
    if not isinstance(obj, dict) or key not in obj:
        raise ValueError("CONFIG_INCOMPLETE: " + parent + "." + key)
    return obj[key]


def validate_config(config, bindings):
    if required(config, "scope") != "RESEARCH_ONLY" or required(config, "profile_id") != PROFILE:
        raise ValueError("UNSUPPORTED_CONFIG: profile")
    if required(config, "source_manifest_sha256") != bindings.identity["source_manifest_sha256"]:
        raise ValueError("SOURCE_MANIFEST_CONFIG_MISMATCH")
    if required(config, "table_manifest_sha256") != bindings.identity["table_manifest_sha256"]:
        raise ValueError("TABLE_MANIFEST_CONFIG_MISMATCH")
    if (required(config, "sample_rate_hz") != 48000 or required(config, "frame_length") != 1024
            or required(config, "hop") != 512 or required(config, "backend") != "portable_q30_frozen"):
        raise ValueError("UNSUPPORTED_CONFIG: sampling_or_backend")
    geometry = required(config, "geometry")
    if (required(geometry, "positions_mm", "geometry") != [[0, 0], [40, 0], [40, 40], [0, 40]]
            or required(geometry, "sound_speed_m_s", "geometry") != 343
            or required(geometry, "correction_policy", "geometry") != "UNAPPLIED_CANDIDATE"
            or required(geometry, "basis", "geometry") != "CANDIDATE_NOT_MEASURED"):
        raise ValueError("UNSUPPORTED_CONFIG: geometry_or_correction")
    activity = required(config, "activity")
    policy = {"on_power_ratio": 4, "off_power_ratio": 2,
              "attack_frames": 3, "release_frames": 3, "minimum_active_channels": 3}
    for key, value in policy.items():
        if integer(required(activity, key, "activity"), key) != value:
            raise ValueError("UNSUPPORTED_CONFIG: activity." + key)
    noise = required(activity, "noise_power_u64", "activity")
    if not isinstance(noise, list) or len(noise) != 4:
        raise ValueError("CONFIG_INCOMPLETE: activity.noise_power_u64")
    activity["noise_power_u64"] = [integer(v, "noise", 0, (1 << 64) - 1) for v in noise]
    integer(required(activity, "band_rms_floor_codes", "activity"), "floor", 0, (1 << 32) - 1)
    if required(activity, "reference_sha256", "activity") in ("", None):
        raise ValueError("CONFIG_INCOMPLETE: activity.reference_sha256")
    if (required(activity, "initial_state", "activity") != "INACTIVE"
            or required(activity, "invalid_policy", "activity") != "RESET_ACTIVITY_AND_TRACKER"):
        raise ValueError("UNSUPPORTED_CONFIG: activity_state")
    tracker = required(config, "tracker")
    bounds = {"half_angle_q8": (1, 90 * 256 - 1), "acquire_frames": (1, 1000000),
              "acquire_spread_q8": (0, 180 * 256), "track_step_q8": (0, 180 * 256),
              "hold_samples": (0, (1 << 63) - 1), "max_gap_samples": (1, (1 << 63) - 1)}
    for key, (lo, hi) in bounds.items():
        integer(required(tracker, key, "tracker"), key, lo, hi)
    if (tracker["acquire_spread_q8"] > 2 * tracker["half_angle_q8"]
            or tracker["track_step_q8"] > 2 * tracker["half_angle_q8"]):
        raise ValueError("UNSUPPORTED_CONFIG: tracker_sector")
    if required(tracker, "time_domain", "tracker") != "SESSION_SAMPLE":
        raise ValueError("UNSUPPORTED_CONFIG: tracker_clock")
    if required(config, "audio_fade_samples") != 480:
        raise ValueError("UNSUPPORTED_CONFIG: fade")
    return config


def validate_time(schedule, planned_frames, sample_count):
    if required(schedule, "time_basis", "schedule") != "SYNTHETIC_TIME":
        raise ValueError("UNSUPPORTED_CONFIG: time_basis")
    for key in ("boot_id", "session_id", "interval_id"):
        value = required(schedule, key, "schedule")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("CONFIG_INCOMPLETE: schedule." + key)
    integer(required(schedule, "generation", "schedule"), "generation", 0, (1 << 63) - 1)
    first = integer(required(schedule, "first_sample_id", "schedule"), "first_sample_id", 0, (1 << 63) - 1)
    ttl = integer(required(schedule, "result_ttl_samples", "schedule"), "result_ttl_samples", 0, (1 << 63) - 1)
    if first + sample_count + 8 >= (1 << 63):
        raise ValueError("SESSION_SAMPLE_ID_OVERFLOW")
    rows = required(schedule, "frames", "schedule")
    if not isinstance(rows, list) or len(rows) != planned_frames:
        raise ValueError("CONFIG_INCOMPLETE: schedule.frames")
    last_available = None
    for i, row in enumerate(rows):
        if integer(required(row, "frame_index", "frame"), "frame_index") != i:
            raise ValueError("FRAME_IDENTITY_MISMATCH")
        visible = required(row, "external_visible_at", "frame")
        if not isinstance(visible, dict) or any(k not in EXTERNAL for k in visible):
            raise ValueError("UNSUPPORTED_CONFIG: external_status")
        for key, value in visible.items():
            integer(value, "external_visible_at." + key, first, (1 << 63) - 1)
        errors = required(row, "external_error_units", "frame")
        if not isinstance(errors, list) or len(errors) != len(set(errors)) or any(k not in EXTERNAL for k in errors):
            raise ValueError("UNSUPPORTED_CONFIG: external_error_units")
        available = integer(required(row, "available", "frame"), "available", 0, (1 << 63) - 1)
        commit = integer(required(row, "commit_now", "frame"), "commit_now", 0, (1 << 63) - 1)
        take = integer(required(row, "take_now", "frame"), "take_now", 0, (1 << 63) - 1)
        audio = required(row, "audio_valid_through_emit", "frame")
        if audio is not None:
            integer(audio, "audio_valid_through_emit", 0, (1 << 63) - 1)
        if last_available is not None and available <= last_available:
            raise ValueError("NONMONOTONIC_OR_SAME_TICK_FRAME_SCHEDULE")
        last_id = first + i * 512 + 1023
        if (last_id >= (1 << 63) or last_id >= first + sample_count
                or available < last_id or available > commit or commit > take
                or take >= first + sample_count + 8):
            raise ValueError("TIME_ORDER_OR_RECORD_COVERAGE")
        if any(value < last_id for value in visible.values()):
            raise ValueError("EXTERNAL_COMPLETION_BEFORE_FRAME_END")
        last_available = available
        if i and take <= rows[i - 1]["take_now"]:
            raise ValueError("NONMONOTONIC_TAKE_SCHEDULE")
    fatal = schedule.get("fatal_emit")
    if fatal is not None:
        integer(fatal, "fatal_emit", first, first + sample_count + 8)
    stop = schedule.get("stop_emit")
    if stop is not None:
        integer(stop, "stop_emit", first, first + sample_count + 8)
    return first, ttl
