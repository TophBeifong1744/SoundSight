#!/usr/bin/env python3
"""Fetch the small, unmodified Xilinx USB RNDIS source closure for review/build."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import urllib.request

BASE = "https://raw.githubusercontent.com/Xilinx/linux-xlnx/xilinx-v2020.2/"
HERE = Path(__file__).resolve().parent


def main():
    root = HERE / "vendor" / "linux-xlnx"
    todo = ["drivers/usb/gadget/function/" + n for n in
            ("u_ether.c", "f_rndis.c", "rndis.c")]
    todo += ["LICENSES/preferred/GPL-2.0", "COPYING"]
    done = {}
    while todo:
        name = todo.pop(0)
        if name in done:
            continue
        # Normalize relative quoted includes; prohibit paths outside source tree.
        parts = []
        for part in PurePosixPath(name).parts:
            if part == "..":
                if not parts:
                    raise ValueError(name)
                parts.pop()
            elif part != ".":
                parts.append(part)
        name = "/".join(parts)
        if name in done:
            continue
        path = root / name
        if path.exists():
            data = path.read_bytes()
        else:
            with urllib.request.urlopen(BASE + name, timeout=45) as response:
                data = response.read()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        done[name] = {"url": BASE + name, "sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data)}
        if name.endswith((".c", ".h")):
            for dependency in re.findall(r'^\s*#\s*include\s+"([^"]+)"', data.decode(), re.M):
                # Upstream function/Makefile includes its gadget parent directory.
                parent = (PurePosixPath("drivers/usb/gadget") if dependency == "configfs.h"
                          else PurePosixPath(name).parent)
                todo.append(str(parent / dependency))
        print(name)
    (HERE / "source-receipt.json").write_text(
        json.dumps({"upstream_ref": "xilinx-v2020.2", "files": done}, indent=2) + "\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
