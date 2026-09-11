#!/usr/bin/env python3
"""Generate a standalone focused HTML pinout for a single ECU from library/ecus/.

Each ECU gets:
  - An ECU info header (variant, CAN buses, safety class, priority)
  - A color-coded visual connector map (one tile per pin, grouped by connector)
  - The full interactive pin table with search / filter

Usage:
    python generate_library_ecu_pinout_single.py --ecu RC5-6
    python generate_library_ecu_pinout_single.py --ecu SRC14-34
    python generate_library_ecu_pinout_single.py  # generates all library ECUs individually

Output: exports/<safe_name>_pinout.html
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_tools = Path(__file__).resolve().parent
sys.path.insert(0, str(_tools))
import generate_architecture_html_pinout as P          # table + section helpers
import generate_library_ecu_pinout_html   as L          # rows_for_ecu, find_templates, elec_lines_from_cap

BASE = _tools.parent

# ---------------------------------------------------------------------------
# Color palette by pin type (used in connector map tiles)
# ---------------------------------------------------------------------------
_TYPE_COLORS: dict[str, tuple[str, str]] = {
    # type       bg                text
    "CAN":       ("#7c3aed", "#ede9fe"),
    "LIN":       ("#6d28d9", "#ede9fe"),
    "ETHERNET":  ("#0d9488", "#ccfbf1"),
    "ANALOG":    ("#0369a1", "#e0f2fe"),
    "DIGITAL":   ("#15803d", "#dcfce7"),
    "PWM":       ("#b45309", "#fef3c7"),
    "POWER":     ("#dc2626", "#fee2e2"),
    "GROUND":    ("#374151", "#f3f4f6"),
    "SENT":      ("#be185d", "#fce7f3"),
}
_DEFAULT_COLOR = ("#475569", "#f1f5f9")


def _tile_color(pin_type: str) -> tuple[str, str]:
    return _TYPE_COLORS.get(pin_type.upper(), _DEFAULT_COLOR)


def _role_symbol(role: str) -> str:
    return {"INPUT": "↓", "OUTPUT": "↑", "INOUT": "⇅",
            "SUPPLY": "⚡", "GROUND": "⏚"}.get(role.upper(), "·")


# ---------------------------------------------------------------------------
# Visual connector map
# ---------------------------------------------------------------------------

def _render_connector_map(ecu: dict, rows: list[dict]) -> str:
    """Render a color-coded tile grid, one section per connector."""
    # Build lookup: (connector, pin_str) → row
    row_map: dict[tuple[str, str], dict] = {
        (r["connector"], r["pin"]): r for r in rows
    }
    # Group pins by connector (sorted by connector name then pin number)
    connectors: dict[str, list[dict]] = {}
    for r in rows:
        connectors.setdefault(r["connector"], []).append(r)
    for pins_list in connectors.values():
        pins_list.sort(key=lambda r: (int(r["pin"]) if r["pin"].isdigit() else 99999))

    # Legend
    seen_types = sorted({r["type"] for r in rows})
    legend_items = []
    for t in seen_types:
        bg, fg = _tile_color(t)
        legend_items.append(
            f'<span class="cmap-legend-item" style="background:{bg};color:{fg}">'
            f'{P.esc(t)}</span>'
        )
    legend_html = "\n      ".join(legend_items)

    # One section per connector
    sections = []
    for conn_name in sorted(connectors):
        pins_list = connectors[conn_name]
        tiles = []
        for r in pins_list:
            bg, fg = _tile_color(r["type"])
            sym = _role_symbol(r["direction"])
            tip = (
                f'{r["connector"]} K{r["pin"]} · {r["pin_name"]}\n'
                f'Group: {r["group"]}\n'
                f'Type: {r["type"]}  Dir: {r["direction"]}\n'
                f'Electrical: {", ".join(r["electrical_lines"]) if r["electrical_lines"] else "—"}'
            )
            assigned_cls = "cmap-tile-assigned" if r["assigned"] == "assigned" else ""
            tiles.append(
                f'<div class="cmap-tile {assigned_cls}" '
                f'style="background:{bg};color:{fg}" '
                f'title="{P.esc(tip)}" '
                f'data-pin="{P.esc(r["pin"])}" '
                f'data-conn="{P.esc(conn_name)}">'
                f'<div class="cmap-pin-num">K{P.esc(r["pin"])}</div>'
                f'<div class="cmap-pin-name">{P.esc((r["pin_name"] or "")[:8])}</div>'
                f'<div class="cmap-pin-sym">{sym}</div>'
                f'</div>'
            )
        tiles_html = "\n        ".join(tiles)
        sections.append(f"""
    <div class="cmap-connector">
      <h3 class="cmap-connector-name">{P.esc(conn_name)}</h3>
      <div class="cmap-grid">
        {tiles_html}
      </div>
    </div>""")

    return f"""
<section class="cmap-section">
  <div class="cmap-header">
    <h2>Connector Map</h2>
    <p>Hover a tile for full pin detail. Assigned pins have a white ring.</p>
  </div>
  <div class="cmap-legend">
    {legend_html}
  </div>
  {"".join(sections)}
