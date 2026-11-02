#!/bin/sh
# 独立屏幕入口：只选择本机可用依赖，不下载、不 prepare、不自动开轴。
set -eu
cd -- "$(dirname -- "$0")"
unset PYTHONHOME PYTHONPATH
export XILINX_XRT="${XILINX_XRT:-/usr}"
export PYTHONDONTWRITEBYTECODE=1
need_hardware=1
for argument in "$@"; do
    case "$argument" in --demo|--demo-window|-h|--help) need_hardware=0 ;; esac
done
probe='import PIL, numpy'
if [ "$need_hardware" = 1 ]; then
    probe='import PIL, numpy; from pynq import Overlay, MMIO, allocate'
fi
interpreter=
check_python() {
    if command -v "$1" >/dev/null 2>&1 && "$1" -B -c "$probe"; then
        interpreter="$1"
        return 0
    fi
    printf 'SCREEN_PYTHON_PROBE_FAILED=%s\n' "$1" >&2
    return 1
}
if [ -n "${PYNQ_PYTHON:-}" ]; then
    if ! check_python "$PYNQ_PYTHON"; then
        unset PYNQ_PYTHON
    fi
fi
if [ -z "$interpreter" ]; then
    if check_python /usr/local/share/pynq-venv/bin/python3; then
        :
    elif check_python python3; then
        :
    else
        printf '%s\n' 'STOP: Need Python 3.8+, Pillow/numpy and (hardware only) PYNQ. No downloads or hardware actions performed.' >&2
        exit 2
    fi
fi
export PYNQ_PYTHON="$interpreter"
exec "$interpreter" -B software/screen/ui.py "$@"
