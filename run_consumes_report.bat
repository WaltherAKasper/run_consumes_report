@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM === SETTINGS ===
set "SERVER=nord"
set "LOGFILE=WoWCombatLog.txt"
set "EXE=summarize_consumes.exe"

REM === SANITY CHECKS ===
if not exist "%EXE%" (
  echo [ERROR] "%EXE%" not found in %CD%
  exit /b 1
)

if not exist "%LOGFILE%" (
  echo [ERROR] "%LOGFILE%" not found in %CD%
  exit /b 1
)

REM === TIMESTAMPED OUTPUT FOLDER ===
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmmss"') do set "TS=%%i"
set "OUTDIR=%CD%\reports\%TS%"
mkdir "%OUTDIR%" >nul 2>&1

echo [INFO] Output: "%OUTDIR%"

REM === RUN summarize_consumes ===
REM Writes:
REM  - summary.txt (via --write-summary)
REM  - consumable-totals.csv (via --write-consumable-totals-csv)
REM  - prices-web.json (via --expert-write-web-prices) so we can audit prices used
echo [INFO] Running summarize_consumes...
"%CD%\%EXE%" "%LOGFILE%" --prices-server %SERVER% --write-summary --write-consumable-totals-csv --expert-write-web-prices

if errorlevel 1 (
  echo [ERROR] summarize_consumes failed.
  exit /b 1
)

REM === MOVE OUTPUTS INTO REPORT FOLDER (if they exist) ===
if exist "summary.txt" move /y "summary.txt" "%OUTDIR%\summary.txt" >nul
if exist "consumable-totals.csv" move /y "consumable-totals.csv" "%OUTDIR%\consumable-totals.csv" >nul
if exist "prices-web.json" move /y "prices-web.json" "%OUTDIR%\prices-web.json" >nul

REM === DISCORD CARD (HTML -> PNG) ===
set "GUILDNAME=YOUR GUILD NAME"

python "%CD%\discord_card.py" "%OUTDIR%\consumable-totals.csv" "%OUTDIR%\discord-card.html" "%LOGFILE%" "Benig" "%OUTDIR%\summary.txt"

REM Edge headless screenshot (most Windows installs)
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"

if exist "%EDGE%" (
  "%EDGE%" --headless --disable-gpu --window-size=1600,900 --screenshot="%OUTDIR%\discord-card.png" "file:///%OUTDIR:\=/%/discord-card.html"
  echo [INFO] Discord PNG created: %OUTDIR%\discord-card.png
  
  REM Crop PNG manually: top right bottom left (in pixels)
  python "%CD%\crop_png_manual.py" "%OUTDIR%\discord-card.png" "%OUTDIR%\discord-card.png" 0 400 285 0
  if errorlevel 1 (
    echo [WARN] PNG cropping failed - Pillow missing? Install with: pip install Pillow
  ) else (
    echo [INFO] PNG cropped successfully
  )
) else (
  echo [WARN] Edge not found. PNG not created. You can still open discord-card.html and screenshot manually.
)

REM Keep a copy of the log used for traceability (optional)
copy /y "%LOGFILE%" "%OUTDIR%\WoWCombatLog.txt" >nul

REM === VISUALIZE ===
REM Requires Python in PATH. If not installed, the CSV will still be usable in Excel.
echo [INFO] Creating HTML report...
python "%CD%\visualize_consumes.py" "%OUTDIR%\consumable-totals.csv" "%OUTDIR%\report.html"

if errorlevel 1 (
  echo [WARN] Visualization failed (Python missing?). Opening folder anyway.
) else (
  echo [INFO] Report created: %OUTDIR%\report.html
  start "" "%OUTDIR%\report.html"
)

REM Always open the output folder
start "" "%OUTDIR%"
echo [DONE]
endlocal
