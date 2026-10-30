"""Independent B14-05/P17 synthetic-time cancellation oracle.

Inputs are the frozen scene schedule and the pre-existing integer reference.
No product module or DUT output is imported to form expectations.
"""

from independent_contract import ALL_UNITS, external_units, state_map


def expected(schedule, arrays):
    frames = schedule["frames"]
    edge_values = [schedule.get("fatal_emit"), schedule.get("stop_emit")]
    edge = min(x for x in edge_values if x is not None) if any(x is not None for x in edge_values) else None
    reason = ("FATAL" if schedule.get("fatal_emit") == edge else "STOP") if edge is not None else None
    first = schedule["first_sample_id"]
    expected_set = set(ALL_UNITS)
    events, observations, terminations, stages = [], [], [], []
    queue = []
    for frame, timing in enumerate(frames):
        issued = set(external_units(frame))
        visible = timing["external_visible_at"]
        if set(visible) != issued:
            raise ValueError(f"FIXTURE_EXTERNAL_SET:{frame}")
        errors = set(timing["external_error_units"])
        if not errors <= issued:
            raise ValueError(f"FIXTURE_ERROR_SET:{frame}")
        available = timing["available"]
        compute = edge is None or available < edge or any(t <= edge for t in visible.values())
        for unit in sorted(issued):
            if compute:
                queue.append((visible[unit], 0, frame, unit))
        if compute:
            queue.extend(((available, 1, frame, "numeric"),
                          (available, 2, frame, "tracker"),
                          (timing["commit_now"], 3, frame, "result_binding"),
                          (timing["take_now"], 4, frame, "take")))

    for at, _priority, frame, unit in sorted(queue):
        timing = frames[frame]
        issued = set(external_units(frame))
        errors = set(timing["external_error_units"])
        if edge is not None and at >= edge:
            if at == edge:
                observations.append({"frame": frame, "unit": unit,
                    "observed_at": at, "time_basis": "SYNTHETIC_TIME",
                    "result": ("EXTERNAL_ERROR" if unit in errors else "OK")
                    if unit in issued else "NOT_PUBLISHED_AT_CANCEL"})
            continue
        status = state_map(frame, arrays)
        if unit in issued:
            value = "EXTERNAL_ERROR" if unit in errors else status[unit]
        elif unit == "tracker":
            value = "NUMERIC_OR_PROTOCOL_INVALID_RESET" if errors else status[unit]
        elif unit == "result_binding":
            value = "INVALID_NO_FRESH" if errors else status[unit]
        elif unit == "take":
            value = "REJECTED_NUMERIC_OR_PROTOCOL_INVALID" if errors else (
                "TAKEN_FRESH" if frame >= 3 else "TAKEN_NO_FRESH")
        else:
            continue
        events.append({"frame": frame, "unit": unit, "visible_at": at, "result": value})

    for frame, timing in enumerate(frames):
        issued = set(external_units(frame))
        errors = set(timing["external_error_units"])
        available, commit, take = (timing[k] for k in ("available", "commit_now", "take_now"))
        normal = state_map(frame, arrays)
        final = {}
        for unit in ALL_UNITS:
            at = timing["external_visible_at"][unit] if unit in issued else (
                commit if unit == "result_binding" else available)
            if edge is None or at < edge:
                final[unit] = "EXTERNAL_ERROR" if unit in errors else normal[unit]
        remainder = expected_set - set(final)
        cancelled = edge is not None and edge <= take
        if not cancelled and remainder:
            raise ValueError(f"ORACLE_INCOMPLETE_NONCANCELLED:{frame}")
        identity = {"boot": schedule["boot_id"], "session": schedule["session_id"],
            "interval": schedule["interval_id"], "frame": frame,
            "generation": schedule["generation"], "last_id": first + frame * 512 + 1023}
        committed = commit < edge if edge is not None else True
        taken = take < edge if edge is not None else True
        if errors and (edge is None or available < edge):
            committed = taken = False
        term_reason = (reason + ("_BEFORE_AVAILABLE" if edge <= available else
                       "_BEFORE_COMMIT" if edge <= commit else "_BEFORE_TAKE")) if cancelled else (
                       "TAKE_REJECTED_NUMERIC_OR_PROTOCOL_INVALID" if errors else "TAKE_COMPLETE")
        terminations.append({"identity": identity, "time_basis": "SYNTHETIC_TIME",
            "at": edge if cancelled else take, "reason": term_reason,
            "expected_units": list(ALL_UNITS), "final_before": final,
            "cancelled_units": sorted(remainder), "ever_committed": committed,
            "ever_taken": taken, "successful_commit_at": commit if committed else None,
            "successful_take_at": take if taken else None,
            "later_interval_end_at": edge if edge is not None and edge > take else None,
            "later_interval_end_reason": reason if edge is not None and edge > take else None,
            "prior_binding_retracted": False})
        stages.append({**final, **{unit: "CANCELLED_BY_TRANSACTION" for unit in remainder}})
    return {"edge": edge, "reason": reason, "events": events,
            "observations": observations, "terminations": terminations,
            "stages": stages}
