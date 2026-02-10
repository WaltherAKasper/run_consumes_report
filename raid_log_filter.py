#!/usr/bin/env python3
"""Filter a WoW combat log down to a selected raid segment.

The log can contain multiple raids in a single file. This script detects raid zones
from ZONE_INFO lines, lets you select one raid, and writes a filtered combat log
containing only lines captured while inside that selected raid.
"""

from __future__ import annotations

import argparse
from pathlib import Path


RAID_ZONE_KEYWORDS: list[tuple[str, str]] = [
    ("Naxxramas", "naxxramas"),
    ("Onyxia's Lair", "onyxia"),
    ("Molten Core", "molten core"),
    ("Blackwing Lair", "blackwing lair"),
    ("Temple of Ahn'Qiraj", "ahn'qiraj temple"),
    ("Ruins of Ahn'Qiraj", "ruins of ahn'qiraj"),
    ("Zul'Gurub", "zul'gurub"),
    ("Zul'Aman", "zul'aman"),
    ("Sunwell Plateau", "sunwell plateau"),
    ("Black Temple", "black temple"),
    ("Karazhan", "karazhan"),
    ("Gruul's Lair", "gruul's lair"),
    ("Magtheridon's Lair", "magtheridon's lair"),
    ("Serpentshrine Cavern", "serpentshrine cavern"),
    ("Tempest Keep", "tempest keep"),
    ("Battle for Mount Hyjal", "hyjal summit"),
]


def zone_to_raid(zone_name: str) -> str | None:
    zone = zone_name.strip().lower()
    if not zone:
        return None

    for raid_name, keyword in RAID_ZONE_KEYWORDS:
        if keyword in zone:
            return raid_name

    # Graceful legacy aliases
    if "aq40" in zone:
        return "Temple of Ahn'Qiraj"
    if "aq20" in zone:
        return "Ruins of Ahn'Qiraj"
    if "tempest" in zone:
        return "Tempest Keep"
    if "serpentshrine" in zone:
        return "Serpentshrine Cavern"

    return None


def extract_zone_name(line: str) -> str | None:
    if "ZONE_INFO:" not in line:
        return None

    parts = line.split("&")
    if len(parts) < 2:
        return None

    return parts[1].strip()


def detect_raids(log_path: Path) -> list[str]:
    raids: list[str] = []
    seen: set[str] = set()

    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            zone = extract_zone_name(line)
            if zone is None:
                continue

            raid = zone_to_raid(zone)
            if not raid or raid in seen:
                continue

            raids.append(raid)
            seen.add(raid)

    return raids


def choose_raid_interactive(raids: list[str]) -> str:
    if len(raids) == 1:
        raid = raids[0]
        print(f"[INFO] Only one raid detected: {raid}")
        return raid

    print("[INFO] Multiple raids detected in combat log:")
    for i, raid in enumerate(raids, start=1):
        print(f"  {i}. {raid}")

    while True:
        answer = input("Select raid by number or name: ").strip()
        if not answer:
            continue

        if answer.isdigit():
            idx = int(answer)
            if 1 <= idx <= len(raids):
                return raids[idx - 1]

        for raid in raids:
            if raid.lower() == answer.lower():
                return raid

        print("[WARN] Invalid selection. Try again.")


def filter_log_to_raid(log_path: Path, out_path: Path, selected_raid: str) -> int:
    lines_out: list[str] = []
    current_raid: str | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            zone = extract_zone_name(line)
            if zone is not None:
                mapped = zone_to_raid(zone)
                current_raid = mapped

            if current_raid == selected_raid:
                lines_out.append(line)

    if not lines_out:
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(lines_out), encoding="utf-8")
    return len(lines_out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect and filter raid segments from WoWCombatLog.txt")
    parser.add_argument("log_path", help="Input combat log path")
    parser.add_argument("out_path", nargs="?", help="Output filtered log path")
    parser.add_argument("--list", action="store_true", help="List detected raids and exit")
    parser.add_argument("--raid", help="Raid name to filter")
    parser.add_argument("--interactive", action="store_true", help="Prompt interactively when multiple raids exist")
    args = parser.parse_args()

    log_path = Path(args.log_path)
    if not log_path.exists():
        print(f"[ERROR] Missing combat log: {log_path}")
        return 1

    raids = detect_raids(log_path)
    if not raids:
        print("[ERROR] No raid zones detected in combat log.")
        return 1

    if args.list:
        print("Detected raids:")
        for raid in raids:
            print(f"- {raid}")
        return 0

    if not args.out_path:
        print("[ERROR] out_path is required unless --list is used.")
        return 1

    selected_raid = args.raid
    if selected_raid:
        canonical = None
        for raid in raids:
            if raid.lower() == selected_raid.lower():
                canonical = raid
                break

        if not canonical:
            print(f"[ERROR] Raid '{selected_raid}' not found in combat log.")
            print("[INFO] Available raids:")
            for raid in raids:
                print(f"  - {raid}")
            return 1

        selected_raid = canonical
    elif args.interactive:
        selected_raid = choose_raid_interactive(raids)
    elif len(raids) == 1:
        selected_raid = raids[0]
        print(f"[INFO] Auto-selected only detected raid: {selected_raid}")
    else:
        print("[ERROR] Multiple raids detected; choose one via --raid or --interactive.")
        print("[INFO] Available raids:")
        for raid in raids:
            print(f"  - {raid}")
        return 1

    out_path = Path(args.out_path)
    kept = filter_log_to_raid(log_path, out_path, selected_raid)
    if kept <= 0:
        print(f"[ERROR] No lines captured for raid '{selected_raid}'.")
        return 1

    print(f"[OK] Selected raid: {selected_raid}")
    print(f"[OK] Wrote filtered combat log: {out_path} ({kept} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())