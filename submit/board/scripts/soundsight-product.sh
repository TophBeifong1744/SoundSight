#!/bin/sh
# P1 startup entry. Service orders us after bootpy; automatic axes always OFF.
set -eu
cd -- "$(dirname -- "$0")"
unset PYTHONHOME PYTHONPATH
export XILINX_XRT="${XILINX_XRT:-/usr}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
interpreter=
for candidate in "${PYNQ_PYTHON:-}" /usr/local/share/pynq-venv/bin/python3 python3; do
    [ -n "$candidate" ] || continue
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -B -c 'import PIL, numpy; from pynq import Overlay, MMIO, allocate'; then
        interpreter="$candidate"
        break
    fi
done
if [ -z "$interpreter" ]; then
    echo 'PRODUCT_DEPENDENCY_ERROR: working PYNQ/Pillow/numpy required' >&2
    exit 2
fi
export PYNQ_PYTHON="$interpreter"
if [ "$#" -eq 0 ]; then set -- boot; fi
exec "$interpreter" -B software/screen/product.py "$@"