</section>"""


# ---------------------------------------------------------------------------
# ECU metadata header card
# ---------------------------------------------------------------------------

def _render_ecu_header(ecu: dict) -> str:
    name      = P.esc(ecu.get("name", "ECU"))
    variant   = P.esc(ecu.get("variant", "—"))
    maker     = P.esc(ecu.get("manufacturer", ""))
    series    = P.esc(ecu.get("series", ""))
    doc       = P.esc(ecu.get("document", ""))
    priority  = P.esc(ecu.get("priority", "—"))
    safety    = P.esc(ecu.get("safety", "—"))
    can_addrs = ecu.get("can_addresses", [])
    can_str   = P.esc(", ".join(str(a) for a in can_addrs)) if can_addrs else "—"
    pins_cnt  = len(ecu.get("pins", []))

    meta_items = [
        ("Variant",    variant),
        ("Pins",       str(pins_cnt)),
        ("Priority",   priority),
        ("Safety",     safety),
        ("CAN",        can_str),
    ]
    if maker:
        meta_items.insert(0, ("Manufacturer", maker))
    if series:
        meta_items.append(("Series", series))
    if doc:
        meta_items.append(("Document", doc))

    meta_html = "\n    ".join(
        f'<div class="ecu-meta-item"><span class="ecu-meta-label">{k}</span>'
        f'<span class="ecu-meta-value">{v}</span></div>'
        for k, v in meta_items
    )
    return f"""
<div class="ecu-header-card">
  <div class="ecu-header-title">
    <h1>{name}</h1>
  </div>
  <div class="ecu-meta-grid">
    {meta_html}
  </div>
</div>"""


# ---------------------------------------------------------------------------
# CSS additions
# ---------------------------------------------------------------------------

_EXTRA_CSS = """
/* ── ECU header card ── */
.ecu-header-card {
  background: var(--panel, #1e293b);
  border: 1px solid var(--border, rgba(255,255,255,0.1));
  border-radius: 14px;
  padding: 24px 28px;
  margin-bottom: 28px;
  display: grid;
  gap: 18px;
}
.ecu-header-title h1 { margin: 0; font-size: 26px; }
.ecu-meta-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 28px;
}
.ecu-meta-item { display: flex; flex-direction: column; gap: 2px; }
.ecu-meta-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .09em;
  text-transform: uppercase;
  color: var(--muted, #94a3b8);
}
.ecu-meta-value { font-size: 14px; font-weight: 600; }

