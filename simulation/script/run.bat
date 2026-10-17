@echo off
setlocal
call "%~dp0..\..\project\script\setting.bat"
if errorlevel 1 exit /b 2
if "%~1"=="--check-tools" (
  "%PYTHON_EXE%" -E -s -B -X utf8 "%~dp0..\..\tools\run_sim.py" --check-tools
  goto done
)
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
