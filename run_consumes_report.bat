@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Always run from this script's directory so relative paths are stable.
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul

REM === SETTINGS ===
set "SERVER=nord"
set "LOGFILE=WoWCombatLog.txt"
set "EXE=summarize_consumes.exe"

REM === SANITY CHECKS ===
if not exist "%EXE%" (
  echo [ERROR] "%EXE%" not found in %CD%
  popd >nul
  exit /b 1
)

if not exist "%LOGFILE%" (
  echo [ERROR] "%LOGFILE%" not found in %CD%
  popd >nul
  exit /b 1
)

REM === TIMESTAMPED OUTPUT FOLDER ===
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmmss"') do set "TS=%%i"
set "OUTDIR=%CD%\reports\%TS%"
mkdir "%OUTDIR%\" >nul 2>&1

echo [INFO] Output: "%OUTDIR%\"

REM === RUN summarize_consumes ===
REM Writes:
REM  - summary.txt (via --write-summary)
REM  - consumable-totals.csv (via --write-consumable-totals-csv)
REM  - prices-web.json (via --expert-write-web-prices) so we can audit prices used
echo [INFO] Running summarize_consumes...
"%CD%\%EXE%" "%LOGFILE%" --prices-server %SERVER% --write-summary --write-consumable-totals-csv --expert-write-web-prices

if errorlevel 1 (
  echo [ERROR] summarize_consumes failed.
  popd >nul
  exit /b 1
)

REM === MOVE OUTPUTS INTO REPORT FOLDER (if they exist) ===
if exist "summary.txt" move /y "summary.txt" "%OUTDIR%\\summary.txt" >nul
if exist "consumable-totals.csv" move /y "consumable-totals.csv" "%OUTDIR%\\consumable-totals.csv" >nul
if exist "prices-web.json" move /y "prices-web.json" "%OUTDIR%\\prices-web.json" >nul

REM === DISCORD CARD (HTML -> PNG) ===
set "GUILDNAME=YOUR GUILD NAME"

python "%CD%\discord_card.py" "%OUTDIR%\\consumable-totals.csv" "%OUTDIR%\\discord-card.html" "%LOGFILE%" "Benig" "%OUTDIR%\\summary.txt" --full-report "%OUTDIR%\\raid-report.html"

REM Edge headless screenshot (most Windows installs)
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"

if exist "%EDGE%" (
  "%EDGE%" --headless --disable-gpu --window-size=1600,900 --screenshot="%OUTDIR%\\discord-card.png" "file:///%OUTDIR:\=/%/discord-card.html"
  echo [INFO] Discord PNG created: %OUTDIR%\\discord-card.png

  if exist "%OUTDIR%\\raid-report.html" (
    "%EDGE%" --headless --disable-gpu --window-size=1800,2200 --screenshot="%OUTDIR%\\raid-report.png" "file:///%OUTDIR:\=/%/raid-report.html"
    echo [INFO] Raid report PNG created: %OUTDIR%\\raid-report.png

    REM Crop raid report PNG manually: top right bottom left (in pixels)
    python "%CD%\crop_png_manual.py" "%OUTDIR%\raid-report.png" "%OUTDIR%\raid-report.png" 0 600 200 0
    if errorlevel 1 (
      echo [WARN] Raid report PNG cropping failed - Pillow missing? Install with: pip install Pillow
    ) else (
      echo [INFO] Raid report PNG cropped successfully
    )
  ) else (
    echo [WARN] Raid report HTML not found. raid-report.png was not created.
  )
  
  REM Crop discord PNG manually: top right bottom left (in pixels)
  python "%CD%\crop_png_manual.py" "%OUTDIR%\\discord-card.png" "%OUTDIR%\\discord-card.png" 0 400 285 0
  if errorlevel 1 (
    echo [WARN] Discord PNG cropping failed - Pillow missing? Install with: pip install Pillow
  ) else (
    echo [INFO] Discord PNG cropped successfully
  )
) else (
  echo [WARN] Edge not found. PNG not created. You can still open discord-card.html and screenshot manually.
)

REM Keep a copy of the log used for traceability (optional)
copy /y "%LOGFILE%" "%OUTDIR%\\WoWCombatLog.txt" >nul

REM === VISUALIZE ===
REM Requires Python in PATH. If not installed, the CSV will still be usable in Excel.
echo [INFO] Creating HTML report...
python "%CD%\visualize_consumes.py" "%OUTDIR%\\consumable-totals.csv" "%OUTDIR%\\report.html"

if errorlevel 1 (
  echo [WARN] Visualization failed (Python missing?). Opening folder anyway.
) else (
  echo [INFO] Report created: %OUTDIR%\\report.html
  start "" "%OUTDIR%\\report.html"
)


REM === TWTHREAT REPORT ===
REM Parses ThreatLogs\TWThreatThreatLog*_part*.txt* and writes a themed raid threat report.
if exist "%CD%\generate_threat_report.py" (
  set "THREAT_LOG_DIR=%CD%\ThreatLogs"
  set "THREAT_REPORT_OUT=%OUTDIR%\raid-threat-report.html"

  if not exist "%THREAT_LOG_DIR%" (
    echo [WARN] TWThreat log directory not found: %THREAT_LOG_DIR%
  )

  echo [INFO] Creating TWThreat report...
  python "%CD%\generate_threat_report.py" --log-dir "%THREAT_LOG_DIR%" --combat-log "%CD%\%LOGFILE%" --output "%THREAT_REPORT_OUT%"
  if errorlevel 1 (
    echo [WARN] TWThreat report generation failed.
  ) else (
    if exist "%THREAT_REPORT_OUT%" (
      echo [INFO] TWThreat report created: %THREAT_REPORT_OUT%
    ) else (
      echo [WARN] TWThreat script succeeded but output file was not found: %THREAT_REPORT_OUT%
    )
  )
) else (
  echo [WARN] generate_threat_report.py not found. Skipping TWThreat report.
)

REM Always open the output folder
start "" "%OUTDIR%\"
echo [DONE]
popd >nul
endlocal
