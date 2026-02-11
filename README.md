# run_consumes_report

Utilities for building **World of Warcraft raid consume and threat reports** from a `WoWCombatLog.txt` file.

This repository is centered around a Windows-friendly workflow (`run_consumes_report.bat`) that:

1. Runs `summarize_consumes.exe` to calculate per-player consume cost totals.
2. Builds a Discord-friendly raid card and full HTML raid report.
3. Optionally renders/crops PNG screenshots with Microsoft Edge + Pillow.
4. Generates a lightweight bar-chart HTML view from CSV.
5. Generates a TWThreat-based boss-fight threat report.

---

## Repository layout

- `run_consumes_report.bat` – end-to-end Windows pipeline.
- `summarize_consumes.exe` – consume parser binary invoked by the batch script.
- `discord_card.py` – themed Discord card + full report HTML generator.
- `visualize_consumes.py` – compact per-player consume chart HTML generator.
- `generate_threat_report.py` – TWThreat log analyzer for boss fight threat reports.
- `raid_log_filter.py` – helper to isolate one raid segment from multi-raid combat logs.
- `crop_png_manual.py` – PNG crop helper used after Edge screenshots.
- `ThreatLogs/` – expected input location for TWThreat log part files.

---

## Requirements

### Required
- **Windows** (for `.bat` workflow).
- `WoWCombatLog.txt` in the repo root.
- `summarize_consumes.exe` in the repo root.

### Optional (recommended)
- **Python 3.10+** for helper scripts.
- **Pillow** for image cropping:
  - `pip install Pillow`
- **Microsoft Edge** installed (for headless screenshots in batch script).

---

## Quick start (Windows)

From a Command Prompt in this folder:

```bat
run_consumes_report.bat
```

The script creates timestamped output under:

- `reports\YYYY-MM-DD_HHMMSS\`

Typical outputs include:

- `summary.txt`
- `consumable-totals.csv`
- `prices-web.json`
- `discord-card.html`
- `discord-card.png` (if Edge + cropping available)
- `raid-report.html`
- `raid-report.png` (if Edge + cropping available)
- `report.html` (from `visualize_consumes.py`)
- `raid-threat-report.html` (from `generate_threat_report.py`)

---

## Running scripts manually

### 1) Filter a combat log to a single raid

```bash
python raid_log_filter.py WoWCombatLog.txt filtered_log.txt --interactive
```

Useful flags:
- `--list` list detected raids and exit.
- `--raid "Naxxramas"` choose raid non-interactively.

### 2) Build consume bar-chart report from CSV

```bash
python visualize_consumes.py consumable-totals.csv report.html
```

Input CSV is expected as:

- `name,copper,deaths`

(Headers are optional; delimiters `, ; | tab` are auto-detected.)

### 3) Build TWThreat boss fight report

```bash
python generate_threat_report.py \
  --log-dir ThreatLogs \
  --combat-log WoWCombatLog.txt \
  --output ThreatLogs/raid-threat-report.html
```

Notable options:
- `--gap` split fights when snapshot gaps exceed N seconds (default `30`).
- `--min-duration` minimum fight duration in seconds (default `10`).
- `--min-snapshots` minimum snapshots per fight (default `25`).
- `--raid` override inferred raid name.

### 4) Manual PNG cropping helper

```bash
python crop_png_manual.py input.png output.png <top> <right> <bottom> <left>
```

Example:

```bash
python crop_png_manual.py raid-report.png raid-report.png 0 600 780 0
```

---

## Notes

- `discord_card.py` is configured for the guilds **Dark Sun** and **Knights Hospitaller** and expects icon files (`ds-icon.png`, `kh-icon.png`) in this repository.
- The batch script currently passes a logger name (`Tyrchast`) to `discord_card.py`; update this if another character records logs.
- If Edge is unavailable, HTML outputs are still generated and can be screenshotted manually.
