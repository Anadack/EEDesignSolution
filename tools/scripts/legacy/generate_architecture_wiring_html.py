#!/usr/bin/env python3
from __future__ import annotations

import json
import re
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


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip())
    cleaned = cleaned.strip("-").lower()
    return cleaned or "item"


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


def pin_order_key(number: str) -> tuple[int, str]:
  return (int(number), "") if number.isdigit() else (999999, number)


def summarize_systems(arch: dict[str, Any], signal_rank: dict[str, int]) -> list[dict[str, Any]]:
  systems_out: list[dict[str, Any]] = []
  systems = arch.get("systems", [])
  if not isinstance(systems, list):
    return systems_out

  for system in systems:
    if not isinstance(system, dict):
      continue

    devices_out = []
    devices = system.get("devices", [])
    if not isinstance(devices, list):
      devices = []

    for device in devices:
      if not isinstance(device, dict):
        continue

      ranked_pins = []
      pins = device.get("pins", [])
      if not isinstance(pins, list):
        pins = []

      for pin in pins:
        if not isinstance(pin, dict):
          continue

        signal = pin.get("signal")
        signal_name = ""
        signal_type = ""
        if isinstance(signal, dict):
          signal_name = str(signal.get("name", ""))
          signal_type = str(signal.get("type", ""))

        pin_number = str(pin.get("number", ""))
        ranked_pins.append(
          {
            "number": pin_number,
            "name": str(pin.get("name", "")),
            "role": str(pin.get("role", "")),
            "signal_name": signal_name,
            "signal_type": signal_type,
            "sort_rank": signal_rank.get(signal_name, 1_000_000 + pin_order_key(pin_number)[0]),
          }
        )

      ranked_pins.sort(key=lambda pin: (int(pin["sort_rank"]), pin_order_key(pin["number"])))
      device_rank = min((int(pin["sort_rank"]) for pin in ranked_pins), default=1_000_000)

      devices_out.append(
        {
          "name": str(device.get("name", "Device")),
          "type": str(device.get("type", "UNKNOWN")),
          "pins": [
            {
              "number": pin["number"],
              "name": pin["name"],
              "role": pin["role"],
              "signal_name": pin["signal_name"],
              "signal_type": pin["signal_type"],
            }
            for pin in ranked_pins
          ],
          "sort_rank": device_rank,
        }
      )

    devices_out.sort(key=lambda device: (int(device["sort_rank"]), device["name"]))
    systems_out.append(
      {
        "name": str(system.get("name", "System")),
        "devices": [
          {"name": device["name"], "type": device["type"], "pins": device["pins"]}
          for device in devices_out
        ],
        "sort_rank": min((int(device["sort_rank"]) for device in devices_out), default=1_000_000),
      }
    )

  systems_out.sort(key=lambda system: (int(system["sort_rank"]), system["name"]))
  return [{"name": system["name"], "devices": system["devices"]} for system in systems_out]


