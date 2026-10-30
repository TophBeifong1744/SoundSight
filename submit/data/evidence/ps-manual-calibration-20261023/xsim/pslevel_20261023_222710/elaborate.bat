@echo off
call xelab "work.tb_pslevel" "-L" "xpm" "--debug" "typical" "--relax" "--mt" "16" "-s" "pslevel" "--log" "elaborate.log"
exit /b %errorlevel%
