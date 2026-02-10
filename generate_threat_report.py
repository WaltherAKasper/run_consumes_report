#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

LINE_MARKER = "TWT_THREAT"
PACKET_PREFIX = "TWTv4="
PART_RE = re.compile(r"_part(\d+)\.txt(?:\.txt)?$", re.IGNORECASE)

TARGET_GUILDS = ["Dark Sun", "Knights Hospitaller"]

RAID_ZONE_KEYWORDS: list[tuple[str, str]] = [
    ("Naxxramas", "naxxramas"),
    ("Onyxia's Lair", "onyxia"),
    ("Molten Core", "molten core"),
    ("Blackwing Lair", "blackwing lair"),
    ("Temple of Ahn'Qiraj", "ahn'qiraj temple"),
    ("Ruins of Ahn'Qiraj", "ruins of ahn'qiraj"),
    ("Zul'Gurub", "zul'gurub"),
]

RAID_BOSSES = {
    "Naxxramas": [
        "Anub'Rekhan", "Grand Widow Faerlina", "Maexxna", "Noth the Plaguebringer",
        "Heigan the Unclean", "Loatheb", "Instructor Razuvious", "Gothik the Harvester",
        "The Four Horsemen", "Patchwerk", "Grobbulus", "Gluth", "Thaddius", "Sapphiron", "Kel'Thuzad",
    ],
    "Onyxia's Lair": ["Onyxia"],
    "Molten Core": [
        "Lucifron", "Magmadar", "Gehennas", "Garr", "Shazzrah", "Baron Geddon",
        "Golemagg the Incinerator", "Sulfuron Harbinger", "Majordomo Executus", "Ragnaros",
    ],
    "Blackwing Lair": [
        "Razorgore the Untamed", "Vaelastrasz the Corrupt", "Broodlord Lashlayer", "Firemaw",
        "Ebonroc", "Flamegor", "Chromaggus", "Nefarian",
    ],
    "Temple of Ahn'Qiraj": [
        "The Prophet Skeram", "Battleguard Sartura", "Fankriss the Unyielding", "Princess Huhuran",
        "Viscidus", "Twin Emperors", "Ouro", "C'Thun",
    ],
    "Ruins of Ahn'Qiraj": [
        "Kurinnaxx", "General Rajaxx", "Moam", "Buru the Gorger", "Ayamiss the Hunter", "Ossirian the Unscarred",
    ],
    "Zul'Gurub": [
        "High Priest Venoxis", "High Priestess Jeklik", "High Priestess Mar'li", "High Priest Thekal",
        "High Priestess Arlokk", "Jin'do the Hexxer", "Hakkar",
    ],
}

TAUNT_ABILITIES = {"Taunt", "Growl", "Mocking Blow", "Challenging Shout", "Challenging Roar"}
TANK_ABILITIES = {
    "Sunder Armor", "Revenge", "Shield Slam", "Shield Block", "Demoralizing Shout",
    "Righteous Fury", "Holy Shield", "Defensive Stance", "Bear Form", "Dire Bear Form",
    "Maul", "Swipe",
}
HEALING_SPELL_HINTS = {
    "Heal", "Flash Heal", "Greater Heal", "Prayer of Healing", "Renew", "Rejuvenation", "Regrowth",
    "Healing Touch", "Lesser Healing Wave", "Chain Heal", "Holy Light", "Flash of Light", "Swiftmend",
}


@dataclass
class Entry:
    time: float
    unit: str
    tank: int
    threat: float
    percent: float
    melee: int


@dataclass
class Snapshot:
    time: float
    sender: str
    target_guid: str
    target_name: str
    entries: list[Entry]


@dataclass
class Fight:
    target_guid: str
    target_name: str
    snapshots: list[Snapshot] = field(default_factory=list)

    @property
    def start(self) -> float:
        return self.snapshots[0].time

    @property
    def end(self) -> float:
        return self.snapshots[-1].time

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def zone_to_raid(zone_name: str) -> str | None:
    zone = zone_name.strip().lower()
    for raid_name, keyword in RAID_ZONE_KEYWORDS:
        if keyword in zone:
            return raid_name
    if "aq20" in zone:
        return "Ruins of Ahn'Qiraj"
    if "aq40" in zone:
        return "Temple of Ahn'Qiraj"
    return None


