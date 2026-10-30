@echo off
setlocal
if "%~1"=="" (
  call "%~dp0rebuild_ps_3d.bat"
  exit /b
)
call "%~dp0setting.bat"
if errorlevel 1 exit /b 2
"%PYTHON_EXE%" -E -s -B -X utf8 "%~dp0..\..\tools\run_vivado.py" %*
set "ss_result=%errorlevel%"
endlocal & exit /b %ss_result%
