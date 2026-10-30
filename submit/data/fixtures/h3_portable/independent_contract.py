"""B14-05/P17 instance and event contract for the frozen seven-frame scene.

This module imports no product code and never reads DUT expected/units/events to
construct its expectations. Frame 0/1 have closed gates; 2..6 have active gates.
The active lag state is derived from the independent inverse-FFT reference.
"""

from independent_reference import independent_lag


PAIRS = ("01", "02", "03", "12", "13", "23")
PAIR_LENGTH_SQ = (1, 2, 1, 1, 2, 1)
DOMAINS = ("gate", "doa")
EXTERNAL_BASE = ("transport", "frame_domain", "binding") + tuple(
    f"{domain}_{node}_{channel}"
    for domain in DOMAINS for node in ("fft", "fixed4") for channel in range(4))


def all_units():
    names = ["transport", "frame_domain", "binding"]
    for channel in range(4):
        names.extend((f"mean_{channel}", f"gate_window_{channel}",
                      f"doa_window_{channel}"))
    for domain in DOMAINS:
        for channel in range(4):
            names.extend((f"{domain}_fft_{channel}", f"{domain}_fixed4_{channel}"))
    names.append("gate_state")
    for pair in PAIRS:
        names.extend((f"phat_{pair}", f"ifft_{pair}", f"lag_{pair}"))
    names.extend(("doa", "tracker", "result_binding"))
    assert len(names) == 53 and len(set(names)) == 53
    return tuple(names)


ALL_UNITS = all_units()


def active(frame):
    if type(frame) is not int or frame not in range(7):
        raise ValueError("SCENE_FRAME_OUTSIDE_0_TO_6")
    return frame >= 2


def external_units(frame):
    return EXTERNAL_BASE + (tuple(f"ifft_{pair}" for pair in PAIRS) if active(frame) else ())


def state_map(frame, independent_arrays):
    """Expected final per-instance status, including independent lag rejection."""
    opened = active(frame)
    states = {name: "OK" for name in ALL_UNITS}
    if not opened:
        for pair in PAIRS:
            for kind in ("phat", "ifft", "lag"):
                states[f"{kind}_{pair}"] = "SKIPPED_GATE_CLOSED"
        states["doa"] = "SKIPPED_GATE_CLOSED"
    else:
        inverse = independent_arrays[f"frame{frame:04d}_ifft_real"]
        for pair_index, pair in enumerate(PAIRS):
            lag = independent_lag(inverse[pair_index], PAIR_LENGTH_SQ[pair_index])
            if not lag["valid"]:
                states[f"lag_{pair}"] = "ALGORITHM_REJECTED:" + lag["reason"]
    fresh = frame >= 3
    states["tracker"] = "OK_FRESH" if fresh else "OK_NO_FRESH"
    states["result_binding"] = "BOUND_FRESH" if fresh else "BOUND_NO_FRESH"
    assert set(states) == set(ALL_UNITS)
    return states


def event_map(schedule, independent_arrays):
    """Expected one event per (frame,unit), with declared external time.

    External completion, tracker, result_binding and take occupy distinct
    categories. The schedule supplies times, while this contract fixes the
    required unit set and success/result semantics for the normal scene.
    """
    if (not isinstance(schedule, dict) or len(schedule.get("frames", [])) != 7):
        raise ValueError("SCENE_SCHEDULE_REQUIRES_SEVEN_FRAMES")
    expected = {}
    for frame, timing in enumerate(schedule["frames"]):
        external = external_units(frame)
        visible = timing["external_visible_at"]
        if set(visible) != set(external) or timing["external_error_units"]:
            raise ValueError("SCENE_EXTERNAL_SCHEDULE_MISMATCH:" + str(frame))
        for unit in external:
            expected[(frame, unit)] = (visible[unit], "OK")
        states = state_map(frame, independent_arrays)
        expected[(frame, "tracker")] = (timing["available"], states["tracker"])
        expected[(frame, "result_binding")] = (timing["commit_now"], states["result_binding"])
        expected[(frame, "take")] = (timing["take_now"],
                                     "TAKEN_FRESH" if frame >= 3 else "TAKEN_NO_FRESH")
    return expected
