@echo off
setlocal
call "%~dp0setting.bat"
if errorlevel 1 exit /b 2
"%PYTHON_EXE%" -E -s -B -X utf8 "%~dp0..\..\tools\rebuild_ps_3d.py" %*
set "ss_result=%errorlevel%"
endlocal & exit /b %ss_result%
