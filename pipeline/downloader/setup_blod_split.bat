@echo off
rem ========================================================================
rem  BLOD (pedigree: HN/SK/BT) download, SPLIT BY PERIOD into many processes.
rem
rem  A single process for all BLOD data leaks COM memory (win32com/JVGets)
rem  and eventually freezes/crashes. Splitting the period into chunks and
rem  running each as its OWN process lets the OS fully reclaim memory
rem  between chunks. Each chunk appends to the existing .dat files.
rem
rem  Uses option=4 (setup data, no dialog) with fromtime "START-END" ranges.
rem  IMPORTANT: option=1 (normal/diff data) returns nothing right after
rem  setup because it only yields incremental updates. Historical full data
rem  lives in the SETUP dataset, so option=4 (or 3) is required here.
rem  Per spec, option=3/4 also honors the "START-END" period in fromtime.
rem
rem  NOTE: The FIRST chunk uses no --append (fresh write); the rest append.
rem ========================================================================

cd /d "%~dp0"
set OUT=..\input

echo === BLOD chunk 1/8 : 1986-1990 (fresh) ===
uv run jvlink-fetch --out "%OUT%" --dataspec BLOD --option 4 --fromtime 19860101000000-19901231235959
if errorlevel 1 goto :error

echo === BLOD chunk 2/8 : 1991-1995 ===
uv run jvlink-fetch --out "%OUT%" --dataspec BLOD --option 4 --fromtime 19910101000000-19951231235959 --append
if errorlevel 1 goto :error

echo === BLOD chunk 3/8 : 1996-2000 ===
uv run jvlink-fetch --out "%OUT%" --dataspec BLOD --option 4 --fromtime 19960101000000-20001231235959 --append
if errorlevel 1 goto :error

echo === BLOD chunk 4/8 : 2001-2005 ===
uv run jvlink-fetch --out "%OUT%" --dataspec BLOD --option 4 --fromtime 20010101000000-20051231235959 --append
if errorlevel 1 goto :error

echo === BLOD chunk 5/8 : 2006-2010 ===
uv run jvlink-fetch --out "%OUT%" --dataspec BLOD --option 4 --fromtime 20060101000000-20101231235959 --append
if errorlevel 1 goto :error

echo === BLOD chunk 6/8 : 2011-2015 ===
uv run jvlink-fetch --out "%OUT%" --dataspec BLOD --option 4 --fromtime 20110101000000-20151231235959 --append
if errorlevel 1 goto :error

echo === BLOD chunk 7/8 : 2016-2020 ===
uv run jvlink-fetch --out "%OUT%" --dataspec BLOD --option 4 --fromtime 20160101000000-20201231235959 --append
if errorlevel 1 goto :error

echo === BLOD chunk 8/8 : 2021-2035 ===
uv run jvlink-fetch --out "%OUT%" --dataspec BLOD --option 4 --fromtime 20210101000000-20351231235959 --append
if errorlevel 1 goto :error

echo.
echo BLOD done. HN/SK/BT written to %OUT%.
goto :end

:error
echo.
echo A chunk failed (see messages above). You can re-run; completed chunks
echo already wrote their data. Adjust the failing chunk's period if needed.

:end
echo Press any key to close.
pause >nul
