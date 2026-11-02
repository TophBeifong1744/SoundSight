# S2 hardware recipe

Vivado 2025.2, xc7z020clg400-2. Set XILINX_VIVADO or put vivado.bat on PATH.
`build.bat` creates the project/BD/IP only. `build.bat synth` or `build.bat route` explicitly starts synthesis/implementation. Use a fresh copy for each invocation; existing project/par is rejected.
No EDA was run by this preparation tool. Prior S2 reports describe the original candidate; this repository packaging change has only offline validation.