def detect_raid_from_log(log_path: Path) -> str | None:
    if not log_path.exists():
        return None
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if "ZONE_INFO:" not in line:
                continue
            parts = line.split("&")
            if len(parts) < 2:
                continue
            raid = zone_to_raid(parts[1])
            if raid:
                return raid
    return None


def parse_combat_log_for_guilds(log_path: Path, target_guilds: list[str]) -> set[str]:
    guild_members = set()
    if not log_path.exists():
        return guild_members
    pattern = re.compile(
        r"COMBATANT_INFO:.*?&([^&]+)&[A-Z]+&[A-Za-z]+&\d+&[^&]*&(" + "|".join(re.escape(g) for g in target_guilds) + r")&"
    )
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = pattern.search(line)
            if match:
                guild_members.add(match.group(1).strip())
    return guild_members


def parse_role_signals(log_path: Path, players: set[str]) -> dict[str, dict[str, int]]:
    signals = {p: {"heals": 0, "taunts": 0, "tank_abilities": 0} for p in players}
    if not log_path.exists() or not players:
        return signals

    casts_re = re.compile(r"\s([A-Za-z][A-Za-z'\-]+) casts ([^.]+?)(?: on [^.]+)?\.")
    gains_re = re.compile(r"\s([A-Za-z][A-Za-z'\-]+) gains ([^.]+)\.")
    heal_re = re.compile(r"\s([A-Za-z][A-Za-z'\-]+)(?:'s [^.]+)? heals ")

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            m = heal_re.search(line)
            if m:
                caster = m.group(1)
                if caster in players:
                    signals[caster]["heals"] += 1

            m = casts_re.search(line)
            if m:
                caster, spell = m.group(1), m.group(2).strip()
                if caster in players:
                    if spell in TAUNT_ABILITIES:
                        signals[caster]["taunts"] += 1
                    if spell in TANK_ABILITIES:
                        signals[caster]["tank_abilities"] += 1
                    if any(h in spell for h in HEALING_SPELL_HINTS):
                        signals[caster]["heals"] += 1

            m = gains_re.search(line)
            if m:
                caster, aura = m.group(1), m.group(2).strip()
                if caster in players and aura in TANK_ABILITIES:
                    signals[caster]["tank_abilities"] += 1
    return signals


def parse_entry(raw: str, snap_time: float) -> Entry | None:
    parts = raw.split(":")
    if len(parts) != 5:
        return None
    unit, tank, threat, pct, melee = parts
    try:
        return Entry(
            time=snap_time,
            unit=unit.strip(),
            tank=int(float(tank)),
            threat=float(threat),
            percent=float(pct),
            melee=int(float(melee)),
        )
    except ValueError:
        return None


def parse_snapshot(line: str) -> Snapshot | None:
    cols = line.rstrip("\n").split("\t")
    if len(cols) < 6 or cols[0] != LINE_MARKER:
        return None
    try:
        snap_time = float(cols[1])
    except ValueError:
        return None
    sender, target_guid, target_name = cols[2], cols[3], cols[4]
    packet = cols[5]
    if not packet.startswith(PACKET_PREFIX):
        return None
    payload = packet[len(PACKET_PREFIX):]
    entries = []
    for chunk in payload.split(";"):
        parsed = parse_entry(chunk.strip(), snap_time)
        if parsed and parsed.unit:
            entries.append(parsed)
    if not entries:
        return None
    return Snapshot(
        time=snap_time,
        sender=sender,
        target_guid=target_guid or "UNKNOWN_GUID",
        target_name=target_name or "Unknown Target",
        entries=entries,
    )


def part_sort_key(path: Path) -> tuple[int, str]:
    m = PART_RE.search(path.name)
    return (int(m.group(1)) if m else 0, path.name)


def load_snapshots(log_dir: Path) -> list[Snapshot]:
    files = sorted(log_dir.glob("TWThreatThreatLog*_part*.txt*"), key=part_sort_key)
    snapshots: list[Snapshot] = []
    for path in files:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                snap = parse_snapshot(line)
                if snap:
                    snapshots.append(snap)
    snapshots.sort(key=lambda s: s.time)
    return snapshots


