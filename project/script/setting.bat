@echo off
rem Configure this machine only; no user/system PATH edits.
if not defined VIVADO_ROOT set "VIVADO_ROOT=F:\AMD\2025.2\Vivado"
if not defined PYTHON_EXE set "PYTHON_EXE=C:\Python314\python.exe"
set "PATH=%VIVADO_ROOT%\bin;%PATH%"
if not exist "%VIVADO_ROOT%\bin\vivado.bat" exit /b 2
if not exist "%PYTHON_EXE%" exit /b 2
exit /b 0
