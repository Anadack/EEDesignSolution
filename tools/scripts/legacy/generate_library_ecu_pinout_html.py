#!/usr/bin/env python3
"""Generate one combined HTML pinout for every ECU defined in library/ecus/*.json.

AGCO variants (SMALL / MEDIUM / LARGE) use the pre-built HTML templates from
templates/ when a matching file is found.  Third-party ECUs (e.g. SRC14-34,
SRC14-34/31) are rendered directly from their JSON pin data without a separate
HTML template — electrical_capability and diagnostic_flags bitmasks are decoded
into human-readable labels automatically.

Output:  exports/library_ecu_pinouts.html
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Import rendering helpers from the existing architecture pinout tool so we
# don't duplicate the CSS / HTML render logic.
# ---------------------------------------------------------------------------
_tools = Path(__file__).resolve().parent
sys.path.insert(0, str(_tools))
import generate_architecture_html_pinout as P  # noqa: E402

BASE = _tools.parent

# ---------------------------------------------------------------------------
# Electrical capability bitmask → human-readable labels
# (matches EEC_ElectricalFlag_t in EEC_types.h)
# ---------------------------------------------------------------------------
_ELEC_CAP_LABELS: list[tuple[int, str]] = [
    (1,   "Pull-Up"),
    (2,   "Pull-Down"),
    (4,   "High-Side"),
    (8,   "Low-Side"),
    (16,  "Push-Pull"),
    (32,  "Current Sense"),
    (64,  "Voltage In"),
    (128, "Differential"),
]


def elec_lines_from_cap(cap: int) -> list[str]:
    """Decode an electrical_capability bitmask into label strings."""
    return [label for bit, label in _ELEC_CAP_LABELS if cap & bit]


# ---------------------------------------------------------------------------
# Pin normalization (library JSON → render-ready row dict)
# ---------------------------------------------------------------------------

def normalize_library_pin(pin: dict) -> dict:
    """Normalize one library pin.
    Calls the architecture tool's normalize_json_pin(), then enriches the
    electrical_lines column from the electrical_capability bitmask when the
    source JSON has no 'electrical' text string.
    """
    row = P.normalize_json_pin(pin)
    # enrich electrical_lines from capability bitmask when absent
    if not row["electrical_lines"]:
        cap = int(pin.get("electrical_capability", 0) or 0)
        labels = elec_lines_from_cap(cap)
        if labels:
            row["electrical_lines"] = labels
    return row


# ---------------------------------------------------------------------------
# Template discovery
# ---------------------------------------------------------------------------

def find_templates() -> tuple[dict[str, str], dict[str, dict]]:
    """Discover *_<VARIANT>_full_pinout.html templates in templates/.
    Returns (raw_html_by_variant, parsed_rows_by_variant).
    """
    raw: dict[str, str] = {}
    parsed: dict[str, dict] = {}
    tdir = BASE / "templates"
    if not tdir.exists():
        return raw, parsed
    for tpl in sorted(tdir.glob("*_full_pinout.html")):
        parts = tpl.stem.split("_")
        try:
            fi = parts.index("full")
            key = parts[fi - 1].upper() if fi >= 1 else None
        except ValueError:
            continue
        if not key:
            continue
        html = tpl.read_text(encoding="utf-8")
        raw[key] = html
        parsed[key] = P.parse_template_rows(html)
    return raw, parsed


# ---------------------------------------------------------------------------
# Build pin rows for one ECU
# ---------------------------------------------------------------------------

def _resolve_template_key(variant: str, templates_parsed: dict[str, dict]) -> str | None:
    """Return the template key for this variant, or None if not found."""
    if variant in templates_parsed:
        return variant
    for tok in reversed(variant.replace("-", "_").split("_")):
        if tok and tok in templates_parsed:
            return tok
    return None


def rows_for_ecu(ecu: dict, templates_parsed: dict[str, dict]) -> list[dict]:
    """Return sorted, render-ready pin rows for one ECU.

    If a matching HTML template exists the rows are template-merged (AGCO path).
    Otherwise every pin from the JSON 'pins' array is normalized directly.
    In both cases electrical_lines is enriched from the electrical_capability
    bitmask when no textual 'electrical' value was provided.
    """
    variant = str(ecu.get("variant", "")).strip().upper()
    key = _resolve_template_key(variant, templates_parsed)

    if key:
        # Template path: overlay library JSON pin data on the pre-built template
        rows = P.merge_template_with_json(templates_parsed[key], ecu)
        # Build a quick lookup so we can add capability labels to template rows
        pin_by_key: dict[tuple[str, str], dict] = {
            (str(p.get("connector", "")), str(p.get("physical_number", ""))): p
            for p in ecu.get("pins", [])
            if isinstance(p, dict)
        }
        for row in rows:
            if not row["electrical_lines"]:
                pin = pin_by_key.get((row["connector"], row["pin"]))
                if pin:
                    cap = int(pin.get("electrical_capability", 0) or 0)
                    row["electrical_lines"] = elec_lines_from_cap(cap)
        return rows

    # JSON-only path: normalize each pin from the library JSON directly
    rows = []
    for pin in ecu.get("pins", []):
        if isinstance(pin, dict):
            rows.append(normalize_library_pin(pin))
    rows.sort(
        key=lambda r: (r["connector"], int(r["pin"]) if str(r["pin"]).isdigit() else 999999)
    )
    return rows


# ---------------------------------------------------------------------------
# Page-level HTML builder (extends architecture tool's per-ECU sections)
# ---------------------------------------------------------------------------

def _extract_css(base_template: str) -> str:
    m = re.search(r"<style>(.*?)</style>", base_template, re.S)
    return m.group(1) if m else ""


def build_page(
    title: str,
    sections: list[str],
    section_meta: list[dict],
    base_template: str,
) -> str:
    """Assemble the final HTML page with a sticky ECU navigation bar."""
    styles = _extract_css(base_template)
    styles += P.OVERFLOW_GUARD_CSS
    styles += """
