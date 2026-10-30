#!/bin/sh
# 板端短入口：仅配置本进程环境，不修改系统启动脚本。
set -eu
cd -- "$(dirname -- "$0")"
# sudo/其他开发环境可能遗留Python搜索路径；仅清理本启动进程及子进程。
unset PYTHONHOME PYTHONPATH
export XILINX_XRT="${XILINX_XRT:-/usr}"
export PYTHONIOENCODING=ascii:backslashreplace
export PYTHONDONTWRITEBYTECODE=1

# 帮助和门限文件操作不需要PYNQ。硬件入口必须先实际导入，不能只看-x。
need_pynq=1
case "${1:-}" in ''|check|level|filter|servo-config|servo-geometry|speaker-config|speaker-import|speaker-check|speaker-stats|speaker-list|speaker-select|-h|--help) need_pynq=0 ;; esac
for argument in "$@"; do
    case "$argument" in -h|--help) need_pynq=0 ;; esac
done
probe='import sys; print("PYTHON_EXE=" + sys.executable, flush=True)'
if [ "$need_pynq" = 1 ]; then
    probe='import sys; from pynq import Overlay, MMIO, Clocks; print("PYTHON_EXE=" + sys.executable, flush=True); print("PYNQ_IMPORT_OK=1", flush=True)'
fi
check_python() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'PYTHON_NOT_FOUND=%s\n' "$1" >&2
        return 1
    fi
    if "$1" -B -c "$probe"; then
        interpreter="$1"
        return 0
    fi
    printf 'PYTHON_PROBE_FAILED=%s\n' "$1" >&2
    return 1
}
interpreter=
if [ -n "${PYNQ_PYTHON:-}" ]; then
    # 旧环境变量只是候选提示；失效时自动探测，不让历史配置堵住启动。
    if ! check_python "$PYNQ_PYTHON"; then
        printf 'IGNORING_STALE_PYNQ_PYTHON=%s AUTO_DETECT=1\n' "$PYNQ_PYTHON" >&2
        unset PYNQ_PYTHON
    fi
fi
if [ -z "$interpreter" ]; then
    if check_python /usr/local/share/pynq-venv/bin/python3; then
        :
    elif check_python python3; then
        :
    else
        printf '%s\n' 'STOP: No usable Python environment. Set PYNQ_PYTHON to a working PYNQ interpreter. No board helper started.' >&2
        exit 1
    fi
fi
# 子进程继承本次已验证的选择；不改登录配置，也不需要用户手动unset。
export PYNQ_PYTHON="$interpreter"
exec "$interpreter" -B software/tetra3d/linux/board_3d.py "$@"
