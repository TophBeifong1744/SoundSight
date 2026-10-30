#!/bin/sh
# Build only CPU inference software; never invokes EDA, PYNQ or hardware.
set -eu
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root=$(CDPATH= cd -- "$source_dir/../../.." && pwd)
build=${SS_CORE_BUILD:-"$root/software/build/speaker-core"}
: "${SS_ARM_TOOLCHAIN:?Point to Arm GNU-A Linux hard-float toolchain}"
: "${SS_BUILD_PYTHON:?Point to the host Python interpreter}"
jobs=${SS_BUILD_JOBS:-8}
case "$jobs" in ''|*[!0-9]*) echo INVALID_BUILD_JOBS >&2; exit 2;; esac
[ "$jobs" -ge 1 ] && [ "$jobs" -le 16 ]
src="$build/onnxruntime"
expected=56b660f36940a919295e6f1e18ad3a9a93a10bf7
[ "$(git -C "$src" rev-parse HEAD)" = "$expected" ] || { echo ORT_SOURCE_VERSION_MISMATCH >&2; exit 2; }
cmake -S "$src/cmake" -B "$build/arm" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE="$source_dir/armv7.cmake" \
  -DCMAKE_CXX_FLAGS="-mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard -Wno-error=attributes" \
  -DPython_EXECUTABLE="$SS_BUILD_PYTHON" \
  -DPYTHON_EXECUTABLE="$SS_BUILD_PYTHON" \
  -Donnxruntime_BUILD_SHARED_LIB=ON \
  -Donnxruntime_BUILD_UNIT_TESTS=OFF \
  -Donnxruntime_BUILD_BENCHMARKS=OFF \
  -Donnxruntime_ENABLE_PYTHON=OFF \
  -Donnxruntime_DISABLE_ML_OPS=ON \
  -Donnxruntime_DISABLE_CONTRIB_OPS=ON \
  -Donnxruntime_USE_CUDA=OFF \
  -Donnxruntime_USE_TENSORRT=OFF \
  -Donnxruntime_USE_XNNPACK=OFF \
  -Donnxruntime_ENABLE_TRAINING=OFF \
  -Donnxruntime_ENABLE_TELEMETRY=OFF \
  -Donnxruntime_ENABLE_LTO=OFF \
  -Donnxruntime_ENABLE_CPU_FP16_OPS=OFF \
  -DFLATBUFFERS_BUILD_FLATC=OFF
cmake --build "$build/arm" --target onnxruntime --parallel "$jobs"
"$SS_ARM_TOOLCHAIN/bin/arm-none-linux-gnueabihf-gcc" -std=c99 -O2 -Wall -Wextra -Werror \
  -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard \
  -I"$src/include/onnxruntime/core/session" "$source_dir/core_bench.c" \
  -L"$build/arm" -Wl,-rpath,'$ORIGIN/lib' -lonnxruntime -lm -o "$build/core_bench"
