#ifndef SS_SPATIAL_H
#define SS_SPATIAL_H
#include "fpga_link.h"
#include "doa_dispatch.h"
/* Diagnostic-only composition. Same S2 wire contract, one shared acquisition /
 * solve / CONSUME deadline. DOA_OK algorithm rejections consume once; transport
 * or solver API errors quarantine without blind retry. Output only on SS_OK.
 * Config must remain stable during the call. No actuator output or submission.
 * All users must use the same SS_DOA_PROFILE; compile/link only in 3D target.
 */
#if SS_DOA_PROFILE == SS_DOA_TETRAHEDRAL
ss_status_t ss_spatial_poll(ss_link_t *link,const doa3d_config_t *config,
                           doa_frame_input_t *frame,doa_dispatch_output_t *output);
#endif
#endif
