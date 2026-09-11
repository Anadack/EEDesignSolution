#!/usr/bin/env python3
"""Generate an interactive allocation matrix (HTML) from the architecture JSON.

The matrix shows every signal mapped end-to-end:
  Signal > Device > Device Pin > Interface > ECU > Connector > ECU Pin > Pin Type
with safety, priority, electrical requirement/capability, and compatibility status.

Features:
  - Column sort (click header)
  - Multi-criteria filters (System, ECU, Interface, Safety, Priority)
  - Full-text search
  - Row highlight on hover, click-to-lock
  - Electrical compatibility indicator (green/orange/red)
  - CSV export button
  - Summary KPIs
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from html_overflow_guard import OVERFLOW_GUARD_CSS

# ── Helpers ───────────────────────────────────────────────────────────────

ELEC_FLAGS = {
    1: "PULLUP", 2: "PULLDOWN", 4: "HIGH_SIDE", 8: "LOW_SIDE",
    16: "PUSH_PULL", 32: "CURRENT_SENSE", 64: "VOLTAGE_IN", 128: "DIFFERENTIAL",
}

IFACE_COLORS = {
    "ANALOG": "#2563eb", "PWM": "#d97706", "DIGITAL": "#16a34a", "SENT": "#9333ea",
    "CAN": "#dc2626", "LIN": "#ea580c", "ETHERNET": "#0891b2",
    "POWER": "#64748b", "GROUND": "#334155",
}
DEFAULT_COLOR = "#94a3b8"

SAFETY_COLORS = {"QM": "#22c55e", "SAFETY_RELATED": "#f59e0b"}
PRIO_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def esc(v: Any) -> str:
    return str("" if v is None else v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def decode_elec(val: int) -> str:
    if val == 0:
        return "-"
    flags = [name for bit, name in sorted(ELEC_FLAGS.items()) if val & bit]
    return " | ".join(flags) if flags else str(val)


def elec_compat(req: int, cap: int) -> str:
    """Return 'ok', 'warn', or 'fail'."""
    if req == 0:
        return "ok"
    if cap == 0:
        return "warn"
    missing = req & ~cap
    return "ok" if missing == 0 else "fail"


def find_base() -> Path:
    s = Path(__file__).resolve().parent
    return s.parent if (s.parent / "exports").exists() else s


def load_json(p: Path) -> dict:
    d = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise ValueError("Top-level JSON must be object")
    return d


def get_arch(data: dict) -> dict:
    a = data.get("architecture", data)
    if not isinstance(a, dict):
        raise ValueError("architecture must be object")
    return a


# ── Data extraction ───────────────────────────────────────────────────────

def extract_rows(arch: dict) -> list[dict]:
    """Build one row per mapped signal."""

    # Index ECU pins by signal name
    ecu_index: dict[str, dict] = {}
    for ecu in arch.get("ecus", []):
        if not isinstance(ecu, dict):
            continue
        en = str(ecu.get("name", ""))
        for pin in ecu.get("pins", []):
            if not isinstance(pin, dict):
                continue
            sig = pin.get("signal")
            if not isinstance(sig, dict) or not sig.get("name"):
                continue
            sn = str(sig["name"])
            ecu_index[sn] = {
                "ecu": en,
                "connector": str(pin.get("connector", "")),
                "ecu_pin_num": pin.get("physical_number", ""),
                "ecu_pin_name": str(pin.get("name", "")),
                "ecu_pin_group": str(pin.get("group", "")),
                "ecu_pin_type": str(pin.get("type", "")),
                "ecu_pin_role": str(pin.get("role", "")),
                "interface_type": str(sig.get("interface_type", pin.get("type", "?"))),
                "electrical_capability": int(pin.get("electrical_capability", 0)),
                "sig_type": str(sig.get("type", "")),
                "sig_unit": str(sig.get("unit", "")),
                "sig_min": sig.get("min"),
                "sig_max": sig.get("max"),
                "sig_priority": str(sig.get("priority", "")),
                "sig_safety": str(sig.get("safety", "")),
            }

    rows: list[dict] = []
    for system in arch.get("systems", []):
        if not isinstance(system, dict):
            continue
        sys_name = str(system.get("name", ""))
        sys_level = str(system.get("system_level", ""))
        sys_safety = str(system.get("safety", ""))
        sys_priority = str(system.get("priority", ""))

        for device in system.get("devices", []):
            if not isinstance(device, dict):
                continue
            dev_name = str(device.get("name", ""))
            dev_type = str(device.get("type", ""))

            for dpin in device.get("pins", []):
                if not isinstance(dpin, dict):
                    continue
                sig = dpin.get("signal")
                if not isinstance(sig, dict) or not sig.get("name"):
                    continue
                sn = str(sig["name"])
                dev_pin_num = dpin.get("number", "")
                dev_pin_role = str(dpin.get("role", ""))
                elec_req = int(dpin.get("electrical_requirement", 0))

                ei = ecu_index.get(sn, {})
                elec_cap = ei.get("electrical_capability", 0)
                compat = elec_compat(elec_req, elec_cap)

                rows.append({
                    "signal": sn,
                    "system": sys_name,
                    "sys_level": sys_level,
                    "device": dev_name,
                    "dev_type": dev_type,
                    "dev_pin": dev_pin_num,
                    "role": dev_pin_role,
                    "interface": ei.get("interface_type", "?"),
                    "sig_type": ei.get("sig_type", str(sig.get("type", ""))),
                    "unit": ei.get("sig_unit", ""),
                    "min": ei.get("sig_min"),
                    "max": ei.get("sig_max"),
                    "ecu": ei.get("ecu", ""),
                    "connector": ei.get("connector", ""),
                    "ecu_pin": ei.get("ecu_pin_num", ""),
                    "ecu_pin_name": ei.get("ecu_pin_name", ""),
                    "ecu_group": ei.get("ecu_pin_group", ""),
                    "ecu_type": ei.get("ecu_pin_type", ""),
                    "elec_req": elec_req,
                    "elec_req_str": decode_elec(elec_req),
                    "elec_cap": elec_cap,
                    "elec_cap_str": decode_elec(elec_cap),
                    "compat": compat,
                    "safety": ei.get("sig_safety", sys_safety),
                    "priority": ei.get("sig_priority", sys_priority),
                })

    return rows


# ── HTML generation ───────────────────────────────────────────────────────

COLUMNS = [
    ("signal",       "Signal"),
    ("system",       "System"),
    ("device",       "Device"),
    ("dev_type",     "Dev Type"),
    ("dev_pin",      "Dev Pin#"),
    ("role",         "Role"),
    ("interface",    "Interface"),
    ("sig_type",     "Sig Type"),
    ("unit",         "Unit"),
    ("range",        "Range"),
    ("ecu",          "ECU"),
    ("connector",    "Connector"),
    ("ecu_pin",      "ECU Pin#"),
    ("ecu_pin_name", "ECU Pin"),
    ("ecu_group",    "Group"),
    ("ecu_type",     "Pin Type"),
    ("elec_req_str", "Elec Req"),
    ("elec_cap_str", "Elec Cap"),
    ("compat",       "Compat"),
    ("safety",       "Safety"),
    ("priority",     "Priority"),
]


def build_html(arch_name: str, rows: list[dict]) -> str:
    # Compute KPIs
    systems = sorted(set(r["system"] for r in rows))
    ecus = sorted(set(r["ecu"] for r in rows if r["ecu"]))
    interfaces = sorted(set(r["interface"] for r in rows))
    n_ok = sum(1 for r in rows if r["compat"] == "ok")
    n_warn = sum(1 for r in rows if r["compat"] == "warn")
    n_fail = sum(1 for r in rows if r["compat"] == "fail")

    # Build JSON for JS
    rows_json = json.dumps(rows)
    colors_json = json.dumps(IFACE_COLORS)

    # Filter options
    def opts(key):
        vals = sorted(set(str(r[key]) for r in rows if r[key]))
        return "\n".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in vals)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(arch_name)} - Allocation Matrix</title>
<style>
:root{{
  --bg:#070b12;--surface0:#0b1018;--surface1:#0f1622;--surface2:#151e2e;
  --surface3:#1d2939;--surface4:#273548;--border0:#1a2436;--border1:#233149;
  --border2:#2d3e5c;--text:#cfdaea;--text-dim:#6c83a2;--text-fade:#46566e;
  --cyan:#2ee6ff;--green:#2ee6a0;--amber:#ffb43d;--red:#ff5a78;
  --purple:#b388ff;--teal:#19d6c0;--blue:#5aa6ff;
  --accent:var(--cyan);--ok:var(--green);--warn:var(--amber);--err:var(--red);
  --ink:var(--text);--muted:var(--text-dim);--panel:var(--surface1);
  --panel2:var(--surface2);--line:var(--border1);--radius:16px;
  --shadow:0 8px 30px rgba(0,0,0,.45);
  font-family:Aptos,"Segoe UI Variable","Inter",system-ui,sans-serif;color:var(--text);
}}
*{{box-sizing:border-box;margin:0}}
body{{background:var(--bg);color:var(--text);padding:0}}

.header{{background:linear-gradient(135deg,var(--surface2),var(--surface3));color:var(--text);padding:32px 36px}}
.header h1{{font-size:clamp(1.6rem,3.5vw,2.8rem);letter-spacing:-.03em;font-weight:800}}
.header p{{color:#94a3b8;margin-top:8px}}

.summary{{display:flex;gap:14px;padding:18px 36px;overflow-x:auto;background:var(--panel);border-bottom:1px solid var(--line)}}
.kpi{{flex:0 0 auto;padding:14px 20px;border-radius:14px;background:var(--surface2);border:1px solid var(--border1);min-width:110px}}
.kpi .label{{font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}}
.kpi .val{{font-size:1.7rem;font-weight:800;margin-top:4px}}
.kpi .val.green{{color:#16a34a}}.kpi .val.orange{{color:#d97706}}.kpi .val.red{{color:#dc2626}}

.toolbar{{display:flex;gap:10px;padding:14px 36px;flex-wrap:wrap;align-items:center;background:var(--panel);border-bottom:1px solid var(--line)}}
.toolbar label{{font-size:.78rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}
.toolbar select,.toolbar input{{padding:7px 12px;border:1.5px solid var(--border1);border-radius:10px;font-size:.82rem;background:var(--surface3);color:var(--text);outline:none;transition:border-color .15s}}
.toolbar select:focus,.toolbar input:focus{{border-color:#3b82f6}}
.toolbar input[type=search]{{width:220px}}
.btn{{padding:8px 16px;border:none;border-radius:10px;font-size:.82rem;font-weight:700;cursor:pointer;transition:all .15s}}
.btn-csv{{background:#0f172a;color:#fff}}.btn-csv:hover{{background:#1e3a5f}}
.btn-reset{{background:var(--surface3);color:var(--text);border:1px solid var(--border1)}}.btn-reset:hover{{background:var(--surface4)}}
.matched{{font-size:.78rem;color:var(--muted);margin-left:auto;white-space:nowrap}}

.wrap{{overflow-x:auto;padding:0 36px 24px}}
table{{width:100%;border-collapse:separate;border-spacing:0;margin-top:14px;font-size:.78rem;background:var(--panel);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden}}
thead th{{position:sticky;top:0;z-index:10;background:var(--surface3);padding:10px 12px;text-align:left;font-weight:800;font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:var(--text-dim);border-bottom:2px solid var(--border1);cursor:pointer;white-space:nowrap;user-select:none;transition:background .12s}}
thead th:hover{{background:var(--surface4)}}
thead th .arrow{{display:inline-block;margin-left:4px;font-size:.65rem;opacity:.5;transition:opacity .12s}}
thead th.sorted .arrow{{opacity:1}}
tbody td{{padding:8px 12px;border-bottom:1px solid var(--line);white-space:nowrap}}
tbody tr{{transition:background .1s}}.tr-hover{{background:var(--surface3)!important}}
tbody tr:nth-child(even){{background:var(--surface0)}}
tbody tr.locked{{background:var(--surface4)!important}}

.iface-badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-weight:700;font-size:.7rem;color:#fff}}
.compat-dot{{display:inline-block;width:10px;height:10px;border-radius:50%}}
.compat-ok{{background:#22c55e}}.compat-warn{{background:#f59e0b}}.compat-fail{{background:#ef4444}}
.safety-badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-weight:700;font-size:.7rem}}
.prio-badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-weight:700;font-size:.7rem;background:var(--surface3);color:var(--text)}}
{OVERFLOW_GUARD_CSS}
</style>
</head>
<body>

<div class="header">
  <h1>{esc(arch_name)} &mdash; Allocation Matrix</h1>
  <p>End-to-end signal traceability: Device Pin &rarr; Signal &rarr; ECU Pin. Sort, filter, search, and export.</p>
</div>

<div class="summary">
  <div class="kpi"><div class="label">Signals</div><div class="val">{len(rows)}</div></div>
  <div class="kpi"><div class="label">Systems</div><div class="val">{len(systems)}</div></div>
  <div class="kpi"><div class="label">ECUs</div><div class="val">{len(ecus)}</div></div>
  <div class="kpi"><div class="label">Interfaces</div><div class="val">{len(interfaces)}</div></div>
  <div class="kpi"><div class="label">Elec OK</div><div class="val green">{n_ok}</div></div>
  <div class="kpi"><div class="label">Elec Warn</div><div class="val orange">{n_warn}</div></div>
  <div class="kpi"><div class="label">Elec Fail</div><div class="val red">{n_fail}</div></div>
</div>

<div class="toolbar">
  <label>System</label>
  <select id="fSystem"><option value="">All</option>{opts("system")}</select>
  <label>ECU</label>
  <select id="fEcu"><option value="">All</option>{opts("ecu")}</select>
  <label>Interface</label>
  <select id="fIface"><option value="">All</option>{opts("interface")}</select>
  <label>Safety</label>
  <select id="fSafety"><option value="">All</option>{opts("safety")}</select>
  <label>Priority</label>
  <select id="fPrio"><option value="">All</option>{opts("priority")}</select>
  <label>Compat</label>
  <select id="fCompat"><option value="">All</option><option value="ok">OK</option><option value="warn">Warn</option><option value="fail">Fail</option></select>
  <input type="search" id="fSearch" placeholder="Search signal / device / pin..."/>
  <button class="btn btn-reset" id="btnReset">Reset</button>
  <button class="btn btn-csv" id="btnCsv">Export CSV</button>
  <span class="matched" id="matchCount"></span>
</div>

<div class="wrap">
<table>
<thead><tr id="thead"></tr></thead>
<tbody id="tbody"></tbody>
</table>
</div>

<script>
const ROWS = {rows_json};
const COLORS = {colors_json};
const DEFAULT_COLOR = "{DEFAULT_COLOR}";
const COLS = {json.dumps(COLUMNS)};

// ── Render table header ──────────────────────────────────────────
const thead = document.getElementById("thead");
let sortCol = null, sortAsc = true;
COLS.forEach(([key, label]) => {{
  const th = document.createElement("th");
  th.dataset.key = key;
  th.innerHTML = label + ' <span class="arrow">&#9650;</span>';
  th.addEventListener("click", () => {{
    if (sortCol === key) sortAsc = !sortAsc;
    else {{ sortCol = key; sortAsc = true; }}
    render();
  }});
  thead.appendChild(th);
}});

// ── Filter state ─────────────────────────────────────────────────
const fSystem = document.getElementById("fSystem");
const fEcu    = document.getElementById("fEcu");
const fIface  = document.getElementById("fIface");
const fSafety = document.getElementById("fSafety");
const fPrio   = document.getElementById("fPrio");
const fCompat = document.getElementById("fCompat");
const fSearch = document.getElementById("fSearch");
const matchCount = document.getElementById("matchCount");

[fSystem, fEcu, fIface, fSafety, fPrio, fCompat].forEach(el => el.addEventListener("change", render));
fSearch.addEventListener("input", render);
document.getElementById("btnReset").addEventListener("click", () => {{
  [fSystem, fEcu, fIface, fSafety, fPrio, fCompat].forEach(el => el.value = "");
  fSearch.value = "";
  sortCol = null; sortAsc = true;
  render();
}});

// ── Sort helper ──────────────────────────────────────────────────
function cmp(a, b) {{
  if (a === b) return 0;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, {{numeric: true}});
}}

// ── Render ───────────────────────────────────────────────────────
let lockedIdx = null;
function render() {{
  const sv = fSystem.value, ev = fEcu.value, iv = fIface.value;
  const sav = fSafety.value, pv = fPrio.value, cv = fCompat.value;
  const sq = fSearch.value.toLowerCase();

  let filtered = ROWS.filter(r => {{
    if (sv && r.system !== sv) return false;
    if (ev && r.ecu !== ev) return false;
    if (iv && r.interface !== iv) return false;
    if (sav && r.safety !== sav) return false;
    if (pv && r.priority !== pv) return false;
    if (cv && r.compat !== cv) return false;
    if (sq) {{
      const hay = (r.signal + " " + r.device + " " + r.ecu_pin_name + " " + r.ecu + " " + r.system + " " + r.connector).toLowerCase();
      if (!hay.includes(sq)) return false;
    }}
    return true;
  }});

  if (sortCol) {{
    filtered.sort((a, b) => {{
      const va = a[sortCol] ?? "", vb = b[sortCol] ?? "";
      return sortAsc ? cmp(va, vb) : cmp(vb, va);
    }});
  }}

  // Update header arrows
  thead.querySelectorAll("th").forEach(th => {{
    const k = th.dataset.key;
    th.classList.toggle("sorted", k === sortCol);
    th.querySelector(".arrow").innerHTML = (k === sortCol && !sortAsc) ? "&#9660;" : "&#9650;";
  }});

  const tbody = document.getElementById("tbody");
  let html = "";
  filtered.forEach((r, i) => {{
    const ic = COLORS[r.interface] || DEFAULT_COLOR;
    const range = (r.min != null && r.max != null) ? r.min + " .. " + r.max : "-";
    const compatCls = "compat-" + r.compat;
    const safetyBg = r.safety === "QM" ? "#dcfce7" : "#fef3c7";
    const safetyFg = r.safety === "QM" ? "#166534" : "#92400e";
    html += '<tr data-idx="' + i + '">';
    html += '<td><strong>' + esc(r.signal) + '</strong></td>';
    html += '<td>' + esc(r.system) + '</td>';
    html += '<td>' + esc(r.device) + '</td>';
    html += '<td>' + esc(r.dev_type) + '</td>';
    html += '<td>' + r.dev_pin + '</td>';
    html += '<td>' + esc(r.role) + '</td>';
    html += '<td><span class="iface-badge" style="background:' + ic + '">' + esc(r.interface) + '</span></td>';
    html += '<td>' + esc(r.sig_type) + '</td>';
    html += '<td>' + esc(r.unit) + '</td>';
    html += '<td>' + range + '</td>';
    html += '<td>' + esc(r.ecu) + '</td>';
    html += '<td>' + esc(r.connector) + '</td>';
    html += '<td>' + r.ecu_pin + '</td>';
    html += '<td>' + esc(r.ecu_pin_name) + '</td>';
    html += '<td>' + esc(r.ecu_group) + '</td>';
    html += '<td>' + esc(r.ecu_type) + '</td>';
    html += '<td>' + esc(r.elec_req_str) + '</td>';
    html += '<td>' + esc(r.elec_cap_str) + '</td>';
    html += '<td><span class="compat-dot ' + compatCls + '" title="' + r.compat + '"></span></td>';
    html += '<td><span class="safety-badge" style="background:' + safetyBg + ';color:' + safetyFg + '">' + esc(r.safety) + '</span></td>';
    html += '<td><span class="prio-badge">' + esc(r.priority) + '</span></td>';
    html += '</tr>';
  }});
  tbody.innerHTML = html;
  matchCount.textContent = filtered.length + " / " + ROWS.length + " signals";

  // Row events
  tbody.querySelectorAll("tr").forEach(tr => {{
    tr.addEventListener("mouseenter", () => {{ if (lockedIdx === null) tr.classList.add("tr-hover"); }});
    tr.addEventListener("mouseleave", () => {{ tr.classList.remove("tr-hover"); }});
    tr.addEventListener("click", () => {{
      const idx = tr.dataset.idx;
      if (lockedIdx === idx) {{
        lockedIdx = null;
        tbody.querySelectorAll("tr").forEach(t => t.classList.remove("locked"));
      }} else {{
        lockedIdx = idx;
        tbody.querySelectorAll("tr").forEach(t => t.classList.remove("locked"));
        tr.classList.add("locked");
      }}
    }});
  }});
}}

function esc(v) {{ return String(v == null ? "" : v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }}

// ── CSV export ───────────────────────────────────────────────────
document.getElementById("btnCsv").addEventListener("click", () => {{
  const hdr = COLS.map(c => c[1]).join(";");
  const lines = ROWS.map(r => {{
    return COLS.map(([key]) => {{
      if (key === "range") return (r.min != null ? r.min + ".." + r.max : "");
      let v = r[key];
      if (v == null) v = "";
      return String(v).replace(/;/g, ",");
    }}).join(";");
  }});
  const csv = hdr + "\\n" + lines.join("\\n");
  const blob = new Blob([csv], {{type: "text/csv;charset=utf-8"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "allocation_matrix.csv";
  a.click();
}});

// ── Escape to unlock ─────────────────────────────────────────────
document.addEventListener("keydown", e => {{
  if (e.key === "Escape") {{
    lockedIdx = null;
    document.querySelectorAll("tr.locked").forEach(t => t.classList.remove("locked"));
  }}
}});

// ── Init ─────────────────────────────────────────────────────────
render();
</script>
</body>
</html>"""


def main() -> None:
    base = find_base()
    json_path = base / "exports" / "example_architecture.json"
    if not json_path.exists():
        json_path = base / "exports" / "example_physical_architecture.json"
    if not json_path.exists():
        raise SystemExit(f"Missing: {json_path}")
    out_path = base / "exports" / "architecture_allocation_matrix.html"

    arch = get_arch(load_json(json_path))
    rows = extract_rows(arch)
    html = build_html(str(arch.get("name", "Architecture")), rows)
    out_path.write_text(html, encoding="utf-8")

    n_ok = sum(1 for r in rows if r["compat"] == "ok")
    n_warn = sum(1 for r in rows if r["compat"] == "warn")
    n_fail = sum(1 for r in rows if r["compat"] == "fail")
    print(f"[OK] {out_path}  ({len(rows)} signals, compat: {n_ok} ok / {n_warn} warn / {n_fail} fail)")


if __name__ == "__main__":
    main()
