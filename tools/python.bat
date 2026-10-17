@echo off
setlocal
call "%~dp0..\project\script\setting.bat"
if errorlevel 1 exit /b 2
"%PYTHON_EXE%" -E -s -B -X utf8 %*
set "ss_result=%errorlevel%"
endlocal & exit /b %ss_result%
