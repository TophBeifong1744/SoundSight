#!/bin/sh
# Native build on PYNQ, or set CC to the intended Linux cross compiler.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
common=$(CDPATH= cd -- "$here/../common" && pwd)
"${CC:-gcc}" -std=c99 -O2 -Wall -Wextra -Wconversion -Wshadow -Werror -pedantic \
  -fPIC -shared -I"$common" -I"$common/s1" -I"$common/s1_3d" \
  "$here/ss_solver_3d_bridge.c" "$common/s1/doa_solver.c" \
  "$common/s1_3d/doa_solver_3d.c" "$common/s1_3d/doa_geometry.c" \
  "$common/s1_3d/doa_target_3d.c" -lm -o "$here/libss_solver_3d.so"
printf '%s\n' "Built for the selected compiler target: $here/libss_solver_3d.so"
