@echo off
setlocal
for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0setting.txt") do (
  if "%%A"=="VIVADO_ROOT" if not defined VIVADO_ROOT set "VIVADO_ROOT=%%B"
  if "%%A"=="PYTHON_EXE" if not defined PYTHON_EXE set "PYTHON_EXE=%%B"
)
if not exist "%PYTHON_EXE%" exit /b 2
if "%~1"=="batch" goto batch
if "%~1"=="" (
  "%PYTHON_EXE%" -E -s -B -X utf8 "%~dp0..\..\tools\run_sim.py" link --gui
) else (
  "%PYTHON_EXE%" -E -s -B -X utf8 "%~dp0..\..\tools\run_sim.py" %~1 --gui
)
goto done
:batch
"%PYTHON_EXE%" -E -s -B -X utf8 "%~dp0..\..\tools\run_sim.py" %~2
:done
set "ss_result=%errorlevel%"
endlocal & exit /b %ss_result%
