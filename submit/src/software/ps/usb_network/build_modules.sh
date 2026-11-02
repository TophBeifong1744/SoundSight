#!/bin/bash
# Host-only build. Never invokes insmod/modprobe, writes /boot, or touches hardware.
set -euo pipefail
if [ "$#" -ne 3 ]; then
    echo "usage: bash build_modules.sh board-inputs.zip arm-toolchain.tar.xz output-dir" >&2
    exit 2
fi
inputs=$(realpath "$1")
toolchain=$(realpath "$2")
mkdir -p "$3"
output=$(realpath "$3")
source_dir=$(cd "$(dirname "$0")" && pwd)
host_python=${SS_HOST_PYTHON:-python3}
if [ -n "${SS_HOST_TOOLS:-}" ]; then
    export PATH="$SS_HOST_TOOLS/usr/bin:$PATH"
    export BISON_PKGDATADIR="$SS_HOST_TOOLS/usr/share/bison"
    export M4="$SS_HOST_TOOLS/usr/bin/m4"
    export LD_LIBRARY_PATH="$SS_HOST_TOOLS/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
fi
work=${SS_USB_REUSE_WORK:-}
if [ -n "$work" ]; then
    case "$work" in /var/tmp/soundsight-usb-build.*) ;; *) exit 2 ;; esac
    test -d "$work/kernel-build"
    test ! -L "$work"
else
    work=$(mktemp -d /var/tmp/soundsight-usb-build.XXXXXXXX)
fi
printf '%s\n' "$work" > "$output/native-work-path.txt"
printf '%s\n' "$work" >> "$output/native-work-paths.txt"
exec > >(tee "$output/build.log") 2>&1
echo "WORK=$work"
if [ -z "${SS_USB_REUSE_WORK:-}" ]; then
"$host_python" - "$inputs" "$work" <<'PY'
import hashlib,json,pathlib,sys,zipfile
root=pathlib.Path(sys.argv[2])
with zipfile.ZipFile(sys.argv[1]) as archive:
    manifest=json.loads(archive.read('manifest.json'))
    for item in manifest['files']:
        data=archive.read(item['path'])
        assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'], item['path']
    assert archive.read('kernel/running.config')==archive.read('kernel-build/.config')
    for name in archive.namelist():
        if name.startswith('kernel-build/'):
            path=root/name
            assert path.resolve().is_relative_to(root.resolve()), name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(archive.read(name))
PY
tar -xJf "$toolchain" -C "$work" --wildcards \
    '*/bin/*' '*/lib/*' '*/libexec/*' '*/lib64/*' --no-same-owner
fi
compiler=$(find "$work" -path '*/bin/arm-none-linux-gnueabihf-gcc' -print -quit)
test -n "$compiler"
cross=${compiler%gcc}
"$compiler" --version
mkdir -p "$work/gadget"
cp -a "$source_dir/vendor/linux-xlnx/drivers/usb/gadget/." "$work/gadget/"
cp "$source_dir/module.Makefile" "$work/gadget/function/Makefile"
cp "$source_dir/prepare-modpost.mk" "$work/prepare-modpost.mk"
headers=$work/kernel-build
# Restored ZIP inputs have no executable bits; no original board files are edited.
find "$headers/scripts" -type f -name '*.sh' -exec chmod u+x {} +
touch "$headers/include/config/auto.conf" "$headers/include/config/auto.conf.cmd" "$headers/include/generated/autoconf.h"
jobs=$(( ($(getconf _NPROCESSORS_ONLN) + 1) / 2 ))
# The board's header export omits arch/arm/include/generated wrappers. Generate
# those from its own Kbuild lists, without rebuilding the kernel image.
make -C "$headers" ARCH=arm CROSS_COMPILE="$cross" HOSTCFLAGS='-O2 -fcommon' CONFIG_SYSTEM_TRUSTED_KEYRING=n -j"$jobs" archprepare
# Do not build the unrelated host certificate extractor. The input .config and
# generated target autoconf stay intact; these USB modules are unsigned.
make -C "$headers" ARCH=arm CROSS_COMPILE="$cross" HOSTCFLAGS='-O2 -fcommon' CONFIG_SYSTEM_TRUSTED_KEYRING=n -j"$jobs" scripts
# Run the official first recipe of prepare0 without its full-kernel bounds build;
# the board export already supplies its generated bounds/asm-offsets headers.
make -C "$headers" ARCH=arm CROSS_COMPILE="$cross" HOSTCFLAGS='-O2 -fcommon' -j"$jobs" \
    -f Makefile -f "$work/prepare-modpost.mk" ss-usb-modpost
make -C "$headers" ARCH=arm CROSS_COMPILE="$cross" HOSTCFLAGS='-O2 -fcommon' -j"$jobs" M="$work/gadget/function" modules
cp "$work/gadget/function/u_ether.ko" "$work/gadget/function/usb_f_rndis.ko" "$output/"
cp "$work/gadget/function/Module.symvers" "$output/new-Module.symvers"
cp "$headers/.config" "$output/built.config"
for module in "$output"/*.ko; do
    "${cross}readelf" -h "$module"
    "${cross}readelf" -p .modinfo "$module"
done
echo 'BUILD_ONLY: no module load or board validation performed.'
echo "Native intermediate files retained for inspection at $work; clean after review."
