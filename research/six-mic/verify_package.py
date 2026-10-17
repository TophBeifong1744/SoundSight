"""Verify the frozen bundle and optionally an independent reproduction."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(root, entries):
    failures = []
    for name, expected in entries.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            failures.append(f"missing/unsafe: {name}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(f"hash mismatch: {name}")
    if failures:
        raise SystemExit("FAIL\n" + "\n".join(failures))
    print(f"PASS: {len(entries)} file hashes in {root.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reproduced", type=Path)
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    verify(base, json.loads((base / "package-manifest.json").read_text(encoding="utf-8-sig")))
    expected = json.loads((base / "results/manifest.json").read_text(encoding="utf-8-sig"))
    verify(base / "results", expected)
    cfg = json.loads((base / "results/config.json").read_text(encoding="utf-8-sig"))
    actual = hashlib.sha256((base / "src/six_mic_acoustic_review.py").read_bytes()).hexdigest()
    if actual != cfg["script_sha256"]:
        raise SystemExit("FAIL: source/config mismatch")
    print("PASS: source matches original simulation config")
    if args.reproduced:
        verify(args.reproduced.resolve(), expected)
