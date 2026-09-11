#!/usr/bin/env python3
"""Bus backbone diagram – fully generic.

Reads the exported JSON and automatically discovers all ECUs, interface types,
and connections.  No hardcoded bus list: if main.c adds new ECUs, signals, or
interface types the diagram updates without any script change.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from html_overflow_guard import OVERFLOW_GUARD_CSS

# ── Interface types that are infrastructure, not routable buses/signals ──
_EXCLUDED_INTERFACES: set[str] = {"POWER", "GROUND", "RESERVED"}

# ── Colour palette – known types first, then a rotating fallback palette ──
_KNOWN_COLORS: dict[str, str] = {
    "CAN":      "#d92d20",
    "LIN":      "#2563eb",
    "ETHERNET": "#0f766e",
    "SENT":     "#7c3aed",
    "DIGITAL":  "#c2410c",
    "ANALOG":   "#0369a1",
    "PWM":      "#9333ea",
}
_FALLBACK_PALETTE: list[str] = [
    "#b91c1c", "#1d4ed8", "#047857", "#7e22ce",
    "#b45309", "#0f766e", "#be185d", "#4338ca",
]

# ── Known bus/interface properties (informational) ──
_KNOWN_PROPS: dict[str, dict[str, str]] = {
    "CAN":      {"protocol": "CAN 2.0B / FD", "speed": "250 – 500 kbit/s", "topology": "Multi-drop"},
    "LIN":      {"protocol": "LIN 2.1",       "speed": "19.2 kbit/s",      "topology": "Single-master"},
    "ETHERNET": {"protocol": "100BASE-T1",     "speed": "100 Mbit/s",       "topology": "Point-to-point"},
    "SENT":     {"protocol": "SAE J2716",      "speed": "Tick-based",       "topology": "Point-to-point"},
}


def _color_for(iface: str, _cache: dict[str, str] = {}) -> str:  # noqa: B006
    """Return a stable colour for *iface*, auto-assigning from the palette."""
    if iface not in _cache:
        if iface in _KNOWN_COLORS:
            _cache[iface] = _KNOWN_COLORS[iface]
        else:
            idx = len(_cache) % len(_FALLBACK_PALETTE)
            _cache[iface] = _FALLBACK_PALETTE[idx]
    return _cache[iface]


def esc(value: Any) -> str:
    return (
        str("" if value is None else value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Top-level JSON must be an object")
    return data


def find_base() -> Path:
    script_dir = Path(__file__).resolve().parent
    if (script_dir.parent / "exports").exists():
        return script_dir.parent
    return script_dir


def get_architecture(data: dict[str, Any]) -> dict[str, Any]:
    arch = data.get("architecture", data)
    if not isinstance(arch, dict):
        raise ValueError("architecture must be an object")
    return arch


# ── Data extraction ─────────────────────────────────────────────────────

def build_topology_from_buses(arch: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    """Build (ecus, lanes) directly from arch['buses'] — authoritative topology.

    Returns None when no buses[] is present so callers can fall back to
    pin-based inference.  Using buses[] avoids counting differential pin
    pairs (CAN_H / CAN_L) as two separate bus signals.
    """
    from collections import defaultdict
    raw_buses = arch.get("buses", [])
    if not isinstance(raw_buses, list) or not raw_buses:
        return None

    ecu_bus_map: dict[str, dict[str, Any]] = defaultdict(dict)
    lanes: list[dict[str, Any]] = []

    for bus in raw_buses:
        if not isinstance(bus, dict):
            continue
        bname = str(bus.get("name", ""))
        btype = str(bus.get("type", bus.get("bus_type", ""))).upper()
        if not btype or btype in _EXCLUDED_INTERFACES or not bname:
            continue
        bitrate = int(bus.get("bitrate", 0) or 0)
        signals = [str(s) for s in (bus.get("signals") or []) if s]

        connected: list[str] = []
        for node in (bus.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            ename = str(node.get("ecu", ""))
            if not ename:
                continue
            connected.append(ename)
            ecu_bus_map[ename][bname] = {
                "signal_count": len(signals),
                "signals": signals[:30],
                "bus_type": btype,
            }

        bitrate_str = (f"{bitrate // 1000} kbit/s" if bitrate and bitrate < 1_000_000
                       else f"{bitrate // 1_000_000} Mbit/s" if bitrate >= 1_000_000 else "")
        props = dict(_KNOWN_PROPS.get(btype, {}))
        if bitrate_str:
            props["bitrate"] = bitrate_str
        lanes.append({
            "name": bname,
            "bus_type": btype,
            "color": _color_for(btype),
            "props": props,
            "connected_ecus": connected,
            "signal_count": len(signals),
        })

    if not lanes:
        return None

    ecus_result: list[dict[str, Any]] = []
    for ecu in (arch.get("ecus") or []):
        if not isinstance(ecu, dict):
            continue
        name = str(ecu.get("name", "ECU"))
        pins = ecu.get("pins") or []
        occupied = sum(1 for p in pins if isinstance(p, dict) and p.get("is_occupied"))
        ecus_result.append({
            "name": name,
            "variant": str(ecu.get("variant", "")),
            "can_addresses": [str(a) for a in (ecu.get("can_addresses") or []) if a],
            "buses": ecu_bus_map.get(name, {}),
            "total_pins": len(pins),
            "occupied_pins": occupied,
        })
    return ecus_result, lanes


def extract_ecus(arch: dict[str, Any]) -> list[dict[str, Any]]:
    """Fallback: infer ECU bus participation from pin interface types.

    Used only when arch['buses'] is absent.  Counts interface types not
    named buses — callers should prefer build_topology_from_buses().
    """
    result: list[dict[str, Any]] = []
    ecus = arch.get("ecus", [])
    if not isinstance(ecus, list):
        return result
    for ecu in ecus:
        if not isinstance(ecu, dict):
            continue
        name = str(ecu.get("name", "ECU"))
        variant = str(ecu.get("variant", ""))
        addresses = ecu.get("can_addresses", [])
        if not isinstance(addresses, list):
            addresses = []
        pins = ecu.get("pins", [])
        if not isinstance(pins, list):
            pins = []
        buses: dict[str, dict[str, Any]] = {}
        total = len(pins)
        occupied = 0
        for pin in pins:
            if not isinstance(pin, dict):
                continue
            if pin.get("is_occupied"):
                occupied += 1
            signal = pin.get("signal")
            iface = str(pin.get("type", ""))
            sig_name = ""
            if isinstance(signal, dict):
                iface = str(signal.get("interface_type", iface))
                sig_name = str(signal.get("name", ""))
            if not iface or iface in _EXCLUDED_INTERFACES:
                continue
            entry = buses.setdefault(iface, {"signal_count": 0, "signals": []})
            entry["signal_count"] += 1
            if sig_name:
                entry["signals"].append(sig_name)
        result.append({
            "name": name,
            "variant": variant,
            "can_addresses": [str(a) for a in addresses],
            "buses": buses,
            "total_pins": total,
            "occupied_pins": occupied,
        })
    return result


def extract_bus_lanes(ecus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build one lane per interface type that has at least one connected ECU.

    The list of types is discovered from *ecus* – nothing hardcoded.
    """
    # Collect every interface type that appears across all ECUs
    all_types: list[str] = []
    seen: set[str] = set()
    for ecu in ecus:
        for bus in ecu["buses"]:
            if bus not in seen:
                seen.add(bus)
                all_types.append(bus)

    lanes: list[dict[str, Any]] = []
    for bus in all_types:
        connected = [e["name"] for e in ecus if bus in e["buses"]]
        total_signals = sum(e["buses"].get(bus, {}).get("signal_count", 0) for e in ecus)
        if not connected:
            continue
        lanes.append({
            "name": bus,
            "color": _color_for(bus),
            "props": _KNOWN_PROPS.get(bus, {}),
            "connected_ecus": connected,
            "signal_count": total_signals,
        })
    return lanes


