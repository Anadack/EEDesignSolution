#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DIAG_LABELS = [
    (1, "Open Load"),
    (2, "Short GND"),
    (4, "Short BAT"),
    (8, "Range Check"),
    (16, "Overcurrent"),
    (32, "Thermal Warn"),
    (64, "Line Break"),
    (128, "Plausibility"),
]

ELEC_CAP_LABELS = [
    (1, "Pull-Up"),
    (2, "Pull-Down"),
    (4, "High-Side"),
    (8, "Low-Side"),
    (16, "Push-Pull"),
    (32, "Current Sense"),
    (64, "Voltage In"),
    (128, "Differential"),
]

OVERFLOW_GUARD_CSS = """
/* Long-name guards: keep ECU, signal, connector and device names inside their boxes. */
:where(h1, h2, h3, p, a, span, strong, div, td, th, input, select) {
    overflow-wrap: anywhere;
    word-break: normal;
}
:where(.card, .summary-card, .connector-card, .ecu-section, .table-wrap, .toolbar,
             .device-card, .ecu-card, .cmap-section, .ecu-header-card) {
    min-width: 0;
    max-width: 100%;
}
.table-wrap {
    max-width: 100%;
    overflow-x: auto;
}
table {
    table-layout: auto;
}
thead th,
tbody td {
    white-space: normal;
    max-width: 24rem;
}
.badge {
    white-space: normal;
    max-width: 100%;
    line-height: 1.35;
    vertical-align: top;
}
.toolbar {
    grid-template-columns: minmax(0, 2fr) repeat(4, minmax(0, 1fr));
}
.toolbar input,
.toolbar select {
    min-width: 0;
}
.connector-card-head,
.ecu-header-title,
.ecu-meta-item {
    min-width: 0;
}
@media (max-width: 900px) {
    .toolbar {
        grid-template-columns: 1fr;
    }
}
"""


