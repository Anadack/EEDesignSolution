#!/usr/bin/env python3
"""Professional Multi-ECU Wiring Viewer — adapts the user-supplied interactive
SVG wiring-template (search/zoom/inspect, per-ECU sensors-left/actuators-right
schematic, print-to-PDF) to the real architecture export. Every pin (wired and
unconnected/spare) is shown; occupied pins are grouped into devices by
device_pin.description so each device's terminals wire to the real ECU pins.
"""
from __future__ import annotations
import json
from collections import defaultdict
from eec_archdoc_common import *

FAMILY_PRIORITY = ["CAN", "LIN", "ETH", "SENT", "PWM", "FREQ", "RES", "AO", "AI", "DI", "DO"]
TYPE_TEXT = {
    "CAN": "CAN node", "LIN": "LIN node", "ETH": "Ethernet node", "SENT": "SENT sensor",
    "PWM": "PWM output", "FREQ": "Frequency input", "RES": "Resistance input",
    "AO": "Analog output", "AI": "Analog input", "DI": "Digital input", "DO": "Digital output",
}
ACTUATOR_KEYWORDS = ("VALVE", "SOLENOID", "MOTOR", "PUMP", "COIL", "ACTUATOR", "PROPORTIONAL")


def pad_pin(value) -> str:
    try:
        return f"{int(value):03d}"
    except Exception:
        return str(value or "000")


def pin_caps(pin: dict) -> list[str]:
    """Derive template capability codes from the real pin's role/type/electrical_flags.
    Priority-ordered and deterministic; trusts the formal `type` field over group-name
    heuristics (e.g. AIV_5 group has type=RESISTANCE despite the "voltage" in its name)."""
    role = str(pin.get("role") or "").upper()
    typ = str(pin.get("type") or "").upper() or str(pin.get("interface_type") or "").upper()
    flags = set(pin.get("electrical_flags") or [])

    if role == "UNASSIGNED" or typ in ("", "RESERVED"):
        return ["NC"]
    if typ == "POWER":
        return ["PWR"]
    if typ == "GROUND":
        return ["GND"]
    if typ == "CAN":
        return ["CAN"]
    if typ == "LIN":
        return ["LIN"]
    if typ == "ETHERNET":
        return ["ETH"]
    if typ == "SENT":
        return ["SENT"]
    if typ == "PWM":
        if role == "OUTPUT":
            if "HIGH_SIDE" in flags:
                return ["PWM", "HSD"]
            if "LOW_SIDE" in flags:
                return ["PWM", "LSD"]
            return ["PWM", "DO"]
        if role == "INOUT":
            if "LOW_SIDE" in flags:
                return ["LSD", "RET"]
            if "HIGH_SIDE" in flags:
                return ["HSD", "RET"]
            return ["PWM", "RET"]
        return ["DI", "PWM"]
    if typ == "DIGITAL":
        if role == "OUTPUT":
            if "HIGH_SIDE" in flags:
                return ["HSD", "DO"]
            if "LOW_SIDE" in flags:
                return ["LSD", "DO"]
            return ["DO"]
        if role == "INOUT":
            return ["DI", "DO"]
        return ["DI"]
    if typ == "FREQUENCY":
        return ["FREQ", "DI"]
    if typ == "RESISTANCE":
        return ["RES"]
    if typ == "ANALOG":
        return ["AO"] if role == "OUTPUT" else ["AI"]
    return ["NC"]


def pin_desc(pin: dict) -> str:
    return str(pin.get("electrical") or pin.get("name") or "—")


def connector_side(pins: list[dict]) -> str | None:
    """Majority vote of occupied pins' role; falls back to the full pin role mix.
    None means tied/undecided — caller breaks the tie by connector index parity."""
    occupied = [p for p in pins if p.get("is_occupied")]
    basis = occupied if occupied else pins
    in_n = sum(1 for p in basis if str(p.get("role") or "").upper() == "INPUT")
    out_n = sum(1 for p in basis if str(p.get("role") or "").upper() == "OUTPUT")
    if in_n > out_n:
        return "left"
    if out_n > in_n:
        return "right"
    return None


def device_family_and_type(term_caps: set[str]) -> tuple[str, str]:
    fam = next((c for c in FAMILY_PRIORITY if c in term_caps), "DI")
    base = TYPE_TEXT[fam]
    if "HSD" in term_caps and fam == "DO":
        typ = "High-side output"
    elif "LSD" in term_caps and fam == "DO":
        typ = "Low-side output"
    elif "HSD" in term_caps and fam == "PWM":
        typ = "PWM output (high-side)"
    elif "LSD" in term_caps and fam == "PWM":
        typ = "PWM output (low-side, controlled return)"
    else:
        typ = base
    return fam, typ


def device_category(desc_upper: str, term_roles: list[str]) -> str:
    if any(r == "OUTPUT" for r in term_roles):
        return "actuator"
    if any(r == "INPUT" for r in term_roles):
        return "sensor"
    return "actuator" if any(k in desc_upper for k in ACTUATOR_KEYWORDS) else "sensor"


def term_code(cap: str, used: set[str]) -> str:
    base = {"PWR": "SUP", "GND": "GND", "CAN": "CAN", "LIN": "LIN", "ETH": "ETH", "RET": "RET"}.get(cap, "SIG")
    code, n = base, 1
    while code in used:
        n += 1
        code = f"{base}{n}"
    used.add(code)
    return code


def term_net(pin: dict) -> str:
    signal = pin.get("signal") if isinstance(pin.get("signal"), dict) else {}
    return signal_display_name(signal) if signal else str(pin.get("name") or "—")


