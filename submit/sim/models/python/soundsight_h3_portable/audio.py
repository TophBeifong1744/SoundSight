"""Three research lanes on one source-to-emit (+8) sample coordinate."""
import numpy as np


def _manual_lane(pcm, delays, dynamic):
    """Fixed-angle S5 interpolation; only real record boundaries are zero padded."""
    q = dynamic.Q
    count = pcm.shape[1]
    result = np.empty(count, dtype=np.int64)
    for n in range(count):
        acc = 0
        for ch, delay in enumerate(delays):
            left, fraction = divmod(n * q - delay, q)
            a = int(pcm[ch, left]) if 0 <= left < count else 0
            acc += a * (q - fraction)
            if fraction:
                b = int(pcm[ch, left + 1]) if 0 <= left + 1 < count else 0
                acc += b * fraction
        result[n] = dynamic.rne(acc, 4 * q)
    if np.any(result < -(1 << 23)) or np.any(result >= (1 << 23)):
        raise ValueError("MANUAL_S24_OVERFLOW")
    return result


def render_three_lanes(pcm, manual_angle_q8, controls, bindings, *, fatal_emit=None):
    """Controls use local physical emit time; fatal cancels before that emission."""
    x = np.asarray(pcm)
    if x.ndim != 2 or x.shape[0] != 4 or not np.issubdtype(x.dtype, np.integer):
        raise ValueError("FOUR_CHANNEL_PCM_REQUIRED")
    count = x.shape[1]
    manual_delays = bindings.delay_rom.lookup(manual_angle_q8)
    manual = _manual_lane(x, manual_delays, bindings.dynamic)
    stream = bindings.dynamic.DynamicDAS(fade_samples=480)
    by_emit = {}
    for row in controls:
        emit = row["emit"]
        if emit in by_emit or emit < 0 or emit >= count + 8:
            raise ValueError("DUPLICATE_OR_OUTSIDE_CONTROL")
        by_emit[emit] = row
    raw, trace = [], []
    stopped = None
    for t in range(count + 8):
        if fatal_emit is not None and t >= fatal_emit:
            stopped = t
            break
        control = by_emit.get(t)
        if control is not None:
            stream.control(state=control["state"], delays=control.get("delays"),
                           valid_through=control.get("valid_through"))
        if t < count:
            values, traces = stream.push(x[:, t:t + 1])
            raw.append(int(values[0]))
            trace.append(traces[0])
        else:
            # The leaf's final=True emits all eight at once. Emit individually
            # so a fatal edge in the tail cannot publish later samples.
            stream.input_end = count
            value, one_trace = stream._emit()
            raw.append(int(value))
            trace.append(one_trace)
    if stopped is None:
        stream.closed = True
    raw_array = np.asarray(raw, dtype=np.int64)
    end = min(count, max(0, len(raw) - 8))
    return {
        "single": x[0, :end].astype(np.int64).copy(),
        "manual": manual[:end].copy(),
        "automatic": raw_array[8:8 + end].copy(),
        "automatic_raw": raw_array,
        "trace": trace,
        "events": stream.events,
        "aborted_at_emit": stopped,
        "source_count": end,
        "stats": {"max_history": stream.max_history, "max_beams": stream.max_beams,
                  "saturations": stream.saturations},
    }
