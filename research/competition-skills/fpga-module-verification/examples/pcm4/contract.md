# Existing module contract and provenance

Uses the unmodified project module rtl/acquisition/pcm4_signext_pack.v, attributed to C's C-RTL-003 delivery; active-source normalized SHA256 d4e30cbc2f76009aea781c8baef5752c248d8e7aac8b84ec62fea6ad80703d7c (CRLF to LF), recorded in sim/modules.json. The project source license is MIT; retain C attribution. This new TB is a Skill-use example, not a repeated request for C acceptance or a new microphone/room simulation.

Pure combinational logic; no clock/reset/ready/valid. SAMPLE_WIDTH supports 2..32. Four signed inputs independently sign-extend to four 32-bit words, mic0 in bits31:0 and mic3 in127:96. All two's-complement bit patterns legal. No rounding, sample-numbering or synchronization claim.

TB interprets values through a signed 64-bit integer, compares each resulting 32-bit word with case inequality, covers width2/24/32, extrema and 64 deterministic patterns (seed0x76543210). 66 groups x4 words x3 widths = 792 comparisons. This is HDL code-pattern simulation, not four-microphone acoustic simulation, FPGA synthesis, board or system acceptance.

The case references the repository source rather than storing a second maintained production copy. For standalone export, include that exact permitted module once with attribution and rewrite the case source path; re-run after exporting.
