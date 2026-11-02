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
    if args.reproduced:
        # Text-only replay comparison permits Windows/Linux newline differences.
        # Preserved originals above still require their exact recorded bytes.
        names = [k for k in expected if k.startswith('direction-') or k == 'self-tests.json']
        for name in names:
            original = (base / 'results' / name).read_text(encoding='utf-8-sig')
            reproduced = (args.reproduced / name).read_text(encoding='utf-8-sig')
            if reproduced != original:
                raise SystemExit('FAIL: reproduced content differs: ' + name)
        print(f'PASS: {len(names)} direction outputs match (newline normalization only)')
