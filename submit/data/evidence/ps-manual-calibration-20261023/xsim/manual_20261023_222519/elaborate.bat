@echo off
call xelab "work.tb_manual" "-L" "xpm" "--debug" "typical" "--relax" "--mt" "16" "-s" "manual" "--log" "elaborate.log"
exit /b %errorlevel%
