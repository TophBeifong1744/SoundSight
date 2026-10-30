"""Exact-byte bindings to the fixed research leaves and frozen numeric tables."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

HERE = Path(__file__).resolve().parent


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _module(role, path, expected):
    name = "_soundsight_h3_" + role + "_" + expected[:16]
    previous = sys.modules.get(name)
    if previous is not None:
        if (Path(getattr(previous, "__file__", "")).resolve() != path.resolve()
                or getattr(previous, "_soundsight_sha256", None) != expected
                or digest(path) != expected):
            raise RuntimeError("MODULE_CACHE_IDENTITY_MISMATCH: " + role)
        return previous
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("MODULE_LOAD_FAILED: " + role)
    value = importlib.util.module_from_spec(spec)
    value._soundsight_sha256 = expected
    sys.modules[name] = value  # dataclasses in fixed_golden need this exact module key
    try:
        spec.loader.exec_module(value)
    except BaseException:
        del sys.modules[name]
        raise
    if Path(value.__file__).resolve() != path.resolve() or digest(path) != expected:
        del sys.modules[name]
        raise RuntimeError("MODULE_POSTLOAD_IDENTITY_MISMATCH: " + role)
    return value


class Bindings:
    def __init__(self, repo):
        self.repo = Path(repo).resolve(strict=True)
        if not (self.repo / ".git").exists():
            raise ValueError("REPO_ROOT_REQUIRED")
        self.source_manifest_path = HERE / "tables/source-manifest.json"
        self.table_manifest_path = HERE / "tables/table-manifest.json"
        self.sources = json.loads(self.source_manifest_path.read_text(encoding="utf-8"))
        self.tables = json.loads(self.table_manifest_path.read_text(encoding="utf-8"))
        if (self.sources.get("schema") != "soundsight-portable-source-binding-v1"
                or self.tables.get("schema") != "soundsight-frozen-table-v1"):
            raise RuntimeError("MANIFEST_SCHEMA_MISMATCH")
        self.identity = {"source_manifest_sha256": digest(self.source_manifest_path),
                         "table_manifest_sha256": digest(self.table_manifest_path),
                         "source_files": {}, "table_files": {}}
        for role, row in self.sources["entries"].items():
            path = (self.repo / row["path"]).resolve(strict=True)
            if not path.is_relative_to(self.repo) or digest(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
                raise RuntimeError("SOURCE_IDENTITY_MISMATCH: " + role)
            if "commit" in row:
                oid = subprocess.run(
                    ["git", "-C", str(self.repo), "rev-parse", "--verify",
                     row["commit"] + ":" + row["path"]],
                    capture_output=True, text=True, check=True).stdout.strip()
                if oid != row.get("git_blob"):
                    raise RuntimeError("SOURCE_GIT_BLOB_IDENTITY_MISMATCH: " + role)
                blob = subprocess.run(["git", "-C", str(self.repo), "cat-file", "blob", oid],
                                      capture_output=True, check=True).stdout
                if hashlib.sha256(blob).hexdigest() != row["sha256"]:
                    raise RuntimeError("SOURCE_GIT_BYTES_MISMATCH: " + role)
            self.identity["source_files"][role] = row["sha256"]
        self.fg = self.load("fixed_golden")
        self.phat = self.load("phat_model")
        self.guards = self.load("guards")
        self.cordic = self.load("cordic_candidate")
        self.dynamic = self.load("dynamic_das")
        self.delay_loader = self.load("delay_rom_loader")
        self.hann = np.frombuffer((self.repo / self.sources["entries"]["hann"]["path"]).read_bytes(), dtype="<u4").astype(np.int64)
        if self.hann.shape != (1024,) or np.any(self.hann > 2**17) or not np.any(self.hann):
            raise RuntimeError("HANN_FORMAT_MISMATCH")
        self.delay_rom = self.delay_loader.DelayROM(
            self.repo / self.sources["entries"]["delay_rom"]["path"],
            self.sources["entries"]["delay_rom"]["sha256"])
        self.fft_twiddle = self._table("fft", (2, 1023, 2))
        self.cordic_atan = self._table("atan", (24,))
        if tuple(int(v) for v in self.fg._CORDIC_ATAN_Q16) != tuple(map(int, self.cordic_atan)):
            raise RuntimeError("CORDIC_ATAN_LEAF_TABLE_MISMATCH")
        # The frozen values, rather than runtime atan(), feed the unchanged leaf.
        self.fg._CORDIC_ATAN_Q16 = tuple(map(int, self.cordic_atan))

    def load(self, role):
        row = self.sources["entries"][role]
        return _module(role, self.repo / row["path"], row["sha256"])

    def _table(self, key, shape):
        item = self.tables[key]
        path = HERE / "tables" / item["file"]
        if digest(path) != item["sha256"] or path.stat().st_size != item["bytes"] or item["shape"] != list(shape):
            raise RuntimeError("FROZEN_TABLE_IDENTITY_MISMATCH: " + key)
        self.identity["table_files"][key] = item["sha256"]
        return np.frombuffer(path.read_bytes(), dtype="<i4").reshape(shape).copy()

    def verify_post(self):
        if digest(self.source_manifest_path) != self.identity["source_manifest_sha256"]:
            raise RuntimeError("SOURCE_MANIFEST_CHANGED_DURING_RUN")
        if digest(self.table_manifest_path) != self.identity["table_manifest_sha256"]:
            raise RuntimeError("TABLE_MANIFEST_CHANGED_DURING_RUN")
        for role, expected in self.identity["source_files"].items():
            if digest(self.repo / self.sources["entries"][role]["path"]) != expected:
                raise RuntimeError("SOURCE_CHANGED_DURING_RUN: " + role)
        for key, expected in self.identity["table_files"].items():
            if digest(HERE / "tables" / self.tables[key]["file"]) != expected:
                raise RuntimeError("TABLE_CHANGED_DURING_RUN: " + key)
