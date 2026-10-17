"""Run bundled tests and emit a source-bound offline self-test report."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
        self.outcomes = {}
        self.subtests = 0

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes[test.id()] = "PASS"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes[test.id()] = "FAIL"

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes[test.id()] = "ERROR"

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes[test.id()] = "SKIP"

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        self.subtests += 1
        if err:
            self.outcomes[test.id()] = "FAIL"

    def stopTest(self, test):
        self.records.append({"id": test.id(), "status": self.outcomes.get(test.id(), "UNKNOWN")})
        super().stopTest(test)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="new JSON filename; existing evidence is never overwritten")
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error("output exists; choose a fresh filename")
    sys.dont_write_bytecode = True
    inputs = sorted((ROOT / "scripts").glob("*.py")) + sorted((ROOT / "tests").glob("*.py"))
    inputs += sorted((ROOT / "references").glob("*.json"))

    def hashes():
        return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}

    before = hashes()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    after = hashes()
    passed = result.wasSuccessful() and not result.skipped and before == after and result.testsRun > 0
    report = {
        "schema_version": 1, "status": "PASS" if passed else "FAIL",
        "evidence_level": "mock", "board_execution": False,
        "review_status": "AUTHOR_SELF_TEST_NOT_B_ACCEPTANCE",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": sys.version, "platform": platform.platform()},
        "reproduce": "python -B scripts/run_offline_tests.py --output <new-report.json>",
        "tests_run": result.testsRun, "subtests_run": result.subtests,
        "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "tests": result.records,
        "failure_details": [{"test": test.id(), "traceback": detail} for test, detail in result.failures + result.errors],
        "source_sha256": before, "sources_unchanged_during_run": before == after,
        "claims": {"pynq_driver": "NOT_RUN", "overlay_download": "NOT_RUN", "physical_dma": "NOT_RUN",
                   "tlast_waveform": "NOT_RUN", "hardware_performance": "NOT_RUN", "vivado_resources": "NOT_RUN"},
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    print(encoded, end="")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
