# Board evidence captured on 2026-09-07

These files are the original board photographs supplied by the team for the M0 hardware identity audit. They are evidence of the photographed markings only; they do not prove electrical behavior, pin mapping, PYNQ compatibility, or a successful FPGA build.

| File | Visible evidence | Accepted conclusion | Still not proven |
|---|---|---|---|
| `board-model-label.jpg` | ALIENTEK label, `ATK-DF7010P_7020P` | The photographed kit belongs to the ALIENTEK Navigator 7010/7020P family | Exact core-board order code, speed grade, runtime behavior |
| `baseboard-back-v3-9.jpg` | Baseboard rear silkscreen, `ATK-DF7010/7020P V3.9` | Baseboard revision is V3.9 | Connector electrical state and signal integrity |
| `baseboard-front-core-xc7z020.jpg` | Baseboard front, core-board silkscreen `CF7010B/7020B`, Xilinx Zynq marking `XC7Z020` | The installed SoC is in the Zynq-7020 device family | Full Vivado part including speed grade; Codec identity; PYNQ image compatibility |

## Integrity

| File | SHA-256 |
|---|---|
| `baseboard-back-v3-9.jpg` | `F17CEAFFF1ECD813D7DB9D27983C6557A5C1C663D0564404589C8605A2A14FB8` |
| `baseboard-front-core-xc7z020.jpg` | `F60578411E176429D9297D33AC8DDE44BF4B3A22F4691F0F61F0B1701FD8E394` |
| `board-model-label.jpg` | `15E5B00F0567EFC330BB0124F9EAFDEBDB1BBA5E0CDE388B29CFB730D64D9C08` |

The photographs contain visible QR or barcode information. Review or redact those regions before publishing the evidence in a public competition repository or presentation; keep the original files unchanged for the internal evidence chain.