/* ── ECU section layout ── */
.ecu-section { margin-bottom: 48px; }
.ecu-section:not(:first-of-type) {
  border-top: 2px solid rgba(255,255,255,0.08);
  padding-top: 28px;
}
.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}
/* Connector hotspot cards */
.connector-summary { display: grid; gap: 14px; }
.connector-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}
.connector-card {
  background: var(--surface1, #0f1622);
  border: 1px solid var(--border1, #233149);
  border-radius: 12px;
  padding: 16px;
  display: grid;
  gap: 12px;
}
.connector-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.connector-card-head h3 { margin: 0; font-size: 16px; }
.connector-bar {
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(148,163,184,0.18);
}
.connector-bar span { display: block; height: 100%; }
.connector-bar span.ok  { background: rgba(22,163,74,0.75); }
.connector-bar span.warn{ background: rgba(217,119,6,0.75); }
.connector-bar span.err { background: rgba(220,38,38,0.75); }
.connector-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  color: var(--muted);
  font-size: 13px;
}
.connector-empty { padding: 12px 0; }
/* ── Sticky ECU navigation bar ── */
.page-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--bg, #070b12);
  border-bottom: 1px solid var(--border, #233149);
  padding: 10px 24px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  box-shadow: 0 2px 12px rgba(0,0,0,0.35);
}
.page-nav .nav-label {
  color: var(--muted, #6c83a2);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  margin-right: 6px;
}
.page-nav a {
  color: var(--accent, #2ee6ff);
  text-decoration: none;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid rgba(46,230,255,0.25);
  transition: background 0.15s;
  white-space: nowrap;
}
.page-nav a:hover { background: rgba(46,230,255,0.12); }
.page-nav .pin-count { opacity: 0.55; font-size: 11px; margin-left: 3px; }
"""

    nav_links = "\n    ".join(
        f'<a href="#{m["id"]}">{P.esc(m["name"])}'
        f'<span class="pin-count">·{m["pins"]}p</span></a>'
        for m in section_meta
    )

    scripts_js = []
    for m in section_meta:
        sid = m["id"]
        scripts_js.append(f"""
(function(){{
  var s  = document.getElementById("searchInput_{sid}");
  var gf = document.getElementById("groupFilter_{sid}");
  var tf = document.getElementById("typeFilter_{sid}");
  var sf = document.getElementById("statusFilter_{sid}");
  var af = document.getElementById("assignedFilter_{sid}");
  var rows = Array.from(document.querySelectorAll("#pinTable_{sid} tbody tr"));
  function apply() {{
    var search = s ? s.value.toLowerCase() : "";
    var grp    = gf ? gf.value : "";
    var typ    = tf ? tf.value : "";
    var stat   = sf ? sf.value : "";
    var asgn   = af ? af.value : "";
    rows.forEach(function(r) {{
      r.style.display =
        (!search || r.innerText.toLowerCase().includes(search)) &&
        (!grp  || r.dataset.group  === grp)  &&
        (!typ  || r.dataset.type   === typ)  &&
        (!stat || r.dataset.status === stat) &&
        (!asgn || r.dataset.assigned === asgn)
        ? "" : "none";
    }});
  }}
  [s, gf, tf, sf, af].forEach(function(el) {{
    if (el) el.addEventListener("input", apply);
  }});
}})();
""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{P.esc(title)}</title>
  <style>
{styles}
  </style>
</head>
<body>
  <nav class="page-nav">
    <span class="nav-label">ECU Library</span>
    {nav_links}
  </nav>
  <header style="padding:24px 32px 12px">
    <h1>{P.esc(title)}</h1>
    <p style="color:var(--muted,#6c83a2)">
      Pinout for every ECU defined in <code>library/ecus/</code>.
      AGCO ECUs use hardware templates; third-party ECUs (e.g.&nbsp;SRC14-34)
      are rendered from their JSON pin data with bitmask-decoded electrical specs.
    </p>
  </header>
  <main class="container">
{"".join(sections)}
  </main>
  <script>
{"".join(scripts_js)}
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    output = BASE / "exports" / "library_ecu_pinouts.html"
    ecu_dir = BASE / "library" / "ecus"

    print("[library_ecu_pinout] Discovering templates …")
    templates_raw, templates_parsed = find_templates()
    if templates_parsed:
        print(f"  Found templates: {', '.join(sorted(templates_parsed))}")
    else:
        print("  No templates found — all ECUs will render in JSON-only mode")

    ecu_files = sorted(
        p for p in ecu_dir.glob("*.json")
        if not p.name.endswith("_export.json")
    )
    if not ecu_files:
        print(f"[ERROR] No ECU JSON files found in {ecu_dir}")
        return 1

    print(f"\n[library_ecu_pinout] Processing {len(ecu_files)} ECU file(s) …")
    sections: list[str] = []
    section_meta: list[dict] = []

    for idx, ecu_path in enumerate(ecu_files):
        try:
            ecu = P.load_json(ecu_path)
        except Exception as exc:
            print(f"  [WARN] Skipping {ecu_path.name}: {exc}")
            continue

        if ecu.get("type") != "ecu":
            print(f"  [SKIP] {ecu_path.name} — not type='ecu'")
            continue

        ecu_name = str(ecu.get("name", ecu_path.stem))
        variant  = P.detect_variant(ecu)
        rows     = rows_for_ecu(ecu, templates_parsed)

        if not rows:
            print(f"  [WARN] {ecu_name} — no pins, skipped")
            continue

        key = _resolve_template_key(variant, templates_parsed)
        mode = f"template:{key}" if key else "json-only"
        print(f"  [{idx + 1}] {ecu_name:<32} variant={variant:<14} {len(rows):4d} pins  [{mode}]")

        sections.append(P.build_section(ecu, ecu_name, variant, rows, idx))
        section_meta.append({"id": f"ecu{idx}", "name": ecu_name, "pins": len(rows)})

    if not sections:
        print("[ERROR] No ECU sections generated")
        return 1

    base_tpl = next(iter(templates_raw.values())) if templates_raw else "<style></style>"
    html = build_page("Library ECU Pinouts", sections, section_meta, base_tpl)
    output.write_text(html, encoding="utf-8")

    print(f"\n[OK] {output}  ({len(sections)} ECU(s), "
          f"{sum(m['pins'] for m in section_meta)} total pins)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
