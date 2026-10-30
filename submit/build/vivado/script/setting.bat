@echo off
rem Only bootstrap Python; tool_config.py resolves Vivado/GCC when needed.
rem Read data, never CALL the local file. Environment overrides local settings.
if exist "%~dp0..\..\tools.local.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%~dp0..\..\tools.local.env") do (
    if "%%A"=="PYTHON_EXE" if not defined PYTHON_EXE set "PYTHON_EXE=%%B"
  )
)
if not defined PYTHON_EXE (
  for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
)
if not defined PYTHON_EXE goto missing_python
if not exist "%PYTHON_EXE%" goto missing_python
exit /b 0
:missing_python
echo Python 3 not found. Set PYTHON_EXE in tools.local.env or environment, or add Python to PATH. 1>&2
exit /b 2
