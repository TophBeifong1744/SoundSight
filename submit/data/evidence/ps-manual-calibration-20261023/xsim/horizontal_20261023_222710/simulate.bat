@echo off
call xsim "horizontal" "--maxdeltaid" "1000" "--onerror" "quit" "--tclbatch" "run.tcl" "--log" "simulate.log"
exit /b %errorlevel%
