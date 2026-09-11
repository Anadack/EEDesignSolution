#!/usr/bin/env python3
"""ECU Communication bus diagram – fully generic.

Discovers all interface types from the exported JSON.  No hardcoded bus list:
if main.c adds new interfaces, ECUs, or signals the diagram updates
automatically."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from html_overflow_guard import OVERFLOW_GUARD_CSS

# Only true routable multi-node communication protocols are shown.
# Signal-level IO types (ANALOG, PWM, DIGITAL, SENT …) are not buses.
_BUS_TYPES: set[str] = {"CAN", "LIN", "ETHERNET", "ISOBUS", "FLEXRAY", "MOST", "K_LINE", "KLINE"}
_EXCLUDED_INTERFACES: set[str] = {"POWER", "GROUND", "RESERVED"}


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


def summarize_buses(arch: dict[str, Any]) -> list[dict[str, Any]]:
    """Discover all interface types from data and build one lane per type."""
    lanes: dict[str, dict[str, Any]] = {}
    lane_order: list[str] = []  # preserve discovery order
    ecus = arch.get("ecus", [])
    if not isinstance(ecus, list):
        return []

    for ecu in ecus:
        if not isinstance(ecu, dict):
            continue
        ecu_name = str(ecu.get("name", "ECU"))
        variant = str(ecu.get("variant", ""))
        can_addresses = ecu.get("can_addresses", [])
        if not isinstance(can_addresses, list):
            can_addresses = []
        participant_map: dict[str, dict[str, Any]] = {}
        pins = ecu.get("pins", [])
        if not isinstance(pins, list):
            pins = []
        for pin in pins:
            if not isinstance(pin, dict):
                continue
            signal = pin.get("signal")
            interface = ""
            signal_name = ""
            if isinstance(signal, dict):
                interface = str(signal.get("interface_type", pin.get("type", "")))
                signal_name = str(signal.get("name", ""))
            else:
                interface = str(pin.get("type", ""))
            if not interface or interface in _EXCLUDED_INTERFACES:
                continue
            if interface not in _BUS_TYPES:
                continue  # skip non-bus IO interface types
            # auto-register new interface type
            if interface not in lanes:
                lanes[interface] = {"name": interface, "participants": []}
                lane_order.append(interface)
            participant = participant_map.setdefault(
                interface,
                {
                    "ecu": ecu_name,
                    "variant": variant,
                    "can_addresses": [str(item) for item in can_addresses],
                    "connectors": set(),
                    "pins": [],
                    "signals": set(),
                },
            )
            connector_pin = f"{pin.get('connector', '')}/{pin.get('physical_number', '')}"
            participant["connectors"].add(str(pin.get("connector", "")))
            participant["pins"].append(connector_pin)
            if signal_name:
                participant["signals"].add(signal_name)

        for interface, participant in participant_map.items():
            participant["connectors"] = sorted(connector for connector in participant["connectors"] if connector)
            participant["pins"] = sorted(participant["pins"])
            participant["signals"] = sorted(participant["signals"])
            lanes[interface]["participants"].append(participant)

    for lane in lanes.values():
        lane["participants"].sort(key=lambda item: item["ecu"])
    return [lanes[name] for name in lane_order]


def render_chip_list(items: list[str], empty_text: str) -> str:
    if not items:
        return f'<span class="empty">{esc(empty_text)}</span>'
    return "".join(f'<span class="chip">{esc(item)}</span>' for item in items)


def render_bus_sections(bus_lanes: list[dict[str, Any]]) -> str:
    sections = []
    for lane in bus_lanes:
        bitrate = lane.get("bitrate", 0)
        total_sigs = lane.get("total_signals", 0)
        meta_parts = []
        if bitrate:
            meta_parts.append(f'{bitrate // 1000} kbit/s' if bitrate < 1_000_000 else f'{bitrate // 1_000_000} Mbit/s')
        if total_sigs:
            meta_parts.append(f'{total_sigs} signal{"s" if total_sigs != 1 else ""}')
        meta_str = " · ".join(meta_parts)

        participant_cards = []
        for participant in lane["participants"]:
            port_info = f' port {participant["port"]}' if participant.get("port") != "" and participant.get("port") is not None else ""
            pins_or_port = (render_chip_list(participant['pins'], 'No pin')
                            if participant['pins']
                            else f'<span class="muted">Bus port{port_info}</span>')
            participant_cards.append(
                f"""
          <article class="participant-card">
            <div class="participant-head">
              <div>
                <h3>{esc(participant['ecu'])}</h3>
                <p>{esc(participant['variant'])}{esc(port_info)}</p>
              </div>
              <span class="badge">{len(participant['signals']) if participant['signals'] else len(participant['pins'])} {'signal(s)' if participant['signals'] else 'pin(s)'}</span>
            </div>
            <div class="meta-row">CAN: {esc(', '.join(participant['can_addresses']) if participant['can_addresses'] else 'N/A')}</div>
            <div class="subsection">
              <div class="sub-label">Connectors / Port</div>
              <div class="chip-row">{render_chip_list(participant['connectors'], '') if participant['connectors'] else f'<span class="muted">Bus port{esc(port_info)}</span>'}</div>
            </div>
            <div class="subsection">
              <div class="sub-label">Mapped Signals</div>
              <div class="chip-row">{render_chip_list(participant['signals'], 'No mapped signal')}</div>
            </div>
          </article>"""
            )
        if not participant_cards:
            participant_cards.append('<div class="empty">No ECU participates on this bus.</div>')
        meta_html = f'<p class="muted" style="margin-top:4px">{esc(meta_str)}</p>' if meta_str else ''
        sections.append(
            f"""
      <section class="bus-section">
        <div class="bus-head">
          <h2>{esc(lane['name'])}</h2>
          <p>{len(lane['participants'])} ECU node{"s" if len(lane['participants']) != 1 else ""} on this bus.</p>
          {meta_html}
        </div>
        <div class="participant-grid">
{''.join(participant_cards)}
        </div>
      </section>"""
        )
    return "\n".join(sections)


def build_html(arch_name: str, bus_lanes: list[dict[str, Any]]) -> str:
    total_participants = sum(len(lane["participants"]) for lane in bus_lanes)
    active_lanes = sum(1 for lane in bus_lanes if lane["participants"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(arch_name)} - ECU Communication</title>
  <style>
    :root {{ --bg:#070b12; --surface0:#0b1018; --surface1:#0f1622; --surface2:#151e2e; --surface3:#1d2939; --surface4:#273548;
             --border0:#1a2436; --border1:#233149; --border2:#2d3e5c;
             --text:#cfdaea; --text-dim:#6c83a2; --text-fade:#46566e;
             --cyan:#2ee6ff; --green:#2ee6a0; --amber:#ffb43d; --red:#ff5a78;
             --purple:#b388ff; --teal:#19d6c0; --blue:#5aa6ff;
             --accent:var(--cyan); --ok:var(--green); --warn:var(--amber); --err:var(--red);
             --ink:var(--text); --muted:var(--text-dim); --panel:var(--surface1); --panel2:var(--surface2);
             --line:var(--border1); --shadow:0 8px 30px rgba(0,0,0,.45); }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Aptos, "Segoe UI Variable", sans-serif; color:var(--text); background:radial-gradient(circle at top left, rgba(46,230,255,0.06), transparent 28%), var(--bg); }}
    .page {{ max-width:1480px; margin:0 auto; padding:28px; display:grid; gap:24px; }}
    .hero,.summary,.bus-section {{ background:var(--panel); border:1px solid var(--line); border-radius:24px; box-shadow:var(--shadow); }}
    .hero {{ padding:28px; display:grid; gap:12px; }}
    .hero h1 {{ margin:0; font-size:clamp(2rem,4vw,3.4rem); letter-spacing:-0.04em; }}
    .hero p,.bus-head p,.participant-head p,.meta-row,.empty {{ margin:0; color:var(--muted); }}
    .eyebrow,.sub-label {{ font-size:0.78rem; font-weight:800; letter-spacing:0.12em; text-transform:uppercase; color:var(--text-dim); }}
    .summary {{ padding:18px; display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; }}
    .summary-card {{ padding:16px; border-radius:18px; background:var(--panel2); border:1px solid var(--line); }}
    .summary-card .label {{ font-size:0.82rem; text-transform:uppercase; color:var(--muted); letter-spacing:0.08em; }}
    .summary-card .value {{ font-size:2rem; font-weight:700; margin-top:8px; }}
    .bus-section {{ padding:22px; display:grid; gap:18px; }}
    .bus-head h2 {{ margin:0; font-size:1.6rem; }}
    .participant-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:18px; }}
    .participant-card {{ padding:18px; border-radius:20px; background:var(--panel2); border:1px solid var(--line); }}
    .participant-head {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }}
    .participant-head h3 {{ margin:4px 0 0; font-size:1.2rem; }}
    .badge {{ display:inline-flex; padding:6px 10px; border-radius:999px; background:rgba(46,230,255,0.12); color:var(--cyan); font-size:0.8rem; font-weight:700; }}
    .subsection {{ margin-top:14px; display:grid; gap:8px; }}
    .chip-row {{ display:flex; flex-wrap:wrap; gap:8px; }}
    .chip {{ display:inline-flex; align-items:center; padding:6px 10px; border-radius:999px; background:var(--surface3); font-size:0.82rem; }}
    @media (max-width:900px) {{ .page {{ padding:18px; }} .participant-grid {{ grid-template-columns:1fr; }} }}
{OVERFLOW_GUARD_CSS}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <span class="eyebrow">ECU Communication</span>
      <h1>{esc(arch_name)}</h1>
      <p>Communication capability view grouped by interface type, showing which ECUs participate on each lane and which mapped signals currently use them.</p>
    </section>
    <section class="summary">
      <article class="summary-card"><div class="label">Bus Types</div><div class="value">{len(bus_lanes)}</div></article>
      <article class="summary-card"><div class="label">Active Lanes</div><div class="value">{active_lanes}</div></article>
      <article class="summary-card"><div class="label">Participants</div><div class="value">{total_participants}</div></article>
    </section>
{render_bus_sections(bus_lanes)}
  </main>
</body>
</html>"""


