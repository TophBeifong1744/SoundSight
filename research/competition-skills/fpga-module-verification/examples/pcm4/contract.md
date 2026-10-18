# Existing module contract and provenance

Uses the unmodified historical pcm4_signext_pack.v beside this contract, attributed to C's C-RTL-003 delivery. It was restored byte-for-byte from the archived examples-r2 simulation input; provenance.json records its origin. The license is MIT; retain C attribution. This is a standalone historical Skill-use example, not current SoundSight production RTL, a new request for C acceptance, or a microphone/room simulation.

Pure combinational logic; no clock/reset/ready/valid. SAMPLE_WIDTH supports 2..32. Four signed inputs independently sign-extend to four 32-bit words, mic0 in bits31:0 and mic3 in127:96. All two's-complement bit patterns legal. No rounding, sample-numbering or synchronization claim.

TB interprets values through a signed 64-bit integer, compares each resulting 32-bit word with case inequality, covers width2/24/32, extrema and 64 deterministic patterns (seed0x76543210). 66 groups x4 words x3 widths = 792 comparisons. This is HDL code-pattern simulation, not four-microphone acoustic simulation, FPGA synthesis, board or system acceptance.

The case resolves every input inside this example directory. Standalone export includes this exact permitted module and its attribution; no old repository, Git history or external archive is needed to run it.