def split_fights(snapshots: list[Snapshot], gap_seconds: float, min_duration: float, min_snapshots: int) -> list[Fight]:
    fights: list[Fight] = []
    by_target: dict[tuple[str, str], list[Snapshot]] = defaultdict(list)
    for snap in snapshots:
        by_target[(snap.target_guid, snap.target_name)].append(snap)

    for (guid, name), snaps in by_target.items():
        snaps.sort(key=lambda s: s.time)
        current = Fight(target_guid=guid, target_name=name)
        last_time = None
        for snap in snaps:
            if last_time is not None and snap.time - last_time > gap_seconds and current.snapshots:
                fights.append(current)
                current = Fight(target_guid=guid, target_name=name)
            current.snapshots.append(snap)
            last_time = snap.time
        if current.snapshots:
            fights.append(current)

    fights = [f for f in fights if f.duration >= min_duration and len(f.snapshots) >= min_snapshots]
    fights.sort(key=lambda f: f.start)
    return fights




def infer_raid_from_fights(fights: list[Fight]) -> str | None:
    target_names = {f.target_name for f in fights}
    best_raid = None
    best_hits = 0
    for raid, bosses in RAID_BOSSES.items():
        hits = len(target_names.intersection(bosses))
        if hits > best_hits:
            best_hits = hits
            best_raid = raid
    return best_raid if best_hits > 0 else None
def filter_to_boss_fights(fights: list[Fight], boss_names: set[str]) -> list[Fight]:
    if not boss_names:
        return fights
    return [f for f in fights if f.target_name in boss_names]


def build_unit_stats(fight: Fight, allowed_players: set[str]) -> dict[str, dict[str, float]]:
    per_unit: dict[str, dict[str, float]] = {}
    for snap in fight.snapshots:
        for e in snap.entries:
            if e.unit not in allowed_players:
                continue
            s = per_unit.setdefault(
                e.unit,
                {
                    "first_time": e.time,
                    "last_time": e.time,
                    "first_threat": e.threat,
                    "last_threat": e.threat,
                    "pct_sum": 0.0,
                    "pct_n": 0,
                    "tank_count": 0,
                    "samples": 0,
                },
            )
            if e.time < s["first_time"]:
                s["first_time"] = e.time
                s["first_threat"] = e.threat
            if e.time > s["last_time"]:
                s["last_time"] = e.time
                s["last_threat"] = e.threat
            if e.time == s["first_time"]:
                s["first_threat"] = min(s["first_threat"], e.threat)
            if e.time == s["last_time"]:
                s["last_threat"] = max(s["last_threat"], e.threat)
            s["pct_sum"] += e.percent
            s["pct_n"] += 1
            s["tank_count"] += int(e.tank == 1)
            s["samples"] += 1

    for stats in per_unit.values():
        dt = max(0.0, stats["last_time"] - stats["first_time"])
        dthreat = max(0.0, stats["last_threat"] - stats["first_threat"])
        stats["duration"] = dt
        stats["threat_done"] = dthreat
        stats["tps"] = dthreat / dt if dt > 0 else 0.0
        stats["avg_pct"] = stats["pct_sum"] / stats["pct_n"] if stats["pct_n"] else 0.0
        stats["tank_ratio"] = stats["tank_count"] / stats["samples"] if stats["samples"] else 0.0
    return per_unit


def classify_role(player: str, avg_pct: float, tank_ratio: float, signals: dict[str, dict[str, int]]) -> tuple[str, str]:
    sig = signals.get(player, {"heals": 0, "taunts": 0, "tank_abilities": 0})
    heals = sig["heals"]
    taunts = sig["taunts"]
    tank_acts = sig["tank_abilities"]

    if taunts >= 2 or tank_ratio >= 0.55 or (tank_acts >= 8 and avg_pct >= 60):
        return "tank", "Tank"
    if heals >= max(10, (tank_acts + taunts) * 2):
        return "healer", "Healer"
    return "dps", "DPS"


def fmt_num(value: float) -> str:
    return f"{value:,.1f}"