def summarize_ecus(arch: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
  ecus_out: list[dict[str, Any]] = []
  signal_rank: dict[str, int] = {}
  next_rank = 0
  ecus = arch.get("ecus", [])
  if not isinstance(ecus, list):
    return ecus_out, signal_rank

  for ecu in ecus:
    if not isinstance(ecu, dict):
      continue

    connectors: dict[str, list[dict[str, str]]] = {}
    pins = ecu.get("pins", [])
    if not isinstance(pins, list):
      pins = []

    for pin in pins:
      if not isinstance(pin, dict):
        continue

      connector_name = str(pin.get("connector", "UNASSIGNED"))
      signal = pin.get("signal")
      signal_name = ""
      signal_interface = str(pin.get("type", ""))
      if isinstance(signal, dict):
        signal_name = str(signal.get("name", ""))
        signal_interface = str(signal.get("interface_type", signal_interface))

      if signal_name and signal_name not in signal_rank:
        signal_rank[signal_name] = next_rank
        next_rank += 1

      connectors.setdefault(connector_name, []).append(
        {
          "physical_number": str(pin.get("physical_number", "")),
          "name": str(pin.get("name", "")),
          "role": str(pin.get("role", "")),
          "signal_name": signal_name,
          "signal_interface": signal_interface,
          "occupied": "true" if bool(pin.get("is_occupied")) else "false",
        }
      )

    sorted_connectors = []
    for connector_name, connector_pins in sorted(connectors.items(), key=lambda item: item[0]):
      connector_pins.sort(key=lambda pin: int(pin["physical_number"]) if pin["physical_number"].isdigit() else 999999)
      sorted_connectors.append({"name": connector_name, "pins": connector_pins})

    total, allocated, free, percent = allocation_summary(ecu)
    ecus_out.append(
      {
        "name": str(ecu.get("name", "ECU")),
        "variant": str(ecu.get("variant", "")),
        "connectors": sorted_connectors,
        "total": total,
        "allocated": allocated,
        "free": free,
        "percent": percent,
      }
    )

  return ecus_out, signal_rank


def render_systems(systems: list[dict[str, Any]]) -> str:
    sections = []
    for system in systems:
        device_html = []
        for device in system["devices"]:
            pins_html = []
            for pin in device["pins"]:
                signal_attr = esc(pin["signal_name"])
                anchor_class = "signal-anchor has-signal" if pin["signal_name"] else "signal-anchor"
                signal_markup = f'<span class="signal-status">{esc(pin["signal_name"] or "No signal")}</span>' if not pin["signal_name"] else ""
                pins_html.append(
                    f"""
                <li class="logical-pin {'wired' if pin['signal_name'] else 'free'}" data-signal="{signal_attr}">
                  <div class="pin-meta">
                    <span class="pin-number">{esc(pin['number'])}</span>
                    <div>
                      <div class="pin-name">{esc(pin['name'])}</div>
                      <div class="pin-sub">{esc(pin['role'])} · {esc(pin['signal_type'] or 'UNWIRED')}</div>
                    </div>
                  </div>
                  <div class="pin-end">
                    {signal_markup}
                    <span class="{anchor_class}" data-signal="{signal_attr}" data-side="source"></span>
                  </div>
                </li>"""
                )
            device_html.append(
                f"""
            <article class="device-card {esc(device['type'].lower())}">
              <div class="device-head">
                <div>
                  <span class="eyebrow">{esc(device['type'])}</span>
                  <h3>{esc(device['name'])}</h3>
                </div>
                <span class="badge">{len(device['pins'])} pin(s)</span>
              </div>
              <ul class="pin-list">
{''.join(pins_html)}
              </ul>
            </article>"""
            )
        sections.append(
            f"""
        <section class="system-card">
          <div class="system-head">
            <h2>{esc(system['name'])}</h2>
            <p>{len(system['devices'])} device block(s)</p>
          </div>
          <div class="device-stack">
{''.join(device_html)}
          </div>
        </section>"""
        )
    return "\n".join(sections)


def render_ecus(ecus: list[dict[str, Any]]) -> str:
    ecu_cards = []
    for ecu in ecus:
        connector_html = []
        for connector in ecu["connectors"]:
            wired_count = sum(1 for pin in connector["pins"] if pin["signal_name"])
            pin_rows = []
            for pin in connector["pins"]:
                signal_attr = esc(pin["signal_name"])
                anchor_class = "signal-anchor has-signal" if pin["signal_name"] else "signal-anchor"
                row_class = "ecu-pin wired" if pin["signal_name"] else "ecu-pin free-pin"
                signal_markup = f'<span class="signal-status">{esc(pin["signal_name"] or "Free")}</span>' if not pin["signal_name"] else ""
                pin_rows.append(
                    f"""
                <li class="{row_class}" data-signal="{signal_attr}" data-occupied="{esc(pin['occupied'])}">
                  <div class="pin-meta">
                    <span class="{anchor_class}" data-signal="{signal_attr}" data-side="target"></span>
                    <span class="pin-number">{esc(pin['physical_number'])}</span>
                    <div>
                      <div class="pin-name">{esc(pin['name'])}</div>
                      <div class="pin-sub">{esc(pin['role'])} · {esc(pin['signal_interface'])}</div>
                    </div>
                  </div>
                  {signal_markup}
                </li>"""
                )
            connector_html.append(
                f"""
            <details class="connector-card" open>
              <summary>
                <span>{esc(connector['name'])}</span>
                <span>{wired_count}/{len(connector['pins'])} wired</span>
              </summary>
              <ul class="pin-list ecu-pin-list">
{''.join(pin_rows)}
              </ul>
            </details>"""
            )
        ecu_cards.append(
            f"""
        <section class="ecu-card">
          <div class="ecu-head">
            <div>
              <h2>{esc(ecu['name'])}</h2>
              <p>{esc(ecu['variant'])} · {ecu['allocated']}/{ecu['total']} used · {ecu['percent']:.1f}% allocation</p>
            </div>
            <span class="badge">{len(ecu['connectors'])} connector(s)</span>
          </div>
          <div class="connector-stack">
{''.join(connector_html)}
          </div>
        </section>"""
        )
    return "\n".join(ecu_cards)


def build_html(arch_name: str, systems: list[dict[str, Any]], ecus: list[dict[str, Any]], total_pins: int, total_allocated: int, total_free: int, total_percent: float) -> str:
    system_count = len(systems)
    device_count = sum(len(system["devices"]) for system in systems)
    logical_pin_count = sum(len(device["pins"]) for system in systems for device in system["devices"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(arch_name)} - Wiring Diagram</title>
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
      --line: var(--border1);
      --shadow: 0 8px 30px rgba(0,0,0,.45);
      --sensor: #19d6c0;
      --actuator: #ffb43d;
      --wire: rgba(46,230,255,0.45);
      --wire-active: rgba(255,90,120,0.85);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Aptos, "Segoe UI Variable", sans-serif; color: var(--text); background: radial-gradient(circle at top left, rgba(46,230,255,0.06), transparent 28%), var(--bg); }}
    .page {{ max-width: 1560px; margin: 0 auto; padding: 20px; display: grid; gap: 16px; }}
    .hero, .summary, .diagram-shell {{ background: var(--surface1); border: 1px solid var(--border1); border-radius: 24px; box-shadow: var(--shadow); }}
    .hero {{ padding: 20px 22px; display: grid; gap: 8px; }}
    .hero h1 {{ margin: 0; font-size: clamp(1.8rem, 3.2vw, 2.8rem); letter-spacing: -0.04em; }}
    .hero p {{ margin: 0; max-width: 76ch; color: var(--muted); }}
    .eyebrow {{ font-size: 0.78rem; font-weight: 800; letter-spacing: 0.12em; color: var(--muted); text-transform: uppercase; }}
    .summary {{ padding: 14px; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
    .summary-card {{ padding: 12px 14px; border-radius: 16px; background: var(--surface2); border: 1px solid var(--border1); }}
    .summary-card .label {{ font-size: 0.82rem; text-transform: uppercase; color: var(--muted); letter-spacing: 0.08em; }}
    .summary-card .value {{ font-size: 1.6rem; font-weight: 700; margin-top: 6px; }}
    .diagram-shell {{ position: relative; padding: 14px; overflow: hidden; }}
    .toolbar {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; padding: 2px 2px 12px; }}
    .toolbar p {{ margin: 0; color: var(--muted); }}
    .toolbar label {{ display: inline-flex; align-items: center; gap: 8px; font-size: 0.95rem; color: var(--ink); }}
    .toolbar-actions {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: flex-end; }}
    .zoom-controls {{ display: inline-flex; align-items: center; gap: 6px; padding: 6px; border: 1px solid var(--border1); border-radius: 999px; background: var(--surface2); }}
    .zoom-controls button {{ width: 32px; height: 32px; border: 1px solid var(--border1); border-radius: 999px; background: var(--surface3); color: var(--text); font: inherit; cursor: pointer; }}
    .zoom-readout {{ min-width: 52px; text-align: center; font-size: 0.82rem; font-weight: 700; color: var(--muted); }}
    .diagram-viewport {{ overflow: auto; max-height: 78vh; padding: 4px; border-radius: 18px; background: var(--surface0); border: 1px solid var(--border1); }}
    .diagram-canvas {{ position: relative; width: max-content; min-width: 100%; }}
    .diagram-stage {{ position: relative; width: max-content; transform-origin: top left; }}
    .diagram-grid {{ position: relative; display: grid; grid-template-columns: minmax(280px, max-content) minmax(320px, max-content); gap: 18px; align-items: start; justify-content: space-between; padding: 2px; }}
    .column {{ display: grid; gap: 14px; position: relative; z-index: 1; align-content: start; }}
    .systems-column {{ justify-items: start; }}
    .ecus-column {{ justify-items: end; }}
    .system-card, .ecu-card, .device-card, .connector-card {{ background: var(--surface2); border: 1px solid var(--border1); border-radius: 22px; width: fit-content; max-width: 100%; }}
    .system-card {{ padding: 14px; display: grid; gap: 12px; justify-items: start; }}
    .system-head h2, .ecu-head h2, .device-head h3 {{ margin: 0; }}
    .system-head p, .ecu-head p {{ margin: 4px 0 0; color: var(--muted); font-size: 0.9rem; }}
    .device-stack, .connector-stack {{ display: grid; gap: 10px; justify-items: start; width: fit-content; max-width: 100%; }}
    .device-card {{ padding: 12px; justify-self: start; }}
    .device-card.sensor {{ border-left: 5px solid rgba(15,118,110,0.82); }}
    .device-card.actuator {{ border-left: 5px solid rgba(180,83,9,0.82); }}
    .device-head, .ecu-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; width: 100%; }}
    .badge {{ display: inline-flex; padding: 5px 9px; border-radius: 999px; background: rgba(46,230,255,0.1); color: var(--cyan); font-size: 0.75rem; font-weight: 700; white-space: nowrap; }}
    .pin-list {{ list-style: none; margin: 10px 0 0; padding: 0; display: grid; gap: 6px; justify-items: start; }}
    .logical-pin, .ecu-pin {{ display: inline-flex; width: fit-content; max-width: 100%; align-items: center; justify-content: space-between; gap: 10px; padding: 7px 9px; border-radius: 12px; border: 1px solid var(--border1); background: var(--surface3); min-height: 40px; }}
    .logical-pin.wired, .ecu-pin.wired {{ background: rgba(46,230,255,0.06); }}
    .logical-pin.free, .ecu-pin.free-pin {{ background: var(--surface2); color: var(--text-dim); }}
    .pin-meta {{ display: flex; gap: 8px; align-items: center; min-width: 0; flex: 0 1 auto; }}
    .pin-number {{ min-width: 28px; padding: 3px 6px; border-radius: 999px; background: var(--surface4); text-align: center; font-size: 0.75rem; font-weight: 700; }}
    .pin-name {{ font-weight: 700; font-size: 0.9rem; }}
    .pin-sub, .signal-status {{ color: var(--muted); font-size: 0.78rem; }}
    .signal-status {{ max-width: 180px; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 0 1 auto; }}
    .pin-end {{ display: flex; align-items: center; gap: 8px; justify-content: flex-end; flex: 0 1 auto; }}
    .ecu-card {{ padding: 14px; display: grid; gap: 12px; justify-items: end; }}
    .connector-card {{ overflow: hidden; justify-self: end; }}
    .connector-card summary {{ list-style: none; cursor: pointer; display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; font-weight: 700; background: var(--surface3); }}
    .connector-card summary::-webkit-details-marker {{ display: none; }}
    .connector-card[open] summary {{ border-bottom: 1px solid var(--line); }}
    .ecu-pin-list {{ padding: 8px; margin: 0; justify-items: end; width: fit-content; max-width: 100%; }}
    .signal-anchor {{ width: 12px; height: 12px; border-radius: 999px; background: var(--surface4); border: 2px solid var(--border2); flex: 0 0 auto; position: relative; z-index: 4; }}
    .signal-anchor.has-signal {{ background: var(--cyan); box-shadow: 0 0 0 4px rgba(46,230,255,0.15); }}
    .signal-overlay {{ position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 2; overflow: visible; }}
    .signal-overlay path {{ fill: none; stroke: var(--wire); stroke-width: 2.6; stroke-linecap: round; opacity: 0.95; }}
    .signal-overlay path.active {{ stroke: var(--wire-active); stroke-width: 3.8; filter: drop-shadow(0 0 8px rgba(185,28,28,0.24)); }}
    .signal-overlay text {{ font-size: 10.5px; font-weight: 700; letter-spacing: 0.03em; fill: var(--text); paint-order: stroke; stroke: var(--bg); stroke-width: 4px; stroke-linejoin: round; }}
    .signal-overlay text.active {{ fill: var(--red); }}
    .signal-hover {{ outline: 2px solid rgba(185,28,28,0.24); outline-offset: 1px; }}
    .hide-free .free-pin {{ display: none; }}
    @media (max-width: 1200px) {{ .diagram-grid {{ grid-template-columns: 1fr; }} .signal-overlay {{ display: none; }} }}
{OVERFLOW_GUARD_CSS}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <span class="eyebrow">Wiring Diagram</span>
      <h1>{esc(arch_name)}</h1>
      <p>Full architecture wiring view showing systems, sensors, actuators, logical pins, ECU connectors, physical pins, and signal-based wiring across the whole mapped design.</p>
    </section>
    <section class="summary">
      <article class="summary-card"><div class="label">Systems</div><div class="value">{system_count}</div></article>
      <article class="summary-card"><div class="label">Devices</div><div class="value">{device_count}</div></article>
      <article class="summary-card"><div class="label">Logical Pins</div><div class="value">{logical_pin_count}</div></article>
      <article class="summary-card"><div class="label">ECU Pins</div><div class="value">{total_pins}</div></article>
      <article class="summary-card"><div class="label">Connected Pins</div><div class="value">{total_allocated}</div></article>
      <article class="summary-card"><div class="label">Free Pins</div><div class="value">{total_free} · {total_percent:.1f}% used</div></article>
    </section>
    <section class="diagram-shell hide-free" id="diagramShell">
      <div class="toolbar">
        <p>Compact view keeps focus on routed signals. Left: systems and logical pins. Right: ECU connectors and mapped physical endpoints.</p>
        <div class="toolbar-actions">
          <label><input type="checkbox" id="hideFreePinsToggle" checked /> Hide free ECU pins</label>
          <div class="zoom-controls" aria-label="Zoom controls">
            <button type="button" id="zoomOutBtn" aria-label="Zoom out">-</button>
            <span class="zoom-readout" id="zoomReadout">100%</span>
            <button type="button" id="zoomInBtn" aria-label="Zoom in">+</button>
            <button type="button" id="zoomResetBtn" aria-label="Reset zoom">Reset</button>
          </div>
        </div>
      </div>
      <div class="diagram-viewport" id="diagramViewport">
        <div class="diagram-canvas" id="diagramCanvas">
          <div class="diagram-stage" id="diagramStage">
            <div class="diagram-grid" id="diagramGrid">
              <svg class="signal-overlay" id="signalOverlay"></svg>
              <div class="column systems-column">
{render_systems(systems)}
              </div>
              <div class="column ecus-column">
{render_ecus(ecus)}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>
  <script>
    (function() {{
      const shell = document.getElementById('diagramShell');
      const viewport = document.getElementById('diagramViewport');
      const canvas = document.getElementById('diagramCanvas');
      const stage = document.getElementById('diagramStage');
      const grid = document.getElementById('diagramGrid');
      const overlay = document.getElementById('signalOverlay');
      const toggle = document.getElementById('hideFreePinsToggle');
      const zoomReadout = document.getElementById('zoomReadout');
      const zoomInBtn = document.getElementById('zoomInBtn');
      const zoomOutBtn = document.getElementById('zoomOutBtn');
      const zoomResetBtn = document.getElementById('zoomResetBtn');
      let zoom = 1;
      const minZoom = 0.6;
      const maxZoom = 2.25;

      function clampZoom(value) {{
        return Math.min(maxZoom, Math.max(minZoom, value));
      }}

      function syncStageSize() {{
        const baseWidth = Math.max(grid.scrollWidth, grid.offsetWidth, 1);
        const baseHeight = Math.max(grid.scrollHeight, grid.offsetHeight, 1);
        stage.style.transform = `scale(${{zoom}})`;
        canvas.style.width = `${{Math.ceil(baseWidth * zoom)}}px`;
        canvas.style.height = `${{Math.ceil(baseHeight * zoom)}}px`;
        if (zoomReadout) {{
          zoomReadout.textContent = `${{Math.round(zoom * 100)}}%`;
        }}
        return {{ baseWidth, baseHeight }};
      }}

      function compactSvgLabel(value) {{
        if (!value || value.length <= 30) {{
          return value || '';
        }}
        return `${{value.slice(0, 14)}}...${{value.slice(-12)}}`;
      }}

      function setZoom(nextZoom, anchorX, anchorY) {{
        const previousZoom = zoom;
        zoom = clampZoom(nextZoom);
        const focusX = anchorX ?? viewport.scrollLeft + viewport.clientWidth / 2;
        const focusY = anchorY ?? viewport.scrollTop + viewport.clientHeight / 2;
        syncStageSize();
        const ratio = zoom / previousZoom;
        viewport.scrollLeft = Math.max(0, focusX * ratio - viewport.clientWidth / 2);
        viewport.scrollTop = Math.max(0, focusY * ratio - viewport.clientHeight / 2);
        requestAnimationFrame(drawLines);
      }}

      function drawLines() {{
        if (window.innerWidth <= 1200) {{
          overlay.innerHTML = '';
          return;
        }}

        const size = syncStageSize();
        const gridRect = grid.getBoundingClientRect();
        overlay.setAttribute('viewBox', `0 0 ${{size.baseWidth}} ${{size.baseHeight}}`);
        overlay.setAttribute('width', String(size.baseWidth));
        overlay.setAttribute('height', String(size.baseHeight));
        overlay.innerHTML = '';
        let lineIndex = 0;

        const sources = Array.from(document.querySelectorAll('.signal-anchor[data-side="source"][data-signal]:not([data-signal=""])'));
        sources.forEach((source) => {{
          const signal = source.getAttribute('data-signal');
          const targets = Array.from(document.querySelectorAll(`.signal-anchor[data-side="target"][data-signal="${{CSS.escape(signal)}}"]`));
          if (!targets.length) {{
            return;
          }}

          const sourceRect = source.getBoundingClientRect();
          const startX = (sourceRect.left - gridRect.left + sourceRect.width / 2) / zoom;
          const startY = (sourceRect.top - gridRect.top + sourceRect.height / 2) / zoom;

          targets.forEach((target) => {{
            const targetRow = target.closest('.ecu-pin');
            if (targetRow && getComputedStyle(targetRow).display === 'none') {{
              return;
            }}
            const targetRect = target.getBoundingClientRect();
            const endX = (targetRect.left - gridRect.left + targetRect.width / 2) / zoom;
            const endY = (targetRect.top - gridRect.top + targetRect.height / 2) / zoom;
            const control = Math.max((endX - startX) * 0.42, 80);
            const pathId = `wire-${{lineIndex++}}-${{signal.toLowerCase().replace(/[^a-z0-9]+/g, '-')}}`;
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', `M ${{startX}} ${{startY}} C ${{startX + control}} ${{startY}}, ${{endX - control}} ${{endY}}, ${{endX}} ${{endY}}`);
            path.id = pathId;
            path.dataset.signal = signal;
            overlay.appendChild(path);

            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.dataset.signal = signal;
            text.classList.add('wire-label');
            text.setAttribute('dy', '-2');
            const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
            title.textContent = signal;
            text.appendChild(title);
            const textPath = document.createElementNS('http://www.w3.org/2000/svg', 'textPath');
            textPath.setAttributeNS('http://www.w3.org/1999/xlink', 'href', `#${{pathId}}`);
            textPath.setAttribute('href', `#${{pathId}}`);
            textPath.setAttribute('startOffset', '50%');
            textPath.setAttribute('text-anchor', 'middle');
            textPath.textContent = compactSvgLabel(signal);
            text.appendChild(textPath);
            overlay.appendChild(text);
          }});
        }});
      }}

      function bindHover() {{
        document.querySelectorAll('[data-signal]').forEach((node) => {{
          node.addEventListener('mouseenter', () => {{
            const signal = node.getAttribute('data-signal');
            if (!signal) {{
              return;
            }}
            document.querySelectorAll(`[data-signal="${{CSS.escape(signal)}}"]`).forEach((match) => match.classList.add('signal-hover'));
            overlay.querySelectorAll(`path[data-signal="${{CSS.escape(signal)}}"]`).forEach((path) => path.classList.add('active'));
            overlay.querySelectorAll(`text[data-signal="${{CSS.escape(signal)}}"]`).forEach((label) => label.classList.add('active'));
          }});
          node.addEventListener('mouseleave', () => {{
            const signal = node.getAttribute('data-signal');
            if (!signal) {{
              return;
            }}
            document.querySelectorAll(`[data-signal="${{CSS.escape(signal)}}"]`).forEach((match) => match.classList.remove('signal-hover'));
            overlay.querySelectorAll(`path[data-signal="${{CSS.escape(signal)}}"]`).forEach((path) => path.classList.remove('active'));
            overlay.querySelectorAll(`text[data-signal="${{CSS.escape(signal)}}"]`).forEach((label) => label.classList.remove('active'));
          }});
        }});
      }}

      toggle.addEventListener('change', () => {{
        shell.classList.toggle('hide-free', toggle.checked);
        requestAnimationFrame(() => {{
          syncStageSize();
          drawLines();
        }});
      }});

      zoomInBtn.addEventListener('click', () => setZoom(zoom + 0.15));
      zoomOutBtn.addEventListener('click', () => setZoom(zoom - 0.15));
      zoomResetBtn.addEventListener('click', () => setZoom(1));
      viewport.addEventListener('wheel', (event) => {{
        if (!event.ctrlKey) {{
          return;
        }}
        event.preventDefault();
        const delta = event.deltaY < 0 ? 0.12 : -0.12;
        setZoom(zoom + delta, viewport.scrollLeft + event.offsetX, viewport.scrollTop + event.offsetY);
      }}, {{ passive: false }});

      window.addEventListener('resize', () => requestAnimationFrame(() => {{ syncStageSize(); drawLines(); }}));
      document.querySelectorAll('details').forEach((details) => details.addEventListener('toggle', () => requestAnimationFrame(() => {{ syncStageSize(); drawLines(); }})));
      bindHover();
      syncStageSize();
      requestAnimationFrame(drawLines);
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
    output_path = base / "exports" / "architecture_wiring_diagram.html"

    arch = get_architecture(load_json(json_path))
    ecus, signal_rank = summarize_ecus(arch)
    systems = summarize_systems(arch, signal_rank)
    total_pins, total_allocated, total_free, total_percent = allocation_summary(arch)
    output_path.write_text(
        build_html(str(arch.get("name", "Architecture")), systems, ecus, total_pins, total_allocated, total_free, total_percent),
        encoding="utf-8",
    )
    print(output_path)


if __name__ == "__main__":
    main()