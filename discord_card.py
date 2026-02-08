#!/usr/bin/env python3
"""
Discord Consume Card Generator
Generates a stylish HTML card for raid consume reports.

Features:
- Filters to only show members of specified guilds
- Automatically detects pets and excludes them
- Auto-detects raid name from combat log
- Embeds guild icons with smooth circular masks
- Counts "You die." events and attributes them to the logger's character
- Displays Sunder Armor race from summary.txt
"""

import csv
import sys
import re
import base64
from pathlib import Path
from datetime import datetime
from html import escape
import argparse

# =============================================================================
# CONFIGURATION - Edit these paths to your guild icons
# =============================================================================
GUILD_CONFIG = {
    "Dark Sun": {
        "icon_path": "ds-icon.png",  # Path to Dark Sun icon
        "glow_color": "rgba(212, 175, 55, 0.3)",  # Gold glow
    },
    "Knights Hospitaller": {
        "icon_path": "kh-icon.png",  # Path to Knights Hospitaller icon  
        "glow_color": "rgba(200, 200, 200, 0.25)",  # Silver glow
    },
}

# Server name for the badge
SERVER_NAME = "Nordanaar"
LOG_TIMESTAMP_RE = re.compile(r"^(\d{1,2})/(\d{1,2}) (\d{1,2}):(\d{2}):(\d{2})\.(\d{3})")

RAID_BOSSES = {
    "Naxxramas": [
        "Anub'Rekhan",
        "Grand Widow Faerlina",
        "Maexxna",
        "Noth the Plaguebringer",
        "Heigan the Unclean",
        "Loatheb",
        "Instructor Razuvious",
        "Gothik the Harvester",
        "The Four Horsemen",
        "Patchwerk",
        "Grobbulus",
        "Gluth",
        "Thaddius",
        "Sapphiron",
        "Kel'Thuzad",
    ],
    "Onyxia's Lair": ["Onyxia"],
    "Molten Core": [
        "Lucifron",
        "Magmadar",
        "Gehennas",
        "Garr",
        "Shazzrah",
        "Baron Geddon",
        "Golemagg the Incinerator",
        "Sulfuron Harbinger",
        "Majordomo Executus",
        "Ragnaros",
    ],
    "Blackwing Lair": [
        "Razorgore the Untamed",
        "Vaelastrasz the Corrupt",
        "Broodlord Lashlayer",
        "Firemaw",
        "Ebonroc",
        "Flamegor",
        "Chromaggus",
        "Nefarian",
    ],
    "Temple of Ahn'Qiraj": [
        "The Prophet Skeram",
        "Battleguard Sartura",
        "Fankriss the Unyielding",
        "Princess Huhuran",
        "Twin Emperors",
        "C'Thun",
        "Viscidus",
        "Ouro",
        "Lord Kri",
        "Princess Yauj",
        "Vem",
    ],
    "Ruins of Ahn'Qiraj": [
        "Kurinnaxx",
        "General Rajaxx",
        "Moam",
        "Buru the Gorger",
        "Ayamiss the Hunter",
        "Ossirian the Unscarred",
    ],
    "Zul'Gurub": [
        "High Priest Venoxis",
        "High Priestess Jeklik",
        "High Priestess Mar'li",
        "High Priest Thekal",
        "High Priestess Arlokk",
        "Jin'do the Hexxer",
        "Hakkar",
    ],
    "Zul'Aman": [
        "Akil'zon",
        "Nalorakk",
        "Jan'alai",
        "Halazzi",
        "Hex Lord Malacrass",
        "Zul'jin",
    ],
    "Sunwell Plateau": [
        "Kalecgos",
        "Brutallus",
        "Felmyst",
        "Eredar Twins",
        "M'uru",
        "Kil'jaeden",
    ],
    "Black Temple": [
        "High Warlord Naj'entus",
        "Supremus",
        "Shade of Akama",
        "Teron Gorefiend",
        "Gurtogg Bloodboil",
        "Reliquary of Souls",
        "Mother Shahraz",
        "The Illidari Council",
        "Illidan Stormrage",
    ],
    "Karazhan": [
        "Attumen the Huntsman",
        "Moroes",
        "Maiden of Virtue",
        "The Curator",
        "Shade of Aran",
        "Terestian Illhoof",
        "Netherspite",
        "Nightbane",
        "Prince Malchezaar",
    ],
    "Gruul's Lair": ["High King Maulgar", "Gruul the Dragonkiller"],
    "Magtheridon's Lair": ["Magtheridon"],
    "Serpentshrine Cavern": [
        "Hydross the Unstable",
        "The Lurker Below",
        "Leotheras the Blind",
        "Fathom-Lord Karathress",
        "Morogrim Tidewalker",
        "Lady Vashj",
    ],
    "Tempest Keep": [
        "Al'ar",
        "Void Reaver",
        "High Astromancer Solarian",
        "Kael'thas Sunstrider",
    ],
    "Battle for Mount Hyjal": [
        "Rage Winterchill",
        "Anetheron",
        "Kaz'rogal",
        "Azgalor",
        "Archimonde",
    ],
}


def copper_to_gold_rounded(copper: int) -> int:
    """Convert copper to gold, rounding to the nearest whole gold."""
    return int((copper / 10000) + 0.5)


def copper_to_gsc_short(copper: int) -> str:
    """Convert copper to rounded gold only (no silver/copper)."""
    g = copper_to_gold_rounded(copper)
    return f"{g}g"


def safe_int(x, default=0):
    """Safely convert to integer."""
    try:
        return int(str(x).strip().replace(",", ""))
    except:
        return default


