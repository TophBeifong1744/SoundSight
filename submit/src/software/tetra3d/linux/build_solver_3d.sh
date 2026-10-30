#!/bin/sh
# Native build on PYNQ, or set CC to the intended Linux cross compiler.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
common=$(CDPATH= cd -- "$here/../../common" && pwd)
core=$(CDPATH= cd -- "$here/../core" && pwd)
"${CC:-gcc}" -std=c99 -O2 -Wall -Wextra -Wconversion -Wshadow -Werror -pedantic \
  -fPIC -shared -I"$common" -I"$common/s1" -I"$core" \
  "$here/ss_solver_3d_bridge.c" "$common/s1/doa_solver.c" \
  "$core/doa_solver_3d.c" "$core/doa_geometry.c" \
  "$core/doa_target_3d.c" -lm -o "$here/libss_solver_3d.so"
printf '%s\n' "Built for the selected compiler target: $here/libss_solver_3d.so"