# ── HTML rendering ──────────────────────────────────────────────────────

def render_ecu_card(ecu: dict[str, Any], idx: int) -> str:
    addr_html = ""
    if ecu["can_addresses"]:
        chips = "".join(
            f'<span class="addr-chip">{esc(a)}</span>' for a in ecu["can_addresses"]
        )
        addr_html = f'<div class="ecu-addr"><span class="addr-label">CAN addr</span>{chips}</div>'
    bus_chips = "".join(
        f'<span class="bus-chip" style="--bc:{_color_for(d.get("bus_type", b))}">'
        f'{esc(b)} ({d["signal_count"]})</span>'
        for b, d in ecu["buses"].items()
    )
    alloc = 0
    if ecu["total_pins"]:
        alloc = round(ecu["occupied_pins"] / ecu["total_pins"] * 100)
    return f"""
      <article class="ecu-card" data-ecu="{esc(ecu['name'])}" id="ecu-{idx}">
        <div class="ecu-header">
          <div class="ecu-name">{esc(ecu['name'])}</div>
          <span class="ecu-variant">{esc(ecu['variant'])}</span>
        </div>
        {addr_html}
        <div class="ecu-buses">{bus_chips}</div>
        <div class="ecu-alloc">{ecu['occupied_pins']}/{ecu['total_pins']} pins ({alloc}%)</div>
      </article>"""


