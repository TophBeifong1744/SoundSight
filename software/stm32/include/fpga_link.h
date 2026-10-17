#ifndef SOUNDSIGHT_FPGA_LINK_H
#define SOUNDSIGHT_FPGA_LINK_H
/* S2 host-testable C99 transport. ABI constants and S1 structures stay frozen.
 * One owner, main-loop only: never call concurrently or from an IRQ handler.
 */
#include <stdint.h>
#include "doa_solver.h"

typedef enum {
    SS_OK = 0, SS_NO_FRAME, SS_BUSY, SS_ARGUMENT, SS_BAD_REGISTER,
    SS_IO_ERROR, SS_TIMEOUT, SS_IDENTITY, SS_WIRE_FORMAT, SS_STALE_FRAME,
    SS_DEVICE_FAULT, SS_SOLVER_ERROR, SS_RECOVERY_REQUIRED, SS_NOT_PROBED
} ss_status_t;
typedef enum { SS_BUS_OK = 0, SS_BUS_ERROR, SS_BUS_TIMEOUT } ss_bus_status_t;

/* Transfer exactly 5 bytes full-duplex under ONE CS assertion. Adapter owns CS,
 * Mode0/MSB-first/1MHz and >=8 PL clocks setup/hold. It must bound all waits,
 * wait for actual shift completion, and return CS HIGH on EVERY exit, including
 * error/timeout. Return OK only after all 40 bits and CS release are complete.
 * RX byte0 is unspecified. No CRC/write ACK exists in the frozen wire ABI.
 */
typedef ss_bus_status_t (*ss_transfer_fn)(void *user, const uint8_t tx[5],
                                        uint8_t rx[5], uint32_t timeout_ms);
typedef uint32_t (*ss_now_fn)(void *user); /* monotonic ms, modulo 2^32 */
typedef struct {
    void *user;
    ss_transfer_fn transfer;
    ss_now_fn now_ms;
    uint32_t transfer_timeout_ms, operation_timeout_ms; /* 0 < each < 2^31 */
} ss_bus_t;

typedef enum { SS_RUN_REAL = 0, SS_RUN_BIST_REJECT, SS_RUN_BIST_PASS } ss_run_t;
typedef enum { SS_RELEASE = 0, SS_CONSUME } ss_finish_t;

/* Treat fields as read-only diagnostics outside the implementation. Re-init
 * resets sequence history: use only for a deliberate new session after reset,
 * not as a way to bypass a stale-frame or recovery error.
 */
typedef struct {
    ss_bus_t bus;
    uint32_t last_consumed_id, locked_id, snapshot_status, faults;
    uint8_t probed, identity_verified, recovery_required, locked, have_consumed;
    ss_status_t last_error, revoke_result;
    doa_status_t solver_status;
} ss_link_t;

ss_status_t ss_init(ss_link_t *link, const ss_bus_t *bus);
/* Exact magic/ABI, revoke permit, set watchdog=0 and verify. Does not enable PL.
 * Also used by recover; probing never erases frame sequence history. */
ss_status_t ss_probe(ss_link_t *link);
/* Disable preserving SYS_CTRL bits, return BUSY while draining/queue occupied.
 * Configure only when empty, fault-free. All runs keep movement disabled. */
ss_status_t ss_start(ss_link_t *link, ss_run_t mode);
ss_status_t ss_stop(ss_link_t *link);
/* STOP latches internally in PL; explicitly disable preserving mode bits, then
 * verify before declaring producer idle. Does not clear sticky faults. */
ss_status_t ss_disable(ss_link_t *link);
/* Explicit acknowledgement of ONLY an isolated STOP fault, after disabled,
 * drain-free and motion-off readbacks. Never clears any other fault. BUSY if
 * still enabled/draining. Does not restart, consume, or reset frame history. */
ss_status_t ss_acknowledge_stop(ss_link_t *link);
ss_status_t ss_read_register(ss_link_t *link, uint32_t address, uint32_t *value);
/* 39 transfers on success; frame is fully validated, lock stays held. */
ss_status_t ss_acquire_frame(ss_link_t *link, doa_frame_input_t *frame);
/* One transfer. Never automatically retried. RELEASE permits diagnostic reread. */
ss_status_t ss_finish_frame(ss_link_t *link, ss_finish_t how);
/* Whole read/solve/consume operation: exactly 40 transfers on success. Both
 * outputs are cleared on any error/NO_FRAME. Algorithm rejection is SS_OK with
 * direction_valid=0. This diagnostic API submits NO action, even if S1's
 * servo_cmd_valid is true. Its result must NOT later be committed: consumed.
 */
ss_status_t ss_poll_solve(ss_link_t *link, const doa_servo_config_t *servo,
                          doa_frame_input_t *frame, doa_solve_output_t *result);
/* Explicit recovery: probe/revoke, read actual lock, RELEASE if present, verify
 * release. Does NOT replay CONSUME, clear faults, enable PL or reset frame IDs.
 * Malformed/duplicate data may remain READY; diagnose/reset source explicitly.
 */
ss_status_t ss_recover(ss_link_t *link);
#endif
