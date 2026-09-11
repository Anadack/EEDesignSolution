#!/usr/bin/env python3
"""Generate an interactive clickable arborescence HTML from an AM architecture JSON.

Reads:
  exports/example_architecture.json  (fallback: example_physical_architecture.json)

Output:
  exports/architecture_tree.html

Shows the full object hierarchy:
  Architecture
  ├── Systems → Devices (Sensors/Actuators) → Device Pins → Signals
  └── ECUs    → Connectors                 → ECU Pins    → Signals

Click any mapped pin to cross-navigate to its counterpart.
Search to filter nodes. Expand / collapse all. Toggle free pins.
Fully generic: every ECU, system, device, signal is derived from the JSON.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from html_overflow_guard import OVERFLOW_GUARD_CSS

# ── Helpers ───────────────────────────────────────────────────────────────────

def esc(v: Any) -> str:
    return (
        str("" if v is None else v)
        .replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )

def slug(v: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", str(v))

def find_base() -> Path:
    s = Path(__file__).resolve().parent
    return s.parent if (s.parent / "exports").exists() else s

def load_json(p: Path) -> dict[str, Any]:
    d = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise ValueError("Top-level JSON must be an object")
    return d

def get_arch(data: dict[str, Any]) -> dict[str, Any]:
    a = data.get("architecture", data)
    if not isinstance(a, dict):
        raise ValueError("architecture must be an object")
    return a

# ── Color palettes (auto-extends at runtime for unknown keys) ─────────────────

_IFACE_COLOR: dict[str, str] = {
    "ANALOG": "#2563eb", "PWM": "#d97706", "DIGITAL": "#16a34a",
    "SENT": "#9333ea",   "CAN": "#dc2626", "LIN":    "#ea580c",
    "ETHERNET": "#0891b2", "POWER": "#64748b", "GROUND": "#334155",
}
_PRIO_COLOR: dict[str, str] = {
    "LOW": "#64748b", "MEDIUM": "#3b82f6", "HIGH": "#f59e0b", "CRITICAL": "#ef4444",
}
_SAFETY_COLOR: dict[str, str] = {"QM": "#16a34a", "SAFETY_RELATED": "#ea580c"}
_ROLE_COLOR:   dict[str, str] = {
    "INPUT": "#2563eb", "OUTPUT": "#d97706", "INOUT": "#9333ea",
    "SUPPLY": "#64748b", "GROUND": "#334155",
}
_VARIANT_COLOR: dict[str, str] = {
    "SMALL": "#7c3aed", "MEDIUM": "#0891b2", "LARGE": "#be185d",
}
_TYPE_COLOR: dict[str, str] = {"SENSOR": "#16a34a", "ACTUATOR": "#d97706"}

_FALLBACK: list[str] = [
    "#b91c1c","#1d4ed8","#047857","#7e22ce","#b45309","#0f766e","#be185d","#4338ca",
]

def _col(d: dict[str, str], key: str) -> str:
    k = str(key).upper()
    if k not in d:
        d[k] = _FALLBACK[len(d) % len(_FALLBACK)]
    return d[k]

def _bdg(text: str, color: str) -> str:
    if not text:
        return ""
    return (
        f'<span class="bdg" style="color:{color};background:{color}18;'
        f'border:1px solid {color}44">{esc(text)}</span>'
    )

# ── Signal index ──────────────────────────────────────────────────────────────

def build_index(arch: dict[str, Any]) -> dict[str, dict]:
    """Build a two-way cross-reference index: signal_name -> {ecu:[], device:[]}."""
    idx: dict[str, dict] = {}

    # ECU side
    for ecu in arch.get("ecus", []):
        if not isinstance(ecu, dict):
            continue
        en = str(ecu.get("name", ""))
        for pin in ecu.get("pins", []):
            if not isinstance(pin, dict) or not pin.get("is_occupied"):
                continue
            sig = pin.get("signal")
            if not isinstance(sig, dict) or not sig.get("name"):
                continue
            sn    = str(sig["name"])
            conn  = str(pin.get("connector", ""))
            num   = str(pin.get("physical_number", ""))
            entry = idx.setdefault(sn, {"signal": sig, "ecu": [], "device": []})
            entry["ecu"].append({
                "id":              f"ep_{slug(en)}_{slug(conn)}_{slug(num)}",
                "ecu":             en,
                "connector":       conn,
                "physical_number": num,
                "pin_name":        str(pin.get("name", "")),
                "type":            str(pin.get("type", "")),
                "role":            str(pin.get("role", "")),
            })

    # System / device side
    for sys in arch.get("systems", []):
        if not isinstance(sys, dict):
            continue
        sys_name = str(sys.get("name", ""))
        for dev in sys.get("devices", []):
            if not isinstance(dev, dict):
                continue
            dn = str(dev.get("name", ""))
            for pin in dev.get("pins", []):
                if not isinstance(pin, dict):
                    continue
                sig = pin.get("signal")
                if not isinstance(sig, dict) or not sig.get("name"):
                    continue
                sn  = str(sig["name"])
                num = str(pin.get("number", ""))
                entry = idx.setdefault(sn, {"signal": sig, "ecu": [], "device": []})
                entry["device"].append({
                    "id":       f"dp_{slug(dn)}_{slug(num)}",
                    "device":   dn,
                    "number":   num,
                    "pin_name": str(pin.get("name", "")),
                    "role":     str(pin.get("role", "")),
                    "system":   sys_name,
                })

    return idx

# ── Jump link ─────────────────────────────────────────────────────────────────

def _jump(node_id: str, label: str) -> str:
    return (
        f'<a class="xref" href="#{node_id}" '
        f'onclick="return doJump(\'{node_id}\')">{esc(label)}</a>'
    )

# ── Device-side rendering ─────────────────────────────────────────────────────

def _render_device_pin(pin: dict, device_name: str, idx: dict) -> str:
    if not isinstance(pin, dict):
        return ""
    num   = str(pin.get("number", "?"))
    pname = str(pin.get("name", ""))
    role  = str(pin.get("role", ""))
    sig   = pin.get("signal")
    sn    = str(sig["name"]) if isinstance(sig, dict) and sig.get("name") else ""
    pin_id = f"dp_{slug(device_name)}_{slug(num)}"

    parts = [
        f'<span class="pnum">#{num}</span>',
        f'<span class="pname">{esc(pname)}</span>',
        _bdg(role, _col(_ROLE_COLOR, role)),
    ]
    if sn:
        iface = str(sig.get("interface_type", "")) if isinstance(sig, dict) else ""
        if iface:
            parts.append(_bdg(iface, _col(_IFACE_COLOR, iface)))
        ecu_entries = idx.get(sn, {}).get("ecu", [])
        if ecu_entries:
            e = ecu_entries[0]
            parts.append(_jump(e["id"], f"&#8594; {e['ecu']} {e['connector']}/{e['physical_number']}"))

    cls  = "prow pocc" if sn else "prow pfree"
    data = f'data-sig="{esc(sn)}"' if sn else ""
    return f'<li class="{cls}" id="{pin_id}" {data}>\n  {"".join(parts)}\n</li>'


def _render_device(dev: dict, idx: dict) -> str:
    if not isinstance(dev, dict):
        return ""
    dn     = str(dev.get("name", "Device"))
    dt     = str(dev.get("type", ""))
    prio   = str(dev.get("priority", ""))
    safety = str(dev.get("safety", ""))
    pins   = [p for p in dev.get("pins", []) if isinstance(p, dict)]
    mapped = sum(1 for p in pins if isinstance(p.get("signal"), dict))

    icon   = "&#128225;" if dt == "SENSOR" else "&#128295;"  # 📡 / 🔧
    tc     = _col(_TYPE_COLOR, dt)
    summary = (
        f'{icon} <span class="nname">{esc(dn)}</span>'
        f'{_bdg(dt, tc)}'
        f'{_bdg(prio, _col(_PRIO_COLOR, prio))}'
        f'{_bdg(safety.replace("_"," "), _col(_SAFETY_COLOR, safety))}'
        f'<span class="nmeta">{mapped}/{len(pins)} pins mapped</span>'
    )
    pin_html = "\n".join(_render_device_pin(p, dn, idx) for p in pins)
    return (
        f'<details class="nd nd-device nd-{dt.lower()}" data-name="{esc(dn)}">\n'
        f'  <summary>{summary}</summary>\n'
        f'  <ul class="plist">{pin_html}</ul>\n'
        f'</details>\n'
    )


def _render_system(sys: dict, idx: dict) -> str:
    if not isinstance(sys, dict):
        return ""
    sn     = str(sys.get("name", "System"))
    level  = str(sys.get("system_level", ""))
    prio   = str(sys.get("priority", ""))
    safety = str(sys.get("safety", ""))
    devs   = [d for d in sys.get("devices", []) if isinstance(d, dict)]
    total  = sum(len(d.get("pins", [])) for d in devs)
    mapped = sum(
        1 for d in devs
        for p in d.get("pins", []) if isinstance(p, dict) and isinstance(p.get("signal"), dict)
    )
    devs_html = "\n".join(_render_device(d, idx) for d in devs)
    summary = (
        f'&#9881; <span class="nname">{esc(sn)}</span>'
        + (_bdg(level, "#1d4ed8") if level else "")
        + _bdg(prio, _col(_PRIO_COLOR, prio))
        + _bdg(safety.replace("_"," "), _col(_SAFETY_COLOR, safety))
        + f'<span class="nmeta">{len(devs)} device{"s" if len(devs)!=1 else ""} &middot; {mapped}/{total} pins mapped</span>'
    )
    return (
        f'<details class="nd nd-system" data-name="{esc(sn)}" open>\n'
        f'  <summary>{summary}</summary>\n'
        f'  <div class="nch">{devs_html}</div>\n'
        f'</details>\n'
    )

# ── ECU-side rendering ────────────────────────────────────────────────────────

def _render_ecu_pin(pin: dict, ecu_name: str, idx: dict) -> str:
    if not isinstance(pin, dict):
        return ""
    conn  = str(pin.get("connector", ""))
    num   = str(pin.get("physical_number", "?"))
    pname = str(pin.get("name", ""))
    role  = str(pin.get("role", ""))
    ptype = str(pin.get("type", ""))
    occ   = bool(pin.get("is_occupied"))
    sig   = pin.get("signal") if isinstance(pin.get("signal"), dict) else None
    dp_obj= pin.get("device_pin") if isinstance(pin.get("device_pin"), dict) else None
    sn    = str(sig["name"]) if sig and sig.get("name") else ""
    pin_id = f"ep_{slug(ecu_name)}_{slug(conn)}_{slug(num)}"

    parts = [
        f'<span class="pdot">{"&#9679;" if occ else "&#9675;"}</span>',
        f'<span class="pnum">#{num}</span>',
        f'<span class="pname">{esc(pname)}</span>',
        _bdg(ptype, _col(_IFACE_COLOR, ptype)) if ptype else "",
        _bdg(role,  _col(_ROLE_COLOR, role))  if role  else "",
    ]
    if sn:
        parts.append(f'<strong class="signame">{esc(sn)}</strong>')
        dev_entries = idx.get(sn, {}).get("device", [])
        if dev_entries:
            d = dev_entries[0]
            parts.append(_jump(d["id"], f"&#8592; {d['device']}/{d['number']}"))

    cls  = "prow pocc" if occ else "prow pfree"
    data = f'data-sig="{esc(sn)}"' if sn else ""
    return f'<li class="{cls}" id="{pin_id}" {data}>\n  {"".join(p for p in parts if p)}\n</li>'


def _render_connector(conn_name: str, pins: list, ecu_name: str, idx: dict) -> str:
    occ  = [p for p in pins if isinstance(p, dict) and p.get("is_occupied")]
    free = [p for p in pins if isinstance(p, dict) and not p.get("is_occupied")]

    occ_html  = "\n".join(_render_ecu_pin(p, ecu_name, idx) for p in occ)
    free_html = "\n".join(_render_ecu_pin(p, ecu_name, idx) for p in free)

    free_section = (
        f'<details class="nd nd-free">\n'
        f'  <summary>Free pins <span class="nmeta">({len(free)})</span></summary>\n'
        f'  <ul class="plist plist-free">{free_html}</ul>\n'
        f'</details>'
    ) if free else ""

    summary = (
        f'&#128268; <span class="nname">{esc(conn_name)}</span>'
        f'<span class="nmeta">{len(occ)} occupied &middot; {len(free)} free</span>'
    )
    return (
        f'<details class="nd nd-conn" data-name="{esc(conn_name)}" open>\n'
        f'  <summary>{summary}</summary>\n'
        f'  <ul class="plist">{occ_html}</ul>\n'
        f'  {free_section}\n'
        f'</details>\n'
    )


def _render_ecu(ecu: dict, idx: dict) -> str:
    if not isinstance(ecu, dict):
        return ""
    en      = str(ecu.get("name", "ECU"))
    variant = str(ecu.get("variant", ""))
    prio    = str(ecu.get("priority", ""))
    safety  = str(ecu.get("safety", ""))
    addrs   = ecu.get("can_addresses", [])
    can_str = " ".join(str(a) for a in (addrs if isinstance(addrs, list) else []))
    pins    = [p for p in ecu.get("pins", []) if isinstance(p, dict)]
    n_occ   = sum(1 for p in pins if p.get("is_occupied"))

    by_conn: dict[str, list] = defaultdict(list)
    for p in pins:
        by_conn[str(p.get("connector", "X?"))].append(p)

    conns_html = "\n".join(
        _render_connector(cn, by_conn[cn], en, idx)
        for cn in sorted(by_conn)
    )
    vc = _col(_VARIANT_COLOR, variant)
    summary = (
        f'&#128421; <span class="nname">{esc(en)}</span>'
        f'{_bdg(variant, vc)}'
        f'{_bdg(prio, _col(_PRIO_COLOR, prio))}'
        f'{_bdg(safety.replace("_"," "), _col(_SAFETY_COLOR, safety))}'
        f'<span class="nmeta">CAN: {esc(can_str) or "&mdash;"} &middot; {len(pins)} pins ({n_occ} occupied)</span>'
    )
    return (
        f'<details class="nd nd-ecu" data-name="{esc(en)}">\n'
        f'  <summary>{summary}</summary>\n'
        f'  <div class="nch">{conns_html}</div>\n'
        f'</details>\n'
    )

# ── Full HTML page ────────────────────────────────────────────────────────────

def build_html(arch: dict[str, Any]) -> str:
    arch_name = str(arch.get("name", "Architecture"))
    prio      = str(arch.get("priority", ""))
    safety    = str(arch.get("safety", ""))
    ecus      = [e for e in arch.get("ecus", [])    if isinstance(e, dict)]
    systems   = [s for s in arch.get("systems", []) if isinstance(s, dict)]

    idx = build_index(arch)

    n_ecus    = len(ecus)
    n_sys     = len(systems)
    n_devs    = sum(len(s.get("devices", [])) for s in systems)
    n_sigs    = len(idx)
    total_ep  = sum(len(e.get("pins", [])) for e in ecus)
    total_occ = sum(1 for e in ecus for p in e.get("pins", [])
                    if isinstance(p, dict) and p.get("is_occupied"))

    systems_html = "\n".join(_render_system(s, idx) for s in systems)
    ecus_html    = "\n".join(_render_ecu(e, idx) for e in ecus)
    today        = date.today().strftime("%d/%m/%Y")

    # Serialise the index for the JS cross-nav engine (signal → {ecu[], device[]} IDs only)
    idx_js = json.dumps({
        k: {
            "ecu":    [{"id": x["id"], "label": f"{x['ecu']} {x['connector']}/{x['physical_number']}"} for x in v.get("ecu", [])],
            "device": [{"id": x["id"], "label": f"{x['device']}/{x['number']}"}                        for x in v.get("device", [])],
        }
        for k, v in idx.items()
    }, ensure_ascii=True)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>{esc(arch_name)} &mdash; Architecture Tree</title>
<style>
:root {{
  --bg:#070b12; --surface:#0f1622; --ink:#cfdaea; --muted:#6c83a2; --line:#233149;
  --surface2:#151e2e; --surface3:#1d2939; --surface4:#273548;
  --text:#cfdaea; --text-dim:#6c83a2; --border1:#233149; --border2:#2d3e5c;
  --cyan:#2ee6ff; --green:#2ee6a0; --amber:#ffb43d; --red:#ff5a78;
  --r:14px; --shadow:0 8px 30px rgba(0,0,0,.45);
  font-family:Aptos,"Segoe UI Variable","Inter",system-ui,sans-serif;
  font-size:14px; color:var(--ink);
}}
* {{ box-sizing:border-box; margin:0; padding:0 }}
body {{ background:var(--bg); color:var(--text); min-height:100vh }}

/* ── Header ── */
.hdr {{ background:linear-gradient(135deg,var(--surface2),var(--surface3)); color:var(--text); padding:28px 36px }}
.hdr h1 {{ font-size:clamp(1.4rem,3vw,2.2rem); font-weight:800; letter-spacing:-.03em }}
.hdr p  {{ color:var(--text-dim); margin-top:6px; font-size:.88rem }}

/* ── KPIs ── */
.kpis {{
  display:flex; gap:12px; padding:16px 36px; background:var(--surface);
  border-bottom:1px solid var(--border1); overflow-x:auto; flex-wrap:wrap;
}}
.kpi {{ flex:0 0 auto; padding:12px 18px; border-radius:12px; background:var(--surface2); border:1px solid var(--border1); min-width:110px }}
.kpi .lbl {{ font-size:.68rem; text-transform:uppercase; letter-spacing:.1em; color:var(--muted) }}
.kpi .val {{ font-size:1.6rem; font-weight:800; margin-top:2px }}

/* ── Toolbar ── */
.bar {{
  display:flex; gap:10px; padding:12px 36px; background:var(--surface);
  border-bottom:1px solid var(--border1); align-items:center; flex-wrap:wrap;
}}
.bar input {{
  flex:1; min-width:200px; max-width:400px; padding:8px 14px;
  border-radius:999px; border:1.5px solid var(--border1); background:var(--surface3);
  color:var(--text); font-size:.85rem; outline:none;
}}
.bar input:focus {{ border-color:var(--cyan); background:var(--surface4) }}
.bar button {{
  padding:7px 16px; border-radius:999px; border:1.5px solid var(--border1);
  background:var(--surface2); cursor:pointer; font-size:.82rem; font-weight:600; color:var(--text);
}}
.bar button:hover {{ background:var(--surface3); border-color:var(--cyan) }}
.bar .sep {{ color:var(--line); user-select:none; padding:0 4px }}
.bar .lbl-bar {{ font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em; color:var(--muted) }}

/* ── Tree container ── */
.tree {{ padding:20px 36px 40px }}

/* ── Top-level sections ── */
.section {{
  background:var(--surface); border:1px solid var(--border1); border-radius:var(--r);
  box-shadow:var(--shadow); margin-bottom:20px; overflow:hidden;
}}
.section > summary {{
  padding:16px 20px; font-size:1.02rem; font-weight:700;
  cursor:pointer; list-style:none; display:flex; align-items:center; gap:10px;
  background:var(--surface3); border-bottom:1px solid var(--border1); user-select:none;
}}
.section > summary::-webkit-details-marker {{ display:none }}
.section > summary::before {{ content:"&#9654;"; font-size:.55rem; color:var(--muted); transition:.15s }}
.section[open] > summary::before {{ transform:rotate(90deg) }}
.section-body {{ padding:12px 16px; display:flex; flex-direction:column; gap:6px }}

/* ── Nodes ── */
.nd {{ border-radius:10px; overflow:visible }}
.nd > summary {{
  padding:8px 12px; cursor:pointer; list-style:none;
  display:flex; align-items:center; gap:6px; flex-wrap:wrap;
  user-select:none; border-radius:10px; transition:background .12s; position:relative;
}}
.nd > summary::-webkit-details-marker {{ display:none }}
.nd > summary::before {{
  content:"&#9654;"; font-size:.5rem; color:var(--muted);
  margin-right:4px; transition:.15s; flex-shrink:0;
}}
.nd[open] > summary::before {{ transform:rotate(90deg) }}
.nd > summary:hover {{ background:var(--surface3) }}
.nd[open] > summary {{
  background:var(--surface2); border-radius:10px 10px 0 0;
  border-bottom:1px solid var(--border1);
}}
.nch {{ padding:6px 8px 6px 20px; display:flex; flex-direction:column; gap:4px }}

/* ── Node-type accent colours ── */
.nd-system[open] > summary  {{ background:var(--surface2); border-color:var(--border2) }}
.nd-sensor[open] > summary  {{ background:var(--surface2); border-color:var(--border2) }}
.nd-actuator[open] > summary{{ background:var(--surface2); border-color:var(--border2) }}
.nd-ecu[open] > summary     {{ background:var(--surface2); border-color:var(--border2) }}
.nd-conn[open] > summary    {{ background:var(--surface2); border-color:var(--border2) }}
.nd-free > summary          {{ color:var(--muted); font-size:.82rem }}

/* ── Node name / meta ── */
.nname {{ font-weight:700; font-size:.9rem }}
.nmeta {{ font-size:.73rem; color:var(--muted); margin-left:6px }}

/* ── Badges ── */
.bdg {{
  display:inline-flex; align-items:center; font-size:.65rem; font-weight:700;
  text-transform:uppercase; letter-spacing:.06em; padding:2px 7px;
  border-radius:999px; flex-shrink:0;
}}

/* ── Pin list ── */
.plist {{ list-style:none; padding:4px 0 4px 12px; display:flex; flex-direction:column; gap:2px }}
.plist-free {{ opacity:.55 }}
.prow {{
  display:flex; align-items:center; gap:6px; padding:5px 8px;
  border-radius:7px; flex-wrap:wrap; font-size:.79rem; transition:background .1s; cursor:default;
}}
.prow:hover {{ background:var(--surface3) }}
.prow[data-sig] {{ cursor:pointer }}
.pocc {{ }}
.pfree {{ color:var(--muted) }}
.pnum  {{ font-family:monospace; font-size:.75rem; color:var(--muted); min-width:30px }}
.pname {{ font-weight:600 }}
.pdot  {{ font-size:.65rem; min-width:12px }}
.signame {{ font-weight:700; font-size:.8rem }}

/* ── Cross-ref links ── */
a.xref {{
  color:var(--cyan); font-size:.72rem; font-weight:600; text-decoration:none;
  padding:1px 7px; border-radius:6px; border:1px solid rgba(46,230,255,0.25); background:rgba(46,230,255,0.08);
  white-space:nowrap;
}}
a.xref:hover {{ background:var(--cyan); color:#000 }}

/* ── Highlight animation ── */
.hl {{
  background:var(--surface4) !important; outline:2.5px solid var(--cyan);
  border-radius:8px; animation:pulse .8s ease 2;
}}
@keyframes pulse {{ 0%,100% {{ background:var(--surface4) }} 50% {{ background:var(--surface3) }} }}

/* ── Dimmed (search) ── */
.ndim {{ opacity:.12; pointer-events:none }}

/* ── Legend ── */
.legend {{
  display:flex; gap:12px; flex-wrap:wrap; padding:12px 36px;
  background:var(--surface); border-top:1px solid var(--border1);
  font-size:.75rem; color:var(--text-dim); align-items:center;
}}
.leg-item {{ display:flex; align-items:center; gap:5px }}
.leg-dot  {{ width:10px; height:10px; border-radius:50%; flex-shrink:0 }}
{OVERFLOW_GUARD_CSS}
</style>
</head>
<body>

<div class="hdr">
  <h1>{esc(arch_name)} &mdash; Architecture Tree</h1>
  <p>Interactive object hierarchy. Click any mapped pin to cross-navigate to its counterpart. Search to filter. Generated {today}.</p>
</div>

<div class="kpis">
  <div class="kpi"><div class="lbl">Systems</div>       <div class="val">{n_sys}</div></div>
  <div class="kpi"><div class="lbl">Devices</div>       <div class="val">{n_devs}</div></div>
  <div class="kpi"><div class="lbl">Signals Mapped</div><div class="val">{n_sigs}</div></div>
  <div class="kpi"><div class="lbl">ECUs</div>          <div class="val">{n_ecus}</div></div>
  <div class="kpi"><div class="lbl">Total ECU Pins</div><div class="val">{total_ep}</div></div>
  <div class="kpi"><div class="lbl">Allocated Pins</div><div class="val">{total_occ}</div></div>
</div>

<div class="bar">
  <span class="lbl-bar">Filter:</span>
  <input type="search" id="srch" placeholder="Search nodes, signals, ECU names&hellip;" oninput="doSearch(this.value)"/>
  <span class="sep">|</span>
  <button onclick="expandAll(true)">Expand all</button>
  <button onclick="expandAll(false)">Collapse all</button>
  <span class="sep">|</span>
  <button onclick="toggleFree()" id="btn-free">Hide free pins</button>
</div>

<div class="tree" id="tree">

  <details class="section" open>
    <summary>&#9881; Systems <span class="nmeta">({n_sys})</span></summary>
    <div class="section-body">
{systems_html}
    </div>
  </details>

  <details class="section" open>
    <summary>&#128421; ECUs <span class="nmeta">({n_ecus})</span></summary>
    <div class="section-body">
{ecus_html}
    </div>
  </details>

</div>

<div class="legend">
  <strong>Legend:</strong>
  <span class="leg-item"><span class="leg-dot" style="background:#16a34a"></span>Sensor</span>
  <span class="leg-item"><span class="leg-dot" style="background:#d97706"></span>Actuator</span>
  <span class="leg-item"><span class="leg-dot" style="background:#be185d"></span>ECU</span>
  <span class="leg-item"><span class="leg-dot" style="background:#7c3aed"></span>SMALL</span>
  <span class="leg-item"><span class="leg-dot" style="background:#0891b2"></span>MEDIUM</span>
  <span class="leg-item"><span class="leg-dot" style="background:#be185d"></span>LARGE</span>
  <span class="leg-item"><span class="leg-dot" style="background:#f59e0b"></span>HIGH priority</span>
  <span class="leg-item"><span class="leg-dot" style="background:#ef4444"></span>CRITICAL priority</span>
  <span class="leg-item">&#9679; = occupied &nbsp; &#9675; = free</span>
  <span class="leg-item">Click mapped pin to cross-navigate</span>
</div>

<script>
const SIGIDX = {idx_js};
let freePinsShown = true;

/* ── Cross-navigate to node ── */
function doJump(id) {{
  const el = document.getElementById(id);
  if (!el) return false;
  let p = el.parentElement;
  while (p) {{
    if (p.tagName === 'DETAILS') p.open = true;
    p = p.parentElement;
  }}
  el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
  el.classList.remove('hl');
  void el.offsetWidth;  // force reflow to restart animation
  el.classList.add('hl');
  setTimeout(() => el.classList.remove('hl'), 2400);
  return false;
}}

/* ── Click mapped pin row → jump to counterpart ── */
document.querySelectorAll('.prow[data-sig]').forEach(row => {{
  row.addEventListener('click', e => {{
    if (e.target.tagName === 'A') return;
    const sig = row.getAttribute('data-sig');
    const info = SIGIDX[sig];
    if (!info) return;
    const isEcu = row.id.startsWith('ep_');
    const targets = isEcu ? info.device : info.ecu;
    if (targets && targets.length > 0) doJump(targets[0].id);
  }});
}});

/* ── Search ── */
function doSearch(q) {{
  q = q.trim().toLowerCase();
  document.querySelectorAll('.nd').forEach(n => {{
    if (!q) {{ n.classList.remove('ndim'); return; }}
    const text = (n.textContent || '').toLowerCase();
    n.classList.toggle('ndim', !text.includes(q));
  }});
  if (!q) document.querySelectorAll('.prow').forEach(r => r.classList.remove('ndim'));
}}

/* ── Expand / collapse all ── */
function expandAll(open) {{
  document.querySelectorAll('details').forEach(d => d.open = open);
}}

/* ── Toggle free pins ── */
function toggleFree() {{
  freePinsShown = !freePinsShown;
  document.querySelectorAll('.nd-free').forEach(d => d.style.display = freePinsShown ? '' : 'none');
  document.querySelectorAll('.plist-free').forEach(ul => ul.style.display = freePinsShown ? '' : 'none');
  document.getElementById('btn-free').textContent = freePinsShown ? 'Hide free pins' : 'Show free pins';
}}
</script>
</body>
</html>"""

# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    base = find_base()
    json_path = base / "exports" / "example_architecture.json"
    if not json_path.exists():
        json_path = base / "exports" / "example_physical_architecture.json"
    if not json_path.exists():
        raise SystemExit(f"Missing file: {json_path}")

    output_path = base / "exports" / "architecture_tree.html"
    arch = get_arch(load_json(json_path))
    html = build_html(arch)
    output_path.write_text(html, encoding="utf-8")

    idx = build_index(arch)
    n_sys  = len([s for s in arch.get("systems", []) if isinstance(s, dict)])
    n_ecus = len([e for e in arch.get("ecus", [])    if isinstance(e, dict)])
    print(f"[OK] {output_path}  ({n_sys} systems, {n_ecus} ECUs, {len(idx)} signals mapped)")


if __name__ == "__main__":
    main()
