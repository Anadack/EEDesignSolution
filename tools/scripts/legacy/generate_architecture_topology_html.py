#!/usr/bin/env python3
from __future__ import annotations

import json
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


def allocation_summary(node: dict[str, Any]) -> tuple[int, int, int, float]:
    summary = node.get("allocation_summary")
    if isinstance(summary, dict):
        return (
            int(summary.get("total_pins", 0) or 0),
            int(summary.get("allocated_pins", 0) or 0),
            int(summary.get("free_pins", 0) or 0),
            float(summary.get("allocation_percent", 0.0) or 0.0),
        )
    return 0, 0, 0, 0.0


def build_signal_routes(arch: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    routes: dict[str, list[dict[str, str]]] = {}
    ecus = arch.get("ecus", [])
    if not isinstance(ecus, list):
        return routes

    for ecu in ecus:
        if not isinstance(ecu, dict):
            continue
        ecu_name = str(ecu.get("name", "ECU"))
        variant = str(ecu.get("variant", ""))
        pins = ecu.get("pins", [])
        if not isinstance(pins, list):
            continue
        for pin in pins:
            if not isinstance(pin, dict):
                continue
            signal = pin.get("signal")
            if not isinstance(signal, dict) or not signal.get("name"):
                continue
            signal_name = str(signal.get("name"))
            routes.setdefault(signal_name, []).append(
                {
                    "ecu_name": ecu_name,
                    "variant": variant,
                    "connector": str(pin.get("connector", "")),
                    "pin": str(pin.get("physical_number", "")),
                    "interface": str(signal.get("interface_type", pin.get("type", ""))),
                    "role": str(pin.get("role", "")),
                }
            )
    return routes


def summarize_device(device: dict[str, Any], signal_routes: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    pins = device.get("pins", [])
    route_map: dict[tuple[str, str], dict[str, Any]] = {}
    signal_count = 0

    if not isinstance(pins, list):
        pins = []

    for pin in pins:
        if not isinstance(pin, dict):
            continue
        signal = pin.get("signal")
        if not isinstance(signal, dict) or not signal.get("name"):
            continue
        signal_name = str(signal.get("name"))
        signal_count += 1
        for route in signal_routes.get(signal_name, []):
            key = (route["ecu_name"], route["variant"])
            entry = route_map.setdefault(
                key,
                {
                    "ecu_name": route["ecu_name"],
                    "variant": route["variant"],
                    "signals": [],
                    "connectors": set(),
                    "interfaces": set(),
                },
            )
            entry["signals"].append(signal_name)
            if route["connector"]:
                entry["connectors"].add(route["connector"])
            if route["interface"]:
                entry["interfaces"].add(route["interface"])

    routes = []
    for entry in route_map.values():
        entry["signals"].sort()
        entry["connectors"] = sorted(entry["connectors"])
        entry["interfaces"] = sorted(entry["interfaces"])
        routes.append(entry)
    routes.sort(key=lambda item: (item["ecu_name"], item["variant"]))

    return {
        "name": str(device.get("name", "Device")),
        "type": str(device.get("type", "UNKNOWN")),
        "pin_count": len(pins),
        "signal_count": signal_count,
        "routes": routes,
    }


def summarize_systems(arch: dict[str, Any], signal_routes: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    systems_out: list[dict[str, Any]] = []
    systems = arch.get("systems", [])
    if not isinstance(systems, list):
        return systems_out

    for system in systems:
        if not isinstance(system, dict):
            continue
        devices = system.get("devices", [])
        if not isinstance(devices, list):
            devices = []
        summarized_devices = [summarize_device(device, signal_routes) for device in devices if isinstance(device, dict)]
        systems_out.append(
            {
                "name": str(system.get("name", "System")),
                "devices": summarized_devices,
            }
        )
    return systems_out


def summarize_ecus(arch: dict[str, Any]) -> list[dict[str, Any]]:
    ecus_out: list[dict[str, Any]] = []
    ecus = arch.get("ecus", [])
    if not isinstance(ecus, list):
        return ecus_out

    for ecu in ecus:
        if not isinstance(ecu, dict):
            continue
        total, allocated, free, percent = allocation_summary(ecu)
        can_addresses = ecu.get("can_addresses", [])
        if not isinstance(can_addresses, list):
            can_addresses = []
        ecus_out.append(
            {
                "name": str(ecu.get("name", "ECU")),
                "variant": str(ecu.get("variant", "")),
                "can_addresses": [str(value) for value in can_addresses],
                "total": total,
                "allocated": allocated,
                "free": free,
                "percent": percent,
            }
        )
    return ecus_out


def render_signal_chips(signals: list[str], limit: int = 6) -> str:
    visible = signals[:limit]
    chips = "".join(f'<span class="chip">{esc(signal)}</span>' for signal in visible)
    if len(signals) > limit:
        chips += f'<span class="chip muted-chip">+{len(signals) - limit} more</span>'
    return chips or '<span class="empty">No mapped signals</span>'


def render_ecu_cards(ecus: list[dict[str, Any]]) -> str:
    cards = []
    for ecu in ecus:
        tone = "ok"
        if ecu["percent"] >= 50.0:
            tone = "warn"
        if ecu["percent"] >= 80.0:
            tone = "err"
        addresses = ", ".join(ecu["can_addresses"]) if ecu["can_addresses"] else "No CAN address"
        cards.append(
            f"""
        <article class="ecu-card">
          <div class="ecu-card-head">
            <div>
              <h3>{esc(ecu['name'])}</h3>
              <p>{esc(ecu['variant'])} ECU</p>
            </div>
            <span class="badge {tone}">{ecu['percent']:.1f}% allocated</span>
          </div>
          <div class="meta-row">{esc(addresses)}</div>
          <div class="meter"><span class="{tone}" style="width: {min(ecu['percent'], 100.0):.1f}%"></span></div>
          <div class="stat-row">
            <span>Total {ecu['total']}</span>
            <span>Used {ecu['allocated']}</span>
            <span>Free {ecu['free']}</span>
          </div>
        </article>"""
        )
    return "\n".join(cards)


def render_systems(systems: list[dict[str, Any]]) -> str:
    sections = []
    for system in systems:
        device_cards = []
        for device in system["devices"]:
            route_cards = []
            for route in device["routes"]:
                connectors = ", ".join(route["connectors"]) if route["connectors"] else "Unresolved connector"
                interfaces = " · ".join(route["interfaces"]) if route["interfaces"] else "Unknown interface"
                route_cards.append(
                    f"""
                <div class="route-card">
                  <div class="route-head">
                    <span class="route-label">Mapped to</span>
                    <strong>{esc(route['ecu_name'])}</strong>
                    <span class="route-variant">{esc(route['variant'])}</span>
                  </div>
                  <div class="route-meta">{esc(connectors)} · {esc(interfaces)} · {len(route['signals'])} signal(s)</div>
                  <div class="chip-row">{render_signal_chips(route['signals'])}</div>
                </div>"""
                )
            if not route_cards:
                route_cards.append('<div class="route-card empty-route">No mapped ECU route yet.</div>')

            device_cards.append(
                f"""
            <article class="device-card {esc(device['type'].lower())}">
              <div class="device-card-head">
                <div>
                  <span class="eyebrow">{esc(device['type'])}</span>
                  <h3>{esc(device['name'])}</h3>
                </div>
                <div class="device-stats">
                  <span>{device['pin_count']} pin(s)</span>
                  <span>{device['signal_count']} signal(s)</span>
                </div>
              </div>
              <div class="route-stack">
{''.join(route_cards)}
              </div>
            </article>"""
            )

        sections.append(
            f"""
        <section class="system-section">
          <div class="system-head">
            <h2>{esc(system['name'])}</h2>
            <p>{len(system['devices'])} device block(s) participating in the topology.</p>
          </div>
          <div class="device-grid">
{''.join(device_cards)}
          </div>
        </section>"""
        )
    return "\n".join(sections)


def build_html(arch_name: str, systems: list[dict[str, Any]], ecus: list[dict[str, Any]], total_pins: int, total_allocated: int, total_free: int, total_percent: float) -> str:
    system_count = len(systems)
    device_count = sum(len(system["devices"]) for system in systems)
    routed_signal_count = sum(device["signal_count"] for system in systems for device in system["devices"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(arch_name)} - System Topology</title>
  <style>
    :root {{
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
      --accent: var(--cyan);
      --ok: var(--green);
      --warn: var(--amber);
      --err: var(--red);
      --ink: var(--text);
      --muted: var(--text-dim);
      --panel: var(--surface1);
      --panel2: var(--surface2);
      --line: var(--border1);
      --shadow: 0 8px 30px rgba(0,0,0,.45);
      --paper: var(--surface1);
      --accent-soft: rgba(46,230,255,0.12);
      --sensor: #19d6c0;
      --actuator: #ffb43d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Aptos, "Segoe UI Variable", "Trebuchet MS", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(46,230,255,0.06), transparent 28%),
        radial-gradient(circle at top right, rgba(255,180,61,0.04), transparent 26%),
        var(--bg);
    }}
    .page {{ max-width: 1440px; margin: 0 auto; padding: 28px; display: grid; gap: 28px; }}
    .hero, .summary-strip, .fleet, .system-section {{ background: var(--surface1); border: 1px solid var(--border1); border-radius: 24px; box-shadow: var(--shadow); }}
    .hero {{ padding: 28px; display: grid; gap: 14px; }}
    .hero h1 {{ margin: 0; font-size: clamp(2rem, 3vw, 3.6rem); line-height: 1; letter-spacing: -0.04em; }}
    .hero p {{ margin: 0; color: var(--muted); max-width: 72ch; font-size: 1.02rem; }}
    .summary-strip {{ padding: 18px; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }}
    .summary-card {{ padding: 16px; border-radius: 18px; background: var(--surface2); border: 1px solid var(--border1); }}
    .summary-card .label {{ color: var(--muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    .summary-card .value {{ font-size: 2rem; font-weight: 700; margin-top: 8px; }}
    .fleet {{ padding: 22px; display: grid; gap: 18px; }}
    .fleet-head h2, .system-head h2 {{ margin: 0; font-size: 1.6rem; }}
    .fleet-head p, .system-head p {{ margin: 6px 0 0; color: var(--muted); }}
    .ecu-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
    .ecu-card, .device-card {{ border-radius: 20px; padding: 18px; background: var(--surface2); border: 1px solid var(--border1); }}
    .ecu-card-head, .device-card-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }}
    .ecu-card h3, .device-card h3 {{ margin: 4px 0 0; font-size: 1.2rem; }}
    .ecu-card p {{ margin: 4px 0 0; color: var(--text-dim); }}
    .badge {{ display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 6px 10px; font-size: 0.8rem; font-weight: 700; background: var(--accent-soft); color: var(--accent); white-space: nowrap; }}
    .badge.ok {{ color: var(--ok); background: rgba(21, 128, 61, 0.12); }}
    .badge.warn {{ color: var(--warn); background: rgba(180, 83, 9, 0.12); }}
    .badge.err {{ color: var(--err); background: rgba(185, 28, 28, 0.12); }}
    .meta-row, .route-meta, .device-stats {{ color: var(--muted); font-size: 0.92rem; }}
    .meter {{ margin-top: 14px; height: 10px; border-radius: 999px; overflow: hidden; background: rgba(107, 114, 128, 0.14); }}
    .meter span {{ display: block; height: 100%; background: rgba(29, 78, 216, 0.8); }}
    .meter span.ok {{ background: rgba(21, 128, 61, 0.76); }}
    .meter span.warn {{ background: rgba(180, 83, 9, 0.76); }}
    .meter span.err {{ background: rgba(185, 28, 28, 0.76); }}
    .stat-row {{ display: flex; flex-wrap: wrap; gap: 14px; margin-top: 14px; color: var(--muted); font-size: 0.9rem; }}
    .system-section {{ padding: 22px; display: grid; gap: 18px; }}
    .device-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 18px; }}
    .device-card.sensor {{ border-left: 5px solid rgba(15, 118, 110, 0.8); }}
    .device-card.actuator {{ border-left: 5px solid rgba(180, 83, 9, 0.8); }}
    .eyebrow {{ font-size: 0.78rem; font-weight: 800; letter-spacing: 0.12em; color: var(--muted); text-transform: uppercase; }}
    .route-stack {{ margin-top: 16px; display: grid; gap: 12px; }}
    .route-card {{ position: relative; padding: 14px 14px 14px 18px; border-radius: 16px; background: linear-gradient(135deg, var(--surface1), var(--surface2)); border: 1px solid var(--border1); }}
    .route-card::before {{ content: ""; position: absolute; left: 0; top: 14px; bottom: 14px; width: 4px; border-radius: 999px; background: rgba(29, 78, 216, 0.72); }}
    .route-head {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }}
    .route-label {{ font-size: 0.78rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }}
    .route-variant {{ color: var(--muted); font-size: 0.86rem; }}
    .chip-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
    .chip {{ display: inline-flex; align-items: center; padding: 5px 10px; border-radius: 999px; background: var(--surface3); font-size: 0.82rem; }}
    .muted-chip {{ color: var(--muted); }}
    .empty-route, .empty {{ color: var(--muted); }}
    @media (max-width: 900px) {{
      .page {{ padding: 18px; }}
      .device-grid {{ grid-template-columns: 1fr; }}
    }}
{OVERFLOW_GUARD_CSS}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <span class="eyebrow">Architecture Topology</span>
      <h1>{esc(arch_name)}</h1>
      <p>System-level view of how sensors and actuators are distributed across ECU targets, with routing clusters grouped by logical device and resolved ECU destination.</p>
    </section>

    <section class="summary-strip">
      <article class="summary-card"><div class="label">Systems</div><div class="value">{system_count}</div></article>
      <article class="summary-card"><div class="label">Devices</div><div class="value">{device_count}</div></article>
      <article class="summary-card"><div class="label">Routed Signals</div><div class="value">{routed_signal_count}</div></article>
      <article class="summary-card"><div class="label">ECUs</div><div class="value">{len(ecus)}</div></article>
      <article class="summary-card"><div class="label">Allocated Pins</div><div class="value">{total_allocated}/{total_pins}</div></article>
      <article class="summary-card"><div class="label">Free Pins</div><div class="value">{total_free} · {total_percent:.1f}% used</div></article>
    </section>

    <section class="fleet">
      <div class="fleet-head">
        <h2>ECU Fleet</h2>
        <p>Capacity and bus identity for each controller participating in the architecture.</p>
      </div>
      <div class="ecu-grid">
{render_ecu_cards(ecus)}
      </div>
    </section>

{render_systems(systems)}
  </main>
</body>
</html>"""


def main() -> None:
    base = find_base()
    json_path = base / "exports" / "example_architecture.json"
    if not json_path.exists():
        json_path = base / "exports" / "example_physical_architecture.json"
    output_path = base / "exports" / "architecture_topology.html"

    if not json_path.exists():
        raise SystemExit(f"Missing file: {json_path}")

    data = load_json(json_path)
    arch = get_architecture(data)
    arch_name = str(arch.get("name", "Architecture"))
    signal_routes = build_signal_routes(arch)
    systems = summarize_systems(arch, signal_routes)
    ecus = summarize_ecus(arch)
    total_pins, total_allocated, total_free, total_percent = allocation_summary(arch)

    html = build_html(arch_name, systems, ecus, total_pins, total_allocated, total_free, total_percent)
    output_path.write_text(html, encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()