#ifndef SS_DOA_GEOMETRY_H
#define SS_DOA_GEOMETRY_H
#include "doa_solver_3d.h"
#define DOA_GEOMETRY_SCHEMA UINT32_C(1)
#define DOA_GEOMETRY_SOURCE_BYTES 64
/* Local configuration only, never serialized as a wire ABI structure. */
typedef enum { DOA_GEOMETRY_NOMINAL=0, DOA_GEOMETRY_MEASURED=1,
               DOA_GEOMETRY_SYNTHETIC=2 } doa_geometry_source_t;
typedef struct { uint8_t channel; float xyz_mm[3]; } doa_geometry_mic_t;
typedef struct {
    uint32_t schema, revision;
    doa_geometry_source_t provenance;
    char source_id[DOA_GEOMETRY_SOURCE_BYTES]; /* printable ASCII, NUL terminated */
    doa_geometry_mic_t mic[4]; /* physical rows; channel maps to wire channel */
    float sample_rate_hz, sound_speed_m_s;
    /* Per-mic radial position-error upper bound, not stddev. -1 = unknown.
     * MEASURED requires >0. Declared provenance is NOT verified calibration. */
    float position_error_mm;
} doa_geometry_record_t;
typedef enum {
    DOA_GEOMETRY_OK=0, DOA_GEOMETRY_ARGUMENT, DOA_GEOMETRY_METADATA,
    DOA_GEOMETRY_CHANNEL, DOA_GEOMETRY_RANGE, DOA_GEOMETRY_WINDOW,
    DOA_GEOMETRY_SINGULAR, DOA_GEOMETRY_CONDITION
} doa_geometry_status_t;
typedef struct {
    doa_geometry_status_t status;
    uint8_t valid, uncertainty_known, bad_pair; /* bad_pair=255 when inapplicable */
    float distance_mm[6], nominal_delay_samples[6], bounded_delay_samples[6];
    float normal_condition; /* infinity-norm condition of all-six normal matrix */
} doa_geometry_report_t;
void doa_geometry_nominal(doa_geometry_record_t *);
/* Pure C99, no I/O. Output config cleared on failure, report may be partial.
 * Pairs remain 01,02,03,12,13,23. Reorders coordinates, NEVER frame features.
 * Uses existing solver thresholds; all-six preflight does not replace the
 * solver's per-frame subset/rank/condition checks. Outputs must not alias. */
doa_geometry_status_t doa_geometry_build(const doa_geometry_record_t *,
                                        doa3d_config_t *,doa_geometry_report_t *);
#endif

