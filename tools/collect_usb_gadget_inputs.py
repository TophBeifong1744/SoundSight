#!/usr/bin/env python3
"""Collect existing PYNQ USB bring-up inputs; never configure or load hardware.

Python 3.8+, standard library only. The only write is a new output ZIP.
"""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import zipfile


MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024


class Collector:
    def __init__(self, archive):
        self.archive = archive
        self.total = 0
        self.files = []
        self.issues = []

    def add(self, name, data):
        if len(data) > MAX_FILE or self.total + len(data) > MAX_TOTAL:
            raise ValueError("collection size limit exceeded: " + name)
        self.archive.writestr(name, data)
        self.total += len(data)
        self.files.append({"path": name, "bytes": len(data),
                           "sha256": hashlib.sha256(data).hexdigest()})

    def file(self, source, name):
        try:
            # Read rather than ZipFile.write: DT sysfs properties can have size 0.
            with source.open("rb") as stream:
                data = stream.read(MAX_FILE + 1)
            self.add(name, data)
        except (OSError, ValueError) as exc:
            self.issues.append({"path": str(source), "error": str(exc)})

    def tree(self, source, prefix):
        root = source.resolve()
        if not root.is_dir():
            self.issues.append({"path": str(source), "error": "directory missing"})
            return
        def walk_error(exc):
            self.issues.append({"path": str(exc.filename), "error": str(exc)})
        for directory, dirs, files in os.walk(str(root), onerror=walk_error):
            for item in list(dirs):
                path = Path(directory) / item
                if item == ".git":
                    dirs.remove(item)
                elif path.is_symlink():
                    dirs.remove(item)
                    self.issues.append({"path": str(path),
                                        "error": "directory symlink skipped",
                                        "target": os.readlink(str(path))})
            for item in sorted(files):
                path = Path(directory) / item
                try:
                    path.resolve().relative_to(root)
                except (ValueError, RuntimeError):
                    self.issues.append({"path": str(path),
                                        "error": "external or cyclic symlink skipped"})
                    continue
                self.file(path, prefix + "/" + path.relative_to(root).as_posix())


def collect(output):
    release = platform.release()
    build = Path("/lib/modules") / release / "build"
    if shutil.disk_usage(str(output.parent)).free < 128 * 1024 * 1024:
        raise RuntimeError("need at least 128 MiB free in output filesystem")
    # Exclusive creation: never overwrite a previous collection or boot file.
    with output.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            collector = Collector(archive)
            for name in ("BOOT.BIN", "BOOT.SCR", "IMAGE.UB", "REVISION", "boot.py"):
                collector.file(Path("/boot") / name, "boot/" + name)
            print("Boot files read; collecting running device tree...", flush=True)
            collector.tree(Path("/sys/firmware/devicetree/base"), "live-device-tree")
            print("Collecting installed kernel build files...", flush=True)
            collector.tree(build, "kernel-build")
            config = Path("/proc/config.gz")
            if config.exists():
                try:
                    with gzip.open(str(config), "rb") as config_stream:
                        collector.add("kernel/running.config", config_stream.read(MAX_FILE + 1))
                except (OSError, ValueError, EOFError) as exc:
                    collector.issues.append({"path": str(config), "error": str(exc)})
            else:
                collector.issues.append({"path": str(config),
                                         "error": "running config unavailable; inspect build/.config"})
            for name in ("version", "cmdline", "mounts"):
                collector.file(Path("/proc") / name, "system/" + name)
            manifest = {"schema": 1, "kernel_release": release,
                        "machine": platform.machine(), "build_target": str(build.resolve()),
                        "source_bytes": collector.total, "files": collector.files,
                        "issues": collector.issues,
                        "scope": "input collection only; no driver/DT/network/FPGA changes"}
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    print("OUTPUT=" + str(output))
    print("FILES=%d ISSUES=%d" % (len(collector.files), len(collector.issues)))
    print("Collection only. USB networking has NOT been enabled.")
    if collector.issues:
        print("Some inputs could not be collected; send this ZIP and the terminal output for review.")
    return 2 if collector.issues else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/boot/soundsight_usb_inputs.zip"))
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("run this collector on the PYNQ board, not Windows")
    output = args.output.expanduser().absolute()
    try:
        return collect(output)
    except (OSError, ValueError, RuntimeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        print("No hardware configuration was changed. An interrupted output ZIP may remain.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
