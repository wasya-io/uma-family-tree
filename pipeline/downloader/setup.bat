@echo off
rem ========================================================================
rem  JV-Link initial setup download (one-click)
rem  Downloads pedigree data in TWO separate processes to avoid the
rem  win32com/JVGets memory leak that exhausts RAM on a single long run.
rem    1) DIFF  -> UM.dat (racehorse master)
rem    2) BLOD  -> HN.dat / SK.dat / BT.dat (pedigree/breeding/lineage)
rem  Each process exits and the OS reclaims all COM memory before the next.
rem ========================================================================

cd /d "%~dp0"

echo === [1/2] DIFF (UM) ===
uv run jvlink-fetch --out "..\input" --dataspec DIFF --fromtime 00000000000000 --option 4
if errorlevel 1 goto :error

echo.
echo === [2/2] BLOD (HN/SK/BT) ===
uv run jvlink-fetch --out "..\input" --dataspec BLOD --fromtime 00000000000000 --option 4
if errorlevel 1 goto :error

echo.
echo All done. Files written to pipeline\input.
goto :end

:error
echo.
echo A step failed (see messages above).

:end
echo Press any key to close.
pause >nul
