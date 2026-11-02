@echo off
setlocal
if defined XILINX_VIVADO set "PATH=%XILINX_VIVADO%\bin;%PATH%"
where vivado.bat >nul 2>nul
if errorlevel 1 exit /b 2
pushd "%~dp0"
if "%~1"=="" goto prepare
if "%~1"=="synth" goto build
if "%~1"=="route" goto build
echo Usage: build.bat [synth or route]
popd
exit /b 2
:prepare
call vivado.bat -mode batch -source project.tcl -log prepare.log -journal prepare.jou
goto done
:build
call vivado.bat -mode batch -source build.tcl -log build.log -journal build.jou -tclargs %1
:done
set "ss_exit=%ERRORLEVEL%"
popd
exit /b %ss_exit%
