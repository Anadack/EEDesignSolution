#!/usr/bin/env python3
"""Generate an interactive signal-flow diagram with paired System/ECU rows
and a network backbone section for CAN/ETH bus interfaces.

Layout:
  - Each System is placed in a row next to its primary ECU
  - Sensor/Actuator batches (I/O signals) flow left-to-right via SVG bezier
  - Bus interfaces (CAN, ETH, LIN) are extracted into a horizontal network
    backbone section at the bottom, showing which ECUs share bus segments
  - Direction arrowheads on every path

No external JS/CSS libraries required.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from html_overflow_guard import OVERFLOW_GUARD_CSS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def esc(v: Any) -> str:
    return str("" if v is None else v).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def load_json(p: Path) -> dict[str, Any]:
    d = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(d, dict): raise ValueError("Top-level JSON must be an object")
    return d

def find_base() -> Path:
    s = Path(__file__).resolve().parent
    return s.parent if (s.parent / "exports").exists() else s

def get_arch(data: dict[str, Any]) -> dict[str, Any]:
    a = data.get("architecture", data)
    if not isinstance(a, dict): raise ValueError("architecture must be an object")
    return a

IFACE_COLORS = {
    "ANALOG":"#2563eb","PWM":"#d97706","DIGITAL":"#16a34a","SENT":"#9333ea",
    "CAN":"#dc2626","LIN":"#ea580c","ETHERNET":"#0891b2","POWER":"#64748b","GROUND":"#334155",
}
DEFAULT_COLOR = "#94a3b8"
BUS_IFACES = {"CAN","LIN","ETHERNET"}

def iface_color(i: str) -> str: return IFACE_COLORS.get(i.upper(), DEFAULT_COLOR)
def strip_digits(n: str) -> str: return re.sub(r"_\d+$", "", n)

# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def extract(arch: dict[str, Any]):
    sig_to_ecu: dict[str, dict] = {}
    ecu_conn_groups: dict[str, dict[str, dict[str, list[str]]]] = {}

    for ecu in arch.get("ecus", []):
        if not isinstance(ecu, dict): continue
        en = str(ecu.get("name","ECU"))
        for pin in ecu.get("pins", []):
            if not isinstance(pin, dict): continue
            sig = pin.get("signal")
            if not isinstance(sig, dict) or not sig.get("name"): continue
            sn = str(sig["name"])
            conn = str(pin.get("connector","X?"))
            iface = str(sig.get("interface_type", pin.get("type","?")))
            sig_to_ecu[sn] = {"ecu":en,"connector":conn,"pin":str(pin.get("physical_number","")),"interface":iface}
            ecu_conn_groups.setdefault(en,{}).setdefault(conn,{}).setdefault(iface,[]).append(sn)

    # Build system info, links, separate bus vs io
    pairs: list[dict[str, Any]] = []  # [{system, devices_io, primary_ecu, io_links}]
    bus_links: list[dict] = []
    iface_counts: dict[str, int] = defaultdict(int)

    for system in arch.get("systems", []):
        if not isinstance(system, dict): continue
        sys_name = str(system.get("name","System"))
        devices_io = []
        devices_bus = []
        io_links = []

        for device in system.get("devices", []):
            if not isinstance(device, dict): continue
            dn = str(device.get("name","Device"))
            dt = str(device.get("type","UNKNOWN"))
            batches: dict[str, dict] = {}
            for pin in device.get("pins", []):
                if not isinstance(pin, dict): continue
                sig = pin.get("signal")
                if not isinstance(sig, dict) or not sig.get("name"): continue
                sn = str(sig["name"])
                prefix = strip_digits(sn)
                ei = sig_to_ecu.get(sn, {})
                iface = str(sig.get("interface_type") or ei.get("interface") or pin.get("type") or "?")
                role = str(pin.get("role","?"))
                key = f"{prefix}|{iface}"
                if key not in batches:
                    batches[key] = {"prefix":prefix,"interface":iface,"role":role,"signals":[]}
                batches[key]["signals"].append(sn)
                iface_counts[iface] += 1

            bl = sorted(batches.values(), key=lambda b: b["prefix"])
            is_bus = all(b["interface"] in BUS_IFACES for b in bl) and bl
            dev_entry = {"name":dn,"type":dt,"batches":bl}
            if is_bus:
                devices_bus.append(dev_entry)
            else:
                devices_io.append(dev_entry)

            for b in bl:
                for sn in b["signals"]:
                    t = sig_to_ecu.get(sn)
                    if not t: continue
                    link = {"signal":sn,"system":sys_name,"device":dn,
                            "batch":b["prefix"],"interface":b["interface"],
                            "ecu":t["ecu"],"connector":t["connector"],"ecu_pin":t["pin"]}
                    if b["interface"] in BUS_IFACES:
                        bus_links.append(link)
                    else:
                        io_links.append(link)

        # find primary ECU (majority vote from io links)
        ecu_votes = Counter(l["ecu"] for l in io_links)
        primary_ecu = ecu_votes.most_common(1)[0][0] if ecu_votes else ""

        pairs.append({
            "system": sys_name,
            "devices_io": devices_io,
            "devices_bus": devices_bus,
            "primary_ecu": primary_ecu,
            "io_links": io_links,
        })

    # Right-side ECU data (only IO groups, bus groups separate)
    ecu_io: dict[str, list[dict]] = {}
    for en, conns in ecu_conn_groups.items():
        cl = []
        for cn in sorted(conns):
            groups = []
            for iname in sorted(conns[cn]):
                if iname in BUS_IFACES: continue
                groups.append({"interface":iname,"count":len(conns[cn][iname]),"signals":conns[cn][iname]})
            if groups:
                cl.append({"name":cn,"groups":groups})
        ecu_io[en] = cl

    # Bus network: per bus type → list of ECU endpoints
    bus_network: dict[str, list[dict]] = defaultdict(list)
    for en, conns in ecu_conn_groups.items():
        for cn in sorted(conns):
            for iname in sorted(conns[cn]):
                if iname not in BUS_IFACES: continue
                sigs = conns[cn][iname]
                bus_network[iname].append({"ecu":en,"connector":cn,"count":len(sigs),"signals":sigs})

    return pairs, ecu_io, bus_links, dict(bus_network), dict(iface_counts)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def build_html(arch_name, pairs, ecu_io, bus_links, bus_network, iface_counts):
    total_io = sum(len(p["io_links"]) for p in pairs)
    total_bus = len(bus_links)
    interfaces = sorted(iface_counts.keys())
    colors_json = json.dumps(IFACE_COLORS)
    pairs_json = json.dumps(pairs)
    ecu_io_json = json.dumps(ecu_io)
    bus_links_json = json.dumps(bus_links)
    bus_network_json = json.dumps(bus_network)

    filter_buttons = "\n".join(
        f'        <button class="filter-btn active" data-iface="{esc(i)}" '
        f'style="--dot:{iface_color(i)}">'
        f'<span class="dot"></span>{esc(i)} '
        f'<span class="cnt">{iface_counts[i]}</span></button>'
        for i in interfaces
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>{esc(arch_name)} - Signal Flow</title>
<style>
:root{{
  --bg:#070b12;--surface0:#0b1018;--surface1:#0f1622;--surface2:#151e2e;
  --surface3:#1d2939;--surface4:#273548;--border0:#1a2436;--border1:#233149;
  --border2:#2d3e5c;--text:#cfdaea;--text-dim:#6c83a2;--text-fade:#46566e;
  --cyan:#2ee6ff;--green:#2ee6a0;--amber:#ffb43d;--red:#ff5a78;
  --purple:#b388ff;--teal:#19d6c0;--blue:#5aa6ff;
  --accent:var(--cyan);--ok:var(--green);--warn:var(--amber);--err:var(--red);
  --ink:var(--text);--muted:var(--text-dim);--panel:var(--surface1);
  --line:var(--border1);--radius:16px;--shadow:0 8px 30px rgba(0,0,0,.45);
  font-family:Aptos,"Segoe UI Variable","Inter",system-ui,sans-serif;
  color:var(--text);
}}
*{{box-sizing:border-box;margin:0}}
body{{background:var(--bg);color:var(--text);padding:0}}

/* header */
.header{{background:linear-gradient(135deg,var(--surface2),var(--surface3));color:var(--text);padding:32px 36px}}
.header h1{{font-size:clamp(1.6rem,3.5vw,2.8rem);letter-spacing:-.03em;font-weight:800}}
.header p{{color:var(--text-dim);margin-top:8px;max-width:80ch}}

/* summary */
.summary{{display:flex;gap:14px;padding:18px 36px;overflow-x:auto;background:var(--panel);border-bottom:1px solid var(--line)}}
.kpi{{flex:0 0 auto;padding:14px 20px;border-radius:14px;background:var(--surface2);border:1px solid var(--border1);min-width:130px}}
.kpi .label{{font-size:.75rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}}
.kpi .val{{font-size:1.8rem;font-weight:800;margin-top:4px}}

/* filters */
.filters{{display:flex;gap:8px;flex-wrap:wrap;padding:14px 36px;background:var(--panel);border-bottom:1px solid var(--line);align-items:center}}
.filters-label{{font-size:.82rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-right:6px}}
.filter-btn{{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:999px;border:1.5px solid var(--border1);background:var(--surface2);cursor:pointer;font-size:.82rem;font-weight:600;color:var(--text);transition:all .15s}}
.filter-btn .dot{{width:10px;height:10px;border-radius:50%;background:var(--dot);display:inline-block}}
.filter-btn .cnt{{background:rgba(255,255,255,.06);padding:2px 7px;border-radius:999px;font-size:.72rem}}
.filter-btn:hover{{border-color:var(--dot);background:var(--surface3)}}
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
.node-card{{background:var(--surface1);border:1px solid var(--border1);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden;width:360px}}
.node-head{{padding:14px 18px;display:flex;justify-content:space-between;align-items:center;background:var(--surface3);border-bottom:1px solid var(--border1);cursor:pointer;user-select:none}}
.node-head h3{{font-size:1.05rem;font-weight:700}}
.tag{{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;padding:4px 10px;border-radius:999px}}
.tag-system{{background:rgba(46,230,255,0.12);color:var(--cyan)}}
.tag-ecu{{background:rgba(179,136,255,0.12);color:var(--purple)}}
.node-body{{padding:10px 14px;display:flex;flex-direction:column;gap:6px}}

.sub-card{{border-radius:12px;border:1px solid var(--line);overflow:hidden}}
.sub-head{{padding:8px 12px;font-size:.82rem;font-weight:700;display:flex;justify-content:space-between;align-items:center;cursor:pointer;user-select:none}}
.sub-head .kind{{font-size:.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}}
.device-sensor .sub-head{{background:rgba(46,230,160,0.08);border-bottom:1px solid var(--border1)}}
.device-actuator .sub-head{{background:rgba(255,180,61,0.08);border-bottom:1px solid var(--border1)}}
.conn-card .sub-head{{background:rgba(179,136,255,0.08);border-bottom:1px solid var(--border1)}}
.sub-body{{padding:6px 10px;display:flex;flex-direction:column;gap:3px}}

.batch-row,.group-row{{display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:8px;font-size:.8rem;transition:background .12s;cursor:default;position:relative}}
.batch-row:hover,.group-row:hover{{background:var(--surface3)}}
.batch-row.highlight,.group-row.highlight{{background:var(--surface4)}}
.batch-dot,.group-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
.batch-label,.group-label{{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.batch-count,.group-count{{font-size:.72rem;font-weight:700;color:var(--text-dim);background:var(--surface3);padding:2px 7px;border-radius:999px}}

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
.bus-ecu-node{{background:var(--surface2);border:1px solid var(--border1);border-radius:12px;padding:10px 16px;display:flex;flex-direction:column;align-items:center;gap:4px;min-width:110px}}
.bus-ecu-node .ecu-name{{font-weight:700;font-size:.85rem}}
.bus-ecu-node .ecu-conn{{font-size:.72rem;color:var(--muted)}}
.bus-ecu-node .ecu-cnt{{font-size:.72rem;font-weight:700;color:var(--text-dim);background:var(--surface3);padding:2px 8px;border-radius:999px}}
.bus-link-line{{flex:0 0 auto;display:flex;align-items:center;gap:0}}
.bus-link-line .seg{{height:3px;width:40px;border-radius:2px}}

/* tooltip */
.tooltip{{position:fixed;z-index:100;padding:10px 14px;border-radius:10px;background:var(--surface3);color:var(--text);font-size:.78rem;line-height:1.5;box-shadow:var(--shadow);pointer-events:none;opacity:0;transition:opacity .15s;max-width:320px}}
.tooltip.show{{opacity:1}}
.tooltip strong{{color:#fff}}

/* legend */
.legend{{padding:14px 36px 28px;display:flex;gap:16px;flex-wrap:wrap;align-items:center;font-size:.78rem;color:var(--muted)}}
.legend-item{{display:flex;align-items:center;gap:5px}}
.legend-swatch{{width:28px;height:4px;border-radius:2px}}
{OVERFLOW_GUARD_CSS}
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
  <div class="kpi"><div class="label">Systems</div><div class="val">{len(pairs)}</div></div>
  <div class="kpi"><div class="label">ECUs</div><div class="val">{len(ecu_io)}</div></div>
  <div class="kpi"><div class="label">I/O signals</div><div class="val">{total_io}</div></div>
  <div class="kpi"><div class="label">Bus signals</div><div class="val">{total_bus}</div></div>
  <div class="kpi"><div class="label">Interfaces</div><div class="val">{len(interfaces)}</div></div>
</div>

<div class="filters">
  <span class="filters-label">Filter</span>
{filter_buttons}
</div>

<div id="pairContainer"></div>

<div class="network-section">
  <h2>Network Backbone</h2>
  <div class="bus-lanes" id="busLanes"></div>
</div>

<div class="legend" id="legend"></div>
<div class="tooltip" id="tooltip"></div>

<script>
const PAIRS = {pairs_json};
const ECU_IO = {ecu_io_json};
const BUS_LINKS = {bus_links_json};
const BUS_NET = {bus_network_json};
const COLORS = {colors_json};
const DEFAULT_COLOR = "{DEFAULT_COLOR}";
function ifaceColor(i){{ return COLORS[i]||DEFAULT_COLOR; }}

let activeIfaces = new Set({json.dumps(interfaces)});
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
Object.entries(COLORS).forEach(([n,c])=>{{
  legend.innerHTML+=`<span class="legend-item"><span class="legend-swatch" style="background:${{c}}"></span>${{n}}</span>`;
}});

// ── Init ─────────────────────────────────────────────────────────
requestAnimationFrame(drawAll);
window.addEventListener("resize",()=>requestAnimationFrame(drawAll));
document.addEventListener("keydown",e=>{{
  if(e.key==="Escape"&&lockedSignal){{ hlPath(lockedSignal,false);lockedSignal=null;hideTip(); }}
}});
</script>
</body>
</html>"""


def main() -> None:
    base = find_base()
    json_path = base / "exports" / "example_architecture.json"
    if not json_path.exists():
        json_path = base / "exports" / "example_physical_architecture.json"
    if not json_path.exists():
        raise SystemExit(f"Missing file: {json_path}")
    output_path = base / "exports" / "architecture_signal_flow_v2.html"

    arch = get_arch(load_json(json_path))
    pairs, ecu_io, bus_links, bus_network, iface_counts = extract(arch)
    html = build_html(str(arch.get("name","Architecture")), pairs, ecu_io, bus_links, bus_network, iface_counts)
    output_path.write_text(html, encoding="utf-8")
    print(f"[OK] {output_path}  ({sum(len(p['io_links']) for p in pairs)} I/O + {len(bus_links)} bus = {sum(len(p['io_links']) for p in pairs)+len(bus_links)} signals, {len(iface_counts)} interface types)")


if __name__ == "__main__":
    main()
