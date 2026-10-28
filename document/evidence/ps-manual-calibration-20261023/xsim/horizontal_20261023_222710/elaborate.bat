@echo off
call xelab "work.tb_horizontal" "-L" "xpm" "--debug" "typical" "--relax" "--mt" "16" "-s" "horizontal" "--log" "elaborate.log"
exit /b %errorlevel%
