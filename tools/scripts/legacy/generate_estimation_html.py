#!/usr/bin/env python3
"""
E/E Architect Design — Generate Architecture Estimation HTML report.

Reads estimation_result.json and produces a professional HTML report
with IO demand tables, ECU sizing scenarios, and the optimised proposition.

Author: Anadack Temtching Dassi
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from html_overflow_guard import OVERFLOW_GUARD_CSS


def esc(value: Any) -> str:
    return (
        str("" if value is None else value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def find_base() -> Path:
    script_dir = Path(__file__).resolve().parent
    if (script_dir.parent / "exports").exists():
        return script_dir.parent
    return script_dir


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Top-level JSON must be an object")
    return data


# ──── Colour helpers ─────────────────────────────────────────────────────
IFACE_COLORS: dict[str, str] = {
    "DIGITAL":  "#5aa6ff",
    "ANALOG":   "#2ee6a0",
    "PWM":      "#ffb43d",
    "CAN":      "#ff5a78",
    "LIN":      "#ff9e6e",
    "SENT":     "#2ee6ff",
    "ETHERNET": "#19d6c0",
    "POWER":    "#6c83a2",
    "GROUND":   "#46566e",
}

VARIANT_COLORS: dict[str, str] = {
    "SMALL":  "#2ee6a0",
    "MEDIUM": "#5aa6ff",
    "LARGE":  "#ffb43d",
}


def iface_color(name: str) -> str:
    return IFACE_COLORS.get(name, "#6c83a2")


def variant_color(name: str) -> str:
    return VARIANT_COLORS.get(name, "#6c83a2")


def util_color(pct: float) -> str:
    if pct <= 50:
        return "#2ee6a0"
    if pct <= 70:
        return "#5aa6ff"
    if pct <= 85:
        return "#ffb43d"
    return "#ff5a78"


# ──── HTML sections ──────────────────────────────────────────────────────

def render_css() -> str:
    return """\
    :root {
      --bg: #070b12;
      --surface0: #0b1018;
      --surface1: #0f1622;
      --surface2: #151e2e;
      --surface3: #1d2939;
      --surface4: #273548;
      --border0: #1a2436;
      --border1: #233149;
      --border2: #2d3e5c;
      --text: #cfdaea;
      --text-dim: #6c83a2;
      --text-fade: #46566e;
      --cyan: #2ee6ff;
      --green: #2ee6a0;
      --amber: #ffb43d;
      --red: #ff5a78;
      --purple: #b388ff;
      --teal: #19d6c0;
      --blue: #5aa6ff;
      --ink: var(--text);
      --muted: var(--text-dim);
      --card: var(--surface2);
      --line: var(--border1);
      --accent: var(--cyan);
      --ok: var(--green);
      --warn: var(--amber);
      --err: var(--red);
      --shadow: 0 8px 30px rgba(0,0,0,.45);
    }
    *, *::before, *::after { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      color: var(--text);
      background: var(--bg);
      min-height: 100vh;
    }
    a { color: var(--cyan); text-decoration: none; }
    a:hover { color: var(--green); }
    .page { max-width: 1440px; margin: 0 auto; padding: 28px; display: grid; gap: 28px; }

    /* Hero */
    .hero {
      display: grid; gap: 8px; padding: 28px;
      background: linear-gradient(135deg, var(--surface1), var(--surface2));
      border: 1px solid var(--border2); border-radius: 20px; box-shadow: var(--shadow);
    }
    .kicker { text-transform: uppercase; letter-spacing: .12em; color: var(--cyan); font-weight: 800; font-size: .78rem; }
    .hero h1 { margin: 0; font-size: clamp(2rem, 3vw, 3.2rem); line-height: 1.1; letter-spacing: -0.04em; color: var(--text); }
    .hero p  { margin: 0; color: var(--text-dim); max-width: 72ch; font-size: 1.02rem; }
    .stamp { font-size: .85rem; color: var(--text-fade); }

    /* Summary cards */
    .summary-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }
    .summary-card {
      background: var(--surface2);
      border: 1px solid var(--border2);
      border-radius: 16px;
      padding: 18px;
      text-align: center;
      box-shadow: 0 4px 16px rgba(0,0,0,.3);
    }
    .summary-card .label { font-size: .85rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: .04em; }
    .summary-card .value { font-size: 2rem; font-weight: 700; margin-top: 8px; color: var(--cyan); }
    .summary-card .sub   { font-size: .82rem; color: var(--text-fade); margin-top: 4px; }

    /* Section */
    .section {
      display: grid; gap: 16px;
      background: var(--surface1); border: 1px solid var(--border1);
      border-radius: 18px; padding: 20px; box-shadow: 0 6px 24px rgba(0,0,0,.25);
    }
    .section h2 { margin: 0; font-size: 1.5rem; border-bottom: 1px solid var(--border2); padding-bottom: 6px; color: var(--text); }
    .section p { color: var(--text-dim); }

    /* Tables */
    table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: .92rem; background: var(--surface2); border: 1px solid var(--border1); border-radius: 12px; overflow: hidden; }
    th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border0); color: var(--text); }
    th { background: var(--surface3); font-weight: 600; font-size: .82rem; text-transform: uppercase; letter-spacing: .03em; color: var(--text-dim); }
    tr:last-child td { border-bottom: none; }
    tbody tr:hover { background: var(--surface3); }
    td.num { text-align: right; font-variant-numeric: tabular-nums; }
    tr.missing { background: rgba(255,90,120,.08); color: var(--red); }
    tr.total-row { font-weight: 700; background: var(--surface3); }

    /* IO bar */
    .io-bar { display: flex; gap: 2px; height: 20px; border-radius: 6px; overflow: hidden; min-width: 120px; background: var(--surface3); }
    .io-bar span { display: block; height: 100%; }

    /* ECU scenario cards */
    .scenario-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
    .scenario-card {
      background: var(--surface2);
      border: 1px solid var(--border2);
      border-radius: 16px;
      padding: 20px;
      text-align: center;
    }
    .scenario-card .variant { font-size: 1.1rem; font-weight: 700; text-transform: uppercase; }
    .scenario-card .count { font-size: 2.4rem; font-weight: 800; margin: 8px 0; }
    .scenario-card .details { font-size: .85rem; color: var(--text-dim); }

    /* Utilisation bar */
    .util-bar-bg { width: 100%; height: 18px; background: var(--surface3); border-radius: 9px; overflow: hidden; margin-top: 8px; }
    .util-bar-fg { height: 100%; border-radius: 9px; transition: width .3s; }

    /* Proposition ECU cards */
    .prop-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
    .prop-card {
      background: var(--surface2);
      border: 1px solid var(--border1);
      border-radius: 16px;
      padding: 20px;
      position: relative;
      overflow: hidden;
    }
    .prop-card .ecu-label { font-weight: 700; font-size: 1.1rem; }
    .prop-card .systems   { margin: 8px 0; color: var(--text-dim); font-size: .9rem; }
    .prop-card .pins      { font-size: .88rem; color: var(--text-dim); }

    /* Rules box */
    .rules-box {
      background: rgba(255,180,61,.06);
      border: 1px solid rgba(255,180,61,.35);
      border-radius: 12px;
      padding: 18px 22px;
      font-size: .92rem;
      line-height: 1.7;
      color: var(--text);
    }
    .rules-box strong { color: var(--amber); }

    /* Errors box */
    .error-box {
      background: rgba(255,90,120,.06);
      border: 1px solid rgba(255,90,120,.35);
      border-radius: 12px;
      padding: 18px 22px;
      font-size: .92rem;
    }
    .error-box h3 { margin: 0 0 8px; color: var(--red); }
    .error-box ul { margin: 4px 0 0 18px; padding: 0; color: var(--text-dim); }
    .error-box li { margin: 4px 0; }

    /* Footer */
    .footer { text-align: center; font-size: .82rem; color: var(--text-fade); padding: 20px 0 10px; border-top: 1px solid var(--border1); }

    @media print {
      body { background: #fff; color: #000; }
      .page { padding: 0; }
    }"""


def render_hero(data: dict[str, Any]) -> str:
    platform = esc(data.get("platform", "Unknown"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""\
<div class="hero">
  <div class="kicker">E/E Architect Design</div>
  <h1>Architecture Estimation</h1>
  <p>Platform: <strong>{platform}</strong></p>
  <div class="stamp">Generated {now} from framework JSON exports</div>
</div>"""


def render_summary_cards(data: dict[str, Any]) -> str:
    arch_io = data.get("architecture_io", {})
    total_sig = arch_io.get("total_signals", 0)
    found = arch_io.get("systems_found", 0)
    missing = arch_io.get("systems_missing", 0)
    total_sys = found + missing

    prop = data.get("proposition", {})
    best_count = prop.get("ecu_count", 0)

    # Build homogeneous label dynamically from estimates array
    estimates = data.get("estimates", [])
    homo_parts = []
    for e in estimates:
        v = e.get("variant", "?")
        n = e.get("ecu_count", "?")
        c = variant_color(v)
        homo_parts.append(f'<span style="color:{c}">{n}{v[0]}</span>')
    homo_html = " / ".join(homo_parts) if homo_parts else "?"
    homo_sub_parts = [f"all-{e.get('variant','?')}" for e in estimates]
    homo_sub = " / ".join(homo_sub_parts) if homo_sub_parts else ""

    cards = f"""\
<div class="summary-row">
  <div class="summary-card">
    <div class="label">Systems</div>
    <div class="value">{total_sys}</div>
    <div class="sub">{found} found &middot; {missing} missing</div>
  </div>
  <div class="summary-card">
    <div class="label">Total Signals</div>
    <div class="value">{total_sig}</div>
    <div class="sub">across all resolved systems</div>
  </div>
  <div class="summary-card">
    <div class="label">Best Proposition</div>
    <div class="value" style="color:{variant_color('MEDIUM')}">{best_count} ECU(s)</div>
    <div class="sub">optimised mix</div>
  </div>
  <div class="summary-card">
    <div class="label">Homogeneous</div>
    <div class="value" style="font-size:1.2rem">{homo_html}</div>
    <div class="sub">{homo_sub}</div>
  </div>
</div>"""
    return cards


def _io_bar(io_list: list[dict[str, Any]], max_total: int) -> str:
    if max_total <= 0:
        return '<div class="io-bar"></div>'
    parts = []
    for io in io_list:
        iface = io.get("interface", "?")
        total = io.get("total", 0)
        w = total / max_total * 100
        if w < 0.5:
            continue
        parts.append(
            f'<span title="{esc(iface)}: {total}" '
            f'style="width:{w:.1f}%;background:{iface_color(iface)}"></span>'
        )
    return f'<div class="io-bar">{"".join(parts)}</div>'


def render_system_io_table(data: dict[str, Any]) -> str:
    systems = data.get("systems", [])
    if not systems:
        return ""

    # Collect all interface types
    ifaces_set: list[str] = []
    for s in systems:
        for io in s.get("io", []):
            name = io.get("interface", "?")
            if name not in ifaces_set:
                ifaces_set.append(name)

    # Max total for bar scaling
    max_total = max((s.get("total_signals", 0) for s in systems), default=1) or 1

    header_cols = "".join(f"<th>{esc(i)}</th>" for i in ifaces_set)
    rows = []
    for s in systems:
        found = s.get("found", False)
        ref = esc(s.get("ref_2x", ""))
        name = esc(s.get("name", ""))
        total = s.get("total_signals", 0)
        io_list = s.get("io", [])
        io_map = {io["interface"]: io for io in io_list}

        cls = ' class="missing"' if not found else ""
        status = "&#10003;" if found else "&#10007;"
        status_color = "var(--ok)" if found else "var(--err)"

        cols = []
        for iface in ifaces_set:
            val = io_map.get(iface, {}).get("total", 0)
            cols.append(f'<td class="num">{val if val else "&mdash;"}</td>')

        bar = _io_bar(io_list, max_total)
        rows.append(
            f'<tr{cls}>'
            f'<td><span style="color:{status_color}">{status}</span></td>'
            f'<td><strong>{ref}</strong></td>'
            f'<td>{name}</td>'
            f'{"".join(cols)}'
            f'<td class="num"><strong>{total}</strong></td>'
            f'<td>{bar}</td>'
            f'</tr>'
        )

    # Architecture total row
    arch_io = data.get("architecture_io", {})
    arch_per = arch_io.get("per_interface", [])
    arch_map = {io["interface"]: io for io in arch_per}
    arch_total = arch_io.get("total_signals", 0)
    total_cols = []
    for iface in ifaces_set:
        val = arch_map.get(iface, {}).get("total", 0)
        total_cols.append(f'<td class="num">{val if val else "&mdash;"}</td>')
    rows.append(
        f'<tr class="total-row">'
        f'<td></td>'
        f'<td colspan="2"><strong>ARCHITECTURE TOTAL</strong></td>'
        f'{"".join(total_cols)}'
        f'<td class="num"><strong>{arch_total}</strong></td>'
        f'<td>{_io_bar(arch_per, max_total)}</td>'
        f'</tr>'
    )

    return f"""\
<div class="section">
  <h2>IO Demand per System</h2>
  <div style="overflow-x:auto">
  <table>
    <thead>
      <tr><th></th><th>Ref-2X</th><th>System</th>{header_cols}<th>Total</th><th>Distribution</th></tr>
    </thead>
    <tbody>
      {"".join(rows)}
    </tbody>
  </table>
  </div>
</div>"""


def render_io_breakdown(data: dict[str, Any]) -> str:
    arch_io = data.get("architecture_io", {})
    per = arch_io.get("per_interface", [])
    if not per:
        return ""

    total = arch_io.get("total_signals", 1) or 1
    rows = []
    for io in per:
        iface = io.get("interface", "?")
        inp = io.get("input", 0)
        outp = io.get("output", 0)
        inout = io.get("inout", 0)
        t = io.get("total", 0)
        pct = t / total * 100
        color = iface_color(iface)
        rows.append(
            f'<tr>'
            f'<td><span style="display:inline-block;width:12px;height:12px;'
            f'border-radius:3px;background:{color};vertical-align:middle"></span> '
            f'{esc(iface)}</td>'
            f'<td class="num">{inp}</td>'
            f'<td class="num">{outp}</td>'
            f'<td class="num">{inout}</td>'
            f'<td class="num"><strong>{t}</strong></td>'
            f'<td class="num">{pct:.1f}%</td>'
            f'</tr>'
        )

    return f"""\
<div class="section">
  <h2>Architecture IO Breakdown</h2>
  <table>
    <thead><tr><th>Interface</th><th>Input</th><th>Output</th><th>InOut</th><th>Total</th><th>Share</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</div>"""


def render_ecu_capacities(data: dict[str, Any]) -> str:
    caps = data.get("ecu_capacities", [])
    if not caps:
        return ""

    # Collect all interface keys
    ifaces: list[str] = []
    for c in caps:
        for k in c.get("per_interface", {}):
            if k not in ifaces:
                ifaces.append(k)

    header = "".join(f"<th>{esc(i)}</th>" for i in ifaces)
    rows = []
    for c in caps:
        v = esc(c.get("variant", "?"))
        total = c.get("total_pins", 0)
        cols = []
        pi = c.get("per_interface", {})
        for iface in ifaces:
            val = pi.get(iface, 0)
            cols.append(f'<td class="num">{val if val else "&mdash;"}</td>')
        color = variant_color(v)
        rows.append(
            f'<tr>'
            f'<td><strong style="color:{color}">AEC {v}</strong></td>'
            f'{"".join(cols)}'
            f'<td class="num"><strong>{total}</strong></td>'
            f'</tr>'
        )

    return f"""\
<div class="section">
  <h2>ECU Pin Capacities (Reference)</h2>
  <table>
    <thead><tr><th>Variant</th>{header}<th>Total Pins</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</div>"""


def render_homogeneous_estimates(data: dict[str, Any]) -> str:
    estimates = data.get("estimates", [])
    if not estimates:
        return ""

    cards = []
    for e in estimates:
        variant = e.get("variant", "?")
        count = e.get("ecu_count", 0)
        pins_avail = e.get("pins_available", 0)
        pins_used = e.get("pins_used", 0)
        util = e.get("utilisation_pct", 0.0)
        color = variant_color(variant)
        uc = util_color(util)
        cards.append(f"""\
<div class="scenario-card">
  <div class="variant" style="color:{color}">All AEC {esc(variant)}</div>
  <div class="count" style="color:{color}">{count}</div>
  <div class="details">ECU(s) required</div>
  <div class="details">{pins_used} / {pins_avail} pins &middot; {util:.1f}% utilisation</div>
  <div class="util-bar-bg"><div class="util-bar-fg" style="width:{min(util,100):.1f}%;background:{uc}"></div></div>
</div>""")

    return f"""\
<div class="section">
  <h2>Homogeneous ECU Scenarios</h2>
  <p style="color:var(--muted);margin:0">How many ECUs are needed if using only one variant type?</p>
  <div class="scenario-grid">
    {"".join(cards)}
  </div>
</div>"""


def render_proposition(data: dict[str, Any]) -> str:
    prop = data.get("proposition", {})
    ecus = prop.get("ecus", [])
    notes = prop.get("notes", "")
    total_count = prop.get("ecu_count", 0)

    if not ecus:
        return ""

    cards = []
    for idx, ecu in enumerate(ecus):
        variant = ecu.get("variant", "?")
        systems = esc(ecu.get("systems", ""))
        pins_used = ecu.get("pins_used", 0)
        pins_total = ecu.get("pins_total", 0)
        util = ecu.get("utilisation_pct", 0.0)
        color = variant_color(variant)
        uc = util_color(util)
        cards.append(f"""\
<div class="prop-card" style="border-left:6px solid {color}">
  <div class="ecu-label" style="color:{color}">ECU #{idx+1} &mdash; AEC {esc(variant)}</div>
  <div class="systems">Systems: {systems}</div>
  <div class="pins">{pins_used} / {pins_total} pins used &middot; <strong style="color:{uc}">{util:.1f}%</strong> utilisation</div>
  <div class="util-bar-bg"><div class="util-bar-fg" style="width:{min(util,100):.1f}%;background:{uc}"></div></div>
</div>""")

    # Design rules from structured JSON (generic — no hardcoded rules)
    rules_html = ""
    rules = data.get("design_rules", [])
    thresholds = data.get("thresholds", {})
    if rules:
        items = "".join(
            f'<li><strong>{esc(r.get("id", ""))}</strong> — '
            f'<em>{esc(r.get("title", ""))}</em>: {esc(r.get("description", ""))}</li>'
            for r in rules
        )
        thresh_html = ""
        if thresholds:
            thresh_items = []
            for k, v in thresholds.items():
                label = k.replace("_", " ").title()
                thresh_items.append(f"<li>{esc(label)}: <strong>{v}</strong></li>")
            thresh_html = (
                '<div style="margin-top:12px"><strong>Design Thresholds:</strong>'
                f'<ul style="margin:4px 0 0 18px;padding:0">{"".join(thresh_items)}</ul></div>'
            )
        rules_html = f"""\
<div class="rules-box">
  <strong>Design Rules Applied:</strong>
  <ul style="margin:8px 0 0 18px;padding:0">{items}</ul>
  {thresh_html}
</div>"""

    return f"""\
<div class="section">
  <h2>Optimised Mixed Proposition — {total_count} ECU(s)</h2>
  <div class="prop-grid">
    {"".join(cards)}
  </div>
  {rules_html}
</div>"""


def render_errors(data: dict[str, Any]) -> str:
    systems = data.get("systems", [])
    missing = [s for s in systems if not s.get("found", False)]
    if not missing:
        return ""

    items = "".join(
        f'<li><strong>{esc(s.get("ref_2x", "?"))}</strong> — not found in library</li>'
        for s in missing
    )
    return f"""\
<div class="error-box">
  <h3>&#9888; Missing Systems ({len(missing)})</h3>
  <p>The following system Ref-2X identifiers could not be resolved in the component library.
     IO demand may be underestimated.</p>
  <ul>{items}</ul>
</div>"""


def render_footer() -> str:
    return """\
<div class="footer">
  E/E Architect Design &mdash; Architecture Estimation Report &mdash; Anadack Temtching Dassi
</div>"""


# ──── Main ───────────────────────────────────────────────────────────────

def generate(input_json: Path, output_html: Path) -> None:
    try:
        data = load_json(input_json)
    except (OSError, ValueError) as exc:
        print(f"[ERROR] Failed to load estimation JSON: {exc}")
        sys.exit(1)

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>E/E Architect Design — Architecture Estimation — {esc(data.get("platform", ""))}</title>
<style>
{render_css()}
{OVERFLOW_GUARD_CSS}
</style>
</head>
<body>
<div class="page">
{render_hero(data)}
{render_summary_cards(data)}
{render_errors(data)}
{render_system_io_table(data)}
{render_io_breakdown(data)}
{render_ecu_capacities(data)}
{render_homogeneous_estimates(data)}
{render_proposition(data)}
{render_footer()}
</div>
</body>
</html>"""

    output_html.write_text(html, encoding="utf-8")
    print(f"[OK] Estimation HTML written to {output_html}")


def main() -> None:
    base = find_base()

    # Default paths
    input_path = base / "exports" / "estimation_result.json"
    output_path = base / "exports" / "architecture_estimation.html"

    # Allow overrides via CLI args
    args = sys.argv[1:]
    if "--input" in args:
        idx = args.index("--input")
        if idx + 1 < len(args):
            input_path = Path(args[idx + 1])
    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 < len(args):
            output_path = Path(args[idx + 1])

    if not input_path.exists():
        print(f"[ERROR] Estimation JSON not found: {input_path}")
        print("  Run app.exe first to generate exports/estimation_result.json")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    generate(input_path, output_path)


if __name__ == "__main__":
    main()
