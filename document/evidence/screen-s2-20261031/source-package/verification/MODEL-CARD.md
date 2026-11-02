# Host boundary model card

Version: S2, 2026-10-31. Author: screen_verify. Purpose: test Linux-I2C boundary assembly, fail-closed ownership, UI lifecycle ordering and installer rollback. It does not model I2C electrical timing, GT911 silicon, FPGA cycle latency or Cadence kernel scheduling.

## Independent bases

- Linux `include/uapi/linux/i2c.h` and `i2c-dev.h`: address/flags/length/pointer layout; native alignment; I2C_M_RD; combined I2C_RDWR and exact message count. Tests declare their own ctypes structures and decode actual product arguments. Windows x64 layout is executed; ARM native layout remains a board check.
- Board read-only evidence: `/amba/i2c@e0004000`, `cdns,i2c-r1p10`, clock/IRQ identity, initially disabled with no adapters. Fixtures use those DT properties and synthetic bus 7 to prevent dependence on guessed numbering. Windows symlink privilege is unavailable, so explicit Path.resolve aliases model sysfs symlinks. Real Linux links/devices/locks/ioctl are not exercised.
- Lifecycle requirements: acquire/check bus before GPIO/reset/probe, enable DMA before lock wait, first-frame acknowledgment before backlight, stop backend/DMA before closing bus, offline demo must not acquire hardware. Mocks record calls while real ui.main controls ordering. They cannot establish real hardware safe states.
- Installer: actual baseline ZIP + S1 payload and three actual software variants; immutable original bytes and independent filesystem snapshots are the oracle. Faults are deterministic one-shot os.replace failures at each replacement position. Process death/power loss/fsync durability on the SD filesystem are not modeled.

## Official HWH parser attribution

`vendor_hwh_parser_pynq270.py` is the official Xilinx PYNQ v2.7.0 `pynq/pl_server/hwh_parser.py` source.

Source: https://github.com/Xilinx/PYNQ/blob/v2.7.0/pynq/pl_server/hwh_parser.py

Local SHA256: `6b210f365ca061b7440e1c43afc4b1445c61161a4f9be6daf849edeaef03c386`.

Copyright (c) 2021, Xilinx, Inc. Full BSD 3-clause copyright, conditions and disclaimer are retained verbatim at the top of the distributed source. Keep that header with redistributed test assets. No additional license download is required.

Tests supply only the PYNQ CPU architecture flags and execute this parser on the actual S2 generated HWH, then call product metadata checks. They do not replace HWH with a hand-authored parameter dictionary. Negative cases alter a copy of the XML's EMIO parameter or connection and require rejection. Real installed PYNQ integration remains NOT RUN.

## Checker sensitivity and limits

Five isolated in-memory negative variants each fail the designated assertion without test errors: accept a short transfer; remove read flag; ignore a claimed runtime client; perform GPIO access before ownership; bypass PS EMIO parameter validation. Details and assertion traces are in `canary-results.json`.

This is a host-software model, not an RTL functional simulation model. No cycle scoreboard, HDL coverage, metastability claim or SIMULATION_PASS is applicable. The model author requires a separate reader to accept the evidence for release.
