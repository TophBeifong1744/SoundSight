import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_xsim", ROOT / "scripts/run_xsim.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class RunnerTest(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(runner.assess("SKILL_PASS cases=2 checks=9\n", 9)["status"], "PASS_SIMULATION")

    def test_no_false_pass(self):
        for log in ("", "SKILL_PASS cases=0 checks=9", "SKILL_PASS cases=1 checks=0",
                    "SKILL_PASS cases=1 checks=8", "SKILL_PASS cases=1 checks=9\nFatal: after marker",
                    "SKILL_PASS cases=1 checks=9\nERROR: later", "SKILL_PASS cases=1 checks=9\nSKILL_FAIL bad",
                    "SKILL_PASS cases=1 checks=9\nSKILL_PASS cases=1 checks=9"):
            with self.subTest(log=log):
                self.assertEqual(runner.assess(log, 9)["status"], "FAIL_SIMULATION")

    def test_existing_output_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = Path(tmp) / "sentinel"
            sentinel.write_bytes(b"keep")
            with self.assertRaises(runner.CaseError):
                runner.run("bad", "bad", tmp)
            self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_examples_load(self):
        for example in ("elastic", "pcm4"):
            case, sources, contract = runner.load_case(ROOT / "examples" / example / "case.json")
            self.assertTrue(sources and contract.is_file())
            self.assertGreater(case["minimum_checks"], 0)

    def test_reject_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case.json"
            for invalid in ({}, [], {"schema_version": 999}):
                path.write_text(json.dumps(invalid))
                with self.assertRaises(runner.CaseError):
                    runner.load_case(path)

    def test_bad_input_reports_no_hardware(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            code, result = runner.run(Path(tmp) / "missing", tmp, out)
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "BLOCKED_INPUT")
            self.assertIn("board", result["not_run"])
            self.assertTrue((out / "result.json").is_file())

    def test_stage_failures(self):
        casefile = ROOT / "examples/elastic/case.json"
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            for tool in ("xvlog", "xelab", "xsim"):
                (bindir / (tool + (".bat" if runner.os.name == "nt" else ""))).touch()
            cases = {
                "compile": [{"returncode": 0, "text": "v2025.2", "timed_out": False},
                            {"returncode": 1, "text": "ERROR: compile", "timed_out": False}],
                "timeout": [{"returncode": None, "text": "partial", "timed_out": True, "cleanup_confirmed": False}],
                "version": [{"returncode": 0, "text": "v2018.3", "timed_out": False}],
            }
            for name, responses in cases.items():
                with self.subTest(name=name), patch.object(runner, "execute", side_effect=responses):
                    code, result = runner.run(casefile, bindir, Path(tmp) / name)
                    self.assertNotEqual(code, 0)
                    self.assertNotEqual(result["status"], "PASS_SIMULATION")
                    self.assertTrue((Path(tmp) / name / "result.json").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
