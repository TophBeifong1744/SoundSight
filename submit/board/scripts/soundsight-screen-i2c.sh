#!/bin/sh
# 独立内核 I2C 准备入口；安装/位流准备仍由原入口和人类执行。
set -eu
cd -- "$(dirname -- "$0")"
unset PYTHONHOME PYTHONPATH
export XILINX_XRT="${XILINX_XRT:-/usr}"
export PYTHONDONTWRITEBYTECODE=1
interpreter=
probe='import ctypes, pathlib, numpy; from pynq import Overlay, MMIO, allocate'
for argument in "$@"; do
    case "$argument" in -h|--help) probe='import ctypes, pathlib' ;; esac
done
check_python() {
    if command -v "$1" >/dev/null 2>&1 && "$1" -B -c "$probe"; then
        interpreter="$1"
        return 0
    fi
    printf 'SCREEN_I2C_PYTHON_PROBE_FAILED=%s\n' "$1" >&2
    return 1
}
if [ -n "${PYNQ_PYTHON:-}" ]; then
    if ! check_python "$PYNQ_PYTHON"; then unset PYNQ_PYTHON; fi
fi
if [ -z "$interpreter" ]; then
    if check_python /usr/local/share/pynq-venv/bin/python3; then :
    elif check_python python3; then :
    else printf '%s\n' 'STOP: Need Python 3 with ctypes/numpy/PYNQ; no downloads or hardware actions.' >&2; exit 2
    fi
fi
export PYNQ_PYTHON="$interpreter"
exec "$interpreter" -B software/screen/screen_i2c_prepare.py "$@"
