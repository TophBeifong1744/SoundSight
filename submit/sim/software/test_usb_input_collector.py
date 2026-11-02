"""Offline input-collection checks; no board or USB hardware accessed."""

import ast
import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile


SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "collect_usb_gadget_inputs.py"
spec = importlib.util.spec_from_file_location("usb_collector", str(SCRIPT))
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class USBInputCollectorTests(unittest.TestCase):
    def test_python38_syntax(self):
        ast.parse(SCRIPT.read_text(encoding="utf-8"), feature_version=8)

    def exercise(self, missing_boot=False):
        with tempfile.TemporaryDirectory(prefix="soundsight-usb-test-") as folder:
            root = Path(folder)
            def put(name, data):
                path = root / name.lstrip("/")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            for name in ("BOOT.BIN", "BOOT.SCR", "IMAGE.UB", "REVISION", "boot.py"):
                if not (missing_boot and name == "IMAGE.UB"):
                    put("boot/" + name, ("fixture:" + name).encode())
            put("sys/firmware/devicetree/base/amba/usb@e0002000/status", b"disabled\x00")
            put("sys/firmware/devicetree/base/empty-property", b"")
            put("lib/modules/test-kernel/build/Module.symvers", b"fixture-symbols\n")
            put("lib/modules/test-kernel/build/include/generated/autoconf.h", b"fixture-header\n")
            put("proc/config.gz", gzip.compress(b"CONFIG_USB_GADGET=y\n"))
            for name in ("version", "cmdline", "mounts"):
                put("proc/" + name, b"fixture\n")
            before = {p.relative_to(root).as_posix(): p.read_bytes()
                      for p in root.rglob("*") if p.is_file()}
            output = root / "inputs.zip"
            def mapped_path(value):
                value = str(value)
                if value.startswith(("/boot", "/proc", "/sys", "/lib/modules")):
                    return root / value.lstrip("/")
                return Path(value)
            with patch.object(collector, "Path", mapped_path), \
                    patch.object(collector.platform, "release", return_value="test-kernel"), \
                    contextlib.redirect_stdout(io.StringIO()):
                result = collector.collect(output)
                saved = output.read_bytes()
                with self.assertRaises(FileExistsError):
                    collector.collect(output)
                self.assertEqual(output.read_bytes(), saved)
            self.assertEqual(result, 2 if missing_boot else 0)
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(len(manifest["issues"]), 1 if missing_boot else 0)
                self.assertEqual(archive.read("live-device-tree/amba/usb@e0002000/status"), b"disabled\x00")
                self.assertEqual(archive.read("live-device-tree/empty-property"), b"")
                self.assertEqual(archive.read("kernel/running.config"), b"CONFIG_USB_GADGET=y\n")
                for item in manifest["files"]:
                    data = archive.read(item["path"])
                    self.assertEqual(len(data), item["bytes"])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])
            for name, data in before.items():
                self.assertEqual((root / name).read_bytes(), data)

    def test_collects_inputs_and_preserves_sources_and_existing_output(self):
        self.exercise()

    def test_missing_input_is_reported_without_claiming_complete(self):
        self.exercise(missing_boot=True)


if __name__ == "__main__":
    unittest.main()