def esc(value: Any) -> str:
    return (
        str("" if value is None else value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Top-level JSON must be an object")
    return data


def load_html(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_arch_and_ecus(data: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    arch = data.get("architecture", data)
    name = str(arch.get("name", "Architecture"))
    ecus = arch.get("ecus", [])
    if not isinstance(ecus, list):
        raise ValueError("architecture.ecus must be a list")
    return name, [x for x in ecus if isinstance(x, dict)]


def detect_variant(ecu: dict[str, Any]) -> str:
    """Return the variant string from the ECU data, uppercased."""
    variant = str(ecu.get("variant", "")).strip().upper()
    if variant:
        return variant
    # Fallback: try to infer from the name
    name = str(ecu.get("name", "")).upper()
    # Check for common variant words in the name
    for token in name.replace("_", " ").replace("-", " ").split():
        if token and len(token) >= 3:
            return token
    return "UNKNOWN"


def split_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in re.split(r"[;,|]", str(value)) if x.strip()]


def electrical_lines_from_capability(capability: int) -> list[str]:
    return [label for bit, label in ELEC_CAP_LABELS if capability & bit]


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .strip()
    )


def extract_badges(cell_html: str) -> list[str]:
    badges = re.findall(r'<span class="badge[^"]*">(.*?)</span>', cell_html, re.S)
    return [strip_html(x) for x in badges if strip_html(x)]


def extract_badge_or_text(cell_html: str) -> str:
    badges = extract_badges(cell_html)
    if badges:
        return badges[0]
    return strip_html(cell_html)


def extract_small_text(cell_html: str) -> str:
    m = re.search(r'<div class="small">(.*?)</div>', cell_html, re.S)
    return strip_html(m.group(1)) if m else ""


def extract_strong_or_text(cell_html: str, fallback: str = "") -> str:
    m = re.search(r"<strong>(.*?)</strong>", cell_html, re.S)
    if m:
        value = strip_html(m.group(1))
        return value or fallback
    value = strip_html(cell_html)
    return value or fallback


def extract_details_lines(cell_html: str) -> list[str]:
    blocks = re.findall(r"<div(?: class=\"small\")?>(.*?)</div>", cell_html, re.S)
    out = [strip_html(x) for x in blocks if strip_html(x)]
    if out:
        return out
    text = strip_html(cell_html)
    return [text] if text else []


def parse_template_rows(template_html: str) -> dict[tuple[str, str], dict[str, Any]]:
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", template_html, re.S)
    if not tbody_match:
        raise RuntimeError("Could not find <tbody> in template")
    tbody = tbody_match.group(1)

    row_pattern = re.compile(
        r'<tr[^>]*data-group="(?P<group>[^"]*)"[^>]*data-type="(?P<type>[^"]*)"[^>]*'
        r'data-status="(?P<status>[^"]*)"[^>]*data-assigned="(?P<assigned>[^"]*)"[^>]*>'
        r'(?P<body>.*?)</tr>',
        re.S,
    )
    cell_pattern = re.compile(r"<td>(.*?)</td>", re.S)

    rows = {}
    for row_match in row_pattern.finditer(tbody):
        cells = cell_pattern.findall(row_match.group("body"))
        if len(cells) != 13:
            continue
        connector = strip_html(cells[0]).strip()
        pin = strip_html(cells[1]).strip()
        rows[(connector, pin)] = {
            "connector": connector,
            "pin": pin,
            "pin_name": extract_strong_or_text(cells[2]),
            "group": extract_badge_or_text(cells[3]),
            "alt_groups": extract_badges(cells[4]),
            "type": extract_badge_or_text(cells[5]),
            "direction": extract_badge_or_text(cells[6]),
            "electrical_lines": extract_details_lines(cells[7]),
            "diagnostics": extract_badges(cells[8]),
            "sw_config": extract_badges(cells[9]),
            "signal_title": extract_strong_or_text(cells[10], fallback="—"),
            "signal_sub": extract_small_text(cells[10]),
            "device_title": extract_strong_or_text(cells[11], fallback="—"),
            "device_sub": extract_small_text(cells[11]),
            "status": extract_badge_or_text(cells[12]) or row_match.group("status") or "free",
            "assigned": row_match.group("assigned") or "free",
        }
    if not rows:
        raise RuntimeError("No rows parsed from template")
    return rows


def diagnostics_from_pin(pin: dict[str, Any], fallback: list[str]) -> list[str]:
    out = []
    flags = int(pin.get("diagnostic_flags", 0) or 0)
    for bit, label in DIAG_LABELS:
        if flags & bit:
            out.append(label)
    for item in split_items(pin.get("diagnostics")):
        if item not in out:
            out.append(item)
    return out or fallback


def signal_from_pin(pin: dict[str, Any]) -> tuple[str, str]:
    sig = pin.get("signal")
    if isinstance(sig, dict) and sig.get("name"):
        title = str(sig["name"])
        unit = str(sig.get("unit", "")).strip()
        mn = sig.get("min")
        mx = sig.get("max")
        sub = ""
        if mn is not None or mx is not None:
            sub = f"{unit} · {mn}..{mx}".strip()
        return title, sub
    if isinstance(sig, str) and sig.strip():
        return sig, ""
    return "—", ""


def device_from_pin(pin: dict[str, Any]) -> tuple[str, str]:
    dev = pin.get("device_pin")
    if isinstance(dev, dict):
        return str(dev.get("name", "—")), str(dev.get("description", ""))
    if isinstance(dev, str) and dev.strip():
        return dev, ""
    return "—", ""


def normalize_json_pin(pin: dict[str, Any]) -> dict[str, Any]:
    group = str(pin.get("group", "")).strip()
    functions = pin.get("functions", [])
    if not isinstance(functions, list):
        functions = split_items(functions)
    alt_groups = [str(x) for x in functions if str(x).strip() and str(x).strip() != group]
    signal = pin.get("signal")
    pin_type = pin.get("type", "")
    if isinstance(signal, dict):
        pin_type = signal.get("interface_type", pin_type)
    signal_title, signal_sub = signal_from_pin(pin)
    device_title, device_sub = device_from_pin(pin)
    electrical_lines = split_items(pin.get("electrical")) or []
    if not electrical_lines:
        electrical_lines = electrical_lines_from_capability(int(pin.get("electrical_capability", 0) or 0))

    return {
        "connector": str(pin.get("connector", "")),
        "pin": str(pin.get("physical_number", "")),
        "pin_name": str(pin.get("name", "")),
        "group": group,
        "alt_groups": alt_groups,
        "type": str(pin_type or "UNASSIGNED"),
        "direction": str(pin.get("role", "UNASSIGNED")),
        "electrical_lines": electrical_lines,
        "diagnostics": diagnostics_from_pin(pin, []),
        "sw_config": split_items(pin.get("sw_config")) or [],
        "signal_title": signal_title,
        "signal_sub": signal_sub,
        "device_title": device_title,
        "device_sub": device_sub,
        "status": str(pin.get("status", "free")),
        "assigned": "assigned" if pin.get("is_occupied") else "free",
    }


def merge_template_with_json(template_rows: dict[tuple[str, str], dict[str, Any]], ecu: dict[str, Any]) -> list[dict[str, Any]]:
    merged = {k: dict(v) for k, v in template_rows.items()}
    for pin in ecu.get("pins", []):
        if not isinstance(pin, dict):
            continue
        key = (str(pin.get("connector", "")), str(pin.get("physical_number", "")))
        if key not in merged:
            continue
        src = normalize_json_pin(pin)
        dst = merged[key]

        for field in ("pin_name", "group", "type", "direction", "status", "assigned"):
            if src[field] and src[field] not in {"UNASSIGNED", ""}:
                dst[field] = src[field]
        if src["alt_groups"]:
            dst["alt_groups"] = src["alt_groups"]
        if src["electrical_lines"]:
            dst["electrical_lines"] = src["electrical_lines"]
        if src["diagnostics"]:
            dst["diagnostics"] = src["diagnostics"]
        if src["sw_config"]:
            dst["sw_config"] = src["sw_config"]

        dst["signal_title"] = src["signal_title"]
        dst["signal_sub"] = src["signal_sub"]
        dst["device_title"] = src["device_title"]
        dst["device_sub"] = src["device_sub"]

    rows = list(merged.values())
    rows.sort(key=lambda r: (r["connector"], int(r["pin"]) if str(r["pin"]).isdigit() else 999999))
    return rows


def resolve_template_key(variant: str, parsed_templates: dict[str, dict[tuple[str, str], dict[str, Any]]]) -> str | None:
    normalized = variant.strip().upper()
    if normalized in parsed_templates:
        return normalized
    for token in reversed(re.split(r"[_\-\s]+", normalized)):
        if token in parsed_templates:
            return token
    return None


def rows_for_ecu(ecu: dict[str, Any], parsed_templates: dict[str, dict[tuple[str, str], dict[str, Any]]]) -> tuple[list[dict[str, Any]], str]:
    variant = detect_variant(ecu)
    template_key = resolve_template_key(variant, parsed_templates)

    if template_key:
        rows = merge_template_with_json(parsed_templates[template_key], ecu)
        return rows, f"template:{template_key}"

    rows = [normalize_json_pin(pin) for pin in ecu.get("pins", []) if isinstance(pin, dict)]
    rows.sort(key=lambda r: (r["connector"], int(r["pin"]) if str(r["pin"]).isdigit() else 999999))
    return rows, "json-only"


def render_badges(items: list[str], classes: list[str] | None = None, empty_text: str = "—") -> str:
    if not items:
        return f'<span class="muted">{esc(empty_text)}</span>'
    out = []
    for i, item in enumerate(items):
        cls = classes[i] if classes else ""
        out.append(f'<span class="badge {cls}">{esc(item)}</span>')
    return "\n              ".join(out)


def render_details(lines: list[str]) -> str:
    clean = [str(x).strip() for x in lines if str(x).strip()]
    if not clean:
        return '<span class="muted">—</span>'
    html = ['<div class="details">', f'<div>{esc(clean[0])}</div>']
    for line in clean[1:]:
        html.append(f'<div class="small">{esc(line)}</div>')
    html.append('</div>')
    return "\n                ".join(html)


def render_signal_cell(title: str, sub: str) -> str:
    if not title or title == "—":
        return '<span class="muted">—</span>'
    html = [f'<div><strong>{esc(title)}</strong></div>']
    if sub:
        html.append(f'<div class="small">{esc(sub)}</div>')
    return "\n              ".join(html)


def render_row(r: dict[str, Any]) -> str:
    diag_classes = []
    for i, _ in enumerate(r["diagnostics"]):
        if r["status"] == "warning" and i == len(r["diagnostics"]) - 1:
            diag_classes.append("warn")
        elif r["status"] == "error" and i == len(r["diagnostics"]) - 1:
            diag_classes.append("err")
        else:
            diag_classes.append("ok")
    status_cls = {"valid": "ok", "warning": "warn", "error": "err"}.get(r["status"], "info")
    return f"""          <tr data-group="{esc(r['group'])}" data-type="{esc(r['type'])}" data-status="{esc(r['status'])}" data-assigned="{esc(r['assigned'])}">
            <td>{esc(r['connector'])}</td>
            <td>{esc(r['pin'])}</td>
            <td><strong>{esc(r['pin_name'])}</strong></td>
            <td><span class="badge info">{esc(r['group'])}</span></td>
            <td>
              {render_badges(r['alt_groups'], empty_text='—')}
            </td>
            <td><span class="badge info">{esc(r['type'])}</span></td>
            <td><span class="badge">{esc(r['direction'])}</span></td>
            <td>
              {render_details(r['electrical_lines'])}
            </td>
            <td>
              {render_badges(r['diagnostics'], diag_classes)}
            </td>
            <td>
              {render_badges(r['sw_config'])}
            </td>
            <td>
              {render_signal_cell(r['signal_title'], r['signal_sub'])}
            </td>
            <td>
              {render_signal_cell(r['device_title'], r['device_sub'])}
            </td>
            <td><span class="badge {status_cls}">{esc(r['status'])}</span></td>
          </tr>"""


def compute_kpis(rows: list[dict[str, Any]]) -> tuple[int, int, int, int, int]:
    total = len(rows)
    assigned = sum(1 for r in rows if r["assigned"] == "assigned")
    free = total - assigned
    diagnosable = sum(1 for r in rows if r["diagnostics"])
    errors = sum(1 for r in rows if r["status"] == "error")
    return total, assigned, free, diagnosable, errors


def allocation_summary_from_node(node: dict[str, Any], fallback_total: int, fallback_assigned: int) -> dict[str, float | int]:
    summary = node.get("allocation_summary")
    if isinstance(summary, dict):
        total = int(summary.get("total_pins", fallback_total) or fallback_total)
        assigned = int(summary.get("allocated_pins", fallback_assigned) or fallback_assigned)
        free = int(summary.get("free_pins", max(total - assigned, 0)) or 0)
        percent = float(summary.get("allocation_percent", 0.0) or 0.0)
        return {
            "total": total,
            "assigned": assigned,
            "free": free,
            "percent": percent,
        }
    percent = (100.0 * fallback_assigned / fallback_total) if fallback_total else 0.0
    return {
        "total": fallback_total,
        "assigned": fallback_assigned,
        "free": max(fallback_total - fallback_assigned, 0),
        "percent": percent,
    }


def connector_summaries_from_ecu(ecu: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, float | int | str]]:
    connectors = ecu.get("connectors")
    out: list[dict[str, float | int | str]] = []
    if isinstance(connectors, list):
        for connector in connectors:
            if not isinstance(connector, dict):
                continue
            name = str(connector.get("name", "")).strip()
            if not name:
                continue
            summary = allocation_summary_from_node(connector, 0, 0)
            out.append({
                "name": name,
                "total": int(summary["total"]),
                "assigned": int(summary["assigned"]),
                "free": int(summary["free"]),
                "percent": float(summary["percent"]),
            })
    if out:
        return sorted(out, key=lambda item: (-float(item["percent"]), str(item["name"])))

    grouped: dict[str, dict[str, float | int | str]] = {}
    for row in rows:
        name = str(row.get("connector", "")).strip()
        if not name:
            continue
        if name not in grouped:
            grouped[name] = {"name": name, "total": 0, "assigned": 0}
        grouped[name]["total"] = int(grouped[name]["total"]) + 1
        if row.get("assigned") == "assigned":
            grouped[name]["assigned"] = int(grouped[name]["assigned"]) + 1

    for item in grouped.values():
        total = int(item["total"])
        assigned = int(item["assigned"])
        item["free"] = max(total - assigned, 0)
        item["percent"] = (100.0 * assigned / total) if total else 0.0
        out.append(item)

    return sorted(out, key=lambda item: (-float(item["percent"]), str(item["name"])))


def render_connector_cards(connectors: list[dict[str, float | int | str]]) -> str:
    if not connectors:
        return '<div class="connector-empty muted">No connector allocation data.</div>'

    cards = []
    for connector in connectors:
        name = str(connector["name"])
        total = int(connector["total"])
        assigned = int(connector["assigned"])
        free = int(connector["free"])
        percent = float(connector["percent"])
        tone = "ok"
        if percent >= 80.0:
            tone = "err"
        elif percent >= 50.0:
            tone = "warn"
        cards.append(f"""
    <article class="connector-card">
      <div class="connector-card-head">
        <h3>{esc(name)}</h3>
        <span class="badge {tone}">{percent:.1f}% used</span>
      </div>
      <div class="connector-bar"><span class="{tone}" style="width: {min(percent, 100.0):.1f}%"></span></div>
      <div class="connector-stats">
        <span>Total {total}</span>
        <span>Assigned {assigned}</span>
        <span>Free {free}</span>
      </div>
    </article>""")
    return "\n".join(cards)


def build_section(ecu: dict[str, Any], ecu_name: str, variant: str, rows: list[dict[str, Any]], section_index: int) -> str:
    total, assigned, free, diagnosable, errors = compute_kpis(rows)
    allocation = allocation_summary_from_node(ecu, total, assigned)
    connectors = connector_summaries_from_ecu(ecu, rows)
    groups = sorted({r["group"] for r in rows})
    types = sorted({r["type"] for r in rows})
    statuses = sorted({r["status"] for r in rows})
    tbody = "\n".join(render_row(r) for r in rows)
    group_opts = "\n        ".join([f'<option value="">All Groups</option>'] + [f"<option>{esc(v)}</option>" for v in groups])
    type_opts = "\n        ".join([f'<option value="">All Types</option>'] + [f"<option>{esc(v)}</option>" for v in types])
    status_opts = "\n        ".join([f'<option value="">All Status</option>'] + [f"<option>{esc(v)}</option>" for v in statuses])

    sid = f"ecu{section_index}"
    return f"""
<section class="ecu-section" id="{sid}">
  <header>
    <h1>ECU Pinout - {esc(ecu_name)}</h1>
    <p>Variant: {esc(variant)} · Connector view with assignment, diagnostics, software configuration, and validation status</p>
  </header>

  <section class="summary-cards">
        <div class="card"><div class="label">Total Pins</div><div class="value">{int(allocation['total'])}</div></div>
        <div class="card"><div class="label">Assigned Pins</div><div class="value">{int(allocation['assigned'])}</div></div>
        <div class="card"><div class="label">Free Pins</div><div class="value">{int(allocation['free'])}</div></div>
        <div class="card"><div class="label">Allocation Rate</div><div class="value">{float(allocation['percent']):.1f}%</div></div>
    <div class="card"><div class="label">Diagnosable Pins</div><div class="value">{diagnosable}</div></div>
    <div class="card"><div class="label">Validation Errors</div><div class="value">{errors}</div></div>
  </section>

    <section class="connector-summary">
        <div class="section-title">
            <h2>Connector Hotspots</h2>
            <p>Allocation pressure by connector, sorted from busiest to most available.</p>
        </div>
        <div class="connector-grid">
{render_connector_cards(connectors)}
        </div>
    </section>

  <div class="toolbar">
    <input type="text" id="searchInput_{sid}" placeholder="Search pin, signal, device, connector..." />
    <select id="groupFilter_{sid}">
        {group_opts}
    </select>
    <select id="typeFilter_{sid}">
        {type_opts}
    </select>
    <select id="statusFilter_{sid}">
        {status_opts}
    </select>
    <select id="assignedFilter_{sid}">
        <option value="">Assigned / Free</option>
        <option value="assigned">Assigned</option>
        <option value="free">Free</option>
    </select>
  </div>

  <div class="table-wrap">
    <table id="pinTable_{sid}">
      <thead>
        <tr>
          <th>Connector</th>
          <th>Pin #</th>
          <th>Pin Name</th>
          <th>Main Group</th>
          <th>Alt Groups</th>
          <th>Type</th>
          <th>Direction</th>
          <th>Electrical</th>
          <th>Diagnostics</th>
          <th>SW Config</th>
          <th>Signal</th>
          <th>Device Pin</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
{tbody}
      </tbody>
    </table>
  </div>
</section>
"""


def build_stacked_html(arch_name: str, sections_html: list[str], base_template: str) -> str:
    style_match = re.search(r"<style>(.*?)</style>", base_template, re.S)
    styles = style_match.group(1) if style_match else ""
    styles += """
.ecu-section { margin-bottom: 48px; }
.ecu-section:not(:first-of-type) { border-top: 2px solid rgba(255,255,255,0.08); padding-top: 28px; }
.summary-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }
.connector-summary { display: grid; gap: 14px; }
.connector-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
.connector-card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 16px; display: grid; gap: 12px; }
.connector-card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.connector-card-head h3 { margin: 0; font-size: 16px; }
.connector-bar { height: 10px; border-radius: 999px; overflow: hidden; background: rgba(148,163,184,0.18); }
.connector-bar span { display: block; height: 100%; background: rgba(37,99,235,0.75); }
.connector-bar span.ok { background: rgba(22,163,74,0.75); }
.connector-bar span.warn { background: rgba(217,119,6,0.75); }
.connector-bar span.err { background: rgba(220,38,38,0.75); }
.connector-stats { display: flex; flex-wrap: wrap; gap: 10px 14px; color: var(--muted); font-size: 13px; }
.connector-empty { padding: 12px 0; }
"""
    styles += OVERFLOW_GUARD_CSS
    body = "\n".join(sections_html)
    script_lines = []
    for idx in range(len(sections_html)):
        sid = f"ecu{idx}"
        script_lines.append(f"""
(function() {{
  const searchInput = document.getElementById("searchInput_{sid}");
  const groupFilter = document.getElementById("groupFilter_{sid}");
  const typeFilter = document.getElementById("typeFilter_{sid}");
  const statusFilter = document.getElementById("statusFilter_{sid}");
  const assignedFilter = document.getElementById("assignedFilter_{sid}");
  const rows = Array.from(document.querySelectorAll("#pinTable_{sid} tbody tr"));

  function applyFilters() {{
    const search = searchInput.value.toLowerCase().trim();
    const group = groupFilter.value;
    const type = typeFilter.value;
    const status = statusFilter.value;
    const assigned = assignedFilter.value;

    rows.forEach(row => {{
      const text = row.innerText.toLowerCase();
      const rowGroup = row.dataset.group;
      const rowType = row.dataset.type;
      const rowStatus = row.dataset.status;
      const rowAssigned = row.dataset.assigned;

      const matchSearch = !search || text.includes(search);
      const matchGroup = !group || rowGroup === group;
      const matchType = !type || rowType === type;
      const matchStatus = !status || rowStatus === status;
      const matchAssigned = !assigned || rowAssigned === assigned;

      row.style.display =
        matchSearch && matchGroup && matchType && matchStatus && matchAssigned ? "" : "none";
    }});
  }}

  [searchInput, groupFilter, typeFilter, statusFilter, assignedFilter]
    .forEach(el => el.addEventListener("input", applyFilters));
}})();
""")
    scripts = "\n".join(script_lines)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(arch_name)} - ECU Pinouts</title>
  <style>
{styles}
  </style>
