@echo off
cd /d %~dp0
rem just the last one is selected, don't know if it's worth it to support selection
FOR %%I in (*.json) DO (
set file=%%I
)
echo.
echo -----------------------
echo server config selected:  %file%
echo -----------------------
echo.

pause

python prmk_main.py -c "%file%" -bt no
pause
