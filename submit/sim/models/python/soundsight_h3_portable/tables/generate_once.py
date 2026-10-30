"""One-time extraction of the fixed leaf's actual Q30/atan values.

This is not called by the portable runtime. Existing table outputs are never
overwritten; generation requires an explicit clean source tree.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SOURCES = json.loads((HERE / "source-manifest.json").read_text(encoding="utf-8"))
row = SOURCES["entries"]["fixed_golden"]
path = REPO / row["path"]
if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
    raise RuntimeError("FIXED_LEAF_BYTES_CHANGED")
name = "_soundsight_table_source_" + row["sha256"][:16]
if name in sys.modules:
    raise RuntimeError("MODULE_CACHE_COLLISION")
spec = importlib.util.spec_from_file_location(name, path)
leaf = importlib.util.module_from_spec(spec)
sys.modules[name] = leaf
try:
    spec.loader.exec_module(leaf)
except BaseException:
    del sys.modules[name]
    raise


class Recorder:
    pi = math.pi
    log2 = staticmethod(math.log2)

    def __init__(self):
        self.calls = []

    def cos(self, angle):
        value = math.cos(angle)
        self.calls.append(("cos", angle, value))
        return value

    def sin(self, angle):
        value = math.sin(angle)
        self.calls.append(("sin", angle, value))
        return value


tables = []
for inverse, width in ((False, 29), (True, 25)):
    recorder = Recorder()
    leaf.math = recorder
    leaf.fixed_fft([(0, 0)] * 1024, inverse=inverse, width=width)
    if len(recorder.calls) != 2046:
        raise RuntimeError("TWIDDLE_COUNT")
    pairs = []
    for first, second in zip(recorder.calls[::2], recorder.calls[1::2]):
        if first[0] != "cos" or second[0] != "sin" or first[1] != second[1]:
            raise RuntimeError("TWIDDLE_CALL_ORDER")
        pairs.append((round(first[2] * (1 << 30)), round(second[2] * (1 << 30))))
    tables.append(pairs)
fft = np.asarray(tables, dtype="<i4")
atan = np.asarray(leaf._CORDIC_ATAN_Q16, dtype="<i4")
if fft.shape != (2, 1023, 2) or atan.shape != (24,):
    raise RuntimeError("TABLE_SHAPE")
outputs = {"fft-q30-i32le.bin": fft.tobytes(order="C"),
           "cordic-atan-q16-i32le.bin": atan.tobytes(order="C")}
for filename, payload in outputs.items():
    with (HERE / filename).open("xb") as f:
        f.write(payload)
meta = {"schema": "soundsight-frozen-table-v1", "scope": "RESEARCH_ONLY",
        "source_path": row["path"], "source_sha256": row["sha256"],
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": platform.python_version(), "numpy": np.__version__,
        "method": "instrument fixed_golden.fixed_fft on 1024 zeros, forward29 then inverse25; capture every actual cos/sin call in stage-size ascending, j ascending order; capture imported _CORDIC_ATAN_Q16",
        "fft": {"file": "fft-q30-i32le.bin", "shape": [2, 1023, 2],
                "order": "direction forward,inverse; radix2 size 2..1024; j ascending; real,imag",
                "dtype": "little-endian signed int32", "fraction_bits": 30,
                "sha256": hashlib.sha256(outputs["fft-q30-i32le.bin"]).hexdigest(),
                "bytes": len(outputs["fft-q30-i32le.bin"])},
        "atan": {"file": "cordic-atan-q16-i32le.bin", "shape": [24],
                 "order": "iteration i=0..23", "dtype": "little-endian signed int32",
                 "fraction_bits": 16,
                 "sha256": hashlib.sha256(outputs["cordic-atan-q16-i32le.bin"]).hexdigest(),
                 "bytes": len(outputs["cordic-atan-q16-i32le.bin"])}}
with (HERE / "table-manifest.json").open("x", encoding="utf-8") as f:
    json.dump(meta, f, indent=2)
    f.write("\n")
print(json.dumps({"fft_sha256": meta["fft"]["sha256"], "atan_sha256": meta["atan"]["sha256"]}))
