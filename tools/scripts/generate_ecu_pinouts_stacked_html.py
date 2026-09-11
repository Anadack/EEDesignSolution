#!/usr/bin/env python3
"""ECU Pinouts (Stacked) — All ECU connector pinouts in one interactive page.

Generates a comprehensive pinout viewer showing:
- All ECUs in the architecture
- For each ECU: all connectors with pin utilization
- For each connector: sortable pin table with signals, roles, electrical flags

Signals display using clean standardized names (SYSTEM_Function_[POSITION_]TYPE)
with fallback to original names when clean names unavailable.

Usage:
    python3 generate_ecu_pinouts_stacked_html.py --root /path/to/project
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eec_report_common import (
    get_output_file, load_architecture_from_args, load_config,
    resolve_root, signal_name, standard_arg_parser, write_text,
)


def esc(s: Any) -> str:
    """HTML escape string."""
    if s is None:
        return ""
    s = str(s)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def slugify(s: str) -> str:
    """Convert string to URL-safe slug."""
    import re
    s = str(s or "").replace(" ", "_")
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", s)
    s = re.sub(r"^_|_$", "", s)
    return s or "item"


def iface_color(iface: str) -> str:
    """Return color for interface type."""
    colors = {
        "POWER": "#dc2626",
        "GROUND": "#6b7280",
        "ANALOG": "#f59e0b",
        "DIGITAL": "#3b82f6",
        "CAN": "#06b6d4",
        "LIN": "#8b5cf6",
        "PWM": "#8b5cf6",
        "CURRENT": "#f59e0b",
    }
    iface_upper = str(iface or "").upper()
    return colors.get(iface_upper, "#64748b")


def build_ecu_data(arch: dict) -> dict:
    """Extract ECU and pin data from architecture JSON."""
    ecus = []
    total_pins = 0
    total_occupied = 0

    for ecu_obj in arch.get("ecus", []):
        if not isinstance(ecu_obj, dict):
            continue

        ecu_name = str(ecu_obj.get("name", "Unnamed ECU"))
        ecu_variant = str(ecu_obj.get("variant", ""))
        ecu_pins = ecu_obj.get("pins", [])

        # Group pins by connector
        connectors_dict: dict[str, list] = {}
        occupied_by_connector: dict[str, int] = {}

        for pin_obj in ecu_pins:
            if not isinstance(pin_obj, dict):
                continue

            connector_name = str(pin_obj.get("connector", "Unknown"))
            if connector_name not in connectors_dict:
                connectors_dict[connector_name] = []
                occupied_by_connector[connector_name] = 0

            pin_num = str(pin_obj.get("physical_number", pin_obj.get("number", "")))
            pin_name = str(pin_obj.get("name", ""))
            pin_type = str(pin_obj.get("type", pin_obj.get("interface", "")))
            pin_role = str(pin_obj.get("role", ""))
            pin_group = str(pin_obj.get("group", ""))
            pin_is_occupied = bool(pin_obj.get("is_occupied", False))

            # Extract signal info
            sig_obj = pin_obj.get("signal")
            sig_name = ""
            if isinstance(sig_obj, dict):
                sig_name = signal_name(sig_obj)  # Uses clean_name if available
            elif isinstance(sig_obj, str):
                sig_name = sig_obj

            # Extract electrical flags
            elec_flags = pin_obj.get("electrical_flags", [])
            if isinstance(elec_flags, int):
                # Decode bitmask if needed
                elec_flags = []
            elif not isinstance(elec_flags, list):
                elec_flags = []

            # Extract diagnostic flags
            diag_flags = pin_obj.get("diagnostics", [])
            if not isinstance(diag_flags, list):
                diag_flags = []

            pin_data = {
                "pin": pin_num,
                "name": pin_name,
                "type": pin_type,
                "interface": pin_type,
                "signal": sig_name,
                "role": pin_role,
                "group": pin_group,
                "elec": elec_flags,
                "diag": diag_flags,
                "occupied": pin_is_occupied,
            }

            connectors_dict[connector_name].append(pin_data)
            if pin_is_occupied:
                occupied_by_connector[connector_name] += 1

        # Build connector objects
        connectors = []
        for conn_name in sorted(connectors_dict.keys()):
            pins = connectors_dict[conn_name]
            total_in_conn = len(pins)
            occupied_in_conn = occupied_by_connector.get(conn_name, 0)

            conn_data = {
                "name": conn_name,
                "total": total_in_conn,
                "occupied": occupied_in_conn,
                "pins": pins,
            }
            connectors.append(conn_data)
            total_pins += total_in_conn
            total_occupied += occupied_in_conn

        ecu_data = {
            "name": ecu_name,
            "variant": ecu_variant,
            "connectors": connectors,
        }
        ecus.append(ecu_data)

    return {
        "ecus": ecus,
        "total_pins": total_pins,
        "total_occupied": total_occupied,
        "total_free": total_pins - total_occupied,
    }


def generate_html(ecu_data: dict, arch: dict, arch_path: Path) -> str:
    """Generate HTML pinout viewer."""
    arch_name = str(arch.get("architecture", {}).get("name", "Architecture"))

    html = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Architecture ECU Pinout</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<style>
:root{{
  --bg:#0d0f14;--surface:#131720;--raised:#1a1f2e;--hover:#1f2538;--active:#242b42;
  --b0:rgba(255,255,255,.06);--b1:rgba(255,255,255,.10);--b2:rgba(255,255,255,.16);
  --tp:#e8ecf4;--ts:#8993a8;--tm:#5a6278;--ta:#60a5fa;
  --accent:#3b82f6;--accent-dim:rgba(59,130,246,.15);
  --ok:#22c55e;--err:#ef4444;
  --r:6px;--rm:10px;--rl:16px;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%;overflow:hidden}}
body{{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--tp);font-size:13px;display:flex;flex-direction:column}}
button,input,select{{font:inherit;color:inherit}}

/* ── topbar ────────────────────────────────────────────────── */
.topbar{{
  flex:0 0 auto;display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  padding:0 20px;height:56px;
  background:var(--surface);border-bottom:1px solid var(--b1);
  position:sticky;top:0;z-index:200;
}}
.topbar-logo{{display:flex;align-items:center;gap:9px}}
.topbar-logo svg{{color:var(--accent)}}
.topbar-title{{font-size:1rem;font-weight:700;letter-spacing:-.02em;white-space:nowrap}}
.topbar-source{{font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--tm);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px}}
.kpi-strip{{display:flex;gap:6px;align-items:center;margin-left:auto;flex-wrap:wrap}}
.kpi-pill{{display:flex;flex-direction:column;align-items:center;padding:4px 12px;
  border-radius:20px;background:var(--raised);border:1px solid var(--b1);min-width:72px}}
.kp-label{{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--tm);line-height:1.2}}
.kp-val{{font-family:'JetBrains Mono',monospace;font-size:1rem;font-weight:700;color:var(--tp);line-height:1.2}}
.kp-val.ok{{color:#4ade80}}.kp-val.err{{color:#f87171}}.kp-val.acc{{color:#60a5fa}}

/* ── layout ────────────────────────────────────────────────── */
.app-body{{flex:1;display:flex;overflow:hidden}}

/* ── sidebar ────────────────────────────────────────────────── */
.sidebar{{
  flex:0 0 240px;display:flex;flex-direction:column;
  background:var(--surface);border-right:1px solid var(--b0);
  overflow:hidden;
}}
.sidebar-header{{
  padding:12px 14px 8px;font-size:10px;font-weight:700;
  text-transform:uppercase;letter-spacing:.07em;color:var(--tm);
  border-bottom:1px solid var(--b0);flex-shrink:0;
}}
.sidebar-search{{padding:8px 10px;flex-shrink:0;border-bottom:1px solid var(--b0)}}
.sidebar-search input{{
  width:100%;padding:6px 10px;border-radius:var(--r);
  background:var(--raised);border:1px solid var(--b1);color:var(--tp);
  outline:none;font-size:12px;transition:border-color .15s;
}}
.sidebar-search input:focus{{border-color:var(--accent)}}
.sidebar-search input::placeholder{{color:var(--tm)}}
.sidebar-list{{overflow-y:auto;flex:1;padding:6px 0}}
.sidebar-item{{
  display:flex;align-items:center;gap:8px;padding:8px 14px;
  cursor:pointer;border-left:3px solid transparent;transition:all .12s;
}}
.sidebar-item:hover{{background:var(--hover);color:var(--tp)}}
.sidebar-item.active{{
  background:var(--accent-dim);border-left-color:var(--accent);color:var(--ta);
}}
.sidebar-item-name{{font-size:12px;font-weight:500;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.sidebar-item-cnt{{
  font-family:'JetBrains Mono',monospace;font-size:9.5px;color:var(--tm);
  background:var(--raised);border:1px solid var(--b0);border-radius:10px;
  padding:1px 6px;flex-shrink:0;
}}

/* ── main content ───────────────────────────────────────────── */
.main-content{{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:0}}

/* ── filterbar ──────────────────────────────────────────────── */
.filterbar{{
  position:sticky;top:0;z-index:100;
  display:flex;gap:8px;flex-wrap:wrap;align-items:center;
  background:var(--surface);border-bottom:1px solid var(--b0);
  padding:9px 18px;flex-shrink:0;
}}
.filterbar-label{{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--tm);white-space:nowrap}}
.filter-btn{{
  padding:4px 10px;border-radius:20px;border:1px solid var(--b1);
  background:transparent;color:var(--ts);font-size:11px;font-weight:500;
  cursor:pointer;transition:all .12s;white-space:nowrap;
}}
.filter-btn:hover{{background:var(--hover);color:var(--tp);border-color:var(--b2)}}
.filter-btn.active{{background:var(--accent-dim);color:var(--ta);border-color:var(--accent)}}
.filter-input{{
  padding:5px 10px;border-radius:var(--r);
  background:var(--raised);border:1px solid var(--b1);color:var(--tp);outline:none;
  font-size:12px;min-width:140px;transition:border-color .15s;
}}
.filter-input:focus{{border-color:var(--accent)}}
.filter-input::placeholder{{color:var(--tm)}}

/* ── ECU sections ───────────────────────────────────────────── */
.ecu-sections{{padding:18px 20px;display:flex;flex-direction:column;gap:22px}}
.ecu-section{{display:flex;flex-direction:column;gap:12px}}
.ecu-section[hidden]{{display:none!important}}
.ecu-header{{
  display:flex;align-items:center;gap:10px;
  padding-bottom:10px;border-bottom:1px solid var(--b0);
}}
.ecu-header h2{{font-size:1.05rem;font-weight:700;letter-spacing:-.01em}}
.variant-badge{{
  padding:2px 9px;border-radius:12px;font-size:10px;font-weight:700;
  font-family:'JetBrains Mono',monospace;
  background:var(--accent-dim);color:var(--ta);border:1px solid rgba(59,130,246,.25);
}}

/* ── connector grid ─────────────────────────────────────────── */
.conn-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}}
.conn-card{{
  background:var(--raised);border:1px solid var(--b0);border-radius:var(--rm);
  padding:12px 14px;display:flex;flex-direction:column;gap:8px;
}}
.conn-card-name{{font-size:11px;font-weight:700;color:var(--tp);font-family:'JetBrains Mono',monospace}}
.conn-card-counts{{display:flex;justify-content:space-between;font-size:10px;color:var(--ts)}}
.conn-card-counts .used{{color:#4ade80}}
.conn-prog-track{{height:3px;border-radius:2px;background:var(--b0);overflow:hidden}}
.conn-prog-fill{{height:100%;border-radius:2px;background:#22c55e;transition:width .3s}}

/* ── pin table ──────────────────────────────────────────────── */
.pin-table-wrap{{
  background:var(--surface);border:1px solid var(--b0);border-radius:var(--rm);overflow:auto;
}}
table{{width:100%;border-collapse:collapse;font-size:11.5px}}
thead th{{
  position:sticky;top:0;z-index:5;
  background:var(--raised);padding:8px 12px;
  text-align:left;font-size:9.5px;font-weight:700;text-transform:uppercase;
  letter-spacing:.06em;color:var(--tm);
  border-bottom:1px solid var(--b1);cursor:pointer;white-space:nowrap;user-select:none;
}}
thead th:hover{{background:var(--active);color:var(--ts)}}
thead th .sa{{margin-left:3px;opacity:.35;font-size:9px}}
thead th.sort-asc .sa::after{{content:'▲';opacity:1}}
thead th.sort-desc .sa::after{{content:'▼';opacity:1}}
thead th:not(.sort-asc):not(.sort-desc) .sa::after{{content:'⇅'}}
td{{padding:7px 12px;border-bottom:1px solid var(--b0);vertical-align:middle;color:var(--ts)}}
tr:last-child td{{border-bottom:none}}
tbody tr:hover td{{background:rgba(255,255,255,.025);color:var(--tp)}}
tbody tr[hidden]{{display:none!important}}
.pin-num{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;color:var(--tp)}}
.sig-name{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;color:var(--ta)}}
.iface-pill{{
  display:inline-flex;align-items:center;padding:2px 7px;border-radius:4px;
  font-family:'JetBrains Mono',monospace;font-size:9.5px;font-weight:700;
  white-space:nowrap;border:1px solid transparent;
}}
.occ-badge{{
  display:inline-flex;align-items:center;gap:5px;
  font-size:10px;font-weight:600;
}}
.occ-dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0}}
.occ-yes .occ-dot{{background:#22c55e}}
.occ-yes{{color:#4ade80}}
.occ-no .occ-dot{{background:var(--tm)}}
.occ-no{{color:var(--tm)}}
.elec-tag{{
  display:inline-block;padding:1px 5px;border-radius:3px;
  background:rgba(255,255,255,.05);color:var(--ts);
  font-size:9.5px;font-family:'JetBrains Mono',monospace;border:1px solid var(--b0);
  margin:1px 2px 1px 0;
}}

::-webkit-scrollbar{{width:5px;height:5px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:var(--b1);border-radius:3px}}
::-webkit-scrollbar-thumb:hover{{background:var(--b2)}}
</style>
</head>
<body>

<header class="topbar">
  <div class="topbar-logo">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
         stroke-linecap="round" stroke-linejoin="round">
      <rect x="2" y="7" width="20" height="14" rx="2"/>
      <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
      <line x1="12" y1="12" x2="12" y2="16"/><line x1="10" y1="14" x2="14" y2="14"/>
    </svg>
    <span class="topbar-title">ECU Pinout</span>
  </div>
  <span class="topbar-source" id="src-label">{esc(str(arch_path))}</span>
  <div class="kpi-strip">
    <div class="kpi-pill"><span class="kp-label">ECUs</span><span class="kp-val acc" id="kpi-ecus">{len(ecu_data['ecus'])}</span></div>
    <div class="kpi-pill"><span class="kp-label">Total Pins</span><span class="kp-val" id="kpi-total">{ecu_data['total_pins']}</span></div>
    <div class="kpi-pill"><span class="kp-label">Occupied</span><span class="kp-val ok" id="kpi-occ">{ecu_data['total_occupied']}</span></div>
    <div class="kpi-pill"><span class="kp-label">Free</span><span class="kp-val err" id="kpi-free">{ecu_data['total_free']}</span></div>
  </div>
</header>

<div class="app-body">
  <aside class="sidebar">
    <div class="sidebar-header">ECUs</div>
    <div class="sidebar-search"><input id="sidebar-search" type="text" placeholder="Search ECU..."/></div>
    <div class="sidebar-list" id="sidebar-list"></div>
  </aside>
  <main class="main-content">
    <div class="filterbar">
      <span class="filterbar-label">Signal</span>
      <button class="filter-btn active" data-filter="all">All</button>
      <button class="filter-btn" data-filter="occupied">Occupied</button>
      <button class="filter-btn" data-filter="free">Free</button>
    </div>
    <div class="ecu-sections" id="ecu-sections"></div>
  </main>
</div>

<script>
var ecuData = {json.dumps(ecu_data)};

function escHtml(s) {{
  if(!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}}

function ifacePill(iface) {{
  var colors = {{'POWER':'#dc2626','GROUND':'#6b7280','ANALOG':'#f59e0b','DIGITAL':'#3b82f6','CAN':'#06b6d4','LIN':'#8b5cf6','PWM':'#8b5cf6','CURRENT':'#f59e0b'}};
  var i = String(iface||'').toUpperCase();
  var color = colors[i] || '#64748b';
  return '<span class="iface-pill" style="background:' + color + '40;border-color:' + color + '66;color:' + color + '">' + escHtml(iface) + '</span>';
}}

function elecTags(arr) {{
  if(!arr || !arr.length) return '<span style="color:var(--tm)">—</span>';
  return arr.map(function(tag) {{ return '<span class="elec-tag">' + escHtml(tag) + '</span>'; }}).join('');
}}

function occBadge(occ) {{
  return '<span class="occ-badge ' + (occ ? 'occ-yes' : 'occ-no') + '"><span class="occ-dot"></span>' + (occ ? 'Occupied' : 'Free') + '</span>';
}}

function slugify(s) {{
  return String(s||'').replace(/[^A-Za-z0-9_.-]+/g,'_').replace(/^_|_$/g,'') || 'item';
}}

buildSidebar();
buildEcuSections();

function buildSidebar() {{
  var list = document.getElementById('sidebar-list');
  list.innerHTML = '';
  ecuData.ecus.forEach(function(ecu) {{
    var occPins = 0;
    ecu.connectors.forEach(function(c) {{ occPins += c.occupied; }});
    var totalPins = 0;
    ecu.connectors.forEach(function(c) {{ totalPins += c.total; }});
    var item = document.createElement('div');
    item.className = 'sidebar-item';
    item.dataset.ecuName = ecu.name;
    item.innerHTML = '<span class="sidebar-item-name">' + escHtml(ecu.name) + '</span>'
                   + '<span class="sidebar-item-cnt">' + occPins + '/' + totalPins + '</span>';
    item.addEventListener('click', function() {{
      document.querySelectorAll('.sidebar-item').forEach(function(i) {{ i.classList.remove('active'); }});
      item.classList.add('active');
      var sec = document.getElementById('ecu-sec-' + slugify(ecu.name));
      if(sec) sec.scrollIntoView({{behavior:'smooth',block:'start'}});
    }});
    list.appendChild(item);
  }});
}}

document.getElementById('sidebar-search').addEventListener('input', function() {{
  var q = this.value.toLowerCase();
  document.querySelectorAll('.sidebar-item').forEach(function(item) {{
    var name = (item.dataset.ecuName || '').toLowerCase();
    item.style.display = name.indexOf(q) >= 0 ? '' : 'none';
  }});
}});

function buildEcuSections() {{
  var container = document.getElementById('ecu-sections');
  container.innerHTML = '';
  ecuData.ecus.forEach(function(ecu) {{
    var secId = 'ecu-sec-' + slugify(ecu.name);
    var sec = document.createElement('div');
    sec.className = 'ecu-section';
    sec.id = secId;
    sec.dataset.ecuName = ecu.name.toLowerCase();

    var hdr = document.createElement('div');
    hdr.className = 'ecu-header';
    hdr.innerHTML = '<h2>' + escHtml(ecu.name) + '</h2>'
                  + (ecu.variant ? '<span class="variant-badge">' + escHtml(ecu.variant) + '</span>' : '');
    sec.appendChild(hdr);

    var grid = document.createElement('div');
    grid.className = 'conn-grid';
    ecu.connectors.forEach(function(conn) {{
      var pct = conn.total > 0 ? Math.round(conn.occupied / conn.total * 100) : 0;
      var card = document.createElement('div');
      card.className = 'conn-card';
      card.innerHTML = '<div class="conn-card-name">' + escHtml(conn.name) + '</div>'
        + '<div class="conn-card-counts"><span><span class="used">' + conn.occupied + '</span> used</span><span>' + conn.total + ' total</span></div>'
        + '<div class="conn-prog-track"><div class="conn-prog-fill" style="width:' + pct + '%"></div></div>';
      grid.appendChild(card);
    }});
    sec.appendChild(grid);

    ecu.connectors.forEach(function(conn) {{
      var tbl = buildPinTable(ecu.name, conn);
      sec.appendChild(tbl);
    }});

    container.appendChild(sec);
  }});
}}

function buildPinTable(ecuName, conn) {{
  var wrap = document.createElement('div');
  wrap.className = 'pin-table-wrap';
  wrap.dataset.connName = conn.name.toLowerCase();

  var connLabel = document.createElement('div');
  connLabel.style.cssText = 'padding:10px 14px 0;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--tm)';
  connLabel.textContent = conn.name;
  wrap.appendChild(connLabel);

  var tbl = document.createElement('table');
  tbl.dataset.ecuName = ecuName;
  tbl.dataset.connName = conn.name;
  var PIN_COLS = ['pin','name','type','signal','role','group','elec','diag','occupied'];
  var PIN_LABELS = ['Pin #','Name','Type','Signal','Role','Group','Electrical','Diagnostics','Status'];

  var thead = document.createElement('thead');
  var trh = document.createElement('tr');
  PIN_LABELS.forEach(function(lbl, idx) {{
    var th = document.createElement('th');
    th.innerHTML = escHtml(lbl) + '<span class="sa"></span>';
    th.dataset.idx = idx;
    th.addEventListener('click', function() {{
      var rows = Array.from(tbl.querySelectorAll('tbody tr'));
      var asc  = tbl.dataset.sortIdx === String(idx) ? tbl.dataset.sortDir !== 'asc' : true;
      tbl.dataset.sortIdx = idx;
      tbl.dataset.sortDir = asc ? 'asc' : 'desc';
      trh.querySelectorAll('th').forEach(function(h) {{ h.classList.remove('sort-asc','sort-desc'); }});
      th.classList.add(asc ? 'sort-asc' : 'sort-desc');
      rows.sort(function(a,b) {{
        var A = a.children[idx].dataset.sortVal || a.children[idx].textContent;
        var B = b.children[idx].dataset.sortVal || b.children[idx].textContent;
        var na = parseFloat(A), nb = parseFloat(B);
        var cmp = (!isNaN(na)&&!isNaN(nb)) ? na-nb : A.localeCompare(B);
        return asc ? cmp : -cmp;
      }});
      rows.forEach(function(r) {{ tbl.querySelector('tbody').appendChild(r); }});
    }});
    trh.appendChild(th);
  }});
  thead.appendChild(trh);
  tbl.appendChild(thead);

  var tbody = document.createElement('tbody');
  conn.pins.forEach(function(p) {{
    var tr = document.createElement('tr');
    tr.dataset.pinType = (p.type||'').toLowerCase();
    tr.dataset.pinOcc  = p.occupied;

    var cells = [
      '<span class="pin-num">' + escHtml(p.pin) + '</span>',
      escHtml(p.name),
      ifacePill(p.type || p.interface),
      p.signal ? '<span class="sig-name">' + escHtml(p.signal) + '</span>' : '<span style="color:var(--tm)">—</span>',
      escHtml(p.role) || '<span style="color:var(--tm)">—</span>',
      escHtml(p.group) || '<span style="color:var(--tm)">—</span>',
      elecTags(p.elec),
      elecTags(p.diag),
      occBadge(p.occupied),
    ];
    cells.forEach(function(c, ci) {{
      var td = document.createElement('td');
      td.innerHTML = c;
      if(ci===0) td.dataset.sortVal = parseFloat(p.pin)||0;
      tr.appendChild(td);
    }});
    tbody.appendChild(tr);
  }});
  tbl.appendChild(tbody);
  wrap.appendChild(tbl);
  return wrap;
}}

var activeFilter = 'all';
document.querySelectorAll('.filter-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    this.classList.add('active');
    activeFilter = this.dataset.filter;
    applyFilters();
  }});
}});

function applyFilters() {{
  document.querySelectorAll('tbody tr').forEach(function(tr) {{
    var occ = tr.dataset.pinOcc === 'true' || tr.dataset.pinOcc === '1';
    var show = (activeFilter === 'all') || (activeFilter === 'occupied' && occ) || (activeFilter === 'free' && !occ);
    tr.hidden = !show;
  }});
}}
</script>
</body>
</html>
"""
    return html


def main() -> int:
    parser = standard_arg_parser(
        "Generate comprehensive ECU pinout viewer with all connectors and pins."
    )
    args = parser.parse_args()
    root = resolve_root(args.root)
    cfg = load_config(Path(args.config) if args.config else None)
    src, arch = load_architecture_from_args(args, cfg, physical=False)

    if not arch:
        print("[ERROR] Could not load architecture")
        return 1

    # Get architecture path for display
    arch_path = args.input or src

    # Extract ECU data
    ecu_data = build_ecu_data(arch)

    # Generate HTML
    html = generate_html(ecu_data, arch, arch_path)

    # Write output
    outfile = get_output_file(root, cfg, "ecu_pinouts_stacked", args.output, args.outdir)
    write_text(outfile, html)
    print(outfile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