def summarize_buses_from_topology(arch: dict[str, Any]) -> list[dict[str, Any]]:
    """Build bus lanes from arch['buses'] — the authoritative named bus list.

    Each ECU participating on a bus appears exactly once per bus entry.
    Falls back to pin-based inference if no buses are defined.
    """
    raw_buses = arch.get("buses", [])
    if not isinstance(raw_buses, list) or not raw_buses:
        return summarize_buses(arch)

    ecu_by_name = {str(e.get("name", "")): e for e in (arch.get("ecus") or []) if isinstance(e, dict)}
    lanes = []
    for bus in raw_buses:
        if not isinstance(bus, dict):
            continue
        bus_name = str(bus.get("name", ""))
        btype = str(bus.get("type", bus.get("bus_type", ""))).upper()
        if not btype or btype not in _BUS_TYPES:
            continue
        bitrate = int(bus.get("bitrate", 0) or 0)
        signals = [str(s) for s in (bus.get("signals") or []) if s]
        participants = []
        for node in (bus.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            ecu_name = str(node.get("ecu", ""))
            port = node.get("port_index", "")
            ecu = ecu_by_name.get(ecu_name, {})
            can_addresses = [str(a) for a in (ecu.get("can_addresses") or []) if a]
            participants.append({
                "ecu": ecu_name,
                "variant": str(ecu.get("variant", "")),
                "can_addresses": can_addresses,
                "port": str(port) if port != "" else "",
                "connectors": [],
                "pins": [],
                "signals": signals[:30],
            })
        participants.sort(key=lambda p: p["ecu"])
        lanes.append({
            "name": bus_name,
            "bus_type": btype,
            "bitrate": bitrate,
            "total_signals": len(signals),
            "participants": participants,
        })
    return lanes or summarize_buses(arch)


def main() -> None:
    base = find_base()
    json_path = base / "exports" / "example_physical_architecture.json"
    if not json_path.exists():
        json_path = base / "exports" / "example_architecture.json"
    if not json_path.exists():
        raise SystemExit(f"Missing file: {json_path}")
    output_path = base / "exports" / "architecture_bus_diagram.html"
    arch = get_architecture(load_json(json_path))
    # Prefer topology (buses[]) over pin-inference; pin-inference is the fallback.
    lanes = summarize_buses_from_topology(arch)
    output_path.write_text(build_html(str(arch.get("name", "Architecture")), lanes), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()