def load_icon_base64(icon_path: Path) -> str:
    """Load an icon file and return base64 encoded string."""
    if not icon_path.exists():
        return ""
    with open(icon_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def parse_log_timestamp(line: str) -> datetime | None:
    match = LOG_TIMESTAMP_RE.match(line)
    if not match:
        return None
    month, day, hour, minute, second, millis = (int(g) for g in match.groups())
    return datetime(datetime.now().year, month, day, hour, minute, second, millis * 1000)

def build_boss_pattern(raid_name: str) -> re.Pattern | None:
    boss_names = RAID_BOSSES.get(raid_name, [])
    if not boss_names:
        return None
    return re.compile("|".join(re.escape(name) for name in boss_names), re.IGNORECASE)

def parse_death_breakdown(
    log_path: Path,
    raider_names: set[str],
    raid_name: str,
    logger_name: str | None,
    boss_window_seconds: int = 45,
) -> dict[str, dict[str, int]]:
    boss_pattern = build_boss_pattern(raid_name)
    last_boss_time: datetime | None = None
    breakdown: dict[str, dict[str, int]] = {
        name: {"total": 0, "boss": 0, "trash": 0} for name in raider_names
    }

    death_re = re.compile(r"^\d{1,2}/\d{1,2} \d{1,2}:\d{2}:\d{2}\.\d{3}  ([A-Za-z'`-]+) dies\.$")

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            timestamp = parse_log_timestamp(line)
            if timestamp and boss_pattern and boss_pattern.search(line):
                last_boss_time = timestamp

            match = death_re.match(line)
            if match:
                name = match.group(1)
            elif "You die." in line:
                name = logger_name or "You"
            else:
                continue

            if name not in raider_names:
                continue

            is_boss = False
            if timestamp and last_boss_time:
                delta = (timestamp - last_boss_time).total_seconds()
                is_boss = 0 <= delta <= boss_window_seconds

            breakdown[name]["total"] += 1
            if is_boss:
                breakdown[name]["boss"] += 1
            else:
                breakdown[name]["trash"] += 1

    return breakdown

def parse_healthstone_uses(
    log_path: Path,
    raider_names: set[str],
    logger_name: str | None,
) -> dict[str, int]:
    counts = {name: 0 for name in raider_names}
    healthstone_re = re.compile(
        r"(?P<owner>[A-Za-z'`-]+)'s .*?(?:Healthstone|Lifestone) heals (?P<target>[A-Za-z'`-]+)",
        re.IGNORECASE,
    )

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            match = healthstone_re.search(line)
            if not match:
                continue
            target = match.group("target")
            if target.lower() == "you" and logger_name:
                target = logger_name
            if target not in raider_names:
                continue
            counts[target] += 1

    return counts


def parse_orange_uses(
    log_path: Path,
    raider_names: set[str],
    logger_name: str | None,
) -> dict[str, int]:
    counts = {name: 0 for name in raider_names}
    orange_re = re.compile(r"(?P<target>[A-Za-z'`-]+) uses Conjured Mana Orange\.", re.IGNORECASE)

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            match = orange_re.search(line)
            if not match:
                if "You use Conjured Mana Orange." in line and logger_name:
                    target = logger_name
                else:
                    continue
            else:
                target = match.group("target")

            if target not in raider_names:
                continue
            counts[target] += 1

    return counts


def parse_resurrection_casts(
    log_path: Path,
    raider_names: set[str],
    logger_name: str | None,
) -> dict[str, int]:
    counts = {name: 0 for name in raider_names}
    spell_names = [
        "Resurrection",
        "Ancestral Spirit",
        "Redemption",
        "Rebirth",
        "Revive Champion",
    ]
    spell_pattern = "|".join(re.escape(name) for name in spell_names)
    cast_re = re.compile(
        rf"(?P<caster>[A-Za-z'`-]+) casts (?:{spell_pattern}) on (?P<target>[A-Za-z'`-]+)\.",
        re.IGNORECASE,
    )

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            match = cast_re.search(line)
            if not match:
                if "You cast " in line and logger_name:
                    if any(spell in line for spell in spell_names):
                        caster = logger_name
                    else:
                        continue
                else:
                    continue
            else:
                caster = match.group("caster")

            if caster not in raider_names:
                continue
            counts[caster] += 1

    return counts


def parse_combat_log_for_guilds(log_path: Path, target_guilds: list[str]) -> set[str]:
    """Parse combat log to extract character names belonging to target guilds."""
    guild_members = set()
    pattern = re.compile(
        r"COMBATANT_INFO:.*?&([^&]+)&[A-Z]+&[A-Za-z]+&\d+&[^&]*&(" + 
        "|".join(re.escape(g) for g in target_guilds) + r")&"
    )
    
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                match = pattern.search(line)
                if match:
                    char_name = match.group(1).strip()
                    guild_members.add(char_name)
    except Exception as e:
        print(f"[WARN] Could not parse combat log for guilds: {e}")
    
    return guild_members


def parse_combat_log_for_pets(log_path: Path) -> set[str]:
    """Parse combat log to identify pet names."""
    pets = set()
    pattern = re.compile(r"\b([A-Z][a-z]+)\s+\([A-Z][a-z]+\)")
    
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                for match in pattern.finditer(line):
                    pets.add(match.group(1))
    except Exception as e:
        print(f"[WARN] Could not parse combat log for pets: {e}")
    
    return pets


def count_logger_deaths(log_path: Path) -> int:
    """Count the number of times 'You die.' appears in the combat log."""
    count = 0
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if "You die." in line:
                    count += 1
    except Exception as e:
        print(f"[WARN] Could not count logger deaths: {e}")
    
    return count


def detect_raid_from_log(log_path: Path) -> str:
    """Detect raid/zone name from combat log."""
    raid_names = {
        "naxxramas": "Naxxramas",
        "onyxia": "Onyxia's Lair", 
        "molten": "Molten Core",
        "blackwing": "Blackwing Lair",
        "aq40": "Temple of Ahn'Qiraj",
        "aq20": "Ruins of Ahn'Qiraj",
        "zulgurub": "Zul'Gurub",
        "zulaman": "Zul'Aman",
        "sunwell": "Sunwell Plateau",
        "black_temple": "Black Temple",
        "karazhan": "Karazhan",
        "gruul": "Gruul's Lair",
        "magtheridon": "Magtheridon's Lair",
        "serpentshrine": "Serpentshrine Cavern",
        "tempest_keep": "Tempest Keep",
        "hyjal": "Battle for Mount Hyjal",
    }
    
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if "ZONE_INFO:" in line:
                    parts = line.split("&")
                    if len(parts) >= 2:
                        zone = parts[1].strip().lower()
                        for key, name in raid_names.items():
                            if key in zone:
                                return name
    except Exception as e:
        print(f"[WARN] Could not detect raid from log: {e}")
    
    return "Raid"


def extract_raid_date_from_log(log_path: Path) -> str:
    """
    Extract the raid date from the first timestamp in the combat log.
    
    WoW combat logs have timestamps in the format: MM/DD HH:MM:SS.mmm
    This function extracts the first timestamp and formats it as "DD MMM YYYY".
    
    Returns the formatted date string, or today's date if parsing fails.
    """
    date_pattern = re.compile(r'^(\d{1,2}/\d{1,2})\s+\d{1,2}:\d{2}:\d{2}')
    
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                match = date_pattern.match(line)
                if match:
                    # Extract MM/DD and add current year
                    date_str = match.group(1)
                    current_year = datetime.now().year
                    
                    # Parse and format the date
                    parsed_date = datetime.strptime(f"{date_str}/{current_year}", "%m/%d/%Y")
                    return parsed_date.strftime("%d %b %Y")
    except Exception as e:
        print(f"[WARN] Could not extract date from log: {e}")
    
    # Fallback to today's date
    return datetime.now().strftime("%d %b %Y")


def parse_sunder_data(summary_path: Path) -> list[tuple[str, int, int]]:
    """
    Parse Sunder Armor data from summary.txt.
    
    Returns list of (name, trash_count, boss_count) tuples.
    
    Expected format in summary.txt:
    Sunder Armor Summary (trash and boss counts)
       Yelena 345 303
       Zulahachus 164 47
       ...
    """
    sunders = []
    
    if not summary_path.exists():
        return sunders
    
    try:
        with open(summary_path, "r", encoding="utf-8", errors="replace") as f:
            in_sunder_section = False
            for line in f:
                if "Sunder Armor Summary" in line:
                    in_sunder_section = True
                    continue
                
                if in_sunder_section:
                    stripped = line.strip()
                    if not stripped:
                        break
                    
                    # Check if line starts with whitespace (indented data)
                    if not line[0].isspace():
                        break
                    
                    # Parse: "   Name trash_count boss_count"
                    parts = stripped.split()
                    if len(parts) >= 3:
                        name = parts[0]
                        trash = safe_int(parts[1], 0)
                        boss = safe_int(parts[2], 0)
                        sunders.append((name, trash, boss))
                    elif len(parts) == 2:
                        name = parts[0]
                        total = safe_int(parts[1], 0)
                        sunders.append((name, total, 0))
    except Exception as e:
        print(f"[WARN] Could not parse sunder data: {e}")
    
    return sunders


def generate_html(
    rows: list[tuple[str, int, int]],
    guild_names: list[str],
    raid_name: str,
    server_name: str,
    icon_data: dict[str, str],
    date_str: str,
    sunder_data: list[tuple[str, int, int]] = None,
) -> str:
    """Generate the HTML for the Discord card."""
    
    total_copper = sum(x[1] for x in rows)
    total_deaths = sum(x[2] for x in rows)
    players = len(rows)
    
    avg_cost = total_copper // players if players > 0 else 0
    zero_death_count = sum(1 for x in rows if x[2] == 0)
    
    top_5 = rows[:5]
    top_spender = rows[0] if rows else ("—", 0, 0)
    most_deaths = max(rows, key=lambda x: x[2]) if rows else ("—", 0, 0)
    
    # Build guild icons HTML
    guild_icons_html = ""
    for guild in guild_names:
        icon_b64 = icon_data.get(guild, "")
        glow_color = GUILD_CONFIG.get(guild, {}).get("glow_color", "rgba(255,255,255,0.2)")
        if icon_b64:
            guild_icons_html += f'''
          <div class="guild-icon-wrapper">
            <div class="guild-icon-glow" style="background: radial-gradient(circle, {glow_color} 0%, transparent 70%);"></div>
            <img class="guild-icon" src="data:image/png;base64,{icon_b64}" alt="{escape(guild)}">
          </div>'''
    
    guild_names_display = '<span class="separator">×</span>'.join(escape(g) for g in guild_names)
    
    # Build top 5 spend rows
    player_rows_html = ""
    for i, (name, copper, deaths) in enumerate(top_5, start=1):
        rank_class = f"top-{i}" if i <= 3 else ""
        player_rows_html += f'''
          <div class="player-row {rank_class}">
            <span class="rank">{i}</span>
            <span class="player-name">{escape(name)}</span>
            <span class="player-cost">{copper_to_gsc_short(copper)}</span>
          </div>'''
    
    # Build sunder race HTML
    sunder_html = ""
    if sunder_data:
        sorted_sunders = sorted(sunder_data, key=lambda x: x[2], reverse=True)[:5]
        max_boss_sunders = sorted_sunders[0][2] if sorted_sunders else 1
        
        sunder_rows = ""
        medals = ["🥇", "🥈", "🥉", "4", "5"]
        for i, (name, trash, boss) in enumerate(sorted_sunders):
            bar_width = int((boss / max_boss_sunders) * 100) if max_boss_sunders > 0 else 0
            medal = medals[i] if i < len(medals) else str(i + 1)
            medal_class = f"medal-{i+1}" if i < 3 else ""
            sunder_rows += f'''
            <div class="sunder-row">
              <span class="sunder-medal {medal_class}">{medal}</span>
              <span class="sunder-name">{escape(name)}</span>
              <div class="sunder-bar-container">
                <div class="sunder-bar" style="width: {bar_width}%"></div>
              </div>
              <span class="sunder-count">{boss}</span>
            </div>'''
        
        sunder_html = f'''
        <div class="sunder-race">
          <h3>⚔️ Sunder Race <span class="sunder-subtitle">(boss sunders)</span></h3>
          <div class="sunder-list">
            {sunder_rows}
          </div>
        </div>'''
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=1200, height=630">
  <title>Raid Consume Report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Fira+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
      width: 1200px;
      height: 630px;
      background: linear-gradient(155deg, #0a0e14 0%, #131922 40%, #0f1419 100%);
      font-family: 'Fira Sans', sans-serif;
      color: #e6edf3;
      overflow: hidden;
      position: relative;
    }}

    body::before {{
      content: '';
      position: absolute;
      inset: 0;
      background: 
        radial-gradient(ellipse 80% 50% at 15% 20%, rgba(212, 175, 55, 0.07) 0%, transparent 50%),
        radial-gradient(ellipse 60% 40% at 85% 75%, rgba(140, 130, 120, 0.05) 0%, transparent 50%),
        radial-gradient(ellipse 100% 60% at 50% 110%, rgba(80, 60, 40, 0.08) 0%, transparent 60%);
      pointer-events: none;
    }}

    .container {{
      padding: 32px 44px;
      height: 100%;
      display: flex;
      flex-direction: column;
      position: relative;
      z-index: 1;
    }}

    .header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 20px;
    }}

    .header-left {{
      display: flex;
      align-items: center;
      gap: 18px;
    }}

    .guild-icons {{
      display: flex;
      gap: 10px;
    }}

    .guild-icon-wrapper {{
      position: relative;
      width: 56px;
      height: 56px;
    }}

    .guild-icon {{
      width: 56px;
      height: 56px;
      border-radius: 50%;
      object-fit: cover;
      filter: drop-shadow(0 4px 12px rgba(0,0,0,0.5));
      -webkit-mask-image: radial-gradient(circle, black 55%, transparent 72%);
      mask-image: radial-gradient(circle, black 55%, transparent 72%);
    }}

    .guild-icon-glow {{
      position: absolute;
      inset: -4px;
      border-radius: 50%;
      filter: blur(8px);
      z-index: -1;
    }}

    .title-block {{
      display: flex;
      flex-direction: column;
      gap: 3px;
    }}

    .guild-names {{
      font-family: 'Cinzel', serif;
      font-size: 28px;
      font-weight: 700;
      color: #f0f6fc;
      letter-spacing: 1px;
      text-shadow: 0 2px 16px rgba(212, 175, 55, 0.25);
    }}

    .guild-names .separator {{
      color: #4a5568;
      margin: 0 6px;
      font-weight: 400;
    }}

    .raid-subtitle {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .raid-badge {{
      background: linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(139, 92, 246, 0.1) 100%);
      border: 1px solid rgba(139, 92, 246, 0.3);
      padding: 3px 10px;
      border-radius: 10px;
      font-size: 10px;
      font-weight: 600;
      color: #a78bfa;
      letter-spacing: 1px;
      text-transform: uppercase;
    }}

    .date-text {{
      font-size: 12px;
      color: #586069;
    }}

    .server-badge {{
      background: linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(34, 197, 94, 0.08) 100%);
      border: 1px solid rgba(34, 197, 94, 0.3);
      padding: 8px 18px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      color: #4ade80;
      letter-spacing: 1px;
      text-transform: uppercase;
    }}

    .stats-row {{
      display: flex;
      gap: 16px;
      margin-bottom: 20px;
    }}

    .stat-card {{
      flex: 1;
      background: rgba(22, 27, 34, 0.7);
      border: 1px solid rgba(48, 54, 61, 0.6);
      border-radius: 12px;
      padding: 14px 18px;
      position: relative;
      overflow: hidden;
    }}

    .stat-card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
    }}

    .stat-card.gold::before {{ background: linear-gradient(90deg, #ffd700, #f59e0b, #ffd700); }}
    .stat-card.players::before {{ background: linear-gradient(90deg, #3b82f6, #60a5fa, #3b82f6); }}
    .stat-card.deaths::before {{ background: linear-gradient(90deg, #ef4444, #f87171, #ef4444); }}

    .stat-label {{
      font-size: 10px;
      color: #6e7681;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      margin-bottom: 6px;
    }}

    .stat-value {{
      font-size: 26px;
      font-weight: 700;
      color: #f0f6fc;
    }}

    .stat-value .g {{ color: #ffd700; }}
    .stat-value .s {{ color: #c0c0c0; }}
    .stat-value .c {{ color: #cd7f32; }}

    .main-content {{
      display: flex;
      gap: 24px;
      flex: 1;
      min-height: 0;
    }}

    .leaderboard {{
      flex: 1.2;
      display: flex;
      flex-direction: column;
    }}

    .section-title {{
      font-size: 11px;
      color: #6e7681;
      text-transform: uppercase;
      letter-spacing: 2px;
      margin-bottom: 10px;
      font-weight: 600;
    }}

    .player-list {{
      display: flex;
      flex-direction: column;
      gap: 5px;
    }}

    .player-row {{
      display: flex;
      align-items: center;
      padding: 10px 14px;
      background: rgba(22, 27, 34, 0.5);
      border-radius: 8px;
      border: 1px solid rgba(48, 54, 61, 0.4);
    }}

    .player-row.top-1 {{
      background: linear-gradient(135deg, rgba(255, 215, 0, 0.12) 0%, rgba(22, 27, 34, 0.7) 100%);
      border-color: rgba(255, 215, 0, 0.25);
    }}

    .player-row.top-2 {{
      background: linear-gradient(135deg, rgba(192, 192, 192, 0.08) 0%, rgba(22, 27, 34, 0.7) 100%);
      border-color: rgba(192, 192, 192, 0.2);
    }}

    .player-row.top-3 {{
      background: linear-gradient(135deg, rgba(205, 127, 50, 0.08) 0%, rgba(22, 27, 34, 0.7) 100%);
      border-color: rgba(205, 127, 50, 0.2);
    }}

    .rank {{
      width: 24px;
      font-size: 13px;
      font-weight: 700;
      color: #586069;
    }}

    .top-1 .rank {{ color: #ffd700; }}
    .top-2 .rank {{ color: #c0c0c0; }}
    .top-3 .rank {{ color: #cd7f32; }}

    .player-name {{
      flex: 1;
      font-weight: 600;
      font-size: 14px;
      color: #e6edf3;
    }}

    .player-cost {{
      font-size: 13px;
      font-weight: 500;
      color: #8b949e;
      min-width: 100px;
      text-align: right;
    }}

    .top-1 .player-cost {{ color: #ffd700; }}

    .middle-column {{
      flex: 0.9;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .highlight-card {{
      background: rgba(22, 27, 34, 0.6);
      border: 1px solid rgba(48, 54, 61, 0.5);
      border-radius: 10px;
      padding: 12px 14px;
    }}

    .highlight-card h3 {{
      font-size: 9px;
      color: #6e7681;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      margin-bottom: 6px;
    }}

    .highlight-value {{
      font-size: 14px;
      font-weight: 600;
    }}

    .highlight-value .name {{ color: #58a6ff; }}
    .highlight-value .detail {{ color: #6e7681; font-size: 12px; font-weight: 400; }}

    .fun-stats {{
      padding: 12px 14px;
      background: rgba(59, 130, 246, 0.06);
      border: 1px solid rgba(59, 130, 246, 0.15);
      border-radius: 10px;
    }}

    .fun-stats h3 {{
      font-size: 9px;
      color: #60a5fa;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      margin-bottom: 8px;
    }}

    .fun-stat-item {{
      font-size: 12px;
      color: #8b949e;
      margin-bottom: 4px;
      display: flex;
      justify-content: space-between;
    }}

    .fun-stat-item:last-child {{ margin-bottom: 0; }}
    .fun-stat-item strong {{ color: #e6edf3; }}

    /* Sunder Race */
    .sunder-race {{
      flex: 1;
      background: rgba(22, 27, 34, 0.6);
      border: 1px solid rgba(234, 179, 8, 0.2);
      border-radius: 12px;
      padding: 14px 16px;
      display: flex;
      flex-direction: column;
    }}

    .sunder-race h3 {{
      font-size: 11px;
      color: #eab308;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      margin-bottom: 12px;
      font-weight: 700;
    }}

    .sunder-subtitle {{
      font-size: 9px;
      color: #6e7681;
      font-weight: 500;
      text-transform: lowercase;
    }}

    .sunder-list {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      flex: 1;
    }}

    .sunder-row {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .sunder-medal {{
      width: 22px;
      font-size: 14px;
      text-align: center;
    }}

    .sunder-medal.medal-1 {{ filter: drop-shadow(0 0 4px rgba(255, 215, 0, 0.5)); }}
    .sunder-medal.medal-2 {{ filter: drop-shadow(0 0 4px rgba(192, 192, 192, 0.4)); }}
    .sunder-medal.medal-3 {{ filter: drop-shadow(0 0 4px rgba(205, 127, 50, 0.4)); }}

    .sunder-name {{
      width: 90px;
      font-size: 12px;
      font-weight: 600;
      color: #e6edf3;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .sunder-bar-container {{
      flex: 1;
      height: 16px;
      background: rgba(48, 54, 61, 0.5);
      border-radius: 8px;
      overflow: hidden;
    }}

    .sunder-bar {{
      height: 100%;
      background: linear-gradient(90deg, #eab308 0%, #f59e0b 50%, #fbbf24 100%);
      border-radius: 8px;
      box-shadow: 0 0 10px rgba(234, 179, 8, 0.3);
    }}

    .sunder-count {{
      width: 40px;
      font-size: 13px;
      font-weight: 700;
      color: #fbbf24;
      text-align: right;
    }}

    .footer {{
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid rgba(48, 54, 61, 0.4);
      display: flex;
      justify-content: space-between;
      font-size: 10px;
      color: #484f58;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="header-left">
        <div class="guild-icons">{guild_icons_html}</div>
        <div class="title-block">
          <div class="guild-names">{guild_names_display}</div>
          <div class="raid-subtitle">
            <span class="raid-badge">{escape(raid_name)}</span>
            <span class="date-text">{escape(date_str)}</span>
          </div>
        </div>
      </div>
      <div class="server-badge">{escape(server_name)}</div>
    </div>

    <div class="stats-row">
      <div class="stat-card gold">
        <div class="stat-label">Total Raid Cost</div>
        <div class="stat-value">
          <span class="g">{copper_to_gold_rounded(total_copper)}</span>g
        </div>
      </div>
      <div class="stat-card players">
        <div class="stat-label">Raiders</div>
        <div class="stat-value">{players}</div>
      </div>
      <div class="stat-card deaths">
        <div class="stat-label">Deaths</div>
        <div class="stat-value">{total_deaths}</div>
      </div>
    </div>

    <div class="main-content">
      <div class="leaderboard">
        <div class="section-title">Top Spenders</div>
        <div class="player-list">{player_rows_html}</div>
      </div>

      <div class="middle-column">
        <div class="highlight-card">
          <h3>💰 Big Spender</h3>
          <div class="highlight-value">
            <span class="name">{escape(top_spender[0])}</span>
            <span class="detail"> — {copper_to_gsc_short(top_spender[1])}</span>
          </div>
        </div>

        <div class="highlight-card">
          <h3>💀 Most Deaths</h3>
          <div class="highlight-value">
            <span class="name">{escape(most_deaths[0])}</span>
            <span class="detail"> — {most_deaths[2]} death{"s" if most_deaths[2] != 1 else ""}</span>
          </div>
        </div>

        <div class="fun-stats">
          <h3>📊 Raid Stats</h3>
          <div class="fun-stat-item">
            <span>Avg cost per raider</span>
            <strong>{copper_to_gsc_short(avg_cost)}</strong>
          </div>
          <div class="fun-stat-item">
            <span>Zero-death raiders</span>
            <strong>{zero_death_count}/{players}</strong>
          </div>
        </div>
      </div>

      {sunder_html}
    </div>

    <div class="footer">
      <span>Generated by summarize_consumes</span>
      <span>Prices: {escape(server_name)} AH</span>
    </div>
  </div>
</body>
</html>'''
    
    return html


def generate_full_report_html(
    rows: list[tuple[str, int, int]],
    guild_names: list[str],
    raid_name: str,
    server_name: str,
    icon_data: dict[str, str],
    date_str: str,
    sunder_data: list[tuple[str, int, int]] | None,
    death_breakdown: dict[str, dict[str, int]],
    healthstone_uses: dict[str, int],
    orange_uses: dict[str, int],
    resurrection_casts: dict[str, int],
) -> str:
    total_copper = sum(x[1] for x in rows)
    total_deaths = sum(x[2] for x in rows)
    players = len(rows)
    avg_cost = total_copper // players if players > 0 else 0
    zero_death_count = sum(1 for x in rows if x[2] == 0)

    top_spender = rows[0] if rows else ("—", 0, 0)
    most_deaths = max(rows, key=lambda x: x[2]) if rows else ("—", 0, 0)
    top_orange = max(orange_uses.items(), key=lambda x: x[1]) if orange_uses else ("—", 0)
    top_boss_deaths = (
        max(death_breakdown.items(), key=lambda x: x[1]["boss"])
        if death_breakdown
        else ("—", {"boss": 0})
    )
    top_trash_deaths = (
        max(death_breakdown.items(), key=lambda x: x[1]["trash"])
        if death_breakdown
        else ("—", {"trash": 0})
    )
    top_healthstones = (
        max(healthstone_uses.items(), key=lambda x: x[1])
        if healthstone_uses
        else ("—", 0)
    )
    top_resurrections = (
        max(resurrection_casts.items(), key=lambda x: x[1])
        if resurrection_casts
        else ("—", 0)
    )

    guild_icons_html = ""
    for guild in guild_names:
        icon_b64 = icon_data.get(guild, "")
        glow_color = GUILD_CONFIG.get(guild, {}).get("glow_color", "rgba(255,255,255,0.2)")
        if icon_b64:
            guild_icons_html += f'''
          <div class="guild-icon-wrapper">
            <div class="guild-icon-glow" style="background: radial-gradient(circle, {glow_color} 0%, transparent 70%);"></div>
            <img class="guild-icon" src="data:image/png;base64,{icon_b64}" alt="{escape(guild)}">
          </div>'''

    guild_names_display = '<span class="separator">×</span>'.join(escape(g) for g in guild_names)

    sunder_html = ""
    if sunder_data:
        sorted_sunders = sorted(sunder_data, key=lambda x: x[2], reverse=True)[:10]
        max_boss_sunders = sorted_sunders[0][2] if sorted_sunders else 1
        sunder_rows = ""
        medals = ["🥇", "🥈", "🥉"] + [str(i) for i in range(4, 11)]
        for i, (name, trash, boss) in enumerate(sorted_sunders):
            bar_width = int((boss / max_boss_sunders) * 100) if max_boss_sunders > 0 else 0
            medal = medals[i] if i < len(medals) else str(i + 1)
            medal_class = f"medal-{i+1}" if i < 3 else ""
            sunder_rows += f'''
            <div class="sunder-row">
              <span class="sunder-medal {medal_class}">{medal}</span>
              <span class="sunder-name">{escape(name)}</span>
              <div class="sunder-bar-container">
                <div class="sunder-bar" style="width: {bar_width}%"></div>
              </div>
              <span class="sunder-count">{boss}</span>
            </div>'''

        sunder_html = f'''
        <div class="sunder-race full">
          <h3>⚔️ Sunder Race <span class="sunder-subtitle">(boss sunders)</span></h3>
          <div class="sunder-list">
            {sunder_rows}
          </div>
        </div>'''

    table_rows = ""
    for i, (name, copper, deaths) in enumerate(rows, start=1):
        breakdown = death_breakdown.get(name, {"total": deaths, "boss": 0, "trash": 0})
        healthstones = healthstone_uses.get(name, 0)
        oranges = orange_uses.get(name, 0)
        resurrections = resurrection_casts.get(name, 0)
        sort_name = escape(name.lower())
        table_rows += f"""
          <tr>
            <td class="num" data-value="{i}">{i}</td>
            <td class="player-name" data-value="{sort_name}">{escape(name)}</td>
            <td class="num stat-cell" data-value="{copper}"><span class="badge badge-gold">💰 {copper_to_gsc_short(copper)}</span></td>
            <td class="num stat-cell" data-value="{breakdown['total']}"><span class="badge badge-total">💀 {breakdown['total']}</span></td>
            <td class="num stat-cell" data-value="{breakdown['boss']}"><span class="badge badge-boss">👹 {breakdown['boss']}</span></td>
            <td class="num stat-cell" data-value="{breakdown['trash']}"><span class="badge badge-trash">🗑️ {breakdown['trash']}</span></td>
            <td class="num stat-cell" data-value="{healthstones}"><span class="badge badge-healthstone">🟢 {healthstones}</span></td>
            <td class="num stat-cell" data-value="{oranges}"><span class="badge badge-orange">🍊 {oranges}</span></td>
            <td class="num stat-cell" data-value="{resurrections}"><span class="badge badge-res">😇 {resurrections}</span></td>
          </tr>
        """

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=1200">
  <title>Raid Consume Report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Fira+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
      width: 1200px;
      background: linear-gradient(155deg, #0a0e14 0%, #131922 40%, #0f1419 100%);
      font-family: 'Fira Sans', sans-serif;
      color: #e6edf3;
      position: relative;
    }}

    body::before {{
      content: '';
      position: absolute;
      inset: 0;
      background:
        radial-gradient(ellipse 80% 50% at 15% 20%, rgba(212, 175, 55, 0.07) 0%, transparent 50%),
        radial-gradient(ellipse 60% 40% at 85% 75%, rgba(140, 130, 120, 0.05) 0%, transparent 50%),
        radial-gradient(ellipse 100% 60% at 50% 110%, rgba(80, 60, 40, 0.08) 0%, transparent 60%);
      pointer-events: none;
    }}

    .container {{
      padding: 32px 44px 48px;
      position: relative;
      z-index: 1;
    }}

    .header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 20px;
    }}

    .header-left {{
      display: flex;
      align-items: center;
      gap: 18px;
    }}

    .guild-icons {{
      display: flex;
      gap: 10px;
    }}

    .guild-icon-wrapper {{
      position: relative;
      width: 56px;
      height: 56px;
    }}

    .guild-icon {{
      width: 56px;
      height: 56px;
      border-radius: 50%;
      object-fit: cover;
      filter: drop-shadow(0 4px 12px rgba(0,0,0,0.5));
      -webkit-mask-image: radial-gradient(circle, black 55%, transparent 72%);
      mask-image: radial-gradient(circle, black 55%, transparent 72%);
    }}

    .guild-icon-glow {{
      position: absolute;
      inset: -4px;
      border-radius: 50%;
      filter: blur(8px);
      z-index: -1;
    }}

    .title-block {{
      display: flex;
      flex-direction: column;
      gap: 3px;
    }}

    .guild-names {{
      font-family: 'Cinzel', serif;
      font-size: 28px;
      font-weight: 700;
      color: #f0f6fc;
      letter-spacing: 1px;
      text-shadow: 0 2px 16px rgba(212, 175, 55, 0.25);
    }}

    .guild-names .separator {{
      color: #4a5568;
      margin: 0 6px;
      font-weight: 400;
    }}

    .raid-subtitle {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .raid-badge {{
      background: linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(139, 92, 246, 0.1) 100%);
      border: 1px solid rgba(139, 92, 246, 0.3);
      padding: 3px 10px;
      border-radius: 10px;
      font-size: 10px;
      font-weight: 600;
      color: #a78bfa;
      letter-spacing: 1px;
      text-transform: uppercase;
    }}

    .date-text {{
      font-size: 12px;
      color: #586069;
    }}

    .server-badge {{
      background: linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(34, 197, 94, 0.08) 100%);
      border: 1px solid rgba(34, 197, 94, 0.3);
      padding: 8px 18px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      color: #4ade80;
      letter-spacing: 1px;
      text-transform: uppercase;
    }}

    .stats-row {{
      display: flex;
      gap: 16px;
      margin-bottom: 20px;
    }}

    .stat-card {{
      flex: 1;
      background: rgba(22, 27, 34, 0.7);
      border: 1px solid rgba(48, 54, 61, 0.6);
      border-radius: 12px;
      padding: 14px 18px;
      position: relative;
      overflow: hidden;
    }}

    .stat-card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
    }}

    .stat-card.gold::before {{ background: linear-gradient(90deg, #ffd700, #f59e0b, #ffd700); }}
    .stat-card.players::before {{ background: linear-gradient(90deg, #3b82f6, #60a5fa, #3b82f6); }}
    .stat-card.deaths::before {{ background: linear-gradient(90deg, #ef4444, #f87171, #ef4444); }}

    .stat-label {{
      font-size: 10px;
      color: #6e7681;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      margin-bottom: 6px;
    }}

    .stat-value {{
      font-size: 26px;
      font-weight: 700;
      color: #f0f6fc;
    }}

    .stat-value .g {{ color: #ffd700; }}
    .stat-value .s {{ color: #c0c0c0; }}
    .stat-value .c {{ color: #cd7f32; }}

    .main-content {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 24px;
      margin-bottom: 24px;
    }}

    .panel {{
      background: rgba(22, 27, 34, 0.6);
      border: 1px solid rgba(48, 54, 61, 0.5);
      border-radius: 12px;
      padding: 16px;
    }}

    .section-title {{
      font-size: 11px;
      color: #6e7681;
      text-transform: uppercase;
      letter-spacing: 2px;
      margin-bottom: 12px;
      font-weight: 600;
    }}

    .highlight-grid {{
      display: grid;
      gap: 12px;
    }}

    .highlight-card h3 {{
      font-size: 9px;
      color: #6e7681;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      margin-bottom: 6px;
    }}

    .highlight-value {{
      font-size: 14px;
      font-weight: 600;
    }}

    .highlight-value .name {{ color: #58a6ff; }}
    .highlight-value .detail {{ color: #6e7681; font-size: 12px; font-weight: 400; }}

    .fun-stats {{
      padding: 12px 14px;
      background: rgba(59, 130, 246, 0.06);
      border: 1px solid rgba(59, 130, 246, 0.15);
      border-radius: 10px;
    }}

    .fun-stats h3 {{
      font-size: 9px;
      color: #60a5fa;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      margin-bottom: 8px;
    }}

    .fun-stat-item {{
      font-size: 12px;
      color: #8b949e;
      margin-bottom: 4px;
      display: flex;
      justify-content: space-between;
    }}

    .fun-stat-item:last-child {{ margin-bottom: 0; }}
    .fun-stat-item strong {{ color: #e6edf3; }}

    .sunder-race.full {{
      margin-top: 12px;
    }}

    .sunder-race {{
      background: rgba(22, 27, 34, 0.6);
      border: 1px solid rgba(234, 179, 8, 0.2);
      border-radius: 12px;
      padding: 14px 16px;
      display: flex;
      flex-direction: column;
    }}

    .sunder-race h3 {{
      font-size: 11px;
      color: #eab308;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      margin-bottom: 12px;
      font-weight: 700;
    }}

    .sunder-subtitle {{
      font-size: 9px;
      color: #6e7681;
      font-weight: 500;
      text-transform: lowercase;
    }}

    .sunder-list {{
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}

    .sunder-row {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .sunder-medal {{
      width: 22px;
      font-size: 14px;
      text-align: center;
    }}

    .sunder-medal.medal-1 {{ filter: drop-shadow(0 0 4px rgba(255, 215, 0, 0.5)); }}
    .sunder-medal.medal-2 {{ filter: drop-shadow(0 0 4px rgba(192, 192, 192, 0.4)); }}
    .sunder-medal.medal-3 {{ filter: drop-shadow(0 0 4px rgba(205, 127, 50, 0.4)); }}

    .sunder-name {{
      width: 90px;
      font-size: 12px;
      font-weight: 600;
      color: #e6edf3;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .sunder-bar-container {{
      flex: 1;
      height: 16px;
      background: rgba(48, 54, 61, 0.5);
      border-radius: 8px;
      overflow: hidden;
    }}

    .sunder-bar {{
      height: 100%;
      background: linear-gradient(90deg, #eab308 0%, #f59e0b 50%, #fbbf24 100%);
      border-radius: 8px;
      box-shadow: 0 0 10px rgba(234, 179, 8, 0.3);
    }}

    .sunder-count {{
      width: 40px;
      font-size: 13px;
      font-weight: 700;
      color: #fbbf24;
      text-align: right;
    }}

    .table-card {{
      background: rgba(22, 27, 34, 0.75);
      border: 1px solid rgba(48, 54, 61, 0.6);
      border-radius: 14px;
      padding: 16px;
      box-shadow: 0 12px 24px rgba(0, 0, 0, 0.25);
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      table-layout: auto;
    }}

    col.col-rank {{
      width: 4ch;
    }}

    col.col-name {{
      width: auto;
    }}

    col.col-stat {{
      width: 12ch;
    }}

    th, td {{
      padding: 10px 8px;
      text-align: left;
      border-bottom: 1px solid rgba(48, 54, 61, 0.6);
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    th {{
      text-transform: uppercase;
      letter-spacing: 1.5px;
      font-size: 10px;
      color: #8b949e;
      background: rgba(13, 17, 23, 0.85);
    }}

    th.sortable {{
      cursor: pointer;
      user-select: none;
    }}

    th.sortable::after {{
      content: '⇅';
      font-size: 9px;
      margin-left: 6px;
      color: rgba(139, 148, 158, 0.5);
    }}

    th.sortable.sorted-asc::after {{
      content: '↑';
      color: #60a5fa;
    }}

    th.sortable.sorted-desc::after {{
      content: '↓';
      color: #60a5fa;
    }}

    td.num {{
      font-variant-numeric: tabular-nums;
    }}

    td.stat-cell {{
      white-space: nowrap;
      text-align: center;
    }}

    tbody tr:nth-child(odd) {{
      background: rgba(22, 27, 34, 0.55);
    }}

    tbody tr:hover {{
      background: rgba(56, 139, 253, 0.08);
    }}

    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 3px 8px;
      border-radius: 999px;
      font-weight: 600;
      font-size: 11px;
      color: #e6edf3;
      background: rgba(30, 41, 59, 0.7);
      border: 1px solid rgba(71, 85, 105, 0.6);
    }}

    .badge-total {{
      background: rgba(239, 68, 68, 0.15);
      border-color: rgba(239, 68, 68, 0.35);
      color: #fca5a5;
    }}

    .badge-boss {{
      background: rgba(139, 92, 246, 0.15);
      border-color: rgba(139, 92, 246, 0.35);
      color: #c4b5fd;
    }}

    .badge-trash {{
      background: rgba(56, 189, 248, 0.15);
      border-color: rgba(56, 189, 248, 0.35);
      color: #7dd3fc;
    }}

    .badge-healthstone {{
      background: rgba(34, 197, 94, 0.15);
      border-color: rgba(34, 197, 94, 0.35);
      color: #86efac;
    }}

    .badge-orange {{
      background: rgba(249, 115, 22, 0.18);
      border-color: rgba(249, 115, 22, 0.4);
      color: #fdba74;
    }}

    .badge-res {{
      background: rgba(191, 219, 254, 0.2);
      border-color: rgba(147, 197, 253, 0.45);
      color: #bfdbfe;
    }}

    .badge-gold {{
      background: rgba(245, 158, 11, 0.18);
      border-color: rgba(245, 158, 11, 0.4);
      color: #fcd34d;
    }}

    .footer {{
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid rgba(48, 54, 61, 0.4);
      display: flex;
      justify-content: space-between;
      font-size: 10px;
      color: #484f58;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="header-left">
        <div class="guild-icons">{guild_icons_html}</div>
        <div class="title-block">
          <div class="guild-names">{guild_names_display}</div>
          <div class="raid-subtitle">
            <span class="raid-badge">{escape(raid_name)}</span>
            <span class="date-text">{escape(date_str)}</span>
          </div>
        </div>
      </div>
      <div class="server-badge">{escape(server_name)}</div>
    </div>

    <div class="stats-row">
      <div class="stat-card gold">
        <div class="stat-label">Total Raid Cost</div>
        <div class="stat-value">
          <span class="g">{copper_to_gold_rounded(total_copper)}</span>g
        </div>
      </div>
      <div class="stat-card players">
        <div class="stat-label">Raiders</div>
        <div class="stat-value">{players}</div>
      </div>
      <div class="stat-card deaths">
        <div class="stat-label">Deaths</div>
        <div class="stat-value">{total_deaths}</div>
      </div>
    </div>

    <div class="main-content">
      <div class="panel">
        <div class="section-title">Highlights</div>
        <div class="highlight-grid">
          <div class="highlight-card">
            <h3>💰 Big Spender</h3>
            <div class="highlight-value">
              <span class="name">{escape(top_spender[0])}</span>
              <span class="detail"> — {copper_to_gsc_short(top_spender[1])}</span>
            </div>
          </div>
          <div class="highlight-card">
            <h3>💀 Most Deaths</h3>
            <div class="highlight-value">
              <span class="name">{escape(most_deaths[0])}</span>
              <span class="detail"> — {most_deaths[2]} death{"s" if most_deaths[2] != 1 else ""}</span>
            </div>
          </div>
          <div class="highlight-card">
            <h3>👹 Boss Deaths Leader</h3>
            <div class="highlight-value">
              <span class="name">{escape(top_boss_deaths[0])}</span>
              <span class="detail"> — {top_boss_deaths[1]["boss"]} deaths</span>
            </div>
          </div>
          <div class="highlight-card">
            <h3>🗑️ Trash Deaths Leader</h3>
            <div class="highlight-value">
              <span class="name">{escape(top_trash_deaths[0])}</span>
              <span class="detail"> — {top_trash_deaths[1]["trash"]} deaths</span>
            </div>
          </div>
          <div class="highlight-card">
            <h3>🟢 Healthstone King</h3>
            <div class="highlight-value">
              <span class="name">{escape(top_healthstones[0])}</span>
              <span class="detail"> — {top_healthstones[1]} used</span>
            </div>
          </div>
          <div class="highlight-card">
            <h3>😇 Resurrection Leader</h3>
            <div class="highlight-value">
              <span class="name">{escape(top_resurrections[0])}</span>
              <span class="detail"> — {top_resurrections[1]} casts</span>
            </div>
          </div>
          <div class="highlight-card">
            <h3>🍊 Top Orange Consumer</h3>
            <div class="highlight-value">
              <span class="name">{escape(top_orange[0])}</span>
              <span class="detail"> — {top_orange[1]} used</span>
            </div>
          </div>
          <div class="fun-stats">
            <h3>📊 Raid Stats</h3>
            <div class="fun-stat-item">
              <span>Avg cost per raider</span>
              <strong>{copper_to_gsc_short(avg_cost)}</strong>
            </div>
            <div class="fun-stat-item">
              <span>Zero-death raiders</span>
              <strong>{zero_death_count}/{players}</strong>
            </div>
          </div>
          {sunder_html}
        </div>
      </div>

      <div class="panel">
        <div class="section-title">All Raiders</div>
        <div class="table-card">
          <table class="raid-table">
            <colgroup>
              <col class="col-rank">
              <col class="col-name">
              <col class="col-stat">
              <col class="col-stat">
              <col class="col-stat">
              <col class="col-stat">
              <col class="col-stat">
              <col class="col-stat">
              <col class="col-stat">
            </colgroup>
            <thead>
              <tr>
                <th>#</th>
                <th class="sortable" data-type="text">Raider</th>
                <th class="sortable sorted-desc" data-type="number">Spend</th>
                <th class="sortable" data-type="number">Deaths</th>
                <th class="sortable" data-type="number">Boss</th>
                <th class="sortable" data-type="number">Trash</th>
                <th class="sortable" data-type="number">Healthstones</th>
                <th class="sortable" data-type="number">Oranges</th>
                <th class="sortable" data-type="number">Resurrections</th>
              </tr>
            </thead>
            <tbody>
              {table_rows}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="footer">
      <span>Generated by summarize_consumes</span>
      <span>Prices: {escape(server_name)} AH</span>
    </div>
  </div>
  <script>
    (function () {{
      const table = document.querySelector('.raid-table');
      if (!table) return;
      const headers = Array.from(table.querySelectorAll('th.sortable'));
      const tbody = table.querySelector('tbody');

      const clearSortIndicators = () => {{
        headers.forEach((header) => {{
          header.classList.remove('sorted-asc', 'sorted-desc');
        }});
      }};

      const sortRows = (columnIndex, type, direction) => {{
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const multiplier = direction === 'asc' ? 1 : -1;
        rows.sort((a, b) => {{
          const aCell = a.children[columnIndex];
          const bCell = b.children[columnIndex];
          const aValue = aCell?.dataset.value ?? aCell?.textContent.trim();
          const bValue = bCell?.dataset.value ?? bCell?.textContent.trim();
          if (type === 'number') {{
            return (Number(aValue) - Number(bValue)) * multiplier;
          }}
          return String(aValue).localeCompare(String(bValue)) * multiplier;
        }});
        rows.forEach((row) => tbody.appendChild(row));
      }};

      headers.forEach((header) => {{
        header.addEventListener('click', () => {{
          const columnIndex = header.cellIndex;
          const type = header.dataset.type || 'text';
          const isDesc = header.classList.contains('sorted-desc');
          const direction = isDesc ? 'asc' : 'desc';
          clearSortIndicators();
          header.classList.add(direction === 'asc' ? 'sorted-asc' : 'sorted-desc');
          sortRows(columnIndex, type, direction);
        }});
      }});
    }})();
  </script>
</body>
</html>'''

    return html


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Discord-ready consume card and optional full report.",
    )
    parser.add_argument("csv", help="consumable-totals.csv with name,copper,deaths")
    parser.add_argument("out_html", help="Output HTML file path")
    parser.add_argument("combat_log", nargs="?", help="Optional: WoW combat log for guild/pet filtering")
    parser.add_argument("logger_name", nargs="?", help="Optional: Character name who logged (for 'You die.' counts)")
    parser.add_argument("summary", nargs="?", help="Optional: Summary file with Sunder Armor data")
    parser.add_argument(
        "--full-report",
        dest="full_report",
        help="Optional: Output path for full-size HTML report",
    )

    args = parser.parse_args()

    csv_path = Path(args.csv)
    out_html = Path(args.out_html)
    log_path = Path(args.combat_log) if args.combat_log else None
    logger_name = args.logger_name
    summary_path = Path(args.summary) if args.summary else None
    full_report_path = Path(args.full_report) if args.full_report else None
    
    if not csv_path.exists():
        print(f"[ERROR] Missing CSV: {csv_path}")
        return 1
    
    target_guilds = list(GUILD_CONFIG.keys())
    
    guild_members: set[str] = set()
    pets: set[str] = set()
    raid_name = "Raid"
    raid_date = datetime.now().strftime("%d %b %Y")  # Default fallback
    logger_deaths = 0
    death_breakdown: dict[str, dict[str, int]] = {}
    healthstone_uses: dict[str, int] = {}
    orange_uses: dict[str, int] = {}
    resurrection_casts: dict[str, int] = {}
    
    if log_path and log_path.exists():
        print(f"[INFO] Parsing combat log: {log_path}")
        guild_members = parse_combat_log_for_guilds(log_path, target_guilds)
        pets = parse_combat_log_for_pets(log_path)
        raid_name = detect_raid_from_log(log_path)
        raid_date = extract_raid_date_from_log(log_path)
        print(f"[INFO] Found {len(guild_members)} guild members")
        print(f"[INFO] Found {len(pets)} pet names")
        print(f"[INFO] Detected raid: {raid_name}")
        print(f"[INFO] Raid date: {raid_date}")
        
        if logger_name:
            logger_deaths = count_logger_deaths(log_path)
            print(f"[INFO] Logger '{logger_name}': {logger_deaths} deaths from 'You die.'")
    
    sunder_data = []
    if summary_path and summary_path.exists():
        print(f"[INFO] Parsing sunder data: {summary_path}")
        sunder_data = parse_sunder_data(summary_path)
        print(f"[INFO] Found {len(sunder_data)} sunder entries")
    
    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=",")
        for line in reader:
            if not line or len(line) < 2:
                continue
            name = line[0].strip()
            copper = safe_int(line[1], 0)
            deaths = safe_int(line[2], 0) if len(line) > 2 else 0
            
            if not name or name in pets:
                continue
            
            if guild_members and name not in guild_members:
                continue
            
            if logger_name and name == logger_name:
                deaths += logger_deaths
            
            rows.append((name, copper, deaths))
    
    if not rows:
        print("[ERROR] No valid rows!")
        return 1
    
    rows.sort(key=lambda x: x[1], reverse=True)
    print(f"[INFO] {len(rows)} players after filtering")

    raider_names = {name for name, _, _ in rows}
    if log_path and log_path.exists():
        death_breakdown = parse_death_breakdown(log_path, raider_names, raid_name, logger_name)
        healthstone_uses = parse_healthstone_uses(log_path, raider_names, logger_name)
        orange_uses = parse_orange_uses(log_path, raider_names, logger_name)
        resurrection_casts = parse_resurrection_casts(log_path, raider_names, logger_name)
        if death_breakdown:
            rows = [
                (name, copper, death_breakdown.get(name, {"total": deaths})["total"])
                for name, copper, deaths in rows
            ]

    script_dir = Path(__file__).parent
    icon_data = {}
    for guild, config in GUILD_CONFIG.items():
        icon_path = script_dir / config["icon_path"]
        if icon_path.exists():
            icon_data[guild] = load_icon_base64(icon_path)
    
    html = generate_html(
        rows=rows,
        guild_names=target_guilds,
        raid_name=raid_name,
        server_name=SERVER_NAME,
        icon_data=icon_data,
        date_str=raid_date,
        sunder_data=sunder_data,
    )
    
    out_html.write_text(html, encoding="utf-8")
    print(f"[OK] Wrote {out_html}")

    if full_report_path:
        full_html = generate_full_report_html(
            rows=rows,
            guild_names=target_guilds,
            raid_name=raid_name,
            server_name=SERVER_NAME,
            icon_data=icon_data,
            date_str=raid_date,
            sunder_data=sunder_data,
            death_breakdown=death_breakdown,
            healthstone_uses=healthstone_uses,
            orange_uses=orange_uses,
            resurrection_casts=resurrection_casts,
        )
        full_report_path.write_text(full_html, encoding="utf-8")
        print(f"[OK] Wrote {full_report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
