/* Bounded CPU-only ECAPA feasibility probe. No MMIO, PYNQ or actuator access.
 * Input: one normalized feature tensor [1, frames, 80], little-endian float32.
 * Reference: 192 float32 values produced by the frozen PyTorch model.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <time.h>
#include "onnxruntime_c_api.h"

static const OrtApi *api;
static int checked(OrtStatus *status) {
    if (!status) return 1;
    fprintf(stderr, "ORT_ERROR=%s\n", api->GetErrorMessage(status));
    api->ReleaseStatus(status);
    return 0;
}
#define CHECK(expr) do { if (!checked(expr)) goto done; } while (0)

static double seconds(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) return -1;
    return (double)t.tv_sec + (double)t.tv_nsec * 1e-9;
}

static int number(const char *text, long low, long high, long *value) {
    char *end = NULL;
    errno = 0;
    long x = strtol(text, &end, 10);
    if (errno || !*text || *end || x < low || x > high) return 0;
    *value = x;
    return 1;
}

static float *read_floats(const char *path, size_t count) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "INPUT_OPEN_FAILED=%s\n", path); return NULL; }
    float *data = malloc(count * sizeof(float));
    if (!data) { fclose(f); return NULL; }
    size_t got = fread(data, sizeof(float), count, f);
    int extra = fgetc(f);
    int bad = ferror(f);
    fclose(f);
    if (got != count || extra != EOF || bad) {
        fprintf(stderr, "INPUT_LENGTH_MISMATCH=%s\n", path);
        free(data); return NULL;
    }
    for (size_t i=0; i<count; ++i) if (!isfinite(data[i])) {
        fprintf(stderr, "INPUT_NONFINITE=%s\n", path);
        free(data); return NULL;
    }
    return data;
}

int main(int argc, char **argv) {
    long frames, threads;
    if (argc != 6 || !number(argv[3], 151, 401, &frames) || !number(argv[5], 1, 2, &threads)) {
        fprintf(stderr, "USAGE: core_bench model.onnx features.f32 frames reference.f32 threads\n");
        return 2;
    }
    const uint32_t endian = 1;
    if (*(const unsigned char *)&endian != 1 || sizeof(float) != 4) return 2;
    float *features = read_floats(argv[2], (size_t)frames*80);
    float *gold = read_floats(argv[4], 192);
    if (!features || !gold) { free(features); free(gold); return 2; }
    double gold_norm = 0;
    for (int i=0;i<192;++i) gold_norm += (double)gold[i]*gold[i];
    if (gold_norm < 1e-12) { free(features); free(gold); return 2; }
    api = OrtGetApiBase()->GetApi(ORT_API_VERSION);
    if (!api) { free(features); free(gold); return 2; }
    OrtEnv *env = NULL;
    OrtSessionOptions *options = NULL;
    OrtSession *session = NULL;
    OrtMemoryInfo *memory = NULL;
    OrtValue *input = NULL, *output = NULL;
    OrtTensorTypeAndShapeInfo *shape = NULL;
    int result = 2;
    double start = seconds();
    if (start < 0) goto done;
    CHECK(api->CreateEnv(ORT_LOGGING_LEVEL_WARNING, "SoundSightCore", &env));
    CHECK(api->CreateSessionOptions(&options));
    CHECK(api->SetIntraOpNumThreads(options, (int)threads));
    CHECK(api->SetInterOpNumThreads(options, 1));
    CHECK(api->SetSessionExecutionMode(options, ORT_SEQUENTIAL));
    CHECK(api->DisableCpuMemArena(options));
    CHECK(api->DisableMemPattern(options));
    CHECK(api->AddSessionConfigEntry(options, "session.intra_op.allow_spinning", "0"));
    CHECK(api->SetSessionGraphOptimizationLevel(options, ORT_ENABLE_ALL));
    CHECK(api->CreateSession(env, argv[1], options, &session));
    double loaded = seconds();
    if (loaded < start) goto done;
    CHECK(api->CreateCpuMemoryInfo(OrtArenaAllocator, OrtMemTypeDefault, &memory));
    const int64_t dims[] = {1, frames, 80};
    CHECK(api->CreateTensorWithDataAsOrtValue(memory, features, (size_t)frames*80*sizeof(float),
           dims, 3, ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT, &input));
    const char *inputs[] = {"features"}, *outputs[] = {"embedding"};
    printf("CORE_ONLY=1 MOTION_COMMANDS=0 ORT=%s THREADS=%ld LOAD_SECONDS=%.6f\n",
           OrtGetApiBase()->GetVersionString(), threads, loaded-start);
    fflush(stdout);
    for (int repeat=0;repeat<2;++repeat) {
        double begin = seconds();
        if (begin < 0) goto done;
        CHECK(api->Run(session, NULL, inputs, (const OrtValue *const *)&input, 1, outputs, 1, &output));
        double end = seconds();
        if (end < begin) goto done;
        CHECK(api->GetTensorTypeAndShape(output, &shape));
        size_t count = 0;
        ONNXTensorElementDataType kind;
        CHECK(api->GetTensorShapeElementCount(shape, &count));
        CHECK(api->GetTensorElementType(shape, &kind));
        if (count != 192 || kind != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT) goto done;
        api->ReleaseTensorTypeAndShapeInfo(shape); shape = NULL;
        float *actual = NULL;
        CHECK(api->GetTensorMutableData(output, (void **)&actual));
        double dot=0, norm=0, max_error=0;
        int pass=1;
        for (int i=0;i<192;++i) {
            if (!isfinite(actual[i])) { pass=0; break; }
            double error=fabs((double)actual[i]-gold[i]);
            if (error>max_error) max_error=error;
            if (error>0.002+0.0002*fabs(gold[i])) pass=0;
            dot+=(double)actual[i]*gold[i]; norm+=(double)actual[i]*actual[i];
        }
        double cosine = norm>1e-12 ? dot/sqrt(norm*gold_norm) : 0;
        if (!isfinite(cosine) || cosine<0.99999) pass=0;
        struct rusage usage;
        if (getrusage(RUSAGE_SELF, &usage)) goto done;
        printf("{\"run\":%d,\"frames\":%ld,\"seconds\":%.6f,\"max_abs_error\":%.9g,\"cosine\":%.9g,\"peak_rss_mib\":%.3f,\"pass\":%s}\n",
               repeat+1, frames, end-begin, max_error, cosine, usage.ru_maxrss/1024.0, pass?"true":"false");
        fflush(stdout);
        api->ReleaseValue(output); output = NULL;
        if (!pass) goto done;
    }
    puts("CORE_BENCH=PASS NOT_END_TO_END=1 MOTION_COMMANDS=0");
    result=0;
done:
    if (shape) api->ReleaseTensorTypeAndShapeInfo(shape);
    if (output) api->ReleaseValue(output);
    if (input) api->ReleaseValue(input);
    if (memory) api->ReleaseMemoryInfo(memory);
    if (session) api->ReleaseSession(session);
    if (options) api->ReleaseSessionOptions(options);
    if (env) api->ReleaseEnv(env);
    free(features); free(gold);
    if (result) fputs("CORE_BENCH=FAIL MOTION_COMMANDS=0\n", stderr);
    return result;
}
