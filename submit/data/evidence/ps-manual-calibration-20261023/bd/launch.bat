@echo off
call "F:\AMD\2025.2\Vivado\bin\vivado.bat" "-mode" "batch" "-notrace" "-source" "E:\Users\Toph Beifong\Documents\GitHub\SoundSight\simulation\work\hz5supiji\check.tcl" "-log" "E:\Users\Toph Beifong\Documents\GitHub\SoundSight\document\evidence\ps-manual-calibration-20261023\bd\vivado.log" "-nojournal"
exit /b %errorlevel%
