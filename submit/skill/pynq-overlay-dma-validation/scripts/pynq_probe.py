#!/usr/bin/env python3
"""Fail-closed board entrypoint; use simulate_dma.py for offline execution."""

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--supplemental-evidence", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.parse_args()
    # No hidden board implementation or bypass switch. The tested lifecycle
    # implementation is in dma_session.py, with a mock adapter only.
    raise SystemExit(
        "BOARD_RUNNER_NOT_QUALIFIED: no PYNQ import, allocation, MMIO or download. "
        "Use simulate_dma.py for offline tests. A real adapter must first qualify "
        "driver completion, abort/quiescence, coherency and process lifetime; "
        "see references/hardware-runbook.md."
    )


if __name__ == "__main__":
    main()
