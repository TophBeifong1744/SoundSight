"""Behavioral lifecycle tests using distinct CPU/device bytes, never a board."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from dma_session import DmaSession, TransferSpec
from simulate_dma import MockClock, MockDma, pattern_bytes


class DmaSessionTests(unittest.TestCase):
    def make(self, mode="loopback", faults=(), allow_abort=True, coherent=False, **changes):
        spec = TransferSpec(mode, 96, 64, 8, 4096, .02, .01,
                            allow_abort=allow_abort, max_polls=100)
        spec = replace(spec, **changes)
        expected = pattern_bytes("xorshift32", max(1, spec.length_bytes))
        dma = MockDma(mode=mode, capture=expected, alignment=64,
                      faults=set(faults), coherent=coherent)
        return spec, expected, dma, DmaSession(dma, clock=MockClock())

    def execute(self, setup):
        spec, expected, dma, session = setup
        return session.run(spec, expected=expected,
                           tx_data=expected if spec.mode == "loopback" else None)

    def assert_released(self, dma):
        self.assertFalse(dma.active)
        self.assertTrue(dma.allocations)
        for buffer in dma.allocations:
            self.assertTrue(buffer.released)
            self.assertEqual(buffer.release_attempts, 1)

    def test_success_cache_and_ownership_order(self):
        setup = self.make()
        report = self.execute(setup)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["actual_bytes"], 96)
        self.assertEqual(report["mismatch_count"], 0)
        trace = [x for x in setup[2].trace if not x.endswith(("allocate", "release"))]
        self.assertEqual(trace, ["tx.write", "tx.flush", "rx.write", "rx.flush",
                                "rx.invalidate", "rx.arm", "tx.arm", "snapshot", "snapshot",
                                "rx.invalidate", "rx.read"])
        self.assert_released(setup[2])

    def test_receive_only_never_allocates_or_submits_tx(self):
        setup = self.make(mode="receive")
        report = self.execute(setup)
        self.assertEqual(report["status"], "PASS")
        self.assertFalse(any(x.startswith("tx.") for x in setup[2].trace))
        self.assertIsNone(report["tlast_observed"])

    def test_repeated_success_rearms_fresh_transaction(self):
        spec, expected, dma, session = self.make()
        for sequence in range(1, 4):
            data = bytes(x ^ sequence for x in expected)
            report = session.run(spec, expected=data, tx_data=data)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["transaction_id"], sequence)
        self.assert_released(dma)

    def test_second_allocation_failure_releases_first(self):
        setup = self.make(faults={"rx-allocate"})
        report = self.execute(setup)
        self.assertEqual(report["status"], "FAIL")
        self.assertNotIn("rx.arm", setup[2].trace)
        self.assertEqual(len(setup[2].allocations), 1)
        self.assert_released(setup[2])

    def test_submission_can_start_then_raise_or_cancel(self):
        for fault in ("rx-arm-after", "tx-arm-after", "interrupt"):
            with self.subTest(fault=fault):
                setup = self.make(faults={fault})
                report = self.execute(setup)
                self.assertEqual(report["status"], "FAIL")
                events = report["events"]
                self.assertLess(events.index("status.before_abort"), events.index("abort.request"))
                self.assertLess(events.index("abort.quiescent"), events.index("rx.release"))
                self.assert_released(setup[2])

    def test_no_abort_authority_retains_and_blocks_next_run(self):
        setup = self.make(faults={"tx-arm-after"}, allow_abort=False)
        report = self.execute(setup)
        self.assertEqual(report["buffer_disposition"], "retained")
        self.assertTrue(setup[2].active)
        self.assertEqual(len(setup[3].retained_buffers), 2)
        self.assertTrue(all(x.release_attempts == 0 for x in setup[2].allocations))
        trace = list(setup[2].trace)
        setup[2].faults.clear()
        self.assertIn("SESSION_BLOCKED", self.execute(setup)["errors"][0])
        self.assertEqual(trace, setup[2].trace)

    def test_abort_timeout_or_exception_retains(self):
        for fault in ("abort-timeout", "abort-raises"):
            with self.subTest(fault=fault):
                setup = self.make(faults={"timeout", fault})
                report = self.execute(setup)
                self.assertEqual(report["buffer_disposition"], "retained")
                self.assertTrue(setup[2].active)
                self.assertTrue(all(x.release_attempts == 0 for x in setup[2].allocations))
                self.assertLessEqual(setup[3].clock.value, .032)

    def test_unreadable_status_does_not_mask_primary_error(self):
        setup = self.make(faults={"status-read"})
        report = self.execute(setup)
        self.assertTrue(report["errors"][0].startswith("poll: OSError:"))
        self.assertTrue(any(x.startswith("diagnostic:") for x in report["errors"]))
        self.assertEqual(report["buffer_disposition"], "retained")

    def test_pre_abort_snapshot_survives_reused_adapter_dictionary(self):
        setup = self.make(faults={"timeout"})
        snapshot = setup[2].snapshot
        shared = {}

        def reused():
            shared.clear()
            shared.update(snapshot())
            return shared

        setup[2].snapshot = reused
        report = self.execute(setup)
        before = next(x["state"] for x in report["snapshots"] if x["phase"] == "before_abort")
        after = next(x["state"] for x in report["snapshots"] if x["phase"] == "abort")
        self.assertIs(before["raw_status"]["simulated_active"], True)
        self.assertIs(after["raw_status"]["simulated_active"], False)
        self.assertIsNot(before, after)

    def test_missing_or_stale_status_is_not_default_success(self):
        for fault in ("missing-status", "stale-status"):
            with self.subTest(fault=fault):
                setup = self.make(faults={fault})
                report = self.execute(setup)
                self.assertEqual(report["status"], "FAIL")
                self.assertEqual(report["buffer_disposition"], "retained")
                self.assertNotIn("rx.read", setup[2].trace)

    def test_error_register_prevents_read_and_performance_claim(self):
        setup = self.make(faults={"dma-error"})
        report = self.execute(setup)
        self.assertIn("DMA error", report["errors"][0])
        self.assertIsNone(report["throughput_bytes_per_second"])
        self.assertNotIn("rx.read", setup[2].trace)
        self.assert_released(setup[2])

    def test_transfer_timeout_is_failure_even_after_successful_abort(self):
        setup = self.make(faults={"timeout"})
        report = self.execute(setup)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("TimeoutError", report["errors"][0])
        self.assert_released(setup[2])

    def test_actual_length_not_capacity(self):
        setup = self.make(faults={"short-output"})
        report = self.execute(setup)
        self.assertEqual(report["actual_bytes"], 95)
        self.assertEqual(report["requested_bytes"], 96)
        self.assertEqual(report["status"], "FAIL")
        self.assertNotIn("rx.read", setup[2].trace)
        self.assert_released(setup[2])

    def test_golden_mismatch_stops_session(self):
        setup = self.make(faults={"corrupt-output"})
        report = self.execute(setup)
        self.assertEqual(report["mismatch_count"], 1)
        self.assertEqual(report["first_mismatch"], 0)
        self.assertEqual(report["status"], "FAIL")
        trace = list(setup[2].trace)
        self.execute(setup)
        self.assertEqual(trace, setup[2].trace)

    def test_flush_failure_is_before_submission(self):
        for fault in ("tx-flush", "rx-flush"):
            with self.subTest(fault=fault):
                setup = self.make(faults={fault})
                self.assertEqual(self.execute(setup)["status"], "FAIL")
                self.assertNotIn("rx.arm", setup[2].trace)
                self.assert_released(setup[2])

    def test_post_dma_invalidate_failure_prevents_cpu_read(self):
        setup = self.make(faults={"rx-invalidate"})
        report = self.execute(setup)
        self.assertEqual(report["status"], "FAIL")
        self.assertNotIn("rx.read", setup[2].trace)
        self.assert_released(setup[2])

    def test_missing_cache_operations_produce_real_byte_mismatch(self):
        for faults in ({"tx-flush-noop"}, {"rx-invalidate-noop"},
                       {"rx-flush-noop", "rx-invalidate-noop"}):
            with self.subTest(faults=faults):
                setup = self.make(faults=faults)
                report = self.execute(setup)
                self.assertEqual(report["status"], "FAIL")
                self.assertGreater(report["mismatch_count"], 0)
                self.assertNotEqual(report["expected_sha256"], report["output_sha256"])

    def test_coherent_policy_requires_allocator_confirmation(self):
        setup = self.make(tx_policy="coherent", rx_policy="coherent")
        self.assertEqual(self.execute(setup)["status"], "FAIL")
        self.assertNotIn("rx.arm", setup[2].trace)

    def test_confirmed_coherent_path_needs_no_flush_or_invalidate(self):
        setup = self.make(coherent=True, tx_policy="coherent", rx_policy="coherent")
        self.assertEqual(self.execute(setup)["status"], "PASS")
        self.assertFalse(any(x.endswith(("flush", "invalidate")) for x in setup[2].trace))
        self.assert_released(setup[2])

    def test_length_granularity_independent_of_buffer_alignment(self):
        setup = self.make(length_bytes=96, buffer_alignment_bytes=64, length_granularity_bytes=8)
        self.assertEqual(self.execute(setup)["status"], "PASS")

    def test_invalid_contract_fails_before_allocations(self):
        for changes in ({"length_bytes": 95}, {"max_transfer_bytes": 80},
                        {"timeout_seconds": float("nan")}, {"abort_timeout_seconds": float("inf")},
                        {"max_polls": True}, {"allow_abort": "yes"}):
            with self.subTest(changes=changes):
                setup = self.make(**changes)
                self.assertEqual(self.execute(setup)["status"], "FAIL")
                self.assertEqual(setup[2].trace, [])

    def test_transfer_sizes_and_directions_are_inputs(self):
        for mode in ("receive", "loopback"):
            for length in (8, 96, 512, 4096):
                with self.subTest(mode=mode, length=length):
                    setup = self.make(mode=mode, length_bytes=length)
                    self.assertEqual(self.execute(setup)["status"], "PASS")

    def test_payload_contract_errors_do_not_allocate(self):
        for mode, expected_size, tx_size in (("receive", 96, 96), ("loopback", 95, 96),
                                            ("loopback", 96, 95), ("loopback", 96, None)):
            with self.subTest(mode=mode, expected_size=expected_size, tx_size=tx_size):
                spec, _, dma, session = self.make(mode=mode)
                report = session.run(spec, expected=bytes(expected_size),
                                     tx_data=None if tx_size is None else bytes(tx_size))
                self.assertEqual(report["status"], "FAIL")
                self.assertEqual(dma.trace, [])

    def test_boolean_transaction_id_and_actual_count_rejected(self):
        for key in ("transaction_id", "actual_bytes"):
            with self.subTest(key=key):
                setup = self.make()
                snapshot = setup[2].snapshot

                def bad_integer():
                    state = snapshot()
                    state[key] = True
                    return state

                setup[2].snapshot = bad_integer
                report = self.execute(setup)
                self.assertEqual(report["status"], "FAIL")
                self.assertNotIn("rx.read", setup[2].trace)

    def test_misaligned_allocation_rejected_before_dma(self):
        setup = self.make(faults={"misaligned"})
        self.assertEqual(self.execute(setup)["status"], "FAIL")
        self.assertNotIn("rx.arm", setup[2].trace)
        self.assert_released(setup[2])

    def test_aliased_object_released_only_once(self):
        setup = self.make()
        dma = setup[2]
        allocate = dma.allocate
        dma.allocate = lambda role, size: dma.allocations[0] if dma.allocations else allocate(role, size)
        report = self.execute(setup)
        self.assertIn("same object", report["errors"][0])
        self.assert_released(dma)

    def test_overlapping_allocations_rejected(self):
        setup = self.make()
        dma = setup[2]
        allocate = dma.allocate

        def overlap(role, size):
            buffer = allocate(role, size)
            buffer.device_address = dma.allocations[0].device_address
            return buffer

        dma.allocate = overlap
        report = self.execute(setup)
        self.assertIn("overlap", report["errors"][0])
        self.assertNotIn("rx.arm", dma.trace)
        self.assert_released(dma)

    def test_release_exception_not_retried(self):
        setup = self.make(faults={"rx-release"})
        report = self.execute(setup)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["buffer_disposition"], "release_indeterminate")
        self.execute(setup)
        self.assertEqual(setup[2].allocations[-1].release_attempts, 1)

    def test_poll_budget_bounds_a_nonadvancing_clock(self):
        setup = self.make(faults={"timeout", "abort-timeout"}, max_polls=3)
        setup[3].clock.sleep = lambda seconds: None
        report = self.execute(setup)
        self.assertIn("poll budget exhausted", report["errors"][0])
        self.assertEqual(report["buffer_disposition"], "retained")
        self.assertLessEqual(setup[2].trace.count("snapshot"), 7)

    def test_completed_without_quiescence_never_reads_or_frees(self):
        setup = self.make(allow_abort=False)
        snapshot = setup[2].snapshot

        def not_quiescent():
            state = snapshot()
            state["quiescent"] = False
            return state

        setup[2].snapshot = not_quiescent
        report = self.execute(setup)
        self.assertEqual(report["buffer_disposition"], "retained")
        self.assertNotIn("rx.read", setup[2].trace)

    def test_hardware_adapter_not_accepted(self):
        setup = self.make()
        setup[2].evidence_level = "hardware"
        with self.assertRaisesRegex(ValueError, "OFFLINE_ONLY"):
            DmaSession(setup[2])

    def test_cli_report_is_mock_and_existing_evidence_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            command = [sys.executable, "-B", str(ROOT / "scripts" / "simulate_dma.py"),
                       "--contract", str(ROOT / "references" / "example-session.json"),
                       "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            original = output.read_bytes()
            report = json.loads(original)
            self.assertEqual(report["evidence_level"], "mock")
            self.assertIs(report["board_execution"], False)
            self.assertIn("synthetic", report["timing_source"])
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(original, output.read_bytes())


if __name__ == "__main__":
    unittest.main()