def build_devices(ecu_name: str, flat_pins: list[dict]) -> list[dict]:
    """Group occupied pins by device_pin.description into one device per real wired
    component, each with terminals referencing real connector-pin ids."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for p in flat_pins:
        if not p["is_occupied"]:
            continue
        desc = p["device_desc"] or p["signal_name"] or f"Device@{p['id']}"
        groups[desc].append(p)

    sensors, actuators = [], []
    for desc, pins in groups.items():
        roles = [p["role"] for p in pins]
        cat = device_category(desc.upper(), roles)
        used_codes: set[str] = set()
        terms = []
        all_caps: set[str] = set()
        for p in pins:
            cap0 = p["caps"][0] if p["caps"] else "NC"
            all_caps.update(p["caps"])
            code = term_code(cap0, used_codes)
            terms.append([code, p["name"], p["id"], cap0, term_net(p)])
        fam, typ = device_family_and_type(all_caps - {"PWR", "GND"})
        title = desc.replace("_", " ").strip() or desc
        entry = {"category": cat, "family": fam, "title": title, "type": typ, "terms": terms}
        (sensors if cat == "sensor" else actuators).append(entry)

    devices = []
    for i, d in enumerate(sorted(sensors, key=lambda x: x["title"]), start=1):
        devices.append({"id": f"S{i:02d}", **d})
    for i, d in enumerate(sorted(actuators, key=lambda x: x["title"]), start=1):
        devices.append({"id": f"A{i:02d}", **d})
    return devices


def build_ecu_model(ecu: dict) -> dict:
    ename = str(ecu.get("name", "ECU"))
    pins = [p for p in (ecu.get("pins") or []) if isinstance(p, dict)]
    conn_order: list[str] = []
    conn_pins: dict[str, list[dict]] = defaultdict(list)
    for p in pins:
        c = str(p.get("connector") or "—")
        if c not in conn_pins:
            conn_order.append(c)
        conn_pins[c].append(p)

    connectors = []
    flat_pins = []
    for ci, cname in enumerate(conn_order):
        cp = sorted(conn_pins[cname], key=lambda p: int(p.get("physical_number") or 0))
        side = connector_side(cp)
        if side is None:
            side = "left" if ci % 2 == 0 else "right"
        occupied = sum(1 for p in cp if p.get("is_occupied"))
        raw_pins = []
        for p in cp:
            no = pad_pin(p.get("physical_number"))
            name = str(p.get("name") or f"PIN_{no}")
            caps = pin_caps(p)
            desc = pin_desc(p)
            raw_pins.append([no, name, caps, desc])
            device_pin = p.get("device_pin") if isinstance(p.get("device_pin"), dict) else {}
            signal = p.get("signal") if isinstance(p.get("signal"), dict) else {}
            flat_pins.append({
                "id": f"{cname}-{no}", "no": no, "name": name, "caps": caps,
                "connector": cname, "is_occupied": bool(p.get("is_occupied")),
                "role": str(p.get("role") or "").upper(),
                "device_desc": str(device_pin.get("description") or ""),
                "signal_name": signal_display_name(signal) if signal else "",
            })
        connectors.append({
            "id": cname, "side": side,
            "title": f"{cname} — {occupied}/{len(cp)} pins wired",
            "pins": raw_pins,
        })

    devices = build_devices(ename, flat_pins)
    variant = str(ecu.get("variant") or "")
    role = f"{variant} controller" if variant else "Tractor E/E controller"
    return {"id": ename, "name": ename, "role": role, "connectors": connectors, "devices": devices}


HEAD_CSS = """
:root{
  --font:Inter,Segoe UI,Roboto,Arial,sans-serif;
  --bg:#f4f7fb; --card:#fff; --ink:#0f172a; --muted:#64748b; --soft:#e2e8f0;
  --shadow:0 16px 45px rgba(15,23,42,.10);
  --pwr:#f59e0b; --gnd:#111827; --ai:#0284c7; --res:#0369a1; --di:#16a34a;
  --do:#dc2626; --pwm:#0f766e; --ao:#0891b2; --can:#7c3aed; --lin:#8b5cf6; --ret:#6b7280; --nc:#94a3b8;
  --eth:#0d9488; --sent:#c026d3;
}
*{box-sizing:border-box}
body{
  margin:0; font-family:var(--font); color:var(--ink);
  background:radial-gradient(circle at 0 0,rgba(37,99,235,.10),transparent 32%),
             radial-gradient(circle at 100% 0,rgba(245,158,11,.10),transparent 28%),var(--bg);
}
header{max-width:1900px;margin:auto;padding:16px 18px 8px}
h1{margin:0;font-size:clamp(24px,3vw,38px);letter-spacing:-.04em}
.subtitle{margin-top:6px;color:var(--muted);line-height:1.45;max-width:1200px}
.toolbar{
  margin-top:12px;display:grid;grid-template-columns:minmax(340px,1fr) 150px 160px 140px 112px 112px 112px;
  gap:8px;align-items:center;
}
input,select,button{
  min-height:39px;border:1px solid #cbd5e1;border-radius:11px;background:#fff;color:var(--ink);
  padding:8px 11px;font:inherit;
}
button{cursor:pointer;font-weight:850;box-shadow:0 7px 16px rgba(15,23,42,.06)}
button.primary{background:#111827;border-color:#111827;color:#fff}
button.active{background:#2563eb;color:#fff;border-color:#2563eb}
main{max-width:1900px;margin:auto;padding:0 18px 28px}
.ecu-bar-card{margin-bottom:10px}
.card{
  background:rgba(255,255,255,.96);border:1px solid rgba(148,163,184,.42);
  border-radius:18px;box-shadow:var(--shadow);overflow:hidden;
}
.card-head{padding:12px 14px;border-bottom:1px solid var(--soft);display:flex;align-items:center;justify-content:space-between;gap:10px}
.card-head h2{margin:0;font-size:15px;letter-spacing:-.01em}
.pill{padding:5px 9px;border-radius:999px;background:#eef2ff;color:#3730a3;font-size:12px;font-weight:900;white-space:nowrap}
.ecu-bar{display:flex;gap:8px;overflow:auto;padding:12px 14px}
.ecu-tab{
  flex:0 0 auto;border-radius:999px;border:1px solid #cbd5e1;background:#fff;padding:9px 13px;
  display:flex;gap:8px;align-items:center;font-weight:900;box-shadow:none;
}
.ecu-tab.active{background:#111827;color:#fff;border-color:#111827}
.ecu-dot{width:9px;height:9px;border-radius:50%;background:#94a3b8}
.ecu-tab.active .ecu-dot{background:#22c55e}

.workbench{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:12px;align-items:stretch}
.workbench.panel-collapsed{grid-template-columns:minmax(0,1fr) 54px}
.panel-collapsed .panel-content,.panel-collapsed .side-panel .card-head h2,.panel-collapsed .side-panel .pill,.panel-collapsed .panel-card:not(.panel-toggle-card){display:none}
.panel-collapsed #togglePanelInside{writing-mode:vertical-rl;transform:rotate(180deg);width:100%;min-height:300px}

.diagram-card{min-width:0}
.diagram-tools{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.zoom-btn{min-height:31px;padding:5px 9px;border-radius:9px;box-shadow:none}
#zoomRange{width:140px;min-height:0;padding:0}
.diagram-wrap{
  height:calc(100vh - 230px);min-height:720px;overflow:auto;padding:12px;
  background:linear-gradient(90deg,rgba(15,23,42,.035) 1px,transparent 1px),
             linear-gradient(0deg,rgba(15,23,42,.035) 1px,transparent 1px);
  background-size:24px 24px;
}
#svgScaler{transform-origin:top left;transition:transform .12s ease}
svg{display:block;background:#fff;border:1px solid #e5e7eb;border-radius:14px;font-family:var(--font)}
svg text{font-family:var(--font)}

.side-panel{display:grid;grid-template-rows:auto auto auto 1fr;gap:12px;min-width:0}
.panel-content{padding:12px}
.inspector{background:#f8fafc;border:1px solid #e2e8f0;border-radius:13px;padding:11px;min-height:150px;font-size:13px;line-height:1.45}
.legend{display:grid;gap:7px}
.legend-item{display:flex;align-items:center;gap:8px;font-size:12.5px}
.swatch{width:25px;height:8px;border-radius:999px}
.small{color:var(--muted);font-size:12.5px;line-height:1.45}
.mini-table-wrap{max-height:390px;overflow:auto}

.helper-box{
  background:#f8fafc;border:1px solid #e2e8f0;border-radius:13px;padding:11px;
  font-size:12.5px;line-height:1.45;max-height:320px;overflow:auto;
}
.helper-box h3{margin:0 0 6px;font-size:14px}
.helper-box h4{margin:10px 0 4px;font-size:12px;color:#334155}
.helper-box ul{margin:5px 0 0;padding-left:18px}
.helper-chip{display:inline-block;margin:4px 4px 4px 0;padding:3px 7px;border-radius:999px;background:#e0f2fe;color:#075985;font-weight:900;font-size:11px}

table{width:100%;border-collapse:collapse}
th,td{border-bottom:1px solid #e5e7eb;padding:7px 6px;text-align:left;vertical-align:top}
th{color:#475569;background:#f8fafc;font-size:12px}
td{font-size:12px}

.below{margin-top:12px}
.tabs{display:flex;gap:7px;flex-wrap:wrap;padding:12px 14px 0}
.tab{min-height:auto;padding:8px 11px;border-radius:999px;box-shadow:none;font-size:13px}
.tab.active{background:#111827;color:#fff;border-color:#111827}
.table-panel{display:none;padding:14px;overflow:auto}
.table-panel.active{display:block}
.note{padding:12px 14px;border-radius:13px;border:1px solid #fde68a;background:#fffbeb;color:#92400e;font-size:13px;line-height:1.45}

/* SVG */
.svg-title{font-size:19px;font-weight:950;fill:#0f172a}
.svg-sub{font-size:11px;font-weight:850;fill:#64748b;letter-spacing:.05em}
.zone{fill:#f8fafc;stroke:#cbd5e1;stroke-width:1}
.ecu{fill:#111827;stroke:#020617;stroke-width:2}
.ecu-title{fill:#fff;font-size:26px;font-weight:950;letter-spacing:.08em}
.ecu-sub{fill:#cbd5e1;font-size:11px}
.ecu-block{fill:#1e293b;stroke:#475569;stroke-width:1}
.connector-title{font-size:12px;font-weight:950;fill:#e5e7eb}
.pin-row,.device-group,.wire{cursor:pointer}
.pin-card{fill:#f8fafc;stroke:#334155;stroke-width:1.05}
.pin-card.highlight{stroke:#fb923c;stroke-width:3}
.pin-port{fill:#fff;stroke:#111827;stroke-width:1}
.pin-number{font-size:8.2px;fill:#64748b;font-weight:900}
.pin-name{font-size:10px;fill:#0f172a;font-weight:950}
.pin-desc{display:none}
.cap-bg{rx:5;ry:5}
.cap-text{font-size:7.6px;fill:#fff;font-weight:950}
.device-card{fill:#fff;stroke:#475569;stroke-width:1.15}
.device-card.sensor{stroke:#2563eb}
.device-card.actuator{stroke:#dc2626}

/* Professional device typography: neutral text, subtle colored category border */
.device-card.sensor{stroke:#93c5fd}
.device-card.actuator{stroke:#fca5a5}
.device-group text{stroke:none!important}
.device-group .dev-title{fill:#0f172a!important;font-weight:850!important}
.device-group .dev-type{fill:#64748b!important;font-weight:700!important}
.device-group .term-label{fill:#334155!important;font-weight:550!important}
.device-group .dev-badge-text{fill:#fff!important;stroke:none!important}
.term{fill:#fff!important;stroke:#334155!important;stroke-width:1.05}
.wire{opacity:.88}

.dev-badge{rx:5;ry:5}
.dev-badge-text{fill:#fff;font-size:8.5px;font-weight:950}
.dev-title{font-size:11.5px;fill:#0f172a;font-weight:950}
.dev-type{font-size:8.8px;fill:#64748b}
.term{fill:#fff;stroke:#111827;stroke-width:1.1}
.term-label{font-size:7.8px;fill:#334155;font-weight:550}
.wire{fill:none;stroke-width:2.25;stroke-linecap:round;stroke-linejoin:round}
.wire.power{stroke:var(--pwr)} .wire.ground{stroke:var(--gnd)} .wire.analog{stroke:var(--ai)}
.wire.res{stroke:var(--res)} .wire.digital{stroke:var(--di)} .wire.output{stroke:var(--do)}
.wire.pwm{stroke:var(--pwm)} .wire.ao{stroke:var(--ao)} .wire.comms{stroke:var(--can)}
.wire.ret{stroke:var(--ret)} .wire.nc{stroke:var(--nc);stroke-dasharray:5 5}
.wire.ethernet{stroke:var(--eth)} .wire.sent{stroke:var(--sent)}
.wire.dim{opacity:.10}.hidden{display:none!important}.fade{opacity:.20}
.lane-dot{fill:#fff;stroke:#111827;stroke-width:.8}
.wire-label{font-size:8.8px;font-weight:950;paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round}

.print-report{display:none}
.print-page{font-family:var(--font)}
.print-chip{display:inline-block;margin:1px 3px 1px 0;padding:2px 6px;border-radius:999px;color:#fff;font-size:9px;font-weight:900}
.print-card{border:1px solid #cbd5e1;border-radius:8px;padding:5px 6px;margin-bottom:5px;background:#fff}
.print-card b{font-size:11px}
.print-card small{display:block;color:#64748b;font-size:9px;line-height:1.25}
.print-table{width:100%;border-collapse:collapse;font-size:8.6px}
.print-table th,.print-table td{border:1px solid #dbe3ee;padding:3px 4px;vertical-align:top}
.print-table th{background:#f1f5f9;color:#334155;font-weight:900}
.print-checks{display:grid;grid-template-columns:repeat(3,1fr);gap:4mm;margin-top:3mm}
.print-checks div{border:1px solid #fde68a;background:#fffbeb;border-radius:8px;padding:4px 6px;font-size:8.5px;line-height:1.25;color:#78350f}

@media(max-width:1250px){.toolbar{grid-template-columns:1fr 1fr}.workbench{grid-template-columns:1fr}.workbench.panel-collapsed{grid-template-columns:1fr}.panel-collapsed .side-panel{display:none}}
@media(max-width:720px){header,main{padding-left:10px;padding-right:10px}.toolbar{grid-template-columns:1fr}}
@media print{
  @page{size:A4 landscape;margin:7mm}
  *{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}
  body{background:#fff;font-family:var(--font)}
  header,main{display:none!important}
  .print-report{display:block!important}
  .print-page{
    display:block;
    width:100%;
    height:190mm;
    page-break-after:always;
    break-after:page;
    overflow:hidden;
    background:#fff;
    color:#0f172a;
    padding:0;
  }
  .print-page:last-child{page-break-after:auto;break-after:auto}
  .print-header{
    display:flex;
    align-items:flex-start;
    justify-content:space-between;
    gap:8mm;
    border-bottom:2px solid #0f172a;
    padding-bottom:2mm;
    margin-bottom:3mm;
  }
  .print-header h2{margin:0;font-size:16px;letter-spacing:-.02em}
  .print-header p{margin:1mm 0 0;color:#475569;font-size:9px}
  .print-meta{font-size:9px;text-align:right;color:#334155;font-weight:800}
  .print-layout{
    display:grid;
    grid-template-columns:58mm 100mm 1fr;
    gap:4mm;
    align-items:start;
  }
  .print-col-title{
    font-size:10px;
    font-weight:950;
    color:#334155;
    letter-spacing:.04em;
    margin:0 0 2mm;
  }
  .print-device-list{max-height:152mm;overflow:hidden}
  .print-table{font-size:7.7px}
  .print-table th,.print-table td{padding:2.5px 3.5px}
  .print-checks{break-inside:avoid}
}
"""

BODY_HTML = """
<header>
  <h1>Multi-ECU Generic Pinout & Wiring Viewer</h1>
  <div class="subtitle">
    Select one ECU from the horizontal ECU bar. The main view redraws that ECU's sensors, actuators, pins, capabilities and direct wiring.
    Zoom controls are inside the main view, mouse wheel zoom is enabled, connection points are spaced for readability, wiring helpers show each sensor/actuator wiring concept, ECU title text is removed from inside the ECU box, pin rows are compact and ordered, sensor/actuator terminal labels are light and readable, including in PDF print, and A4 landscape PDF print creates one full wiring schematic page per ECU.
  </div>
  <div class="toolbar">
    <input id="search" placeholder="Search selected ECU: AI, DI, PWM, CAN, J1-05, sensor, valve, solenoid..." />
    <select id="category"><option value="all">All devices</option><option value="sensor">Sensors only</option><option value="actuator">Actuators only</option></select>
    <select id="capability">
      <option value="all">All capabilities</option><option value="PWR">PWR / supply</option><option value="GND">GND</option>
      <option value="AI">AI</option><option value="RES">RES</option><option value="DI">DI / FREQ</option>
      <option value="DO">DO / HSD / LSD</option><option value="PWM">PWM</option><option value="AO">AO</option><option value="CAN">CAN / LIN</option>
      <option value="ETH">ETH</option><option value="SENT">SENT</option>
    </select>
    <select id="connector"><option value="all">All connectors</option></select>
    <button id="togglePanel">Hide panel</button>
    <button id="reset" class="primary">Reset</button>
    <button id="print">Print/PDF</button>
  </div>
</header>

<main>
  <section class="card ecu-bar-card">
    <div class="card-head">
      <h2>ECU selection bar</h2>
      <span class="pill" id="selectedEcuPill">Selected ECU</span>
    </div>
    <div class="ecu-bar" id="ecuBar"></div>
  </section>

  <div class="workbench" id="workbench">
    <section class="card diagram-card">
      <div class="card-head">
        <h2 id="diagramTitle">Direct wiring schematic</h2>
        <div class="diagram-tools">
          <button class="zoom-btn" id="zoomOut">−</button>
          <input id="zoomRange" type="range" min="45" max="180" step="10" value="100" />
          <button class="zoom-btn" id="zoomIn">+</button>
          <button class="zoom-btn" id="zoomReset">100%</button>
          <span class="pill" id="statsPill">0 wires</span><span class="pill">Mouse wheel zoom</span>
        </div>
      </div>
      <div class="diagram-wrap" id="diagramWrap">
        <div id="svgScaler">
          <svg id="svg" width="2500" height="1500" viewBox="0 0 2500 1500" role="img" aria-label="Selected ECU pinout and wiring">
            <defs>
              <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="5" stdDeviation="6" flood-color="#0f172a" flood-opacity=".14"/>
              </filter>
            </defs>
            <g id="background"></g><g id="wires"></g><g id="labels"></g><g id="devices"></g><g id="ecu"></g>
          </svg>
        </div>
      </div>
    </section>

    <aside class="side-panel">
      <section class="card panel-card panel-toggle-card">
        <div class="card-head"><h2>Panel</h2><span class="pill">No overlap</span></div>
        <div class="panel-content"><button id="togglePanelInside" class="primary" style="width:100%">Hide / show panel</button></div>
      </section>
      <section class="card panel-card">
        <div class="card-head"><h2>Inspector</h2><span class="pill">Click item</span></div>
        <div class="panel-content"><div id="inspector" class="inspector">Click a device, ECU pin, or wire to inspect it.</div></div>
      </section>

      <section class="card panel-card">
        <div class="card-head"><h2>Wiring helper</h2><span class="pill">Checks</span></div>
        <div class="panel-content">
          <select id="helperSelect" style="width:100%;margin-bottom:8px"></select>
          <div id="helperBox" class="helper-box">Select a wiring type or click a device.</div>
        </div>
      </section>
      <section class="card panel-card">
        <div class="card-head"><h2>Legend</h2></div>
        <div class="panel-content">
          <div class="legend">
            <div class="legend-item"><span class="swatch" style="background:var(--pwr)"></span>Power / Vbat / reference</div>
            <div class="legend-item"><span class="swatch" style="background:var(--gnd)"></span>Ground</div>
            <div class="legend-item"><span class="swatch" style="background:var(--ai)"></span>Analog input / current input</div>
            <div class="legend-item"><span class="swatch" style="background:var(--res)"></span>Resistance input</div>
            <div class="legend-item"><span class="swatch" style="background:var(--di)"></span>Digital / frequency input</div>
            <div class="legend-item"><span class="swatch" style="background:var(--do)"></span>Digital output / HSD / LSD</div>
            <div class="legend-item"><span class="swatch" style="background:var(--pwm)"></span>PWM / proportional</div>
            <div class="legend-item"><span class="swatch" style="background:var(--can)"></span>CAN / LIN</div>
            <div class="legend-item"><span class="swatch" style="background:var(--eth)"></span>Ethernet</div>
            <div class="legend-item"><span class="swatch" style="background:var(--sent)"></span>SENT</div>
            <div class="legend-item"><span class="swatch" style="background:var(--ret)"></span>Return</div>
          </div>
        </div>
      </section>
      <section class="card panel-card">
        <div class="card-head"><h2>Filtered netlist</h2></div>
        <div class="panel-content mini-table-wrap">
          <table id="miniNet"><thead><tr><th>Wire</th><th>Device</th><th>Pin</th></tr></thead><tbody></tbody></table>
        </div>
      </section>
    </aside>
  </div>

  <section class="card below">
    <div class="card-head"><h2>Selected ECU source tables</h2><span class="pill">Data-driven</span></div>
    <div class="tabs">
      <button class="tab active" data-tab="tabPins">Pin capability matrix</button>
      <button class="tab" data-tab="tabDevices">Sensor & actuator library</button>
      <button class="tab" data-tab="tabNetlist">Full netlist</button>
      <button class="tab" data-tab="tabHelpers">Wiring helpers & checks</button>
      <button class="tab" data-tab="tabNotes">About this report</button>
    </div>
    <div id="tabPins" class="table-panel active"><table id="pinTable"></table></div>
    <div id="tabDevices" class="table-panel"><table id="deviceTable"></table></div>
    <div id="tabNetlist" class="table-panel"><table id="netlistTable"></table></div>
    <div id="tabHelpers" class="table-panel"><table id="helperTable"></table></div>
    <div id="tabNotes" class="table-panel">
      <div class="note">
        Generated directly from the framework's physical architecture export. Every documented pin on every connector is shown, including unconnected/spare cavities (capability <b>NC</b>). Pin capabilities are decoded from each pin's role, type and electrical flags; wired devices are grouped from <b>device_pin.description</b> and wired to their real connector-pin id (e.g. <b>X1-014</b>). Wiring helper rules are stored in <b>WIRING_HELPERS</b>. The ECU bar is generated automatically from the export's ECU list.
      </div>
    </div>
  </section>
</main>

<section id="printReport" class="print-report"></section>
"""

SCRIPT_PRE = """
const CAP_COLORS={PWR:"#f59e0b",GND:"#111827",AI:"#0284c7",RES:"#0369a1",DI:"#16a34a",FREQ:"#16a34a",DO:"#dc2626",HSD:"#dc2626",LSD:"#b91c1c",PWM:"#0f766e",AO:"#0891b2",CAN:"#7c3aed",LIN:"#8b5cf6",RET:"#6b7280",NC:"#94a3b8",SHIELD:"#64748b",ETH:"#0d9488",SENT:"#c026d3"};
const WIRE_CLASS={PWR:"power",GND:"ground",AI:"analog",RES:"res",DI:"digital",FREQ:"digital",DO:"output",HSD:"output",LSD:"ret",PWM:"pwm",AO:"ao",CAN:"comms",LIN:"comms",RET:"ret",NC:"nc",SHIELD:"ground",ETH:"ethernet",SENT:"sent"};

const WIRING_HELPERS={
 ACTIVE_VOLTAGE_SENSOR:{group:"Sensor",title:"Active voltage sensor",caps:["PWR","AI","GND"],wiring:["Sensor supply from ECU reference/supply pin.","Sensor signal to ECU analog input pin.","Sensor 0 V to ECU sensor ground pin."],checks:["Confirm sensor supply voltage and maximum supply current.","Confirm ECU AI range: 0–5 V, 0–10 V or 0–32 V.","Check common ground strategy and sensor ground current.","Check short-to-battery, short-to-ground and open-circuit diagnostic concept.","Verify shielding/twisted pair if signal is noisy or cable is long."]},
 POTENTIOMETER:{group:"Sensor",title:"Potentiometer / joystick / pedal",caps:["PWR","AI","GND"],wiring:["ECU 5 V or 10 V reference to potentiometer high side.","Wiper terminal to ratiometric ECU analog input.","Low side to ECU sensor ground."],checks:["Confirm potentiometer resistance is compatible with ECU reference output.","Check wiper voltage never exceeds AI limits at mechanical end stops.","Verify plausibility diagnostics if dual-channel pedal/joystick is safety relevant.","Check open wiper and short-to-reference/ground detection.","Avoid sharing noisy actuator ground with sensor ground."]},
 DIGITAL_SWITCH:{group:"Sensor",title:"Digital switch / proximity input",caps:["PWR","DI","GND"],wiring:["Low-active: switch closes ECU DI to ground with ECU/internal pull-up.","High-active: switch sends protected Vbat/supply to ECU DI.","Optional supply pin used for wetting current or proximity sensor power."],checks:["Confirm DI voltage rating for Vbat and load-dump/transients.","Check pull-up/pull-down configuration and wetting current.","Define debounce/filter time in software.","Verify active state, fail state, open-circuit behavior and diagnostics.","Check if sensor is PNP, NPN, dry contact, Namur, or push-pull."]},
 RESISTANCE_SENSOR:{group:"Sensor",title:"Resistance / NTC sensor",caps:["RES","GND"],wiring:["Sensor resistance terminal to ECU resistance input.","Other terminal to ECU sensor ground or dedicated return.","ECU internal pull-up/excitation performs measurement."],checks:["Confirm resistance range and temperature curve match ECU calibration.","Check ECU excitation current and self-heating of NTC.","Verify open/short diagnostic thresholds.","Use sensor ground, not power ground, for low-noise measurement.","Check cable resistance effect if sensor is far from ECU."]},
 CURRENT_LOOP_SENSOR:{group:"Sensor",title:"4–20 mA current-loop sensor",caps:["PWR","AI","RET"],wiring:["Loop supply from ECU/protected supply where required.","Current signal into ECU current input or AI with burden resistor.","Return to ECU loop return or sensor ground according to sensor type."],checks:["Identify 2-wire loop-powered vs 3-wire separately powered sensor.","Confirm ECU input mode, burden resistor and voltage compliance.","Check 4 mA and 20 mA calibration limits, plus under/over-range diagnostics.","Verify loop supply voltage under worst-case cable resistance.","Check isolation/grounding if multiple supplies are used."]},
 FREQUENCY_SENSOR:{group:"Sensor",title:"Frequency / Hall / speed sensor",caps:["PWR","FREQ","GND"],wiring:["Supply sensor from ECU sensor supply or protected Vbat.","Frequency output to ECU frequency/digital input.","Ground to ECU sensor ground."],checks:["Confirm output type: open collector, push-pull, PNP or NPN.","Set correct pull-up voltage and resistor/current.","Verify frequency range, duty cycle and input capture capability.","Check shielding/twisted pair for high speed or long cables.","Validate missing-tooth/no-pulse diagnostics if used for control."]},
 ENCODER:{group:"Sensor",title:"Quadrature encoder",caps:["PWR","DI","GND"],wiring:["Encoder A and B channels to two ECU digital/frequency inputs.","Optional index Z to a third input.","Supply and ground from ECU sensor supply/ground."],checks:["Confirm input speed can handle maximum pulse rate.","Check A/B phase convention and direction logic.","Verify pull-up/pull-down and signal voltage levels.","Use shielding/twisted pairs for A/B where needed.","Validate missing pulse, stuck channel and plausibility diagnostics."]},
 PWM_SENSOR:{group:"Sensor",title:"PWM duty-cycle sensor",caps:["DI","PWM","GND"],wiring:["PWM signal to ECU duty/frequency-capable input.","Sensor ground to ECU sensor ground.","Optional supply to sensor power pin."],checks:["Confirm PWM frequency and duty range accepted by ECU.","Check signal voltage level and input threshold.","Verify pull-up/down requirements for open collector outputs.","Define timeout and invalid duty diagnostics.","Check filtering so duty measurement is stable."]},
 SMART_SENSOR:{group:"Sensor",title:"CAN / LIN / Ethernet smart sensor node",caps:["CAN","LIN","ETH","PWR","GND"],wiring:["CAN H/L, LIN or Ethernet pair to ECU communication pins.","Node supply to protected Vbat/sensor supply.","Node ground to ECU/common ground.","Shield/drain according to EMC strategy."],checks:["Confirm bus speed, protocol and node addressing.","Check CAN termination: only at bus ends, typically 120 Ω each end.","Verify topology, stub length and cable impedance.","Check wake/sleep behavior and supply current.","Validate timeout, message counter and CRC diagnostics where applicable."]},
 SENT_SENSOR:{group:"Sensor",title:"SENT digital sensor (SAE J2716)",caps:["PWR","SENT","GND"],wiring:["Sensor supply from ECU sensor supply or protected Vbat.","Single SENT signal wire to ECU SENT-capable input.","Sensor ground to ECU sensor ground."],checks:["Confirm SENT protocol variant/message format matches ECU decoding.","Check supply voltage/current and signal line pull-up per sensor datasheet.","Verify cable length and termination against the SENT timing budget.","Check sync-pulse, CRC and timeout diagnostics.","Validate shielding/twisted pair if cable is long or routed near noise sources."]},
 HSD_LOAD:{group:"Actuator",title:"High-side driven load / solenoid",caps:["HSD","DO","GND"],wiring:["ECU HSD output to positive side of coil/load.","Other side of load to actuator ground.","ECU switches Vbat to the load."],checks:["Confirm load current is below HSD continuous and peak rating.","Check inrush current, cold resistance and duty cycle.","Verify flyback/clamp strategy and output diagnostics.","Check short-to-ground, short-to-battery and open-load detection.","Validate fuse and wire section for maximum fault current."]},
 LSD_LOAD:{group:"Actuator",title:"Low-side driven load / solenoid",caps:["PWR","LSD","DO"],wiring:["Fused Vbat/protected supply to one side of coil/load.","Other side of load to ECU LSD output.","ECU switches the return/ground side."],checks:["Confirm LSD current rating and thermal limits.","Check supply fuse, cable size and load resistance.","Verify flyback path/clamp voltage.","Check short-to-battery, short-to-ground and open-load diagnostics.","Ensure load is not unintentionally powered through shared returns."]},
 PWM_VALVE:{group:"Actuator",title:"PWM proportional valve — ground return",caps:["PWM","GND"],wiring:["ECU PWM output to proportional coil command terminal.","Other coil terminal to actuator ground.","PWM duty/current controls valve position."],checks:["Confirm coil resistance, nominal current and ECU PWM current rating.","Check PWM frequency recommended by valve manufacturer.","Verify current control vs voltage PWM mode.","Check coil heating at maximum duty and ambient temperature.","Validate flyback, dither, ramp and failsafe behavior."]},
 PWM_VALVE_RETURN:{group:"Actuator",title:"PWM proportional valve — ECU controlled return",caps:["PWM","LSD","RET"],wiring:["ECU PWM/HSD command to one coil terminal.","ECU LSD/return pin to other coil terminal.","ECU can diagnose/control both sides of the coil."],checks:["Confirm the ECU supports paired PWM + controlled return on those pins.","Check both high-side and low-side current/thermal limits.","Validate diagnostic coverage for each side of the coil.","Confirm flyback strategy for the paired driver topology.","Check valve connector polarity if diagnostics depend on it."]},
 PILOT_OUTPUT:{group:"Actuator",title:"Pilot / duty-cycle command output",caps:["PWM","GND"],wiring:["ECU pilot/PWM output to controlled device input.","Reference ground to ECU/device ground.","Output duty often represents 25–75% Vbat command."],checks:["Confirm expected duty range, frequency and voltage level.","Check input impedance of receiving device.","Verify reference ground offset is acceptable.","Check fail-safe duty or output-off state.","Validate filtering and response time."]},
 ANALOG_COMMAND:{group:"Actuator",title:"Analog command output",caps:["AO","RET"],wiring:["ECU analog output to actuator/amplifier command input.","Analog return to ECU AO return or signal ground.","Used for 0–10 V, 0–5 V or 4–20 mA commands."],checks:["Confirm voltage/current mode and output range.","Check load impedance or current-loop compliance voltage.","Verify return/grounding to avoid offset error.","Check output short-circuit protection.","Validate fail-safe output value on ECU reset/power loss."]},
 MOTOR_HBRIDGE:{group:"Actuator",title:"DC motor H-bridge",caps:["PWM","DO"],wiring:["Motor terminal A to ECU H-bridge A output.","Motor terminal B to ECU H-bridge B output.","Optional enable/brake pin to ECU DO/PWM."],checks:["Confirm stall current, inrush current and thermal duty cycle.","Check H-bridge current rating and protection strategy.","Verify direction logic and brake/coast behavior.","Check EMC suppression for motor brushes/cables.","Validate mechanical end-stop and jam detection."]},
 STEPPER_MOTOR:{group:"Actuator",title:"Stepper motor",caps:["DO","PWM"],wiring:["Each motor phase terminal to its ECU stepper/DO output.","Bipolar stepper uses paired phase outputs.","Power supply/ground according to driver topology."],checks:["Confirm motor phase current and driver rating.","Check winding resistance/inductance and step rate.","Verify phase order and direction.","Check holding current and thermal behavior.","Validate stall, missed-step or end-stop strategy."]},
 SMART_ACTUATOR:{group:"Actuator",title:"CAN / LIN / Ethernet smart actuator",caps:["CAN","LIN","ETH","PWR","GND"],wiring:["CAN H/L, LIN or Ethernet pair to ECU communication pins.","Actuator supply from fused/protected Vbat.","Ground to power ground/common ground.","Optional shield according to bus/EMC design."],checks:["Confirm protocol, baud rate, node ID and message set.","Check CAN termination and stub length.","Verify supply current, fuse and ground return path.","Check wake/sleep and network management requirements.","Validate timeout/failsafe behavior if communication is lost."]},
 SAFETY_OUTPUT:{group:"Actuator",title:"Safety output with feedback",caps:["DO","DI","GND"],wiring:["ECU safety output to load or safety relay input.","Feedback contact/signal back to ECU digital input.","Common ground/reference as specified by safety concept."],checks:["Confirm safety category/PL/SIL target and diagnostic coverage.","Check feedback timing and discrepancy monitoring.","Verify output off-state leakage and load input threshold.","Validate short/open diagnostics and safe state.","Test power-up, reset and emergency-stop behavior."]}
};

"""

SCRIPT_POST = """
const svg=document.getElementById("svg"), scaler=document.getElementById("svgScaler");
const gBg=document.getElementById("background"),gWires=document.getElementById("wires"),gLabels=document.getElementById("labels"),gDevices=document.getElementById("devices"),gEcu=document.getElementById("ecu");
const inspector=document.getElementById("inspector");
const LAYOUT={
 canvasW:2500,
 leftDeviceX:60,
 deviceW:330,
 ecuX:870,
 ecuW:760,
 rightDeviceX:2110,
 topY:104,
 deviceGap:16,
 pinPitch:34,
 pinH:26,
 pinW:300,
 terminalPitch:21,
 deviceHeaderH:54,
 devicePadBottom:10,
 minDeviceH:82,
 laneMarginFromBox:44,
 laneMarginFromEcu:58,
 laneMinGap:8,
 laneMaxGap:14
};
const X={leftDevice:LAYOUT.leftDeviceX,leftDeviceW:LAYOUT.deviceW,ecu:LAYOUT.ecuX,ecuW:LAYOUT.ecuW,rightDevice:LAYOUT.rightDeviceX,rightDeviceW:LAYOUT.deviceW};
const topY=LAYOUT.topY,deviceGap=LAYOUT.deviceGap,pinPitch=LAYOUT.pinPitch,pinH=LAYOUT.pinH,pinW=LAYOUT.pinW;
let selectedIndex=0,selected=null,flatPins=[],devices=[],wires=[],zoom=1;

function ns(name,attrs={},text=""){const n=document.createElementNS("http://www.w3.org/2000/svg",name);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));if(text!=="")n.textContent=text;return n;}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#039;"}[c]));}
function fitText(s,max=24){s=String(s);return s.length>max?s.slice(0,Math.max(0,max-1))+"…":s;}
function capColor(cap){return CAP_COLORS[cap]||"#64748b"} function wireClass(cap){return WIRE_CLASS[cap]||"digital"}
function normalizePin(raw,conn){return {no:raw[0],name:raw[1],caps:raw[2],desc:raw[3],id:conn.id+"-"+raw[0],connector:conn.id,connectorTitle:conn.title,side:conn.side};}
function normalizeDevice(raw){return {...raw,terminals:raw.terms.map(t=>({id:t[0],label:t[1],pin:t[2],cap:t[3],net:t[4]}))};}
function pinById(id){return flatPins.find(p=>p.id===id)} function deviceById(id){return devices.find(d=>d.id===id)}
function sideOfWire(w){return deviceById(w.deviceId).category==="sensor"?"left":"right"}
function terminalPort(d,t){return {x:d.category==="sensor"?d.x+d.w:d.x,y:d.y+t.y}}
function pinPort(p){return {x:p.side==="left"?X.ecu:X.ecu+X.ecuW,y:p.y}}

function layoutData(){
 selected=ecuModels[selectedIndex];
 flatPins=[];
 const sideCursor={left:topY,right:topY};
 selected.connectors.forEach(conn=>{
  conn.pins.forEach((raw,i)=>{
   flatPins.push({...normalizePin(raw,conn),index:i,y:sideCursor[conn.side]});
   sideCursor[conn.side]+=pinPitch;
  });
 });
 devices=selected.devices.map(normalizeDevice);
 ["sensor","actuator"].forEach(cat=>{
  let y=topY;
  devices.filter(d=>d.category===cat).forEach(d=>{
   d.x=cat==="sensor"?X.leftDevice:X.rightDevice; d.w=cat==="sensor"?X.leftDeviceW:X.rightDeviceW;
   d.h=Math.max(LAYOUT.minDeviceH,LAYOUT.deviceHeaderH+d.terminals.length*LAYOUT.terminalPitch+LAYOUT.devicePadBottom); d.y=y; d.terminals.forEach((t,i)=>t.y=LAYOUT.deviceHeaderH+i*LAYOUT.terminalPitch); y+=d.h+deviceGap;
  });
 });
 wires=[];
 devices.forEach(d=>d.terminals.forEach(t=>{if(pinById(t.pin))wires.push({id:d.id+"."+t.id,deviceId:d.id,terminalId:t.id,pinId:t.pin,cap:t.cap||pinById(t.pin).caps[0],cls:wireClass(t.cap||pinById(t.pin).caps[0]),net:t.net||t.label});}));
}
function requiredHeight(){return Math.max(1500,...devices.map(d=>d.y+d.h+80),...flatPins.map(p=>p.y+80))}
function setSvgSize(){const h=requiredHeight();svg.setAttribute("height",h);svg.setAttribute("viewBox",`0 0 ${LAYOUT.canvasW} ${h}`);scaler.style.width=LAYOUT.canvasW+"px";scaler.style.height=h+"px";applyZoom();}
function drawBackground(){
 const h=requiredHeight();gBg.innerHTML="";
 gBg.appendChild(ns("text",{x:40,y:42,class:"svg-title"},"Sensors / Inputs"));
 gBg.appendChild(ns("text",{x:X.ecu+20,y:42,class:"svg-title"},selected.name));
 gBg.appendChild(ns("text",{x:X.rightDevice,y:42,class:"svg-title"},"Actuators / Outputs"));
 gBg.appendChild(ns("text",{x:X.ecu+20,y:62,class:"svg-sub"},selected.role));
 gBg.appendChild(ns("rect",{x:30,y:68,width:390,height:h-110,rx:18,class:"zone"}));
 gBg.appendChild(ns("rect",{x:X.rightDevice-30,y:68,width:390,height:h-110,rx:18,class:"zone"}));
 gBg.appendChild(ns("text",{x:50,y:94,class:"svg-sub"},"GENERIC SENSOR TYPES"));
 gBg.appendChild(ns("text",{x:X.rightDevice,y:94,class:"svg-sub"},"GENERIC ACTUATOR TYPES"));
 gBg.appendChild(ns("text",{x:X.leftDevice+X.leftDeviceW+LAYOUT.laneMarginFromBox,y:94,class:"svg-sub"},"WIRE ROUTING CORRIDOR"));
 gBg.appendChild(ns("text",{x:X.ecu+X.ecuW+LAYOUT.laneMarginFromEcu,y:94,class:"svg-sub"},"WIRE ROUTING CORRIDOR"));
}
function drawECU(){
 gEcu.innerHTML=""; const h=Math.max(requiredHeight()-120,980), y0=52;
 gEcu.appendChild(ns("rect",{x:X.ecu,y:y0,width:X.ecuW,height:h,rx:22,class:"ecu",filter:"url(#shadow)"}));
 selected.connectors.forEach(conn=>{
  const cp=flatPins.filter(p=>p.connector===conn.id); if(!cp.length)return;
  const ys=Math.min(...cp.map(p=>p.y))-18, ye=Math.max(...cp.map(p=>p.y))+18;
  const bx=conn.side==="left"?X.ecu+28:X.ecu+X.ecuW-pinW-28, bw=pinW+18;
  gEcu.appendChild(ns("rect",{x:bx-9,y:ys,width:bw,height:ye-ys,rx:14,class:"ecu-block"}));
 });
 flatPins.forEach(p=>{
  const rowX=p.side==="left"?X.ecu+36:X.ecu+X.ecuW-pinW-36, rowY=p.y-pinH/2, port=pinPort(p);
  const g=ns("g",{class:"pin-row","data-id":p.id,"data-text":`${p.id} ${p.name} ${p.caps.join(" ")} ${p.desc} ${p.connector}`});
  g.appendChild(ns("rect",{x:rowX,y:rowY,width:pinW,height:pinH,rx:6,class:"pin-card"}));
  g.appendChild(ns("circle",{cx:port.x,cy:port.y,r:3.2,class:"pin-port"}));
  g.appendChild(ns("line",{x1:port.x,y1:port.y,x2:p.side==="left"?rowX:rowX+pinW,y2:port.y,stroke:"#cbd5e1","stroke-width":"1"}));

  // Fixed zones: ID/name on the left, capability chips on the right.
  // No title, no description inside the ECU row, so there is no text/chip overlap.
  const textX=rowX+12;
  g.appendChild(ns("text",{x:textX,y:rowY+9,class:"pin-number"},p.id));
  g.appendChild(ns("text",{x:textX,y:rowY+21,class:"pin-name"},fitText(p.name,20)));

  let chipX=rowX+pinW-8;
  p.caps.slice(0,3).reverse().forEach(cap=>{
    const w=Math.max(26,cap.length*7+11);
    chipX-=w;
    g.appendChild(ns("rect",{x:chipX,y:rowY+5,width:w,height:16,class:"cap-bg",fill:capColor(cap)}));
    g.appendChild(ns("text",{x:chipX+w/2,y:rowY+17.2,"text-anchor":"middle",class:"cap-text"},cap));
    chipX-=4;
  });

  g.addEventListener("click",e=>{e.stopPropagation();showPin(p)});gEcu.appendChild(g);
 });
}
function drawDevices(){
 gDevices.innerHTML="";
 devices.forEach(d=>{
  const g=ns("g",{class:`device-group ${d.category}`,"data-id":d.id,"data-text":`${d.id} ${d.category} ${d.family} ${d.title} ${d.type}`});
  g.appendChild(ns("rect",{x:d.x,y:d.y,width:d.w,height:d.h,rx:15,class:`device-card ${d.category}`,filter:"url(#shadow)"}));
  const bc=d.category==="sensor"?"#2563eb":"#ef4444";
  g.appendChild(ns("rect",{x:d.x+12,y:d.y+9,width:50,height:19,class:"dev-badge",fill:bc}));
  g.appendChild(ns("text",{x:d.x+37,y:d.y+23.2,"text-anchor":"middle",class:"dev-badge-text"},d.id));
  g.appendChild(ns("text",{x:d.x+64,y:d.y+23,class:"dev-title"},fitText(d.title,25)));
  g.appendChild(ns("text",{x:d.x+64,y:d.y+39,class:"dev-type"},fitText(d.type+" • "+d.family,30)));
  d.terminals.forEach(t=>{const port=terminalPort(d,t), labelX=d.category==="sensor"?port.x-12:port.x+12, anchor=d.category==="sensor"?"end":"start";g.appendChild(ns("circle",{cx:port.x,cy:port.y,r:3.8,class:"term"}));g.appendChild(ns("text",{x:labelX,y:port.y+3,"text-anchor":anchor,class:"term-label"},fitText(t.label,17)));});
  g.addEventListener("click",e=>{e.stopPropagation();showDevice(d)});gDevices.appendChild(g);
 });
}
function laneGapFor(count,start,end){
 const span=Math.max(1,end-start);
 if(count<=1) return 0;
 return Math.max(LAYOUT.laneMinGap,Math.min(LAYOUT.laneMaxGap,span/(count-1)));
}
function routeLaneX(w,ids){
 const idx=ids.indexOf(w.id);
 if(sideOfWire(w)==="left"){
  const start=X.leftDevice+X.leftDeviceW+LAYOUT.laneMarginFromBox;
  const end=X.ecu-LAYOUT.laneMarginFromEcu;
  return start+idx*laneGapFor(ids.length,start,end);
 }
 const start=X.ecu+X.ecuW+LAYOUT.laneMarginFromEcu;
 const end=X.rightDevice-LAYOUT.laneMarginFromBox;
 return start+idx*laneGapFor(ids.length,start,end);
}
function wirePath(w,ids){const d=deviceById(w.deviceId),t=d.terminals.find(x=>x.id===w.terminalId),p=pinById(w.pinId),tp=terminalPort(d,t),pp=pinPort(p),lane=routeLaneX(w,ids);return d.category==="sensor"?`M ${tp.x} ${tp.y} H ${lane} V ${pp.y} H ${pp.x}`:`M ${pp.x} ${pp.y} H ${lane} V ${tp.y} H ${tp.x}`}
function drawWires(){
 gWires.innerHTML="";gLabels.innerHTML="";
 const left=wires.filter(w=>sideOfWire(w)==="left").map(w=>w.id), right=wires.filter(w=>sideOfWire(w)==="right").map(w=>w.id);
 wires.forEach(w=>{
  const ids=sideOfWire(w)==="left"?left:right,d=deviceById(w.deviceId),t=d.terminals.find(x=>x.id===w.terminalId),p=pinById(w.pinId),tp=terminalPort(d,t),pp=pinPort(p),lane=routeLaneX(w,ids);
  const path=ns("path",{d:wirePath(w,ids),class:`wire ${w.cls}`,"data-id":w.id,"data-text":`${w.id} ${w.net} ${w.cap} ${d.title} ${t.label} ${p.id} ${p.name}`});
  path.addEventListener("click",e=>{e.stopPropagation();showWire(w)});gWires.appendChild(path);
  gWires.appendChild(ns("circle",{cx:lane,cy:tp.y,r:2.25,class:"lane-dot"}));gWires.appendChild(ns("circle",{cx:lane,cy:pp.y,r:2.25,class:"lane-dot"}));
  const lx=sideOfWire(w)==="left"?lane-4:lane+4, ly=Math.min(tp.y,pp.y)+Math.abs(tp.y-pp.y)/2;
  gLabels.appendChild(ns("text",{x:lx,y:ly,"text-anchor":sideOfWire(w)==="left"?"end":"start",class:"wire-label",fill:capColor(w.cap),"data-wire":w.id},w.cap));
 });
}
function renderEcuBar(){
 const bar=document.getElementById("ecuBar");bar.innerHTML="";
 ecuModels.forEach((e,i)=>{const b=document.createElement("button");b.className="ecu-tab"+(i===selectedIndex?" active":"");b.innerHTML=`<span class="ecu-dot"></span><span>${esc(e.id)}</span><span style="color:inherit;opacity:.72;font-weight:700">${esc(e.name.replace(e.id,"").trim())}</span>`;b.onclick=()=>selectEcu(i);bar.appendChild(b);});
}
function updateConnectorOptions(){
 const sel=document.getElementById("connector");sel.innerHTML='<option value="all">All connectors</option>'+selected.connectors.map(c=>`<option value="${esc(c.id)}">${esc(c.id)} ${esc(c.side)}</option>`).join("");
}
function renderAll(){
 layoutData();setSvgSize();drawBackground();drawWires();drawDevices();drawECU();renderTables();renderMiniNet(wires.map(w=>w.id));renderEcuBar();updateConnectorOptions();renderHelperOptions();
 document.getElementById("selectedEcuPill").textContent=selected.name;document.getElementById("diagramTitle").textContent=selected.name+" — direct wiring schematic";resetFiltersOnly();
}
function selectEcu(i){selectedIndex=i;inspector.innerHTML="Click a device, ECU pin, or wire to inspect it.";renderAll();}
function resetFiltersOnly(){document.getElementById("search").value="";document.getElementById("category").value="all";document.getElementById("capability").value="all";document.getElementById("connector").value="all";document.querySelectorAll(".hidden").forEach(n=>n.classList.remove("hidden"));clearHighlight();}

function helperKeyForDevice(d){
 const txt=(d.title+" "+d.type+" "+d.family+" "+d.category).toLowerCase();
 if(d.category==="sensor"){
  if(d.family==="CAN"||d.family==="LIN"||d.family==="ETH") return "SMART_SENSOR";
  if(d.family==="SENT") return "SENT_SENSOR";
  if(d.family==="RES") return "RESISTANCE_SENSOR";
  if(d.family==="PWM") return "PWM_SENSOR";
  if(txt.includes("current")||txt.includes("4–20")||txt.includes("4-20")) return "CURRENT_LOOP_SENSOR";
  if(txt.includes("potentiometer")||txt.includes("joystick")||txt.includes("pedal")||txt.includes("knob")) return "POTENTIOMETER";
  if(txt.includes("encoder")||txt.includes("quadrature")) return "ENCODER";
  if(txt.includes("hall")||txt.includes("speed")||txt.includes("flow")||txt.includes("frequency")) return "FREQUENCY_SENSOR";
  if(d.family==="DI") return "DIGITAL_SWITCH";
  return "ACTIVE_VOLTAGE_SENSOR";
 }
 if(txt.includes("safety")||txt.includes("safe output")) return "SAFETY_OUTPUT";
 if(d.family==="CAN"||d.family==="LIN"||d.family==="ETH") return "SMART_ACTUATOR";
 if(d.family==="AO") return "ANALOG_COMMAND";
 if(txt.includes("stepper")) return "STEPPER_MOTOR";
 if(txt.includes("motor")||txt.includes("h-bridge")) return "MOTOR_HBRIDGE";
 if(txt.includes("pilot")) return "PILOT_OUTPUT";
 if(d.family==="PWM" && (txt.includes("ecu return")||txt.includes("controlled return")||txt.includes("return"))) return "PWM_VALVE_RETURN";
 if(d.family==="PWM") return "PWM_VALVE";
 if(txt.includes("lsd")||txt.includes("low-side")) return "LSD_LOAD";
 return "HSD_LOAD";
}
function helperHTML(key,d=null){
 const h=WIRING_HELPERS[key]||WIRING_HELPERS.ACTIVE_VOLTAGE_SENSOR;
 const deviceNote=d?`<p><b>Applied to:</b> ${esc(d.id)} — ${esc(d.title)}</p>`:"";
 return `<h3>${esc(h.title)}</h3><span class="helper-chip">${esc(h.group)}</span>${h.caps.map(c=>`<span class="helper-chip">${esc(c)}</span>`).join("")}${deviceNote}
 <h4>Typical wiring</h4><ul>${h.wiring.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>
 <h4>Electrical verification to perform</h4><ul>${h.checks.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`;
}
function updateHelper(key,d=null){
 const sel=document.getElementById("helperSelect");
 const box=document.getElementById("helperBox");
 if(sel && WIRING_HELPERS[key]) sel.value=key;
 if(box) box.innerHTML=helperHTML(key,d);
}
function renderHelperOptions(){
 const sel=document.getElementById("helperSelect");
 if(!sel) return;
 sel.innerHTML=Object.entries(WIRING_HELPERS).map(([k,h])=>`<option value="${esc(k)}">${esc(h.group)} — ${esc(h.title)}</option>`).join("");
 sel.onchange=()=>updateHelper(sel.value);
 updateHelper(sel.value||"ACTIVE_VOLTAGE_SENSOR");
}

function showDevice(d){const lines=d.terminals.map(t=>{const p=pinById(t.pin);return `<li><b>${esc(t.label)}</b> → ${esc(p.id)} ${esc(p.name)} <span style="color:#64748b">(${esc(t.cap)} / ${esc(t.net)})</span></li>`}).join("");const hk=helperKeyForDevice(d);inspector.innerHTML=`<b>${esc(d.id)} — ${esc(d.title)}</b><br><span style="color:#64748b">${esc(d.category)} • ${esc(d.type)} • ${esc(d.family)}</span><p><b>Direct ECU connections</b></p><ul style="padding-left:18px;margin:6px 0 0">${lines}</ul><p style="margin-top:8px;color:#64748b">Wiring helper updated: <b>${esc(WIRING_HELPERS[hk].title)}</b></p>`;updateHelper(hk,d);highlight({device:d.id})}
function showPin(p){const conns=wires.filter(w=>w.pinId===p.id).map(w=>{const d=deviceById(w.deviceId),t=d.terminals.find(x=>x.id===w.terminalId);return `<li><b>${esc(w.net)}</b><br>${esc(d.id)} ${esc(d.title)} / ${esc(t.label)}</li>`}).join("");inspector.innerHTML=`<b>${esc(p.id)} — ${esc(p.name)}</b><br>${p.caps.map(c=>`<span style="display:inline-block;margin:6px 4px 4px 0;padding:4px 8px;border-radius:999px;background:${capColor(c)};color:#fff;font-weight:900;font-size:12px">${esc(c)}</span>`).join("")}<p>${esc(p.desc)}<br><span style="color:#64748b">${esc(p.connectorTitle)}</span></p><b>Connected terminal(s)</b><ul style="padding-left:18px;margin:6px 0 0">${conns||"<li>No mapped terminal yet</li>"}</ul>`;highlight({pin:p.id})}
function showWire(w){const d=deviceById(w.deviceId),t=d.terminals.find(x=>x.id===w.terminalId),p=pinById(w.pinId);inspector.innerHTML=`<b>${esc(w.id)} — ${esc(w.net)}</b><br><span style="display:inline-block;margin:6px 0;padding:4px 8px;border-radius:999px;background:${capColor(w.cap)};color:#fff;font-weight:900;font-size:12px">${esc(w.cap)}</span><p><b>From:</b> ${esc(d.id)} ${esc(d.title)} / ${esc(t.label)}<br><b>To:</b> ${esc(p.id)} ${esc(p.name)}<br><b>Pin capability:</b> ${esc(p.caps.join(", "))}<br><b>Description:</b> ${esc(p.desc)}</p>`;highlight({wire:w.id})}
function clearHighlight(){document.querySelectorAll(".wire").forEach(n=>n.classList.remove("dim"));document.querySelectorAll(".device-card").forEach(n=>n.classList.remove("fade"));document.querySelectorAll(".pin-card").forEach(n=>n.classList.remove("highlight"))}
function highlight(sel){clearHighlight();document.querySelectorAll(".wire").forEach(n=>n.classList.add("dim"));document.querySelectorAll(".device-card").forEach(n=>n.classList.add("fade"));let list=[];if(sel.wire)list=wires.filter(w=>w.id===sel.wire);if(sel.pin)list=wires.filter(w=>w.pinId===sel.pin);if(sel.device)list=wires.filter(w=>w.deviceId===sel.device);list.forEach(w=>{document.querySelector(`.wire[data-id="${CSS.escape(w.id)}"]`)?.classList.remove("dim");document.querySelector(`.pin-row[data-id="${CSS.escape(w.pinId)}"] .pin-card`)?.classList.add("highlight");document.querySelector(`.device-group[data-id="${CSS.escape(w.deviceId)}"] .device-card`)?.classList.remove("fade")})}
function filterMatches(w){const q=document.getElementById("search").value.trim().toLowerCase(),cat=document.getElementById("category").value,cap=document.getElementById("capability").value,conn=document.getElementById("connector").value,d=deviceById(w.deviceId),t=d.terminals.find(x=>x.id===w.terminalId),p=pinById(w.pinId),text=`${w.id} ${w.net} ${w.cap} ${d.id} ${d.category} ${d.family} ${d.title} ${d.type} ${t.label} ${p.id} ${p.name} ${p.caps.join(" ")} ${p.desc} ${p.connector}`.toLowerCase();const catOk=cat==="all"||d.category===cat,connOk=conn==="all"||p.connector===conn,capOk=cap==="all"||w.cap===cap||p.caps.includes(cap)||(cap==="DI"&&(p.caps.includes("DI")||p.caps.includes("FREQ")))||(cap==="DO"&&(p.caps.includes("DO")||p.caps.includes("HSD")||p.caps.includes("LSD")))||(cap==="CAN"&&(p.caps.includes("CAN")||p.caps.includes("LIN")));return catOk&&connOk&&capOk&&(!q||text.includes(q))}
function applyFilters(){clearHighlight();const vw=new Set(),vd=new Set(),vp=new Set();wires.forEach(w=>{if(filterMatches(w)){vw.add(w.id);vd.add(w.deviceId);vp.add(w.pinId)}});document.querySelectorAll(".wire").forEach(n=>n.classList.toggle("hidden",!vw.has(n.dataset.id)));document.querySelectorAll(".wire-label").forEach(n=>n.classList.toggle("hidden",!vw.has(n.dataset.wire)));document.querySelectorAll(".device-group").forEach(n=>n.classList.toggle("hidden",!vd.has(n.dataset.id)));document.querySelectorAll(".pin-row").forEach(n=>n.classList.toggle("hidden",!vp.has(n.dataset.id)));renderMiniNet([...vw])}
function renderMiniNet(ids){const set=new Set(ids);document.querySelector("#miniNet tbody").innerHTML=wires.filter(w=>set.has(w.id)).map(w=>{const d=deviceById(w.deviceId),t=d.terminals.find(x=>x.id===w.terminalId),p=pinById(w.pinId);return `<tr><td><b>${esc(w.id)}</b><br>${esc(w.net)}</td><td>${esc(d.id)} ${esc(d.title)}<br><span style="color:#64748b">${esc(t.label)}</span></td><td>${esc(p.id)}<br><b>${esc(p.name)}</b></td></tr>`}).join("");document.getElementById("statsPill").textContent=`${ids.length} wires • ${flatPins.length} pins • ${devices.length} devices`}
function renderTables(){document.getElementById("pinTable").innerHTML=`<thead><tr><th>Pin</th><th>Name</th><th>Capabilities</th><th>Description</th><th>Mapped terminals</th></tr></thead><tbody>${flatPins.map(p=>{const mapped=wires.filter(w=>w.pinId===p.id).map(w=>{const d=deviceById(w.deviceId),t=d.terminals.find(x=>x.id===w.terminalId);return `${d.id} ${d.title} / ${t.label}`}).join("<br>")||"—";return `<tr><td><b>${esc(p.id)}</b></td><td>${esc(p.name)}</td><td>${p.caps.map(c=>`<b>${esc(c)}</b>`).join(", ")}</td><td>${esc(p.desc)}</td><td>${mapped}</td></tr>`}).join("")}</tbody>`;document.getElementById("deviceTable").innerHTML=`<thead><tr><th>ID</th><th>Category</th><th>Family</th><th>Type</th><th>Terminals → pins</th><th>Helper</th></tr></thead><tbody>${devices.map(d=>{const hk=helperKeyForDevice(d);return `<tr><td><b>${esc(d.id)}</b></td><td>${esc(d.category)}</td><td>${esc(d.family)}</td><td>${esc(d.title)}<br><span style="color:#64748b">${esc(d.type)}</span></td><td>${d.terminals.map(t=>`${esc(t.label)} → <b>${esc(t.pin)}</b> (${esc(t.cap)})`).join("<br>")}</td><td><b>${esc(WIRING_HELPERS[hk].title)}</b></td></tr>`}).join("")}</tbody>`;document.getElementById("netlistTable").innerHTML=`<thead><tr><th>Wire</th><th>Device terminal</th><th>ECU pin</th><th>Capability</th><th>Net</th></tr></thead><tbody>${wires.map(w=>{const d=deviceById(w.deviceId),t=d.terminals.find(x=>x.id===w.terminalId),p=pinById(w.pinId);return `<tr><td><b>${esc(w.id)}</b></td><td>${esc(d.id)} ${esc(d.title)} / ${esc(t.label)}</td><td><b>${esc(p.id)}</b> ${esc(p.name)}</td><td><b>${esc(w.cap)}</b></td><td>${esc(w.net)}</td></tr>`}).join("")}</tbody>`;document.getElementById("helperTable").innerHTML=`<thead><tr><th>Type</th><th>Required ECU capability</th><th>Typical wiring</th><th>Electrical verification to perform</th></tr></thead><tbody>${Object.values(WIRING_HELPERS).map(h=>`<tr><td><b>${esc(h.group)} — ${esc(h.title)}</b></td><td>${h.caps.map(c=>`<b>${esc(c)}</b>`).join(", ")}</td><td><ul style="margin:0;padding-left:18px">${h.wiring.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></td><td><ul style="margin:0;padding-left:18px">${h.checks.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></td></tr>`).join("")}</tbody>`}

function capChipHTML(cap){return `<span class="print-chip" style="background:${capColor(cap)}">${esc(cap)}</span>`}
function normalizedDataForEcu(ecu){
 const fps=[];
 ecu.connectors.forEach(conn=>conn.pins.forEach(raw=>fps.push({...normalizePin(raw,conn)})));
 const devs=ecu.devices.map(normalizeDevice);
 const ws=[];
 devs.forEach(d=>d.terminals.forEach(t=>{
  const p=fps.find(x=>x.id===t.pin);
  if(p) ws.push({deviceId:d.id,terminalId:t.id,pinId:t.pin,cap:t.cap||p.caps[0],net:t.net||t.label});
 }));
 return {pins:fps,devices:devs,wires:ws};
}
function printDeviceCard(d){
 const hk=helperKeyForDevice(d);
 const terminals=d.terminals.map(t=>`${esc(t.label)} → ${esc(t.pin)} (${esc(t.cap)})`).join("<br>");
 return `<div class="print-card"><b>${esc(d.id)} — ${esc(d.title)}</b><small>${esc(d.type)} • ${esc(d.family)}</small><small>${terminals}</small><small><b>Helper:</b> ${esc(WIRING_HELPERS[hk].title)}</small></div>`;
}
function printSvgText(x,y,text,cls="",anchor="start"){
 return `<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}">${esc(text)}</text>`;
}
function renderPrintSchematic(ecu){
 const data=normalizedDataForEcu(ecu);
 const pins=data.pins;
 const devs=data.devices;
 const wires=data.wires;
 const W=1500;
 const leftX=24, devW=250, ecuX=560, ecuW=380, rightX=1226, top=72;
 const pinPitch=22, pinH=17, pinW=164;
 const leftPins=pins.filter(p=>p.side==="left");
 const rightPins=pins.filter(p=>p.side==="right");
 const sensors=devs.filter(d=>d.category==="sensor");
 const actuators=devs.filter(d=>d.category==="actuator");
 const maxPinN=Math.max(leftPins.length,rightPins.length,1);
 const deviceHeight=d=>Math.max(42,32+d.terminals.length*11);
 const sideHeight=list=>list.reduce((s,d)=>s+deviceHeight(d)+6,0);
 const H=Math.max(650,top+maxPinN*pinPitch+60,top+sideHeight(sensors)+50,top+sideHeight(actuators)+50);

 const pMap={};
 leftPins.forEach((p,i)=>pMap[p.id]={...p,x:ecuX+18,y:top+i*pinPitch});
 rightPins.forEach((p,i)=>pMap[p.id]={...p,x:ecuX+ecuW-pinW-18,y:top+i*pinPitch});

 const dMap={};
 function placeDevices(list,x){
   let y=top;
   list.forEach(d=>{
    const h=deviceHeight(d);
    const dd={...d,x,y,w:devW,h,terminals:d.terminals.map((t,i)=>({...t,y:32+i*11}))};
    dMap[d.id]=dd;
    y+=h+6;
   });
 }
 placeDevices(sensors,leftX);
 placeDevices(actuators,rightX);

 const wireIdsLeft=wires.filter(w=>dMap[w.deviceId]?.category==="sensor").map(w=>w.deviceId+"."+w.terminalId);
 const wireIdsRight=wires.filter(w=>dMap[w.deviceId]?.category==="actuator").map(w=>w.deviceId+"."+w.terminalId);
 function termPoint(d,t){return {x:d.category==="sensor"?d.x+d.w:d.x,y:d.y+t.y};}
 function pinPoint(p){return {x:p.side==="left"?ecuX:ecuX+ecuW,y:p.y};}
 function laneX(w){
   const id=w.deviceId+"."+w.terminalId;
   if(dMap[w.deviceId].category==="sensor"){
    const start=leftX+devW+18, end=ecuX-18;
    const idx=wireIdsLeft.indexOf(id), gap=wireIdsLeft.length<=1?0:(end-start)/(wireIdsLeft.length-1);
    return start+idx*gap;
   }
   const start=ecuX+ecuW+18, end=rightX-18;
   const idx=wireIdsRight.indexOf(id), gap=wireIdsRight.length<=1?0:(end-start)/(wireIdsRight.length-1);
   return start+idx*gap;
 }

 let out=`<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
 <style>
  text{font-family:Inter,Segoe UI,Arial,sans-serif}
  .ttl{font-size:16px;font-weight:900;fill:#0f172a}
  .sub{font-size:8px;font-weight:800;fill:#64748b}
  .zone{fill:#f8fafc;stroke:#cbd5e1;stroke-width:1}
  .ecu{fill:#111827;stroke:#020617;stroke-width:1.3}
  .bank{fill:#1e293b;stroke:#334155;stroke-width:.8}
  .dev{fill:#fff;stroke:#94a3b8;stroke-width:1}
  .dev.sensor{stroke:#93c5fd}.dev.actuator{stroke:#fca5a5}
  text{stroke:none}
  .pin{fill:#f8fafc;stroke:#cbd5e1;stroke-width:.8}
  .pno{font-size:6.5px;font-weight:850;fill:#64748b}
  .pname{font-size:8px;font-weight:850;fill:#0f172a}
  .cap{font-size:6.2px;font-weight:900;fill:#fff}
  .devt{font-size:8px;font-weight:850;fill:#0f172a}
  .devs{font-size:6.5px;font-weight:700;fill:#64748b}
  .term{font-size:5.4px;font-weight:400;fill:#475569;stroke:none}
  .wire{fill:none;stroke-width:1.05;stroke-linecap:round;stroke-linejoin:round}
  .power{stroke:${CAP_COLORS.PWR}}.ground{stroke:${CAP_COLORS.GND}}.analog{stroke:${CAP_COLORS.AI}}.res{stroke:${CAP_COLORS.RES}}.digital{stroke:${CAP_COLORS.DI}}.output{stroke:${CAP_COLORS.DO}}.pwm{stroke:${CAP_COLORS.PWM}}.ao{stroke:${CAP_COLORS.AO}}.comms{stroke:${CAP_COLORS.CAN}}.ret{stroke:${CAP_COLORS.RET}}.ethernet{stroke:${CAP_COLORS.ETH}}.sent{stroke:${CAP_COLORS.SENT}}
 </style>
 ${printSvgText(20,26,"Sensors / Inputs","ttl")}
 ${printSvgText(ecuX,26,ecu.name,"ttl")}
 ${printSvgText(rightX,26,"Actuators / Outputs","ttl")}
 ${printSvgText(ecuX,42,ecu.role,"sub")}
 <rect x="12" y="50" width="280" height="${H-70}" rx="10" class="zone"/>
 <rect x="${rightX-14}" y="50" width="280" height="${H-70}" rx="10" class="zone"/>
 <rect x="${ecuX}" y="50" width="${ecuW}" height="${H-70}" rx="14" class="ecu"/>
 <rect x="${ecuX+10}" y="${top-18}" width="${pinW+20}" height="${Math.max(1,leftPins.length)*pinPitch+10}" rx="8" class="bank"/>
 <rect x="${ecuX+ecuW-pinW-30}" y="${top-18}" width="${pinW+20}" height="${Math.max(1,rightPins.length)*pinPitch+10}" rx="8" class="bank"/>`;

 // wires first
 wires.forEach(w=>{
   const d=dMap[w.deviceId], t=d?.terminals.find(x=>x.id===w.terminalId), p=pMap[w.pinId];
   if(!d||!t||!p) return;
   const tp=termPoint(d,t), pp=pinPoint(p), lx=laneX(w);
   const path=d.category==="sensor"?`M ${tp.x} ${tp.y} H ${lx} V ${pp.y} H ${pp.x}`:`M ${pp.x} ${pp.y} H ${lx} V ${tp.y} H ${tp.x}`;
   out+=`<path d="${path}" class="wire ${wireClass(w.cap)}"/>`;
 });

 // devices
 devs.forEach(d0=>{
   const d=dMap[d0.id];
   if(!d) return;
   out+=`<rect x="${d.x}" y="${d.y}" width="${d.w}" height="${d.h}" rx="7" class="dev ${d.category}"/>`;
   out+=printSvgText(d.x+8,d.y+13,fitText(d.id+"  "+d.title,32),"devt");
   out+=printSvgText(d.x+8,d.y+23,fitText(d.type+" • "+d.family,36),"devs");
   d.terminals.forEach(t=>{
    const pt=termPoint(d,t);
    out+=`<circle cx="${pt.x}" cy="${pt.y}" r="2.2" fill="#fff" stroke="#334155" stroke-width=".6"/>`;
    out+=`<text x="${d.category==="sensor"?pt.x-5:pt.x+5}" y="${pt.y+2}" text-anchor="${d.category==="sensor"?"end":"start"}" class="term" font-weight="400" font-size="5.4" fill="#475569" stroke="none">${esc(fitText(t.label,16))}</text>`;
   });
 });

 // pins
 pins.forEach(p0=>{
   const p=pMap[p0.id]; if(!p) return;
   const rx=p.x, ry=p.y-pinH/2;
   out+=`<rect x="${rx}" y="${ry}" width="${pinW}" height="${pinH}" rx="4" class="pin"/>`;
   out+=`<circle cx="${p.side==="left"?ecuX:ecuX+ecuW}" cy="${p.y}" r="2.3" fill="#fff" stroke="#111827" stroke-width=".7"/>`;
   out+=printSvgText(rx+6,ry+7,fitText(p.id,8),"pno");
   out+=printSvgText(rx+6,ry+15,fitText(p.name,18),"pname");
   let cx=rx+pinW-4;
   p.caps.slice(0,3).reverse().forEach(cap=>{
    const cw=Math.max(18,cap.length*5+7); cx-=cw;
    out+=`<rect x="${cx}" y="${ry+3}" width="${cw}" height="11" rx="4" fill="${capColor(cap)}"/>`;
    out+=`<text x="${cx+cw/2}" y="${ry+11}" text-anchor="middle" class="cap">${esc(cap)}</text>`;
    cx-=3;
   });
 });
 out+=`</svg>`;
 return out;
}
function renderPrintReport(){
 const root=document.getElementById("printReport");
 if(!root) return;
 root.innerHTML=ecuModels.map(ecu=>{
  const data=normalizedDataForEcu(ecu);
  const connectorList=ecu.connectors.map(c=>`${esc(c.id)} ${c.side}: ${c.pins.length} pins`).join(" • ");
  return `<article class="print-page">
    <div class="print-header">
      <div><h2>${esc(ecu.id)} — ${esc(ecu.name)}</h2><p>${esc(ecu.role)}</p></div>
      <div class="print-meta">${connectorList}<br>${data.devices.length} devices • ${data.wires.length} direct wires • ${data.pins.length} pins</div>
    </div>
    <div class="print-schematic">${renderPrintSchematic(ecu)}</div>
    <div class="print-checks">
      <div><b>Input checks:</b> voltage/current range, pull-up/pull-down, sensor supply current, ground reference, open/short diagnostics.</div>
      <div><b>Output checks:</b> load current, inrush, PWM frequency, flyback/clamp, fuse and cable section, thermal limits.</div>
      <div><b>Network/safety checks:</b> CAN/LIN termination, topology, wake/sleep, timeout handling, safe state and feedback plausibility.</div>
    </div>
  </article>`;
 }).join("");
}
function applyZoom(){scaler.style.transform=`scale(${zoom})`;const h=Number(svg.getAttribute("height"))||1500;scaler.style.width=(LAYOUT.canvasW*zoom)+"px";scaler.style.height=(h*zoom)+"px";document.getElementById("zoomRange").value=Math.round(zoom*100);document.getElementById("zoomReset").textContent=Math.round(zoom*100)+"%"}
function setZoom(v){zoom=Math.min(1.8,Math.max(.45,v));applyZoom()}
function zoomAtPointer(delta, clientX, clientY){
 const wrap=document.getElementById("diagramWrap");
 const oldZoom=zoom;
 const rect=wrap.getBoundingClientRect();
 const ox=clientX-rect.left, oy=clientY-rect.top;
 const contentX=(wrap.scrollLeft+ox)/oldZoom;
 const contentY=(wrap.scrollTop+oy)/oldZoom;
 setZoom(oldZoom+delta);
 wrap.scrollLeft=contentX*zoom-ox;
 wrap.scrollTop=contentY*zoom-oy;
}
function togglePanel(){const wb=document.getElementById("workbench");wb.classList.toggle("panel-collapsed");document.getElementById("togglePanel").textContent=wb.classList.contains("panel-collapsed")?"Show panel":"Hide panel"}
document.getElementById("search").addEventListener("input",applyFilters);document.getElementById("category").addEventListener("change",applyFilters);document.getElementById("capability").addEventListener("change",applyFilters);document.getElementById("connector").addEventListener("change",applyFilters);
document.getElementById("reset").addEventListener("click",()=>{resetFiltersOnly();renderMiniNet(wires.map(w=>w.id));inspector.innerHTML="Click a device, ECU pin, or wire to inspect it."});
document.getElementById("print").addEventListener("click",()=>window.print());document.getElementById("togglePanel").addEventListener("click",togglePanel);document.getElementById("togglePanelInside").addEventListener("click",togglePanel);
document.getElementById("zoomOut").addEventListener("click",()=>setZoom(zoom-.1));document.getElementById("zoomIn").addEventListener("click",()=>setZoom(zoom+.1));document.getElementById("zoomReset").addEventListener("click",()=>setZoom(1));document.getElementById("zoomRange").addEventListener("input",e=>setZoom(Number(e.target.value)/100));
document.getElementById("diagramWrap").addEventListener("wheel",e=>{e.preventDefault();zoomAtPointer(e.deltaY<0?.08:-.08,e.clientX,e.clientY)},{passive:false});
document.querySelectorAll(".tab").forEach(btn=>btn.addEventListener("click",()=>{document.querySelectorAll(".tab").forEach(b=>b.classList.remove("active"));document.querySelectorAll(".table-panel").forEach(p=>p.classList.remove("active"));btn.classList.add("active");document.getElementById(btn.dataset.tab).classList.add("active")}));
svg.addEventListener("click",clearHighlight);
renderAll();
renderPrintReport();
"""


def render_html(ecu_models: list[dict]) -> str:
    models_json = json.dumps(ecu_models, ensure_ascii=False).replace("</script", "<\\/script")
    script = SCRIPT_PRE + "\nconst ecuModels=" + models_json + ";\n" + SCRIPT_POST
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1" />\n'
        '<title>Professional Multi-ECU Wiring Viewer — Tractor E/E Architecture</title>\n'
        "<style>" + HEAD_CSS + "</style>\n"
        "</head>\n<body>\n" + BODY_HTML + "\n<script>" + script + "</script>\n</body>\n</html>\n"
    )


def main() -> int:
    parser = make_argparser(
        "Generate Professional Multi-ECU Wiring Viewer — adapts the interactive SVG wiring "
        "template (search/zoom/inspect/print-to-PDF) to the real architecture export, with "
        "every pin (wired and unconnected/spare) visible per ECU connector.",
        input_help="Physical architecture export JSON.",
    )
    parser.set_defaults(prefer_physical=True)
    args = parser.parse_args()
    root, cfg, arch, arch_path, outdir = cli_context(args)

    ecu_models = [build_ecu_model(ecu) for ecu in iter_ecus(arch)]

    out = outdir / "professional_multi_ecu_wiring.html"
    out.write_text(render_html(ecu_models), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