def render_bus_lane(lane: dict[str, Any], idx: int) -> str:
    props = lane["props"]
    prop_chips = ""
    for key, val in props.items():
        if val:
            prop_chips += f'<span class="prop-chip">{esc(key)}: {esc(val)}</span>'
    return f"""
      <div class="bus-lane" id="bus-{idx}" data-bus="{esc(lane['name'])}"
           style="--bc:{lane['color']};">
        <div class="bus-label">
          <span class="bus-badge">{esc(lane['name'])}</span>
          <span class="bus-sig-count">{lane['signal_count']} signals &middot; {len(lane['connected_ecus'])} ECU(s)</span>
        </div>
        <div class="bus-line-wrap">
          <div class="bus-backbone-line"></div>
        </div>
        <div class="bus-props">{prop_chips}</div>
      </div>"""


def build_html(arch_name: str, ecus: list[dict[str, Any]],
               lanes: list[dict[str, Any]]) -> str:
    ecu_cards = "\n".join(render_ecu_card(e, i) for i, e in enumerate(ecus))
    bus_lanes_html = "\n".join(render_bus_lane(l, i) for i, l in enumerate(lanes))
    if not ecu_cards:
        ecu_cards = '<div class="empty-panel">No ECUs found.</div>'
    if not bus_lanes_html:
        bus_lanes_html = '<div class="empty-panel">No bus interfaces detected.</div>'

    # Build connection data for JS
    connections: list[dict[str, Any]] = []
    for ei, ecu in enumerate(ecus):
        for li, lane in enumerate(lanes):
            if lane["name"] in ecu["buses"]:
                connections.append({
                    "ecuIdx": ei,
                    "busIdx": li,
                    "bus": lane["name"],
                    "count": ecu["buses"][lane["name"]]["signal_count"],
                })
    conn_json = json.dumps(connections)

    # Build colour map from lanes (fully dynamic)
    color_map = {lane["name"]: lane["color"] for lane in lanes}
    color_json = json.dumps(color_map)

    total_ecus = len(ecus)
    total_buses = len(lanes)
    total_signals = sum(l["signal_count"] for l in lanes)
    total_connections = len(connections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(arch_name)} &ndash; Bus Backbone</title>
  <style>
    :root {{ --bg:#070b12; --surface0:#0b1018; --surface1:#0f1622; --surface2:#151e2e;
             --surface3:#1d2939; --surface4:#273548; --border0:#1a2436; --border1:#233149;
             --border2:#2d3e5c; --text:#cfdaea; --text-dim:#6c83a2; --text-fade:#46566e;
             --cyan:#2ee6ff; --green:#2ee6a0; --amber:#ffb43d; --red:#ff5a78;
             --purple:#b388ff; --teal:#19d6c0; --blue:#5aa6ff;
             --accent:var(--cyan); --ok:var(--green); --warn:var(--amber); --err:var(--red);
             --ink:var(--text); --muted:var(--text-dim); --panel:var(--surface1);
             --panel2:var(--surface2); --line:var(--border1);
             --shadow:0 8px 30px rgba(0,0,0,.45); }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Aptos,"Segoe UI Variable",sans-serif; color:var(--text);
            background:radial-gradient(circle at top left, rgba(46,230,255,0.06), transparent 28%), var(--bg); }}

    /* ── page layout ── */
    .page {{ max-width:1700px; margin:0 auto; padding:24px; display:grid; gap:20px; }}
    .hero,.summary,.diagram-wrap,.empty-panel {{
      background:var(--surface1); border:1px solid var(--border1); border-radius:24px; box-shadow:var(--shadow); }}
    .hero {{ padding:24px; display:grid; gap:8px; }}
    .hero h1 {{ margin:0; font-size:clamp(2rem,4vw,3rem); letter-spacing:-.04em; }}
    .hero p {{ margin:0; color:var(--muted); }}
    .eyebrow {{ font-size:.78rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }}

    /* ── summary ── */
    .summary {{ padding:14px; display:grid; gap:12px; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); }}
    .summary-card {{ padding:14px; border-radius:18px; background:var(--surface2); border:1px solid var(--border1); }}
    .summary-card .label {{ font-size:.8rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }}
    .summary-card .value {{ margin-top:6px; font-size:1.8rem; font-weight:700; }}

    /* ── diagram container ── */
    .diagram-wrap {{ padding:24px; position:relative; overflow:visible; }}
    .diagram-inner {{ position:relative; }}
    svg.conn-overlay {{ position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:2; }}

    /* ── ECU row ── */
    .ecu-row {{ display:flex; flex-wrap:wrap; gap:20px; justify-content:center; padding-bottom:36px; position:relative; z-index:3; }}
    .ecu-card {{ min-width:200px; max-width:280px; flex:1 1 220px; padding:14px; border:1px solid var(--border1);
                 border-radius:14px; background:var(--surface2); box-shadow:var(--shadow); display:grid; gap:8px; text-align:center; }}
    .ecu-header {{ display:grid; gap:2px; }}
    .ecu-name {{ font-size:1rem; font-weight:800; }}
    .ecu-variant {{ font-size:.78rem; color:var(--muted); font-weight:700; text-transform:uppercase; letter-spacing:.06em; }}
    .ecu-addr {{ display:flex; flex-wrap:wrap; gap:5px; justify-content:center; align-items:center; }}
    .addr-label {{ font-size:.7rem; font-weight:700; color:var(--muted); margin-right:2px; }}
    .addr-chip {{ display:inline-flex; padding:3px 7px; border-radius:6px; background:var(--surface3); color:var(--amber);
                  font-size:.72rem; font-weight:700; font-family:Consolas,"Courier New",monospace; }}
    .ecu-buses {{ display:flex; flex-wrap:wrap; gap:5px; justify-content:center; }}
    .bus-chip {{ display:inline-flex; padding:3px 8px; border-radius:999px; font-size:.72rem; font-weight:700;
                 color:var(--bc); background:color-mix(in srgb,var(--bc) 12%,transparent);
                 border:1px solid color-mix(in srgb,var(--bc) 22%,transparent); }}
    .ecu-alloc {{ font-size:.74rem; color:var(--muted); }}

    /* ── bus lanes ── */
    .bus-lanes {{ display:grid; gap:28px; padding:20px 0; position:relative; z-index:3; }}
    .bus-lane {{ display:grid; gap:6px; }}
    .bus-label {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
    .bus-badge {{ display:inline-flex; align-items:center; padding:7px 14px; border-radius:10px;
                  background:var(--bc); color:white; font-weight:800; font-size:.84rem; white-space:nowrap; }}
    .bus-sig-count {{ font-size:.8rem; color:var(--muted); font-weight:600; }}
    .bus-line-wrap {{ position:relative; height:6px; }}
    .bus-backbone-line {{ position:absolute; inset:0; border-radius:999px; background:var(--bc); }}
    .bus-backbone-line::after {{ content:""; position:absolute; inset:-5px 0; border-radius:999px;
      background:linear-gradient(90deg,color-mix(in srgb,var(--bc) 16%,transparent),transparent 20%,transparent 80%,color-mix(in srgb,var(--bc) 16%,transparent)); }}
    .bus-props {{ display:flex; flex-wrap:wrap; gap:6px; }}
    .prop-chip {{ display:inline-flex; padding:3px 8px; border-radius:8px; font-size:.7rem;
                  color:var(--bc); background:color-mix(in srgb,var(--bc) 10%,transparent);
                  border:1px solid color-mix(in srgb,var(--bc) 16%,transparent); font-weight:600; }}

    /* ── connection lines (SVG) ── */
    .conn-line {{ stroke-width:2; fill:none; opacity:.7; }}
    .conn-line:hover {{ stroke-width:3.5; opacity:1; }}
    .conn-dot {{ opacity:.85; }}
    .conn-label {{ font-size:10px; font-weight:700; fill:var(--text-dim); text-anchor:middle; }}

    .empty-panel {{ padding:24px; color:var(--muted); }}

    @media(max-width:900px) {{
      .page {{ padding:16px; }}
      .ecu-card {{ min-width:160px; }}
    }}
{OVERFLOW_GUARD_CSS}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <span class="eyebrow">Bus Backbone</span>
      <h1>{esc(arch_name)}</h1>
      <p>Each ECU is represented once. Lines show every bus connection. ECU addresses and bus properties are displayed.</p>
    </section>

    <section class="summary">
      <article class="summary-card"><div class="label">ECUs</div><div class="value">{total_ecus}</div></article>
      <article class="summary-card"><div class="label">Active Buses</div><div class="value">{total_buses}</div></article>
      <article class="summary-card"><div class="label">Bus Signals</div><div class="value">{total_signals}</div></article>
      <article class="summary-card"><div class="label">Connections</div><div class="value">{total_connections}</div></article>
    </section>

    <section class="diagram-wrap">
      <div class="diagram-inner" id="diagram">
        <div class="ecu-row" id="ecu-row">
{ecu_cards}
        </div>
        <div class="bus-lanes" id="bus-lanes">
{bus_lanes_html}
        </div>
        <svg class="conn-overlay" id="svg-overlay"></svg>
      </div>
    </section>
  </main>

  <script>
  (function() {{
    var COLORS = {color_json};
    var CONNS  = {conn_json};

    function drawConnections() {{
      var svg = document.getElementById('svg-overlay');
      var diagram = document.getElementById('diagram');
      if (!svg || !diagram) return;
      var dRect = diagram.getBoundingClientRect();
      svg.setAttribute('viewBox', '0 0 ' + dRect.width + ' ' + dRect.height);
      svg.style.width  = dRect.width  + 'px';
      svg.style.height = dRect.height + 'px';
      svg.innerHTML = '';

      /* Group connections by ECU so we know how many lines per ECU */
      var ecuGroups = {{}};
      CONNS.forEach(function(c) {{
        if (!ecuGroups[c.ecuIdx]) ecuGroups[c.ecuIdx] = [];
        ecuGroups[c.ecuIdx].push(c);
      }});

      var LINE_GAP = 18; /* px between parallel lines */

      Object.keys(ecuGroups).forEach(function(key) {{
        var group = ecuGroups[key];
        var n = group.length;
        var ecuEl = document.getElementById('ecu-' + key);
        if (!ecuEl) return;
        var eRect = ecuEl.getBoundingClientRect();

        /* Spread departure points across the bottom of the ECU card */
        var totalSpan = LINE_GAP * (n - 1);
        var xCenter = eRect.left + eRect.width / 2 - dRect.left;
        var xStart = xCenter - totalSpan / 2;

        group.forEach(function(c, i) {{
          var busEl = document.getElementById('bus-' + c.busIdx);
          if (!busEl) return;
          var bLine = busEl.querySelector('.bus-backbone-line');
          if (!bLine) return;
          var bRect = bLine.getBoundingClientRect();

          var x1 = xStart + LINE_GAP * i;
          var y1 = eRect.bottom - dRect.top;
          var x2 = x1; /* same x → parallel vertical lines */
          /* clamp to bus backbone bounds */
          x2 = Math.min(Math.max(x2, bRect.left - dRect.left + 6), bRect.right - dRect.left - 6);
          var y2 = bRect.top + bRect.height / 2 - dRect.top;

          var color = COLORS[c.bus] || '#888';

          /* straight line (parallel) */
          var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          path.setAttribute('d', 'M' + x1 + ',' + y1 + ' L' + x2 + ',' + y2);
          path.setAttribute('stroke', color);
          path.setAttribute('class', 'conn-line');
          svg.appendChild(path);

          /* dot on bus backbone */
          var dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
          dot.setAttribute('cx', x2);
          dot.setAttribute('cy', y2);
          dot.setAttribute('r', 5);
          dot.setAttribute('fill', color);
          dot.setAttribute('class', 'conn-dot');
          svg.appendChild(dot);

          /* label beside the line */
          var label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
          label.setAttribute('x', x2 + 8);
          label.setAttribute('y', (y1 + y2) / 2);
          label.setAttribute('class', 'conn-label');
          label.textContent = c.count + ' sig';
          svg.appendChild(label);
        }});
      }});
    }}

    window.addEventListener('load', drawConnections);
    window.addEventListener('resize', drawConnections);
  }})();
  </script>
</body>
</html>"""


def main() -> None:
    base = find_base()
    json_path = base / "exports" / "example_physical_architecture.json"
    if not json_path.exists():
        json_path = base / "exports" / "example_architecture.json"
    if not json_path.exists():
        raise SystemExit(f"Missing file: {json_path}")
    output_path = base / "exports" / "architecture_bus_backbone.html"
    arch = get_architecture(load_json(json_path))
    # Prefer topology from buses[] (authoritative); fall back to pin inference.
    topology = build_topology_from_buses(arch)
    if topology is not None:
        ecus, lanes = topology
    else:
        ecus = extract_ecus(arch)
        lanes = extract_bus_lanes(ecus)
    output_path.write_text(build_html(str(arch.get("name", "Architecture")), ecus, lanes), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()