#!/bin/sh
# 在目标PYNQ的ARM Linux里运行；不使用Windows DLL、不下载bit或启动动作。
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
common_dir=$(CDPATH= cd -- "$script_dir/../common" && pwd)
"${CC:-gcc}" -std=c99 -O2 -Wall -Wextra -Wconversion -Wshadow -Werror -pedantic \
  -fPIC -shared -I"$common_dir" -I"$common_dir/s1" \
  "$script_dir/ss_solver_bridge.c" "$common_dir/s1/doa_solver.c" \
  -lm -o "$script_dir/libss_solver.so"
printf '%s\n' "Solver library built for selected compiler: $script_dir/libss_solver.so"