</head>
<body>
  <header>
    <h1>{esc(arch_name)} - ECU Pinouts</h1>
    <p>All ECU pinouts stacked in one HTML file.</p>
  </header>
  <main class="container">
{body}
  </main>
  <script>
{scripts}
  </script>
</body>
</html>"""


def find_base() -> Path:
    script_dir = Path(__file__).resolve().parent
    if (script_dir / "exports").exists() and (script_dir / "templates").exists():
        return script_dir
    if (script_dir.parent / "exports").exists() and (script_dir.parent / "templates").exists():
        return script_dir.parent
    return script_dir


def resolve_path(base: Path, value: Path | None) -> Path | None:
    if value is None:
        return None
    return value if value.is_absolute() else base / value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one stacked HTML pinout for every ECU in an exported architecture JSON."
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Architecture JSON to read. Defaults to exports/exported_physical_architecture.json when present.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="HTML file to write. Defaults to exports/architecture_pinouts_stacked.html.",
    )
    parser.add_argument(
        "--template-dir",
        type=Path,
        help="Directory containing *_full_pinout.html templates. Defaults to templates/.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base = find_base()
    input_override = resolve_path(base, args.input)
    if input_override:
        arch_json = input_override
    else:
        arch_json_candidates = [
            base / "exports" / "exported_physical_architecture.json",
            base / "exports" / "exported_architecture.json",
            base / "exports" / "example_physical_architecture.json",
            base / "exports" / "example_architecture.json",
        ]
        arch_json = next((path for path in arch_json_candidates if path.exists()), arch_json_candidates[0])
    output_html = resolve_path(base, args.output) or base / "exports" / "architecture_pinouts_stacked.html"

    if not arch_json.exists():
        raise SystemExit(f"Missing file: {arch_json}")

    template_dir = resolve_path(base, args.template_dir) or base / "templates"
    templates: dict[str, str] = {}
    parsed_templates: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    if template_dir.exists():
        for tpl_path in sorted(template_dir.glob("*_full_pinout.html")):
            stem = tpl_path.stem
            parts = stem.split("_")
            try:
                fi = parts.index("full")
                if fi >= 1:
                    variant_key = parts[fi - 1].upper()
                else:
                    continue
            except ValueError:
                continue
            try:
                templates[variant_key] = load_html(tpl_path)
                parsed_templates[variant_key] = parse_template_rows(templates[variant_key])
            except Exception as exc:
                print(f"WARNING: Could not parse template '{tpl_path.name}': {exc}")

    data = load_json(arch_json)
    arch_name, ecus = find_arch_and_ecus(data)
    if not ecus:
        raise SystemExit("No ECU found in architecture JSON")

    sections = []
    for ecu in ecus:
        ecu_name = str(ecu.get("name", "ECU"))
        variant = detect_variant(ecu)
        rows, mode = rows_for_ecu(ecu, parsed_templates)
        if not rows:
            print(f"WARNING: ECU '{ecu_name}' has no pin data, skipping")
            continue
        print(f"[OK] {ecu_name}: variant={variant}, pins={len(rows)}, mode={mode}")
        sections.append(build_section(ecu, ecu_name, variant, rows, len(sections)))

    if not sections:
        raise SystemExit("No ECU pinout sections generated")

    first_template = next(iter(templates.values())) if templates else "<style></style>"
    html = build_stacked_html(arch_name, sections, first_template)
    output_html.write_text(html, encoding="utf-8")
    print(f"[OK] {output_html} ({len(sections)} ECU(s) from {arch_json.name})")


if __name__ == "__main__":
    main()
