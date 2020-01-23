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
echo Scegli se vuoi eseguire il programma in baackground:
CHOICE /C SNFC /M "(S per Si, N per No, F per Si+forza alpha, C per Cancel)"

set fa=-1
IF ERRORLEVEL 1 SET BT=yes
IF ERRORLEVEL 2 SET BT=no

IF ERRORLEVEL 3 SET BT=no
IF ERRORLEVEL 3 set /p fa="Enter forced alpha: "

IF ERRORLEVEL 4 EXIT 0


python prmk_main.py -c "%file%" -bt %BT% -fa %fa%
pause
