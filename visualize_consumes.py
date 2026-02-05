import csv
import re
import sys
from pathlib import Path
from html import escape

NUM_RE = re.compile(r"-?\d+")

def to_int_any(x) -> int:
    if x is None:
        return 0
    s = str(x).strip()
    if not s:
        return 0
    m = NUM_RE.search(s.replace(",", ""))
    return int(m.group(0)) if m else 0

def copper_to_gsc(copper: int) -> str:
    g = copper // 10000
    s = (copper % 10000) // 100
    c = copper % 100
    return f"{g}g {s:02d}s {c:02d}c"

def make_bar(value: int, max_value: int, width_px: int = 520) -> str:
    if max_value <= 0:
        return ""
    w = int((value / max_value) * width_px)
    return f'<div class="bar" style="width:{w}px"></div>'

def sniff_delim(sample: str) -> str:
    # Try Sniffer first, then fallback heuristic
    try:
        d = csv.Sniffer().sniff(sample, delimiters=";,|\t,")
        return getattr(d, "delimiter", ",")
    except Exception:
        return ";" if sample.count(";") > sample.count(",") else ","

def main():
    if len(sys.argv) < 3:
        print("Usage: visualize_consumes.py <consumable-totals.csv> <report.html>")
        return 2

    csv_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    if not csv_path.exists():
        print(f"[ERROR] CSV not found: {csv_path}")
        return 1

    raw = csv_path.read_text(encoding="utf-8-sig", errors="replace")
    sample = "\n".join(raw.splitlines()[:50])
    delim = sniff_delim(sample)

    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=delim)
        first = True
        for row in reader:
            if not row or len(row) < 2:
                continue

            # Handle optional header row:
            # If col2 isn't numeric on first row, treat it as headers and skip.
            if first:
                first = False
                if to_int_any(row[1]) == 0 and row[1].strip().lower() in ("copper", "cost", "total", "total_cost"):
                    continue
                # Another header pattern: "name,copper,deaths"
                if row[0].strip().lower() in ("name", "player", "character") and row[1].strip().lower() in ("copper", "cost"):
                    continue

            name = row[0].strip()
            copper = to_int_any(row[1])
            deaths = to_int_any(row[2]) if len(row) > 2 else 0

            if name:
                rows.append((name, copper, deaths))

    rows.sort(key=lambda x: x[1], reverse=True)
    total_copper = sum(r[1] for r in rows)
    max_copper = rows[0][1] if rows else 0

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Consume Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    h1 {{ margin: 0 0 8px 0; }}
    .meta {{ color: #555; margin-bottom: 18px; }}
    .warn {{ background:#fff3cd; border:1px solid #ffeeba; padding:12px; border-radius:8px; margin: 14px 0; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f4f4f4; }}
    .barwrap {{ display:flex; align-items:center; gap:12px; }}
    .bar {{ height: 14px; background: #333; border-radius: 8px; }}
    .num {{ white-space: nowrap; font-variant-numeric: tabular-nums; }}
    .small {{ color:#666; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>Consume totals (per player)</h1>
  <div class="meta">
    File: <span class="num">{escape(str(csv_path.name))}</span><br/>
    Players: <span class="num">{len(rows)}</span><br/>
    Total cost: <span class="num">{copper_to_gsc(total_copper)}</span>
    <span class="small">({total_copper} copper)</span><br/>
    Delimiter detected: <span class="num">{escape(delim)}</span>
  </div>
"""

    if not rows:
        html += """
  <div class="warn">
    <b>No rows parsed from the CSV.</b><br/>
    Open <code>consumable-totals.csv</code> and confirm it contains rows like <code>Name,1337,2</code>.
  </div>
</body></html>
"""
        out_path.write_text(html, encoding="utf-8")
        print("[WARN] No rows parsed. Report generated with warning box.")
        return 0

    html += """
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Player</th>
        <th>Total cost</th>
        <th>Deaths</th>
        <th>Visual</th>
      </tr>
    </thead>
    <tbody>
"""
    for i, (name, copper, deaths) in enumerate(rows, start=1):
        html += f"""
      <tr>
        <td class="num">{i}</td>
        <td>{escape(name)}</td>
        <td class="num">{copper_to_gsc(copper)}</td>
        <td class="num">{deaths}</td>
        <td>
          <div class="barwrap">
            {make_bar(copper, max_copper)}
            <span class="small num">{copper}</span>
          </div>
        </td>
      </tr>
"""
    html += """
    </tbody>
  </table>
</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")
    print(f"[OK] Wrote {out_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
