from __future__ import annotations

import hashlib
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_profile.py"
SPEC = importlib.util.spec_from_file_location("validate_profile", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)
GOLDEN_SCRIPT = Path(__file__).parents[1] / "scripts" / "compare_golden.py"
GOLDEN_SPEC = importlib.util.spec_from_file_location("compare_golden", GOLDEN_SCRIPT)
assert GOLDEN_SPEC and GOLDEN_SPEC.loader
GOLDEN = importlib.util.module_from_spec(GOLDEN_SPEC)
GOLDEN_SPEC.loader.exec_module(GOLDEN)


class ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        self.bit = artifacts / "demo.bit"
        self.hwh = artifacts / "demo.hwh"
        self.manifest = artifacts / "manifest.json"
        self.profile_path = self.root / "profile.json"
        self.evidence_path = self.root / "evidence.json"
        self.bit.write_bytes(b"mock-bit-for-static-validation-only\n")
        self.hwh.write_text(
            "<HW PART='xc7z020clg400-1'><MODULE INSTANCE='control_regs' NAME='control_regs'/>"
            "<MODULE INSTANCE='axi_dma_0' NAME='axi_dma_0'/></HW>",
            encoding="utf-8",
        )
        self.profile = {
            "schema_version": 1,
            "profile_id": "mock-board-overlay-v1",
            "board": {
                "board_name": "mock-board",
                "board_revision": "rev-a",
                "device_part": "xc7z020clg400-1",
                "pynq_image": "mock-image-v1",
                "compatibility_contains": ["mock,board"],
            },
            "overlay": {
                "bit": "artifacts/demo.bit",
                "hwh": "artifacts/demo.hwh",
                "manifest": "artifacts/manifest.json",
                "build_id": "mock-build-1",
                "interface_version": 7,
                "vivado_version": "2025.2",
                "required_ip": ["control_regs", "axi_dma_0"],
            },
            "register_contract": {
                "ip_name": "control_regs",
                "address_span_bytes": 4096,
                "registers": [
                    {"name": "hardware_id", "offset": 0, "width_bits": 32, "access": "ro"},
                    {"name": "interface_version", "offset": 4, "width_bits": 32, "access": "ro"},
                ],
                "identity": [
                    {"register": "hardware_id", "expected": 0x12345678, "mask": 0xFFFFFFFF},
                    {"register": "interface_version", "expected": 7, "mask": 0xFFFFFFFF},
                ],
            },
            "dma_contract": {
                "ip_name": "axi_dma_0",
                "mode": "simple",
                "mm2s_channel": "sendchannel",
                "s2mm_channel": "recvchannel",
                "stream_data_width_bits": 32,
                "buffer_alignment_bytes": 64,
                "max_transfer_bytes": 8192,
                "cache_policy": {"tx": "flush", "rx": "invalidate"},
                "tlast_required": True,
            },
            "self_tests": [
                {
                    "id": "loopback-4k",
                    "kind": "loopback",
                    "length_bytes": 4096,
                    "pattern": "counter8",
                    "timeout_seconds": 2.0,
                    "golden": "exact",
                }
            ],
            "acceptance": {
                "minimum_throughput_bytes_per_second": 1000,
                "maximum_latency_seconds": 1.0,
                "timing": {"minimum_wns_ns": 0.0},
                "resources": {"lut_max": 1000, "ff_max": 1000, "bram_max": 10, "dsp_max": 10},
            },
        }
        self.write_manifest()
        self.write_profile()
        self.evidence = {
            "evidence_level": "mock",
            "overlay_downloaded": False,
            "artifact_hashes": {"bit": self.hash(self.bit), "hwh": self.hash(self.hwh)},
            "register_reads": {"hardware_id": 0x12345678, "interface_version": 7},
            "dma_runs": [
                {
                    "id": "loopback-4k",
                    "length_bytes": 4096,
                    "timed_out": False,
                    "dma_error": False,
                    "mm2s_completed": True,
                    "s2mm_completed": True,
                    "tlast_observed": True,
                    "cache_operations": ["tx.flush", "rx.invalidate"],
                    "mismatch_count": 0,
                }
            ],
            "performance": {"minimum_throughput_bytes_per_second": 2000, "maximum_latency_seconds": 0.5},
            "timing": {"wns_ns": 0.25, "source": "mock timing report"},
            "resources": {"lut": 10, "ff": 20, "bram": 1, "dsp": 1, "source": "mock utilization report"},
        }
        self.write_evidence()

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def write_manifest(self) -> None:
        self.manifest.write_text(
            json.dumps(
                {
                    "build_id": "mock-build-1",
                    "interface_version": 7,
                    "vivado_version": "2025.2",
                    "device_part": "xc7z020clg400-1",
                    "bit_sha256": self.hash(self.bit),
                    "hwh_sha256": self.hash(self.hwh),
                }
            ),
            encoding="utf-8",
        )

    def write_profile(self) -> None:
        self.profile_path.write_text(json.dumps(self.profile), encoding="utf-8")

    def write_evidence(self) -> None:
        self.evidence_path.write_text(json.dumps(self.evidence), encoding="utf-8")

    def test_valid_profile_and_mock_evidence_pass_offline(self) -> None:
        report, code = VALIDATOR.validate(self.profile_path, self.evidence_path, "offline")
        self.assertEqual(0, code, report)
        self.assertEqual("PASS", report["status"])
        self.assertEqual("mock", report["evidence_level"])

    def test_contract_ip_must_exist_in_hwh(self) -> None:
        for scope in ("register_contract", "dma_contract"):
            with self.subTest(scope=scope):
                original = self.profile[scope]["ip_name"]
                self.profile[scope]["ip_name"] = "not_in_hwh"
                self.write_profile()
                report, code = VALIDATOR.validate(self.profile_path, None, "offline")
                self.assertEqual(1, code, report)
                self.assertIn("HWH_CONTRACT_IP", {x["code"] for x in report["issues"]})
                self.profile[scope]["ip_name"] = original

    def test_parameter_or_module_type_is_not_contract_instance(self) -> None:
        for decoy in ("<PARAMETER NAME='not_in_hwh'/>",
                      "<PORT NAME='not_in_hwh'/>",
                      "<MODULE INSTANCE='other_ip' MODULENAME='not_in_hwh'/>"):
            with self.subTest(decoy=decoy):
                self.hwh.write_text("<HW PART='xc7z020clg400-1'><MODULE INSTANCE='control_regs'/>"
                                    "<MODULE INSTANCE='axi_dma_0'/>" + decoy + "</HW>", encoding="utf-8")
                self.write_manifest()
                self.profile["dma_contract"]["ip_name"] = "not_in_hwh"
                self.write_profile()
                report, code = VALIDATOR.validate(self.profile_path, None, "offline")
                self.assertEqual(1, code, report)
                self.assertIn("HWH_CONTRACT_IP", {x["code"] for x in report["issues"]})

    def test_hierarchical_contract_requires_full_instance_path(self) -> None:
        self.hwh.write_text("<HW PART='xc7z020clg400-1'><MODULE INSTANCE='control_regs'/>"
                            "<MODULE INSTANCE='axi_dma_0' FULLNAME='/sub/axi_dma_0'/></HW>", encoding="utf-8")
        self.write_manifest()
        for name, expected in (("sub/axi_dma_0", 0), ("/sub/axi_dma_0", 0), ("axi_dma_0", 1)):
            with self.subTest(name=name):
                self.profile["dma_contract"]["ip_name"] = name
                self.write_profile()
                report, code = VALIDATOR.validate(self.profile_path, None, "offline")
                self.assertEqual(expected, code, report)

    def test_duplicate_dma_ids_fail_in_every_order(self) -> None:
        good = copy.deepcopy(self.evidence["dma_runs"][0])
        bad = dict(good, timed_out=True, mismatch_count=4)
        for records in ((bad, good), (good, bad), (good, good), (bad, bad), (good, bad, good)):
            with self.subTest(records=records):
                self.evidence["dma_runs"] = records
                self.write_evidence()
                report, code = VALIDATOR.validate(self.profile_path, self.evidence_path, "offline")
                self.assertEqual(1, code, report)
                self.assertEqual("FAIL", report["status"])
                self.assertIn("DMA_RUN_DUPLICATE", {x["code"] for x in report["issues"]})

    def test_malformed_dma_records_fail_closed(self) -> None:
        for value in (None, {}, [None], [{"id": []}], [{"id": ""}]):
            with self.subTest(value=value):
                self.evidence["dma_runs"] = value
                self.write_evidence()
                report, code = VALIDATOR.validate(self.profile_path, self.evidence_path, "offline")
                self.assertNotEqual(0, code, report)
                self.assertEqual("FAIL", report["status"])

    def test_manifest_hash_tamper_fails(self) -> None:
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest["bit_sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        report, code = VALIDATOR.validate(self.profile_path, None, "offline")
        self.assertEqual(1, code)
        self.assertIn("BIT_HASH", {item["code"] for item in report["issues"]})

    def test_unaligned_dma_length_fails(self) -> None:
        self.profile["self_tests"][0]["length_bytes"] = 4098
        self.write_profile()
        report, code = VALIDATOR.validate(self.profile_path, None, "offline")
        self.assertEqual(1, code)
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("DMA_LENGTH_BEAT", codes)
        self.assertIn("DMA_LENGTH_GRANULARITY", codes)

    def test_packet_length_does_not_inherit_buffer_address_alignment(self) -> None:
        self.profile["self_tests"][0]["length_bytes"] = 96
        self.profile["dma_contract"]["buffer_alignment_bytes"] = 64
        self.profile["dma_contract"]["length_granularity_bytes"] = 8
        self.write_profile()
        report, code = VALIDATOR.validate(self.profile_path, None, "offline")
        self.assertEqual(0, code, report)

    def test_explicit_transfer_granularity_and_boolean_rejected(self) -> None:
        self.profile["self_tests"][0]["length_bytes"] = 96
        self.profile["dma_contract"]["length_granularity_bytes"] = 64
        self.write_profile()
        report, code = VALIDATOR.validate(self.profile_path, None, "offline")
        self.assertEqual(1, code)
        self.assertIn("DMA_LENGTH_GRANULARITY", {x["code"] for x in report["issues"]})
        self.profile["dma_contract"]["length_granularity_bytes"] = True
        self.write_profile()
        report, code = VALIDATOR.validate(self.profile_path, None, "offline")
        self.assertEqual(1, code)
        self.assertIn("DMA_GRANULARITY", {x["code"] for x in report["issues"]})

    def test_mock_cannot_claim_hardware(self) -> None:
        report, code = VALIDATOR.validate(self.profile_path, self.evidence_path, "hardware")
        self.assertEqual(1, code)
        self.assertIn("FALSE_HARDWARE_CLAIM", {item["code"] for item in report["issues"]})

    def test_golden_comparison_detects_first_mismatch(self) -> None:
        result = GOLDEN.compare_bytes(b"\x00\x01\x02\x03", b"\x00\x01\x09\x03")
        self.assertEqual(1, result["mismatch_count"])
        self.assertEqual(2, result["first_mismatch"])

    def test_json_integer_golden_preserves_large_integer_difference(self) -> None:
        expected_path, actual_path = self.root / "large-expected.json", self.root / "large-actual.json"
        expected_path.write_text("[9007199254740992]", encoding="utf-8")
        actual_path.write_text("[9007199254740993]", encoding="utf-8")
        result = GOLDEN.compare_numbers(GOLDEN.numeric_list(expected_path),
                                       GOLDEN.numeric_list(actual_path), 0.0, 0.0)
        self.assertEqual(result["mismatch_count"], 1)
        self.assertEqual(result["max_absolute_error"], 1)

    def test_numeric_tolerances_do_not_overflow_to_false_pass(self) -> None:
        result = GOLDEN.compare_numbers([1e308], [-1e308], 0.0, 1.9)
        self.assertEqual(result["mismatch_count"], 1)

    def test_integer_tolerance_and_mixed_float_are_compared_exactly(self) -> None:
        self.assertEqual(GOLDEN.compare_numbers([2**53], [2**53 + 1], 1.0, 0.0)["mismatch_count"], 0)
        self.assertEqual(GOLDEN.compare_numbers([2**53 + 1], [float(2**53)], 0.0, 0.0)["mismatch_count"], 1)

    def test_nonfinite_golden_tolerance_is_rejected(self) -> None:
        for tolerance in (float("nan"), float("inf"), -1.0):
            with self.subTest(tolerance=tolerance), self.assertRaises(ValueError):
                GOLDEN.compare_numbers([0.0], [99.0], tolerance, 0.0)

    def test_nonfinite_profile_is_rejected(self) -> None:
        self.profile["self_tests"][0]["timeout_seconds"] = float("nan")
        self.write_profile()
        report, code = VALIDATOR.validate(self.profile_path, None, "offline")
        self.assertNotEqual(0, code)
        self.assertEqual("FAIL", report["status"])

    def test_side_effect_identity_is_rejected(self) -> None:
        for access in ("wo", "w1c", "rc", "rw"):
            with self.subTest(access=access):
                self.profile["register_contract"]["registers"][0]["access"] = access
                self.write_profile()
                report, code = VALIDATOR.validate(self.profile_path, None, "offline")
                self.assertNotEqual(0, code)
                self.assertIn("IDENTITY_ACCESS", {item["code"] for item in report["issues"]})

    def test_wide_register_and_zero_mask_are_rejected(self) -> None:
        self.profile["register_contract"]["registers"][0]["width_bits"] = 64
        self.profile["register_contract"]["identity"][0]["mask"] = 0
        self.write_profile()
        report, code = VALIDATOR.validate(self.profile_path, None, "offline")
        self.assertNotEqual(0, code)
        self.assertTrue({"REGISTER_WIDTH", "IDENTITY_VALUE"}.issubset({item["code"] for item in report["issues"]}))

    def test_hwh_in_different_directory_is_rejected(self) -> None:
        other = self.root / "other"
        other.mkdir()
        (other / "demo.hwh").write_bytes(self.hwh.read_bytes())
        self.profile["overlay"]["hwh"] = "other/demo.hwh"
        self.write_profile()
        report, code = VALIDATOR.validate(self.profile_path, None, "offline")
        self.assertNotEqual(0, code)
        self.assertIn("OVERLAY_DIRECTORY", {item["code"] for item in report["issues"]})

    def test_malformed_nested_evidence_returns_failure_report(self) -> None:
        self.profile["register_contract"]["identity"] = [None]
        self.write_profile()
        report, code = VALIDATOR.validate(self.profile_path, self.evidence_path, "hardware")
        self.assertNotEqual(0, code)
        self.assertEqual("FAIL", report["status"])

    def test_second_synthetic_board_and_overlay_reuse(self) -> None:
        # A different device family, IP names, offsets and transfer geometry;
        # this demonstrates portability of offline logic, not physical support.
        self.profile["board"].update(board_name="mock-image-accelerator", device_part="xczu3eg-sbva484-1-e",
                                     compatibility_contains=["mock,second-board"])
        self.profile["overlay"]["required_ip"] = ["image_control", "frame_dma"]
        self.profile["register_contract"]["ip_name"] = "image_control"
        self.profile["register_contract"]["registers"][0]["offset"] = 32
        self.profile["register_contract"]["registers"][1]["offset"] = 36
        self.profile["dma_contract"].update(ip_name="frame_dma", stream_data_width_bits=64, max_transfer_bytes=16384)
        self.profile["self_tests"][0]["length_bytes"] = 8192
        self.hwh.write_text("<HW PART='xczu3eg-sbva484-1-e'><MODULE INSTANCE='image_control'/>"
                            "<MODULE INSTANCE='frame_dma'/></HW>", encoding="utf-8")
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest.update(device_part=self.profile["board"]["device_part"], hwh_sha256=self.hash(self.hwh))
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        self.write_profile()
        report, code = VALIDATOR.validate(self.profile_path, None, "offline")
        self.assertEqual(0, code, report)
        self.assertEqual("static", report["evidence_level"])

    def test_unqualified_board_runner_stops_before_hardware_access(self) -> None:
        probe = SCRIPT.with_name("pynq_probe.py")
        output = self.root / "hardware.json"
        run = subprocess.run([sys.executable, "-B", str(probe), "--profile", str(self.profile_path),
                              "--download", "--output", str(output)], capture_output=True, text=True, timeout=5)
        self.assertNotEqual(0, run.returncode)
        self.assertIn("BOARD_RUNNER_NOT_QUALIFIED", run.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
