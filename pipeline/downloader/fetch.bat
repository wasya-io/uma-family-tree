@echo off
rem ========================================================================
rem  JV-Link batch downloader (one-click)
rem  Runs the uv-based fetch script from this folder and writes raw data
rem  to pipeline\input.
rem ========================================================================

rem Move to this batch file's own folder (works regardless of launch dir)
cd /d "%~dp0"

rem Run the fetch script in the uv environment.
rem First run: setup data, full period (option=3, fromtime=all zeros).
uv run jvlink-fetch --out "..\input" --fromtime 00000000000000 --option 3

echo.
echo Done. Press any key to close.
pause >nul