def render_report(
    fights: list[Fight],
    output_path: Path,
    source_files: list[str],
    gap_seconds: float,
    raid_name: str,
    players: set[str],
    role_signals: dict[str, dict[str, int]],
) -> None:
    fight_rows_html = []
    raid_summary = defaultdict(lambda: {"threat": 0.0, "duration": 0.0, "fights": 0, "pct": [], "tank_ratio": []})

    for idx, fight in enumerate(fights, start=1):
        unit_stats = build_unit_stats(fight, players)
        rows = []
        for unit, s in sorted(unit_stats.items(), key=lambda item: item[1]["threat_done"], reverse=True):
            cls, label = classify_role(unit, s["avg_pct"], s["tank_ratio"], role_signals)
            rows.append(
                f"<tr><td>{html.escape(unit)}</td>"
                f"<td><span class='badge {cls}'>{label}</span></td>"
                f"<td>{fmt_num(s['threat_done'])}</td>"
                f"<td>{fmt_num(s['tps'])}</td>"
                f"<td>{s['avg_pct']:.1f}%</td>"
                f"<td>{s['samples']:.0f}</td></tr>"
            )
            raid_summary[unit]["threat"] += s["threat_done"]
            raid_summary[unit]["duration"] += s["duration"]
            raid_summary[unit]["fights"] += 1
            raid_summary[unit]["pct"].append(s["avg_pct"])
            raid_summary[unit]["tank_ratio"].append(s["tank_ratio"])

        fight_rows_html.append(
            f"""
      <section class='panel'>
        <div class='panel-header'>
          <h3>{idx}. {html.escape(fight.target_name)}</h3>
          <div class='fight-meta'>{fight.duration:.1f}s • {len(fight.snapshots)} snapshots</div>
        </div>
        <table>
          <thead><tr><th>Player</th><th>Role</th><th>Threat Done</th><th>TPS</th><th>Avg Top %</th><th>Samples</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </section>
            """
        )

    summary_rows = []
    for unit, s in sorted(raid_summary.items(), key=lambda item: item[1]["threat"], reverse=True):
        tps = s["threat"] / s["duration"] if s["duration"] > 0 else 0.0
        avg_pct = mean(s["pct"]) if s["pct"] else 0.0
        avg_tank_ratio = mean(s["tank_ratio"]) if s["tank_ratio"] else 0.0
        cls, label = classify_role(unit, avg_pct, avg_tank_ratio, role_signals)
        sig = role_signals.get(unit, {"taunts": 0, "heals": 0})
        summary_rows.append(
            f"<tr><td>{html.escape(unit)}</td><td><span class='badge {cls}'>{label}</span></td>"
            f"<td>{s['fights']}</td><td>{fmt_num(s['threat'])}</td><td>{fmt_num(tps)}</td><td>{avg_pct:.1f}%</td><td>{sig['heals']}</td><td>{sig['taunts']}</td></tr>"
        )

    total_snapshots = sum(len(f.snapshots) for f in fights)

    doc = f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8'>
  <meta name='viewport' content='width=1200'>
  <title>Raid Threat Report</title>
  <link rel='preconnect' href='https://fonts.googleapis.com'>
  <link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>
  <link href='https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Fira+Sans:wght@400;500;600;700&display=swap' rel='stylesheet'>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ width:1200px; background:linear-gradient(155deg,#0a0e14 0%,#131922 40%,#0f1419 100%); font-family:'Fira Sans',sans-serif; color:#e6edf3; }}
    .container {{ padding:32px 44px 48px; }}
    .header {{ display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:20px; }}
    .title {{ font-family:'Cinzel',serif; font-size:34px; font-weight:700; color:#f0f6fc; letter-spacing:1px; }}
    .subtitle {{ margin-top:6px; color:#8b949e; font-size:13px; }}
    .server-badge {{ background:linear-gradient(135deg,rgba(34,197,94,.15),rgba(34,197,94,.08)); border:1px solid rgba(34,197,94,.3); padding:8px 18px; border-radius:20px; font-size:12px; font-weight:600; color:#4ade80; letter-spacing:1px; text-transform:uppercase; }}
    .stats-row {{ display:flex; gap:16px; margin-bottom:20px; }}
    .stat-card {{ flex:1; background:rgba(22,27,34,.7); border:1px solid rgba(48,54,61,.6); border-radius:12px; padding:14px 18px; }}
    .stat-label {{ font-size:10px; color:#6e7681; text-transform:uppercase; letter-spacing:1.5px; margin-bottom:6px; }}
    .stat-value {{ font-size:26px; font-weight:700; color:#f0f6fc; }}
    .panel {{ background:rgba(22,27,34,.6); border:1px solid rgba(48,54,61,.5); border-radius:12px; padding:16px; margin-bottom:16px; }}
    .panel-header {{ display:flex; justify-content:space-between; align-items:baseline; margin-bottom:10px; gap:20px; }}
    .panel h3 {{ font-size:18px; color:#f0f6fc; }}
    .fight-meta {{ font-size:12px; color:#8b949e; white-space:nowrap; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ padding:8px 10px; text-align:left; border-bottom:1px solid rgba(110,118,129,.25); font-size:13px; }}
    th {{ font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:1px; }}
    .badge {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; border:1px solid transparent; }}
    .badge.tank {{ color:#fca5a5; border-color:rgba(248,113,113,.5); background:rgba(127,29,29,.2); }}
    .badge.healer {{ color:#86efac; border-color:rgba(34,197,94,.5); background:rgba(20,83,45,.2); }}
    .badge.dps {{ color:#93c5fd; border-color:rgba(59,130,246,.5); background:rgba(30,58,138,.2); }}
    .footnote {{ margin-top:8px; color:#6e7681; font-size:12px; line-height:1.5; }}
  </style>
</head>
<body>
  <div class='container'>
    <div class='header'>
      <div>
        <div class='title'>Raid Threat Report</div>
        <div class='subtitle'>{html.escape(raid_name)} • guild-filtered players only ({', '.join(TARGET_GUILDS)})</div>
      </div>
      <div class='server-badge'>TWThreat v4</div>
    </div>

    <div class='stats-row'>
      <div class='stat-card'><div class='stat-label'>Detected Boss Fights</div><div class='stat-value'>{len(fights)}</div></div>
      <div class='stat-card'><div class='stat-label'>Boss Targets</div><div class='stat-value'>{len({f.target_name for f in fights})}</div></div>
      <div class='stat-card'><div class='stat-label'>Threat Snapshots</div><div class='stat-value'>{total_snapshots:,}</div></div>
      <div class='stat-card'><div class='stat-label'>Guild Players Seen</div><div class='stat-value'>{len(players)}</div></div>
    </div>

    <section class='panel'>
      <div class='panel-header'><h3>Raid Summary</h3></div>
      <table>
        <thead><tr><th>Player</th><th>Role</th><th>Fights</th><th>Total Threat Done</th><th>Weighted TPS</th><th>Avg Top %</th><th>Heals</th><th>Taunts</th></tr></thead>
        <tbody>{''.join(summary_rows)}</tbody>
      </table>
      <p class='footnote'>Input files: {html.escape(', '.join(source_files))}</p>
      <p class='footnote'>Fights are grouped by target GUID + target name and split when gaps exceed {gap_seconds:.0f}s. Non-boss targets are removed using raid boss list for {html.escape(raid_name)}.</p>
    </section>

    {''.join(fight_rows_html)}
  </div>
</body>
</html>
"""
    output_path.write_text(doc, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a themed raid threat HTML report from TWThreat logs.")
    parser.add_argument("--log-dir", default="ThreatLogs", help="Directory containing TWThreat log part files")
    parser.add_argument("--combat-log", default="WoWCombatLog.txt", help="Combat log path for guild/raid/role detection")
    parser.add_argument("--output", default="ThreatLogs/raid-threat-report.html", help="Output HTML file")
    parser.add_argument("--gap", type=float, default=30.0, help="Gap (seconds) to split fights")
    parser.add_argument("--min-duration", type=float, default=10.0, help="Minimum fight duration to include")
    parser.add_argument("--min-snapshots", type=int, default=25, help="Minimum snapshots in a fight to include")
    parser.add_argument("--raid", default="", help="Optional raid name override for boss filtering")
    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    combat_log = Path(args.combat_log)
    output = Path(args.output)

    snapshots = load_snapshots(log_dir)
    all_fights = split_fights(snapshots, args.gap, args.min_duration, args.min_snapshots)

    raid_name = args.raid or infer_raid_from_fights(all_fights) or detect_raid_from_log(combat_log) or "Unknown Raid"
    boss_names = set(RAID_BOSSES.get(raid_name, []))
    fights = filter_to_boss_fights(all_fights, boss_names)

    players = parse_combat_log_for_guilds(combat_log, TARGET_GUILDS)
    role_signals = parse_role_signals(combat_log, players)

    files = [p.name for p in sorted(log_dir.glob("TWThreatThreatLog*_part*.txt*"), key=part_sort_key)]
    render_report(fights, output, files, args.gap, raid_name, players, role_signals)
    print(f"Wrote {output} ({len(fights)} boss fights from {len(snapshots)} snapshots; raid={raid_name})")


if __name__ == "__main__":
    main()
