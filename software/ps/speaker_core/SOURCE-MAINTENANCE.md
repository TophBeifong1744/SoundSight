# 声纹原生计算与 Python 适配

本目录维护当前 SD 包所用声纹计算程序的源码。`pipeline_backend.c` 包含 `core_bench.c`、`stream_frontend.h`、`detail_profile.h`；Python 入口为 `pipeline_bench.py`、`short_bench.py`、`stream_bench.py`，CPU 诊断使用 `cpu_profile_bench.py`。上层生命周期和目标配置在父目录，三维联合入口在 `software/tetra3d/linux`。

这些源码与模型资产分开：运行仍需要配套 ARM `pipeline_backend`、ONNX Runtime 1.17.3、前端系数、CP1/VF1 模型和用户原有登记模板。不要将缺少模板或模型解释为可以跳过声纹门控；`follow-sound` 是用户显式选择的纯声源模式。来源和第三方许可见 `licenses/`。

## 构建边界

`build-lock.json` 固定 ORT 版本和依赖来源。`prepare_dependencies.py --source <ORT源码> --cache <缓存>` 仅准备依赖；`--verify-only` 只校验已有缓存。`build_runtime.sh` 使用 `SS_ARM_TOOLCHAIN`、`SS_BUILD_PYTHON` 和可选 `SS_CORE_BUILD`，构建 ARM ORT 和基础 `core_bench`，**不会自动生成当前流式 pipeline_backend**。

已有匹配的 ORT 头文件和 ARM 库时，当前流式后端的编译参数如下（Linux 构建主机，路径由使用者提供）：

```sh
"$SS_ARM_TOOLCHAIN/bin/arm-none-linux-gnueabihf-gcc" \
  -std=c99 -O2 -Wall -Wextra -ffp-contract=off \
  -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard \
  -DSS_MIN_CHUNK_SAMPLES=8000 -DSS_STREAMING \
  -I "$ORT_SOURCE/include/onnxruntime/core/session" \
  software/ps/speaker_core/pipeline_backend.c \
  -L "$ORT_ARM_LIB" -lonnxruntime -lm \
  -Wl,-rpath,'$ORIGIN/lib' -o "$OUTPUT_DIR/pipeline_backend"
```

先创建输出目录，配套库放在输出旁的 `lib/`。这是已有编译方式的说明，本次源码同步没有重建 ORT、推理模型或替换现有 ARM 二进制。替换后端前仍需复做对应数值对照。不要直接使用不同模型、ABI 或前处理系数。
