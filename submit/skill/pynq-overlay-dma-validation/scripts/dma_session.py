"""Offline DMA lifecycle core. No PYNQ, MMIO, reset API or board adapter.

Adapters used here are mock instruments only. A future hardware binding must
separately qualify nonblocking status/abort and process-lifetime ownership.
"""
from __future__ import annotations

import hashlib
import math
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TransferSpec:
    mode: str
    length_bytes: int
    buffer_alignment_bytes: int
    length_granularity_bytes: int
    max_transfer_bytes: int
    timeout_seconds: float
    abort_timeout_seconds: float
    tx_policy: str = "flush"
    rx_policy: str = "invalidate"
    allow_abort: bool = False
    poll_interval_seconds: float = 0.001
    max_polls: int = 10000

    def validate(self) -> None:
        if self.mode not in ("loopback", "receive"):
            raise ValueError("mode must be loopback or receive; SG/cyclic not supported")
        for name in ("length_bytes", "buffer_alignment_bytes", "length_granularity_bytes",
                     "max_transfer_bytes", "max_polls"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(name + " must be a positive integer")
        for name in ("timeout_seconds", "abort_timeout_seconds", "poll_interval_seconds"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 60:
                raise ValueError(name + " must be finite and in (0, 60]")
        if type(self.allow_abort) is not bool:
            raise ValueError("allow_abort must be boolean")
        if self.length_bytes > self.max_transfer_bytes or self.length_bytes % self.length_granularity_bytes:
            raise ValueError("length violates maximum or transfer granularity")
        if self.tx_policy not in ("flush", "coherent") or self.rx_policy not in ("invalidate", "coherent"):
            raise ValueError("unknown cache policy")


class DmaSession:
    """Own allocations across failures; never recycle a failed session.

    `retained_buffers` deliberately holds strong references. This models the
    ownership obligation, not a guarantee across Python/process exit on hardware.
    """
    def __init__(self, adapter: Any, *, clock: Any = None) -> None:
        if getattr(adapter, "evidence_level", None) != "mock":
            raise ValueError("OFFLINE_ONLY: this session accepts mock adapters only")
        self.adapter = adapter
        self.clock = clock or time
        self.retained_buffers: list[Any] = []
        self.blocked = False
        self.sequence = 0

    def run(self, spec: TransferSpec, *, expected: bytes, tx_data: bytes | None = None) -> dict[str, Any]:
        self.sequence += 1
        report: dict[str, Any] = {
            "schema_version": 1, "evidence_level": "mock", "board_execution": False,
            "transaction_id": self.sequence, "mode": spec.mode, "status": "FAIL",
            "requested_bytes": spec.length_bytes, "actual_bytes": None,
            "events": [], "errors": [], "snapshots": [], "mismatch_count": None,
            "first_mismatch": None, "transfer_elapsed_seconds": None,
            "throughput_bytes_per_second": None, "buffer_disposition": "none",
            "tlast_observed": None,
        }
        if self.blocked:
            report["errors"].append("SESSION_BLOCKED: previous failure requires external review")
            report["buffer_disposition"] = "retained" if self.retained_buffers else "none"
            report["session_blocked"] = True
            return report
        buffers: list[Any] = []
        uncertain = False
        stage = "validate"
        start = None

        def event(value: str) -> None:
            report["events"].append(value)

        def snapshot(label: str) -> dict[str, Any]:
            state = deepcopy(self.adapter.snapshot())
            # Record raw state before interpreting it; no default-false flags.
            report["snapshots"].append({"phase": label, "state": state})
            if (not isinstance(state, dict) or type(state.get("transaction_id")) is not int
                    or state["transaction_id"] != self.sequence):
                raise RuntimeError("missing/stale transaction status")
            for key in ("rx_completed", "tx_completed", "quiescent"):
                if type(state.get(key)) is not bool:
                    raise RuntimeError("missing/invalid status flag: " + key)
            if "error" not in state or (state["error"] is not None and not isinstance(state["error"], str)):
                raise RuntimeError("missing/invalid error status")
            if not isinstance(state.get("raw_status"), dict):
                raise RuntimeError("raw status must be supplied by the adapter")
            return state

        def retain_all() -> None:
            self.retained_buffers.extend(buffers)
            report["buffer_disposition"] = "retained"
            event("buffers.retain")

        try:
            spec.validate()
            if type(expected) is not bytes or len(expected) != spec.length_bytes:
                raise ValueError("expected must be exact-length bytes")
            if spec.mode == "loopback":
                if type(tx_data) is not bytes or len(tx_data) != spec.length_bytes:
                    raise ValueError("loopback requires exact-length TX bytes")
            elif tx_data is not None:
                raise ValueError("receive-only mode must not submit TX")
            roles = ("tx", "rx") if spec.mode == "loopback" else ("rx",)
            by_role = {}
            for role in roles:
                stage = role + ".allocate"
                buffer = self.adapter.allocate(role, spec.length_bytes)
                # Own each allocation immediately, even if the next allocation fails.
                if any(buffer is previous for previous in buffers):
                    raise ValueError("allocator returned the same object twice")
                buffers.append(buffer)
                by_role[role] = buffer
                event(stage)
                if type(buffer.device_address) is not int or buffer.device_address < 0 or buffer.device_address % spec.buffer_alignment_bytes:
                    raise ValueError("allocated address violates alignment")
                if type(buffer.nbytes) is not int or buffer.nbytes < spec.length_bytes:
                    raise ValueError("undersized allocation")
                for previous in buffers[:-1]:
                    if max(previous.device_address, buffer.device_address) < min(
                            previous.device_address + previous.nbytes, buffer.device_address + buffer.nbytes):
                        raise ValueError("DMA buffer address ranges overlap")
                policy = spec.tx_policy if role == "tx" else spec.rx_policy
                if policy == "coherent" and buffer.coherent is not True:
                    raise ValueError("coherent policy lacks allocator confirmation")
                stage = role + ".fill"
                buffer.write_bytes(tx_data if role == "tx" else b"\xa5" * spec.length_bytes)
                event(stage)
                if policy != "coherent":
                    # RX initialization creates dirty CPU cache lines too.
                    stage = role + ".flush"
                    buffer.flush()
                    event(stage)
                    if role == "rx":
                        stage = "rx.invalidate_before"
                        buffer.invalidate()
                        event(stage)
            start = self.clock.monotonic()
            uncertain = True  # BEFORE a submission which may start and then raise.
            stage = "rx.arm"
            event(stage)
            self.adapter.arm_receive(by_role["rx"], spec.length_bytes, self.sequence)
            if spec.mode == "loopback":
                stage = "tx.arm"
                event(stage)
                self.adapter.arm_send(by_role["tx"], spec.length_bytes, self.sequence)
            stage = "poll"
            deadline = start + spec.timeout_seconds
            for _ in range(spec.max_polls):
                if self.clock.monotonic() >= deadline:
                    raise TimeoutError("transfer deadline exceeded")
                state = snapshot("transfer")
                if self.clock.monotonic() >= deadline:
                    raise TimeoutError("status arrived after deadline")
                if state["error"] is not None:
                    raise RuntimeError("DMA error: " + state["error"])
                complete = state["rx_completed"] and (spec.mode == "receive" or state["tx_completed"])
                if complete and state["quiescent"]:
                    uncertain = False
                    event("dma.quiescent")
                    break
                self.clock.sleep(spec.poll_interval_seconds)
            else:
                raise TimeoutError("transfer poll budget exhausted")
            elapsed = self.clock.monotonic() - start
            report["transfer_elapsed_seconds"] = elapsed
            actual = state.get("actual_bytes")
            report["actual_bytes"] = actual
            stage = "length"
            if type(actual) is not int or actual != spec.length_bytes:
                raise RuntimeError("received byte count differs from requested length")
            if spec.rx_policy != "coherent":
                stage = "rx.invalidate_after"
                by_role["rx"].invalidate()
                event(stage)
            stage = "compare"
            output = by_role["rx"].read_bytes(actual)
            event("rx.read")
            if type(output) is not bytes or len(output) != actual:
                raise RuntimeError("CPU capture length differs from DMA actual count")
            mismatches = [i for i, (a, b) in enumerate(zip(expected, output)) if a != b]
            report.update(expected_sha256=hashlib.sha256(expected).hexdigest(),
                          output_sha256=hashlib.sha256(output).hexdigest(),
                          mismatch_count=len(mismatches),
                          first_mismatch=mismatches[0] if mismatches else None)
            if mismatches:
                raise RuntimeError("golden mismatch")
            report["status"] = "PASS"
            report["throughput_bytes_per_second"] = actual / elapsed if elapsed > 0 else None
        except BaseException as exc:
            self.blocked = True
            report["errors"].append(f"{stage}: {type(exc).__name__}: {exc}")
            if uncertain:
                # Diagnostics must not mask the primary failure or skip recovery.
                try:
                    snapshot("before_abort")
                    event("status.before_abort")
                except BaseException as diag:
                    report["errors"].append(f"diagnostic: {type(diag).__name__}: {diag}")
                if spec.allow_abort:
                    event("abort.request")
                    deadline = self.clock.monotonic() + spec.abort_timeout_seconds
                    try:
                        self.adapter.request_abort()
                        for _ in range(spec.max_polls):
                            if self.clock.monotonic() >= deadline:
                                raise TimeoutError("abort deadline exceeded")
                            state = snapshot("abort")
                            if self.clock.monotonic() >= deadline:
                                raise TimeoutError("abort status arrived after deadline")
                            if state["quiescent"]:
                                uncertain = False
                                event("abort.quiescent")
                                break
                            self.clock.sleep(spec.poll_interval_seconds)
                        else:
                            raise TimeoutError("abort poll budget exhausted")
                    except BaseException as recovery:
                        report["errors"].append(f"abort: {type(recovery).__name__}: {recovery}")
                else:
                    event("abort.not_authorized")
        finally:
            if uncertain:
                retain_all()
            else:
                for buffer in buffers:
                    try:
                        buffer.release()
                        event(buffer.role + ".release")
                    except BaseException as cleanup:
                        # A failed release may already have freed memory: never retry.
                        self.retained_buffers.append(buffer)
                        self.blocked = True
                        report["status"] = "FAIL"
                        report["errors"].append(f"release: {type(cleanup).__name__}: {cleanup}")
                report["buffer_disposition"] = ("release_indeterminate" if self.retained_buffers
                                                  else "released" if buffers else "none")
        if report["status"] != "PASS":
            report["throughput_bytes_per_second"] = None
        report["session_blocked"] = self.blocked
        return report
