#!/usr/bin/env python3
"""Signal Flow Diagram — Interactive system-to-ECU signal routing visualization.

Generates an interactive diagram showing:
- System/ECU pairs with signal flow paths
- I/O signals flowing left to right
- Bus interfaces (CAN, ETH) in network backbone
- Hover/click interactions for signal inspection
- Filtering by interface type

Usage:
    python3 generate_signal_flow_html.py --root /path/to/project
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from collections import defaultdict

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


def build_signal_flow_data(arch: dict) -> dict:
    """Extract signal flow data from architecture JSON."""
    pairs = []
    ecu_io_map = {}
    bus_links = []
    bus_net = defaultdict(list)

    all_ifaces = set()

    # Process systems
    for sys_obj in (arch.get("systems") or []):
        if not isinstance(sys_obj, dict):
            continue

        sys_name = str(sys_obj.get("name", "Unnamed System"))

        # Get sensors and actuators for this system
        devices_io = []

        # Process components and their devices
        for comp_obj in (sys_obj.get("components") or []):
            if not isinstance(comp_obj, dict):
                continue

            for dev_obj in (comp_obj.get("sensors") or []):
                if isinstance(dev_obj, dict):
                    dev_data = _extract_device_data(dev_obj, "SENSOR")
                    if dev_data:
                        devices_io.append(dev_data)

            for dev_obj in (comp_obj.get("actuators") or []):
                if isinstance(dev_obj, dict):
                    dev_data = _extract_device_data(dev_obj, "ACTUATOR")
                    if dev_data:
                        devices_io.append(dev_data)

        # Find primary ECU for this system (first ECU in architecture)
        primary_ecu = None
        for ecu_obj in (arch.get("ecus") or []):
            if isinstance(ecu_obj, dict):
                primary_ecu = str(ecu_obj.get("name", ""))
                break

        if not primary_ecu or not devices_io:
            continue

        # Build IO links
        io_links = []
        for dev in devices_io:
            for batch in dev.get("batches", []):
                iface = batch.get("interface", "?")
                all_ifaces.add(iface)

                for sig_name in batch.get("signals", []):
                    io_links.append({
                        "signal": sig_name,
                        "system": sys_name,
                        "device": dev.get("name", ""),
                        "batch": batch.get("prefix", ""),
                        "interface": iface,
                        "ecu": primary_ecu,
                        "connector": "X1000",  # Default connector
                        "ecu_pin": "",
                    })

        pairs.append({
            "system": sys_name,
            "devices_io": devices_io,
            "devices_bus": [],
            "primary_ecu": primary_ecu,
            "io_links": io_links,
        })

    # Build ECU_IO map
    for ecu_obj in (arch.get("ecus") or []):
        if not isinstance(ecu_obj, dict):
            continue

        ecu_name = str(ecu_obj.get("name", ""))
        connectors = []

        for conn_obj in (ecu_obj.get("connectors") or []):
            if not isinstance(conn_obj, dict):
                continue

            conn_name = str(conn_obj.get("name", ""))
            groups = {}

            for pin_obj in (ecu_obj.get("pins") or []):
                if not isinstance(pin_obj, dict):
                    continue

                if str(pin_obj.get("connector", "")) != conn_name:
                    continue

                iface = str(pin_obj.get("interface_type", pin_obj.get("type", "?"))).upper()
                all_ifaces.add(iface)

                if iface not in groups:
                    groups[iface] = {"interface": iface, "count": 0, "signals": []}

                sig_obj = pin_obj.get("signal")
                if sig_obj:
                    sig_name = signal_name(sig_obj) if isinstance(sig_obj, dict) else str(sig_obj)
                    groups[iface]["signals"].append(sig_name)
                    groups[iface]["count"] += 1

            if groups:
                connectors.append({
                    "name": conn_name,
                    "groups": list(groups.values()),
                })

        if connectors:
            ecu_io_map[ecu_name] = connectors

    # Build bus links and network
    for ecu_obj in (arch.get("ecus") or []):
        if not isinstance(ecu_obj, dict):
            continue

        ecu_name = str(ecu_obj.get("name", ""))

        for pin_obj in (ecu_obj.get("pins") or []):
            if not isinstance(pin_obj, dict):
                continue

            iface = str(pin_obj.get("interface_type", pin_obj.get("type", ""))).upper()

            # Check if it's a bus interface
            if iface in ("CAN", "LIN", "ETHERNET", "FLEXRAY"):
                sig_obj = pin_obj.get("signal")
                if sig_obj:
                    sig_name = signal_name(sig_obj) if isinstance(sig_obj, dict) else str(sig_obj)

                    bus_links.append({
                        "signal": sig_name,
                        "system": "",
                        "device": "",
                        "batch": "",
                        "interface": iface,
                        "ecu": ecu_name,
                        "connector": str(pin_obj.get("connector", "")),
                        "ecu_pin": str(pin_obj.get("physical_number", "")),
                    })

                    # Add to bus_net
                    key = (ecu_name, str(pin_obj.get("connector", "")))
                    found = False
                    for ep in bus_net.get(iface, []):
                        if ep["ecu"] == ecu_name and ep["connector"] == str(pin_obj.get("connector", "")):
                            ep["signals"].append(sig_name)
                            ep["count"] += 1
                            found = True
                            break

                    if not found:
                        bus_net[iface].append({
                            "ecu": ecu_name,
                            "connector": str(pin_obj.get("connector", "")),
                            "count": 1,
                            "signals": [sig_name],
                        })

    return {
        "pairs": pairs,
        "ecu_io": ecu_io_map,
        "bus_links": bus_links,
        "bus_net": dict(bus_net),
        "all_ifaces": sorted(list(all_ifaces)),
    }


def _extract_device_data(dev_obj: dict, dev_type: str) -> dict | None:
    """Extract device with batches of signals."""
    dev_name = str(dev_obj.get("name", ""))
    if not dev_name:
        return None

    pins = dev_obj.get("pins", [])
    if not pins:
        return None

    batches = {}
    for pin_obj in pins:
        if not isinstance(pin_obj, dict):
            continue

        iface = str(pin_obj.get("interface", pin_obj.get("interface_type", "?"))).upper()
        role = str(pin_obj.get("role", "")).upper()

        # Create batch prefix from role
        batch_prefix = f"{slugify(dev_name)}_{role.lower()}"

        if batch_prefix not in batches:
            batches[batch_prefix] = {
                "prefix": batch_prefix,
                "interface": iface,
                "role": role,
                "signals": [],
            }

        sig_obj = pin_obj.get("signal")
        if sig_obj:
            sig_name = signal_name(sig_obj) if isinstance(sig_obj, dict) else str(sig_obj)
            batches[batch_prefix]["signals"].append(sig_name)

    if not batches:
        return None

    return {
        "name": dev_name,
        "type": dev_type,
        "batches": list(batches.values()),
    }


def generate_html(data: dict, arch: dict, arch_path: Path) -> str:
    """Generate signal flow HTML."""
    arch_name = str(arch.get("architecture", {}).get("name", "Architecture"))

    pairs = data.get("pairs", [])
    ecu_io = data.get("ecu_io", {})
    bus_links = data.get("bus_links", [])
    bus_net = data.get("bus_net", {})
    all_ifaces = data.get("all_ifaces", [])

    # Count totals
    total_systems = len(pairs)
    total_ecus = len(ecu_io)
    total_io_signals = sum(len(link["signals"]) for link in [l for link in pairs for l in [l.get("io_links", [])]])
    total_bus_signals = len(bus_links)
    total_ifaces = len(all_ifaces)

    # Build filter buttons
    filter_btns = ""
    colors = {
        "ANALOG": "#2563eb", "PWM": "#d97706", "DIGITAL": "#16a34a", "SENT": "#9333ea",
        "CAN": "#dc2626", "LIN": "#ea580c", "ETHERNET": "#0891b2", "FLEXRAY": "#6366f1",
        "POWER": "#64748b", "GROUND": "#334155", "FREQUENCY": "#94a3b8",
        "CURRENT": "#16a34a", "RESISTANCE": "#94a3b8", "SUPPLY": "#64748b",
        "?": "#94a3b8"
    }

    for iface in sorted(all_ifaces):
        color = colors.get(iface, "#94a3b8")
        count = sum(1 for l in bus_links if l["interface"] == iface) + \
                sum(1 for p in pairs for link in p.get("io_links", []) if link["interface"] == iface)
        filter_btns += f'<button class="filter-btn active" data-iface="{esc(iface)}" style="--dot:{color}"><span class="dot"></span>{esc(iface)} <span class="cnt">{count}</span></button>\n        '

    # Build legend
    legend_items = ""
    for iface in sorted(colors.keys()):
        if iface in all_ifaces or iface in colors:
            legend_items += f'<span class="legend-item"><span class="legend-swatch" style="background:{colors[iface]}"></span>{iface}</span>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>{esc(arch_name)} - Signal Flow</title>
<style>
:root{{
  --bg:#f0f4f8;--panel:#fff;--ink:#1e293b;--muted:#64748b;--line:#dbe4f0;
  --radius:16px;--shadow:0 8px 32px rgba(30,41,59,.07);
  font-family:Aptos,"Segoe UI Variable","Inter",system-ui,sans-serif;
  color:var(--ink);
}}
*{{box-sizing:border-box;margin:0}}
body{{background:var(--bg);padding:0}}

/* header */
.header{{background:linear-gradient(135deg,#0f172a,#1e3a5f);color:#fff;padding:32px 36px}}
.header h1{{font-size:clamp(1.6rem,3.5vw,2.8rem);letter-spacing:-.03em;font-weight:800}}
.header p{{color:#94a3b8;margin-top:8px;max-width:80ch}}

/* summary */
.summary{{display:flex;gap:14px;padding:18px 36px;overflow-x:auto;background:var(--panel);border-bottom:1px solid var(--line)}}
.kpi{{flex:0 0 auto;padding:14px 20px;border-radius:14px;background:#f8fafc;border:1px solid var(--line);min-width:130px}}
.kpi .label{{font-size:.75rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}}
.kpi .val{{font-size:1.8rem;font-weight:800;margin-top:4px}}

/* filters */
.filters{{display:flex;gap:8px;flex-wrap:wrap;padding:14px 36px;background:var(--panel);border-bottom:1px solid var(--line);align-items:center}}
.filters-label{{font-size:.82rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-right:6px}}
.filter-btn{{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:999px;border:1.5px solid var(--line);background:var(--panel);cursor:pointer;font-size:.82rem;font-weight:600;color:var(--ink);transition:all .15s}}
.filter-btn .dot{{width:10px;height:10px;border-radius:50%;background:var(--dot);display:inline-block}}
.filter-btn .cnt{{background:rgba(0,0,0,.06);padding:2px 7px;border-radius:999px;font-size:.72rem}}
.filter-btn:hover{{border-color:var(--dot);background:#f1f5f9}}
.filter-btn.active{{border-color:var(--dot);box-shadow:0 0 0 2px color-mix(in srgb,var(--dot) 25%,transparent)}}
.filter-btn:not(.active){{opacity:.45}}

/* pair rows */
.pair-section{{padding:24px 36px}}
.pair-section h2{{font-size:1.3rem;font-weight:800;margin-bottom:14px;display:flex;align-items:center;gap:10px}}
.pair-section h2 .arrow-label{{color:var(--muted);font-weight:400;font-size:.9rem}}
.pair-row{{position:relative;display:flex;gap:0;min-height:200px;margin-bottom:20px}}
.pair-left,.pair-right{{flex:0 0 360px;z-index:2}}
.pair-mid{{flex:1;position:relative;min-width:200px}}
.pair-mid svg{{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none}}
.pair-mid svg path{{fill:none;stroke-width:1.6;opacity:.35;transition:opacity .15s,stroke-width .15s;pointer-events:stroke}}
.pair-mid svg path.highlight{{opacity:.85;stroke-width:3}}
.pair-mid svg path.dim{{opacity:.06}}
.pair-mid svg .arrow{{pointer-events:none;opacity:.55;transition:opacity .15s}}
.pair-mid svg .arrow.highlight{{opacity:.95}}
.pair-mid svg .arrow.dim{{opacity:.06}}

/* cards */
.node-card{{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden;width:360px}}
.node-head{{padding:14px 18px;display:flex;justify-content:space-between;align-items:center;background:#f8fafc;border-bottom:1px solid var(--line);cursor:pointer;user-select:none}}
.node-head h3{{font-size:1.05rem;font-weight:700}}
.tag{{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;padding:4px 10px;border-radius:999px}}
.tag-system{{background:#dbeafe;color:#1d4ed8}}
.tag-ecu{{background:#fce7f3;color:#be185d}}
.node-body{{padding:10px 14px;display:flex;flex-direction:column;gap:6px}}

.sub-card{{border-radius:12px;border:1px solid var(--line);overflow:hidden}}
.sub-head{{padding:8px 12px;font-size:.82rem;font-weight:700;display:flex;justify-content:space-between;align-items:center;cursor:pointer;user-select:none}}
.sub-head .kind{{font-size:.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}}
.device-sensor .sub-head{{background:#ecfdf5;border-bottom:1px solid #d1fae5}}
.device-actuator .sub-head{{background:#fffbeb;border-bottom:1px solid #fef3c7}}
.conn-card .sub-head{{background:#fdf2f8;border-bottom:1px solid #fce7f3}}
.sub-body{{padding:6px 10px;display:flex;flex-direction:column;gap:3px}}

.batch-row,.group-row{{display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:8px;font-size:.8rem;transition:background .12s;cursor:default;position:relative}}
.batch-row:hover,.group-row:hover{{background:#f1f5f9}}
.batch-row.highlight,.group-row.highlight{{background:#e0f2fe}}
.batch-dot,.group-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
.batch-label,.group-label{{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.batch-count,.group-count{{font-size:.72rem;font-weight:700;color:var(--muted);background:#f1f5f9;padding:2px 7px;border-radius:999px}}

/* network backbone */
.network-section{{padding:24px 36px;border-top:2px solid var(--line)}}
.network-section h2{{font-size:1.3rem;font-weight:800;margin-bottom:14px}}
.bus-lanes{{display:flex;flex-direction:column;gap:18px}}
.bus-lane{{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:18px;position:relative}}
.bus-lane-head{{display:flex;align-items:center;gap:10px;margin-bottom:12px}}
.bus-lane-head .bus-dot{{width:14px;height:14px;border-radius:50%}}
.bus-lane-head h3{{font-size:1rem;font-weight:700}}
.bus-lane-head .bus-count{{font-size:.78rem;color:var(--muted)}}
.bus-nodes{{display:flex;gap:16px;flex-wrap:wrap;align-items:center}}
.bus-ecu-node{{background:#f8fafc;border:1px solid var(--line);border-radius:12px;padding:10px 16px;display:flex;flex-direction:column;align-items:center;gap:4px;min-width:110px}}
.bus-ecu-node .ecu-name{{font-weight:700;font-size:.85rem}}
.bus-ecu-node .ecu-conn{{font-size:.72rem;color:var(--muted)}}
.bus-ecu-node .ecu-cnt{{font-size:.72rem;font-weight:700;color:var(--muted);background:#e0f2fe;padding:2px 8px;border-radius:999px}}
.bus-link-line{{flex:0 0 auto;display:flex;align-items:center;gap:0}}
.bus-link-line .seg{{height:3px;width:40px;border-radius:2px}}

/* tooltip */
.tooltip{{position:fixed;z-index:100;padding:10px 14px;border-radius:10px;background:#0f172a;color:#e2e8f0;font-size:.78rem;line-height:1.5;box-shadow:0 8px 24px rgba(0,0,0,.25);pointer-events:none;opacity:0;transition:opacity .15s;max-width:320px}}
.tooltip.show{{opacity:1}}
.tooltip strong{{color:#fff}}

/* legend */
.legend{{padding:14px 36px 28px;display:flex;gap:16px;flex-wrap:wrap;align-items:center;font-size:.78rem;color:var(--muted)}}
.legend-item{{display:flex;align-items:center;gap:5px}}
.legend-swatch{{width:28px;height:4px;border-radius:2px}}
</style>
</head>
<body>

<div class="header">
  <h1>{esc(arch_name)}</h1>
  <p>Signal flow organized by System / ECU pairs. I/O signals flow left to right.
  Bus interfaces (CAN, ETH) are shown in the network backbone below.
  Hover paths to inspect, click to lock, use filters to isolate interface types.</p>
</div>

<div class="summary">
  <div class="kpi"><div class="label">Systems</div><div class="val">{total_systems}</div></div>
  <div class="kpi"><div class="label">ECUs</div><div class="val">{total_ecus}</div></div>
  <div class="kpi"><div class="label">I/O signals</div><div class="val">{total_io_signals}</div></div>
  <div class="kpi"><div class="label">Bus signals</div><div class="val">{total_bus_signals}</div></div>
  <div class="kpi"><div class="label">Interfaces</div><div class="val">{total_ifaces}</div></div>
</div>

<div class="filters">
  <span class="filters-label">Filter</span>
        {filter_btns}
</div>

<div id="pairContainer"></div>

<div class="network-section">
  <h2>Network Backbone</h2>
  <div class="bus-lanes" id="busLanes"></div>
</div>

<div class="legend" id="legend">{legend_items}</div>
<div class="tooltip" id="tooltip"></div>

<script>
const PAIRS = {json.dumps(pairs)};
const ECU_IO = {json.dumps(ecu_io)};
const BUS_LINKS = {json.dumps(bus_links)};
const BUS_NET = {json.dumps(bus_net)};
const COLORS = {{"ANALOG": "#2563eb", "PWM": "#d97706", "DIGITAL": "#16a34a", "SENT": "#9333ea", "CAN": "#dc2626", "LIN": "#ea580c", "ETHERNET": "#0891b2", "POWER": "#64748b", "GROUND": "#334155"}};
const DEFAULT_COLOR = "#94a3b8";
function ifaceColor(i){{ return COLORS[i]||DEFAULT_COLOR; }}

let activeIfaces = new Set({json.dumps(all_ifaces)});
let lockedSignal = null;
const tooltip = document.getElementById("tooltip");

// ── Bezier helpers ───────────────────────────────────────────────
function bezPt(x0,y0,cx0,cy0,cx1,cy1,x1,y1,t){{
  const u=1-t;
  return [u*u*u*x0+3*u*u*t*cx0+3*u*t*t*cx1+t*t*t*x1,
          u*u*u*y0+3*u*u*t*cy0+3*u*t*t*cy1+t*t*t*y1];
}}
function bezTan(x0,y0,cx0,cy0,cx1,cy1,x1,y1,t){{
  const u=1-t;
  return [3*u*u*(cx0-x0)+6*u*t*(cx1-cx0)+3*t*t*(x1-cx1),
          3*u*u*(cy0-y0)+6*u*t*(cy1-cy0)+3*t*t*(y1-cy1)];
}}

function deviceClass(name){{
  const t=name.toUpperCase();
  if(t.includes("ACTUATOR"))return "device-actuator";
  return "device-sensor";
}}
function kindLabel(name){{
  const t=name.toUpperCase();
  if(t.includes("ACTUATOR"))return "Actuator";
  return "Sensor";
}}
function toggleBody(el){{
  const b=el.nextElementSibling;
  if(!b)return;
  b.style.display=b.style.display==="none"?"":"none";
  requestAnimationFrame(drawAll);
}}

// ── Build pair rows ──────────────────────────────────────────────
const container = document.getElementById("pairContainer");
const pairSvgs = [];

PAIRS.forEach((pair, pi) => {{
  const section = document.createElement("div");
  section.className = "pair-section";

  const ecuName = pair.primary_ecu;
  const ecuConns = ECU_IO[ecuName] || [];

  // section heading
  section.innerHTML = `<h2>${{pair.system}} <span class="arrow-label">&xrarr;</span> ${{ecuName}}</h2>`;

  const row = document.createElement("div");
  row.className = "pair-row";

  // LEFT: system devices (IO only)
  const left = document.createElement("div");
  left.className = "pair-left";
  const sysCard = document.createElement("div");
  sysCard.className = "node-card";
  let devHtml = "";
  pair.devices_io.forEach(dev => {{
    let bHtml = "";
    dev.batches.forEach(b => {{
      const c = ifaceColor(b.interface);
      const id = `L|${{pair.system}}|${{dev.name}}|${{b.prefix}}|${{b.interface}}`;
      bHtml += `<div class="batch-row" data-id="${{id}}" data-iface="${{b.interface}}" data-pair="${{pi}}">
        <span class="batch-dot" style="background:${{c}}"></span>
        <span class="batch-label">${{b.prefix}}</span>
        <span class="batch-count">${{b.signals.length}}</span></div>`;
    }});
    const dc = deviceClass(dev.name);
    devHtml += `<div class="sub-card ${{dc}}">
      <div class="sub-head" onclick="toggleBody(this)"><span>${{dev.name}}</span><span class="kind">${{kindLabel(dev.name)}}</span></div>
      <div class="sub-body">${{bHtml}}</div></div>`;
  }});
  sysCard.innerHTML = `<div class="node-head" onclick="toggleBody(this)"><h3>${{pair.system}}</h3><span class="tag tag-system">System</span></div><div class="node-body">${{devHtml}}</div>`;
  left.appendChild(sysCard);

  // MID: SVG
  const mid = document.createElement("div");
  mid.className = "pair-mid";
  const svg = document.createElementNS("http://www.w3.org/2000/svg","svg");
  svg.style.width = "100%";
  svg.style.height = "100%";
  mid.appendChild(svg);
  pairSvgs.push({{ svg, pairIdx: pi, row }});

  // RIGHT: ECU
  const right = document.createElement("div");
  right.className = "pair-right";
  const ecuCard = document.createElement("div");
  ecuCard.className = "node-card";
  let connHtml = "";
  ecuConns.forEach(conn => {{
    let gHtml = "";
    conn.groups.forEach(g => {{
      const c = ifaceColor(g.interface);
      const id = `R|${{ecuName}}|${{conn.name}}|${{g.interface}}`;
      gHtml += `<div class="group-row" data-id="${{id}}" data-iface="${{g.interface}}" data-pair="${{pi}}">
        <span class="group-dot" style="background:${{c}}"></span>
        <span class="group-label">${{g.interface}}</span>
        <span class="group-count">${{g.count}}</span></div>`;
    }});
    connHtml += `<div class="sub-card conn-card">
      <div class="sub-head" onclick="toggleBody(this)"><span>${{conn.name}}</span><span class="kind">Connector</span></div>
      <div class="sub-body">${{gHtml}}</div></div>`;
  }});
  ecuCard.innerHTML = `<div class="node-head" onclick="toggleBody(this)"><h3>${{ecuName}}</h3><span class="tag tag-ecu">ECU</span></div><div class="node-body">${{connHtml}}</div>`;
  right.appendChild(ecuCard);

  row.appendChild(left);
  row.appendChild(mid);
  row.appendChild(right);
  section.appendChild(row);
  container.appendChild(section);
}});

// ── Build network backbone ───────────────────────────────────────
const busLanes = document.getElementById("busLanes");
Object.entries(BUS_NET).sort().forEach(([iface, endpoints]) => {{
  const lane = document.createElement("div");
  lane.className = "bus-lane";
  const col = ifaceColor(iface);
  const totalSigs = endpoints.reduce((s,e)=>s+e.count,0);
  let nodesHtml = "";
  endpoints.forEach((ep, i) => {{
    if (i > 0) nodesHtml += `<div class="bus-link-line"><div class="seg" style="background:${{col}}"></div><div class="seg" style="background:${{col}}"></div></div>`;
    nodesHtml += `<div class="bus-ecu-node">
      <span class="ecu-name">${{ep.ecu}}</span>
      <span class="ecu-conn">${{ep.connector}}</span>
      <span class="ecu-cnt">${{ep.count}} ch</span></div>`;
  }});
  lane.innerHTML = `<div class="bus-lane-head">
    <span class="bus-dot" style="background:${{col}}"></span>
    <h3>${{iface}} Bus</h3>
    <span class="bus-count">${{totalSigs}} channels across ${{endpoints.length}} ECU(s)</span>
  </div><div class="bus-nodes">${{nodesHtml}}</div>`;
  busLanes.appendChild(lane);
}});

// ── Draw SVG paths per pair ──────────────────────────────────────
function drawAll() {{
  pairSvgs.forEach(ps => {{
    const svg = ps.svg;
    const row = ps.row;
    const pi = ps.pairIdx;
    const pair = PAIRS[pi];
    const rowRect = row.getBoundingClientRect();

    // anchors within this row
    const anchors = {{}};
    row.querySelectorAll(".batch-row,.group-row").forEach(el => {{
      const r = el.getBoundingClientRect();
      const id = el.dataset.id;
      const isLeft = id.startsWith("L");
      anchors[id] = {{
        x: r.left - rowRect.left + (isLeft ? r.width : 0),
        y: r.top - rowRect.top + r.height/2,
        visible: el.offsetParent !== null,
      }};
    }});

    // group IO links for this pair
    const grouped = {{}};
    pair.io_links.forEach(link => {{
      const lid = `L|${{link.system}}|${{link.device}}|${{link.batch}}|${{link.interface}}`;
      const rid = `R|${{link.ecu}}|${{link.connector}}|${{link.interface}}`;
      const key = `${{lid}}:::${{rid}}`;
      if (!grouped[key]) grouped[key] = {{lid,rid,iface:link.interface,signals:[]}};
      grouped[key].signals.push(link.signal);
    }});

    let html = "";
    const midW = svg.parentElement.getBoundingClientRect().width;
    Object.values(grouped).forEach(g => {{
      const la = anchors[g.lid];
      const ra = anchors[g.rid];
      if (!la||!ra||!la.visible||!ra.visible) return;
      const show = activeIfaces.has(g.iface);
      const w = Math.max(1.2, Math.min(g.signals.length*0.6, 8));
      const x0 = la.x - svg.parentElement.getBoundingClientRect().left + rowRect.left;
      const x1 = ra.x - svg.parentElement.getBoundingClientRect().left + rowRect.left;
      const y0 = la.y;
      const y1 = ra.y;
      const cpx0 = x0 + midW*0.35;
      const cpx1 = x1 - midW*0.35;
      const d = `M${{x0}},${{y0}} C${{cpx0}},${{y0}} ${{cpx1}},${{y1}} ${{x1}},${{y1}}`;
      const cls = show?"":"dim";
      const col = ifaceColor(g.iface);
      html += `<path class="${{cls}}" d="${{d}}" stroke="${{col}}" stroke-width="${{w}}"
        data-iface="${{g.iface}}" data-lid="${{g.lid}}" data-rid="${{g.rid}}"
        data-signals="${{g.signals.join(",")}}" data-count="${{g.signals.length}}" data-pair="${{pi}}" />`;
      // arrowhead at t=0.55
      const [mx,my] = bezPt(x0,y0,cpx0,y0,cpx1,y1,x1,y1, 0.55);
      const [tx,ty] = bezTan(x0,y0,cpx0,y0,cpx1,y1,x1,y1, 0.55);
      const ang = Math.atan2(ty,tx)*180/Math.PI;
      const sz = Math.max(5, w*1.6);
      html += `<polygon class="arrow ${{cls}}" fill="${{col}}"
        points="0,${{-sz/2}} ${{sz}},0 0,${{sz/2}}"
        transform="translate(${{mx}},${{my}}) rotate(${{ang}})"
        data-iface="${{g.iface}}" data-lid="${{g.lid}}" data-rid="${{g.rid}}" data-pair="${{pi}}" />`;
    }});

    svg.setAttribute("width", row.scrollWidth);
    svg.setAttribute("height", row.scrollHeight);
    svg.style.width = row.scrollWidth+"px";
    svg.style.height = row.scrollHeight+"px";
    svg.innerHTML = html;

    // hover events
    svg.querySelectorAll("path").forEach(p => {{
      p.style.pointerEvents = "stroke";
      p.addEventListener("mouseenter", onEnter);
      p.addEventListener("mouseleave", onLeave);
      p.addEventListener("click", onClick);
    }});
  }});
}}

// ── Interaction ──────────────────────────────────────────────────
function onEnter(e){{ if(lockedSignal)return; hlPath(e.target,true); showTip(e,e.target); }}
function onLeave(e){{ if(lockedSignal)return; hlPath(e.target,false); hideTip(); }}
function onClick(e){{
  const p=e.target;
  if(lockedSignal===p){{ lockedSignal=null; hlPath(p,false); hideTip(); }}
  else {{ if(lockedSignal)hlPath(lockedSignal,false); lockedSignal=p; hlPath(p,true); showTip(e,p); }}
}}
function hlPath(pathEl,on){{
  pathEl.classList.toggle("highlight",on);
  const lid=pathEl.dataset.lid, rid=pathEl.dataset.rid, pi=pathEl.dataset.pair;
  // highlight matching anchors
  document.querySelectorAll(".batch-row,.group-row").forEach(el=>{{
    el.classList.toggle("highlight",on&&(el.dataset.id===lid||el.dataset.id===rid));
  }});
  // dim/undim all paths+arrows in same pair
  const svg = pathEl.closest("svg");
  if(svg){{
    svg.querySelectorAll("path,.arrow").forEach(p=>{{
      if(p!==pathEl) p.classList.toggle("dim",on);
    }});
    svg.querySelectorAll(".arrow").forEach(a=>{{
      if(a.dataset.lid===lid&&a.dataset.rid===rid) a.classList.toggle("highlight",on);
    }});
  }}
  if(!on && svg){{
    svg.querySelectorAll("path,.arrow").forEach(p=>{{
      p.classList.toggle("dim",!activeIfaces.has(p.dataset.iface));
    }});
  }}
}}
function showTip(e,el){{
  const sigs=el.dataset.signals.split(",");
  const iface=el.dataset.iface;
  const lid=el.dataset.lid.split("|"), rid=el.dataset.rid.split("|");
  const preview=sigs.slice(0,6).join(", ")+(sigs.length>6?` ... (+${{sigs.length-6}})`:"");
  tooltip.innerHTML=`<strong>${{iface}}</strong> &middot; ${{sigs.length}} signal(s)<br>
    <strong>From:</strong> ${{lid[1]}} / ${{lid[2]}} / ${{lid[3]}}<br>
    <strong>To:</strong> ${{rid[1]}} / ${{rid[2]}}<br>
    <span style="color:#94a3b8">${{preview}}</span>`;
  tooltip.classList.add("show");
  posTip(e);
}}
function posTip(e){{
  let x=e.clientX+14,y=e.clientY+14;
  const r=tooltip.getBoundingClientRect();
  if(x+r.width>window.innerWidth)x=e.clientX-r.width-14;
  if(y+r.height>window.innerHeight)y=e.clientY-r.height-14;
  tooltip.style.left=x+"px"; tooltip.style.top=y+"px";
}}
function hideTip(){{ tooltip.classList.remove("show"); }}
document.addEventListener("mousemove",e=>{{ if(tooltip.classList.contains("show"))posTip(e); }});

// ── Filters ──────────────────────────────────────────────────────
document.querySelectorAll(".filter-btn").forEach(btn=>{{
  btn.addEventListener("click",()=>{{
    const i=btn.dataset.iface;
    if(activeIfaces.has(i)){{ activeIfaces.delete(i);btn.classList.remove("active"); }}
    else {{ activeIfaces.add(i);btn.classList.add("active"); }}
    drawAll();
  }});
}});

// ── Legend ────────────────────────────────────────────────────────
const legend=document.getElementById("legend");

// ── Init ─────────────────────────────────────────────────────────
requestAnimationFrame(drawAll);
window.addEventListener("resize",()=>requestAnimationFrame(drawAll));
document.addEventListener("keydown",e=>{{
  if(e.key==="Escape"&&lockedSignal){{ hlPath(lockedSignal,false);lockedSignal=null;hideTip(); }}
}});
</script>
</body>
</html>"""

    return html


def main() -> int:
    parser = standard_arg_parser(
        "Generate interactive signal flow diagram showing system-to-ECU signal routing."
    )
    args = parser.parse_args()
    root = resolve_root(args.root)
    cfg = load_config(Path(args.config) if args.config else None)
    src, arch = load_architecture_from_args(args, cfg, physical=False)

    if not arch:
        print("[ERROR] Could not load architecture")
        return 1

    # Build signal flow data
    data = build_signal_flow_data(arch)

    # Generate HTML
    html = generate_html(data, arch, src)

    # Write output
    outfile = get_output_file(root, cfg, "signal_flow", args.output, args.outdir)
    write_text(outfile, html)
    print(outfile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
