"""Run a deterministic in-memory DMA experiment; NEVER accesses hardware."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from dma_session import DmaSession, TransferSpec


class MockClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class MockBuffer:
    def __init__(self, backend: Any, role: str, size: int, address: int, coherent: bool) -> None:
        self.backend, self.role = backend, role
        self.nbytes, self.device_address, self.coherent = size, address, coherent
        self.cpu = bytearray(size)
        self.device = self.cpu if coherent else bytearray(size)
        self.dirty = False
        self.released = False
        self.release_attempts = 0
        self.invalidations = 0

    def idle_cpu(self) -> None:
        if self.released or self.backend.active:
            raise RuntimeError("CPU access/release while freed or DMA owns buffers")

    def write_bytes(self, data: bytes) -> None:
        self.idle_cpu()
        self.backend.trace.append(self.role + ".write")
        self.cpu[:] = data
        self.dirty = not self.coherent

    def flush(self) -> None:
        self.idle_cpu()
        self.backend.trace.append(self.role + ".flush")
        if self.role + "-flush" in self.backend.faults:
            raise RuntimeError("injected flush failure")
        if self.role + "-flush-noop" not in self.backend.faults:
            self.device[:] = self.cpu
            self.dirty = False

    def invalidate(self) -> None:
        self.idle_cpu()
        self.invalidations += 1
        self.backend.trace.append(self.role + ".invalidate")
        if "rx-invalidate" in self.backend.faults and self.invalidations == 2:
            raise RuntimeError("injected post-DMA invalidate failure")
        if "rx-invalidate-noop" not in self.backend.faults:
            self.cpu[:] = self.device
            self.dirty = False

    def read_bytes(self, count: int) -> bytes:
        self.idle_cpu()
        self.backend.trace.append(self.role + ".read")
        return bytes(self.cpu[:count])

    def release(self) -> None:
        self.release_attempts += 1
        self.idle_cpu()
        self.backend.trace.append(self.role + ".release")
        if self.role + "-release" in self.backend.faults:
            raise RuntimeError("injected uncertain release failure")
        self.released = True


class MockDma:
    evidence_level = "mock"

    def __init__(self, *, mode: str, capture: bytes, alignment: int,
                 faults: set[str] | None = None, coherent: bool = False) -> None:
        self.mode, self.capture, self.alignment = mode, capture, alignment
        self.faults = set(faults or ())
        self.coherent = coherent
        self.trace: list[str] = []
        self.allocations: list[MockBuffer] = []
        self.active = False
        self.transaction_id = 0
        self.polls = 0
        self.aborting = False
        self.actual_bytes = None
        self.complete = False
        self.tx = self.rx = None

    def allocate(self, role: str, length: int) -> MockBuffer:
        self.trace.append(role + ".allocate")
        if role + "-allocate" in self.faults:
            raise MemoryError("injected allocation failure")
        # Synthesized addresses only; never physical memory allocations.
        stride = ((length + self.alignment - 1) // self.alignment + 1) * self.alignment
        address = stride * (len(self.allocations) + 1)
        if "misaligned" in self.faults:
            address += 1
        buffer = MockBuffer(self, role, length, address, self.coherent)
        self.allocations.append(buffer)
        return buffer

    def arm_receive(self, buffer: MockBuffer, length: int, transaction_id: int) -> None:
        self.trace.append("rx.arm")
        self.rx, self.tx = buffer, None
        self.transaction_id, self.polls = transaction_id, 0
        self.actual_bytes, self.complete, self.aborting = None, False, False
        self.active = True
        if "rx-arm-after" in self.faults:
            raise RuntimeError("RX started before submission raised")
        if "interrupt" in self.faults:
            raise KeyboardInterrupt("injected cancellation after RX start")

    def arm_send(self, buffer: MockBuffer, length: int, transaction_id: int) -> None:
        self.trace.append("tx.arm")
        self.tx = buffer
        if "tx-arm-after" in self.faults:
            raise RuntimeError("TX submission raised after RX started")

    def snapshot(self) -> dict[str, Any]:
        self.trace.append("snapshot")
        if "status-read" in self.faults:
            raise OSError("injected unreadable DMA status")
        self.polls += 1
        error = "injected DMA fault" if "dma-error" in self.faults else None
        if self.aborting:
            if "abort-timeout" not in self.faults:
                self.active = False
        elif self.active and self.polls >= 2 and "timeout" not in self.faults and not error:
            data = self.capture if self.mode == "receive" else bytes(self.tx.device)
            self.actual_bytes = len(data) - 1 if "short-output" in self.faults else len(data)
            data = data[:self.actual_bytes]
            if "corrupt-output" in self.faults:
                data = bytes([data[0] ^ 1]) + data[1:]
            # Simulate dirty RX cache eviction overwriting device output.
            stale_rx = bytes(self.rx.cpu) if self.rx.dirty else None
            self.rx.device[:len(data)] = data
            if stale_rx is not None:
                self.rx.device[:] = stale_rx
            self.active = False
            self.complete = True
        state = {
            "transaction_id": self.transaction_id - (1 if "stale-status" in self.faults else 0),
            "rx_completed": self.complete,
            "tx_completed": self.complete and self.mode == "loopback",
            "quiescent": not self.active,
            "actual_bytes": self.actual_bytes,
            "error": error,
            "raw_status": {"simulated_poll": self.polls, "simulated_active": self.active},
        }
        if "missing-status" in self.faults:
            del state["error"]
        return state

    def request_abort(self) -> None:
        self.trace.append("abort.request")
        self.aborting = True
        if "abort-raises" in self.faults:
            raise RuntimeError("injected abort request failure")


def pattern_bytes(kind: str, length: int) -> bytes:
    if type(length) is not int or length <= 0:
        raise ValueError("pattern length must be positive")
    if kind == "counter8":
        return bytes(index & 255 for index in range(length))
    if kind == "alternating":
        return bytes(0xA5 if index % 2 == 0 else 0x5A for index in range(length))
    if kind == "xorshift32":
        state, output = 0x6D2B79F5, bytearray()
        while len(output) < length:
            state ^= (state << 13) & 0xFFFFFFFF
            state ^= state >> 17
            state ^= (state << 5) & 0xFFFFFFFF
            output.extend((state & 0xFFFFFFFF).to_bytes(4, "little"))
        return bytes(output[:length])
    raise ValueError("unknown pattern")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True, help="offline lifecycle contract, not a board profile")
    parser.add_argument("--fault", action="append", default=[], choices=(
        "rx-allocate", "rx-arm-after", "tx-arm-after", "timeout", "dma-error", "status-read",
        "missing-status", "stale-status", "short-output", "corrupt-output", "rx-flush", "tx-flush",
        "rx-invalidate", "tx-flush-noop", "rx-invalidate-noop", "rx-release", "interrupt",
        "abort-timeout", "abort-raises", "misaligned"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error("output exists; use a fresh filename to preserve evidence")
    contract_bytes = args.contract.read_bytes()
    contract = json.loads(contract_bytes.decode("utf-8"))
    if (not isinstance(contract, dict) or type(contract.get("schema_version")) is not int
            or contract["schema_version"] != 1):
        parser.error("lifecycle contract requires schema_version 1")
    if type(contract.get("mock_coherent", False)) is not bool:
        parser.error("mock_coherent must be boolean")
    spec = TransferSpec(**contract["transfer"])
    spec.validate()
    expected = pattern_bytes(contract["pattern"], spec.length_bytes)
    dma = MockDma(mode=spec.mode, capture=expected, alignment=spec.buffer_alignment_bytes,
                  coherent=contract.get("mock_coherent", False), faults=set(args.fault))
    session = DmaSession(dma, clock=MockClock())
    report = session.run(spec, expected=expected, tx_data=expected if spec.mode == "loopback" else None)
    report.update(adapter_trace=dma.trace, contract_sha256=hashlib.sha256(contract_bytes).hexdigest(),
                  faults=args.fault, timing_source="synthetic mock clock; not measured performance")
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    print(encoded, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
