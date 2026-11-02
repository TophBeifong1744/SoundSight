#!/bin/bash
set -euo pipefail
inputs=$(realpath "$1")
output=$(realpath "$2")
source_dir=$(cd "$(dirname "$0")" && pwd)
host_python=${SS_HOST_PYTHON:-python3}
tools=${SS_HOST_TOOLS:?Point to locally unpacked DTC tools}
export LD_LIBRARY_PATH="$tools/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
work=$(mktemp -d /var/tmp/soundsight-usb-dt.XXXXXXXX)
cleanup() {
    case "$work" in /var/tmp/soundsight-usb-dt.*) ;; *) return 1 ;; esac
    test ! -L "$work" && rm -rf -- "$work"
}
trap cleanup EXIT
"$host_python" - "$inputs" "$work" <<'PY'
import pathlib,sys,zipfile
root=pathlib.Path(sys.argv[2])
with zipfile.ZipFile(sys.argv[1]) as archive:
    for name in archive.namelist():
        if name.startswith('live-device-tree/'):
            path=root/name
            assert path.resolve().is_relative_to(root.resolve())
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(archive.read(name))
PY
"$tools/usr/bin/dtc" -@ -I fs -O dtb -o "$output/base.dtb" "$work/live-device-tree" 2> "$output/base-dtc.log"
for stage in usb-pins-phy usb-controller; do
    "$tools/usr/bin/dtc" -@ -I dts -O dtb -o "$output/$stage.dtbo" "$source_dir/$stage.dts"
done
"$tools/usr/bin/fdtoverlay" -i "$output/base.dtb" -o "$output/combined.dtb" "$output/usb-pins-phy.dtbo" "$output/usb-controller.dtbo"
echo 'DT_OVERLAY_COMPOSITION_OK (offline only)'