/* ── Connector map ── */
.cmap-section {
  background: var(--panel, #1e293b);
  border: 1px solid var(--border, rgba(255,255,255,0.1));
  border-radius: 14px;
  padding: 22px 26px;
  margin-bottom: 28px;
  display: grid;
  gap: 16px;
}
.cmap-header h2 { margin: 0 0 4px; font-size: 18px; }
.cmap-header p  { margin: 0; color: var(--muted, #94a3b8); font-size: 13px; }
.cmap-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.cmap-legend-item {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .06em;
  padding: 3px 10px;
  border-radius: 999px;
}
.cmap-connector-name {
  margin: 14px 0 8px;
  font-size: 14px;
  color: var(--muted, #94a3b8);
  text-transform: uppercase;
  letter-spacing: .1em;
}
.cmap-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.cmap-tile {
  width: 72px;
  height: 72px;
  border-radius: 8px;
  padding: 5px 4px 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  cursor: default;
  transition: transform 0.1s, box-shadow 0.1s;
  box-sizing: border-box;
  border: 2px solid transparent;
}
.cmap-tile:hover {
  transform: scale(1.12);
  box-shadow: 0 4px 18px rgba(0,0,0,0.45);
  z-index: 10;
  position: relative;
}
.cmap-tile-assigned {
  border-color: rgba(255,255,255,0.75) !important;
}
.cmap-pin-num  { font-size: 11px; font-weight: 800; letter-spacing: .04em; }
.cmap-pin-name { font-size: 9px; font-weight: 600; text-align: center; word-break: break-all; }
.cmap-pin-sym  { font-size: 14px; }

/* ── Section layout ── */
.ecu-section { margin-bottom: 48px; }
.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}
.connector-summary { display: grid; gap: 14px; }
.connector-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}
.connector-card {
  background: var(--panel, #1e293b);
  border: 1px solid var(--border, rgba(255,255,255,0.1));
  border-radius: 12px;
  padding: 16px;
  display: grid;
  gap: 12px;
}
.connector-card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.connector-card-head h3 { margin: 0; font-size: 16px; }
.connector-bar { height: 10px; border-radius: 999px; overflow: hidden; background: rgba(148,163,184,0.18); }
.connector-bar span { display: block; height: 100%; }
.connector-bar span.ok   { background: rgba(22,163,74,0.75); }
.connector-bar span.warn { background: rgba(217,119,6,0.75); }
.connector-bar span.err  { background: rgba(220,38,38,0.75); }
.connector-stats { display: flex; flex-wrap: wrap; gap: 10px 14px; color: var(--muted, #94a3b8); font-size: 13px; }
"""


# ---------------------------------------------------------------------------
# Full page builder
# ---------------------------------------------------------------------------

def build_page(ecu_name: str, ecu: dict, rows: list[dict], section_html: str, sid: str) -> str:
    header_html  = _render_ecu_header(ecu)
    cmap_html    = _render_connector_map(ecu, rows)

    script_js = f"""
(function(){{
  var s  = document.getElementById("searchInput_{sid}");
  var gf = document.getElementById("groupFilter_{sid}");
  var tf = document.getElementById("typeFilter_{sid}");
  var sf = document.getElementById("statusFilter_{sid}");
  var af = document.getElementById("assignedFilter_{sid}");
  var rows = Array.from(document.querySelectorAll("#pinTable_{sid} tbody tr"));
  function apply() {{
    var search = s ? s.value.toLowerCase() : "";
    var grp  = gf ? gf.value : "";
    var typ  = tf ? tf.value : "";
    var stat = sf ? sf.value : "";
    var asgn = af ? af.value : "";
    rows.forEach(function(r) {{
      r.style.display =
        (!search || r.innerText.toLowerCase().includes(search)) &&
        (!grp  || r.dataset.group  === grp)  &&
        (!typ  || r.dataset.type   === typ)  &&
        (!stat || r.dataset.status === stat) &&
        (!asgn || r.dataset.assigned === asgn) ? "" : "none";
    }});
  }}
  [s, gf, tf, sf, af].forEach(function(el) {{ if (el) el.addEventListener("input", apply); }});
}})();
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{P.esc(ecu_name)} - ECU Pinout</title>
  <style>
{_EXTRA_CSS}
{P.OVERFLOW_GUARD_CSS}
  </style>
</head>
<body style="background:var(--bg,#0f172a);color:var(--fg,#e2e8f0);font-family:system-ui,sans-serif;margin:0;padding:0">
  <main style="max-width:1600px;margin:0 auto;padding:32px 24px">
{header_html}
{cmap_html}
{section_html}
  </main>
  <script>
{script_js}
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Generate one ECU → one HTML file
# ---------------------------------------------------------------------------

def generate_for_ecu(ecu_path: Path, templates_parsed: dict, out_dir: Path) -> Path:
    ecu = P.load_json(ecu_path)
    if ecu.get("type") != "ecu":
        raise ValueError(f"{ecu_path.name} is not type='ecu'")

    ecu_name = str(ecu.get("name", ecu_path.stem))
    variant  = P.detect_variant(ecu)
    rows     = L.rows_for_ecu(ecu, templates_parsed)

    if not rows:
        raise ValueError(f"{ecu_name} has no pins")

    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", ecu_name)
    out_path  = out_dir / f"{safe_name}_pinout.html"
    sid = f"ecu0"

    section_html = P.build_section(ecu, ecu_name, variant, rows, 0)
    html = build_page(ecu_name, ecu, rows, section_html, sid)

    out_path.write_text(html, encoding="utf-8")
    key  = L._resolve_template_key(variant, templates_parsed)
    mode = f"template:{key}" if key else "json-only"
    print(f"  [{ecu_name}]  {len(rows)} pins  [{mode}]  -> {out_path.name}")
    return out_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a focused standalone HTML pinout for one or all library ECUs."
    )
    parser.add_argument(
        "--ecu",
        metavar="NAME",
        default=None,
        help="ECU name stem to process (e.g. RC5-6, SRC14-34). "
             "Omit to generate all library ECUs individually.",
    )
    args = parser.parse_args()

    out_dir  = BASE / "exports"
    ecu_dir  = BASE / "library" / "ecus"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[ecu_pinout_single] Loading templates …")
    _, templates_parsed = L.find_templates()
    if templates_parsed:
        print(f"  Templates: {', '.join(sorted(templates_parsed))}")

    # Collect ECU files to process
    if args.ecu:
        # exact filename or stem match
        candidates = list(ecu_dir.glob(f"{args.ecu}.json"))
        if not candidates:
            candidates = [p for p in ecu_dir.glob("*.json")
                          if p.stem.lower() == args.ecu.lower()
                          and not p.name.endswith("_export.json")]
        if not candidates:
            print(f"[ERROR] No library/ecus/{args.ecu}.json found")
            return 1
        ecu_files = candidates
    else:
        ecu_files = sorted(
            p for p in ecu_dir.glob("*.json")
            if not p.name.endswith("_export.json")
        )

    if not ecu_files:
        print(f"[ERROR] No ECU files found in {ecu_dir}")
        return 1

    print(f"\n[ecu_pinout_single] Generating {len(ecu_files)} ECU(s) …")
    generated: list[Path] = []
    for p in ecu_files:
        try:
            out = generate_for_ecu(p, templates_parsed, out_dir)
            generated.append(out)
        except Exception as exc:
            print(f"  [WARN] {p.name}: {exc}")

    if not generated:
        print("[ERROR] Nothing generated")
        return 1

    print(f"\n[OK] {len(generated)} file(s) written:")
    for p in generated:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
